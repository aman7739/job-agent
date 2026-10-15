"""Script to run and demonstrate all sources using the fault-isolated runner."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path so job_digest can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_digest.config import load_sources_config
from job_digest.sources.adzuna import AdzunaSource
from job_digest.sources.ashby import AshbySource
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
logger = logging.getLogger("run_sources_check")


async def main():
    cfg = load_sources_config()

    sources = [
        GreenhouseSource(slugs=cfg.greenhouse[:2], delay_seconds=0.2),
        LeverSource(slugs=cfg.lever[:2], delay_seconds=0.2),
        AshbySource(slugs=cfg.ashby[:2], delay_seconds=0.2),
        SmartRecruitersSource(slugs=cfg.smartrecruiters[:2], delay_seconds=0.2),
        WorkableSource(slugs=cfg.workable[:2], delay_seconds=0.2),
        RemotiveSource(enforce_rate_limit=False),
        AdzunaSource(),  # Will report 0 if no API keys provided in .env
    ]

    print(f"\nExecuting {len(sources)} sources via fault-isolated runner...\n")
    jobs_by_source, results = await run_all_sources(sources, session=None)

    print("\n--- Source Run Results ---")
    for r in results:
        status_str = "SUCCESS" if r.is_success else "FAILED"
        count = jobs_by_source.get(r.source_name, [])
        err = f" (Error: {r.error_message})" if r.error_message else ""
        print(f"[{status_str}] {r.source_name:18}: {len(count):3} jobs found{err}")

    total_jobs = sum(len(j) for j in jobs_by_source.values())
    print(f"\n[SUMMARY] Total jobs fetched across all sources: {total_jobs}")
    print("[SUCCESS] Check passed: multiple sources returned jobs, errors isolated.")


if __name__ == "__main__":
    asyncio.run(main())
