"""Unit tests for eligibility hard filters, 10-point scoring, tracked gaps, and ranking."""

from pathlib import Path
import pytest
from job_digest.match import (
    check_eligibility,
    evaluate_job,
    rank_and_score_jobs,
    score_location,
)
from job_digest.models import Job
from job_digest.profile import load_profile_from_file

PROFILE = load_profile_from_file(Path(__file__).resolve().parent.parent / "profile.example.yaml")


def test_senior_and_manager_titles_excluded():
    """Verify that titles containing excluded words (senior, manager, etc.) are dropped."""
    senior_job = Job(
        title="Senior Software Engineer",
        company="Google",
        location="Bengaluru",
        canonical_url="https://example.com/1",
        description_text="Senior role",
        source="greenhouse",
    )
    eligible, reason = check_eligibility(senior_job, PROFILE)
    assert eligible is False
    assert "senior" in reason.lower()

    manager_job = Job(
        title="Product Manager",
        company="Microsoft",
        location="Noida",
        canonical_url="https://example.com/2",
        description_text="PM role",
        source="lever",
    )
    eligible, reason = check_eligibility(manager_job, PROFILE)
    assert eligible is False
    assert "manager" in reason.lower()


def test_2025_batch_only_listing_excluded():
    """Verify that a listing specifying a batch year other than 2027 is excluded."""
    batch_2025_job = Job(
        title="Graduate Trainee Engineer",
        company="Infosys",
        location="Pune",
        canonical_url="https://example.com/3",
        description_text="Hiring 2025 batch only",
        source="adzuna",
        batch_years=[2025],
    )
    eligible, reason = check_eligibility(batch_2025_job, PROFILE)
    assert eligible is False
    assert "2025" in reason

    # 2027 batch job is kept
    batch_2027_job = Job(
        title="Graduate Trainee Engineer",
        company="Infosys",
        location="Pune",
        canonical_url="https://example.com/4",
        description_text="Hiring 2027 batch",
        source="adzuna",
        batch_years=[2027],
    )
    eligible, reason = check_eligibility(batch_2027_job, PROFILE)
    assert eligible is True


def test_experience_and_salary_filters():
    """Verify jobs requiring > 2 years or listing < 3.5 LPA are excluded."""
    high_exp_job = Job(
        title="Software Engineer",
        company="Amazon",
        location="Hyderabad",
        canonical_url="https://example.com/5",
        description_text="Requires 3+ years experience",
        source="greenhouse",
        min_years=3.5,
    )
    eligible, reason = check_eligibility(high_exp_job, PROFILE)
    assert eligible is False
    assert "Required experience" in reason

    low_salary_job = Job(
        title="Junior Developer",
        company="SmallCorp",
        location="Delhi NCR",
        canonical_url="https://example.com/6",
        description_text="Low pay full-time role",
        source="adzuna",
        salary_lpa=2.4,  # Below 3.5 LPA
    )
    eligible, reason = check_eligibility(low_salary_job, PROFILE)
    assert eligible is False
    assert "Listed salary" in reason


def test_tracked_gaps_do_not_penalize_score():
    """Verify tracked gaps (Java, Spring Boot) are reported in missing_skills but not deducted."""
    job = Job(
        title="Junior Backend Developer",
        company="Fintech",
        location="Pune",
        canonical_url="https://example.com/7",
        description_text="Requires Python and FastAPI. Familiarity with Java and Spring Boot is a plus.",
        source="lever",
        skills=["Python", "FastAPI"],
        min_years=0.0,
    )

    scored = evaluate_job(job, PROFILE)
    assert scored is not None
    assert "Java" in scored.missing_skills
    assert "Spring Boot" in scored.missing_skills
    # Score should still be high (Python, FastAPI, Fresher, Pune)
    assert scored.score >= 8.0


def test_fresher_python_role_in_pune_ranks_high():
    """
    Session 8 Check verification:
    A fresher Python role in Pune ranks high (score >= 7.0, Strong category).
    """
    pune_python_job = Job(
        title="Junior Python Developer",
        company="Razorpay",
        location="Pune",
        canonical_url="https://example.com/8",
        description_text="Looking for freshers in Python, FastAPI, SQL, and Git.",
        source="greenhouse",
        skills=["Python", "FastAPI", "SQL", "Git"],
        min_years=0.0,
        is_intern=False,
    )

    scored = evaluate_job(pune_python_job, PROFILE)

    assert scored is not None
    assert scored.score >= 9.0  # 4 skills (4.0) + role (3.0) + fresher (2.0) + Pune (1.0) = 10.0
    assert scored.category == "Strong"
    assert "Preferred city: Pune" in scored.location_reason
    assert "Python" in scored.matched_skills
    assert "FastAPI" in scored.matched_skills


def test_ranking_sorts_descending():
    """Verify rank_and_score_jobs sorts candidates from highest to lowest score."""
    job_high = Job(
        title="Junior Python Developer",
        company="Razorpay",
        location="Noida",
        canonical_url="https://example.com/h",
        description_text="Python role in Noida",
        source="greenhouse",
        skills=["Python", "FastAPI", "Docker", "Git"],
        min_years=0.0,
    )

    job_medium = Job(
        title="Technical Intern",
        company="GenericTech",
        location="Chennai",  # Non-preferred Indian city (0.5 pts)
        canonical_url="https://example.com/m",
        description_text="General intern",
        source="lever",
        skills=["HTML"],  # Only 1 skill
        is_intern=True,
    )

    ranked = rank_and_score_jobs([job_medium, job_high], PROFILE)
    assert len(ranked) == 2
    assert ranked[0].score >= ranked[1].score
    assert ranked[0].job.company == "Razorpay"
