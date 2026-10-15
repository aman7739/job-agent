"""Unit and integration tests for Session 13: Database-backed profile, versioning, fallback recovery, and job status tracking."""

import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from job_digest.profile import load_profile, load_profile_from_file
from job_digest.profile_service import (
    get_active_profile_from_db,
    get_profile_history,
    save_profile_to_db,
    seed_database_profile_if_empty,
)
from job_digest.status import (
    get_job_status,
    get_jobs_by_status,
    get_status_summary,
    set_job_status,
)

EXAMPLE_YAML_PATH = Path(__file__).resolve().parent.parent / "profile.example.yaml"
EXAMPLE_YAML_CONTENT = EXAMPLE_YAML_PATH.read_text(encoding="utf-8")

SQLITE_SCHEMA = """
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
"""


@pytest.fixture
def db_session():
    """Provides a fresh in-memory SQLite database session with required tables."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        for statement in SQLITE_SCHEMA.split(";"):
            stmt_clean = statement.strip()
            if stmt_clean:
                conn.execute(text(stmt_clean))
        conn.commit()

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ==============================================================================
# 1. Profile in Database: Validation on Save & Version History
# ==============================================================================

def test_save_valid_profile_and_history(db_session: Session):
    """
    Session 13 Check:
    Moving profile into database: validated on save, version incremented, history stored.
    """
    # 1. Save initial version 1
    profile_v1, v1 = save_profile_to_db(db_session, EXAMPLE_YAML_CONTENT)
    assert v1 == 1
    assert profile_v1.user.name == "Candidate"
    assert profile_v1.scoring.min_score == 4.0

    # 2. Modify YAML (change min_score to 5.5) and save as version 2
    modified_yaml = EXAMPLE_YAML_CONTENT.replace("min_score: 4.0", "min_score: 5.5")
    profile_v2, v2 = save_profile_to_db(db_session, modified_yaml)
    assert v2 == 2
    assert profile_v2.scoring.min_score == 5.5

    # 3. Verify active profile is version 2
    active_profile, warning = get_active_profile_from_db(db_session)
    assert warning is None
    assert active_profile is not None
    assert active_profile.scoring.min_score == 5.5

    # 4. Verify version history preserves both versions
    history = get_profile_history(db_session)
    assert len(history) == 2
    assert history[0]["version"] == 2
    assert history[0]["is_active"] is True
    assert history[1]["version"] == 1
    assert history[1]["is_active"] is False


def test_invalid_profile_edit_rejected_without_overwriting(db_session: Session):
    """
    Session 13 Check:
    An invalid edit fails loudly and does not corrupt or overwrite the active profile.
    """
    # 1. Save valid profile version 1
    save_profile_to_db(db_session, EXAMPLE_YAML_CONTENT)

    # 2. Attempt saving an invalid profile (e.g. unknown key or invalid channel)
    invalid_yaml = EXAMPLE_YAML_CONTENT + "\nunknown_illegal_key: true\n"

    with pytest.raises(ValueError) as exc:
        save_profile_to_db(db_session, invalid_yaml)

    assert "Invalid profile configuration" in str(exc.value)

    # 3. Verify version 1 is still the active profile intact
    active_profile, warning = get_active_profile_from_db(db_session)
    assert warning is None
    assert active_profile is not None
    assert active_profile.scoring.min_score == 4.0

    # History still has only version 1
    history = get_profile_history(db_session)
    assert len(history) == 1
    assert history[0]["version"] == 1


# ==============================================================================
# 2. Check Line Verification: Profile Edit Changes Next Run & Fallback Recovery
# ==============================================================================

def test_profile_edit_changes_next_run(db_session: Session):
    """
    Session 13 Check:
    A profile edit changes the next run.
    """
    # Initial run loads default version 1
    save_profile_to_db(db_session, EXAMPLE_YAML_CONTENT)
    run1_profile = load_profile(session=db_session)
    assert run1_profile.scoring.min_score == 4.0

    # User edits profile (adds new target role, changes strong_threshold to 8.0)
    edited_yaml = EXAMPLE_YAML_CONTENT.replace("strong_threshold: 7.0", "strong_threshold: 8.0")
    save_profile_to_db(db_session, edited_yaml)

    # Next run loads updated profile directly from DB
    run2_profile = load_profile(session=db_session)
    assert run2_profile.scoring.strong_threshold == 8.0


def test_corrupted_active_profile_falls_back_to_last_good_version_and_says_so(db_session: Session):
    """
    Session 13 Check:
    An invalid edit / corrupted active version falls back to the last good version and says so.
    """
    # Save valid version 1
    save_profile_to_db(db_session, EXAMPLE_YAML_CONTENT)

    # Manually insert a corrupted active version 2 directly into DB
    db_session.execute(
        text("UPDATE user_profiles SET is_active = 0 WHERE version = 1")
    )
    db_session.execute(
        text(
            """
            INSERT INTO user_profiles (version, profile_yaml, profile_data, is_active)
            VALUES (2, 'corrupted: yaml: ::: illegal', '{}', 1)
            """
        )
    )
    db_session.commit()

    # get_active_profile_from_db should detect corruption, fallback to v1, and say so
    recovered_profile, warning = get_active_profile_from_db(db_session)
    assert recovered_profile is not None
    assert recovered_profile.scoring.min_score == 4.0
    assert warning is not None
    assert "Fell back to last good version 1" in warning

    # load_profile also successfully returns the recovered profile
    loaded = load_profile(session=db_session)
    assert loaded.scoring.min_score == 4.0


# ==============================================================================
# 3. Job Status Tracking (saved, applied, not_interested with timestamps)
# ==============================================================================

def test_job_status_transitions_and_timestamps(db_session: Session):
    """
    Session 13 Check:
    Add job_status (saved, applied, not_interested, with timestamps and notes).
    """
    now = datetime(2026, 10, 3, 15, 30, 0, tzinfo=timezone.utc)
    fp = "fp_stripe_001"

    # Insert a seen job
    db_session.execute(
        text(
            """
            INSERT INTO seen_jobs (fingerprint, canonical_url, status)
            VALUES (:fp, 'https://stripe.com/job/1', 'seen')
            """
        ),
        {"fp": fp},
    )
    # Insert matching job row
    db_session.execute(
        text(
            """
            INSERT INTO jobs (fingerprint, title, company, location, canonical_url, source, score)
            VALUES (:fp, 'Software Engineer', 'Stripe', 'Bengaluru', 'https://stripe.com/job/1', 'greenhouse', 8.5)
            """
        ),
        {"fp": fp},
    )
    db_session.commit()

    # Verify initial status
    initial = get_job_status(db_session, fp)
    assert initial["status"] == "seen"
    assert initial["saved_at"] is None
    assert initial["applied_at"] is None

    # 1. Update to 'saved'
    ok = set_job_status(db_session, fp, "saved", notes="Referral through senior", now=now)
    assert ok is True

    status_saved = get_job_status(db_session, fp)
    assert status_saved["status"] == "saved"
    assert status_saved["saved_at"] is not None
    assert status_saved["notes"] == "Referral through senior"

    # 2. Update to 'applied'
    ok = set_job_status(db_session, fp, "applied", notes="Applied on careers page", now=now)
    assert ok is True

    status_applied = get_job_status(db_session, fp)
    assert status_applied["status"] == "applied"
    assert status_applied["applied_at"] is not None
    assert status_applied["notes"] == "Applied on careers page"

    # 3. Query jobs by status
    applied_list = get_jobs_by_status(db_session, "applied")
    assert len(applied_list) == 1
    assert applied_list[0]["company"] == "Stripe"
    assert applied_list[0]["score"] == 8.5
    assert applied_list[0]["status"] == "applied"

    # 4. Update to 'not_interested'
    ok = set_job_status(db_session, fp, "not_interested")
    assert ok is True
    status_ni = get_job_status(db_session, fp)
    assert status_ni["status"] == "not_interested"
    assert status_ni["not_interested_at"] is not None

    # 5. Invalid status raises ValueError
    with pytest.raises(ValueError):
        set_job_status(db_session, fp, "interviewing_invalid")

    # 6. Non-existent fingerprint returns False
    assert set_job_status(db_session, "non_existent_fp", "saved") is False


def test_status_summary_aggregation(db_session: Session):
    """Verify get_status_summary aggregates counts for seen, saved, applied, not_interested."""
    jobs_data = [
        ("fp_1", "seen"),
        ("fp_2", "saved"),
        ("fp_3", "saved"),
        ("fp_4", "applied"),
        ("fp_5", "not_interested"),
    ]
    for fp, st in jobs_data:
        db_session.execute(
            text("INSERT INTO seen_jobs (fingerprint, canonical_url, status) VALUES (:fp, 'url', :st)"),
            {"fp": fp, "st": st},
        )
    db_session.commit()

    summary = get_status_summary(db_session)
    assert summary["seen"] == 1
    assert summary["saved"] == 2
    assert summary["applied"] == 1
    assert summary["not_interested"] == 1
    assert summary["total"] == 5


def test_seed_database_profile_if_empty(db_session: Session):
    """Verify seed_database_profile_if_empty populates version 1 when table is empty."""
    # When empty, seeds from profile.example.yaml
    seeded = seed_database_profile_if_empty(db_session)
    assert seeded is not None
    assert seeded.user.name == "Candidate"

    # Subsequent call returns active profile without duplicating
    seeded_again = seed_database_profile_if_empty(db_session)
    assert seeded_again is not None
    history = get_profile_history(db_session)
    assert len(history) == 1
