"""Script to test source fetching (Greenhouse and Lever), including handling bad slugs."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path so job_digest can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_digest.config import load_sources_config
from job_digest.sources.greenhouse import GreenhouseSource
from job_digest.sources.lever import LeverSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_sources_run")


async def main():
    cfg = load_sources_config()

    # Pick 2 verified Greenhouse slugs + 1 known invalid slug to demonstrate resilience
    gh_slugs = (cfg.greenhouse[:2] if cfg.greenhouse else ["cloudflare", "gitlab"]) + ["bad-slug-nonexistent-12345"]
    # Pick 2 verified Lever slugs + 1 known invalid slug
    lever_slugs = (cfg.lever[:2] if cfg.lever else ["postman", "docker"]) + ["bad-lever-nonexistent-99999"]

    print("\n--- Testing Greenhouse Source ---")
    gh_source = GreenhouseSource(slugs=gh_slugs, delay_seconds=0.2)
    gh_jobs = await gh_source.fetch()
    print(f"Total Greenhouse jobs fetched (filtered to India/Remote): {len(gh_jobs)}")
    for j in gh_jobs[:3]:
        print(f"  - [{j.company}] {j.title} ({j.location}) -> {j.url}")

    print("\n--- Testing Lever Source ---")
    lever_source = LeverSource(slugs=lever_slugs, delay_seconds=0.2)
    lever_jobs = await lever_source.fetch()
    print(f"Total Lever jobs fetched (filtered to India/Remote): {len(lever_jobs)}")
    for j in lever_jobs[:3]:
        print(f"  - [{j.company}] {j.title} ({j.location}) -> {j.url}")

    print("\n[SUCCESS] Run completed without crashing on bad slugs.")


if __name__ == "__main__":
    asyncio.run(main())
