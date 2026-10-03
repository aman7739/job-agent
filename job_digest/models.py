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
