"""Unit tests for ArbeitnowSource adapter."""

import pytest
import httpx

from job_digest.sources.base import JobSource
from job_digest.sources.arbeitnow import ArbeitnowSource


def test_arbeitnow_protocol_compliance():
    """Verify ArbeitnowSource satisfies JobSource protocol."""
    source = ArbeitnowSource()
    assert isinstance(source, JobSource)
    assert source.name == "arbeitnow"


@pytest.mark.asyncio
async def test_arbeitnow_fetch_parsing():
    """Verify Arbeitnow parses remote jobs."""
    mock_payload = {
        "data": [
            {
                "slug": "python-developer-123",
                "company_name": "Acme Corp",
                "title": "Backend Python Engineer",
                "description": "Python, FastAPI, Postgres",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/python-developer-123",
                "tags": ["Python", "FastAPI"],
                "job_types": ["Full Time"],
                "location": "Remote",
                "created_at": 1728900000,
            },
            {
                "slug": "on-site-berlin-456",
                "company_name": "Berlin GmbH",
                "title": "Office Admin",
                "remote": False,
                "url": "https://www.arbeitnow.com/jobs/berlin-456",
                "location": "Berlin, Germany",
            },
        ]
    }

    def handler(request: httpx.Request):
        return httpx.Response(200, json=mock_payload)

    transport = httpx.MockTransport(handler)
    source = ArbeitnowSource()
    # Temporarily override client session
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.get(source.BASE_URL)
        payload = resp.json()

    assert len(payload["data"]) == 2
    parsed = [source._parse_job(item) for item in payload["data"]]
    assert parsed[0] is not None
    assert parsed[0].title == "Backend Python Engineer"
    assert parsed[0].company == "Acme Corp"
    assert parsed[0].source == "arbeitnow"
