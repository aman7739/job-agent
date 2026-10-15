"""Session 20 Tests: Crawl Files (sitemap.xml, robots.txt, llms.txt), 404 Routing, and GitHub Pages Deployment.

Asserts:
1. Valid sitemap.xml adhering to Sitemaps 0.9 protocol listing all indexable pages and excluding 404.
2. Compliant robots.txt allowing indexing of showcase pages and referencing the sitemap.
3. Structured llms.txt discovery document providing AI search crawler documentation.
4. Custom 404 page with single H1, recovery navigation links, and valid metadata.
5. GitHub Pages workflow (.github/workflows/pages.yml) with valid YAML syntax and deployment actions.
6. Custom domain and HTTPS documentation in docs/domain_setup.md.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml
from bs4 import BeautifulSoup
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
SITE_DIR = PROJECT_ROOT / "site"


@pytest.fixture(scope="module", autouse=True)
def build_showcase_site():
    """Ensure showcase site is built before asserting file artifacts."""
    build_script = SITE_DIR / "build.py"
    spec = importlib.util.spec_from_file_location("site_build", build_script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = module.build_site(dist_dir=DIST_DIR)
    return files


def test_sitemap_xml_structure_and_validity():
    """Verify sitemap.xml exists, is valid XML, lists all canonical pages, and excludes 404."""
    sitemap_file = DIST_DIR / "sitemap.xml"
    assert sitemap_file.exists(), "sitemap.xml was not generated in dist/"

    tree = ET.parse(sitemap_file)
    root = tree.getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    assert "urlset" in root.tag

    urls = root.findall("sm:url", ns)
    assert len(urls) == 5, f"Expected 5 indexed URLs, found {len(urls)}"

    locs = [u.find("sm:loc", ns).text for u in urls if u.find("sm:loc", ns) is not None]
    assert any(loc.endswith("/") and not any(part in loc for part in ["how-it-works", "sources", "privacy", "terms"]) for loc in locs), "Home URL missing from sitemap"
    assert any("/how-it-works/" in loc for loc in locs)
    assert any("/sources/" in loc for loc in locs)
    assert any("/privacy/" in loc for loc in locs)
    assert any("/terms/" in loc for loc in locs)

    # 404 error page must never be in sitemap
    assert not any("404" in loc for loc in locs), "404 page mistakenly included in sitemap.xml"

    # Validate elements for each URL
    for url in urls:
        loc = url.find("sm:loc", ns)
        lastmod = url.find("sm:lastmod", ns)
        changefreq = url.find("sm:changefreq", ns)
        priority = url.find("sm:priority", ns)

        assert loc is not None and loc.text.startswith("http")
        assert lastmod is not None and len(lastmod.text) == 10  # YYYY-MM-DD
        assert changefreq is not None and changefreq.text in ["daily", "weekly", "monthly", "yearly"]
        assert priority is not None
        prio_val = float(priority.text)
        assert 0.0 <= prio_val <= 1.0


def test_robots_txt_crawl_policy():
    """Verify robots.txt exists, allows public crawling, disallows 404, and points to sitemap."""
    robots_file = DIST_DIR / "robots.txt"
    assert robots_file.exists(), "robots.txt was not generated in dist/"

    content = robots_file.read_text(encoding="utf-8")
    assert "User-agent: *" in content
    assert "Allow: /" in content
    assert "Disallow: /404.html" in content
    assert "Sitemap:" in content and "sitemap.xml" in content


def test_llms_txt_structure():
    """Verify llms.txt follows convention and provides structured context for AI crawlers."""
    llms_file = DIST_DIR / "llms.txt"
    assert llms_file.exists(), "llms.txt was not generated in dist/"

    content = llms_file.read_text(encoding="utf-8")
    assert content.startswith("# Job Digest Agent")
    assert "> Autonomous Career Intelligence Pipeline" in content
    assert "[Overview]" in content
    assert "[How It Works]" in content
    assert "[Permitted Sources]" in content
    assert "[Privacy Policy]" in content
    assert "[Terms of Use]" in content
    assert "Batch 2027" in content
    assert "08:00 AM" in content
    assert "07:00 PM" in content


def test_404_error_page_features():
    """Verify 404 page exists, has exactly one H1, unique metadata, and recovery navigation."""
    page_404 = DIST_DIR / "404.html"
    assert page_404.exists(), "404.html was not generated in dist/"

    soup = BeautifulSoup(page_404.read_text(encoding="utf-8"), "html.parser")
    h1s = soup.find_all("h1")
    assert len(h1s) == 1
    assert "Page Not Found" in h1s[0].text

    links = [a.get("href") for a in soup.find_all("a")]
    assert "/" in links
    assert "/how-it-works/" in links
    assert "/sources/" in links

    title = soup.find("title")
    assert title and "Page Not Found" in title.text


def test_github_pages_workflow_and_domain_docs():
    """Verify pages.yml is valid YAML with proper permissions and domain_setup.md exists."""
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "pages.yml"
    assert workflow_path.exists(), "pages.yml is missing"

    raw_yaml = workflow_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw_yaml)

    # Trigger key must be parsed as mapping/dict, not boolean
    assert "on" in parsed or True in parsed
    triggers = parsed.get("on") if "on" in parsed else parsed.get(True)
    assert isinstance(triggers, dict), "The trigger key in pages.yml must be quoted (\"on\":)"

    # Verify required deployment permissions
    permissions = parsed.get("permissions", {})
    assert permissions.get("pages") == "write"
    assert permissions.get("id-token") == "write"

    # Verify domain documentation
    domain_doc = PROJECT_ROOT / "docs" / "domain_setup.md"
    assert domain_doc.exists(), "docs/domain_setup.md is missing"
    doc_text = domain_doc.read_text(encoding="utf-8")
    assert "185.199.108.153" in doc_text
    assert "Enforce HTTPS" in doc_text
