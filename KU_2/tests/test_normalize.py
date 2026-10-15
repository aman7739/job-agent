"""Unit tests for normalization: HTML stripping, location cleaning, URL canonicalization, traps, and 15 sample descriptions."""

import pytest
from job_digest.models import RawJob
from job_digest.normalize import (
    canonicalize_url,
    clean_html_and_text,
    clean_location,
    detect_experience_and_batch,
    extract_skills,
    normalize_raw_job,
    parse_salary_and_stipend,
)
from job_digest.profile import load_profile_from_file
from pathlib import Path

SAMPLE_PROFILE = load_profile_from_file(Path(__file__).resolve().parent.parent / "profile.example.yaml")


def test_url_canonicalization():
    """Verify tracking parameters are removed and URLs normalized."""
    dirty_url = "https://boards.greenhouse.io/stripe/jobs/12345/?utm_source=linkedin&gh_jid=12345&ref=tracker"
    clean = canonicalize_url(dirty_url)
    assert clean == "https://boards.greenhouse.io/stripe/jobs/12345"


def test_clean_location():
    """Verify city names are normalized."""
    assert clean_location("Gurgaon, Haryana") == "Gurugram"
    assert clean_location("Calcutta") == "Kolkata"
    assert clean_location("Bombay") == "Mumbai"
    assert clean_location("Bangalore") == "Bengaluru"
    assert clean_location("Delhi NCR") == "Delhi NCR"
    assert clean_location("New Delhi") == "Delhi NCR"


# --- 15 Sample Description Tests (Session 6 Check) ---

def test_desc_1_c_programming_language():
    """Sample 1: 'C programming' should extract 'C'."""
    text = "Requires strong knowledge of C programming, data structures, and algorithms."
    skills = extract_skills(text, profile=SAMPLE_PROFILE)
    assert "C" in skills
    assert "Data Structures" in skills
    assert "Algorithms" in skills


def test_desc_2_c_trap_avoidance():
    """Sample 2: 'Vitamin C' / 'Section C' must NOT extract 'C'."""
    text = "Join our dynamic team. Looking for candidates with high Vitamin C energy and leadership in Section C."
    skills = extract_skills(text, profile=SAMPLE_PROFILE)
    assert "C" not in skills


def test_desc_3_c_plus_plus_slash_c():
    """Sample 3: 'C/C++' should extract both 'C' and 'C++'."""
    text = "Looking for developers proficient in C/C++ and Linux system internals."
    skills = extract_skills(text, profile=SAMPLE_PROFILE)
    assert "C" in skills
    assert "C++" in skills
    assert "Linux" in skills


def test_desc_4_go_programming_language():
    """Sample 4: 'Go programming' / 'Golang' should extract 'Go'."""
    text = "Building backend microservices using Go programming language and Docker."
    skills = extract_skills(text, profile=SAMPLE_PROFILE)
    assert "Go" in skills
    assert "Docker" in skills


def test_desc_5_go_trap_avoidance():
    """Sample 5: 'go through' / 'go beyond' must NOT extract 'Go'."""
    text = "We want you to go through our training program and go beyond expectations."
    skills = extract_skills(text, profile=SAMPLE_PROFILE)
    assert "Go" not in skills


def test_desc_6_rest_trap_avoidance():
    """Sample 6: 'the rest of the team' must NOT extract 'REST API'."""
    text = "You will collaborate with the rest of the team to deliver amazing product features."
    skills = extract_skills(text, profile=SAMPLE_PROFILE)
    assert "REST API" not in skills


def test_desc_7_rest_api_valid():
    """Sample 7: 'RESTful API' should extract 'REST API'."""
    text = "Proficient in developing RESTful APIs using FastAPI and PostgreSQL database."
    skills = extract_skills(text, profile=SAMPLE_PROFILE)
    assert "REST API" in skills
    assert "FastAPI" in skills
    assert "PostgreSQL" in skills


def test_desc_8_salary_format_1_lpa_range():
    """Sample 8: Format 1 - LPA Range ('6-10 LPA')."""
    text = "Full-time Software Developer. Compensation: 6-10 LPA depending on candidate experience."
    lpa, stipend = parse_salary_and_stipend(text, is_intern=False)
    assert lpa == 6.0
    assert stipend is None


def test_desc_9_salary_format_1_single_lpa():
    """Sample 9: Format 1 - Single LPA ('₹4.5 LPA')."""
    text = "Junior Python Engineer. Offering ₹4.5 LPA plus health benefits and performance bonus."
    lpa, stipend = parse_salary_and_stipend(text, is_intern=False)
    assert lpa == 4.5
    assert stipend is None


def test_desc_10_salary_format_2_yearly_inr():
    """Sample 10: Format 2 - Absolute INR per annum ('₹600,000 - ₹900,000 per annum')."""
    text = "Associate Backend Engineer. Annual CTC: ₹600,000 - ₹900,000 per annum."
    lpa, stipend = parse_salary_and_stipend(text, is_intern=False)
    assert lpa == 6.0
    assert stipend is None


def test_desc_11_salary_format_3_intern_stipend():
    """Sample 11: Format 3 - Monthly stipend ('₹25,000/month stipend')."""
    text = "Frontend Developer Internship. Monthly stipend: ₹25,000/month."
    lpa, stipend = parse_salary_and_stipend(text, is_intern=True)
    assert lpa is None
    assert stipend == 25000.0


def test_desc_12_salary_format_3_fulltime_monthly():
    """Sample 12: Format 3 - Full-time monthly in-hand ('₹30,000 per month' -> 3.6 LPA)."""
    text = "Junior Web Developer. In-hand salary: ₹30,000 per month."
    lpa, stipend = parse_salary_and_stipend(text, is_intern=False)
    assert lpa == 3.6
    assert stipend is None


def test_desc_13_salary_format_4_usd_annual():
    """Sample 13: Format 4 - USD annual converted to estimated LPA ('$40,000 - $60,000 / year')."""
    text = "Remote Full Stack Engineer. Compensation: $40,000 - $60,000 / year."
    lpa, stipend = parse_salary_and_stipend(text, is_intern=False)
    assert lpa == 33.6
    assert stipend is None


def test_desc_14_batch_year_and_experience():
    """Sample 14: Batch year '2027 batch' and experience '0-1 years'."""
    text = "Campus hiring for 2027 batch B.Tech freshers with 0-1 years of experience in Python."
    min_exp, is_intern, is_apprentice, batches = detect_experience_and_batch(text, "Graduate Trainee")
    assert batches == [2027]
    assert min_exp == 0.0
    assert is_intern is False


def test_desc_15_html_cleaning_and_full_job_normalization():
    """Sample 15: Full RawJob normalization with HTML stripping, location, and intern flags."""
    raw = RawJob(
        source="greenhouse",
        source_id="company_test",
        external_id="gh-789",
        title="Software Engineering Intern",
        company="TechCorp",
        location="Gurgaon, Delhi NCR",
        url="https://boards.greenhouse.io/techcorp/jobs/789?utm_source=feed",
        description_html="""
            <div>
                <h1>Internship Program</h1>
                <p>Welcome! We are looking for <strong>React</strong> and <strong>Python</strong> interns.</p>
                <p>Stipend: ₹20,000 per month. Freshers welcome.</p>
            </div>
        """,
    )

    job = normalize_raw_job(raw, profile=SAMPLE_PROFILE)

    assert job.title == "Software Engineering Intern"
    assert job.company == "TechCorp"
    assert job.location == "Gurugram, Delhi NCR"
    assert job.canonical_url == "https://boards.greenhouse.io/techcorp/jobs/789"
    assert "<" not in job.description_text
    assert "Internship Program" in job.description_text
    assert job.is_intern is True
    assert job.stipend == 20000.0
    assert job.min_years == 0.0
    assert "Python" in job.skills
    assert "React" in job.skills
