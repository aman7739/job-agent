"""Urgency and expiring deadline detection for high-priority job alerts."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UrgencyInfo(BaseModel):
    """Urgency evaluation for a job posting."""

    is_urgent: bool = False
    hours_remaining: Optional[float] = None
    urgency_reason: Optional[str] = None


# Regex patterns indicating hours left (e.g., "closes in 2 hours", "apply within 4 hrs")
RE_HOURS_LEFT = re.compile(
    r"\b(?:closes?|closing|expires?|deadline|apply\s+within|last)\s*(?:in|by|within)?\s*([1-4])\s*(?:hours?|hrs?)\b",
    re.IGNORECASE,
)

# Regex patterns indicating same-day / immediate urgency
RE_URGENT_GENERAL = re.compile(
    r"\b(?:closing\s+today|closes\s+today|last\s+day\s+to\s+apply|urgent\s+hiring|expiring\s+in\s+a\s+few\s+hours|closing\s+soon)\b",
    re.IGNORECASE,
)


def detect_job_urgency(
    job_title: str,
    job_description: str,
    raw_data: Optional[Dict[str, Any]] = None,
    deadline_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> UrgencyInfo:
    """
    Detect if a job has <= 4 hours remaining or urgent impending deadline.
    Checks:
    1. Explicit deadline timestamp compared to `now`.
    2. Text indicators (e.g. 'closes in 2 hours', 'apply within 4 hrs').
    3. Urgent hiring keywords in title or description.
    """
    current_time = now or datetime.now(timezone.utc)
    text_corpus = f"{job_title} {job_description}"

    # 1. Check explicit deadline datetime
    if deadline_at:
        diff_seconds = (deadline_at - current_time).total_seconds()
        diff_hours = diff_seconds / 3600.0
        if 0 < diff_hours <= 4.0:
            return UrgencyInfo(
                is_urgent=True,
                hours_remaining=round(diff_hours, 1),
                urgency_reason=f"Deadline closing in {round(diff_hours, 1)} hours",
            )

    # Check raw_data for explicit deadline metadata
    if raw_data:
        deadline_raw = raw_data.get("deadline") or raw_data.get("expires_at")
        if isinstance(deadline_raw, str):
            try:
                parsed_dt = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
                diff_seconds = (parsed_dt - current_time).total_seconds()
                diff_hours = diff_seconds / 3600.0
                if 0 < diff_hours <= 4.0:
                    return UrgencyInfo(
                        is_urgent=True,
                        hours_remaining=round(diff_hours, 1),
                        urgency_reason=f"Application deadline in {round(diff_hours, 1)} hours",
                    )
            except Exception:
                pass

    # 2. Check for explicit hours regex (e.g. "closes in 3 hours")
    match_hours = RE_HOURS_LEFT.search(text_corpus)
    if match_hours:
        hours = float(match_hours.group(1))
        return UrgencyInfo(
            is_urgent=True,
            hours_remaining=hours,
            urgency_reason=f"Posting states closing in {int(hours)} hours",
        )

    # 3. Check for general urgent closing signals
    match_general = RE_URGENT_GENERAL.search(text_corpus)
    if match_general:
        return UrgencyInfo(
            is_urgent=True,
            hours_remaining=4.0,
            urgency_reason=f"High urgency signal: '{match_general.group(0)}'",
        )

    return UrgencyInfo(is_urgent=False)
