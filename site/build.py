"""Static Site Generator for Job Digest Agent Public Portfolio Site."""

from __future__ import annotations

import datetime
import importlib.util
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = PROJECT_ROOT / "site"
TEMPLATES_DIR = SITE_DIR / "templates"
STATIC_DIR = SITE_DIR / "static"
DIST_DIR = PROJECT_ROOT / "dist"

DEFAULT_BASE_URL = os.getenv("SITE_BASE_URL", "https://jobdigest.agent").rstrip("/")

PAGES_CONFIG: List[Dict[str, Any]] = [
    {
        "template": "index.html",
        "output_path": "index.html",
        "slug": "/",
        "active_page": "home",
        "page_title": "Autonomous Fresher & Internship Discovery Pipeline",
        "meta_description": "Personal AI Job Digest Agent aggregating tech postings across 8 ATS APIs with 10-point match scoring, twice-daily delivery, and ethical anti-scraping compliance.",
        "canonical_url": f"{DEFAULT_BASE_URL}/",
        "breadcrumbs": [],
        "include_in_sitemap": True,
        "changefreq": "daily",
        "priority": "1.0",
    },
    {
        "template": "how-it-works.html",
        "output_path": "how-it-works/index.html",
        "slug": "/how-it-works/",
        "active_page": "how-it-works",
        "page_title": "Architecture & Ingestion Pipeline",
        "meta_description": "Detailed architectural breakdown of the Job Digest Agent: 8 source adapters, text normalization, SHA-256 deduplication, and 10-point scoring matrix.",
        "canonical_url": f"{DEFAULT_BASE_URL}/how-it-works/",
        "breadcrumbs": [{"label": "How It Works", "url": "/how-it-works/"}],
        "include_in_sitemap": True,
        "changefreq": "weekly",
        "priority": "0.8",
    },
    {
        "template": "sources.html",
        "output_path": "sources/index.html",
        "slug": "/sources/",
        "active_page": "sources",
        "page_title": "Permitted Sources & API Specifications",
        "meta_description": "Catalog of permitted ATS sources, official endpoints, rate limiting safeguards, and ethical anti-scraping guidelines for the Job Digest Agent.",
        "canonical_url": f"{DEFAULT_BASE_URL}/sources/",
        "breadcrumbs": [{"label": "Sources & Compliance", "url": "/sources/"}],
        "include_in_sitemap": True,
        "changefreq": "weekly",
        "priority": "0.8",
    },
    {
        "template": "privacy.html",
        "output_path": "privacy/index.html",
        "slug": "/privacy/",
        "active_page": "privacy",
        "page_title": "Privacy Policy",
        "meta_description": "Privacy policy for Job Digest Agent: personal single-user scope, zero advertising trackers, and secure dual-mailbox separation.",
        "canonical_url": f"{DEFAULT_BASE_URL}/privacy/",
        "breadcrumbs": [{"label": "Privacy Policy", "url": "/privacy/"}],
        "include_in_sitemap": True,
        "changefreq": "monthly",
        "priority": "0.5",
    },
    {
        "template": "terms.html",
        "output_path": "terms/index.html",
        "slug": "/terms/",
        "active_page": "terms",
        "page_title": "Terms of Use",
        "meta_description": "Terms of use and non-commercial educational project guidelines for the Job Digest Agent personal software repository.",
        "canonical_url": f"{DEFAULT_BASE_URL}/terms/",
        "breadcrumbs": [{"label": "Terms of Use", "url": "/terms/"}],
        "include_in_sitemap": True,
        "changefreq": "monthly",
        "priority": "0.5",
    },
    {
        "template": "404.html",
        "output_path": "404.html",
        "slug": "/404.html",
        "active_page": "",
        "page_title": "Page Not Found",
        "meta_description": "The requested resource could not be found on the Job Digest Agent showcase site.",
        "canonical_url": f"{DEFAULT_BASE_URL}/404.html",
        "breadcrumbs": [{"label": "404 Not Found", "url": "/404.html"}],
        "include_in_sitemap": False,  # 404 pages must never appear in sitemaps
        "changefreq": "never",
        "priority": "0.0",
    },
]


def generate_sitemap(pages: List[Dict[str, Any]], target_base: str, output_path: Path) -> Path:
    """Generate an XML sitemap complying with Sitemaps 0.9 protocol."""
    now_date = datetime.date.today().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for page in pages:
        if not page.get("include_in_sitemap", True):
            continue
        slug = page["slug"]
        loc = f"{target_base}{slug}" if slug != "/" else f"{target_base}/"
        freq = page.get("changefreq", "weekly")
        prio = page.get("priority", "0.8")

        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{now_date}</lastmod>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{prio}</priority>")
        lines.append("  </url>")

    lines.append("</urlset>")
    content = "\n".join(lines) + "\n"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def generate_robots_txt(target_base: str, output_path: Path) -> Path:
    """Generate a clean robots.txt allowing indexing of showcase pages and pointing to sitemap."""
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /404.html\n\n"
        f"Sitemap: {target_base}/sitemap.xml\n"
    )
    output_path.write_text(content, encoding="utf-8")
    return output_path


def generate_llms_txt(target_base: str, output_path: Path) -> Path:
    """Generate an llms.txt discovery file providing structured markdown for AI search crawlers."""
    content = f"""# Job Digest Agent

> Autonomous Career Intelligence Pipeline for Batch 2027 CSE Graduates.

The Job Digest Agent is a high-reliability personal career intelligence pipeline built for an engineering graduate actively applying to both Internships/Apprenticeships and Full-Time software engineering roles immediately. It aggregates postings across 8 permitted ATS feeds twice daily (08:00 AM & 07:00 PM IST), normalizes text, deduplicates opportunities via SHA-256 fingerprinting, evaluates roles with a 10-point scoring algorithm, and delivers morning and evening digests to Telegram and SMTP Email. Expiring postings with deadlines closing in <= 4 hours dispatch immediate high-priority alerts.

## Core Documentation & Pages

- [Overview]({target_base}/): Project overview, dual-priority application targets (Internships & Full-Time), and anti-scraping principles.
- [How It Works]({target_base}/how-it-works/): Detailed 5-stage ingestion, normalization, SHA-256 deduplication, 10-point scoring rubric, and dual-channel delivery.
- [Permitted Sources]({target_base}/sources/): Specifications and rate limits for 8 permitted sources (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Adzuna, Remotive, IMAP Email).
- [Privacy Policy]({target_base}/privacy/): Single-user scope, zero advertising trackers, and complete air-gap isolation of private digest/profile data.
- [Terms of Use]({target_base}/terms/): Non-commercial educational usage, non-affiliation disclaimer, and manual application policy.

## Technical Specifications

- Technology Stack: Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL (Supabase), Jinja2, Argon2id, Pillow.
- Autonomous Cadence: Twice-daily scheduled runs at 08:00 AM and 07:00 PM IST via GitHub Actions and APScheduler.
- Instant Fast-Track: Emergency alert dispatcher for postings expiring in <= 4 hours.
- Scoring Rubric: 10-point scale evaluating Skills Overlap (4.0 pts), Role Match (3.0 pts), Level (2.0 pts), and Location (1.0 pt).
- Candidate Context: Final-year B.Tech CSE (Batch 2027) graduate actively targeting internships and entry-level engineering positions.
- Security & Compliance: Air-gapped single-user web dashboard, enterprise CSP/HSTS headers, zero scraping of LinkedIn/Naukri/Indeed.
"""
    output_path.write_text(content, encoding="utf-8")
    return output_path


def build_site(dist_dir: Optional[Path] = None, base_url: Optional[str] = None) -> List[Path]:
    """
    Render all Jinja2 templates into static HTML in the destination directory.
    Generates sitemap.xml, robots.txt, and llms.txt.
    Copies static assets (CSS, SVG icons, images).
    Returns list of generated file paths.
    """
    output_dir = dist_dir or DIST_DIR
    target_base = (base_url or DEFAULT_BASE_URL).rstrip("/")

    # 1. Clean and re-create dist/ directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Setup Jinja2 Environment
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )

    # 2.5 Ensure social share assets exist
    og_image_file = STATIC_DIR / "images" / "og-image.png"
    if not og_image_file.exists():
        gen_path = SITE_DIR / "generate_og_images.py"
        if gen_path.exists():
            spec = importlib.util.spec_from_file_location("gen_og", gen_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.create_og_image()

    generated_files: List[Path] = []

    # 3. Render each page
    for cfg in PAGES_CONFIG:
        template = env.get_template(cfg["template"])
        canonical = f"{target_base}{cfg['slug']}" if cfg['slug'] != "/" else f"{target_base}/"
        
        context = {
            "page_title": cfg["page_title"],
            "meta_description": cfg["meta_description"],
            "canonical_url": canonical,
            "breadcrumbs": cfg["breadcrumbs"],
            "active_page": cfg["active_page"],
            "base_url": target_base,
        }

        rendered_html = template.render(**context)

        dest_file = output_dir / cfg["output_path"]
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_text(rendered_html, encoding="utf-8")
        generated_files.append(dest_file)

    # 4. Generate Crawl & Discovery Files (sitemap.xml, robots.txt, llms.txt)
    sitemap_path = output_dir / "sitemap.xml"
    generate_sitemap(PAGES_CONFIG, target_base, sitemap_path)
    generated_files.append(sitemap_path)

    robots_path = output_dir / "robots.txt"
    generate_robots_txt(target_base, robots_path)
    generated_files.append(robots_path)

    llms_path = output_dir / "llms.txt"
    generate_llms_txt(target_base, llms_path)
    generated_files.append(llms_path)

    # 5. Copy static assets if they exist
    if STATIC_DIR.exists():
        dest_static = output_dir / "static"
        shutil.copytree(STATIC_DIR, dest_static)

    print(f"[OK] Site build complete: {len(generated_files)} pages & crawl files rendered into {output_dir}")
    return generated_files


if __name__ == "__main__":
    build_site()
