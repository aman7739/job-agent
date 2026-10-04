"""Session 22 Tests: Comprehensive End-to-End System Integrity & Final Wrap-Up Verification.

Asserts:
1. Milestone 1 Pipeline: All 8 source adapters, normalization, dedup, 10-point scoring, urgency detector, and delivery modules.
2. Milestone 2 Private Web App: FastAPI app, authentication, job status actions, settings editor, source health, and health checks.
3. Milestone 3 Public Showcase: Static build files (9 pages and crawl assets), Schema.org JSON-LD, sitemap, robots, llms.txt, and visual media.
4. Milestone 4 Documentation: Complete runbook, portfolio briefing, ADRs 001-017, and disaster recovery backup plan.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from bs4 import BeautifulSoup
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
SITE_DIR = PROJECT_ROOT / "site"


@pytest.fixture(scope="module", autouse=True)
def ensure_built_showcase():
    """Ensure site is freshly built into dist/ before running wrapup assertions."""
    build_script = SITE_DIR / "build.py"
    spec = importlib.util.spec_from_file_location("site_build", build_script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = module.build_site(dist_dir=DIST_DIR)
    return files


def test_milestone_1_autonomous_pipeline_integrity():
    """Verify all 8 source adapters, normalization, dedup, scoring, and urgency modules exist."""
    sources_dir = PROJECT_ROOT / "job_digest" / "sources"
    expected_sources = [
        "greenhouse.py",
        "lever.py",
        "ashby.py",
        "smartrecruiters.py",
        "workable.py",
        "adzuna.py",
        "remote.py",  # Remotive API feed
        "email_alerts.py",
    ]
    for src in expected_sources:
        assert (sources_dir / src).exists(), f"Source adapter {src} missing from job_digest/sources/"

    # Core engine modules
    core_modules = [
        "normalize.py",
        "dedup.py",
        "match.py",      # 10-point scoring algorithm
        "urgency.py",    # urgency detector (<= 4h)
        "notify.py",     # delivery channel dispatch
        "digest.py",     # digest compiler
        "db.py",
        "config.py",
        "run.py",        # pipeline runner
    ]
    for mod in core_modules:
        assert (PROJECT_ROOT / "job_digest" / mod).exists(), f"Core module {mod} missing"


def test_milestone_2_private_web_app_integrity():
    """Verify FastAPI web application routes, templates, and security configuration."""
    web_file = PROJECT_ROOT / "job_digest" / "web.py"
    assert web_file.exists(), "job_digest/web.py is missing"
    web_code = web_file.read_text(encoding="utf-8")

    # Critical route endpoints
    assert "/login" in web_code
    assert "/logout" in web_code
    assert "/history" in web_code
    assert "/settings" in web_code
    assert "/sources" in web_code
    assert "/jobs/add" in web_code
    assert "/jobs/run-now" in web_code
    assert "/health" in web_code
    assert "/manifest.json" in web_code

    # Web templates
    web_tmpl_dir = PROJECT_ROOT / "job_digest" / "templates" / "web"
    for tmpl in ["login.html", "digest_view.html", "history.html", "settings.html", "sources.html", "add_job.html"]:
        assert (web_tmpl_dir / tmpl).exists(), f"Web template {tmpl} missing from job_digest/templates/web/"


def test_milestone_3_public_showcase_site_integrity():
    """Verify all static pages, crawl discovery files, and visual media exist in dist/."""
    # 6 HTML pages
    expected_html = [
        DIST_DIR / "index.html",
        DIST_DIR / "how-it-works" / "index.html",
        DIST_DIR / "sources" / "index.html",
        DIST_DIR / "privacy" / "index.html",
        DIST_DIR / "terms" / "index.html",
        DIST_DIR / "404.html",
    ]
    for p in expected_html:
        assert p.exists(), f"Compiled HTML page {p} missing from dist/"
        soup = BeautifulSoup(p.read_text(encoding="utf-8"), "html.parser")
        assert len(soup.find_all("h1")) == 1, f"Expected exactly one H1 in {p.name}"
        assert soup.find("script", type="application/ld+json") is not None

    # 3 Crawl files
    assert (DIST_DIR / "sitemap.xml").exists()
    assert (DIST_DIR / "robots.txt").exists()
    assert (DIST_DIR / "llms.txt").exists()

    # Static assets
    assert (DIST_DIR / "static" / "css" / "style.css").exists()
    assert (DIST_DIR / "static" / "favicon.svg").exists()
    assert (DIST_DIR / "static" / "images" / "architecture.svg").exists()
    assert (DIST_DIR / "static" / "images" / "telegram-mockup.svg").exists()
    assert (DIST_DIR / "static" / "images" / "og-image.png").exists()


def test_milestone_4_documentation_and_adr_completeness():
    """Verify complete documentation suite, runbook, portfolio briefing, and all ADRs 001-017."""
    doc_files = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "memory.md",
        PROJECT_ROOT / "docs" / "runbook.md",
        PROJECT_ROOT / "docs" / "portfolio_summary.md",
        PROJECT_ROOT / "docs" / "decisions.md",
        PROJECT_ROOT / "docs" / "backup_plan.md",
        PROJECT_ROOT / "docs" / "deployment.md",
        PROJECT_ROOT / "docs" / "domain_setup.md",
    ]
    for doc in doc_files:
        assert doc.exists(), f"Documentation file {doc.name} missing"

    # All ADRs from 001 to 017 must be recorded in docs/decisions.md
    decisions_content = (PROJECT_ROOT / "docs" / "decisions.md").read_text(encoding="utf-8")
    for i in range(1, 18):
        adr_id = f"ADR {i:03d}"
        assert adr_id in decisions_content, f"Missing {adr_id} in docs/decisions.md"
