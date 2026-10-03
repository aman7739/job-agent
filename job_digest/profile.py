"""User profile schema, strict validation, and loading utilities."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, List, Optional
import yaml
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

logger = logging.getLogger(__name__)


class StrictBaseModel(BaseModel):
    """Base model that forbids unknown fields to catch typos immediately."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class UserInfo(StrictBaseModel):
    name: str
    email: EmailStr


class EducationInfo(StrictBaseModel):
    degree: str
    field: str
    batch_year: int

    @field_validator("batch_year")
    @classmethod
    def validate_batch_year(cls, v: int) -> int:
        if v < 2000 or v > 2100:
            raise ValueError(f"Invalid batch year: {v}")
        return v


class ExperienceInfo(StrictBaseModel):
    level: str = "fresher"
    max_years: float = 2.0
    allow_internship: bool = True
    allow_apprenticeship: bool = True


class SkillInfo(StrictBaseModel):
    name: str
    aliases: List[str] = Field(default_factory=list)

    @field_validator("aliases")
    @classmethod
    def deduplicate_aliases(cls, aliases: List[str]) -> List[str]:
        seen = set()
        deduped = []
        for alias in aliases:
            clean = alias.strip().lower()
            if clean and clean not in seen:
                seen.add(clean)
                deduped.append(alias.strip())
        return deduped


class LocationPreferences(StrictBaseModel):
    preferred_cities: List[str] = Field(default_factory=list)
    allow_anywhere_in_india: bool = True
    allow_remote: bool = True
    allow_abroad: bool = False

    @field_validator("preferred_cities")
    @classmethod
    def deduplicate_cities(cls, cities: List[str]) -> List[str]:
        seen = set()
        result = []
        for city in cities:
            normalized = city.strip()
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                result.append(normalized)
        return result


class SalaryPreferences(StrictBaseModel):
    min_fulltime_lpa: float = 3.5
    min_internship_stipend: Optional[float] = None
    keep_unlisted: bool = True


class HardFilters(StrictBaseModel):
    exclude_title_words: List[str] = Field(default_factory=list)
    company_blocklist: List[str] = Field(default_factory=list)
    max_required_experience_years: float = 2.0
    allowed_batch_years: List[int] = Field(default_factory=lambda: [2027])

    @field_validator("exclude_title_words", "company_blocklist")
    @classmethod
    def deduplicate_str_list(cls, items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            clean = item.strip().lower()
            if clean and clean not in seen:
                seen.add(clean)
                result.append(clean)
        return result

    @field_validator("allowed_batch_years")
    @classmethod
    def deduplicate_int_list(cls, items: List[int]) -> List[int]:
        return sorted(list(set(items)))


class ScoringWeights(StrictBaseModel):
    skills: float = 4.0
    role: float = 3.0
    level: float = 2.0
    location: float = 1.0


class LocationScores(StrictBaseModel):
    preferred: float = 1.0
    india_other: float = 0.5
    remote: float = 0.5
    abroad: float = 0.0


class ScoringConfig(StrictBaseModel):
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    location_scores: LocationScores = Field(default_factory=LocationScores)
    min_score: float = 4.0
    strong_threshold: float = 7.0


class DigestConfig(StrictBaseModel):
    max_items: int = 40
    channels: List[str] = Field(default_factory=lambda: ["telegram", "email"])

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, channels: List[str]) -> List[str]:
        allowed = {"telegram", "email"}
        seen = set()
        deduped = []
        for ch in channels:
            ch_lower = ch.strip().lower()
            if ch_lower not in allowed:
                raise ValueError(f"Unsupported delivery channel: {ch}. Allowed: {allowed}")
            if ch_lower not in seen:
                seen.add(ch_lower)
                deduped.append(ch_lower)
        return deduped


class UserProfile(StrictBaseModel):
    """Root user profile configuration."""

    version: int = 3
    user: UserInfo
    education: EducationInfo
    experience: ExperienceInfo = Field(default_factory=ExperienceInfo)
    target_roles: List[str]
    skills: List[SkillInfo]
    tracked_gaps: List[str] = Field(default_factory=list)
    locations: LocationPreferences = Field(default_factory=LocationPreferences)
    salary: SalaryPreferences = Field(default_factory=SalaryPreferences)
    hard_filters: HardFilters = Field(default_factory=HardFilters)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    digest: DigestConfig = Field(default_factory=DigestConfig)

    @field_validator("target_roles", "tracked_gaps")
    @classmethod
    def deduplicate_names(cls, names: List[str]) -> List[str]:
        seen = set()
        result = []
        for name in names:
            clean = name.strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                result.append(clean)
        return result


def parse_profile_yaml(yaml_content: str) -> UserProfile:
    """Parse and validate YAML string into a strict UserProfile."""
    raw_data = yaml.safe_load(yaml_content)
    if not isinstance(raw_data, dict):
        raise ValueError("Profile YAML content must be a valid mapping / dictionary.")
    return UserProfile.model_validate(raw_data)


def load_profile_from_file(file_path: Path | str) -> UserProfile:
    """Load and validate profile from a YAML file."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Profile file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return parse_profile_yaml(f.read())


def load_profile(
    session: Optional[Any] = None,
    base_dir: Optional[Path | str] = None,
) -> UserProfile:
    """
    Load active profile following priority:
    1. Database user_profiles table (if session provided and active profile exists)
    2. Local profile.yaml (gitignored, private)
    3. PROFILE_YAML environment variable (for CI fallback)
    4. profile.example.yaml (default fallback)
    """
    root = Path(base_dir) if base_dir else Path.cwd()

    if session is not None:
        try:
            from job_digest.profile_service import (
                get_active_profile_from_db,
                seed_database_profile_if_empty,
            )
            db_profile, warning_msg = get_active_profile_from_db(session)
            if db_profile:
                if warning_msg:
                    logger.warning(warning_msg)
                return db_profile
            # If database table is empty, attempt to seed it from file
            seeded_profile = seed_database_profile_if_empty(session, base_dir=root)
            if seeded_profile:
                return seeded_profile
        except Exception as exc:
            logger.warning(f"Could not load profile from database ({exc}). Falling back to local file.")

    local_profile = root / "profile.yaml"
    if local_profile.is_file():
        return load_profile_from_file(local_profile)

    env_profile_yaml = os.getenv("PROFILE_YAML")
    if env_profile_yaml and env_profile_yaml.strip():
        return parse_profile_yaml(env_profile_yaml)

    example_profile = root / "profile.example.yaml"
    if example_profile.is_file():
        return load_profile_from_file(example_profile)

    raise FileNotFoundError("No profile found: checked database, profile.yaml, PROFILE_YAML, and profile.example.yaml")
