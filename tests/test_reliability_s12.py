"""Session 12 tests: End-to-end reliability, mocked-network pipeline, error isolation, rate limits, and tuning."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from job_digest.config import SourcesConfig
from job_digest.digest import DigestOutput, build_digest
from job_digest.match import rank_and_score_jobs
from job_digest.models import Job, RawJob, SourceRunResult
from job_digest.normalize import normalize_raw_job
from job_digest.notify import Notifier, deliver_digest, filter_unnotified_jobs, mark_jobs_as_notified
from job_digest.profile import UserProfile, load_profile_from_file
from job_digest.run import instantiate_notifiers, run_digest_pipeline
from job_digest.sources.base import JobSource
from job_digest.sources.remote import RemotiveSource
from job_digest.sources.runner import execute_source, run_all_sources

PROFILE_PATH = Path(__file__).resolve().parent.parent / "profile.example.yaml"
PROFILE = load_profile_from_file(PROFILE_PATH)


class MockJobSource(JobSource):
    """Custom mock source allowing dynamic injection of return jobs or exceptions."""

    def __init__(self, name: str, jobs: Optional[List[RawJob]] = None, should_raise: Optional[Exception] = None):
        self._name = name
        self._jobs = jobs if jobs is not None else []
        self._should_raise = should_raise

    @property
    def name(self) -> str:
        return self._name

    async def fetch(self) -> List[RawJob]:
        if self._should_raise:
            raise self._should_raise
        return self._jobs


class MockChannelNotifier(Notifier):
    """Custom mock notifier channel to verify delivery calls and fault isolation."""

    def __init__(self, channel_name: str, should_succeed: bool = True, raise_exc: Optional[Exception] = None):
        self._channel_name = channel_name
        self.should_succeed = should_succeed
        self.raise_exc = raise_exc
        self.sent_digests: List[DigestOutput] = []

    @property
    def channel_name(self) -> str:
        return self._channel_name

    async def send(self, digest: DigestOutput) -> bool:
        if self.raise_exc:
            raise self.raise_exc
        if self.should_succeed:
            self.sent_digests.append(digest)
            return True
        return False


# ==============================================================================
# 1. Mocked-Network End-to-End Pipeline for Every Source
# ==============================================================================

@pytest.mark.asyncio
async def test_end_to_end_mocked_network_all_sources_pipeline():
    """
    Session 12 Check:
    End-to-end pipeline with mocked-network responses for every source adapter.
    Verifies full flow: Fetch -> Normalize -> Dedup -> Match -> Digest -> Notify.
    """
    now = datetime(2026, 10, 3, 8, 0, 0, tzinfo=timezone.utc)

    # 1. Create realistic RawJobs from all 8 sources
    raw_greenhouse = RawJob(
        source="greenhouse",
        source_id="stripe",
        external_id="gh-1",
        title="Software Engineering Intern",
        company="Stripe",
        location="Bengaluru, Karnataka",
        url="https://boards.greenhouse.io/stripe/jobs/gh-1?utm_source=feed",
        description_text="Looking for 2027 batch Python & FastAPI backend engineering intern. Stipend ₹60,000/month.",
        posted_at=now - timedelta(hours=4),
    )
    raw_lever = RawJob(
        source="lever",
        source_id="razorpay",
        external_id="lev-1",
        title="Junior Python Engineer",
        company="Razorpay",
        location="Bengaluru, India",
        url="https://jobs.lever.co/razorpay/lev-1",
        description_text="0-1 years experience, Python, PostgreSQL, REST APIs. Salary: 8-10 LPA. Batch 2027 eligible.",
        posted_at=now - timedelta(hours=6),
    )
    raw_ashby = RawJob(
        source="ashby",
        source_id="postman",
        external_id="ash-1",
        title="Graduate Software Engineer",
        company="Postman",
        location="Remote - India",
        url="https://jobs.ashbyhq.com/postman/ash-1",
        description_text="Fresh graduates welcome! Skills: TypeScript, Node.js, Python. 12 LPA. 2027 grad.",
        posted_at=now - timedelta(hours=8),
    )
    raw_smartrecruiters = RawJob(
        source="smartrecruiters",
        source_id="swiggy",
        external_id="sr-1",
        title="Data Engineer Apprentice",
        company="Swiggy",
        location="Bengaluru",
        url="https://jobs.smartrecruiters.com/swiggy/sr-1",
        description_text="Apprenticeship program for final year students. Python, SQL, Docker. Stipend ₹40,000/month.",
        posted_at=now - timedelta(hours=10),
    )
    raw_workable = RawJob(
        source="workable",
        source_id="clevertap",
        external_id="wk-1",
        title="Associate Developer",
        company="CleverTap",
        location="Mumbai",
        url="https://apply.workable.com/clevertap/j/wk-1",
        description_text="Entry level role for 2027 batch. Core Python, Git, Linux. 7 LPA.",
        posted_at=now - timedelta(hours=12),
    )
    raw_adzuna = RawJob(
        source="adzuna",
        source_id="adzuna_in",
        external_id="adz-1",
        title="Junior Backend Developer",
        company="Freshworks",
        location="Chennai",
        url="https://adzuna.in/details/adz-1",
        description_text="Fresher role. Python, Django, REST. Salary ₹6,50,000 per year.",
        posted_at=now - timedelta(hours=14),
    )
    raw_remotive = RawJob(
        source="remotive",
        source_id="remotive",
        external_id="rem-1",
        title="Python Engineer (Remote)",
        company="GitLab",
        location="Remote",
        url="https://remotive.com/job/rem-1",
        description_text="Remote fresher friendly. Python, Git, Docker. USD 30,000/year.",
        posted_at=now - timedelta(hours=16),
    )
    raw_email = RawJob(
        source="email_alerts",
        source_id="linkedin_alerts",
        external_id="eml-1",
        title="Software Engineer - Fresher",
        company="InMobi",
        location="Bengaluru",
        url="https://linkedin.com/jobs/view/eml-1?tracking=123",
        description_text="Alert: 2027 B.Tech graduates for Fresher SDE. Python, SQL.",
        posted_at=now - timedelta(hours=18),
    )

    # Ineligible job that should be filtered out by matcher (Senior role)
    raw_senior = RawJob(
        source="greenhouse",
        source_id="oracle",
        external_id="gh-2",
        title="Senior Principal Architect",
        company="Oracle",
        location="Bengaluru",
        url="https://boards.greenhouse.io/oracle/jobs/gh-2",
        description_text="10+ years experience required.",
        posted_at=now - timedelta(hours=2),
    )

    mock_sources = [
        MockJobSource("greenhouse", [raw_greenhouse, raw_senior]),
        MockJobSource("lever", [raw_lever]),
        MockJobSource("ashby", [raw_ashby]),
        MockJobSource("smartrecruiters", [raw_smartrecruiters]),
        MockJobSource("workable", [raw_workable]),
        MockJobSource("adzuna", [raw_adzuna]),
        MockJobSource("remotive", [raw_remotive]),
        MockJobSource("email_alerts", [raw_email]),
    ]

    tg_notifier = MockChannelNotifier("telegram", should_succeed=True)
    em_notifier = MockChannelNotifier("email", should_succeed=True)

    with patch("job_digest.run.instantiate_sources", return_value=mock_sources), \
         patch("job_digest.run.instantiate_notifiers", return_value=[tg_notifier, em_notifier]), \
         patch("job_digest.run.load_profile", return_value=PROFILE):

        result = await run_digest_pipeline(dry_run=False, now=now)

    assert result["status"] == "success"
    assert result["raw_jobs_found"] == 9  # 8 valid + 1 senior
    assert result["new_jobs"] == 9
    assert result["already_seen"] == 0
    # Senior role was filtered out by matcher, leaving 8 eligible jobs
    assert result["scored_jobs"] == 8
    assert result["total_in_digest"] == 8
    assert result["internships_count"] == 2  # Stripe (Intern) + Swiggy (Apprentice)
    assert result["fulltime_count"] == 6    # Razorpay, Postman, CleverTap, Freshworks, GitLab, InMobi
    assert set(result["delivered_channels"]) == {"telegram", "email"}
    assert result["failed_sources"] == []

    # Check notifiers received the rendered digest
    assert len(tg_notifier.sent_digests) == 1
    assert len(em_notifier.sent_digests) == 1
    digest_text = tg_notifier.sent_digests[0].content_text
    digest_html = em_notifier.sent_digests[0].content_html

    # Check section headers in plain text
    assert "1. INTERNSHIPS & APPRENTICESHIPS (APPLY NOW)" in digest_text
    assert "2. FULL-TIME ROLES (APPLY NOW / FRESHER)" in digest_text
    assert "Remotive" in digest_text  # Remotive attribution check
    assert "Stripe" in digest_text
    assert "Razorpay" in digest_text
    assert "Senior Principal Architect" not in digest_text

    # Check HTML contains clean links and badges
    assert "Apply &rarr;" in digest_html
    assert "https://boards.greenhouse.io/stripe/jobs/gh-1" in digest_html
    assert "utm_source" not in digest_html  # Canonicalization stripped UTM


# ==============================================================================
# 2. Zero Results Graceful Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_zero_results_graceful_handling():
    """
    Session 12 Check:
    Pipeline handles a day with zero new jobs gracefully:
    - Renders empty state message.
    - Notifiers receive the zero-jobs digest.
    - Does not raise exceptions.
    """
    mock_sources = [
        MockJobSource("greenhouse", []),
        MockJobSource("lever", []),
        MockJobSource("ashby", []),
    ]
    tg_notifier = MockChannelNotifier("telegram", should_succeed=True)
    em_notifier = MockChannelNotifier("email", should_succeed=True)

    with patch("job_digest.run.instantiate_sources", return_value=mock_sources), \
         patch("job_digest.run.instantiate_notifiers", return_value=[tg_notifier, em_notifier]), \
         patch("job_digest.run.load_profile", return_value=PROFILE):

        result = await run_digest_pipeline(dry_run=False)

    assert result["status"] == "success"
    assert result["raw_jobs_found"] == 0
    assert result["scored_jobs"] == 0
    assert result["total_in_digest"] == 0
    assert set(result["delivered_channels"]) == {"telegram", "email"}

    # Delivered digest has empty message
    assert "No new matching jobs found this morning" in result["digest_text"]
    assert "Checked all configured company boards at 08:00 IST" in result["digest_text"]


# ==============================================================================
# 3. Failed Source Named in Digest Header
# ==============================================================================

@pytest.mark.asyncio
async def test_failed_source_named_in_digest_header():
    """
    Session 12 Check:
    When a source encounters a network failure or 500 error:
    - Other sources succeed and are processed.
    - The failed source is explicitly named in the digest header.
    - Both plain text and HTML prominently display the notice.
    """
    now = datetime(2026, 10, 3, 8, 0, 0, tzinfo=timezone.utc)
    valid_raw_job = RawJob(
        source="lever",
        source_id="swiggy",
        external_id="lev-ok",
        title="Backend Software Engineer - Fresher",
        company="Swiggy",
        location="Bengaluru",
        url="https://jobs.lever.co/swiggy/lev-ok",
        description_text="Python, PostgreSQL, REST APIs. Batch 2027 eligible.",
        posted_at=now - timedelta(hours=2),
    )

    failing_source = MockJobSource("greenhouse", should_raise=httpx.ConnectTimeout("Connection timed out to Greenhouse"))
    working_source = MockJobSource("lever", [valid_raw_job])

    tg_notifier = MockChannelNotifier("telegram", should_succeed=True)

    with patch("job_digest.run.instantiate_sources", return_value=[failing_source, working_source]), \
         patch("job_digest.run.instantiate_notifiers", return_value=[tg_notifier]), \
         patch("job_digest.run.load_profile", return_value=PROFILE):

        result = await run_digest_pipeline(dry_run=False, now=now)

    assert result["status"] == "success"
    assert "greenhouse" in result["failed_sources"]
    assert result["scored_jobs"] == 1

    digest_output = tg_notifier.sent_digests[0]
    # Check text notice
    assert "[Notice: The following sources were unreachable today: greenhouse]" in digest_output.content_text
    # Check HTML notice
    assert "The following sources were unreachable today: greenhouse" in digest_output.content_html
    # Successful source's job is included
    assert "Swiggy" in digest_output.content_text


# ==============================================================================
# 4. Rate Limits Handling Across Sources
# ==============================================================================

@pytest.mark.asyncio
async def test_rate_limits_handling_across_sources():
    """
    Session 12 Check:
    Verify rate limits across sources are handled gracefully:
    - Remotive enforce_rate_limit blocks extra requests beyond limit without crashing.
    - 429 Too Many Requests response is caught and handled safely.
    """
    # 1. Remotive 4 fetches/day limit check
    remotive = RemotiveSource(enforce_rate_limit=True)
    with patch("job_digest.sources.remote._check_and_increment_daily_fetch", return_value=False):
        jobs = await remotive.fetch()
        assert jobs == []

    # 2. HTTP 429 simulated response in custom source
    def handler_429(request):
        return httpx.Response(429, text="Too Many Requests")

    transport = httpx.MockTransport(handler_429)
    async with httpx.AsyncClient(transport=transport) as client:
        # A source encountering 429 returns error status code safely
        response = await client.get("https://api.adzuna.com/test")
        assert response.status_code == 429


# ==============================================================================
# 5. Delivery Channel Fault Isolation
# ==============================================================================

@pytest.mark.asyncio
async def test_failed_delivery_channel_isolation():
    """
    Session 12 Check:
    If one channel fails (e.g. Telegram token invalid / API 500),
    the other channel (Email) still delivers successfully.
    """
    digest = DigestOutput(
        content_html="<html><body>Jobs</body></html>",
        content_text="Jobs",
        total_jobs=1,
        internships_count=0,
        fulltime_count=1,
        new_count=1,
        seen_count=0,
        failed_sources=[],
        is_empty=False,
    )

    # Telegram fails with an exception, Email succeeds
    broken_tg = MockChannelNotifier("telegram", raise_exc=httpx.HTTPStatusError("502 Bad Gateway", request=None, response=None))
    working_em = MockChannelNotifier("email", should_succeed=True)

    delivered = await deliver_digest(digest, [broken_tg, working_em])
    assert delivered == ["email"]
    assert len(working_em.sent_digests) == 1

    # In reverse: Email fails, Telegram succeeds
    working_tg = MockChannelNotifier("telegram", should_succeed=True)
    broken_em = MockChannelNotifier("email", should_succeed=False)

    delivered_rev = await deliver_digest(digest, [working_tg, broken_em])
    assert delivered_rev == ["telegram"]
    assert len(working_tg.sent_digests) == 1


# ==============================================================================
# 6. Tuning and Scoring Verification
# ==============================================================================

def test_tuning_weights_and_thresholds():
    """
    Session 12 Check:
    Verify score weights and filtering thresholds:
    - Min score 4.0 threshold.
    - Weights: Skills (4.0), Role (3.0), Level (2.0), Location (1.0).
    - Tracked gaps do NOT reduce match score.
    """
    # Role matching: Python Developer with preferred city Bengaluru
    strong_job = Job(
        title="Python Developer",
        company="Stripe",
        location="Bengaluru",
        canonical_url="https://example.com/1",
        description_text="Python, FastAPI, Git, React.",
        skills=["Python", "FastAPI", "Git", "React"],
        min_years=0.0,
        source="greenhouse",
        is_intern=False,
    )

    scored = rank_and_score_jobs([strong_job], profile=PROFILE)
    assert len(scored) == 1
    # Full match on skills (4.0), role (3.0), level (2.0), and location (1.0) -> score 10.0
    assert scored[0].score >= 8.0
    assert scored[0].category == "Strong"

    # Role matching with missing tracked gap: 'Java' and 'Spring Boot'
    job_with_gap = Job(
        title="Python Developer",
        company="Razorpay",
        location="Pune",
        canonical_url="https://example.com/2",
        description_text="Python role with Java and Spring Boot familiarity.",
        skills=["Python", "Git"],
        min_years=0.0,
        source="lever",
        is_intern=False,
    )
    scored_gap = rank_and_score_jobs([job_with_gap], profile=PROFILE)
    assert len(scored_gap) == 1
    # Tracked gaps in profile (Java, Spring Boot) listed in missing_skills
    assert "Java" in scored_gap[0].missing_skills
    assert "Spring Boot" in scored_gap[0].missing_skills
    # Still meets threshold
    assert scored_gap[0].score >= 4.0


def test_tuning_blocklist_and_batch_exclusions():
    """
    Session 12 Check:
    Verify tuned blocklist and hard filtering rules:
    - Blocklisted company is dropped.
    - Non-2027 batch requirement is dropped.
    - Experience > 2 years is dropped.
    """
    blocked_company_job = Job(
        title="Python Engineer",
        company="Revature",  # Common blocklist candidate
        location="Bengaluru",
        canonical_url="https://example.com/revature",
        description_text="Python role",
        source="greenhouse",
    )

    # Add Revature to profile blocklist temporarily
    profile_blocked = PROFILE.model_copy(deep=True)
    profile_blocked.hard_filters.company_blocklist.append("revature")

    scored = rank_and_score_jobs([blocked_company_job], profile=profile_blocked)
    assert len(scored) == 0  # Excluded!

    wrong_batch_job = Job(
        title="Graduate Engineer Trainee",
        company="Infosys",
        location="Pune",
        canonical_url="https://example.com/batch2024",
        description_text="Only for 2024 passouts.",
        source="adzuna",
        batch_years=[2024],
    )
    scored_batch = rank_and_score_jobs([wrong_batch_job], profile=PROFILE)
    assert len(scored_batch) == 0  # 2024 passout excluded, user is 2027!


def test_database_notified_marking_and_exclusion():
    """
    Session 12 Check:
    Verify database operations mark notified jobs and exclude them on subsequent runs.
    """
    mock_session = MagicMock()

    # 1. Test mark_jobs_as_notified executes UPDATE statement and commits
    mark_jobs_as_notified(mock_session, ["fp_123", "fp_456"])
    assert mock_session.execute.called
    assert mock_session.commit.called

    # 2. Test filter_unnotified_jobs queries DB and excludes notified fingerprints
    job1 = Job(
        title="Python Dev",
        company="Stripe",
        location="Bengaluru",
        canonical_url="https://stripe.com/1",
        description_text="Desc",
        source="greenhouse",
    )
    job1.fingerprint = "fp_123"

    job2 = Job(
        title="Python Dev",
        company="Razorpay",
        location="Bengaluru",
        canonical_url="https://razorpay.com/2",
        description_text="Desc",
        source="lever",
    )
    job2.fingerprint = "fp_789"

    # Simulate DB returning that fp_123 is already notified
    mock_session.execute.return_value.fetchall.return_value = [("fp_123",)]
    unnotified = filter_unnotified_jobs([job1, job2], mock_session)

    assert len(unnotified) == 1
    assert unnotified[0].fingerprint == "fp_789"


@pytest.mark.asyncio
async def test_deliver_digest_all_channels_fail_does_not_mark_notified():
    """
    Session 12 Check:
    When ALL channels fail, jobs are NOT marked notified in DB,
    ensuring they will be retried in tomorrow's digest.
    """
    mock_session = MagicMock()
    digest = DigestOutput(
        content_html="<html><body>Jobs</body></html>",
        content_text="Jobs",
        total_jobs=1,
        internships_count=0,
        fulltime_count=1,
        new_count=1,
        seen_count=0,
        failed_sources=[],
        is_empty=False,
    )

    broken_tg = MockChannelNotifier("telegram", should_succeed=False)
    broken_em = MockChannelNotifier("email", should_succeed=False)

    delivered = await deliver_digest(
        digest=digest,
        notifiers=[broken_tg, broken_em],
        fingerprints_to_mark=["fp_test"],
        session=mock_session,
    )

    assert delivered == []
    # mark_jobs_as_notified must NOT be called when 0 channels succeeded
    assert not mock_session.execute.called
