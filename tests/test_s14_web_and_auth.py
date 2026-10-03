"""Unit and integration tests for Session 14: Single-user authentication, secure cookies, rate limiting, and web dashboard."""

import os
from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from job_digest.auth import (
    _login_attempts,
    create_session_token,
    hash_password,
    verify_password,
    verify_session_token,
)
from job_digest.web import app, get_db

TEST_PASSWORD = "supersecretpassword123"
TEST_HASH = hash_password(TEST_PASSWORD)

from sqlalchemy.pool import StaticPool

SQLITE_TEST_SCHEMA = """
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


@pytest.fixture(autouse=True)
def reset_rate_limiter(monkeypatch):
    """Ensure clean rate-limit state and password hash for each test."""
    _login_attempts.clear()
    monkeypatch.setenv("DASHBOARD_PASSWORD_HASH", TEST_HASH)
    monkeypatch.setenv("DASHBOARD_PASSWORD", TEST_PASSWORD)


@pytest.fixture
def client_with_db():
    """Provides a TestClient connected to a populated in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        for stmt in SQLITE_TEST_SCHEMA.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))

        # Seed sample digest
        conn.execute(
            text(
                """
                INSERT INTO digests (total_jobs, internships_count, fulltime_count, content_html, content_text)
                VALUES (5, 2, 3, '<div class="digest">Test Digest Content</div>', 'Test Digest Content')
                """
            )
        )

        # Seed sample jobs
        conn.execute(
            text(
                """
                INSERT INTO seen_jobs (fingerprint, canonical_url, status)
                VALUES ('fp_intern_1', 'https://example.com/1', 'seen'),
                       ('fp_fulltime_1', 'https://example.com/2', 'saved')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO jobs (fingerprint, title, company, location, canonical_url, source, is_intern, is_apprentice, score, salary_lpa, stipend)
                VALUES ('fp_intern_1', 'Python Intern', 'Stripe', 'Bengaluru', 'https://example.com/1', 'greenhouse', 1, 0, 8.5, NULL, 50000),
                       ('fp_fulltime_1', 'Junior Developer', 'Razorpay', 'Pune', 'https://example.com/2', 'lever', 0, 0, 7.2, 9.0, NULL)
                """
            )
        )
        conn.commit()

    SessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app, follow_redirects=False)
    yield test_client
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Password Verification & Session Token Tests
# ==============================================================================

def test_password_hashing_and_verification():
    """Verify Argon2 password hashing and verification."""
    password = "secret_password_2027"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_session_token_signing_and_expiry():
    """Verify HMAC signed session token generation, validation, and expiration."""
    token = create_session_token("admin", max_age_seconds=3600)
    assert token is not None
    user = verify_session_token(token)
    assert user == "admin"

    # Expired token
    expired_token = create_session_token("admin", max_age_seconds=-10)
    assert verify_session_token(expired_token) is None

    # Tampered token
    tampered = token[:-4] + "xxxx"
    assert verify_session_token(tampered) is None


# ==============================================================================
# 2. Check Line Verification: Wrong Password Rejected & Pages Require Session
# ==============================================================================

def test_wrong_password_is_rejected(client_with_db):
    """
    Session 14 Check:
    A wrong password is rejected with HTTP 401.
    """
    response = client_with_db.post(
        "/login",
        data={"password": "incorrect_password", "next": "/"},
    )
    assert response.status_code == 401
    assert "Invalid master password" in response.text
    assert "session_token" not in response.cookies


def test_login_rate_limiting_blocks_attacker(client_with_db):
    """
    Session 14 Check:
    Login rate limit blocks repeated failed attempts (HTTP 429).
    """
    # 5 failed attempts
    for _ in range(5):
        resp = client_with_db.post("/login", data={"password": "bad"})
        assert resp.status_code == 401

    # 6th attempt is rate-limited
    rate_limited_resp = client_with_db.post("/login", data={"password": "bad"})
    assert rate_limited_resp.status_code == 429
    assert "Too many failed attempts" in rate_limited_resp.text


def test_every_page_needs_a_session(client_with_db):
    """
    Session 14 Check:
    Every page needs a session. Unauthenticated requests are redirected to /login.
    """
    # 1. Unauthenticated root -> redirects to /login?next=/
    res_root = client_with_db.get("/")
    assert res_root.status_code == 307
    assert "/login?next=/" in res_root.headers["location"]

    # 2. Unauthenticated history -> redirects to /login?next=/history
    res_hist = client_with_db.get("/history")
    assert res_hist.status_code == 307
    assert "/login?next=/history" in res_hist.headers["location"]


# ==============================================================================
# 3. Successful Login, Read Pages & Filtering
# ==============================================================================

def test_login_success_sets_session_cookie(client_with_db):
    """Verify correct password logs in, sets session cookie, and redirects."""
    response = client_with_db.post(
        "/login",
        data={"password": TEST_PASSWORD, "next": "/history"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/history"
    assert "session_token" in response.cookies


def test_authenticated_user_access_today_digest(client_with_db):
    """Verify authenticated user can view today's digest."""
    # Login to acquire session
    login_resp = client_with_db.post("/login", data={"password": TEST_PASSWORD, "next": "/"})
    session_token = login_resp.cookies["session_token"]

    # Request root page with session cookie
    client_with_db.cookies.set("session_token", session_token)
    response = client_with_db.get("/")
    assert response.status_code == 200
    assert "Daily Job Digest" in response.text
    assert "Test Digest Content" in response.text
    assert "Internships / Apprenticeships" in response.text


def test_authenticated_user_filters_job_history(client_with_db):
    """Verify job history filtering by section, minimum score, location, and source."""
    token = create_session_token("admin")
    client_with_db.cookies.set("session_token", token)

    # 1. View all history
    res_all = client_with_db.get("/history")
    assert res_all.status_code == 200
    assert "Python Intern" in res_all.text
    assert "Junior Developer" in res_all.text

    # 2. Filter section: internships only
    res_intern = client_with_db.get("/history?section=internships")
    assert res_intern.status_code == 200
    assert "Python Intern" in res_intern.text
    assert "Junior Developer" not in res_intern.text

    # 3. Filter section: fulltime only
    res_ft = client_with_db.get("/history?section=fulltime")
    assert res_ft.status_code == 200
    assert "Junior Developer" in res_ft.text
    assert "Python Intern" not in res_ft.text

    # 4. Filter by score: min_score = 8.0 (should only include Stripe intern with 8.5)
    res_score = client_with_db.get("/history?min_score=8.0")
    assert res_score.status_code == 200
    assert "Python Intern" in res_score.text
    assert "Junior Developer" not in res_score.text

    # 5. Filter by location: Pune
    res_pune = client_with_db.get("/history?location=Pune")
    assert res_pune.status_code == 200
    assert "Junior Developer" in res_pune.text
    assert "Python Intern" not in res_pune.text

    # 6. Filter by source: greenhouse
    res_gh = client_with_db.get("/history?source=greenhouse")
    assert res_gh.status_code == 200
    assert "Python Intern" in res_gh.text
    assert "Junior Developer" not in res_gh.text


def test_logout_clears_cookie(client_with_db):
    """Verify logout clears session token and redirects to login."""
    token = create_session_token("admin")
    client_with_db.cookies.set("session_token", token)
    res = client_with_db.post("/logout")
    assert res.status_code == 303
    assert res.headers["location"] == "/login"
    # Cookie is invalidated/deleted
    assert 'session_token=""' in res.headers.get("set-cookie", "")
