"""Unit tests for JoobleSource adapter."""

import pytest
import httpx

from job_digest.sources.base import JobSource
from job_digest.sources.jooble import JoobleSource


def test_jooble_protocol_compliance():
    """Verify JoobleSource complies with JobSource protocol."""
    source = JoobleSource()
    assert isinstance(source, JobSource)
    assert source.name == "jooble"


@pytest.mark.asyncio
async def test_jooble_skips_when_api_key_missing():
    """Verify JoobleSource gracefully skips if JOOBLE_API_KEY is not set."""
    source = JoobleSource(api_key=None)
    jobs = await source.fetch()
    assert jobs == []


@pytest.mark.asyncio
async def test_jooble_fetch_query_parsing():
    """Verify Jooble parses jobs from API response."""
    mock_payload = {
        "totalCount": 2,
        "jobs": [
            {
                "id": "jb_101",
                "title": "Junior Python Developer",
                "company": "Infosys",
                "location": "Bengaluru, India",
                "link": "https://jooble.org/desc/101",
                "snippet": "Looking for entry level python developer",
                "updated": "2026-10-14T10:00:00Z",
                "salary": "4.5 LPA",
            },
            {
                "id": "jb_102",
                "title": "Full Stack Intern",
                "company": "TCS",
                "location": "Pune, India",
                "link": "https://jooble.org/desc/102",
                "snippet": "Full stack internship for students",
                "salary": "25000/month",
            },
            {
                "id": "jb_103",
                "title": "Developer",
                "company": "US Firm",
                "location": "Dallas, TX",
                "link": "https://jooble.org/desc/103",
                "snippet": "US only",
            },
        ],
    }

    def handler(request: httpx.Request):
        assert request.method == "POST"
        return httpx.Response(200, json=mock_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        source = JoobleSource(api_key="test_key")
        jobs = await source.fetch_query(client, "python developer fresher")

    assert len(jobs) == 2
    assert jobs[0].external_id == "jb_101"
    assert jobs[0].title == "Junior Python Developer"
    assert jobs[0].company == "Infosys"
    assert jobs[0].source == "jooble"
    assert jobs[1].external_id == "jb_102"
