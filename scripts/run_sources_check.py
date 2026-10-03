"""Script to test source fetching across all 5 ATS platforms (Greenhouse, Lever, Ashby, SmartRecruiters, Workable)."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path so job_digest can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_digest.config import load_sources_config
from job_digest.sources.ashby import AshbySource
from job_digest.sources.greenhouse import GreenhouseSource
from job_digest.sources.lever import LeverSource
from job_digest.sources.smartrecruiters import SmartRecruitersSource
from job_digest.sources.workable import WorkableSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_sources_check")


async def main():
    cfg = load_sources_config()

    print("\n--- Testing Greenhouse Source ---")
    gh_slugs = (cfg.greenhouse[:2] if cfg.greenhouse else ["cloudflare"]) + ["bad-greenhouse-slug-999"]
    gh_source = GreenhouseSource(slugs=gh_slugs, delay_seconds=0.2)
    gh_jobs = await gh_source.fetch()
    print(f"Total Greenhouse jobs (India/Remote): {len(gh_jobs)}")

    print("\n--- Testing Lever Source ---")
    lever_slugs = (cfg.lever[:2] if cfg.lever else ["spotify"]) + ["bad-lever-slug-999"]
    lever_source = LeverSource(slugs=lever_slugs, delay_seconds=0.2)
    lever_jobs = await lever_source.fetch()
    print(f"Total Lever jobs (India/Remote): {len(lever_jobs)}")

    print("\n--- Testing Ashby Source ---")
    ashby_slugs = (cfg.ashby[:2] if cfg.ashby else ["openai"]) + ["bad-ashby-slug-999"]
    ashby_source = AshbySource(slugs=ashby_slugs, delay_seconds=0.2)
    ashby_jobs = await ashby_source.fetch()
    print(f"Total Ashby jobs (India/Remote): {len(ashby_jobs)}")
    for j in ashby_jobs[:2]:
        print(f"  - [{j.company}] {j.title} ({j.location}) -> {j.url}")

    print("\n--- Testing SmartRecruiters Source ---")
    sr_slugs = (cfg.smartrecruiters[:2] if cfg.smartrecruiters else ["BoschGroup"]) + ["bad-sr-slug-999"]
    sr_source = SmartRecruitersSource(slugs=sr_slugs, delay_seconds=0.2)
    sr_jobs = await sr_source.fetch()
    print(f"Total SmartRecruiters jobs (India/Remote): {len(sr_jobs)}")
    for j in sr_jobs[:2]:
        print(f"  - [{j.company}] {j.title} ({j.location}) -> {j.url}")

    print("\n--- Testing Workable Source ---")
    workable_slugs = (cfg.workable[:2] if cfg.workable else ["transferwise"]) + ["bad-workable-slug-999"]
    workable_source = WorkableSource(slugs=workable_slugs, delay_seconds=0.2)
    workable_jobs = await workable_source.fetch()
    print(f"Total Workable jobs (India/Remote): {len(workable_jobs)}")

    print("\n[SUCCESS] Run completed across all 5 ATS platforms without crashing on bad slugs.")


if __name__ == "__main__":
    asyncio.run(main())
