"""Ashby job board API adapter."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

from job_digest.models import RawJob
from job_digest.sources.base import DEFAULT_USER_AGENT, is_india_or_remote

logger = logging.getLogger(__name__)


class AshbySource:
    """Fetches jobs from public Ashby company boards."""

    BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"

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
        return "ashby"

    async def fetch(self) -> List[RawJob]:
        """Fetch jobs across all configured Ashby slugs sequentially."""
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

        logger.info(f"Ashby fetched {len(all_jobs)} jobs across {len(self.slugs)} boards.")
        return all_jobs

    async def fetch_board(self, client: httpx.AsyncClient, slug: str) -> List[RawJob]:
        """Fetch and parse postings for a single Ashby board slug."""
        url = self.BASE_URL.format(slug=slug)
        try:
            response = await client.get(url)
            if response.status_code == 404:
                logger.warning(f"Ashby board not found (404) for slug '{slug}'. Skipping.")
                return []
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"HTTP error fetching Ashby board '{slug}': {exc}. Skipping.")
            return []
        except Exception as exc:
            logger.warning(f"Unexpected error fetching Ashby board '{slug}': {exc}. Skipping.")
            return []

        raw_jobs_list = data.get("jobs", [])
        parsed_jobs: List[RawJob] = []

        for item in raw_jobs_list:
            # Skip postings that are unlisted
            if not item.get("isListed", True):
                continue

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

            location = (item.get("location") or "").strip()
            secondary_locations = item.get("secondaryLocations") or []
            if secondary_locations:
                sec_names = [sec.get("location", "") for sec in secondary_locations if isinstance(sec, dict)]
                if sec_names:
                    location = f"{location}; " + "; ".join(sec_names) if location else "; ".join(sec_names)

            if not location:
                location = "Remote / Unspecified"

            # Parse publishedAt timestamp
            pub_str = item.get("publishedAt")
            posted_at: Optional[datetime] = None
            if pub_str:
                try:
                    posted_at = datetime.fromisoformat(pub_str)
                except Exception:
                    posted_at = None

            url = item.get("jobUrl") or item.get("applyUrl") or f"https://jobs.ashbyhq.com/{slug}/{job_id}"
            description_html = item.get("descriptionHtml")
            description_text = item.get("descriptionPlain")

            return RawJob(
                source="ashby",
                source_id=slug,
                external_id=job_id,
                title=title,
                company=slug.replace("-", " ").title(),
                location=location,
                url=url,
                description_html=description_html,
                description_text=description_text,
                posted_at=posted_at,
                raw_data={
                    "department": item.get("department"),
                    "compensation": item.get("compensation"),
                },
            )
        except Exception as exc:
            logger.debug(f"Failed to parse Ashby job {item.get('id')}: {exc}")
            return None
