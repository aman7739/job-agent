"""Master pipeline runner and scheduler for Job Digest Agent."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

from job_digest.config import load_sources_config
from job_digest.db import get_database_url, get_db_session
from job_digest.dedup import process_and_upsert_jobs
from job_digest.digest import build_digest, save_digest_to_db
from job_digest.match import rank_and_score_jobs
from job_digest.models import Job, RawJob
from job_digest.normalize import normalize_raw_job
from job_digest.notify import (
    EmailNotifier,
    Notifier,
    TelegramNotifier,
    deliver_digest,
    filter_unnotified_jobs,
)
from job_digest.profile import UserProfile, load_profile
from job_digest.sources.adzuna import AdzunaSource
from job_digest.sources.ashby import AshbySource
from job_digest.sources.base import JobSource
from job_digest.sources.email_alerts import EmailAlertSource
from job_digest.sources.greenhouse import GreenhouseSource
from job_digest.sources.lever import LeverSource
from job_digest.sources.remote import RemotiveSource
from job_digest.sources.runner import run_all_sources
from job_digest.sources.smartrecruiters import SmartRecruitersSource
from job_digest.sources.workable import WorkableSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("job_digest.run")


def instantiate_sources(
    sources_cfg,
    db_session=None,
    active_sources: Optional[List[str]] = None,
) -> List[JobSource]:
    """Instantiate configured job sources."""
    available_sources: Dict[str, JobSource] = {
        "greenhouse": GreenhouseSource(slugs=sources_cfg.greenhouse),
        "lever": LeverSource(slugs=sources_cfg.lever),
        "ashby": AshbySource(slugs=sources_cfg.ashby),
        "smartrecruiters": SmartRecruitersSource(slugs=sources_cfg.smartrecruiters),
        "workable": WorkableSource(slugs=sources_cfg.workable),
        "remotive": RemotiveSource(enforce_rate_limit=True),
        "adzuna": AdzunaSource(),
        "email_alerts": EmailAlertSource(session=db_session),
    }

    if active_sources is not None:
        return [s for name, s in available_sources.items() if name in active_sources]
    return list(available_sources.values())


def instantiate_notifiers(profile: UserProfile) -> List[Notifier]:
    """Instantiate delivery channels configured in user profile."""
    notifiers: List[Notifier] = []
    channels = set(profile.digest.channels)

    if "telegram" in channels:
        notifiers.append(TelegramNotifier())
    if "email" in channels:
        notifiers.append(EmailNotifier())

    return notifiers


async def run_digest_pipeline(
    dry_run: bool = False,
    active_sources: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Execute complete Job Digest Agent pipeline end-to-end:
    Fetch -> Normalize -> Deduplicate -> Match/Score -> Build Digest -> Deliver -> Persist.
    """
    run_timestamp = now or datetime.now(timezone.utc)
    logger.info(f"Starting Job Digest Pipeline (dry_run={dry_run}) at {run_timestamp.isoformat()}")

    # 1. Load Profile & Sources Config
    profile = load_profile()
    sources_cfg = load_sources_config()

    # 2. Database Session (if DATABASE_URL is configured)
    db_available = bool(get_database_url())
    session_context = get_db_session() if db_available and not dry_run else None

    # Handle optional DB session safely
    db_session = None
    if session_context:
        try:
            db_session = session_context.__enter__()
        except Exception as exc:
            logger.warning(f"Could not open database session: {exc}. Running in memory.")
            session_context = None

    try:
        # 3. Instantiate and run sources
        sources = instantiate_sources(sources_cfg, db_session=db_session, active_sources=active_sources)
        jobs_by_source, run_results = await run_all_sources(sources, session=db_session)

        all_raw_jobs: List[RawJob] = []
        failed_sources: List[str] = []
        for r in run_results:
            if r.is_success:
                all_raw_jobs.extend(jobs_by_source.get(r.source_name, []))
            else:
                failed_sources.append(r.source_name)

        logger.info(f"Fetched {len(all_raw_jobs)} raw jobs across {len(sources)} sources.")

        # 4. Normalize all raw jobs
        normalized_jobs = [normalize_raw_job(raw, profile=profile) for raw in all_raw_jobs]
        logger.info(f"Normalized {len(normalized_jobs)} jobs.")

        # 5. Deduplicate, filter stale, and upsert
        dedup_result = process_and_upsert_jobs(
            normalized_jobs,
            session=db_session if not dry_run else None,
            now=run_timestamp,
        )
        logger.info(
            f"Deduplication complete: {len(dedup_result.new_jobs)} new, "
            f"{len(dedup_result.already_seen_jobs)} already seen, "
            f"{dedup_result.duplicate_count} duplicates dropped, "
            f"{dedup_result.stale_count} stale dropped."
        )

        # 6. Filter already notified jobs
        fresh_jobs = dedup_result.new_jobs + dedup_result.already_seen_jobs
        unnotified_jobs = (
            filter_unnotified_jobs(fresh_jobs, db_session)
            if db_session and not dry_run
            else fresh_jobs
        )

        # 7. Match, score, and rank jobs
        scored_jobs = rank_and_score_jobs(unnotified_jobs, profile=profile)
        logger.info(f"Scored and ranked {len(scored_jobs)} eligible jobs meeting threshold.")

        # 8. Build digest
        digest = build_digest(
            scored_jobs=scored_jobs,
            new_count=len(dedup_result.new_jobs),
            seen_count=len(dedup_result.already_seen_jobs),
            failed_sources=failed_sources,
            profile=profile,
            now=run_timestamp,
        )

        # 9. Deliver and Persist
        delivered_channels: List[str] = []
        if not dry_run:
            notifiers = instantiate_notifiers(profile)
            fps_to_mark = [s.job.fingerprint for s in scored_jobs if s.job.fingerprint]
            delivered_channels = await deliver_digest(
                digest=digest,
                notifiers=notifiers,
                fingerprints_to_mark=fps_to_mark,
                session=db_session,
            )
            save_digest_to_db(db_session, digest, channels_notified=delivered_channels)
            logger.info(f"Digest delivered to channels: {delivered_channels}")
        else:
            logger.info("[DRY RUN] Digest generated successfully without sending.")

        return {
            "status": "success",
            "timestamp": run_timestamp.isoformat(),
            "raw_jobs_found": len(all_raw_jobs),
            "new_jobs": len(dedup_result.new_jobs),
            "already_seen": len(dedup_result.already_seen_jobs),
            "scored_jobs": len(scored_jobs),
            "total_in_digest": digest.total_jobs,
            "internships_count": digest.internships_count,
            "fulltime_count": digest.fulltime_count,
            "delivered_channels": delivered_channels,
            "failed_sources": failed_sources,
            "digest_text": digest.content_text,
        }

    finally:
        if session_context:
            session_context.__exit__(None, None, None)


def start_local_scheduler():
    """Start local APScheduler running every day at 08:00 IST (02:30 UTC)."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("APScheduler is not installed. Run 'pip install apscheduler'.")
        return

    scheduler = BlockingScheduler()
    # 08:00 IST = 02:30 UTC
    trigger = CronTrigger(hour=2, minute=30, timezone="UTC")

    def scheduled_job():
        logger.info("APScheduler triggered daily digest run...")
        asyncio.run(run_digest_pipeline(dry_run=False))

    scheduler.add_job(scheduled_job, trigger=trigger, name="Daily Job Digest")
    logger.info("Local APScheduler started. Scheduled daily at 08:00 IST (02:30 UTC). Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Local scheduler stopped.")


def main():
    parser = argparse.ArgumentParser(description="Job Digest Agent CLI & Runner")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline and print digest without delivering")
    parser.add_argument("--schedule", action="store_true", help="Start local APScheduler daemon")
    args = parser.parse_args()

    if args.schedule:
        start_local_scheduler()
    else:
        result = asyncio.run(run_digest_pipeline(dry_run=args.dry_run))
        print("\n" + "=" * 50)
        print("PIPELINE RUN SUMMARY")
        print("=" * 50)
        for k, v in result.items():
            if k != "digest_text":
                print(f"  {k:20}: {v}")
        print("=" * 50 + "\n")
        if args.dry_run:
            print("--- PREVIEW DIGEST TEXT ---\n")
            print(result["digest_text"][:2000] + ("\n... [truncated]" if len(result["digest_text"]) > 2000 else ""))


if __name__ == "__main__":
    main()
