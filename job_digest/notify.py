"""Delivery coordinators for Telegram and SMTP Email with message splitting and channel isolation."""

from __future__ import annotations

import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
import smtplib
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from job_digest.digest import DigestOutput
from job_digest.models import Job

logger = logging.getLogger(__name__)

TELEGRAM_MAX_LENGTH = 4000  # Safe threshold below 4096


def split_telegram_message(text_content: str, max_length: int = TELEGRAM_MAX_LENGTH) -> List[str]:
    """
    Split text into chunks under Telegram's character limit.
    Splits along line breaks and paragraph boundaries to prevent truncating links.
    """
    if len(text_content) <= max_length:
        return [text_content]

    chunks: List[str] = []
    lines = text_content.split("\n")
    current_chunk: List[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # include newline
        if current_len + line_len > max_length:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = line_len
            else:
                # Line itself exceeds max_length: hard break
                chunks.append(line[:max_length])
                current_chunk = [line[max_length:]]
                current_len = len(line[max_length:]) + 1
        else:
            current_chunk.append(line)
            current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


@runtime_checkable
class Notifier(Protocol):
    """Protocol for a delivery channel."""

    @property
    def channel_name(self) -> str:
        """Channel identifier name."""
        ...

    async def send(self, digest: DigestOutput) -> bool:
        """Send digest. Returns True if delivery succeeded."""
        ...


class TelegramNotifier:
    """Delivers plain-text digest to a private Telegram chat using BotFather bot API."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout_seconds: float = 15.0,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout_seconds = timeout_seconds

    @property
    def channel_name(self) -> str:
        return "telegram"

    async def send_message(self, text_content: str, client: Optional[httpx.AsyncClient] = None) -> bool:
        """Send custom text message split into chunks if necessary."""
        if not self.bot_token or not self.chat_id:
            logger.info("Telegram credentials (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID) not configured. Skipping.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        chunks = split_telegram_message(text_content)

        async def _send_with_client(c: httpx.AsyncClient) -> bool:
            for idx, chunk in enumerate(chunks):
                if idx > 0:
                    await asyncio.sleep(0.3)  # Courteous pacing

                payload = {
                    "chat_id": self.chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                }
                try:
                    response = await c.post(url, json=payload)
                    if response.status_code != 200:
                        logger.error(f"Telegram send error ({response.status_code}): {response.text}")
                        return False
                except Exception as exc:
                    logger.error(f"Telegram network failure: {exc}")
                    return False
            return True

        if client is not None:
            ok = await _send_with_client(client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as c:
                ok = await _send_with_client(c)

        if ok:
            logger.info(f"Telegram delivery succeeded ({len(chunks)} chunks).")
        return ok

    async def send(self, digest: DigestOutput, client: Optional[httpx.AsyncClient] = None) -> bool:
        """Send digest text split into chunks if necessary."""
        return await self.send_message(digest.content_text, client=client)


class EmailNotifier:
    """Delivers multipart HTML and plain-text digest via SMTP to Mailbox B."""

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        to_email: Optional[str] = None,
        timeout_seconds: float = 20.0,
    ):
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        port_env = os.getenv("SMTP_PORT", "587")
        self.smtp_port = smtp_port or int(port_env)
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.to_email = to_email or os.getenv("NOTIFICATION_EMAIL")
        self.timeout_seconds = timeout_seconds

    @property
    def channel_name(self) -> str:
        return "email"

    async def send_message(
        self,
        subject: str,
        text_content: str,
        html_content: Optional[str] = None,
    ) -> bool:
        """Send custom email asynchronously."""
        if not self.smtp_host or not self.smtp_user or not self.smtp_password or not self.to_email:
            logger.info("SMTP email credentials not fully configured. Skipping email delivery.")
            return False

        return await asyncio.to_thread(self._send_sync, subject, text_content, html_content)

    async def send(self, digest: DigestOutput) -> bool:
        """Send digest email asynchronously."""
        subject = f"Daily Job Digest - {digest.new_count} New Roles"
        return await self.send_message(subject, digest.content_text, digest.content_html)

    def _send_sync(self, subject: str, text_content: str, html_content: Optional[str] = None) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_user
            msg["To"] = self.to_email

            part_plain = MIMEText(text_content, "plain", "utf-8")
            msg.attach(part_plain)

            if html_content:
                part_html = MIMEText(html_content, "html", "utf-8")
                msg.attach(part_html)

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout_seconds) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, [self.to_email], msg.as_string())

            logger.info(f"Email delivery succeeded to {self.to_email}.")
            return True
        except Exception as exc:
            logger.error(f"SMTP email delivery failed: {exc}")
            return False


def mark_jobs_as_notified(session: Optional[Session], fingerprints: List[str]) -> None:
    """Mark jobs as notified in seen_jobs table once at least one channel succeeds."""
    if not session or not fingerprints:
        return

    try:
        session.execute(
            text(
                """
                UPDATE seen_jobs
                SET notified_at = NOW()
                WHERE fingerprint = ANY(:fps)
                """
            ),
            {"fps": fingerprints},
        )
        session.commit()
    except Exception as exc:
        logger.warning(f"Could not mark jobs as notified in DB: {exc}")
        try:
            session.rollback()
        except Exception:
            pass


def filter_unnotified_jobs(jobs: List[Job], session: Optional[Session]) -> List[Job]:
    """Filter out jobs that have already been marked notified in seen_jobs."""
    if not session or not jobs:
        return jobs

    fps = [j.fingerprint for j in jobs if j.fingerprint]
    if not fps:
        return jobs

    try:
        rows = session.execute(
            text(
                """
                SELECT fingerprint FROM seen_jobs
                WHERE fingerprint = ANY(:fps) AND notified_at IS NOT NULL
                """
            ),
            {"fps": fps},
        ).fetchall()
        notified_set = {r[0] for r in rows}
        return [j for j in jobs if j.fingerprint not in notified_set]
    except Exception as exc:
        logger.warning(f"Error checking notified status: {exc}")
        return jobs


async def deliver_digest(
    digest: DigestOutput,
    notifiers: List[Notifier],
    fingerprints_to_mark: Optional[List[str]] = None,
    session: Optional[Session] = None,
) -> List[str]:
    """
    Deliver digest to all configured notifiers with fault isolation.
    If one channel fails, the other channels still deliver.
    Jobs are marked notified if at least one channel succeeds.
    Returns list of successful channel names.
    """
    successful_channels: List[str] = []

    for notifier in notifiers:
        try:
            ok = await notifier.send(digest)
            if ok:
                successful_channels.append(notifier.channel_name)
        except Exception as exc:
            logger.error(f"Delivery channel '{notifier.channel_name}' threw exception: {exc}")

    # Mark notified once at least one channel succeeds
    if successful_channels and fingerprints_to_mark:
        mark_jobs_as_notified(session, fingerprints_to_mark)

    return successful_channels


async def deliver_urgent_alert(
    job: Job,
    score: float,
    urgency_reason: str,
    notifiers: List[Notifier],
    session: Optional[Session] = None,
) -> List[str]:
    """
    Deliver an immediate high-priority alert for a job that closes within <= 4 hours.
    Sends immediately to configured notifiers without waiting for the scheduled digest.
    """
    successful_channels: List[str] = []

    plain_text = (
        f"🚨 URGENT JOB ALERT (Closing Soon: ≤ 4 Hours Left!)\n\n"
        f"🏢 Company: {job.company}\n"
        f"💼 Role: {job.title}\n"
        f"📍 Location: {job.location}\n"
        f"🎯 Match Score: {score:.1f}/10\n"
        f"⏳ Urgency: {urgency_reason}\n\n"
        f"👉 Apply immediately: {job.canonical_url}\n"
    )

    html_content = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; padding: 24px; border: 2px solid #ef4444; border-radius: 8px; background: #fffaf0;">
      <h2 style="color: #b91c1c; margin-top: 0; font-size: 20px;">🚨 Urgent Job Alert: Closing Soon (&le; 4 Hours Left)</h2>
      <p style="font-size: 15px; margin: 8px 0;"><strong>Company:</strong> {job.company}</p>
      <p style="font-size: 15px; margin: 8px 0;"><strong>Role:</strong> {job.title}</p>
      <p style="font-size: 15px; margin: 8px 0;"><strong>Location:</strong> {job.location}</p>
      <p style="font-size: 15px; margin: 8px 0;"><strong>Match Score:</strong> <span style="color: #166534; font-weight: bold;">{score:.1f} / 10</span></p>
      <div style="background: #fee2e2; border-left: 4px solid #ef4444; padding: 10px 14px; margin: 16px 0; color: #991b1b; font-weight: 600; font-size: 14px;">
        ⏳ {urgency_reason}
      </div>
      <div style="margin-top: 24px;">
        <a href="{job.canonical_url}" style="display: inline-block; background: #dc2626; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 15px;">
          Apply Immediately &rarr;
        </a>
      </div>
    </div>
    """

    for notifier in notifiers:
        try:
            if hasattr(notifier, "send_message"):
                if notifier.channel_name == "telegram":
                    ok = await notifier.send_message(plain_text)
                elif notifier.channel_name == "email":
                    subject = f"🚨 URGENT: {job.title} at {job.company} Closing Soon!"
                    ok = await notifier.send_message(subject, plain_text, html_content)
                else:
                    ok = False
                if ok:
                    successful_channels.append(notifier.channel_name)
        except Exception as exc:
            logger.error(f"Urgent alert delivery to channel '{notifier.channel_name}' failed: {exc}")

    if successful_channels and job.fingerprint:
        mark_jobs_as_notified(session, [job.fingerprint])

    return successful_channels

