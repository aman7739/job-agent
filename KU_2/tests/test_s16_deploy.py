"""Tests for Session 16: Deployment configurations and health check endpoint."""

from pathlib import Path
from unittest.mock import MagicMock
import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from job_digest.db import Base
from job_digest.web import app, get_db


@pytest.fixture
def test_client_and_session():
    """Create isolated SQLite in-memory DB and test client."""
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
# 1. /health Endpoint Verification
# ==============================================================================

def test_health_check_public_and_healthy(test_client_and_session):
    """Verify /health is publicly accessible without login and returns HTTP 200."""
    client, session = test_client_and_session

    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "job-digest-agent"
    assert data["version"] == "1.0.0"
    assert data["database"] == "connected"
    assert "uptime_seconds" in data
    assert "timestamp" in data


def test_health_check_degraded_when_db_fails():
    """Verify /health returns HTTP 503 degraded when database ping fails."""
    # Mock a failing session
    mock_session = MagicMock()
    mock_session.execute.side_effect = Exception("DB connection timeout")

    def failing_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = failing_get_db
    client = TestClient(app)

    try:
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "error"
        assert "DB connection timeout" in data["error"]
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 2. Deployment Configuration File Integrity
# ==============================================================================

def test_dockerfile_integrity():
    """Verify Dockerfile exists and enforces security best practices."""
    dockerfile_path = Path("Dockerfile")
    assert dockerfile_path.exists(), "Dockerfile must exist in project root"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in content
    assert "appuser" in content, "Must configure non-root user"
    assert "USER appuser" in content
    assert "HEALTHCHECK" in content
    assert "/health" in content
    assert "uvicorn job_digest.web:app" in content


def test_render_yaml_blueprint_validity():
    """Verify render.yaml exists, is valid YAML, and contains required service specs."""
    render_path = Path("render.yaml")
    assert render_path.exists(), "render.yaml must exist in project root"

    data = yaml.safe_load(render_path.read_text(encoding="utf-8"))
    assert "services" in data
    assert len(data["services"]) >= 1

    svc = data["services"][0]
    assert svc["type"] == "web"
    assert svc["runtime"] == "python"
    assert svc["healthCheckPath"] == "/health"
    assert "uvicorn job_digest.web:app" in svc["startCommand"]
    assert "pip install -r requirements.txt" in svc["buildCommand"]


def test_procfile_and_dockerignore_exist():
    """Verify Procfile and .dockerignore exist and exclude sensitive files."""
    procfile_path = Path("Procfile")
    assert procfile_path.exists()
    assert "uvicorn job_digest.web:app" in procfile_path.read_text(encoding="utf-8")

    dockerignore_path = Path(".dockerignore")
    assert dockerignore_path.exists()
    di_content = dockerignore_path.read_text(encoding="utf-8")
    assert ".env" in di_content
    assert ".venv" in di_content
    assert "*.db" in di_content
