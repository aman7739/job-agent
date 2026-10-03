"""Digest builder: groups jobs, applies Jinja2 templates, renders HTML/text, and persists to DB."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from job_digest.match import ScoredJob
from job_digest.profile import UserProfile

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# Initialize Jinja2 environment
_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


class DigestOutput(BaseModel):
    """Rendered digest content and metadata."""

    model_config = ConfigDict(extra="ignore")

    content_html: str
    content_text: str
    total_jobs: int
    internships_count: int
    fulltime_count: int
    new_count: int
    seen_count: int
    failed_sources: List[str]
    is_empty: bool


def partition_and_cap_jobs(
    scored_jobs: List[ScoredJob],
    max_items: int = 40,
) -> Tuple[List[ScoredJob], List[ScoredJob], List[ScoredJob], List[ScoredJob]]:
    """
    Partition scored jobs into:
      1. Internships/Apprenticeships Strong (>= 7.0)
      2. Internships/Apprenticeships Maybe (4.0 - 6.9)
      3. Full-time Strong (>= 7.0)
      4. Full-time Maybe (4.0 - 6.9)
    Capped at max_items total across all buckets.
    """
    intern_strong: List[ScoredJob] = []
    intern_maybe: List[ScoredJob] = []
    fulltime_strong: List[ScoredJob] = []
    fulltime_maybe: List[ScoredJob] = []

    # Sort candidates highest score first
    sorted_jobs = sorted(scored_jobs, key=lambda s: s.score, reverse=True)

    for item in sorted_jobs:
        if item.is_intern_or_apprentice:
            if item.category == "Strong":
                intern_strong.append(item)
            else:
                intern_maybe.append(item)
        else:
            if item.category == "Strong":
                fulltime_strong.append(item)
            else:
                fulltime_maybe.append(item)

    # Apply global cap prioritizing Strong matches first
    collected: List[ScoredJob] = []
    # Interleave / collect up to max_items
    for bucket in [intern_strong, fulltime_strong, intern_maybe, fulltime_maybe]:
        for job in bucket:
            if len(collected) < max_items:
                collected.append(job)

    # Re-slice buckets to capped set
    collected_set = set(id(j) for j in collected)
    intern_strong = [j for j in intern_strong if id(j) in collected_set]
    intern_maybe = [j for j in intern_maybe if id(j) in collected_set]
    fulltime_strong = [j for j in fulltime_strong if id(j) in collected_set]
    fulltime_maybe = [j for j in fulltime_maybe if id(j) in collected_set]

    return intern_strong, intern_maybe, fulltime_strong, fulltime_maybe


def build_digest(
    scored_jobs: List[ScoredJob],
    new_count: int,
    seen_count: int,
    failed_sources: Optional[List[str]] = None,
    profile: Optional[UserProfile] = None,
    now: Optional[datetime] = None,
) -> DigestOutput:
    """
    Build HTML and plain-text digests from scored jobs.
    Handles zero jobs gracefully with a short 'nothing new today' digest.
    """
    current_time = now or datetime.now(timezone.utc)
    date_str = current_time.strftime("%A, %d %B %Y")
    max_items = profile.digest.max_items if profile else 40
    failed = failed_sources or []

    intern_strong, intern_maybe, fulltime_strong, fulltime_maybe = partition_and_cap_jobs(
        scored_jobs, max_items=max_items
    )

    total_selected = len(intern_strong) + len(intern_maybe) + len(fulltime_strong) + len(fulltime_maybe)
    internships_count = len(intern_strong) + len(intern_maybe)
    fulltime_count = len(fulltime_strong) + len(fulltime_maybe)
    is_empty = total_selected == 0

    has_remotive = any(
        s.job.source == "remotive"
        for s in (intern_strong + intern_maybe + fulltime_strong + fulltime_maybe)
    )

    template_context = {
        "date_str": date_str,
        "new_count": new_count,
        "seen_count": seen_count,
        "total_selected": total_selected,
        "failed_sources": failed,
        "is_empty": is_empty,
        "intern_strong": intern_strong,
        "intern_maybe": intern_maybe,
        "fulltime_strong": fulltime_strong,
        "fulltime_maybe": fulltime_maybe,
        "has_remotive": has_remotive,
    }

    html_template = _jinja_env.get_template("digest.html")
    txt_template = _jinja_env.get_template("digest.txt")

    content_html = html_template.render(template_context)
    content_text = txt_template.render(template_context)

    return DigestOutput(
        content_html=content_html,
        content_text=content_text,
        total_jobs=total_selected,
        internships_count=internships_count,
        fulltime_count=fulltime_count,
        new_count=new_count,
        seen_count=seen_count,
        failed_sources=failed,
        is_empty=is_empty,
    )


def save_digest_to_db(
    session: Optional[Session],
    digest: DigestOutput,
    channels_notified: Optional[List[str]] = None,
) -> Optional[int]:
    """Persist rendered digest into the digests table."""
    if session is None:
        return None

    try:
        stmt = text(
            """
            INSERT INTO digests (
                sent_at, total_jobs, internships_count, fulltime_count,
                channels_notified, failed_sources, content_html, content_text
            ) VALUES (
                NOW(), :total, :intern, :fulltime,
                :channels, :failed, :html, :text
            ) RETURNING id
            """
        )
        res = session.execute(
            stmt,
            {
                "total": digest.total_jobs,
                "intern": digest.internships_count,
                "fulltime": digest.fulltime_count,
                "channels": channels_notified or [],
                "failed": digest.failed_sources,
                "html": digest.content_html,
                "text": digest.content_text,
            },
        )
        session.commit()
        row = res.first()
        return row[0] if row else None
    except Exception as exc:
        logger.warning(f"Could not persist digest in database: {exc}")
        try:
            session.rollback()
        except Exception:
            pass
        return None
