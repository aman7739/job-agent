"""Source orchestrator with error isolation and source_runs database tracking."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from job_digest.models import RawJob, SourceRunResult
from job_digest.sources.base import JobSource

logger = logging.getLogger(__name__)


def record_source_run_in_db(
    session: Optional[Session],
    result: SourceRunResult,
) -> None:
    """Record execution metrics into the source_runs table if a DB session is provided."""
    if session is None:
        return

    try:
        stmt = text(
            """
            INSERT INTO source_runs (
                source_name, started_at, finished_at, jobs_found, jobs_new, is_success, error_message
            ) VALUES (
                :source_name, :started_at, :finished_at, :jobs_found, :jobs_new, :is_success, :error_message
            )
            """
        )
        session.execute(
            stmt,
            {
                "source_name": result.source_name,
                "started_at": result.started_at,
                "finished_at": result.finished_at,
                "jobs_found": result.jobs_found,
                "jobs_new": result.jobs_new,
                "is_success": result.is_success,
                "error_message": result.error_message,
            },
        )
        session.commit()
    except Exception as exc:
        logger.warning(f"Could not write source run metrics to database: {exc}")
        try:
            session.rollback()
        except Exception:
            pass


async def execute_source(
    source: JobSource,
    session: Optional[Session] = None,
) -> Tuple[List[RawJob], SourceRunResult]:
    """Execute a single source wrapped in try/except with metrics recording."""
    started_at = datetime.now(timezone.utc)
    logger.info(f"Starting fetch for source: {source.name}")

    try:
        jobs = await source.fetch()
        finished_at = datetime.now(timezone.utc)
        result = SourceRunResult(
            source_name=source.name,
            started_at=started_at,
            finished_at=finished_at,
            jobs_found=len(jobs),
            jobs_new=0,  # Updated after deduplication in later sessions
            is_success=True,
            error_message=None,
        )
        logger.info(f"Source '{source.name}' completed successfully with {len(jobs)} jobs.")
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        result = SourceRunResult(
            source_name=source.name,
            started_at=started_at,
            finished_at=finished_at,
            jobs_found=0,
            jobs_new=0,
            is_success=False,
            error_message=str(exc),
        )
        logger.error(f"Source '{source.name}' failed with error: {exc}", exc_info=True)
        jobs = []

    record_source_run_in_db(session, result)
    return jobs, result


async def run_all_sources(
    sources: List[JobSource],
    session: Optional[Session] = None,
) -> Tuple[Dict[str, List[RawJob]], List[SourceRunResult]]:
    """
    Run all configured sources with fault isolation.
    If any single source crashes or suffers a network failure, the remaining
    sources continue normally without interruption.
    """
    all_jobs_by_source: Dict[str, List[RawJob]] = {}
    all_results: List[SourceRunResult] = []

    for source in sources:
        jobs, result = await execute_source(source, session=session)
        all_jobs_by_source[source.name] = jobs
        all_results.append(result)

    total_jobs = sum(len(j) for j in all_jobs_by_source.values())
    successful_sources = sum(1 for r in all_results if r.is_success)
    logger.info(
        f"Sources run completed: {successful_sources}/{len(sources)} sources succeeded, {total_jobs} total jobs retrieved."
    )

    return all_jobs_by_source, all_results
