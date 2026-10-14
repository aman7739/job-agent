"""Jooble job search API adapter for Indian tech and fresher roles."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

from job_digest.models import RawJob
from job_digest.sources.base import DEFAULT_USER_AGENT, is_india_or_remote

logger = logging.getLogger(__name__)


class JoobleSource:
    """Fetches jobs from official Jooble API (https://jooble.org/api/about)."""

    BASE_URL = "https://jooble.org/api/{api_key}"

    ROLE_QUERIES = [
        "python developer fresher",
        "backend developer fresher",
        "software engineer trainee OR graduate engineer trainee",
        "software developer intern OR web developer intern",
        "associate software engineer OR junior software engineer",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        location: str = "India",
        user_agent: str = DEFAULT_USER_AGENT,
        delay_seconds: float = 0.5,
        timeout_seconds: float = 15.0,
        results_per_page: int = 15,
    ):
        self.api_key = api_key or os.getenv("JOOBLE_API_KEY")
        self.location = location
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.results_per_page = results_per_page

    @property
    def name(self) -> str:
        return "jooble"

    async def fetch(self) -> List[RawJob]:
        """Fetch jobs across all role query groups sequentially."""
        if not self.api_key:
            logger.info("Jooble API key (JOOBLE_API_KEY) not set. Skipping Jooble source.")
            return []

        all_jobs: List[RawJob] = []
        headers = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds) as client:
            for idx, query in enumerate(self.ROLE_QUERIES):
                if idx > 0 and self.delay_seconds > 0:
                    await asyncio.sleep(self.delay_seconds)

                jobs = await self.fetch_query(client, query)
                all_jobs.extend(jobs)

        logger.info(f"Jooble fetched {len(all_jobs)} jobs across {len(self.ROLE_QUERIES)} role groups.")
        return all_jobs

    async def fetch_query(self, client: httpx.AsyncClient, query: str, page: int = 1) -> List[RawJob]:
        """Fetch a single page of results for a query."""
        if not self.api_key:
            return []

        url = self.BASE_URL.format(api_key=self.api_key)
        payload = {
            "keywords": query,
            "location": self.location,
            "page": page,
            "resultonpage": self.results_per_page,
        }

        try:
            response = await client.post(url, json=payload)
            if response.status_code in (400, 401, 403):
                logger.warning(f"Jooble authentication or quota error ({response.status_code}). Skipping query.")
                return []
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"HTTP error fetching Jooble query '{query}': {exc}. Skipping.")
            return []
        except Exception as exc:
            logger.warning(f"Unexpected error fetching Jooble query '{query}': {exc}. Skipping.")
            return []

        jobs_data = data.get("jobs", [])
        parsed_jobs: List[RawJob] = []

        for item in jobs_data:
            job = self._parse_job(item)
            if job and is_india_or_remote(job.location):
                parsed_jobs.append(job)

        return parsed_jobs

    def _parse_job(self, item: Dict[str, Any]) -> Optional[RawJob]:
        try:
            job_id = str(item.get("id") or "")
            title = (item.get("title") or "").strip()
            if not job_id or not title:
                return None

            company = (item.get("company") or "Unknown Company").strip()
            location = (item.get("location") or "India").strip()
            url = (item.get("link") or "").strip()
            snippet = item.get("snippet") or ""

            # Parse updated/created timestamp if available
            updated_str = item.get("updated")
            posted_at: Optional[datetime] = None
            if updated_str:
                try:
                    posted_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                except Exception:
                    posted_at = None

            salary = item.get("salary") or ""

            return RawJob(
                source="jooble",
                source_id="jooble_in",
                external_id=job_id,
                title=title,
                company=company,
                location=location,
                url=url,
                description_text=snippet,
                posted_at=posted_at,
                raw_data={
                    "salary": salary,
                    "type": item.get("type"),
                    "source": item.get("source"),
                },
            )
        except Exception as exc:
            logger.debug(f"Failed to parse Jooble job {item.get('id')}: {exc}")
            return None
