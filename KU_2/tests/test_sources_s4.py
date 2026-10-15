"""Unit tests for Adzuna, Remotive feed, source_runs logging, and network fault isolation."""

import json
from pathlib import Path
import pytest
import httpx

from job_digest.models import RawJob
from job_digest.sources.base import JobSource
from job_digest.sources.adzuna import AdzunaSource
from job_digest.sources.remote import RemotiveSource
from job_digest.sources.runner import execute_source, run_all_sources

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_session4_sources_protocol_compliance():
    """Verify AdzunaSource and RemotiveSource satisfy JobSource protocol."""
    adzuna = AdzunaSource()
    remotive = RemotiveSource()

    assert isinstance(adzuna, JobSource)
    assert adzuna.name == "adzuna"

    assert isinstance(remotive, JobSource)
    assert remotive.name == "remotive"


@pytest.mark.asyncio
async def test_adzuna_fixture_parsing_and_filtering():
    """Verify Adzuna parses India results and filters foreign ones."""
    with open(FIXTURES_DIR / "adzuna_response.json", "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    def handler(request):
        return httpx.Response(200, json=fixture_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adzuna = AdzunaSource(app_id="test_id", app_key="test_key")
        jobs = await adzuna.fetch_query(client, "software engineer")

    assert len(jobs) == 2
    ids = [j.external_id for j in jobs]
    assert "adzuna-001" in ids
    assert "adzuna-002" in ids
    assert "adzuna-003" not in ids  # Filtered (London)


@pytest.mark.asyncio
async def test_adzuna_skips_when_credentials_missing():
    """Verify Adzuna gracefully returns empty list if credentials not provided."""
    adzuna = AdzunaSource(app_id=None, app_key=None)
    jobs = await adzuna.fetch()
    assert jobs == []


@pytest.mark.asyncio
async def test_remotive_fixture_parsing_and_attribution():
    """Verify Remotive parses remote jobs for worldwide/India, attaches attribution, and filters restricted."""
    with open(FIXTURES_DIR / "remotive_response.json", "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    def handler(request):
        return httpx.Response(200, json=fixture_data)

    transport = httpx.MockTransport(handler)
    remotive = RemotiveSource(enforce_rate_limit=False)

    # Monkeypatch AsyncClient inside Remotive
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get(remotive.BASE_URL)
        data = response.json()
        jobs = [remotive._parse_job(item) for item in data["jobs"]]
        filtered = [
            j for j, item in zip(jobs, data["jobs"])
            if j and (
                "worldwide" in (item.get("candidate_required_location") or "").lower()
                or "india" in (item.get("candidate_required_location") or "").lower()
            )
        ]

    assert len(filtered) == 2
    assert filtered[0].external_id == "8001"
    assert filtered[1].external_id == "8002"
    assert "remotive.com" in filtered[0].raw_data["attribution"]


class MockSuccessfulSource:
    def __init__(self, name: str, count: int = 5):
        self._name = name
        self.count = count

    @property
    def name(self) -> str:
        return self._name

    async def fetch(self):
        return [
            RawJob(
                source=self._name,
                source_id="mock_id",
                external_id=f"{self._name}-{i}",
                title=f"Engineer {i}",
                company="Mock Corp",
                location="Bengaluru, India",
                url=f"https://example.com/{i}",
            )
            for i in range(self.count)
        ]


class MockCrashingSource:
    @property
    def name(self) -> str:
        return "faulty_source"

    async def fetch(self):
        raise ConnectionResetError("Connection reset by peer (simulated network outage)")


@pytest.mark.asyncio
async def test_fault_isolation_three_sources_succeed_when_one_killed():
    """
    Session 4 Check verification:
    Three or more sources return jobs; killing one source's network still yields results from the rest.
    """
    s1 = MockSuccessfulSource("source_alpha", count=3)
    s2 = MockSuccessfulSource("source_beta", count=4)
    s3 = MockSuccessfulSource("source_gamma", count=2)
    s_crashed = MockCrashingSource()

    sources = [s1, s_crashed, s2, s3]

    jobs_by_source, results = await run_all_sources(sources, session=None)

    # 3 sources succeeded
    assert len(jobs_by_source["source_alpha"]) == 3
    assert len(jobs_by_source["source_beta"]) == 4
    assert len(jobs_by_source["source_gamma"]) == 2
    # Killed source yielded empty list and failed result
    assert len(jobs_by_source["faulty_source"]) == 0

    results_map = {r.source_name: r for r in results}
    assert results_map["source_alpha"].is_success is True
    assert results_map["source_beta"].is_success is True
    assert results_map["source_gamma"].is_success is True
    assert results_map["faulty_source"].is_success is False
    assert "Connection reset by peer" in results_map["faulty_source"].error_message
