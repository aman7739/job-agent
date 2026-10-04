"""Tests for urgent alerts (< 4h left), on-demand notify button, and twice-daily schedule (8 AM & 7 PM IST)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from job_digest.auth import create_session_token, hash_password
from job_digest.models import Job
from job_digest.notify import TelegramNotifier, deliver_urgent_alert
from job_digest.urgency import detect_job_urgency
from job_digest.web import app


# ==============================================================================
# 1. Urgency Detection (< 4 Hours Left)
# ==============================================================================

def test_detect_job_urgency_explicit_deadline():
    """Verify jobs with explicit deadline <= 4h are flagged urgent."""
    now = datetime.now(timezone.utc)

    # Closing in 2 hours -> Urgent
    urgency_2h = detect_job_urgency(
        job_title="Software Intern",
        job_description="Python developer",
        deadline_at=now + timedelta(hours=2),
        now=now,
    )
    assert urgency_2h.is_urgent is True
    assert urgency_2h.hours_remaining == 2.0
    assert "2.0 hours" in urgency_2h.urgency_reason

    # Closing in 24 hours -> Not urgent
    urgency_24h = detect_job_urgency(
        job_title="Software Intern",
        job_description="Python developer",
        deadline_at=now + timedelta(hours=24),
        now=now,
    )
    assert urgency_24h.is_urgent is False


def test_detect_job_urgency_text_phrases():
    """Verify textual phrases like 'closes in 3 hours' trigger urgency."""
    now = datetime.now(timezone.utc)

    urgency_text = detect_job_urgency(
        job_title="Backend Fresher (Closing in 3 hours)",
        job_description="Please apply quickly, portal closing in 3 hours.",
        now=now,
    )
    assert urgency_text.is_urgent is True
    assert urgency_text.hours_remaining == 3.0

    urgency_urgent = detect_job_urgency(
        job_title="Urgent Hiring: Python Developer",
        job_description="Immediate hiring, closing today.",
        now=now,
    )
    assert urgency_urgent.is_urgent is True


# ==============================================================================
# 2. Urgent Alert Delivery (Immediate Telegram / Email)
# ==============================================================================

@pytest.mark.asyncio
async def test_deliver_urgent_alert():
    """Verify deliver_urgent_alert dispatches high-priority message immediately."""
    job = Job(
        title="Python Engineer Intern",
        company="Razorpay",
        location="Bengaluru",
        canonical_url="https://razorpay.com/jobs/123",
        description_text="Python and FastAPI developer",
        source="greenhouse",
        fingerprint="fp_urgent_123",
    )

    mock_telegram = MagicMock()
    mock_telegram.channel_name = "telegram"
    mock_telegram.send_message = AsyncMock(return_value=True)

    mock_email = MagicMock()
    mock_email.channel_name = "email"
    mock_email.send_message = AsyncMock(return_value=True)

    channels = await deliver_urgent_alert(
        job=job,
        score=9.0,
        urgency_reason="Closing in 2 hours",
        notifiers=[mock_telegram, mock_email],
    )

    assert "telegram" in channels
    assert "email" in channels

    # Telegram received urgent alert text
    tg_call_args = mock_telegram.send_message.call_args[0][0]
    assert "🚨 URGENT JOB ALERT" in tg_call_args
    assert "Razorpay" in tg_call_args
    assert "https://razorpay.com/jobs/123" in tg_call_args


# ==============================================================================
# 3. Web Dashboard "⚡ Check & Notify Now" Route
# ==============================================================================

def test_web_run_now_button():
    """Verify authenticated user can trigger POST /jobs/run-now."""
    client = TestClient(app)
    token = create_session_token("admin")
    client.cookies.set("session_token", token)

    mock_pipeline_result = {
        "status": "success",
        "new_jobs": 3,
        "total_in_digest": 5,
        "delivered_channels": ["telegram", "email"],
        "urgent_alerts_sent": 1,
    }

    with patch("job_digest.run.run_digest_pipeline", new=AsyncMock(return_value=mock_pipeline_result)):
        response = client.post("/jobs/run-now", follow_redirects=True)
        assert response.status_code == 200
        # Check that flash notice is rendered on digest view
        assert "Check completed!" in response.text
        assert "Found 3 new roles" in response.text
        assert "Sent 1 urgent closing alerts" in response.text


# ==============================================================================
# 4. Schedule Verification (8 AM & 7 PM IST = 02:30 & 13:30 UTC)
# ==============================================================================

def test_github_workflow_and_scheduler_cron():
    """Verify GitHub Actions and local scheduler run twice daily (8 AM & 7 PM IST)."""
    from pathlib import Path
    import re

    # 1. Check daily-digest.yml
    workflow_path = Path(".github/workflows/daily-digest.yml")
    assert workflow_path.exists()
    content = workflow_path.read_text(encoding="utf-8")
    assert "30 2,13 * * *" in content

    # 2. Check run.py start_local_scheduler
    run_path = Path("job_digest/run.py")
    run_content = run_path.read_text(encoding="utf-8")
    assert 'hour="2,13"' in run_content
    assert 'minute="30"' in run_content
