"""Unit tests for EmailAlertSource, sender filtering, untrusted HTML safety, and fixtures."""

from pathlib import Path
import pytest
from job_digest.sources.base import JobSource
from job_digest.sources.email_alerts import (
    DEFAULT_ALLOWED_SENDERS,
    EmailAlertSource,
    parse_alert_message,
    parse_eml_bytes,
    sanitize_url,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_email_source_protocol_compliance():
    """Verify EmailAlertSource satisfies JobSource protocol."""
    source = EmailAlertSource()
    assert isinstance(source, JobSource)
    assert source.name == "email_alerts"


def test_sanitize_url():
    """Verify URL sanitizer permits only valid HTTP/HTTPS URLs."""
    assert sanitize_url("https://www.linkedin.com/jobs/view/123") == "https://www.linkedin.com/jobs/view/123"
    assert sanitize_url("http://example.com/job") == "http://example.com/job"
    # Malicious or unsupported schemes must be rejected
    assert sanitize_url("javascript:alert(1)") is None
    assert sanitize_url("data:text/html,<script>alert(1)</script>") is None
    assert sanitize_url("file:///etc/passwd") is None
    assert sanitize_url("") is None
    assert sanitize_url("invalid-url-string") is None


def test_parse_linkedin_alert_fixture():
    """Verify parsing LinkedIn alert email fixture extracts valid jobs."""
    eml_path = FIXTURES_DIR / "sample_linkedin_alert.eml"
    with open(eml_path, "rb") as f:
        eml_bytes = f.read()

    mid, jobs = parse_eml_bytes(eml_bytes)

    assert "linkedin-alert" in mid
    assert len(jobs) == 2

    job1 = jobs[0]
    assert job1.source == "email_alerts"
    assert job1.source_id == "linkedin_alerts"
    assert "Junior Python Developer" in job1.title
    assert "4123456789" in job1.external_id
    assert "linkedin.com/jobs/view/4123456789" in job1.url

    job2 = jobs[1]
    assert "Associate Software Engineer - ML" in job2.title
    assert "4123456790" in job2.external_id


def test_parse_naukri_alert_fixture():
    """Verify parsing Naukri alert email fixture extracts valid jobs."""
    eml_path = FIXTURES_DIR / "sample_naukri_alert.eml"
    with open(eml_path, "rb") as f:
        eml_bytes = f.read()

    mid, jobs = parse_eml_bytes(eml_bytes)

    assert "naukri-alert" in mid
    assert len(jobs) == 2

    job1 = jobs[0]
    assert job1.source == "email_alerts"
    assert job1.source_id == "naukri_alerts"
    assert "React Frontend Intern" in job1.title
    assert "naukri.com/job-listings-" in job1.url

    job2 = jobs[1]
    assert "Data Analyst Trainee" in job2.title


def test_mail_from_unknown_sender_is_ignored():
    """
    Session 5 Check verification:
    Mail from unknown/unauthorized senders is completely ignored.
    """
    eml_path = FIXTURES_DIR / "sample_unknown_sender.eml"
    with open(eml_path, "rb") as f:
        eml_bytes = f.read()

    mid, jobs = parse_eml_bytes(eml_bytes)

    # Unknown sender promo@unauthorized-promotions.com is ignored
    assert jobs == []


def test_untrusted_html_and_malicious_script_sanitized():
    """Verify scripts and malicious tags inside email body do not break parser or inject bad URLs."""
    malicious_body = """
    <html>
      <body>
        <script>window.location='https://attacker.com';</script>
        <a href="javascript:alert('xss')">Click for free money</a>
        <a href="https://www.linkedin.com/jobs/view/9999999999">Legitimate Role</a>
      </body>
    </html>
    """
    jobs = parse_alert_message(
        sender="jobalerts-noreply@linkedin.com",
        body=malicious_body,
        message_id="msg_test_001",
    )

    # Only legitimate link is extracted; javascript: link was discarded
    assert len(jobs) == 1
    assert jobs[0].url == "https://www.linkedin.com/jobs/view/9999999999"
    assert "alert" not in jobs[0].url
