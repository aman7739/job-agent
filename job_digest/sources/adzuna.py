"""Adzuna job search API adapter."""

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


class AdzunaSource:
    """Fetches jobs from Adzuna Search API for country=in across 5 core role groups."""

    BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

    ROLE_QUERIES = [
        "software engineer OR web developer OR frontend OR backend OR full stack OR python",
        "machine learning OR AI engineer OR NLP OR LLM OR data scientist",
        "data analyst OR business analyst",
        "QA engineer OR software tester OR SDET",
        "software intern OR developer intern OR internship OR apprentice",
    ]

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_key: Optional[str] = None,
        country: str = "in",
        user_agent: str = DEFAULT_USER_AGENT,
        delay_seconds: float = 0.5,
        timeout_seconds: float = 15.0,
        results_per_page: int = 15,
    ):
        self.app_id = app_id or os.getenv("ADZUNA_APP_ID")
        self.app_key = app_key or os.getenv("ADZUNA_APP_KEY")
        self.country = country
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.results_per_page = results_per_page

    @property
    def name(self) -> str:
        return "adzuna"

    async def fetch(self) -> List[RawJob]:
        """Fetch jobs across all role query groups."""
        if not self.app_id or not self.app_key:
            logger.info("Adzuna credentials (ADZUNA_APP_ID / ADZUNA_APP_KEY) not set. Skipping Adzuna source.")
            return []

        all_jobs: List[RawJob] = []
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds) as client:
            for idx, query in enumerate(self.ROLE_QUERIES):
                if idx > 0 and self.delay_seconds > 0:
                    await asyncio.sleep(self.delay_seconds)

                jobs = await self.fetch_query(client, query)
                all_jobs.extend(jobs)

        logger.info(f"Adzuna fetched {len(all_jobs)} jobs across {len(self.ROLE_QUERIES)} role groups.")
        return all_jobs

    async def fetch_query(self, client: httpx.AsyncClient, query: str, page: int = 1) -> List[RawJob]:
        """Fetch a single page of results for a query."""
        url = self.BASE_URL.format(country=self.country, page=page)
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": query,
            "results_per_page": self.results_per_page,
            "content-type": "application/json",
        }

        try:
            response = await client.get(url, params=params)
            if response.status_code == 400 or response.status_code == 401 or response.status_code == 403:
                logger.warning(f"Adzuna authentication or parameter error ({response.status_code}). Skipping query.")
                return []
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"HTTP error fetching Adzuna query '{query}': {exc}. Skipping.")
            return []
        except Exception as exc:
            logger.warning(f"Unexpected error fetching Adzuna query '{query}': {exc}. Skipping.")
            return []

        results = data.get("results", [])
        parsed_jobs: List[RawJob] = []

        for item in results:
            job = self._parse_job(item)
            if job and is_india_or_remote(job.location):
                parsed_jobs.append(job)

        return parsed_jobs

    def _parse_job(self, item: Dict[str, Any]) -> Optional[RawJob]:
        try:
            job_id = str(item.get("id", ""))
            title = (item.get("title") or "").strip()
            if not job_id or not title:
                return None

            company_obj = item.get("company") or {}
            company_name = (company_obj.get("display_name") or "Unknown Company").strip()

            loc_obj = item.get("location") or {}
            location_name = (loc_obj.get("display_name") or "India").strip()

            url = item.get("redirect_url") or ""
            description_text = item.get("description")

            # Parse created timestamp
            created_str = item.get("created")
            posted_at: Optional[datetime] = None
            if created_str:
                try:
                    posted_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                except Exception:
                    posted_at = None

            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")

            return RawJob(
                source="adzuna",
                source_id="adzuna_in",
                external_id=job_id,
                title=title,
                company=company_name,
                location=location_name,
                url=url,
                description_text=description_text,
                posted_at=posted_at,
                raw_data={
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "category": item.get("category"),
                },
            )
        except Exception as exc:
            logger.debug(f"Failed to parse Adzuna job {item.get('id')}: {exc}")
            return None
