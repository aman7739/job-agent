"""Unit tests for master pipeline orchestrator, dry-run mode, and scheduled workflow."""

from pathlib import Path
import pytest
import yaml

from job_digest.run import instantiate_notifiers, instantiate_sources, run_digest_pipeline
from job_digest.config import SourcesConfig
from job_digest.profile import load_profile_from_file

PROFILE = load_profile_from_file(Path(__file__).resolve().parent.parent / "profile.example.yaml")


def test_instantiate_sources():
    """Verify all 8 source adapters are instantiated properly."""
    cfg = SourcesConfig(
        greenhouse=["test"],
        lever=["test"],
        ashby=["test"],
        smartrecruiters=["test"],
        workable=["test"],
    )
    sources = instantiate_sources(cfg)
    assert len(sources) == 8
    names = {s.name for s in sources}
    expected = {
        "greenhouse", "lever", "ashby", "smartrecruiters",
        "workable", "remotive", "adzuna", "email_alerts",
    }
    assert names == expected


def test_instantiate_notifiers():
    """Verify configured channels from profile are instantiated."""
    notifiers = instantiate_notifiers(PROFILE)
    names = {n.channel_name for n in notifiers}
    assert "telegram" in names
    assert "email" in names


@pytest.mark.asyncio
async def test_run_digest_pipeline_dry_run_offline():
    """
    Session 11 Check:
    Verify manual run executes the complete pipeline and generates a digest.
    """
    # Run with empty source list to test full pipeline flow without network calls
    result = await run_digest_pipeline(dry_run=True, active_sources=[])

    assert result["status"] == "success"
    assert "timestamp" in result
    assert result["total_in_digest"] == 0
    assert "digest_text" in result
    assert "No new matching jobs found this morning" in result["digest_text"]


def test_workflow_yaml_syntax_and_cron():
    """Verify .github/workflows/daily-digest.yml is valid YAML and scheduled for 08:00 IST (02:30 UTC)."""
    wf_path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "daily-digest.yml"
    assert wf_path.is_file(), "daily-digest.yml workflow must exist"

    with open(wf_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["name"] == "Daily Job Digest"
    on_trigger = data.get("on") or data.get(True)
    assert on_trigger is not None, "Workflow must define 'on' triggers"
    assert "workflow_dispatch" in on_trigger

    schedules = on_trigger["schedule"]
    assert any(s.get("cron") == "30 2 * * *" for s in schedules), "Expected cron '30 2 * * *' (08:00 IST)"
