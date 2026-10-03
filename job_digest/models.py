"""Data models for raw and normalized job representations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RawJob(BaseModel):
    """Raw job extracted directly from a source before normalization and scoring."""

    model_config = ConfigDict(extra="ignore")

    source: str
    source_id: str  # company board slug or source name
    external_id: str
    title: str
    company: str
    location: str
    url: str
    description_html: Optional[str] = None
    description_text: Optional[str] = None
    posted_at: Optional[datetime] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    def __repr__(self) -> str:
        return f"<RawJob(company='{self.company}', title='{self.title}', location='{self.location}', source='{self.source}')>"


class SourceRunResult(BaseModel):
    """Execution metrics for a single source run."""

    source_name: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    jobs_found: int = 0
    jobs_new: int = 0
    is_success: bool = False
    error_message: Optional[str] = None


class Job(BaseModel):
    """Normalized job representation with extracted metadata and parsed fields."""

    model_config = ConfigDict(extra="ignore")

    id: Optional[int] = None
    fingerprint: Optional[str] = None
    title: str
    company: str
    location: str
    canonical_url: str
    description_text: str
    posted_at: Optional[datetime] = None
    source: str
    skills: List[str] = Field(default_factory=list)
    min_years: Optional[float] = None
    is_intern: bool = False
    is_apprentice: bool = False
    salary_lpa: Optional[float] = None
    stipend: Optional[float] = None
    batch_years: List[int] = Field(default_factory=list)
    status: str = "seen"
    saved_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    not_interested_at: Optional[datetime] = None
    notes: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    def __repr__(self) -> str:
        return f"<Job(company='{self.company}', title='{self.title}', status='{self.status}', lpa={self.salary_lpa})>"

