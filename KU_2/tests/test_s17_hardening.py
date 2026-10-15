"""Tests for Session 17: Enterprise hardening, security headers, robots disallow, PWA manifest, and webhook token."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from job_digest.auth import create_session_token
from job_digest.db import Base
from job_digest.web import TRIGGER_TOKEN, app, get_db
from scripts.backup_db import create_database_backup


@pytest.fixture
def test_client_and_session():
    """Create isolated test environment."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield client, session

    app.dependency_overrides.clear()
    session.close()


# ==============================================================================
# 1. Security Headers Verification (Session 17 Check)
# ==============================================================================

def test_security_headers_present_on_all_responses(test_client_and_session):
    """Verify enterprise security headers are attached by middleware."""
    client, _ = test_client_and_session
    response = client.get("/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "strict-origin" in headers.get("Referrer-Policy", "")
    assert "max-age=31536000" in headers.get("Strict-Transport-Security", "")
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")
    assert "noindex, nofollow" in headers.get("X-Robots-Tag", "")


# ==============================================================================
# 2. Search Engine Disallow (/robots.txt) & PWA Manifest (/manifest.json)
# ==============================================================================

def test_robots_txt_disallows_all_crawlers(test_client_and_session):
    """Verify robots.txt blocks all search engines."""
    client, _ = test_client_and_session
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert "User-agent: *" in response.text
    assert "Disallow: /" in response.text


def test_manifest_json_pwa(test_client_and_session):
    """Verify web app manifest is served with standalone PWA configuration."""
    client, _ = test_client_and_session
    response = client.get("/manifest.json")
    assert response.status_code == 200
    data = response.json()
    assert data["display"] == "standalone"
    assert data["name"] == "Job Digest Agent"
    assert data["theme_color"] == "#2563eb"


# ==============================================================================
# 3. Unreachable Without Login Verification (Session 17 Check)
# ==============================================================================

@pytest.mark.parametrize(
    "route,method",
    [
        ("/", "get"),
        ("/history", "get"),
        ("/settings", "get"),
        ("/sources", "get"),
        ("/jobs/add", "get"),
        ("/jobs/run-now", "post"),
        ("/jobs/test_fp/status", "post"),
    ],
)
def test_app_unreachable_without_login(test_client_and_session, route, method):
    """Verify every private route redirects unauthenticated requests to /login."""
    client, _ = test_client_and_session
    func = getattr(client, method)
    response = func(route, follow_redirects=False)

    assert response.status_code in (302, 303, 307)
    location = response.headers.get("location", "")
    assert "/login" in location


# ==============================================================================
# 4. Token-Protected Webhook Trigger (/api/trigger)
# ==============================================================================

def test_api_trigger_rejected_without_token(test_client_and_session):
    """Verify webhook trigger requires valid secret token."""
    client, _ = test_client_and_session
    response = client.post("/api/trigger")
    assert response.status_code == 401
    assert "Invalid or missing trigger token" in response.json()["detail"]


def test_api_trigger_succeeds_with_valid_token(test_client_and_session):
    """Verify webhook trigger executes pipeline when valid token is supplied."""
    client, _ = test_client_and_session
    mock_result = {
        "new_jobs": 2,
        "total_in_digest": 4,
        "delivered_channels": ["telegram"],
        "urgent_alerts_sent": 0,
    }

    with patch("job_digest.run.run_digest_pipeline", new=AsyncMock(return_value=mock_result)):
        response = client.post(
            "/api/trigger",
            headers={"X-Trigger-Token": TRIGGER_TOKEN},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "triggered"
        assert data["new_jobs"] == 2
        assert "telegram" in data["delivered_channels"]


# ==============================================================================
# 5. Database Backup Utility (Disaster Recovery Plan)
# ==============================================================================

def test_backup_db_script(tmp_path, test_client_and_session):
    """Verify create_database_backup dumps database snapshot into JSON file."""
    _, session = test_client_and_session

    backup_path = create_database_backup(output_dir=tmp_path, session=session)
    assert backup_path.exists()
    assert backup_path.suffix == ".json"

    with open(backup_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "metadata" in data
    assert "user_profiles" in data
    assert "seen_jobs" in data
    assert "jobs" in data
    assert "digests" in data
