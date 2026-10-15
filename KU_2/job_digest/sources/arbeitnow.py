"""Arbeitnow free remote tech jobs API adapter."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from job_digest.models import RawJob
from job_digest.sources.base import DEFAULT_USER_AGENT, is_india_or_remote

logger = logging.getLogger(__name__)


class ArbeitnowSource:
    """Fetches remote software development postings from Arbeitnow public feed."""

    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 15.0,
        max_jobs: int = 50,
    ):
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_jobs = max_jobs

    @property
    def name(self) -> str:
        return "arbeitnow"

    async def fetch(self) -> List[RawJob]:
        """Fetch remote tech jobs from Arbeitnow public API."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds) as client:
                response = await client.get(self.BASE_URL)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"HTTP error fetching Arbeitnow feed: {exc}. Returning empty list.")
            return []
        except Exception as exc:
            logger.warning(f"Unexpected error fetching Arbeitnow feed: {exc}. Returning empty list.")
            return []

        raw_items = payload.get("data", [])
        parsed_jobs: List[RawJob] = []

        for item in raw_items:
            job = self._parse_job(item)
            if job:
                # Only keep jobs that are remote or in India
                is_remote_flag = item.get("remote", False)
                if is_remote_flag or is_india_or_remote(job.location):
                    parsed_jobs.append(job)

            if len(parsed_jobs) >= self.max_jobs:
                break

        logger.info(f"Arbeitnow fetched {len(parsed_jobs)} remote tech jobs.")
        return parsed_jobs

    def _parse_job(self, item: Dict[str, Any]) -> Optional[RawJob]:
        try:
            slug = item.get("slug") or ""
            title = (item.get("title") or "").strip()
            if not slug or not title:
                return None

            company = (item.get("company_name") or "Unknown Company").strip()
            location = item.get("location") or "Remote"
            url = item.get("url") or ""
            description = item.get("description") or ""

            # Created at is a unix timestamp integer in seconds
            created_ts = item.get("created_at")
            posted_at: Optional[datetime] = None
            if created_ts:
                try:
                    posted_at = datetime.fromtimestamp(created_ts, tz=timezone.utc)
                except Exception:
                    posted_at = None

            return RawJob(
                source="arbeitnow",
                source_id="arbeitnow_feed",
                external_id=slug,
                title=title,
                company=company,
                location=location,
                url=url,
                description_text=description,
                posted_at=posted_at,
                raw_data={
                    "tags": item.get("tags", []),
                    "job_types": item.get("job_types", []),
                    "remote": item.get("remote", False),
                },
            )
        except Exception as exc:
            logger.debug(f"Failed to parse Arbeitnow job: {exc}")
            return None
