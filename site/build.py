"""Static Site Generator for Job Digest Agent Public Portfolio Site."""

from __future__ import annotations

import os
import shutil
import sys
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
    },
]


def build_site(dist_dir: Optional[Path] = None, base_url: Optional[str] = None) -> List[Path]:
    """
    Render all Jinja2 templates into static HTML in the destination directory.
    Copies static assets (CSS, SVG icons, images).
    Returns list of generated HTML file paths.
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

    # 4. Copy static assets if they exist
    if STATIC_DIR.exists():
        dest_static = output_dir / "static"
        shutil.copytree(STATIC_DIR, dest_static)

    print(f"[OK] Site build complete: {len(generated_files)} pages rendered into {output_dir}")
    return generated_files


if __name__ == "__main__":
    build_site()
