"""Unit tests for JobSource interface, Greenhouse adapter, Lever adapter, and location filters."""

import pytest
import httpx
from job_digest.sources.base import JobSource, is_india_or_remote
from job_digest.sources.greenhouse import GreenhouseSource
from job_digest.sources.lever import LeverSource


def test_job_source_protocol_compliance():
    """Verify GreenhouseSource and LeverSource comply with JobSource protocol."""
    gh = GreenhouseSource(slugs=["test"])
    lever = LeverSource(slugs=["test"])

    assert isinstance(gh, JobSource)
    assert gh.name == "greenhouse"

    assert isinstance(lever, JobSource)
    assert lever.name == "lever"


@pytest.mark.parametrize(
    "loc,expected",
    [
        ("Bengaluru, India", True),
        ("Bangalore, Karnataka", True),
        ("Noida, Delhi NCR", True),
        ("Gurugram, Haryana", True),
        ("Pune, India", True),
        ("Mumbai, Maharashtra", True),
        ("Remote - India", True),
        ("Remote", True),
        ("Work from home", True),
        ("Anywhere in the world (Remote)", True),
        ("", True),  # unspecified location treated as potentially remote
        (None, True),
        ("Austin, TX", False),
        ("London, United Kingdom", False),
        ("Sydney, Australia", False),
        ("Berlin, Germany", False),
    ],
)
def test_is_india_or_remote(loc, expected):
    """Verify is_india_or_remote correctly filters locations."""
    assert is_india_or_remote(loc) == expected


@pytest.mark.asyncio
async def test_greenhouse_fetch_board_success():
    """Verify Greenhouse parsing on successful response."""
    sample_data = {
        "jobs": [
            {
                "id": 101,
                "title": "Junior Python Developer",
                "location": {"name": "Noida, India"},
                "absolute_url": "https://boards.greenhouse.io/sample/jobs/101",
                "updated_at": "2026-03-01T12:00:00Z",
                "content": "<p>Job description</p>",
            },
            {
                "id": 102,
                "title": "Software Engineer",
                "location": {"name": "New York, NY"},  # Abroad - should be filtered out
                "absolute_url": "https://boards.greenhouse.io/sample/jobs/102",
                "updated_at": "2026-03-01T12:00:00Z",
                "content": "<p>NY Job</p>",
            },
        ]
    }

    def handler(request):
        return httpx.Response(200, json=sample_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        gh = GreenhouseSource(slugs=["sample"], delay_seconds=0)
        jobs = await gh.fetch_board(client, "sample")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "greenhouse"
    assert job.source_id == "sample"
    assert job.external_id == "101"
    assert job.title == "Junior Python Developer"
    assert job.location == "Noida, India"
    assert job.url == "https://boards.greenhouse.io/sample/jobs/101"


@pytest.mark.asyncio
async def test_greenhouse_404_logs_warning_and_skips():
    """Verify that a 404 response for a Greenhouse board returns empty list without raising."""
    def handler(request):
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        gh = GreenhouseSource(slugs=["nonexistent"], delay_seconds=0)
        jobs = await gh.fetch_board(client, "nonexistent")

    assert jobs == []


@pytest.mark.asyncio
async def test_lever_fetch_board_success():
    """Verify Lever parsing on successful response."""
    sample_data = [
        {
            "id": "lever-1",
            "text": "Associate Software Engineer",
            "createdAt": 1709294400000,
            "categories": {
                "location": "Bengaluru",
                "commitment": "Full time",
                "team": "Engineering",
            },
            "description": "<p>Description</p>",
            "descriptionPlain": "Description",
            "hostedUrl": "https://jobs.lever.co/sample/lever-1",
            "workplaceType": "hybrid",
        },
        {
            "id": "lever-2",
            "text": "Site Reliability Engineer",
            "createdAt": 1709294400000,
            "categories": {
                "location": "San Francisco, CA",  # Abroad - should be filtered out
            },
            "hostedUrl": "https://jobs.lever.co/sample/lever-2",
            "workplaceType": "onsite",
        },
    ]

    def handler(request):
        return httpx.Response(200, json=sample_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        lever = LeverSource(slugs=["sample"], delay_seconds=0)
        jobs = await lever.fetch_board(client, "sample")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "lever"
    assert job.source_id == "sample"
    assert job.external_id == "lever-1"
    assert job.title == "Associate Software Engineer"
    assert job.location == "Bengaluru"
    assert job.url == "https://jobs.lever.co/sample/lever-1"


@pytest.mark.asyncio
async def test_lever_404_logs_warning_and_skips():
    """Verify that a 404 response for a Lever board returns empty list without raising."""
    def handler(request):
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        lever = LeverSource(slugs=["nonexistent"], delay_seconds=0)
        jobs = await lever.fetch_board(client, "nonexistent")

    assert jobs == []
