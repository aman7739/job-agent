"""ATS Slug Checker and Source Expansion Utility.

Scans target tech product companies across Greenhouse, Lever, Ashby, and SmartRecruiters
public APIs to verify board existence, total job count, and India / Remote job volume.

Outputs:
1. Console report with per-company validation.
2. CSV report in reports/ats_slug_report.csv.
3. Ready-to-paste YAML block or automated merge into sources.yaml.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to sys.path so job_digest is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import httpx
import yaml

from job_digest.sources.base import DEFAULT_USER_AGENT, is_india_or_remote

logger = logging.getLogger("check_ats_slugs")

# Default comprehensive candidate list of target Indian product companies,
# high-growth startups, and global engineering hubs in India.
DEFAULT_TARGET_COMPANIES: List[Dict[str, Any]] = [
    {"name": "Razorpay", "slugs": ["razorpay"]},
    {"name": "Swiggy", "slugs": ["swiggy"]},
    {"name": "Zomato", "slugs": ["zomato"]},
    {"name": "CRED", "slugs": ["cred", "dreamplug"]},
    {"name": "Meesho", "slugs": ["meesho"]},
    {"name": "Groww", "slugs": ["groww"]},
    {"name": "PhonePe", "slugs": ["phonepe"]},
    {"name": "Urban Company", "slugs": ["urbancompany"]},
    {"name": "Zepto", "slugs": ["zepto", "kiranakart"]},
    {"name": "InMobi", "slugs": ["inmobi"]},
    {"name": "Hasura", "slugs": ["hasura"]},
    {"name": "Innovaccer", "slugs": ["innovaccer"]},
    {"name": "Dream11", "slugs": ["dream11", "dreamsports"]},
    {"name": "ShareChat", "slugs": ["sharechat", "mohalla"]},
    {"name": "Slice", "slugs": ["slice", "sliceit"]},
    {"name": "Jupiter", "slugs": ["jupiter", "jupitermoney"]},
    {"name": "Porter", "slugs": ["porter"]},
    {"name": "Delhivery", "slugs": ["delhivery"]},
    {"name": "Cars24", "slugs": ["cars24"]},
    {"name": "Nykaa", "slugs": ["nykaa"]},
    {"name": "Cleartrip", "slugs": ["cleartrip"]},
    {"name": "MakeMyTrip", "slugs": ["makemytrip"]},
    {"name": "Classplus", "slugs": ["classplus"]},
    {"name": "Apna", "slugs": ["apna"]},
    {"name": "PhysicsWallah", "slugs": ["physicswallah", "pw"]},
    {"name": "Udaan", "slugs": ["udaan"]},
    {"name": "Spinny", "slugs": ["spinny"]},
    {"name": "Khatabook", "slugs": ["khatabook"]},
    {"name": "Pratilipi", "slugs": ["pratilipi"]},
    {"name": "CoinDCX", "slugs": ["coindcx"]},
    {"name": "CoinSwitch", "slugs": ["coinswitch", "coinswitchkuber"]},
    {"name": "BharatPe", "slugs": ["bharatpe"]},
    {"name": "Dukaan", "slugs": ["dukaan"]},
    {"name": "MPL", "slugs": ["mpl", "galactus"]},
    {"name": "LeadSquared", "slugs": ["leadsquared"]},
    {"name": "Darwinbox", "slugs": ["darwinbox"]},
    {"name": "Chargebee", "slugs": ["chargebee"]},
    {"name": "Freshworks", "slugs": ["freshworks"]},
    {"name": "Druva", "slugs": ["druva"]},
    {"name": "Atlassian", "slugs": ["atlassian"]},
    {"name": "Twilio", "slugs": ["twilio"]},
    {"name": "Snowflake", "slugs": ["snowflake"]},
    {"name": "Rubrik", "slugs": ["rubrik"]},
    {"name": "Nutanix", "slugs": ["nutanix"]},
    {"name": "Cohesity", "slugs": ["cohesity"]},
    {"name": "Samsara", "slugs": ["samsara"]},
    {"name": "Sprinklr", "slugs": ["sprinklr"]},
    {"name": "Thoughtspot", "slugs": ["thoughtspot"]},
    {"name": "SentinelOne", "slugs": ["sentinelone"]},
    {"name": "Licious", "slugs": ["licious"]},
]

ATS_ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{slug}/postings",
}


async def check_greenhouse_slug(client: httpx.AsyncClient, slug: str) -> Optional[Dict[str, Any]]:
    """Verify Greenhouse slug and return job metrics if valid."""
    url = ATS_ENDPOINTS["greenhouse"].format(slug=slug)
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not isinstance(data, dict) or "jobs" not in data or not isinstance(data["jobs"], list):
            return None

        jobs = data["jobs"]
        india_jobs = 0
        sample_titles = []
        for j in jobs:
            loc = ""
            loc_val = j.get("location")
            if isinstance(loc_val, dict):
                loc = loc_val.get("name") or ""
            elif isinstance(loc_val, str):
                loc = loc_val

            if is_india_or_remote(loc):
                india_jobs += 1
                if len(sample_titles) < 3:
                    sample_titles.append(f"{j.get('title', 'Unknown')} ({loc or 'Remote'})")

        return {
            "ats": "greenhouse",
            "slug": slug,
            "total_jobs": len(jobs),
            "india_jobs": india_jobs,
            "samples": sample_titles,
        }
    except Exception:
        return None


async def check_lever_slug(client: httpx.AsyncClient, slug: str) -> Optional[Dict[str, Any]]:
    """Verify Lever slug and return job metrics if valid."""
    url = ATS_ENDPOINTS["lever"].format(slug=slug)
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not isinstance(data, list):
            return None

        india_jobs = 0
        sample_titles = []
        for j in data:
            if not isinstance(j, dict):
                continue
            cat = j.get("categories") or {}
            loc = cat.get("location") or j.get("workplaceType") or ""
            if is_india_or_remote(loc):
                india_jobs += 1
                if len(sample_titles) < 3:
                    sample_titles.append(f"{j.get('text', 'Unknown')} ({loc or 'Remote'})")

        return {
            "ats": "lever",
            "slug": slug,
            "total_jobs": len(data),
            "india_jobs": india_jobs,
            "samples": sample_titles,
        }
    except Exception:
        return None


async def check_ashby_slug(client: httpx.AsyncClient, slug: str) -> Optional[Dict[str, Any]]:
    """Verify Ashby slug and return job metrics if valid."""
    url = ATS_ENDPOINTS["ashby"].format(slug=slug)
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not isinstance(data, dict) or "jobs" not in data or not isinstance(data["jobs"], list):
            return None

        jobs = data["jobs"]
        india_jobs = 0
        sample_titles = []
        for j in jobs:
            if j.get("isListed") is False:
                continue
            loc = j.get("location") or ""
            if is_india_or_remote(loc):
                india_jobs += 1
                if len(sample_titles) < 3:
                    sample_titles.append(f"{j.get('title', 'Unknown')} ({loc or 'Remote'})")

        return {
            "ats": "ashby",
            "slug": slug,
            "total_jobs": len(jobs),
            "india_jobs": india_jobs,
            "samples": sample_titles,
        }
    except Exception:
        return None


async def check_smartrecruiters_slug(client: httpx.AsyncClient, slug: str) -> Optional[Dict[str, Any]]:
    """Verify SmartRecruiters slug and return job metrics if valid."""
    url = ATS_ENDPOINTS["smartrecruiters"].format(slug=slug)
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not isinstance(data, dict) or "content" not in data or not isinstance(data["content"], list):
            return None

        jobs = data["content"]
        india_jobs = 0
        sample_titles = []
        for j in jobs:
            loc_obj = j.get("location") or {}
            city = loc_obj.get("city", "")
            country = loc_obj.get("country", "")
            loc = f"{city}, {country}".strip(", ")
            if is_india_or_remote(loc):
                india_jobs += 1
                if len(sample_titles) < 3:
                    sample_titles.append(f"{j.get('name', 'Unknown')} ({loc or 'Remote'})")

        return {
            "ats": "smartrecruiters",
            "slug": slug,
            "total_jobs": len(jobs),
            "india_jobs": india_jobs,
            "samples": sample_titles,
        }
    except Exception:
        return None


async def scan_company(
    client: httpx.AsyncClient,
    company_name: str,
    slugs: List[str],
    delay_seconds: float = 0.3,
) -> List[Dict[str, Any]]:
    """Scan candidate slugs for a company across all 4 supported ATS providers."""
    results: List[Dict[str, Any]] = []

    for slug in slugs:
        # Check Greenhouse
        gh = await check_greenhouse_slug(client, slug)
        if gh:
            gh["company"] = company_name
            results.append(gh)
        await asyncio.sleep(delay_seconds)

        # Check Lever
        lev = await check_lever_slug(client, slug)
        if lev:
            lev["company"] = company_name
            results.append(lev)
        await asyncio.sleep(delay_seconds)

        # Check Ashby
        ash = await check_ashby_slug(client, slug)
        if ash:
            ash["company"] = company_name
            results.append(ash)
        await asyncio.sleep(delay_seconds)

        # Check SmartRecruiters
        sr = await check_smartrecruiters_slug(client, slug)
        if sr:
            sr["company"] = company_name
            results.append(sr)
        await asyncio.sleep(delay_seconds)

    if not results:
        results.append({
            "company": company_name,
            "ats": "unknown",
            "slug": slugs[0],
            "total_jobs": 0,
            "india_jobs": 0,
            "samples": [],
        })

    return results


def save_report_csv(results: List[Dict[str, Any]], output_path: Path) -> None:
    """Save scan results to CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["company", "ats", "slug", "total_jobs", "india_jobs", "samples", "checked_at"]
    now_str = datetime.now(timezone.utc).isoformat()

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "company": r.get("company", ""),
                "ats": r.get("ats", ""),
                "slug": r.get("slug", ""),
                "total_jobs": r.get("total_jobs", 0),
                "india_jobs": r.get("india_jobs", 0),
                "samples": " | ".join(r.get("samples", [])),
                "checked_at": now_str,
            })


def merge_into_sources_yaml(
    valid_discoveries: List[Dict[str, Any]],
    sources_yaml_path: Path,
) -> Tuple[int, List[str]]:
    """Merge newly discovered boards with India/Remote jobs into sources.yaml."""
    if not sources_yaml_path.exists():
        raise FileNotFoundError(f"{sources_yaml_path} does not exist.")

    with open(sources_yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    added_count = 0
    added_summary = []

    for item in valid_discoveries:
        ats = item.get("ats")
        slug = item.get("slug")
        india_jobs = item.get("india_jobs", 0)

        # Only merge valid ATS boards that have >= 1 India/Remote role
        if ats not in ATS_ENDPOINTS or not slug or india_jobs <= 0:
            continue

        existing_slugs = data.get(ats) or []
        # Case-insensitive membership check
        existing_lower = {s.lower() for s in existing_slugs}
        if slug.lower() not in existing_lower:
            existing_slugs.append(slug)
            data[ats] = existing_slugs
            added_count += 1
            added_summary.append(f"{ats}: {slug} ({item.get('company')} - {india_jobs} India/Remote roles)")

    if added_count > 0:
        with open(sources_yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)

    return added_count, added_summary


async def run_scanner(
    companies: List[Dict[str, Any]],
    delay_seconds: float = 0.3,
    update_yaml: bool = False,
    sources_yaml_path: Optional[Path] = None,
    csv_report_path: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Execute scan across list of companies."""
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json",
    }
    all_results: List[Dict[str, Any]] = []
    valid_with_india: List[Dict[str, Any]] = []

    print(f"\nScanning {len(companies)} target companies across Greenhouse, Lever, Ashby, SmartRecruiters...\n")

    async with httpx.AsyncClient(headers=headers, timeout=12.0) as client:
        for idx, comp in enumerate(companies, 1):
            name = comp["name"]
            slugs = comp.get("slugs", [name.lower()])
            print(f"[{idx:02d}/{len(companies):02d}] Checking {name} (slugs: {', '.join(slugs)})...", end="", flush=True)

            comp_results = await scan_company(client, name, slugs, delay_seconds=delay_seconds)
            all_results.extend(comp_results)

            found_any = False
            for r in comp_results:
                if r["ats"] != "unknown" and r["india_jobs"] > 0:
                    found_any = True
                    valid_with_india.append(r)
                    print(f" [FOUND: {r['ats'].upper()}] -> {r['slug']} ({r['india_jobs']} India roles / {r['total_jobs']} total)")
                    for s in r.get("samples", []):
                        print(f"       * {s}")

            if not found_any:
                active_non_in = [r for r in comp_results if r["ats"] != "unknown" and r["total_jobs"] > 0]
                if active_non_in:
                    r0 = active_non_in[0]
                    print(f" [NO INDIA ROLES] {r0['ats']}:{r0['slug']} has {r0['total_jobs']} jobs (none in India)")
                else:
                    print(" [NOT FOUND / NO JOBS]")

    # Save CSV
    if csv_report_path:
        save_report_csv(all_results, csv_report_path)
        print(f"\n[OK] CSV report written to: {csv_report_path}")

    # Merge into sources.yaml if requested
    if update_yaml and sources_yaml_path:
        added_count, summary = merge_into_sources_yaml(valid_with_india, sources_yaml_path)
        print(f"\n[OK] Updated {sources_yaml_path}: Added {added_count} new company boards.")
        for s in summary:
            print(f"     + {s}")

    return all_results, valid_with_india


def main():
    parser = argparse.ArgumentParser(description="ATS Slug Checker & Expansion Utility")
    parser.add_argument("--company", type=str, help="Single company name to test")
    parser.add_argument("--slugs", type=str, help="Comma-separated candidate slugs")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between HTTP calls (seconds)")
    parser.add_argument("--update-sources-yaml", action="store_true", help="Automatically merge valid boards with India roles into sources.yaml")
    parser.add_argument("--report", type=str, default="reports/ats_slug_report.csv", help="Path to output CSV report")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    sources_yaml_path = project_root / "sources.yaml"
    csv_report_path = project_root / args.report

    if args.company:
        slugs = [s.strip() for s in (args.slugs or args.company.lower()).split(",") if s.strip()]
        companies = [{"name": args.company, "slugs": slugs}]
    else:
        companies = DEFAULT_TARGET_COMPANIES

    asyncio.run(
        run_scanner(
            companies=companies,
            delay_seconds=args.delay,
            update_yaml=args.update_sources_yaml,
            sources_yaml_path=sources_yaml_path,
            csv_report_path=csv_report_path,
        )
    )


if __name__ == "__main__":
    main()
