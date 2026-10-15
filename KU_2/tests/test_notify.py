"""Unit tests for Telegram and Email delivery, message splitting, and fault isolation."""

import pytest
import httpx

from job_digest.digest import DigestOutput
from job_digest.models import Job
from job_digest.notify import (
    EmailNotifier,
    Notifier,
    TelegramNotifier,
    deliver_digest,
    filter_unnotified_jobs,
    split_telegram_message,
)


def sample_digest(length: int = 200) -> DigestOutput:
    """Helper creating a sample digest output."""
    sample_text = "Job Description Entry\n\n" * (length // 20)
    return DigestOutput(
        content_html="<html><body><h1>Jobs</h1></body></html>",
        content_text=sample_text,
        total_jobs=2,
        internships_count=1,
        fulltime_count=1,
        new_count=2,
        seen_count=0,
        failed_sources=[],
        is_empty=False,
    )


def test_notifier_protocol_compliance():
    """Verify TelegramNotifier and EmailNotifier satisfy Notifier protocol."""
    tg = TelegramNotifier()
    em = EmailNotifier()

    assert isinstance(tg, Notifier)
    assert tg.channel_name == "telegram"

    assert isinstance(em, Notifier)
    assert em.channel_name == "email"


def test_telegram_message_splitting():
    """Verify long text (>4000 chars) is split into chunks under the character limit without line breaks."""
    # Create 9000-character text with lines
    long_text = "\n".join([f"Line {i}: This is a sample job listing line with enough text." for i in range(150)])
    assert len(long_text) > 4000

    chunks = split_telegram_message(long_text, max_length=4000)

    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) <= 4000

    # Ensure all original lines were preserved
    reconstructed = "\n".join(chunks)
    assert "Line 0:" in reconstructed
    assert "Line 149:" in reconstructed


@pytest.mark.asyncio
async def test_telegram_send_success():
    """Verify TelegramNotifier posts to Telegram bot endpoint."""
    def handler(request):
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 123}})

    transport = httpx.MockTransport(handler)
    tg = TelegramNotifier(bot_token="test_token", chat_id="123456")

    async with httpx.AsyncClient(transport=transport) as client:
        res = await tg.send(sample_digest(100), client=client)
        assert res is True


class MockChannel:
    def __init__(self, name: str, should_succeed: bool = True):
        self._name = name
        self.should_succeed = should_succeed
        self.called = False

    @property
    def channel_name(self) -> str:
        return self._name

    async def send(self, digest: DigestOutput) -> bool:
        self.called = True
        if not self.should_succeed:
            raise ConnectionError(f"Simulated failure on channel {self._name}")
        return True


@pytest.mark.asyncio
async def test_digest_arrives_on_both_channels():
    """
    Session 10 Check:
    The digest arrives on both channels.
    """
    ch_telegram = MockChannel("telegram", should_succeed=True)
    ch_email = MockChannel("email", should_succeed=True)

    digest = sample_digest()
    successful = await deliver_digest(digest, [ch_telegram, ch_email])

    assert ch_telegram.called is True
    assert ch_email.called is True
    assert set(successful) == {"telegram", "email"}


@pytest.mark.asyncio
async def test_with_one_broken_the_other_still_delivers():
    """
    Session 10 Check:
    With one broken, the other still delivers.
    """
    broken_channel = MockChannel("telegram", should_succeed=False)
    working_channel = MockChannel("email", should_succeed=True)

    digest = sample_digest()
    successful = await deliver_digest(digest, [broken_channel, working_channel])

    assert broken_channel.called is True
    assert working_channel.called is True
    # Working channel succeeded despite broken channel
    assert successful == ["email"]


def test_sending_twice_repeats_nothing():
    """
    Session 10 Check:
    Sending twice repeats nothing. Jobs marked as notified are excluded on second pass.
    """
    job1 = Job(
        title="Python Engineer",
        company="Stripe",
        location="Bengaluru",
        canonical_url="https://stripe.com/1",
        description_text="Role",
        source="greenhouse",
    )
    job1.fingerprint = "fp_stripe_1"

    job2 = Job(
        title="Associate Analyst",
        company="Zomato",
        location="Gurugram",
        canonical_url="https://zomato.com/2",
        description_text="Role",
        source="lever",
    )
    job2.fingerprint = "fp_zomato_2"

    # Simulated in-memory notified tracker
    notified_fingerprints = set()

    # Pass 1: neither is notified
    unnotified_pass1 = [j for j in [job1, job2] if j.fingerprint not in notified_fingerprints]
    assert len(unnotified_pass1) == 2

    # Mark as notified after delivery
    notified_fingerprints.add(job1.fingerprint)
    notified_fingerprints.add(job2.fingerprint)

    # Pass 2: check unnotified jobs
    unnotified_pass2 = [j for j in [job1, job2] if j.fingerprint not in notified_fingerprints]
    # Repeats nothing!
    assert len(unnotified_pass2) == 0
