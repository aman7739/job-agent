"""Database backup and disaster recovery utility for Job Digest Agent."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv
from sqlalchemy import text

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from job_digest.db import get_database_url, get_db_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backup_db")


def create_database_backup(output_dir: Optional[Path] = None, session=None) -> Path:
    """
    Export all essential database tables to a structured JSON snapshot.
    Tables: user_profiles, seen_jobs, jobs, digests, source_runs.
    """
    target_dir = output_dir or (PROJECT_ROOT / "backups")
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = target_dir / f"backup_{timestamp_str}.json"

    db_url = get_database_url() if not session else "session_provided"
    if not db_url and not session:
        logger.error("DATABASE_URL is not set. Cannot perform backup.")
        raise ValueError("DATABASE_URL must be configured.")

    backup_data: Dict[str, Any] = {
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_url_type": "postgresql" if "postgres" in str(db_url) else "sqlite",
            "version": "1.0.0",
        },
        "user_profiles": [],
        "seen_jobs": [],
        "jobs": [],
        "digests": [],
        "source_runs": [],
    }

    def _export_with_session(s):
        # 1. user_profiles
        try:
            profiles = s.execute(
                text("SELECT id, version, profile_yaml, profile_data, is_active, created_at FROM user_profiles")
            ).fetchall()
            for p in profiles:
                backup_data["user_profiles"].append({
                    "id": p[0],
                    "version": p[1],
                    "profile_yaml": p[2],
                    "profile_data": p[3],
                    "is_active": p[4],
                    "created_at": str(p[5]),
                })
        except Exception as exc:
            logger.warning(f"Could not export user_profiles: {exc}")

        # 2. seen_jobs
        try:
            seen = s.execute(
                text("SELECT fingerprint, canonical_url, first_seen_at, last_seen_at, notified_at, status, saved_at, applied_at, not_interested_at, notes FROM seen_jobs")
            ).fetchall()
            for row in seen:
                backup_data["seen_jobs"].append({
                    "fingerprint": row[0],
                    "canonical_url": row[1],
                    "first_seen_at": str(row[2]),
                    "last_seen_at": str(row[3]),
                    "notified_at": str(row[4]) if row[4] else None,
                    "status": row[5],
                    "saved_at": str(row[6]) if row[6] else None,
                    "applied_at": str(row[7]) if row[7] else None,
                    "not_interested_at": str(row[8]) if row[8] else None,
                    "notes": row[9],
                })
        except Exception as exc:
            logger.warning(f"Could not export seen_jobs: {exc}")

        # 3. jobs (top 500 recent)
        try:
            jobs = s.execute(
                text("SELECT id, fingerprint, title, company, location, canonical_url, source, score, is_intern, is_apprentice, salary_lpa FROM jobs ORDER BY id DESC LIMIT 500")
            ).fetchall()
            for j in jobs:
                backup_data["jobs"].append({
                    "id": j[0],
                    "fingerprint": j[1],
                    "title": j[2],
                    "company": j[3],
                    "location": j[4],
                    "canonical_url": j[5],
                    "source": j[6],
                    "score": float(j[7]) if j[7] is not None else None,
                    "is_intern": j[8],
                    "is_apprentice": j[9],
                    "salary_lpa": float(j[10]) if j[10] is not None else None,
                })
        except Exception as exc:
            logger.warning(f"Could not export jobs: {exc}")

        # 4. digests (recent 50)
        try:
            digests = s.execute(
                text("SELECT id, sent_at, total_jobs, internships_count, fulltime_count, channels_notified FROM digests ORDER BY id DESC LIMIT 50")
            ).fetchall()
            for d in digests:
                backup_data["digests"].append({
                    "id": d[0],
                    "sent_at": str(d[1]),
                    "total_jobs": d[2],
                    "internships_count": d[3],
                    "fulltime_count": d[4],
                    "channels_notified": d[5],
                })
        except Exception as exc:
            logger.warning(f"Could not export digests: {exc}")

    if session:
        _export_with_session(session)
    else:
        with get_db_session() as s:
            _export_with_session(s)

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2)

    logger.info(f"Database backup saved successfully to {backup_file}")
    logger.info(f"Summary: {len(backup_data['user_profiles'])} profiles, {len(backup_data['seen_jobs'])} tracked jobs, {len(backup_data['digests'])} digests.")
    return backup_file


if __name__ == "__main__":
    create_database_backup()
