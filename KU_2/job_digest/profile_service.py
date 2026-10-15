"""Database-backed profile service with strict validation, version history, and fallback recovery."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from job_digest.profile import UserProfile, parse_profile_yaml

logger = logging.getLogger(__name__)


def save_profile_to_db(session: Session, yaml_content: str) -> Tuple[UserProfile, int]:
    """
    Validate and save a new user profile version into the database.
    - Validates strictly against UserProfile Pydantic schema (extra="forbid").
    - If valid, archives previous version (is_active=False) and creates next version.
    - If invalid, raises ValueError and preserves current active profile untouched.
    Returns: (validated UserProfile, version_number)
    """
    # 1. Strict validation before touching database
    try:
        profile = parse_profile_yaml(yaml_content)
    except Exception as exc:
        logger.error(f"Failed to validate profile YAML: {exc}")
        raise ValueError(f"Invalid profile configuration: {exc}") from exc

    # 2. Determine next version number
    row = session.execute(
        text("SELECT COALESCE(MAX(version), 0) FROM user_profiles")
    ).fetchone()
    current_max = row[0] if row else 0
    next_version = current_max + 1

    current_ts = datetime.now(timezone.utc)
    profile_dict = profile.model_dump(mode="json")
    profile_json_str = json.dumps(profile_dict)

    # 3. Archive prior active profiles
    session.execute(
        text("UPDATE user_profiles SET is_active = FALSE WHERE is_active = TRUE")
    )

    # 4. Insert new active profile version
    session.execute(
        text(
            """
            INSERT INTO user_profiles (
                version, profile_yaml, profile_data, is_active, created_at
            ) VALUES (
                :version, :yaml_content, :profile_data, TRUE, :created_at
            )
            """
        ),
        {
            "version": next_version,
            "yaml_content": yaml_content,
            "profile_data": profile_json_str,
            "created_at": current_ts,
        },
    )
    session.commit()
    logger.info(f"Saved active user profile version {next_version} to database.")
    return profile, next_version


def get_active_profile_from_db(session: Session) -> Tuple[Optional[UserProfile], Optional[str]]:
    """
    Retrieve the active user profile from the database.
    If the active version is corrupted/invalid:
      - Automatically falls back to the latest valid version in history.
      - Returns (profile, warning_message).
    If valid:
      - Returns (profile, None).
    If no profile exists in database:
      - Returns (None, None).
    """
    # Query current active profile
    active_row = session.execute(
        text(
            """
            SELECT version, profile_yaml FROM user_profiles
            WHERE is_active = TRUE
            ORDER BY version DESC LIMIT 1
            """
        )
    ).fetchone()

    if active_row:
        active_version, active_yaml = active_row[0], active_row[1]
        try:
            profile = parse_profile_yaml(active_yaml)
            return profile, None
        except Exception as exc:
            logger.warning(
                f"Active profile version {active_version} is corrupted/invalid ({exc}). Searching history for last good version..."
            )

    # Fallback: scan history in descending order for the last valid version
    history_rows = session.execute(
        text(
            """
            SELECT version, profile_yaml FROM user_profiles
            ORDER BY version DESC
            """
        )
    ).fetchall()

    for row in history_rows:
        v, raw_yaml = row[0], row[1]
        try:
            profile = parse_profile_yaml(raw_yaml)
            warning_msg = (
                f"Active profile was invalid or missing. Fell back to last good version {v} from database history."
            )
            logger.warning(warning_msg)
            return profile, warning_msg
        except Exception:
            continue

    logger.warning("No valid profile found in database user_profiles table.")
    return None, None


def get_profile_history(session: Session) -> List[Dict[str, Any]]:
    """Return historical profile versions stored in the database."""
    rows = session.execute(
        text(
            """
            SELECT id, version, is_active, created_at
            FROM user_profiles
            ORDER BY version DESC
            """
        )
    ).fetchall()

    return [
        {
            "id": r[0],
            "version": r[1],
            "is_active": bool(r[2]),
            "created_at": r[3],
        }
        for r in rows
    ]


def seed_database_profile_if_empty(
    session: Session,
    base_dir: Optional[Path | str] = None,
) -> Optional[UserProfile]:
    """
    If user_profiles table has 0 records, automatically seed it using
    profile.yaml or profile.example.yaml as version 1.
    """
    row = session.execute(text("SELECT COUNT(*) FROM user_profiles")).fetchone()
    count = row[0] if row else 0
    if count > 0:
        active_profile, _ = get_active_profile_from_db(session)
        return active_profile

    root = Path(base_dir) if base_dir else Path.cwd()
    candidate_files = [
        root / "profile.yaml",
        root / "profile.example.yaml",
    ]

    for p in candidate_files:
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8")
                profile, v = save_profile_to_db(session, content)
                logger.info(f"Seeded user_profiles database table from {p.name} as version {v}.")
                return profile
            except Exception as exc:
                logger.warning(f"Could not seed database profile from {p}: {exc}")

    return None
