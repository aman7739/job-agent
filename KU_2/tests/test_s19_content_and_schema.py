"""Session 19 Tests: Real Content, Structured Data (JSON-LD), and Visual Asset Compliance.

Asserts:
1. Valid Schema.org JSON-LD structured data on all pages (SoftwareApplication, WebSite, BreadcrumbList).
2. Complete OpenGraph and Twitter card metadata, including 1200x630 social share card verification.
3. Accessible visual assets (architecture.svg, telegram-mockup.svg) with non-empty, descriptive alt text.
4. Content audit confirming zero placeholder text (lorem, TODO, placeholder, etc.) across the compiled site.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from bs4 import BeautifulSoup
from PIL import Image
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
SITE_DIR = PROJECT_ROOT / "site"


@pytest.fixture(scope="module", autouse=True)
def build_showcase_site():
    """Build the showcase site before executing test assertions."""
    build_script = SITE_DIR / "build.py"
    spec = importlib.util.spec_from_file_location("site_build", build_script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = module.build_site(dist_dir=DIST_DIR)
    assert len(files) >= 6
    return files


def test_schema_org_json_ld_validity_and_entities():
    """Verify all pages contain valid Schema.org JSON-LD with required entity types."""
    html_files = list(DIST_DIR.rglob("*.html"))
    assert len(html_files) >= 6

    for html_file in html_files:
        soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
        scripts = soup.find_all("script", type="application/ld+json")
        assert len(scripts) >= 1, f"Missing JSON-LD script block in {html_file.name}"

        for script in scripts:
            data = json.loads(script.string)
            assert data.get("@context") == "https://schema.org"
            assert "@graph" in data
            graph = data["@graph"]

            types = {item.get("@type") for item in graph}
            # Every page must have WebSite and SoftwareApplication
            assert "WebSite" in types, f"Missing WebSite schema in {html_file.name}"
            assert "SoftwareApplication" in types, f"Missing SoftwareApplication schema in {html_file.name}"

            # Validate SoftwareApplication properties
            app_entity = next(item for item in graph if item.get("@type") == "SoftwareApplication")
            assert app_entity.get("name") == "Job Digest Agent"
            assert app_entity.get("applicationCategory") == "BusinessApplication"
            assert app_entity.get("operatingSystem") == "Linux, Cloud"
            assert app_entity.get("softwareVersion") == "1.0.0"
            assert "description" in app_entity and len(app_entity["description"]) > 20
            assert "offers" in app_entity
            assert app_entity["offers"].get("price") == "0"
            assert "author" in app_entity
            assert app_entity["author"].get("name") == "KRAMA"

            # Validate BreadcrumbList on subpages
            if html_file.parent != DIST_DIR and html_file.name == "index.html":
                assert "BreadcrumbList" in types, f"Missing BreadcrumbList schema in {html_file.parent.name}/index.html"
                crumb_entity = next(item for item in graph if item.get("@type") == "BreadcrumbList")
                items = crumb_entity.get("itemListElement", [])
                assert len(items) >= 2
                assert items[0].get("position") == 1
                assert items[0].get("name") == "Home"
                assert items[1].get("position") == 2
                assert len(items[1].get("name", "")) > 0


def test_social_sharing_open_graph_and_twitter_cards():
    """Verify OpenGraph and Twitter card metadata and 1200x630 image dimensions."""
    html_files = list(DIST_DIR.rglob("*.html"))
    og_image_path = DIST_DIR / "static" / "images" / "og-image.png"

    # 1. Assert social card image file exists and is valid 1200x630 PNG
    assert og_image_path.exists(), "Social preview image og-image.png does not exist in dist/"
    with Image.open(og_image_path) as img:
        assert img.size == (1200, 630), f"Expected 1200x630 dimensions, got {img.size}"
        assert img.format == "PNG", f"Expected PNG format, got {img.format}"

    # 2. Check meta tags in every compiled page
    for html_file in html_files:
        soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")

        # OpenGraph tags
        assert soup.find("meta", property="og:type"), f"Missing og:type in {html_file.name}"
        assert soup.find("meta", property="og:site_name"), f"Missing og:site_name in {html_file.name}"
        assert soup.find("meta", property="og:url"), f"Missing og:url in {html_file.name}"
        assert soup.find("meta", property="og:title"), f"Missing og:title in {html_file.name}"
        assert soup.find("meta", property="og:description"), f"Missing og:description in {html_file.name}"
        
        og_img = soup.find("meta", property="og:image")
        assert og_img is not None, f"Missing og:image in {html_file.name}"
        assert "og-image.png" in og_img.get("content", "")

        # Twitter Card tags
        assert soup.find("meta", attrs={"name": "twitter:card"}), f"Missing twitter:card in {html_file.name}"
        assert soup.find("meta", attrs={"name": "twitter:title"}), f"Missing twitter:title in {html_file.name}"
        assert soup.find("meta", attrs={"name": "twitter:description"}), f"Missing twitter:description in {html_file.name}"
        assert soup.find("meta", attrs={"name": "twitter:image"}), f"Missing twitter:image in {html_file.name}"


def test_visual_assets_and_alt_text_compliance():
    """Verify architecture diagram and Telegram mockup exist and have descriptive alt text."""
    arch_path = DIST_DIR / "static" / "images" / "architecture.svg"
    tg_path = DIST_DIR / "static" / "images" / "telegram-mockup.svg"

    assert arch_path.exists(), "architecture.svg missing from dist/"
    arch_content = arch_path.read_text(encoding="utf-8")
    assert "<svg" in arch_content and "viewBox" in arch_content
    assert "<title" in arch_content and "</title>" in arch_content
    assert "<desc" in arch_content and "</desc>" in arch_content

    assert tg_path.exists(), "telegram-mockup.svg missing from dist/"
    tg_content = tg_path.read_text(encoding="utf-8")
    assert "<svg" in tg_content and "viewBox" in tg_content
    assert "<title" in tg_content and "</title>" in tg_content
    assert "<desc" in tg_content and "</desc>" in tg_content

    # Every <img> element across all pages must have a non-empty, descriptive alt attribute
    html_files = list(DIST_DIR.rglob("*.html"))
    total_imgs = 0
    for html_file in html_files:
        soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
        imgs = soup.find_all("img")
        for img in imgs:
            total_imgs += 1
            alt = img.get("alt", "").strip()
            assert alt, f"Image {img.get('src')} missing alt text in {html_file.name}"
            assert len(alt) >= 15, f"Alt text '{alt}' is too short/generic in {html_file.name}"

    assert total_imgs >= 3, f"Expected at least 3 embedded images across site, found {total_imgs}"


def test_content_audit_zero_placeholders_and_authentic_copy():
    """Grep audit asserting zero placeholder text and confirming authentic domain copy."""
    banned_tokens = [
        "lorem",
        "ipsum",
        "todo",
        "fixme",
        "placeholder",
        "replace me",
        "sample text",
        "under construction",
    ]

    html_files = list(DIST_DIR.rglob("*.html"))
    for html_file in html_files:
        content = html_file.read_text(encoding="utf-8").lower()
        for token in banned_tokens:
            assert token not in content, f"Found banned placeholder token '{token}' in {html_file}"

    # Verify key authentic project concepts in home & documentation
    index_content = (DIST_DIR / "index.html").read_text(encoding="utf-8")
    assert "2027" in index_content
    assert "Internships" in index_content
    assert "Full-Time" in index_content
    assert "Telegram" in index_content
    assert "Email" in index_content
    assert "08:00 AM" in index_content
    assert "07:00 PM" in index_content

    # Privacy and Terms must explicitly confirm no private user profile data is shown on the public site
    privacy_content = (DIST_DIR / "privacy" / "index.html").read_text(encoding="utf-8")
    assert "never exposes" in privacy_content.lower() or "isolated" in privacy_content.lower()
