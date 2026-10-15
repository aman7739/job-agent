"""Workable job board API adapter."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

from job_digest.models import RawJob
from job_digest.sources.base import DEFAULT_USER_AGENT, is_india_or_remote

logger = logging.getLogger(__name__)


class WorkableSource:
    """Fetches jobs from public Workable company boards at apply.workable.com/<subdomain>."""

    V3_URL = "https://apply.workable.com/api/v3/accounts/{slug}/jobs"
    V1_WIDGET_URL = "https://apply.workable.com/api/v1/widget/accounts/{slug}"

    def __init__(
        self,
        slugs: List[str],
        user_agent: str = DEFAULT_USER_AGENT,
        delay_seconds: float = 0.3,
        timeout_seconds: float = 15.0,
    ):
        self.slugs = slugs
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "workable"

    async def fetch(self) -> List[RawJob]:
        """Fetch jobs across all configured Workable subdomains sequentially."""
        all_jobs: List[RawJob] = []

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds) as client:
            for idx, slug in enumerate(self.slugs):
                if idx > 0 and self.delay_seconds > 0:
                    await asyncio.sleep(self.delay_seconds)

                jobs = await self.fetch_board(client, slug)
                all_jobs.extend(jobs)

        logger.info(f"Workable fetched {len(all_jobs)} jobs across {len(self.slugs)} boards.")
        return all_jobs

    async def fetch_board(self, client: httpx.AsyncClient, slug: str) -> List[RawJob]:
        """Fetch and parse postings for a single Workable company board."""
        # Try v3 API first
        url = self.V3_URL.format(slug=slug)
        try:
            response = await client.post(url, json={"query": ""})
            if response.status_code == 404:
                # Try fallback to v1 widget
                return await self._fetch_v1_widget(client, slug)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            return self._parse_v3_results(slug, results)
        except httpx.HTTPError as exc:
            logger.warning(f"HTTP error fetching Workable board '{slug}': {exc}. Trying fallback...")
            return await self._fetch_v1_widget(client, slug)
        except Exception as exc:
            logger.warning(f"Unexpected error fetching Workable board '{slug}': {exc}. Skipping.")
            return []

    async def _fetch_v1_widget(self, client: httpx.AsyncClient, slug: str) -> List[RawJob]:
        """Fallback to Workable v1 widget endpoint."""
        url = self.V1_WIDGET_URL.format(slug=slug)
        try:
            response = await client.get(url)
            if response.status_code == 404:
                logger.warning(f"Workable board not found (404) for slug '{slug}'. Skipping.")
                return []
            response.raise_for_status()
            data = response.json()
            jobs_list = data.get("jobs", [])
            return self._parse_v1_jobs(slug, jobs_list)
        except httpx.HTTPError as exc:
            logger.warning(f"HTTP error fetching Workable widget '{slug}': {exc}. Skipping.")
            return []
        except Exception as exc:
            logger.warning(f"Unexpected error fetching Workable widget '{slug}': {exc}. Skipping.")
            return []

    def _parse_v3_results(self, slug: str, results: List[Dict[str, Any]]) -> List[RawJob]:
        parsed = []
        for item in results:
            shortcode = str(item.get("shortcode") or item.get("id") or "")
            title = (item.get("title") or "").strip()
            if not shortcode or not title:
                continue

            city = item.get("city") or ""
            state = item.get("state") or ""
            country = item.get("country") or ""
            telecommuting = item.get("telecommuting", False)

            parts = [p for p in [city, state, country] if p]
            loc_str = ", ".join(parts)
            if telecommuting and "remote" not in loc_str.lower():
                loc_str = f"{loc_str} (Remote)".strip(" ()") if loc_str else "Remote"
            elif not loc_str:
                loc_str = "Remote / Unspecified"

            pub_str = item.get("published")
            posted_at = None
            if pub_str:
                try:
                    posted_at = datetime.fromisoformat(pub_str)
                except Exception:
                    posted_at = None

            url = f"https://apply.workable.com/{slug}/j/{shortcode}/"
            job = RawJob(
                source="workable",
                source_id=slug,
                external_id=shortcode,
                title=title,
                company=slug.replace("-", " ").title(),
                location=loc_str,
                url=url,
                posted_at=posted_at,
                raw_data={"department": item.get("department")},
            )
            if is_india_or_remote(job.location):
                parsed.append(job)
        return parsed

    def _parse_v1_jobs(self, slug: str, jobs: List[Dict[str, Any]]) -> List[RawJob]:
        parsed = []
        for item in jobs:
            shortcode = str(item.get("shortcode") or "")
            title = (item.get("title") or "").strip()
            if not shortcode or not title:
                continue

            city = item.get("city") or ""
            country = item.get("country") or ""
            telecommuting = item.get("telecommuting", False)

            parts = [p for p in [city, country] if p]
            loc_str = ", ".join(parts)
            if telecommuting and "remote" not in loc_str.lower():
                loc_str = f"{loc_str} (Remote)".strip(" ()") if loc_str else "Remote"
            elif not loc_str:
                loc_str = "Remote / Unspecified"

            pub_str = item.get("published_on")
            posted_at = None
            if pub_str:
                try:
                    posted_at = datetime.fromisoformat(pub_str)
                except Exception:
                    posted_at = None

            url = item.get("url") or f"https://apply.workable.com/{slug}/j/{shortcode}/"
            job = RawJob(
                source="workable",
                source_id=slug,
                external_id=shortcode,
                title=title,
                company=slug.replace("-", " ").title(),
                location=loc_str,
                url=url,
                description_html=item.get("description"),
                posted_at=posted_at,
            )
            if is_india_or_remote(job.location):
                parsed.append(job)
        return parsed
