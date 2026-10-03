"""Job application status tracking: saved, applied, not_interested, and seen."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

VALID_STATUSES = {"seen", "saved", "applied", "not_interested"}


def set_job_status(
    session: Session,
    fingerprint: str,
    status: str,
    notes: Optional[str] = None,
    now: Optional[datetime] = None,
) -> bool:
    """
    Update application status and set corresponding timestamp:
      - 'saved'          -> saved_at = now
      - 'applied'        -> applied_at = now
      - 'not_interested' -> not_interested_at = now
      - 'seen'           -> status = 'seen'
    Optionally stores user notes.
    Returns True if a row was updated, False if fingerprint not found in seen_jobs.
    """
    status_clean = status.strip().lower()
    if status_clean not in VALID_STATUSES:
        raise ValueError(
            f"Invalid job status '{status}'. Must be one of: {sorted(VALID_STATUSES)}"
        )

    current_ts = now or datetime.now(timezone.utc)

    # Check if fingerprint exists in seen_jobs
    row = session.execute(
        text("SELECT status FROM seen_jobs WHERE fingerprint = :fp"),
        {"fp": fingerprint},
    ).fetchone()

    if not row:
        logger.warning(f"Cannot update status: fingerprint '{fingerprint}' not found in seen_jobs.")
        return False

    # Build SQL update with timestamp logic
    params: Dict[str, Any] = {
        "status": status_clean,
        "fp": fingerprint,
        "now": current_ts,
    }

    timestamp_clause = ""
    if status_clean == "saved":
        timestamp_clause = ", saved_at = :now"
    elif status_clean == "applied":
        timestamp_clause = ", applied_at = :now"
    elif status_clean == "not_interested":
        timestamp_clause = ", not_interested_at = :now"

    notes_clause = ""
    if notes is not None:
        notes_clause = ", notes = :notes"
        params["notes"] = notes

    update_sql = f"""
        UPDATE seen_jobs
        SET status = :status
            {timestamp_clause}
            {notes_clause}
        WHERE fingerprint = :fp
    """

    session.execute(text(update_sql), params)
    session.commit()
    logger.info(f"Updated job '{fingerprint[:10]}...' status to '{status_clean}'.")
    return True


def get_job_status(session: Session, fingerprint: str) -> Optional[Dict[str, Any]]:
    """Retrieve tracking status, timestamps, and notes for a job by fingerprint."""
    row = session.execute(
        text(
            """
            SELECT fingerprint, canonical_url, first_seen_at, last_seen_at, notified_at,
                   status, saved_at, applied_at, not_interested_at, notes
            FROM seen_jobs
            WHERE fingerprint = :fp
            """
        ),
        {"fp": fingerprint},
    ).fetchone()

    if not row:
        return None

    return {
        "fingerprint": row[0],
        "canonical_url": row[1],
        "first_seen_at": row[2],
        "last_seen_at": row[3],
        "notified_at": row[4],
        "status": row[5],
        "saved_at": row[6],
        "applied_at": row[7],
        "not_interested_at": row[8],
        "notes": row[9],
    }


def get_jobs_by_status(
    session: Session,
    status: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Return jobs with a specific status joined with job details."""
    status_clean = status.strip().lower()
    if status_clean not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}"
        )

    rows = session.execute(
        text(
            """
            SELECT j.fingerprint, j.title, j.company, j.location, j.canonical_url,
                   j.salary_lpa, j.stipend, j.is_intern, j.is_apprentice, j.score,
                   s.status, s.saved_at, s.applied_at, s.not_interested_at, s.notes
            FROM seen_jobs s
            JOIN jobs j ON s.fingerprint = j.fingerprint
            WHERE s.status = :status
            ORDER BY s.last_seen_at DESC
            LIMIT :limit
            """
        ),
        {"status": status_clean, "limit": limit},
    ).fetchall()

    return [
        {
            "fingerprint": r[0],
            "title": r[1],
            "company": r[2],
            "location": r[3],
            "canonical_url": r[4],
            "salary_lpa": float(r[5]) if r[5] is not None else None,
            "stipend": float(r[6]) if r[6] is not None else None,
            "is_intern": bool(r[7]),
            "is_apprentice": bool(r[8]),
            "score": float(r[9]) if r[9] is not None else None,
            "status": r[10],
            "saved_at": r[11],
            "applied_at": r[12],
            "not_interested_at": r[13],
            "notes": r[14],
        }
        for r in rows
    ]


def get_status_summary(session: Session) -> Dict[str, int]:
    """Get count of jobs categorized by status in seen_jobs."""
    rows = session.execute(
        text("SELECT status, COUNT(*) FROM seen_jobs GROUP BY status")
    ).fetchall()

    counts: Dict[str, int] = {s: 0 for s in VALID_STATUSES}
    total = 0
    for r in rows:
        st = r[0]
        cnt = r[1]
        if st in counts:
            counts[st] = cnt
        total += cnt

    counts["total"] = total
    return counts
