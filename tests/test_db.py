"""Unit tests for database utilities and schema verification."""

from pathlib import Path
import pytest
from job_digest.db import get_database_url, get_engine


def test_database_url_formatting(monkeypatch):
    """Verify DATABASE_URL transforms postgres:// to postgresql+psycopg://."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:6543/db")
    formatted = get_database_url()
    assert formatted == "postgresql+psycopg://user:pass@host:6543/db"

    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:6543/db")
    formatted2 = get_database_url()
    assert formatted2 == "postgresql+psycopg://user:pass@host:6543/db"


def test_missing_database_url_raises_error(monkeypatch):
    """Verify get_engine raises clear error if DATABASE_URL is not set."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError) as exc:
        get_engine("")
    assert "DATABASE_URL is not set" in str(exc.value)


def test_schema_sql_contains_all_required_tables():
    """Verify database/schema.sql contains definitions for all 6 required tables."""
    schema_path = Path(__file__).resolve().parent.parent / "database" / "schema.sql"
    assert schema_path.is_file(), "database/schema.sql must exist"

    sql_content = schema_path.read_text(encoding="utf-8").lower()

    required_tables = [
        "job_sources",
        "seen_jobs",
        "jobs",
        "digests",
        "source_runs",
        "email_messages",
        "user_profiles",
    ]

    for table in required_tables:
        assert f"create table if not exists {table}" in sql_content, f"Table {table} missing from schema.sql"

    # Verify fingerprint primary key in seen_jobs
    assert "fingerprint varchar(64) primary key" in sql_content
    # Verify fingerprint foreign key in jobs
    assert "references seen_jobs(fingerprint)" in sql_content
