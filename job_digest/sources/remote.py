"""Remotive remote job feed adapter with rate limiting and attribution."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from job_digest.models import RawJob
from job_digest.sources.base import DEFAULT_USER_AGENT, is_india_or_remote

logger = logging.getLogger(__name__)

# State tracker file for daily fetch count safeguard (max 4 per day)
STATE_FILE = Path(__file__).resolve().parent.parent.parent / ".remotive_fetch_state.json"
MAX_DAILY_FETCHES = 4


def _check_and_increment_daily_fetch() -> bool:
    """
    Ensure Remotive is fetched at most 4 times in a calendar day.
    Returns True if permitted, False if limit reached.
    """
    today_str = date.today().isoformat()
    state = {"date": today_str, "count": 0}

    if STATE_FILE.is_file():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today_str:
                    state = data
        except Exception:
            pass

    if state["count"] >= MAX_DAILY_FETCHES:
        logger.warning(
            f"Remotive daily fetch limit reached ({state['count']}/{MAX_DAILY_FETCHES} fetches today). Skipping to obey API terms."
        )
        return False

    state["count"] += 1
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as exc:
        logger.debug(f"Could not persist Remotive fetch state: {exc}")

    return True


class RemotiveSource:
    """Fetches remote engineering jobs from Remotive API with mandatory attribution."""

    BASE_URL = "https://remotive.com/api/remote-jobs?category=software-dev&limit=50"
    ATTRIBUTION = "Jobs provided by Remotive (https://remotive.com)"

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 15.0,
        enforce_rate_limit: bool = True,
    ):
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.enforce_rate_limit = enforce_rate_limit

    @property
    def name(self) -> str:
        return "remotive"

    async def fetch(self) -> List[RawJob]:
        """Fetch remote jobs adhering to max 4 fetches/day and location constraints."""
        if self.enforce_rate_limit and not _check_and_increment_daily_fetch():
            return []

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds) as client:
                response = await client.get(self.BASE_URL)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"HTTP error fetching Remotive feed: {exc}. Skipping.")
            return []
        except Exception as exc:
            logger.warning(f"Unexpected error fetching Remotive feed: {exc}. Skipping.")
            return []

        raw_jobs_list = data.get("jobs", [])
        parsed_jobs: List[RawJob] = []

        for item in raw_jobs_list:
            job = self._parse_job(item)
            if job:
                req_loc = (item.get("candidate_required_location") or "").lower()
                # Accept if location requires anywhere, worldwide, india, apac, or is blank/remote
                if (
                    not req_loc
                    or "anywhere" in req_loc
                    or "world" in req_loc
                    or "india" in req_loc
                    or "apac" in req_loc
                    or is_india_or_remote(req_loc)
                ):
                    parsed_jobs.append(job)

        logger.info(f"Remotive fetched {len(parsed_jobs)} jobs matching India/Worldwide remote criteria.")
        return parsed_jobs

    def _parse_job(self, item: Dict[str, Any]) -> Optional[RawJob]:
        try:
            job_id = str(item.get("id", ""))
            title = (item.get("title") or "").strip()
            if not job_id or not title:
                return None

            company = (item.get("company_name") or "Unknown Company").strip()
            req_loc = (item.get("candidate_required_location") or "Remote").strip()
            loc_str = f"Remote ({req_loc})" if req_loc else "Remote"

            pub_str = item.get("publication_date")
            posted_at: Optional[datetime] = None
            if pub_str:
                try:
                    posted_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except Exception:
                    posted_at = None

            url = item.get("url") or f"https://remotive.com/remote-jobs/{job_id}"
            description_html = item.get("description")
            salary_str = item.get("salary") or ""

            return RawJob(
                source="remotive",
                source_id="remotive_feed",
                external_id=job_id,
                title=title,
                company=company,
                location=loc_str,
                url=url,
                description_html=description_html,
                posted_at=posted_at,
                raw_data={
                    "salary_text": salary_str,
                    "category": item.get("category"),
                    "tags": item.get("tags"),
                    "attribution": self.ATTRIBUTION,
                },
            )
        except Exception as exc:
            logger.debug(f"Failed to parse Remotive job {item.get('id')}: {exc}")
            return None
