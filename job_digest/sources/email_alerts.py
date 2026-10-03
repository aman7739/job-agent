"""IMAP Email Alerts job source with sender filtering and untrusted content parsing."""

from __future__ import annotations

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
    "jobalerts-noreply@linkedin.com",
    "jobs-noreply@linkedin.com",
    "messages-noreply@linkedin.com",
    "alerts@naukri.com",
    "info@naukri.com",
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


class _SimpleHTMLJobExtractor(HTMLParser):
    """Safely extracts text and hyperlinks from untrusted HTML content."""

    def __init__(self):
        super().__init__()
        self.links: List[Tuple[str, str]] = []  # (text, href)
        self.current_tag: Optional[str] = None
        self.current_href: Optional[str] = None
        self.current_text: List[str] = []
        self.all_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        self.current_tag = tag.lower()
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            valid_url = sanitize_url(href or "")
            if valid_url:
                self.current_href = valid_url
                self.current_text = []

    def handle_data(self, data: str):
        cleaned = data.strip()
        if cleaned:
            self.all_text.append(cleaned)
            if self.current_href is not None:
                self.current_text.append(cleaned)

    def handle_endtag(self, tag: str):
        if tag.lower() == "a" and self.current_href:
            link_text = " ".join(self.current_text).strip()
            self.links.append((link_text, self.current_href))
            self.current_href = None
            self.current_text = []


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


def parse_alert_message(
    sender: str,
    body: str,
    message_id: str,
    allowed_senders: Set[str] = DEFAULT_ALLOWED_SENDERS,
) -> List[RawJob]:
    """
    Parse an email message from untrusted input.
    Validates sender against allowed_senders; unknown senders are immediately ignored.
    """
    clean_sender = extract_email_address(sender)
    if clean_sender not in allowed_senders:
        logger.debug(f"Ignoring email from unauthorized sender: {clean_sender}")
        return []

    if "linkedin" in clean_sender:
        return parse_linkedin_jobs(body, message_id)
    elif "naukri" in clean_sender:
        return parse_naukri_jobs(body, message_id)
    else:
        # Fallback generic parsing for allowed senders
        return parse_linkedin_jobs(body, message_id) + parse_naukri_jobs(body, message_id)


def parse_eml_bytes(
    eml_bytes: bytes,
    allowed_senders: Set[str] = DEFAULT_ALLOWED_SENDERS,
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

    jobs = parse_alert_message(sender, body_content, message_id, allowed_senders)
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
        session: Optional[Session] = None,
    ):
        self.imap_host = imap_host or os.getenv("IMAP_HOST")
        self.imap_port = int(os.getenv("IMAP_PORT", str(imap_port)))
        self.imap_user = imap_user or os.getenv("IMAP_USER")
        self.imap_password = imap_password or os.getenv("IMAP_PASSWORD")
        self.allowed_senders = allowed_senders or DEFAULT_ALLOWED_SENDERS
        self.session = session

    @property
    def name(self) -> str:
        return "email_alerts"

    async def fetch(self) -> List[RawJob]:
        """Fetch alert emails over IMAP in read-only mode."""
        if not self.imap_host or not self.imap_user or not self.imap_password:
            logger.info("IMAP credentials not configured. Skipping EmailAlertSource.")
            return []

        all_jobs: List[RawJob] = []

        try:
            # Connect over SSL
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.imap_user, self.imap_password)
            # Open INBOX in READONLY mode to never delete or alter flags on Mailbox A
            mail.select("INBOX", readonly=True)

            # Search for unread messages or recent messages
            status, response = mail.search(None, "UNSEEN")
            if status != "OK" or not response[0]:
                # If no unseen messages, search recent messages
                status, response = mail.search(None, "ALL")

            msg_ids = response[0].split()
            # Process at most the latest 20 messages per session
            for msg_id in msg_ids[-20:]:
                res, data = mail.fetch(msg_id, "(RFC822)")
                if res != "OK" or not data or not data[0]:
                    continue

                raw_email = data[0][1]
                mid, jobs = parse_eml_bytes(raw_email, self.allowed_senders)

                if not jobs:
                    continue

                if self._is_message_already_processed(mid):
                    continue

                all_jobs.extend(jobs)
                self._record_processed_message(mid, "alerts_sender", len(jobs))

            mail.close()
            mail.logout()
        except Exception as exc:
            logger.warning(f"Error reading alert emails over IMAP: {exc}")

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
