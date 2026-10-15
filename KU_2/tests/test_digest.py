"""Unit tests for digest builder, Jinja2 template rendering, section partitioning, and zero-job days."""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from job_digest.digest import build_digest, partition_and_cap_jobs
from job_digest.match import ScoredJob
from job_digest.models import Job
from job_digest.profile import load_profile_from_file

PROFILE = load_profile_from_file(Path(__file__).resolve().parent.parent / "profile.example.yaml")


def test_zero_new_jobs_renders_nothing_new_digest():
    """
    Session 9 Check verification:
    A day with zero new jobs still renders a short 'nothing new' digest.
    """
    digest = build_digest(
        scored_jobs=[],
        new_count=0,
        seen_count=45,
        failed_sources=[],
        profile=PROFILE,
    )

    assert digest.is_empty is True
    assert digest.total_jobs == 0
    assert digest.internships_count == 0
    assert digest.fulltime_count == 0

    # HTML contains friendly empty state
    assert "No new matching jobs found this morning" in digest.content_html
    assert "45" in digest.content_html  # Displays previously tracked count

    # Plain text contains friendly empty state
    assert "No new matching jobs found this morning" in digest.content_text
    assert "45" in digest.content_text


def test_digest_renders_both_sections_with_strong_and_maybe():
    """Verify both Internships and Full-Time sections render Strong and Maybe buckets."""
    job_intern_strong = ScoredJob(
        job=Job(
            title="Backend Engineering Intern",
            company="Razorpay",
            location="Bengaluru, India",
            canonical_url="https://example.com/intern-strong",
            description_text="Internship in Python and FastAPI",
            source="greenhouse",
            is_intern=True,
            stipend=30000.0,
        ),
        score=8.5,
        category="Strong",
        matched_skills=["Python", "FastAPI"],
        missing_skills=["Docker"],
        location_reason="India location",
    )

    job_intern_maybe = ScoredJob(
        job=Job(
            title="Web Development Intern",
            company="Startup Labs",
            location="Remote",
            canonical_url="https://example.com/intern-maybe",
            description_text="HTML CSS intern",
            source="lever",
            is_intern=True,
        ),
        score=5.5,
        category="Maybe",
        matched_skills=["HTML", "CSS"],
        location_reason="Remote role",
    )

    job_ft_strong = ScoredJob(
        job=Job(
            title="Junior Software Engineer",
            company="Cloudflare",
            location="Noida, India",
            canonical_url="https://example.com/ft-strong",
            description_text="Fresher engineer",
            source="greenhouse",
            is_intern=False,
            salary_lpa=8.0,
        ),
        score=9.0,
        category="Strong",
        matched_skills=["Python", "SQL", "Git"],
        location_reason="Preferred city: Noida",
    )

    job_ft_maybe = ScoredJob(
        job=Job(
            title="Software Developer",
            company="Tech Corp",
            location="Pune, India",
            canonical_url="https://example.com/ft-maybe",
            description_text="Developer role",
            source="remotive",
            is_intern=False,
        ),
        score=6.0,
        category="Maybe",
        matched_skills=["Git"],
        location_reason="Preferred city: Pune",
    )

    scored_list = [job_intern_strong, job_intern_maybe, job_ft_strong, job_ft_maybe]

    digest = build_digest(
        scored_jobs=scored_list,
        new_count=4,
        seen_count=12,
        failed_sources=["Workable"],
        profile=PROFILE,
    )

    assert digest.is_empty is False
    assert digest.total_jobs == 4
    assert digest.internships_count == 2
    assert digest.fulltime_count == 2

    # Check HTML content
    html = digest.content_html
    assert "1. Internships &amp; Apprenticeships" in html
    assert "2. Full-Time Roles" in html
    assert "Strong Matches (&ge; 7.0)" in html
    assert "Possible Matches (4.0 - 6.9)" in html
    assert "Backend Engineering Intern" in html
    assert "Junior Software Engineer" in html
    assert "₹30,000/month" in html
    assert "8.0 LPA" in html
    assert "Workable" in html  # Failed source notice
    assert "Remotive" in html  # Remotive credit

    # Apply link appears first
    assert 'href="https://example.com/intern-strong" class="apply-btn"' in html

    # Check text content
    text_content = digest.content_text
    assert "1. INTERNSHIPS & APPRENTICESHIPS" in text_content
    assert "2. FULL-TIME ROLES" in text_content
    assert "Apply: https://example.com/ft-strong" in text_content
    assert "[Notice: The following sources were unreachable today: Workable]" in text_content


def test_max_items_cap_enforced():
    """Verify that jobs exceeding max_items (e.g. 40) are capped."""
    many_jobs = [
        ScoredJob(
            job=Job(
                title=f"Engineer {i}",
                company="Corp",
                location="Pune",
                canonical_url=f"https://example.com/{i}",
                description_text="Test",
                source="lever",
                is_intern=False,
            ),
            score=7.0 + (i % 3),
            category="Strong",
        )
        for i in range(50)
    ]

    i_str, i_may, ft_str, ft_may = partition_and_cap_jobs(many_jobs, max_items=40)
    total = len(i_str) + len(i_may) + len(ft_str) + len(ft_may)
    assert total == 40
