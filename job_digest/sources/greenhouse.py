"""Greenhouse job board API adapter."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

from job_digest.models import RawJob
from job_digest.sources.base import DEFAULT_USER_AGENT, is_india_or_remote

logger = logging.getLogger(__name__)


class GreenhouseSource:
    """Fetches jobs from public Greenhouse company boards."""

    BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"

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
        return "greenhouse"

    async def fetch(self) -> List[RawJob]:
        """Fetch jobs across all configured company slugs sequentially."""
        all_jobs: List[RawJob] = []

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds) as client:
            for idx, slug in enumerate(self.slugs):
                if idx > 0 and self.delay_seconds > 0:
                    await asyncio.sleep(self.delay_seconds)

                jobs = await self.fetch_board(client, slug)
                all_jobs.extend(jobs)

        logger.info(f"Greenhouse fetched {len(all_jobs)} jobs across {len(self.slugs)} boards.")
        return all_jobs

    async def fetch_board(self, client: httpx.AsyncClient, slug: str) -> List[RawJob]:
        """Fetch and parse openings for a single Greenhouse slug."""
        url = self.BASE_URL.format(slug=slug)
        try:
            response = await client.get(url)
            if response.status_code == 404:
                logger.warning(f"Greenhouse board not found (404) for slug '{slug}'. Skipping.")
                return []
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"HTTP error fetching Greenhouse board '{slug}': {exc}. Skipping.")
            return []
        except Exception as exc:
            logger.warning(f"Unexpected error fetching Greenhouse board '{slug}': {exc}. Skipping.")
            return []

        raw_jobs_list = data.get("jobs", [])
        parsed_jobs: List[RawJob] = []

        for item in raw_jobs_list:
            job = self._parse_job(slug, item)
            if job and is_india_or_remote(job.location):
                parsed_jobs.append(job)

        return parsed_jobs

    def _parse_job(self, slug: str, item: Dict[str, Any]) -> Optional[RawJob]:
        try:
            job_id = str(item.get("id", ""))
            title = (item.get("title") or "").strip()
            if not job_id or not title:
                return None

            location_obj = item.get("location") or {}
            location_name = location_obj.get("name", "").strip() or "Remote / Unspecified"

            # Parse posted_at / updated_at
            updated_str = item.get("updated_at")
            posted_at: Optional[datetime] = None
            if updated_str:
                try:
                    posted_at = datetime.fromisoformat(updated_str)
                except Exception:
                    posted_at = None

            url = item.get("absolute_url") or f"https://boards.greenhouse.io/{slug}/jobs/{job_id}"
            description_html = item.get("content")

            return RawJob(
                source="greenhouse",
                source_id=slug,
                external_id=job_id,
                title=title,
                company=slug.replace("-", " ").title(),
                location=location_name,
                url=url,
                description_html=description_html,
                posted_at=posted_at,
                raw_data={"departments": item.get("departments"), "offices": item.get("offices")},
            )
        except Exception as exc:
            logger.debug(f"Failed to parse Greenhouse job {item.get('id')}: {exc}")
            return None
