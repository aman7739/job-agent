"""Unit tests and recorded fixture tests for Ashby, SmartRecruiters, and Workable adapters."""

import json
from pathlib import Path
import pytest
import httpx

from job_digest.sources.base import JobSource
from job_digest.sources.ashby import AshbySource
from job_digest.sources.smartrecruiters import SmartRecruitersSource
from job_digest.sources.workable import WorkableSource

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_session3_sources_protocol_compliance():
    """Verify Ashby, SmartRecruiters, and Workable satisfy JobSource protocol."""
    ashby = AshbySource(slugs=["test"])
    sr = SmartRecruitersSource(slugs=["test"])
    workable = WorkableSource(slugs=["test"])

    assert isinstance(ashby, JobSource)
    assert ashby.name == "ashby"

    assert isinstance(sr, JobSource)
    assert sr.name == "smartrecruiters"

    assert isinstance(workable, JobSource)
    assert workable.name == "workable"


# --- Ashby Tests ---

@pytest.mark.asyncio
async def test_ashby_fixture_parsing_and_filtering():
    """Verify Ashby parses listed jobs, filters unlisted jobs, and applies location filter."""
    with open(FIXTURES_DIR / "ashby_response.json", "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    def handler(request):
        return httpx.Response(200, json=fixture_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        ashby = AshbySource(slugs=["example"], delay_seconds=0)
        jobs = await ashby.fetch_board(client, "example")

    # From 3 jobs:
    # - 1 listed in Bengaluru -> KEPT
    # - 1 unlisted in Pune -> SKIPPED (isListed: false)
    # - 1 listed in SF -> FILTERED (abroad)
    assert len(jobs) == 1
    assert jobs[0].external_id == "ashby-job-001"
    assert jobs[0].title == "Junior Backend Engineer"
    assert "Bengaluru" in jobs[0].location
    assert jobs[0].source == "ashby"


@pytest.mark.asyncio
async def test_ashby_404_logs_warning_and_skips():
    """Verify that a 404 response for Ashby skips with warning."""
    def handler(request):
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        ashby = AshbySource(slugs=["invalid-slug"], delay_seconds=0)
        jobs = await ashby.fetch_board(client, "invalid-slug")

    assert jobs == []


# --- SmartRecruiters Tests ---

@pytest.mark.asyncio
async def test_smartrecruiters_fixture_parsing_and_filtering():
    """Verify SmartRecruiters parses India and Remote jobs and filters foreign ones."""
    with open(FIXTURES_DIR / "smartrecruiters_response.json", "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    def handler(request):
        return httpx.Response(200, json=fixture_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        sr = SmartRecruitersSource(slugs=["example"], delay_seconds=0)
        jobs = await sr.fetch_board(client, "example")

    # From 3 jobs:
    # - Pune, India -> KEPT
    # - Chicago (Remote) -> KEPT (remote keyword)
    # - Stuttgart, Germany -> FILTERED
    assert len(jobs) == 2
    ids = [j.external_id for j in jobs]
    assert "sr-job-001" in ids
    assert "sr-job-002" in ids
    assert "sr-job-003" not in ids


@pytest.mark.asyncio
async def test_smartrecruiters_404_and_403_skipped():
    """Verify that 404 and 403 responses for SmartRecruiters skip with warning."""
    def handler(request):
        if "forbidden" in str(request.url):
            return httpx.Response(403, text="Forbidden")
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        sr = SmartRecruitersSource(slugs=["not-found", "forbidden"], delay_seconds=0)
        jobs_404 = await sr.fetch_board(client, "not-found")
        jobs_403 = await sr.fetch_board(client, "forbidden")

    assert jobs_404 == []
    assert jobs_403 == []


# --- Workable Tests ---

@pytest.mark.asyncio
async def test_workable_fixture_parsing_and_filtering():
    """Verify Workable parses India and Remote jobs and filters foreign non-remote ones."""
    with open(FIXTURES_DIR / "workable_response.json", "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    def handler(request):
        return httpx.Response(200, json=fixture_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        workable = WorkableSource(slugs=["example"], delay_seconds=0)
        jobs = await workable.fetch_board(client, "example")

    # From 3 jobs:
    # - Gurugram, India -> KEPT
    # - Austin, TX (Remote) -> KEPT
    # - London, UK -> FILTERED
    assert len(jobs) == 2
    shortcodes = [j.external_id for j in jobs]
    assert "WRK001" in shortcodes
    assert "WRK002" in shortcodes
    assert "WRK003" not in shortcodes


@pytest.mark.asyncio
async def test_workable_404_logs_warning_and_skips():
    """Verify that a 404 response across both v3 and v1 skips with warning."""
    def handler(request):
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        workable = WorkableSource(slugs=["invalid-slug"], delay_seconds=0)
        jobs = await workable.fetch_board(client, "invalid-slug")

    assert jobs == []
