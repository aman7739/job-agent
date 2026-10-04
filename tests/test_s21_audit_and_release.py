"""Session 21 Tests: Pre-Launch Audit, Anti-Slop Verification, and Release Baseline.

Asserts:
1. Zero .map source-map files ship in production dist/.
2. Asset bundle sizes conform to strict limits (JS <= 5KB, CSS <= 50KB).
3. Anti-slop compliance: neutral palette, no purple gradients, no pill badges, no emoji as icons, no 'Made with AI' branding.
4. Comprehensive production README explaining architecture, setup, .env.example, and boundaries.
5. Full pre-launch audit checklist items verified green.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
from bs4 import BeautifulSoup
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
SITE_DIR = PROJECT_ROOT / "site"


@pytest.fixture(scope="module", autouse=True)
def ensure_built_showcase():
    """Ensure site is freshly built into dist/ before running audit assertions."""
    build_script = SITE_DIR / "build.py"
    spec = importlib.util.spec_from_file_location("site_build", build_script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = module.build_site(dist_dir=DIST_DIR)
    return files


def test_distribution_hygiene_no_map_files_and_small_bundles():
    """Verify zero .map files ship and bundle sizes remain tiny."""
    # 1. Zero .map files in dist/
    map_files = list(DIST_DIR.rglob("*.map"))
    assert len(map_files) == 0, f"Found source map files in dist/: {map_files}"

    # 2. JS bundle size <= 5KB (currently 0 bytes vanilla architecture)
    js_files = list(DIST_DIR.rglob("*.js"))
    total_js_bytes = sum(f.stat().st_size for f in js_files)
    assert total_js_bytes <= 5 * 1024, f"JS bundle size {total_js_bytes} bytes exceeds 5KB limit"

    # 3. CSS bundle size <= 50KB
    css_files = list(DIST_DIR.rglob("*.css"))
    assert len(css_files) >= 1
    total_css_bytes = sum(f.stat().st_size for f in css_files)
    assert total_css_bytes <= 50 * 1024, f"CSS bundle size {total_css_bytes} bytes exceeds 50KB limit"

    # 4. Favicon exists
    favicon = DIST_DIR / "static" / "favicon.svg"
    assert favicon.exists(), "Favicon missing from dist/static/"


def test_anti_slop_compliance():
    """Enforce strict anti-slop rules on design, typography, motion, and branding."""
    # 1. Palette: no purple gradients
    style_css = (DIST_DIR / "static" / "css" / "style.css").read_text(encoding="utf-8").lower()
    assert "rebeccapurple" not in style_css
    assert "linear-gradient" not in style_css or "purple" not in style_css
    assert "#8a2be2" not in style_css

    # 2. Badges: no pill-shaped badges (border-radius: 9999px)
    assert "border-radius: 9999px" not in style_css

    # 3. Motion: no scroll animations or cursor effects
    assert "@keyframes" not in style_css
    assert "cursor: url" not in style_css

    # 4. Branding & Icons: No emoji used as icons in templates
    html_files = list(DIST_DIR.rglob("*.html"))
    for html_file in html_files:
        soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
        # Ensure brand has SVG icon, not raw emoji
        brand = soup.find(class_="brand")
        if brand:
            assert brand.find("svg") is not None, f"Brand missing SVG icon in {html_file.name}"
            assert "🚀" not in brand.text, f"Emoji rocket found in brand in {html_file.name}"

        # Ensure footer has no 'Made with AI' branding and includes GitHub link
        footer = soup.find("footer")
        if footer:
            footer_text = footer.get_text().lower()
            assert "made with ai" not in footer_text, f"'Made with AI' found in footer in {html_file.name}"
            github_link = footer.find("a", href=re.compile("github", re.I))
            assert github_link is not None, f"Missing GitHub link in footer in {html_file.name}"


def test_readme_and_documentation_completeness():
    """Verify production README explains architecture, setup, .env.example, and boundaries."""
    readme_path = PROJECT_ROOT / "README.md"
    assert readme_path.exists(), "README.md is missing"
    content = readme_path.read_text(encoding="utf-8")
    assert len(content) > 2000, f"README.md is too brief ({len(content)} characters)"

    # Architecture & Core Features
    assert "8 Permitted Sources" in content
    assert "10-Point Scoring Algorithm" in content
    assert "08:00 AM" in content and "07:00 PM" in content
    assert "Internships" in content and "Full-Time" in content
    assert "Batch 2027" in content

    # Setup & Environment
    assert ".env.example" in content
    assert "pytest" in content
    assert "DATABASE_URL" in content
    assert "TELEGRAM_BOT_TOKEN" in content
    assert "DASHBOARD_PASSWORD_HASH" in content

    # Deployment & Operational Limitations
    assert "GitHub Actions" in content
    assert "Render" in content
    assert "GitHub Pages" in content
    assert "Operational Limitations" in content

    # Verify .env.example matches variables documented
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    for var in [
        "DATABASE_URL",
        "TELEGRAM_BOT_TOKEN",
        "SMTP_HOST",
        "IMAP_HOST",
        "ADZUNA_APP_ID",
        "DASHBOARD_PASSWORD_HASH",
        "SESSION_SECRET",
        "WEBHOOK_TOKEN",
    ]:
        assert var in env_example, f"Variable {var} missing from .env.example"


def test_pre_launch_audit_checklist_verified():
    """Audit check asserting that every pre-launch checklist requirement is satisfied."""
    # 1. Custom domain docs
    assert (PROJECT_ROOT / "docs" / "domain_setup.md").exists()

    # 2. Clean URL slugs
    for slug_dir in ["how-it-works", "sources", "privacy", "terms"]:
        index_file = DIST_DIR / slug_dir / "index.html"
        assert index_file.exists(), f"Missing clean directory slug for {slug_dir}"

    # 3. Custom 404
    assert (DIST_DIR / "404.html").exists()

    # 4. Crawl files
    assert (DIST_DIR / "sitemap.xml").exists()
    assert (DIST_DIR / "robots.txt").exists()
    assert (DIST_DIR / "llms.txt").exists()

    # 5. Media & Assets
    assert (DIST_DIR / "static" / "images" / "architecture.svg").exists()
    assert (DIST_DIR / "static" / "images" / "telegram-mockup.svg").exists()
    assert (DIST_DIR / "static" / "images" / "og-image.png").exists()

    # 6. Structured Data
    for html_file in DIST_DIR.rglob("*.html"):
        soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
        assert soup.find("script", type="application/ld+json") is not None
        assert soup.find("link", rel="canonical") is not None
        assert len(soup.find_all("h1")) == 1

    # 7. Deployment files
    assert (PROJECT_ROOT / ".github" / "workflows" / "pages.yml").exists()
    assert (PROJECT_ROOT / ".github" / "workflows" / "daily-digest.yml").exists()
    assert (PROJECT_ROOT / "Dockerfile").exists()
    assert (PROJECT_ROOT / "render.yaml").exists()
