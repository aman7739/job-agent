"""Tests for Session 18: Static site foundation, Jinja2 builder, and semantic SEO validation."""

import importlib.util
from pathlib import Path
import pytest
from bs4 import BeautifulSoup

BUILD_PATH = Path(__file__).resolve().parent.parent / "site" / "build.py"
spec = importlib.util.spec_from_file_location("site_build_module", BUILD_PATH)
site_build_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_build_module)

build_site = site_build_module.build_site
PAGES_CONFIG = site_build_module.PAGES_CONFIG


@pytest.fixture(scope="module")
def built_site(tmp_path_factory):
    """Build the public showcase site once into a test directory."""
    temp_dist = tmp_path_factory.mktemp("dist")
    generated_files = build_site(dist_dir=temp_dist, base_url="https://jobdigest.agent")
    return temp_dist, generated_files


def test_build_produces_all_expected_pages(built_site):
    """Verify build_site outputs all expected pages and assets."""
    temp_dist, generated_files = built_site

    expected_rel_paths = [
        "index.html",
        "how-it-works/index.html",
        "sources/index.html",
        "privacy/index.html",
        "terms/index.html",
        "404.html",
    ]

    for rel in expected_rel_paths:
        target = temp_dist / rel
        assert target.exists(), f"Expected generated page missing: {rel}"
        assert target.stat().st_size > 0, f"Generated page is empty: {rel}"

    # Verify static assets copied
    assert (temp_dist / "static" / "css" / "style.css").exists()
    assert (temp_dist / "static" / "favicon.svg").exists()


# ==============================================================================
# Session 18 Check Line Verification:
# "A build test asserts every page has one H1, a unique title, a description and a canonical."
# ==============================================================================

def test_semantic_seo_h1_unique_title_description_canonical(built_site):
    """
    Session 18 Check:
    Asserts every page has:
    1. Exactly one <h1> tag.
    2. A non-empty, unique <title>.
    3. A non-empty, unique <meta name='description'>.
    4. A valid canonical <link rel='canonical'>.
    """
    temp_dist, _ = built_site

    titles_seen = set()
    descriptions_seen = set()
    canonicals_seen = set()

    for cfg in PAGES_CONFIG:
        page_file = temp_dist / cfg["output_path"]
        assert page_file.exists()

        content = page_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(content, "html.parser")

        # 1. Exactly one H1
        h1_tags = soup.find_all("h1")
        assert len(h1_tags) == 1, f"{cfg['output_path']} must have exactly one <h1>, found {len(h1_tags)}"
        h1_text = h1_tags[0].get_text(strip=True)
        assert len(h1_text) > 3, f"{cfg['output_path']} <h1> text cannot be empty"

        # 2. Unique Title
        title_tag = soup.find("title")
        assert title_tag is not None, f"{cfg['output_path']} missing <title>"
        title_text = title_tag.get_text(strip=True)
        assert len(title_text) > 5, f"{cfg['output_path']} <title> too short"
        assert title_text not in titles_seen, f"Duplicate title detected: '{title_text}'"
        titles_seen.add(title_text)

        # 3. Unique Meta Description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        assert meta_desc is not None, f"{cfg['output_path']} missing <meta name='description'>"
        desc_content = meta_desc.get("content", "").strip()
        assert len(desc_content) >= 20, f"{cfg['output_path']} meta description too short: {desc_content}"
        assert desc_content not in descriptions_seen, f"Duplicate meta description detected: '{desc_content}'"
        descriptions_seen.add(desc_content)

        # 4. Canonical URL
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        assert canonical_tag is not None, f"{cfg['output_path']} missing canonical link"
        canonical_href = canonical_tag.get("href", "").strip()
        assert canonical_href.startswith("https://jobdigest.agent"), f"Invalid canonical URL: {canonical_href}"
        assert canonical_href not in canonicals_seen, f"Duplicate canonical URL detected: '{canonical_href}'"
        canonicals_seen.add(canonical_href)


def test_internal_navigation_and_breadcrumbs(built_site):
    """Verify internal links resolve and breadcrumbs are structured on sub-pages."""
    temp_dist, _ = built_site

    # Check that breadcrumbs appear on how-it-works
    hiw_file = temp_dist / "how-it-works" / "index.html"
    soup = BeautifulSoup(hiw_file.read_text(encoding="utf-8"), "html.parser")
    breadcrumb_nav = soup.find("nav", attrs={"class": "breadcrumbs"})
    assert breadcrumb_nav is not None
    assert "Home" in breadcrumb_nav.get_text()
    assert "How It Works" in breadcrumb_nav.get_text()

    # Check favicon link
    favicon_link = soup.find("link", attrs={"rel": "icon"})
    assert favicon_link is not None
    assert favicon_link.get("href") == "/static/favicon.svg"
