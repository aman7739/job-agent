"""IMAP Email Alerts job source with sender filtering and untrusted content parsing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import email
from email.header import decode_header
from email.message import Message
from html.parser import HTMLParser
import imaplib
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
from sqlalchemy import text
from sqlalchemy.orm import Session

from job_digest.models import RawJob
from job_digest.sources.base import is_india_or_remote

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_SENDERS = {
    # LinkedIn
    "jobalerts-noreply@linkedin.com",
    "jobs-noreply@linkedin.com",
    "messages-noreply@linkedin.com",
    # Naukri
    "alerts@naukri.com",
    "info@naukri.com",
    # Indeed
    "alert@indeed.com",
    "jobalerts-noreply@indeed.com",
    "noreply@indeed.com",
    "do-not-reply@indeed.com",
    "alerts@indeed.com",
    # Internshala (Internships & Fresher Jobs)
    "alerts@internshala.com",
    "digest@internshala.com",
    "student@internshala.com",
    # Unstop / Dare2Compete (Freshers & Competitions)
    "alerts@unstop.com",
    "updates@unstop.com",
    "notifications@unstop.com",
    # Instahyre (Curated Tech Jobs)
    "jobs@instahyre.com",
    "alerts@instahyre.com",
    "notifications@instahyre.com",
    # Wellfound / AngelList (Startup Roles)
    "talent@wellfound.com",
    "jobs@wellfound.com",
    # Cutshort (Tech Recruitment)
    "notifications@cutshort.io",
    "alerts@cutshort.io",
    # Foundit / Monster (Job Vacancies)
    "alerts@foundit.in",
    "info@foundit.in",
    # Glassdoor
    "noreply@glassdoor.com",
    "alerts@glassdoor.com",
    # Hirist (IT & Software Careers)
    "alerts@hirist.com",
    "jobs@hirist.tech",
}

ALLOWED_SENDER_DOMAINS = {
    "linkedin.com",
    "naukri.com",
    "indeed.com",
    "indeed.co.in",
    "internshala.com",
    "unstop.com",
    "dare2compete.com",
    "instahyre.com",
    "wellfound.com",
    "angel.co",
    "cutshort.io",
    "foundit.in",
    "monsterindia.com",
    "glassdoor.com",
    "glassdoor.co.in",
    "hirist.com",
    "hirist.tech",
}


def sanitize_url(raw_url: str) -> Optional[str]:
    """Sanitize and validate extracted URL. Reject non-HTTP protocols."""
    if not raw_url:
        return None
    url = raw_url.strip()
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return None
        if not parsed.netloc:
            return None
        return url
    except Exception:
        return None


def extract_email_address(raw_sender: str) -> str:
    """Extract clean email address from sender header, e.g. 'Name <user@domain.com>' -> 'user@domain.com'."""
    if not raw_sender:
        return ""
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_sender)
    if match:
        return match.group(0).lower()
    return raw_sender.strip().lower()


def is_sender_allowed(
    sender: str,
    allowed_senders: Optional[Set[str]] = None,
    allowed_domains: Optional[Set[str]] = None,
) -> bool:
    """Validate sender against allowed exact addresses or permitted sender domains."""
    clean = extract_email_address(sender)
    if not clean or "@" not in clean:
        return False

    senders = allowed_senders if allowed_senders is not None else DEFAULT_ALLOWED_SENDERS
    if clean in senders:
        return True

    # If caller provided custom non-default allowed_senders without domains, honor strict whitelist
    if allowed_senders is not None and allowed_senders != DEFAULT_ALLOWED_SENDERS and allowed_domains is None:
        return False

    domain = clean.split("@", 1)[1].lower()
    domains = allowed_domains if allowed_domains is not None else ALLOWED_SENDER_DOMAINS
    for allowed in domains:
        if domain == allowed or domain.endswith("." + allowed):
            return True

    return False


def get_platform_from_sender(clean_sender: str) -> str:
    """Identify the job platform name from sender email domain."""
    domain = clean_sender.split("@")[-1].lower() if "@" in clean_sender else clean_sender.lower()
    if "linkedin" in domain:
        return "linkedin"
    elif "naukri" in domain:
        return "naukri"
    elif "indeed" in domain:
        return "indeed"
    elif "internshala" in domain:
        return "internshala"
    elif "unstop" in domain or "dare2compete" in domain:
        return "unstop"
    elif "instahyre" in domain:
        return "instahyre"
    elif "wellfound" in domain or "angel" in domain:
        return "wellfound"
    elif "cutshort" in domain:
        return "cutshort"
    elif "foundit" in domain or "monster" in domain:
        return "foundit"
    elif "glassdoor" in domain:
        return "glassdoor"
    elif "hirist" in domain:
        return "hirist"
    return "email"


class _SimpleHTMLJobExtractor(HTMLParser):
    """Safely extracts text and hyperlinks from untrusted HTML content."""

    def __init__(self):
        super().__init__()
        self.links: List[Tuple[str, str]] = []  # (text, href)
        self.current_tag: Optional[str] = None
        self.current_href: Optional[str] = None
        self.current_text: List[str] = []
        self.current_fallback_text: str = ""
        self.all_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        self.current_tag = tag.lower()
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href")
            valid_url = sanitize_url(href or "")
            if valid_url:
                self.current_href = valid_url
                self.current_text = []
                self.current_fallback_text = attrs_dict.get("title") or attrs_dict.get("aria-label") or ""

    def handle_data(self, data: str):
        cleaned = data.strip()
        if cleaned:
            self.all_text.append(cleaned)
            if self.current_href is not None:
                self.current_text.append(cleaned)

    def handle_endtag(self, tag: str):
        if tag.lower() == "a" and self.current_href:
            link_text = " ".join(self.current_text).strip()
            if not link_text and self.current_fallback_text:
                link_text = self.current_fallback_text.strip()
            self.links.append((link_text, self.current_href))
            self.current_href = None
            self.current_text = []
            self.current_fallback_text = ""


def parse_linkedin_jobs(html_content: str, message_id: str) -> List[RawJob]:
    """Parse job links and titles from a LinkedIn alerts email."""
    extractor = _SimpleHTMLJobExtractor()
    extractor.feed(html_content)

    jobs: List[RawJob] = []
    seen_urls = set()

    for text_content, href in extractor.links:
        # Match linkedin job view links
        if "/jobs/view/" in href and href not in seen_urls:
            seen_urls.add(href)
            # Match job id in URL
            match_id = re.search(r"/jobs/view/(\d+)", href)
            job_id = match_id.group(1) if match_id else f"li_{abs(hash(href))}"

            # Clean job title
            title = text_content if text_content and len(text_content) > 3 else "LinkedIn Matched Role"
            title = re.sub(r"\s+", " ", title).strip()

            jobs.append(
                RawJob(
                    source="email_alerts",
                    source_id="linkedin_alerts",
                    external_id=job_id,
                    title=title,
                    company="LinkedIn Alert Lead",
                    location="India / Remote (Alert)",
                    url=href,
                    description_text=f"Imported from LinkedIn alert email (Message-ID: {message_id})",
                    raw_data={"message_id": message_id, "original_text": text_content},
                )
            )

    return jobs


def parse_naukri_jobs(html_content: str, message_id: str) -> List[RawJob]:
    """Parse job links and titles from a Naukri alerts email."""
    extractor = _SimpleHTMLJobExtractor()
    extractor.feed(html_content)

    jobs: List[RawJob] = []
    seen_urls = set()

    for text_content, href in extractor.links:
        # Match naukri job listing links
        if "naukri.com/job-listings-" in href and href not in seen_urls:
            seen_urls.add(href)
            match_id = re.search(r"-(\d{8,})", href)
            job_id = match_id.group(1) if match_id else f"nk_{abs(hash(href))}"

            title = text_content if text_content and len(text_content) > 3 else "Naukri Matched Role"
            title = re.sub(r"\s+", " ", title).strip()

            jobs.append(
                RawJob(
                    source="email_alerts",
                    source_id="naukri_alerts",
                    external_id=job_id,
                    title=title,
                    company="Naukri Alert Lead",
                    location="India (Alert)",
                    url=href,
                    description_text=f"Imported from Naukri alert email (Message-ID: {message_id})",
                    raw_data={"message_id": message_id, "original_text": text_content},
                )
            )

    return jobs


def parse_indeed_jobs(html_content: str, message_id: str) -> List[RawJob]:
    """Parse job links and titles from an Indeed alerts email."""
    extractor = _SimpleHTMLJobExtractor()
    extractor.feed(html_content)

    jobs: List[RawJob] = []
    seen_urls = set()

    for text_content, href in extractor.links:
        # Match Indeed job view links: /viewjob, /rc/clk, /job/
        if ("indeed.com" in href or "indeed.co.in" in href) and ("/viewjob" in href or "/rc/clk" in href or "/job/" in href):
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Match job id in URL (jk parameter or trailing id)
            match_jk = re.search(r"[?&]jk=([a-zA-Z0-9]+)", href)
            job_id = match_jk.group(1) if match_jk else f"ind_{abs(hash(href))}"

            title = text_content if text_content and len(text_content) > 3 else "Indeed Matched Role"
            title = re.sub(r"\s+", " ", title).strip()

            jobs.append(
                RawJob(
                    source="email_alerts",
                    source_id="indeed_alerts",
                    external_id=job_id,
                    title=title,
                    company="Indeed Alert Lead",
                    location="India (Alert)",
                    url=href,
                    description_text=f"Imported from Indeed alert email (Message-ID: {message_id})",
                    raw_data={"message_id": message_id, "original_text": text_content},
                )
            )

    return jobs


def parse_internshala_jobs(html_content: str, message_id: str) -> List[RawJob]:
    """Parse internship and fresher job links from an Internshala alert email."""
    extractor = _SimpleHTMLJobExtractor()
    extractor.feed(html_content)

    jobs: List[RawJob] = []
    seen_urls = set()

    for text_content, href in extractor.links:
        if "internshala.com" in href and ("/internship/detail/" in href or "/job/detail/" in href):
            if href in seen_urls:
                continue
            seen_urls.add(href)

            match_slug = re.search(r"/(?:internship|job)/detail/([a-zA-Z0-9\-]+)", href)
            job_id = match_slug.group(1) if match_slug else f"is_{abs(hash(href))}"

            title = text_content if text_content and len(text_content) > 3 else "Internshala Role"
            title = re.sub(r"\s+", " ", title).strip()

            is_intern = "/internship/" in href

            jobs.append(
                RawJob(
                    source="email_alerts",
                    source_id="internshala_alerts",
                    external_id=str(job_id),
                    title=title,
                    company="Internshala Alert Lead",
                    location="India / Remote (Alert)",
                    url=href,
                    description_text=f"Imported from Internshala alert email (Message-ID: {message_id})",
                    raw_data={"message_id": message_id, "original_text": text_content, "is_intern": is_intern},
                )
            )

    if not jobs:
        jobs = parse_generic_job_alerts(html_content, message_id, "internshala")

    return jobs


def parse_generic_job_alerts(html_content: str, message_id: str, platform_name: str) -> List[RawJob]:
    """Universal parser for job alert emails from any authorized platform (Unstop, Instahyre, Wellfound, Cutshort, Glassdoor, etc.)."""
    extractor = _SimpleHTMLJobExtractor()
    extractor.feed(html_content)

    jobs: List[RawJob] = []
    seen_urls = set()

    JOB_KEYWORDS = (
        "/job/", "/jobs/", "/job-", "/job_", "/viewjob", "/job-listing",
        "/internship/", "/internships/", "/opportunity/", "/opportunities/",
        "/careers/", "/rc/clk", "/j/", "/listing/",
    )
    SKIP_TEXTS = {
        "apply", "apply now", "view job", "view jobs", "click here", "read more",
        "see more", "unsubscribe", "privacy policy", "terms of use", "preferences",
        "manage preferences", "learn more", "visit", "help center", "view all",
    }

    for text_content, href in extractor.links:
        if href in seen_urls:
            continue

        href_lower = href.lower()
        if any(keyword in href_lower for keyword in JOB_KEYWORDS):
            seen_urls.add(href)
            title = text_content.strip() if text_content else ""
            if not title or title.lower() in SKIP_TEXTS or len(title) < 4:
                title = f"{platform_name.capitalize()} Matched Role"
            title = re.sub(r"\s+", " ", title).strip()

            match_id = re.search(r"[?&](?:jk|id|job_id|jl)=([a-zA-Z0-9]+)", href) or re.search(r"[-/](\d{5,})", href)
            job_id = match_id.group(1) if match_id else f"{platform_name[:3]}_{abs(hash(href))}"

            is_intern = "intern" in href_lower or "intern" in title.lower()

            jobs.append(
                RawJob(
                    source="email_alerts",
                    source_id=f"{platform_name}_alerts",
                    external_id=str(job_id),
                    title=title,
                    company=f"{platform_name.capitalize()} Alert Lead",
                    location="India / Remote (Alert)",
                    url=href,
                    description_text=f"Imported from {platform_name.capitalize()} alert email (Message-ID: {message_id})",
                    raw_data={
                        "message_id": message_id,
                        "original_text": text_content,
                        "platform": platform_name,
                        "is_intern": is_intern,
                    },
                )
            )

    return jobs


def parse_alert_message(
    sender: str,
    body: str,
    message_id: str,
    allowed_senders: Optional[Set[str]] = None,
    allowed_domains: Optional[Set[str]] = None,
) -> List[RawJob]:
    """
    Parse an email message from untrusted input.
    Validates sender against allowed senders / domains; unauthorized senders are immediately ignored.
    """
    if not is_sender_allowed(sender, allowed_senders=allowed_senders, allowed_domains=allowed_domains):
        clean_sender = extract_email_address(sender)
        logger.debug(f"Ignoring email from unauthorized sender: {clean_sender}")
        return []

    clean_sender = extract_email_address(sender)
    platform = get_platform_from_sender(clean_sender)

    if platform == "linkedin":
        jobs = parse_linkedin_jobs(body, message_id)
    elif platform == "naukri":
        jobs = parse_naukri_jobs(body, message_id)
    elif platform == "indeed":
        jobs = parse_indeed_jobs(body, message_id)
    elif platform == "internshala":
        jobs = parse_internshala_jobs(body, message_id)
    else:
        jobs = parse_generic_job_alerts(body, message_id, platform)

    # If platform-specific parser yielded no jobs (e.g. customized newsletter format), fallback to universal parser
    if not jobs:
        jobs = parse_generic_job_alerts(body, message_id, platform)

    return jobs


def parse_eml_bytes(
    eml_bytes: bytes,
    allowed_senders: Optional[Set[str]] = None,
    allowed_domains: Optional[Set[str]] = None,
) -> Tuple[str, List[RawJob]]:
    """Parse raw RFC-822 email bytes and return (message_id, jobs)."""
    msg: Message = email.message_from_bytes(eml_bytes)

    sender = msg.get("From", "")
    message_id = msg.get("Message-ID", f"msg_{abs(hash(eml_bytes))}")

    body_content = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    body_content = payload.decode(errors="ignore")
                    break
            elif content_type == "text/plain" and not body_content:
                payload = part.get_payload(decode=True)
                if payload:
                    body_content = payload.decode(errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_content = payload.decode(errors="ignore")

    jobs = parse_alert_message(sender, body_content, message_id, allowed_senders, allowed_domains)
    return message_id, jobs


class EmailAlertSource:
    """Reads alert emails over IMAP (read-only mode), extracts job leads, and logs Message-IDs."""

    def __init__(
        self,
        imap_host: Optional[str] = None,
        imap_port: int = 993,
        imap_user: Optional[str] = None,
        imap_password: Optional[str] = None,
        allowed_senders: Optional[Set[str]] = None,
        allowed_domains: Optional[Set[str]] = None,
        session: Optional[Session] = None,
    ):
        self.imap_host = imap_host or os.getenv("IMAP_HOST")
        raw_port = os.getenv("IMAP_PORT")
        if raw_port and raw_port.strip():
            self.imap_port = int(raw_port.strip())
        else:
            self.imap_port = imap_port
        self.imap_user = imap_user or os.getenv("IMAP_USER")
        self.imap_password = imap_password or os.getenv("IMAP_PASSWORD")
        self.allowed_senders = allowed_senders or DEFAULT_ALLOWED_SENDERS
        self.allowed_domains = allowed_domains or ALLOWED_SENDER_DOMAINS
        self.session = session

    @property
    def name(self) -> str:
        return "email_alerts"

    async def fetch(self) -> List[RawJob]:
        """Fetch alert emails over IMAP asynchronously in read-only mode off the main event loop."""
        if not self.imap_host or not self.imap_user or not self.imap_password:
            logger.info("IMAP credentials not configured. Skipping EmailAlertSource.")
            return []

        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> List[RawJob]:
        """Synchronous IMAP fetch executed in a worker thread with socket timeout and header-first filtering."""
        all_jobs: List[RawJob] = []
        mail: Optional[imaplib.IMAP4_SSL] = None

        try:
            # Connect over SSL with a strict 15s timeout to prevent hanging
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port, timeout=15.0)
            if hasattr(mail, "sock") and mail.sock:
                mail.sock.settimeout(15.0)

            mail.login(self.imap_user, self.imap_password)
            # Open INBOX in READONLY mode to never delete or alter flags on mailbox
            mail.select("INBOX", readonly=True)

            # Search recent messages (past 3 days) to avoid scanning thousands of old emails
            since_date = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%d-%b-%Y")
            status, response = mail.search(None, f'(SINCE "{since_date}")')
            if status != "OK" or not response or not response[0]:
                # Fallback to UNSEEN if SINCE returns nothing
                status, response = mail.search(None, "UNSEEN")

            if status != "OK" or not response or not response[0]:
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass
                return []

            msg_ids = response[0].split()
            # Process at most the latest 20 messages
            target_ids = msg_ids[-20:]

            for msg_id in target_ids:
                # 1. Fetch only headers first (fast, ~1KB) to check sender & message-id
                # Avoid downloading megabytes of bodies for non-job emails
                res, hdr_data = mail.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM MESSAGE-ID SUBJECT DATE)])")
                if res != "OK" or not hdr_data or not hdr_data[0]:
                    continue

                raw_headers = hdr_data[0][1] if isinstance(hdr_data[0], tuple) else b""
                hdr_msg = email.message_from_bytes(raw_headers)
                sender = hdr_msg.get("From", "")
                mid = hdr_msg.get("Message-ID", "")

                clean_sender = extract_email_address(sender)
                # Quick filter: is the sender from an allowed job alert domain?
                if not is_sender_allowed(clean_sender, self.allowed_senders, self.allowed_domains):
                    continue

                # Quick filter: has this message ID already been processed and recorded in DB?
                if mid and self._is_message_already_processed(mid):
                    continue

                # 2. Only download the full body for confirmed new job alert emails
                res, body_data = mail.fetch(msg_id, "(BODY.PEEK[])")
                if res != "OK" or not body_data or not body_data[0]:
                    continue

                raw_email = body_data[0][1] if isinstance(body_data[0], tuple) else b""
                parsed_mid, jobs = parse_eml_bytes(raw_email, self.allowed_senders, self.allowed_domains)
                final_mid = mid or parsed_mid

                if not jobs:
                    continue

                if self._is_message_already_processed(final_mid):
                    continue

                all_jobs.extend(jobs)
                self._record_processed_message(final_mid, clean_sender, len(jobs))

            try:
                mail.close()
            except Exception:
                pass
            try:
                mail.logout()
            except Exception:
                pass
        except Exception as exc:
            logger.warning(f"Error reading alert emails over IMAP: {exc}")
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass

        logger.info(f"EmailAlertSource extracted {len(all_jobs)} jobs from alert mailbox.")
        return all_jobs

    def _is_message_already_processed(self, message_id: str) -> bool:
        """Check if message_id exists in email_messages table."""
        if not self.session:
            return False
        try:
            row = self.session.execute(
                text("SELECT 1 FROM email_messages WHERE message_id = :mid"),
                {"mid": message_id},
            ).first()
            return row is not None
        except Exception:
            return False

    def _record_processed_message(self, message_id: str, sender: str, jobs_extracted: int) -> None:
        """Record processed Message-ID in database."""
        if not self.session:
            return
        try:
            self.session.execute(
                text(
                    """
                    INSERT INTO email_messages (message_id, sender, jobs_extracted)
                    VALUES (:mid, :sender, :count)
                    ON CONFLICT (message_id) DO NOTHING
                    """
                ),
                {"mid": message_id, "sender": sender, "count": jobs_extracted},
            )
            self.session.commit()
        except Exception as exc:
            logger.debug(f"Could not record email Message-ID {message_id}: {exc}")
            try:
                self.session.rollback()
            except Exception:
                pass
