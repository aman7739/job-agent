"""Tests for the ATS Slug Checker and Source Expansion Utility."""

import tempfile
from pathlib import Path
import pytest
import yaml

from scripts.check_ats_slugs import (
    check_greenhouse_slug,
    check_lever_slug,
    check_ashby_slug,
    check_smartrecruiters_slug,
    merge_into_sources_yaml,
)


class MockResponse:
    def __init__(self, status_code: int, json_data: any):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


class MockClient:
    def __init__(self, responses: dict):
        self.responses = responses

    async def get(self, url: str):
        for pattern, resp in self.responses.items():
            if pattern in url:
                return resp
        return MockResponse(404, {})


@pytest.mark.asyncio
async def test_check_greenhouse_slug_parsing():
    client = MockClient({
        "boards-api.greenhouse.io/v1/boards/testcompany/jobs": MockResponse(
            200,
            {
                "jobs": [
                    {"id": 1, "title": "Software Engineer", "location": {"name": "Bengaluru, India"}},
                    {"id": 2, "title": "Backend Dev", "location": {"name": "New York, USA"}},
                    {"id": 3, "title": "Intern", "location": {"name": "Remote - India"}},
                ]
            },
        )
    })

    result = await check_greenhouse_slug(client, "testcompany")
    assert result is not None
    assert result["ats"] == "greenhouse"
    assert result["slug"] == "testcompany"
    assert result["total_jobs"] == 3
    assert result["india_jobs"] == 2
    assert len(result["samples"]) == 2


@pytest.mark.asyncio
async def test_check_lever_slug_parsing():
    client = MockClient({
        "api.lever.co/v0/postings/testlever": MockResponse(
            200,
            [
                {"id": "a", "text": "Frontend Engineer", "categories": {"location": "Gurugram, India"}},
                {"id": "b", "text": "Product Designer", "categories": {"location": "London"}},
            ],
        )
    })

    result = await check_lever_slug(client, "testlever")
    assert result is not None
    assert result["ats"] == "lever"
    assert result["slug"] == "testlever"
    assert result["total_jobs"] == 2
    assert result["india_jobs"] == 1


@pytest.mark.asyncio
async def test_check_ashby_slug_parsing():
    client = MockClient({
        "api.ashbyhq.com/posting-api/job-board/testashby": MockResponse(
            200,
            {
                "jobs": [
                    {"id": "x1", "title": "ML Engineer", "location": "Pune, India", "isListed": True},
                    {"id": "x2", "title": "Draft Role", "location": "Pune, India", "isListed": False},
                ]
            },
        )
    })

    result = await check_ashby_slug(client, "testashby")
    assert result is not None
    assert result["ats"] == "ashby"
    assert result["total_jobs"] == 2
    assert result["india_jobs"] == 1  # Unlisted role skipped


@pytest.mark.asyncio
async def test_check_smartrecruiters_slug_parsing():
    client = MockClient({
        "api.smartrecruiters.com/v1/companies/testsr/postings": MockResponse(
            200,
            {
                "content": [
                    {"id": "sr1", "name": "Systems Engineer", "location": {"city": "Noida", "country": "in"}},
                ]
            },
        )
    })

    result = await check_smartrecruiters_slug(client, "testsr")
    assert result is not None
    assert result["ats"] == "smartrecruiters"
    assert result["total_jobs"] == 1
    assert result["india_jobs"] == 1


def test_merge_into_sources_yaml():
    initial_yaml = {
        "version": 1,
        "greenhouse": ["existing_gh"],
        "lever": ["existing_lev"],
        "ashby": [],
    }

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml") as tmp:
        yaml.dump(initial_yaml, tmp)
        tmp_path = Path(tmp.name)

    try:
        discoveries = [
            {"company": "New Corp", "ats": "greenhouse", "slug": "new_corp_gh", "india_jobs": 5},
            {"company": "Existing Corp", "ats": "greenhouse", "slug": "existing_gh", "india_jobs": 2},
            {"company": "No India Corp", "ats": "lever", "slug": "no_in", "india_jobs": 0},
            {"company": "New Ashby", "ats": "ashby", "slug": "new_ashby", "india_jobs": 3},
        ]

        added_count, summary = merge_into_sources_yaml(discoveries, tmp_path)
        assert added_count == 2  # new_corp_gh and new_ashby added; existing_gh deduplicated; no_in skipped
        assert len(summary) == 2

        with open(tmp_path, "r", encoding="utf-8") as f:
            updated = yaml.safe_load(f)

        assert "new_corp_gh" in updated["greenhouse"]
        assert "existing_gh" in updated["greenhouse"]
        assert "new_ashby" in updated["ashby"]
        assert "no_in" not in (updated.get("lever") or [])
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
