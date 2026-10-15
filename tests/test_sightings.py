"""Unit tests for job_sightings table and 7-day source attribution metrics."""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from job_digest.dedup import (
    ensure_sightings_table,
    get_7day_source_metrics,
    record_sighting,
)


@pytest.fixture
def in_memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE seen_jobs (
                    fingerprint VARCHAR(64) PRIMARY KEY,
                    canonical_url TEXT,
                    status VARCHAR(32) DEFAULT 'seen',
                    saved_at TIMESTAMP,
                    applied_at TIMESTAMP
                )
                """
            )
        )
        conn.commit()

    SessionMaker = sessionmaker(bind=engine)
    session = SessionMaker()
    try:
        yield session
    finally:
        session.close()


def test_ensure_sightings_table(in_memory_db):
    """Verify table creation works idempotently."""
    ensure_sightings_table(in_memory_db)
    # Check that table exists
    result = in_memory_db.execute(text("SELECT count(*) FROM job_sightings")).scalar()
    assert result == 0


def test_record_sighting_and_compute_metrics(in_memory_db):
    """Verify recording sightings and computing 7-day attribution metrics."""
    now = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)

    # Setup test jobs in seen_jobs
    in_memory_db.execute(
        text(
            """
            INSERT INTO seen_jobs (fingerprint, status, applied_at)
            VALUES ('fp_exclusive_adzuna', 'applied', '2026-10-14 10:00:00')
            """
        )
    )
    in_memory_db.execute(
        text(
            """
            INSERT INTO seen_jobs (fingerprint, status, saved_at)
            VALUES ('fp_shared_greenhouse', 'saved', '2026-10-14 11:00:00')
            """
        )
    )
    in_memory_db.commit()

    # 1. Record sightings
    # Exclusive to adzuna
    record_sighting(in_memory_db, "fp_exclusive_adzuna", "adzuna", now)
    # Shared between greenhouse and lever
    record_sighting(in_memory_db, "fp_shared_greenhouse", "greenhouse", now)
    record_sighting(in_memory_db, "fp_shared_greenhouse", "lever", now)

    # Old sighting (> 7 days ago)
    old_ts = now - timedelta(days=10)
    record_sighting(in_memory_db, "fp_old", "adzuna", old_ts)

    in_memory_db.commit()

    # 2. Compute 7-day metrics
    metrics = get_7day_source_metrics(in_memory_db, now=now)

    assert "adzuna" in metrics
    assert metrics["adzuna"]["total_sightings"] == 1  # old one excluded
    assert metrics["adzuna"]["unique_jobs"] == 1
    assert metrics["adzuna"]["incremental_jobs"] == 1  # Only adzuna found fp_exclusive_adzuna!
    assert metrics["adzuna"]["applied_jobs"] == 1

    assert "greenhouse" in metrics
    assert metrics["greenhouse"]["unique_jobs"] == 1
    assert metrics["greenhouse"]["incremental_jobs"] == 0  # Shared with lever!
    assert metrics["greenhouse"]["saved_jobs"] == 1

    assert "lever" in metrics
    assert metrics["lever"]["unique_jobs"] == 1
    assert metrics["lever"]["incremental_jobs"] == 0
