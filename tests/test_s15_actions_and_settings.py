"""Unit and integration tests for Session 15: Actions, status updates, settings editor, source health, and manual job entry."""

import os
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from job_digest.auth import create_session_token, hash_password
from job_digest.match import check_eligibility, evaluate_job
from job_digest.models import Job
from job_digest.profile import load_profile
from job_digest.profile_service import get_active_profile_from_db, save_profile_to_db
from job_digest.status import get_job_status, get_weekly_applied_count, set_job_status
from job_digest.web import app, get_db

TEST_PASSWORD = "testpassword123"
TEST_HASH = hash_password(TEST_PASSWORD)

SQLITE_S15_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    fingerprint VARCHAR(64) PRIMARY KEY,
    canonical_url TEXT NOT NULL,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified_at TIMESTAMP,
    status VARCHAR(32) NOT NULL DEFAULT 'seen',
    saved_at TIMESTAMP,
    applied_at TIMESTAMP,
    not_interested_at TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint VARCHAR(64) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    canonical_url TEXT NOT NULL,
    description_text TEXT,
    posted_at TIMESTAMP,
    source VARCHAR(64) NOT NULL,
    is_intern BOOLEAN NOT NULL DEFAULT 0,
    is_apprentice BOOLEAN NOT NULL DEFAULT 0,
    min_years NUMERIC(3, 1),
    salary_lpa NUMERIC(6, 2),
    stipend NUMERIC(8, 2),
    score NUMERIC(4, 2)
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INT NOT NULL,
    profile_yaml TEXT NOT NULL,
    profile_data TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name VARCHAR(64) NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    jobs_found INT NOT NULL DEFAULT 0,
    jobs_new INT NOT NULL DEFAULT 0,
    is_success BOOLEAN NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_jobs INT NOT NULL DEFAULT 0,
    internships_count INT NOT NULL DEFAULT 0,
    fulltime_count INT NOT NULL DEFAULT 0,
    channels_notified TEXT DEFAULT '[]',
    failed_sources TEXT DEFAULT '[]',
    content_html TEXT,
    content_text TEXT
);
"""

EXAMPLE_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "profile.example.yaml")
with open(EXAMPLE_PROFILE_PATH, "r", encoding="utf-8") as f:
    INITIAL_YAML = f.read()


@pytest.fixture
def client_and_session(monkeypatch):
    """Provides a TestClient and SessionLocal connected to a populated in-memory SQLite database."""
    monkeypatch.setenv("DASHBOARD_PASSWORD_HASH", TEST_HASH)
    monkeypatch.setenv("DASHBOARD_PASSWORD", TEST_PASSWORD)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        for stmt in SQLITE_S15_SCHEMA.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
        conn.commit()

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Seed initial profile in database as version 1
    save_profile_to_db(session, INITIAL_YAML)

    # Seed sample job
    session.execute(
        text(
            """
            INSERT INTO seen_jobs (fingerprint, canonical_url, status)
            VALUES ('fp_target_01', 'https://example.com/target', 'seen')
            """
        )
    )
    session.execute(
        text(
            """
            INSERT INTO jobs (fingerprint, title, company, location, canonical_url, source, score)
            VALUES ('fp_target_01', 'Python Developer', 'Razorpay', 'Bengaluru', 'https://example.com/target', 'lever', 8.2)
            """
        )
    )

    # Seed sample source_run
    session.execute(
        text(
            """
            INSERT INTO source_runs (source_name, jobs_found, is_success, error_message)
            VALUES ('greenhouse', 12, 1, NULL),
                   ('remotive', 0, 0, 'Rate limit reached')
            """
        )
    )
    session.commit()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, follow_redirects=False)
    token = create_session_token("admin")
    client.cookies.set("session_token", token)

    yield client, session

    session.close()
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Interactive Job Status Actions & Weekly Applied Count
# ==============================================================================

def test_update_job_status_actions(client_and_session):
    """
    Session 15 Check:
    Buttons for saved, applied and not interested; status transitions and timestamps.
    """
    client, session = client_and_session
    fp = "fp_target_01"

    # 1. Action: Save Job
    res_save = client.post(
        f"/jobs/{fp}/status",
        data={"status": "saved", "notes": "Saved for later review"},
    )
    assert res_save.status_code == 303

    status_saved = get_job_status(session, fp)
    assert status_saved["status"] == "saved"
    assert status_saved["saved_at"] is not None
    assert status_saved["notes"] == "Saved for later review"

    # 2. Action: Applied Job
    res_applied = client.post(
        f"/jobs/{fp}/status",
        data={"status": "applied", "notes": "Applied on portal with resume v3"},
    )
    assert res_applied.status_code == 303

    status_applied = get_job_status(session, fp)
    assert status_applied["status"] == "applied"
    assert status_applied["applied_at"] is not None
    assert status_applied["notes"] == "Applied on portal with resume v3"

    # Weekly applied count increments to 1
    weekly_cnt = get_weekly_applied_count(session)
    assert weekly_cnt == 1

    # 3. Action: Not Interested
    res_ignore = client.post(
        f"/jobs/{fp}/status",
        data={"status": "not_interested"},
    )
    assert res_ignore.status_code == 303

    status_ni = get_job_status(session, fp)
    assert status_ni["status"] == "not_interested"
    assert status_ni["not_interested_at"] is not None


def test_weekly_applied_count_calculation(client_and_session):
    """Verify weekly applied count only counts applications within the last 7 days."""
    client, session = client_and_session
    now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)

    # Insert 2 recent applications (within 7 days)
    session.execute(
        text(
            """
            INSERT INTO seen_jobs (fingerprint, canonical_url, status, applied_at)
            VALUES ('fp_recent_1', 'url1', 'applied', :t1),
                   ('fp_recent_2', 'url2', 'applied', :t2)
            """
        ),
        {"t1": now - timedelta(days=2), "t2": now - timedelta(days=5)},
    )

    # Insert 1 old application (> 7 days ago)
    session.execute(
        text(
            """
            INSERT INTO seen_jobs (fingerprint, canonical_url, status, applied_at)
            VALUES ('fp_old_1', 'url3', 'applied', :t3)
            """
        ),
        {"t3": now - timedelta(days=12)},
    )
    session.commit()

    weekly_cnt = get_weekly_applied_count(session, now=now)
    assert weekly_cnt == 2


# ==============================================================================
# 2. Settings Editor & Check Line Verification (Blocklist Edit Changes Tomorrow's Digest)
# ==============================================================================

def test_settings_page_view(client_and_session):
    """Verify authenticated user can view profile settings page."""
    client, session = client_and_session
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Candidate Profile &amp; Match Settings" in response.text
    assert "Company Blocklist" in response.text
    assert "Minimum Match Score" in response.text


def test_blocklist_edit_changes_tomorrows_digest(client_and_session):
    """
    Session 15 Check:
    A blocklist edit made from your phone changes tomorrow's digest.
    - User edits company_blocklist in web settings to block 'Revature' and 'BadCompany'.
    - Profile is updated in DB as new version.
    - Next run loads the updated profile.
    - A job from 'BadCompany' is strictly excluded from tomorrow's digest!
    """
    client, session = client_and_session

    # 1. Job from BadCompany currently before blocklist edit
    job_before = Job(
        title="Junior Python Engineer",
        company="BadCompany",
        location="Bengaluru",
        canonical_url="https://badcompany.com/job/1",
        description_text="Python role",
        source="lever",
    )
    profile_before = load_profile(session=session)
    is_eligible_before, _ = check_eligibility(job_before, profile_before)
    assert is_eligible_before is True  # Eligible before blocklist edit

    # 2. User makes blocklist edit via POST /settings
    res_edit = client.post(
        "/settings",
        data={
            "name": "Candidate",
            "email": "candidate@example.com",
            "min_score": "4.0",
            "strong_threshold": "7.0",
            "company_blocklist": "Revature, BadCompany, ScamCorp",
            "exclude_title_words": "senior, lead, manager, principal",
            "channels": ["telegram", "email"],
        },
    )
    assert res_edit.status_code == 303
    assert "success=" in res_edit.headers["location"]

    # 3. Verify active profile was updated to version 2 in database
    active_profile, warning = get_active_profile_from_db(session)
    assert active_profile is not None
    assert "badcompany" in active_profile.hard_filters.company_blocklist
    assert "scamcorp" in active_profile.hard_filters.company_blocklist

    # 4. Next run loads profile directly from database
    profile_next_run = load_profile(session=session)
    is_eligible_after, reason = check_eligibility(job_before, profile_next_run)

    # Check Line Satisfied: The job from BadCompany is now strictly dropped from the digest!
    assert is_eligible_after is False
    assert "in blocklist" in reason.lower()


# ==============================================================================
# 3. Source Health Page & Manual Job Entry
# ==============================================================================

def test_source_health_page(client_and_session):
    """Verify /sources displays execution status for all 8 source adapters."""
    client, session = client_and_session
    response = client.get("/sources")
    assert response.status_code == 200
    assert "Source Health &amp; Execution Metrics" in response.text
    assert "greenhouse" in response.text
    assert "remotive" in response.text
    assert "Healthy" in response.text
    assert "Rate Limited" in response.text


def test_manual_add_job_flow(client_and_session):
    """Verify manual add-a-job form saves and scores an opportunity directly."""
    client, session = client_and_session

    # View add job form
    res_get = client.get("/jobs/add")
    assert res_get.status_code == 200
    assert "Manually Add a Job Listing" in res_get.text

    # Submit new manual job
    res_post = client.post(
        "/jobs/add",
        data={
            "title": "Junior Python Developer",
            "company": "Swiggy",
            "location": "Bengaluru",
            "canonical_url": "https://careers.swiggy.com/jobs/sde-1",
            "description_text": "Python, FastAPI, Git, PostgreSQL. 2027 batch welcome.",
            "salary_lpa": "9.5",
            "is_intern": False,
        },
    )
    assert res_post.status_code == 303
    assert "/history?status=saved" in res_post.headers["location"]

    # Verify manual job appears in /history
    res_hist = client.get("/history?status=saved")
    assert res_hist.status_code == 200
    assert "Swiggy" in res_hist.text
    assert "9.5 LPA" in res_hist.text
