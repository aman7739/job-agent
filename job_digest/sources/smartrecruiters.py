"""SmartRecruiters job board API adapter."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

from job_digest.models import RawJob
from job_digest.sources.base import DEFAULT_USER_AGENT, is_india_or_remote

logger = logging.getLogger(__name__)


class SmartRecruitersSource:
    """Fetches jobs from public SmartRecruiters company postings API."""

    BASE_URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"

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
        return "smartrecruiters"

    async def fetch(self) -> List[RawJob]:
        """Fetch jobs across all configured SmartRecruiters company IDs sequentially."""
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

        logger.info(f"SmartRecruiters fetched {len(all_jobs)} jobs across {len(self.slugs)} boards.")
        return all_jobs

    async def fetch_board(self, client: httpx.AsyncClient, slug: str) -> List[RawJob]:
        """Fetch and parse postings for a single SmartRecruiters company ID."""
        url = self.BASE_URL.format(slug=slug)
        try:
            response = await client.get(url)
            if response.status_code == 404:
                logger.warning(f"SmartRecruiters board not found (404) for slug '{slug}'. Skipping.")
                return []
            if response.status_code == 403:
                logger.warning(
                    f"SmartRecruiters access restricted (403) for slug '{slug}' (depends on customer plan). Skipping."
                )
                return []
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"HTTP error fetching SmartRecruiters board '{slug}': {exc}. Skipping.")
            return []
        except Exception as exc:
            logger.warning(f"Unexpected error fetching SmartRecruiters board '{slug}': {exc}. Skipping.")
            return []

        raw_postings = data.get("content", [])
        if not isinstance(raw_postings, list):
            logger.warning(f"Unexpected data format from SmartRecruiters for slug '{slug}'.")
            return []

        parsed_jobs: List[RawJob] = []
        for item in raw_postings:
            job = self._parse_job(slug, item)
            if job and is_india_or_remote(job.location):
                parsed_jobs.append(job)

        return parsed_jobs

    def _parse_job(self, slug: str, item: Dict[str, Any]) -> Optional[RawJob]:
        try:
            job_id = str(item.get("id", ""))
            title = (item.get("name") or "").strip()
            if not job_id or not title:
                return None

            company_data = item.get("company") or {}
            company_name = company_data.get("name") or slug.replace("-", " ").title()

            loc_obj = item.get("location") or {}
            full_loc = loc_obj.get("fullLocation") or ""
            city = loc_obj.get("city") or ""
            country = loc_obj.get("country") or ""
            is_remote = loc_obj.get("remote", False)

            if full_loc:
                location = full_loc
            elif city and country:
                location = f"{city}, {country}"
            elif is_remote:
                location = "Remote"
            else:
                location = city or country or "Remote / Unspecified"

            if is_remote and "remote" not in location.lower():
                location = f"{location} (Remote)"

            # Parse releasedDate timestamp
            released_str = item.get("releasedDate")
            posted_at: Optional[datetime] = None
            if released_str:
                try:
                    posted_at = datetime.fromisoformat(released_str)
                except Exception:
                    posted_at = None

            url = f"https://jobs.smartrecruiters.com/{slug}/{job_id}"

            return RawJob(
                source="smartrecruiters",
                source_id=slug,
                external_id=job_id,
                title=title,
                company=company_name,
                location=location,
                url=url,
                posted_at=posted_at,
                raw_data={
                    "refNumber": item.get("refNumber"),
                    "experienceLevel": item.get("experienceLevel"),
                    "typeOfEmployment": item.get("typeOfEmployment"),
                },
            )
        except Exception as exc:
            logger.debug(f"Failed to parse SmartRecruiters job {item.get('id')}: {exc}")
            return None
