"""Lever job board API adapter."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from job_digest.models import RawJob
from job_digest.sources.base import DEFAULT_USER_AGENT, is_india_or_remote

logger = logging.getLogger(__name__)


class LeverSource:
    """Fetches jobs from public Lever company boards."""

    BASE_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"

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
        return "lever"

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

        logger.info(f"Lever fetched {len(all_jobs)} jobs across {len(self.slugs)} boards.")
        return all_jobs

    async def fetch_board(self, client: httpx.AsyncClient, slug: str) -> List[RawJob]:
        """Fetch and parse postings for a single Lever slug."""
        url = self.BASE_URL.format(slug=slug)
        try:
            response = await client.get(url)
            if response.status_code == 404:
                logger.warning(f"Lever board not found (404) for slug '{slug}'. Skipping.")
                return []
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"HTTP error fetching Lever board '{slug}': {exc}. Skipping.")
            return []
        except Exception as exc:
            logger.warning(f"Unexpected error fetching Lever board '{slug}': {exc}. Skipping.")
            return []

        if not isinstance(data, list):
            logger.warning(f"Expected list of postings for Lever slug '{slug}', got {type(data)}.")
            return []

        parsed_jobs: List[RawJob] = []
        for item in data:
            job = self._parse_job(slug, item)
            if job and is_india_or_remote(job.location):
                parsed_jobs.append(job)

        return parsed_jobs

    def _parse_job(self, slug: str, item: Dict[str, Any]) -> Optional[RawJob]:
        try:
            job_id = str(item.get("id", ""))
            title = (item.get("text") or "").strip()
            if not job_id or not title:
                return None

            categories = item.get("categories") or {}
            location = categories.get("location", "").strip()
            workplace_type = item.get("workplaceType", "").strip()

            combined_location = location
            if workplace_type and workplace_type.lower() == "remote":
                combined_location = f"{location} (Remote)".strip(" ()") if location else "Remote"
            elif not combined_location:
                combined_location = "Remote / Unspecified"

            # Parse createdAt timestamp (millisecond epoch)
            created_at_ms = item.get("createdAt")
            posted_at: Optional[datetime] = None
            if created_at_ms:
                try:
                    posted_at = datetime.fromtimestamp(created_at_ms / 1000.0, tz=timezone.utc)
                except Exception:
                    posted_at = None

            url = item.get("hostedUrl") or item.get("applyUrl") or f"https://jobs.lever.co/{slug}/{job_id}"
            description_html = item.get("description")
            description_text = item.get("descriptionPlain")

            return RawJob(
                source="lever",
                source_id=slug,
                external_id=job_id,
                title=title,
                company=slug.replace("-", " ").title(),
                location=combined_location,
                url=url,
                description_html=description_html,
                description_text=description_text,
                posted_at=posted_at,
                raw_data={"categories": categories, "workplaceType": workplace_type},
            )
        except Exception as exc:
            logger.debug(f"Failed to parse Lever job {item.get('id')}: {exc}")
            return None
