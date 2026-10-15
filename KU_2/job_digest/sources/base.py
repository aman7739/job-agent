"""Base interface and utilities for all job sources."""

from __future__ import annotations

import re
from typing import List, Protocol, runtime_checkable
from job_digest.models import RawJob

DEFAULT_USER_AGENT = "JobDigestAgent/1.0 (+https://github.com/job-digest-agent; personal fresher job search)"

# Common Indian cities and synonyms
INDIAN_LOCATIONS = {
    "india",
    "in",
    "bengaluru",
    "bangalore",
    "delhi",
    "new delhi",
    "noida",
    "greater noida",
    "gurgaon",
    "gurugram",
    "delhi ncr",
    "ncr",
    "hyderabad",
    "mumbai",
    "bombay",
    "pune",
    "chennai",
    "madras",
    "kolkata",
    "calcutta",
    "indore",
    "ahmedabad",
    "jaipur",
    "kochi",
    "cochin",
    "coimbatore",
    "chandigarh",
    "mohali",
    "bhopal",
    "lucknow",
    "trivandrum",
    "thiruvananthapuram",
    "nagpur",
    "surat",
    "vadodara",
    "bhubaneswar",
}

REMOTE_KEYWORDS = {
    "remote",
    "anywhere",
    "telecommute",
    "work from home",
    "wfh",
    "virtual",
    "distributed",
}


def is_india_or_remote(location: str | None) -> bool:
    """
    Check if a location string indicates India or a Remote role.
    Handles compound strings like 'Bengaluru, India', 'Remote - India', 'Anywhere (Remote)'.
    If location is missing or explicitly 'remote', returns True.
    """
    if not location or not location.strip():
        return True

    norm = location.lower()

    # Direct remote keyword check
    for rk in REMOTE_KEYWORDS:
        if rk in norm:
            return True

    # Word-boundary check for Indian locations
    tokens = re.findall(r"\b[a-z0-9\s]+\b", norm)
    for token in tokens:
        clean = token.strip()
        if clean in INDIAN_LOCATIONS:
            return True

    for loc in INDIAN_LOCATIONS:
        # Check subphrase presence (e.g. 'ncr' in 'delhi-ncr', 'india' in 'remote - india')
        if re.search(rf"\b{re.escape(loc)}\b", norm):
            return True

    return False


@runtime_checkable
class JobSource(Protocol):
    """Protocol that every job source adapter must satisfy."""

    @property
    def name(self) -> str:
        """Unique identifier name for this source adapter."""
        ...

    async def fetch(self) -> List[RawJob]:
        """Asynchronously fetch jobs from this source and return RawJob list."""
        ...
