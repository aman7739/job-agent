"""Eligibility filtering, 10-point match scoring, and tracked gaps evaluation."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, ConfigDict, Field

from job_digest.models import Job
from job_digest.profile import UserProfile

logger = logging.getLogger(__name__)


class ScoredJob(BaseModel):
    """Enriched Job with match score, breakdown, and reasoning."""

    model_config = ConfigDict(extra="ignore")

    job: Job
    score: float
    category: str  # 'Strong' (>= 7.0) or 'Maybe' (4.0 - 6.9)
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    location_reason: str = ""
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    short_reasons: List[str] = Field(default_factory=list)

    @property
    def is_intern_or_apprentice(self) -> bool:
        return self.job.is_intern or self.job.is_apprentice


def check_eligibility(job: Job, profile: UserProfile) -> Tuple[bool, Optional[str]]:
    """
    Apply hard filters to determine if candidate is strictly eligible for this role.
    Returns (is_eligible, drop_reason).
    """
    title_lower = job.title.lower()
    company_lower = job.company.lower()

    # 1. Whole-word exclude title words (e.g. senior, lead, manager, principal, director, staff, architect)
    for word in profile.hard_filters.exclude_title_words:
        if re.search(rf"\b{re.escape(word)}\b", title_lower, re.I):
            return False, f"Title contains excluded word: '{word}'"

    # 2. Company blocklist
    for blocked in profile.hard_filters.company_blocklist:
        if blocked in company_lower:
            return False, f"Company '{job.company}' is in blocklist"

    # 3. Required experience > 2 years
    if job.min_years is not None and job.min_years > profile.hard_filters.max_required_experience_years:
        return False, f"Required experience ({job.min_years} yrs) exceeds maximum ({profile.hard_filters.max_required_experience_years} yrs)"

    # 4. Named batch year other than allowed batch years (e.g. 2025 batch listing when only 2027 is allowed)
    if job.batch_years:
        allowed_set = set(profile.hard_filters.allowed_batch_years)
        # If none of the named batch years match the allowed batch years, drop
        if not any(year in allowed_set for year in job.batch_years):
            return False, f"Named batch years {job.batch_years} do not match allowed batch years {profile.hard_filters.allowed_batch_years}"

    # 5. Full-time salary below 3.5 LPA when listed
    if not job.is_intern and not job.is_apprentice and job.salary_lpa is not None:
        if job.salary_lpa < profile.salary.min_fulltime_lpa:
            return False, f"Listed salary ({job.salary_lpa} LPA) is below minimum ({profile.salary.min_fulltime_lpa} LPA)"

    return True, None


def score_skills(job_skills: List[str], profile_skill_names: Set[str], weight: float = 4.0) -> Tuple[float, List[str]]:
    """
    Score skill overlap on 0 to weight scale.
    Graduated score based on number and ratio of candidate skills present.
    """
    matched = [s for s in job_skills if s in profile_skill_names]

    if not matched:
        return 0.0, []

    count = len(matched)
    if count >= 4:
        raw_score = 1.0
    elif count == 3:
        raw_score = 0.8
    elif count == 2:
        raw_score = 0.6
    else:
        raw_score = 0.4

    return round(raw_score * weight, 2), matched


def score_role(job_title: str, target_roles: List[str], weight: float = 3.0) -> float:
    """Score role alignment against candidate's 41 target roles."""
    title_lower = job_title.lower()

    # Exact or near-exact match
    for role in target_roles:
        r_lower = role.lower()
        if r_lower in title_lower or title_lower in r_lower:
            return round(1.0 * weight, 2)

    # Sub-keyword match
    core_tech_terms = ["developer", "engineer", "analyst", "intern", "trainee", "apprentice", "programmer", "sdet"]
    matched_terms = [t for t in core_tech_terms if re.search(rf"\b{t}\b", title_lower)]

    if len(matched_terms) >= 2:
        return round(0.8 * weight, 2)
    elif len(matched_terms) == 1:
        return round(0.6 * weight, 2)

    return round(0.3 * weight, 2)


def score_level(job: Job, weight: float = 2.0) -> float:
    """Score experience level fit on 0 to weight scale."""
    if job.is_intern or job.is_apprentice:
        return round(1.0 * weight, 2)

    if job.min_years is not None:
        if job.min_years == 0.0:
            return round(1.0 * weight, 2)
        elif job.min_years <= 1.0:
            return round(0.9 * weight, 2)
        elif job.min_years <= 2.0:
            return round(0.7 * weight, 2)

    # Experience unstated
    return round(0.6 * weight, 2)


def score_location(location: str, profile: UserProfile, weight: float = 1.0) -> Tuple[float, str]:
    """Score location fit: Preferred city = 1.0, Elsewhere in India / Remote = 0.5, Abroad = 0.0."""
    loc_lower = location.lower()

    # Check preferred cities
    for city in profile.locations.preferred_cities:
        if re.search(rf"\b{re.escape(city.lower())}\b", loc_lower):
            return round(profile.scoring.location_scores.preferred * weight, 2), f"Preferred city: {city}"

    # Check remote
    if "remote" in loc_lower or "anywhere" in loc_lower or "wfh" in loc_lower:
        return round(profile.scoring.location_scores.remote * weight, 2), "Remote role"

    # Check anywhere in India
    indian_cities_or_states = [
        "india", "bengaluru", "bangalore", "hyderabad", "chennai",
        "ahmedabad", "jaipur", "kochi", "coimbatore", "chandigarh",
    ]
    for ic in indian_cities_or_states:
        if re.search(rf"\b{ic}\b", loc_lower):
            return round(profile.scoring.location_scores.india_other * weight, 2), f"India location: {location}"

    return round(profile.scoring.location_scores.abroad * weight, 2), f"Location: {location}"


def evaluate_job(job: Job, profile: UserProfile) -> Optional[ScoredJob]:
    """
    Evaluate eligibility and calculate match score for a job.
    Returns ScoredJob if eligible and score >= profile.scoring.min_score, otherwise None.
    """
    # 1. Hard filters check
    is_eligible, drop_reason = check_eligibility(job, profile)
    if not is_eligible:
        logger.debug(f"Job dropped by hard filter: [{job.company}] {job.title} - {drop_reason}")
        return None

    # Profile candidate skills set
    profile_skill_names = {s.name for s in profile.skills}

    # 2. Score factors
    skill_pts, matched_skills = score_skills(job.skills, profile_skill_names, weight=profile.scoring.weights.skills)
    role_pts = score_role(job.title, profile.target_roles, weight=profile.scoring.weights.role)
    level_pts = score_level(job, weight=profile.scoring.weights.level)
    loc_pts, loc_reason = score_location(job.location, profile, weight=profile.scoring.weights.location)

    total_score = round(skill_pts + role_pts + level_pts + loc_pts, 1)

    # 3. Minimum score threshold check
    if total_score < profile.scoring.min_score:
        logger.debug(f"Job below minimum score ({total_score} < {profile.scoring.min_score}): {job.title}")
        return None

    category = "Strong" if total_score >= profile.scoring.strong_threshold else "Maybe"

    # 4. Identify tracked gaps in description (never deducted from score)
    missing_skills: List[str] = []
    desc_lower = job.description_text.lower()
    for gap in profile.tracked_gaps:
        if re.search(rf"\b{re.escape(gap.lower())}\b", desc_lower) and gap not in matched_skills:
            missing_skills.append(gap)

    short_reasons = []
    if matched_skills:
        short_reasons.append(f"{len(matched_skills)} skills matched")
    short_reasons.append(loc_reason)
    if job.is_intern:
        short_reasons.append("Internship opportunity")
    elif job.min_years == 0.0:
        short_reasons.append("Fresher eligible")

    return ScoredJob(
        job=job,
        score=total_score,
        category=category,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        location_reason=loc_reason,
        score_breakdown={
            "skills": skill_pts,
            "role": role_pts,
            "level": level_pts,
            "location": loc_pts,
        },
        short_reasons=short_reasons,
    )


def rank_and_score_jobs(jobs: List[Job], profile: UserProfile) -> List[ScoredJob]:
    """Score, filter, and sort jobs by score descending."""
    scored: List[ScoredJob] = []
    for job in jobs:
        res = evaluate_job(job, profile)
        if res:
            scored.append(res)

    # Sort descending by score
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
