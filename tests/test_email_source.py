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


def test_parse_indeed_alerts():
    """Verify parsing Indeed alert email extracts valid job links."""
    indeed_body = """
    <html>
      <body>
        <h2>New Jobs for You</h2>
        <a href="https://in.indeed.com/viewjob?jk=abcdef1234567890">Junior Software Engineer</a>
        <a href="https://in.indeed.com/rc/clk?jk=123456abcdef7890">Associate Python Developer</a>
        <a href="https://www.indeed.com/unrelated/page">Unrelated link</a>
      </body>
    </html>
    """
    jobs = parse_alert_message(
        sender="alert@indeed.com",
        body=indeed_body,
        message_id="msg_indeed_001",
    )

    assert len(jobs) == 2
    assert jobs[0].source == "email_alerts"
    assert jobs[0].source_id == "indeed_alerts"
    assert "Junior Software Engineer" in jobs[0].title
    assert jobs[0].external_id == "abcdef1234567890"
    assert "in.indeed.com/viewjob?jk=abcdef1234567890" in jobs[0].url

    assert "Associate Python Developer" in jobs[1].title
    assert jobs[1].external_id == "123456abcdef7890"


@pytest.mark.asyncio
async def test_email_source_fetch_unconfigured():
    """Verify EmailAlertSource.fetch returns empty list when unconfigured without crashing."""
    source = EmailAlertSource(imap_host="", imap_user="", imap_password="")
    jobs = await source.fetch()
    assert jobs == []


@pytest.mark.asyncio
async def test_email_source_fetch_with_header_filtering(monkeypatch):
    """Verify EmailAlertSource uses header-first inspection and only downloads bodies for allowed senders."""
    from unittest.mock import MagicMock
    import imaplib

    eml_path = FIXTURES_DIR / "sample_linkedin_alert.eml"
    with open(eml_path, "rb") as f:
        linkedin_eml_bytes = f.read()

    mock_mail = MagicMock()
    mock_mail.search.return_value = ("OK", [b"1 2"])

    def mock_fetch(msg_id, spec):
        if "HEADER.FIELDS" in spec:
            if msg_id == b"1":
                # Message 1 is spam / unknown sender
                return ("OK", [(b"1", b"From: promo@spam.com\r\nMessage-ID: <spam1@spam.com>\r\n\r\n")])
            else:
                # Message 2 is LinkedIn alerts
                return ("OK", [(b"2", b"From: jobalerts-noreply@linkedin.com\r\nMessage-ID: <alert2@linkedin.com>\r\n\r\n")])
        elif "BODY.PEEK[]" in spec or "RFC822" in spec:
            if msg_id == b"2":
                return ("OK", [(b"2", linkedin_eml_bytes)])
            return ("NO", [])
        return ("NO", [])

    mock_mail.fetch.side_effect = mock_fetch

    monkeypatch.setattr(imaplib, "IMAP4_SSL", lambda host, port, timeout=None: mock_mail)

    source = EmailAlertSource(
        imap_host="imap.example.com",
        imap_user="test@example.com",
        imap_password="test_password",
    )

    jobs = await source.fetch()

    # Message 1 (spam) should NOT have had its body fetched.
    # Message 2 (LinkedIn) had its body fetched and yielded jobs.
    assert len(jobs) == 2
    assert jobs[0].source_id == "linkedin_alerts"

    # Verify that mock_mail.fetch was called with BODY.PEEK[] ONLY for msg_id b"2", never for b"1"
    body_peek_calls = [
        call for call in mock_mail.fetch.call_args_list if "BODY.PEEK[]" in str(call)
    ]
    assert len(body_peek_calls) == 1
    assert body_peek_calls[0][0][0] == b"2"


def test_parse_internshala_alert():
    """Verify parsing Internshala alert email extracts internships and fresher jobs."""
    internshala_body = """
    <html>
      <body>
        <h2>Top Internships & Jobs for You</h2>
        <a href="https://internshala.com/internship/detail/python-development-internship-12345">Python Development Intern</a>
        <a href="https://internshala.com/job/detail/junior-backend-engineer-67890">Junior Backend Engineer</a>
        <a href="https://internshala.com/registration/student">Student Dashboard</a>
      </body>
    </html>
    """
    jobs = parse_alert_message(
        sender="alerts@mail.internshala.com",
        body=internshala_body,
        message_id="msg_is_001",
    )

    assert len(jobs) == 2
    assert jobs[0].source == "email_alerts"
    assert jobs[0].source_id == "internshala_alerts"
    assert "Python Development Intern" in jobs[0].title
    assert "python-development-internship-12345" in jobs[0].external_id
    assert jobs[0].raw_data.get("is_intern") is True

    assert "Junior Backend Engineer" in jobs[1].title
    assert "junior-backend-engineer-67890" in jobs[1].external_id


def test_parse_unstop_and_instahyre_alerts():
    """Verify parsing Unstop and Instahyre job alert emails."""
    unstop_body = """
    <html>
      <body>
        <h3>Exciting Opportunities for You</h3>
        <a href="https://unstop.com/jobs/graduate-trainee-software-engineer-54321">Graduate Trainee Software Engineer</a>
        <a href="https://unstop.com/competitions/hackathon-2026">Hackathon 2026</a>
      </body>
    </html>
    """
    unstop_jobs = parse_alert_message(
        sender="notifications@unstop.com",
        body=unstop_body,
        message_id="msg_unstop_01",
    )

    assert len(unstop_jobs) >= 1
    assert unstop_jobs[0].source_id == "unstop_alerts"
    assert "Graduate Trainee Software Engineer" in unstop_jobs[0].title

    instahyre_body = """
    <html>
      <body>
        <a href="https://www.instahyre.com/job-998877-associate-full-stack-engineer">Associate Full Stack Engineer</a>
      </body>
    </html>
    """
    instahyre_jobs = parse_alert_message(
        sender="jobs@instahyre.com",
        body=instahyre_body,
        message_id="msg_insta_01",
    )
    assert len(instahyre_jobs) == 1
    assert instahyre_jobs[0].source_id == "instahyre_alerts"
    assert "Associate Full Stack Engineer" in instahyre_jobs[0].title


def test_parse_wellfound_cutshort_glassdoor_alerts():
    """Verify parsing Wellfound, Cutshort, and Glassdoor job alerts."""
    wf_body = '<a href="https://wellfound.com/jobs/776655-junior-ai-engineer">Junior AI Engineer</a>'
    wf_jobs = parse_alert_message("talent@wellfound.com", wf_body, "msg_wf_01")
    assert len(wf_jobs) == 1
    assert wf_jobs[0].source_id == "wellfound_alerts"
    assert "Junior AI Engineer" in wf_jobs[0].title

    cs_body = '<a href="https://cutshort.io/job/Software-Developer-at-Innovaccer-112233">Software Developer</a>'
    cs_jobs = parse_alert_message("alerts@cutshort.io", cs_body, "msg_cs_01")
    assert len(cs_jobs) == 1
    assert cs_jobs[0].source_id == "cutshort_alerts"
    assert "Software Developer" in cs_jobs[0].title

    gd_body = '<a href="https://www.glassdoor.co.in/job-listing/data-scientist-intern-xyz?jl=445566">Data Scientist Intern</a>'
    gd_jobs = parse_alert_message("noreply@glassdoor.com", gd_body, "msg_gd_01")
    assert len(gd_jobs) == 1
    assert gd_jobs[0].source_id == "glassdoor_alerts"
    assert "Data Scientist Intern" in gd_jobs[0].title


def test_parse_direct_ats_career_alerts():
    """Verify parsing direct company ATS alerts (Greenhouse / SmartRecruiters)."""
    gh_body = '<a href="https://boards.greenhouse.io/swiggy/jobs/123456">Software Development Engineer Intern</a>'
    gh_jobs = parse_alert_message("no-reply@greenhouse.io", gh_body, "msg_gh_01")
    assert len(gh_jobs) == 1
    assert "Software Development Engineer Intern" in gh_jobs[0].title

    sr_body = '<a href="https://jobs.smartrecruiters.com/Swiggy/789012-associate-engineer">Associate Engineer</a>'
    sr_jobs = parse_alert_message("alerts@smartrecruiters.com", sr_body, "msg_sr_01")
    assert len(sr_jobs) == 1
    assert "Associate Engineer" in sr_jobs[0].title



