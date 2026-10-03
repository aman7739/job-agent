"""Job fingerprinting, freshness filtering, deduplication, and database upserts."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from job_digest.models import Job

logger = logging.getLogger(__name__)


COMPANY_SUFFIXES = [
    r"\b(?:pvt\.?\s*ltd\.?|private\s+limited|pvt\s+limited)\b",
    r"\b(?:inc\.?|incorporated)\b",
    r"\b(?:llc|llp)\b",
    r"\b(?:ltd\.?|limited)\b",
    r"\b(?:corp\.?|corporation)\b",
    r"\b(?:technologies|tech|solutions)\b",
]


def normalize_string_for_hash(s: str) -> str:
    """Normalize string for consistent hash generation: lowercase, remove punctuation, collapse whitespace."""
    if not s:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", s.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_company(company: str) -> str:
    """Normalize company name by stripping common corporate suffixes and punctuation."""
    norm = normalize_string_for_hash(company)
    for suffix_pat in COMPANY_SUFFIXES:
        norm = re.sub(suffix_pat, "", norm, flags=re.I)
    return re.sub(r"\s+", " ", norm).strip()


def calculate_fingerprint(company: str, title: str, location: str) -> str:
    """
    Generate SHA-256 fingerprint from normalized (company | title | location).
    """
    norm_comp = normalize_company(company)
    norm_title = normalize_string_for_hash(title)
    norm_loc = normalize_string_for_hash(location)

    combined = f"{norm_comp}|{norm_title}|{norm_loc}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def is_job_fresh(
    posted_at: Optional[datetime],
    now: Optional[datetime] = None,
    max_age_hours: float = 48.0,
) -> bool:
    """
    Determine if a job is fresh.
    Rule: Fresh means posted in the last 48 hours, or posted_at date unknown but first seen today.
    """
    if posted_at is None:
        # Date unknown: fresh when first fetched
        return True

    current_time = now or datetime.now(timezone.utc)

    # Normalize timezones for comparison
    if posted_at.tzinfo is None:
        posted_at_utc = posted_at.replace(tzinfo=timezone.utc)
    else:
        posted_at_utc = posted_at.astimezone(timezone.utc)

    if current_time.tzinfo is None:
        current_time_utc = current_time.replace(tzinfo=timezone.utc)
    else:
        current_time_utc = current_time.astimezone(timezone.utc)

    age = current_time_utc - posted_at_utc
    return age <= timedelta(hours=max_age_hours)


class DeduplicationResult(BaseModel):
    """Result of running deduplication and freshness filtering."""

    new_jobs: List[Job]
    already_seen_jobs: List[Job]
    stale_count: int = 0
    duplicate_count: int = 0

    @property
    def total_fresh(self) -> int:
        return len(self.new_jobs) + len(self.already_seen_jobs)


def deduplicate_in_memory(
    jobs: List[Job],
    now: Optional[datetime] = None,
    max_age_hours: float = 48.0,
) -> Tuple[List[Job], int, int]:
    """
    Deduplicate a list of normalized jobs in memory based on fingerprint and canonical URL,
    and filter out stale jobs.
    Returns: (unique_fresh_jobs, duplicate_count, stale_count)
    """
    unique_jobs: List[Job] = []
    seen_fingerprints: Set[str] = set()
    seen_urls: Set[str] = set()

    duplicate_count = 0
    stale_count = 0

    for job in jobs:
        # 1. Freshness check
        if not is_job_fresh(job.posted_at, now=now, max_age_hours=max_age_hours):
            stale_count += 1
            continue

        # 2. Fingerprint calculation
        fp = calculate_fingerprint(job.company, job.title, job.location)
        job.fingerprint = fp

        # 3. Duplicate check by fingerprint or canonical_url
        if fp in seen_fingerprints or (job.canonical_url and job.canonical_url in seen_urls):
            duplicate_count += 1
            continue

        seen_fingerprints.add(fp)
        if job.canonical_url:
            seen_urls.add(job.canonical_url)

        unique_jobs.append(job)

    return unique_jobs, duplicate_count, stale_count


def process_and_upsert_jobs(
    jobs: List[Job],
    session: Optional[Session] = None,
    now: Optional[datetime] = None,
    max_age_hours: float = 48.0,
) -> DeduplicationResult:
    """
    Perform complete deduplication and freshness pipeline:
    1. Filter stale jobs and deduplicate in-memory.
    2. Check against seen_jobs table in database to classify as 'new' vs 'already seen'.
    3. Upsert into seen_jobs and jobs tables.
    """
    unique_fresh, dup_count, stale_count = deduplicate_in_memory(
        jobs, now=now, max_age_hours=max_age_hours
    )

    if session is None:
        # Standalone / offline mode without DB
        return DeduplicationResult(
            new_jobs=unique_fresh,
            already_seen_jobs=[],
            stale_count=stale_count,
            duplicate_count=dup_count,
        )

    new_jobs: List[Job] = []
    already_seen_jobs: List[Job] = []

    # Query seen fingerprints from DB
    fingerprints = [j.fingerprint for j in unique_fresh if j.fingerprint]
    existing_fps: Set[str] = set()
    if fingerprints:
        rows = session.execute(
            text("SELECT fingerprint FROM seen_jobs WHERE fingerprint = ANY(:fps)"),
            {"fps": fingerprints},
        ).fetchall()
        existing_fps = {r[0] for r in rows}

    current_ts = now or datetime.now(timezone.utc)

    for job in unique_fresh:
        fp = job.fingerprint
        if not fp:
            continue

        if fp in existing_fps:
            # Already seen job: update last_seen_at
            session.execute(
                text(
                    """
                    UPDATE seen_jobs
                    SET last_seen_at = :now, canonical_url = :url
                    WHERE fingerprint = :fp
                    """
                ),
                {"now": current_ts, "url": job.canonical_url, "fp": fp},
            )
            already_seen_jobs.append(job)
        else:
            # Brand new job: insert into seen_jobs
            session.execute(
                text(
                    """
                    INSERT INTO seen_jobs (fingerprint, canonical_url, first_seen_at, last_seen_at, status)
                    VALUES (:fp, :url, :now, :now, 'seen')
                    ON CONFLICT (fingerprint) DO UPDATE SET last_seen_at = :now
                    """
                ),
                {"fp": fp, "url": job.canonical_url, "now": current_ts},
            )
            new_jobs.append(job)

        # Upsert into jobs table
        session.execute(
            text(
                """
                INSERT INTO jobs (
                    fingerprint, title, company, location, canonical_url,
                    description_text, posted_at, source, is_intern, is_apprentice,
                    min_years, salary_lpa, stipend, batch_years, matched_skills,
                    raw_data, updated_at
                ) VALUES (
                    :fp, :title, :company, :location, :url,
                    :desc, :posted_at, :source, :is_intern, :is_apprentice,
                    :min_years, :salary_lpa, :stipend, :batch_years, :skills,
                    :raw_data, :now
                )
                ON CONFLICT (fingerprint) DO UPDATE SET
                    canonical_url = EXCLUDED.canonical_url,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "fp": fp,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.canonical_url,
                "desc": job.description_text,
                "posted_at": job.posted_at,
                "source": job.source,
                "is_intern": job.is_intern,
                "is_apprentice": job.is_apprentice,
                "min_years": job.min_years,
                "salary_lpa": job.salary_lpa,
                "stipend": job.stipend,
                "batch_years": job.batch_years,
                "skills": job.skills,
                "raw_data": json.dumps(job.raw_data or {}),
                "now": current_ts,
            },
        )

    session.commit()

    return DeduplicationResult(
        new_jobs=new_jobs,
        already_seen_jobs=already_seen_jobs,
        stale_count=stale_count,
        duplicate_count=dup_count,
    )
