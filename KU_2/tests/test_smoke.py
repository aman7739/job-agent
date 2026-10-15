"""Smoke tests for Job Digest Agent environment and setup."""

import sys
import job_digest


def test_python_version():
    """Verify running on Python 3.12+."""
    assert sys.version_info >= (3, 12), f"Expected Python >= 3.12, got {sys.version}"


def test_package_import():
    """Verify job_digest imports cleanly."""
    assert job_digest.__version__ == "0.1.0"


def test_core_dependencies_importable():
    """Verify all primary dependencies import cleanly."""
    import fastapi
    import httpx
    import jinja2
    import psycopg
    import pydantic
    import sqlalchemy
    import yaml

    assert fastapi is not None
    assert httpx is not None
    assert jinja2 is not None
    assert psycopg is not None
    assert pydantic is not None
    assert sqlalchemy is not None
    assert yaml is not None
