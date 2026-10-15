"""Configuration loader for sources and system settings."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import yaml
from pydantic import BaseModel, ConfigDict, Field


class SourcesConfig(BaseModel):
    """Configuration mapping for board slugs and API sources."""

    model_config = ConfigDict(extra="ignore")

    version: int = 1
    greenhouse: List[str] = Field(default_factory=list)
    lever: List[str] = Field(default_factory=list)
    ashby: List[str] = Field(default_factory=list)
    smartrecruiters: List[str] = Field(default_factory=list)
    workable: List[str] = Field(default_factory=list)


def load_sources_config(file_path: Path | str | None = None) -> SourcesConfig:
    """Load sources.yaml configuration."""
    path = Path(file_path) if file_path else Path(__file__).resolve().parent.parent / "sources.yaml"
    if not path.is_file():
        return SourcesConfig()

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return SourcesConfig.model_validate(data)
