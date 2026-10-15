"""Unit tests for deduplication, fingerprinting, freshness filtering, and multi-source dedup."""

from datetime import datetime, timedelta, timezone
import pytest
from job_digest.models import Job
from job_digest.dedup import (
    calculate_fingerprint,
    deduplicate_in_memory,
    is_job_fresh,
    normalize_string_for_hash,
)


def test_fingerprint_normalization_consistency():
    """Verify fingerprints match regardless of casing, punctuation, and extra whitespace."""
    fp1 = calculate_fingerprint(
        company="Stripe, Inc.",
        title="Software Engineer - Backend",
        location="Bengaluru, India",
    )
    fp2 = calculate_fingerprint(
        company="stripe",
        title="Software Engineer Backend",
        location="Bengaluru India",
    )
    assert fp1 == fp2


def test_freshness_filter_logic():
    """Verify freshness filtering rules: <= 48h fresh, > 48h stale, None fresh."""
    now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)

    # Posted 10 hours ago -> FRESH
    posted_recent = now - timedelta(hours=10)
    assert is_job_fresh(posted_recent, now=now) is True

    # Posted exactly 48 hours ago -> FRESH
    posted_48h = now - timedelta(hours=48)
    assert is_job_fresh(posted_48h, now=now) is True

    # Posted 72 hours ago -> STALE
    posted_stale = now - timedelta(hours=72)
    assert is_job_fresh(posted_stale, now=now) is False

    # Date unknown (None) -> FRESH (first seen today)
    assert is_job_fresh(None, now=now) is True


def test_same_job_from_two_sources_counts_once():
    """
    Session 7 Check verification:
    The same job arriving from two sources counts once.
    """
    now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)

    job_from_greenhouse = Job(
        title="Associate Software Engineer",
        company="Cloudflare",
        location="Noida, India",
        canonical_url="https://boards.greenhouse.io/cloudflare/jobs/101",
        description_text="Cloudflare edge team",
        posted_at=now - timedelta(hours=4),
        source="greenhouse",
    )

    job_from_adzuna = Job(
        title="Associate Software Engineer",
        company="Cloudflare",
        location="Noida, India",
        canonical_url="https://adzuna.in/land/ad/101",
        description_text="Cloudflare edge team listing on Adzuna",
        posted_at=now - timedelta(hours=4),
        source="adzuna",
    )

    different_job = Job(
        title="Data Analyst",
        company="Swiggy",
        location="Bengaluru, India",
        canonical_url="https://swiggy.careers/jobs/202",
        description_text="Analytics role",
        posted_at=now - timedelta(hours=6),
        source="lever",
    )

    batch = [job_from_greenhouse, job_from_adzuna, different_job]

    unique_jobs, dup_count, stale_count = deduplicate_in_memory(batch, now=now)

    assert len(unique_jobs) == 2
    assert dup_count == 1
    assert stale_count == 0

    companies = [j.company for j in unique_jobs]
    assert companies == ["Cloudflare", "Swiggy"]
    # The first source (greenhouse) was kept
    assert unique_jobs[0].source == "greenhouse"


def test_stale_jobs_filtered_out():
    """Verify stale jobs (> 48 hours) are dropped from the unique fresh list."""
    now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)

    fresh_job = Job(
        title="Junior Developer",
        company="FreshCorp",
        location="Pune",
        canonical_url="https://example.com/1",
        description_text="Fresh role",
        posted_at=now - timedelta(hours=12),
        source="ashby",
    )

    old_job = Job(
        title="Senior Developer",
        company="OldCorp",
        location="Pune",
        canonical_url="https://example.com/2",
        description_text="Old role",
        posted_at=now - timedelta(hours=80),  # Stale
        source="ashby",
    )

    unique_jobs, dup_count, stale_count = deduplicate_in_memory([fresh_job, old_job], now=now)

    assert len(unique_jobs) == 1
    assert stale_count == 1
    assert unique_jobs[0].company == "FreshCorp"


def test_canonical_url_deduplication():
    """Verify jobs with the exact same canonical URL are deduplicated even if titles slightly vary."""
    now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)

    job1 = Job(
        title="Python Engineer (Noida)",
        company="Company A",
        location="Noida",
        canonical_url="https://company-a.com/jobs/999",
        description_text="Role 1",
        posted_at=now,
        source="lever",
    )

    job2 = Job(
        title="Python Engineer",
        company="Company A",
        location="Noida",
        canonical_url="https://company-a.com/jobs/999",  # Identical URL
        description_text="Role 2",
        posted_at=now,
        source="email_alerts",
    )

    unique_jobs, dup_count, stale_count = deduplicate_in_memory([job1, job2], now=now)
    assert len(unique_jobs) == 1
    assert dup_count == 1
