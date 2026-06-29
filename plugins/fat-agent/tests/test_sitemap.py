import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.sitemap import SitemapModule

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

VALID_SITEMAP = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>https://example.com/</loc><lastmod>2025-01-15</lastmod></url>"
    "<url><loc>https://example.com/about</loc><lastmod>2025-01-10</lastmod></url>"
    "<url><loc>https://example.com/contact</loc></url>"
    "</urlset>"
)

SITEMAP_INDEX = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<sitemap><loc>https://example.com/sitemap-posts.xml</loc>"
    "<lastmod>2025-02-01</lastmod></sitemap>"
    "<sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>"
    "</sitemapindex>"
)

EMPTY_SITEMAP = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
)

INVALID_XML = "<urlset><url><loc>not closed"

DUPLICATE_SITEMAP = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>https://example.com/page1</loc></url>"
    "<url><loc>https://example.com/page1</loc></url>"
    "<url><loc>https://example.com/page2</loc></url>"
    "</urlset>"
)

CROSS_DOMAIN_SITEMAP = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>https://example.com/</loc></url>"
    "<url><loc>https://other-domain.com/sneaky</loc></url>"
    "</urlset>"
)

ROBOTS_WITH = "User-agent: *\nSitemap: https://example.com/sitemap.xml\n"
ROBOTS_WITHOUT = "User-agent: *\nDisallow: /admin/\n"


def _perfect_analysis():
    return {
        "sitemap_exists": True,
        "valid_xml": True,
        "has_urls": True,
        "url_count": 50,
        "unique_url_count": 50,
        "urls_match_domain": True,
        "mismatched_urls": [],
        "has_lastmod": True,
        "lastmod_count": 50,
        "has_duplicates": False,
        "duplicate_count": 0,
        "reasonable_size": True,
        "referenced_in_robots": True,
    }


def _empty_analysis():
    return {
        "sitemap_exists": False,
        "valid_xml": False,
        "has_urls": False,
        "url_count": 0,
        "unique_url_count": 0,
        "urls_match_domain": True,
        "mismatched_urls": [],
        "has_lastmod": False,
        "has_duplicates": False,
        "reasonable_size": True,
        "referenced_in_robots": False,
    }


# --- detection ---


def test_detect_always_true():
    assert SitemapModule.detect("") is True
    assert SitemapModule.detect("<html></html>") is True


def test_module_metadata():
    assert SitemapModule.MODULE_ID == "sitemap"
    assert SitemapModule.DISPLAY_NAME == "Sitemap Analysis"
    assert SitemapModule.ALWAYS_ENABLED is True


# --- analyse: valid sitemap ---


def test_analyse_valid_sitemap():
    mod = SitemapModule()
    r = mod.analyse(
        html="",
        url="https://example.com/",
        sitemap_xml=VALID_SITEMAP,
        robots_txt=ROBOTS_WITH,
    )
    assert r["sitemap_exists"] is True
    assert r["valid_xml"] is True
    assert r["url_count"] == 3
    assert r["has_lastmod"] is True
    assert r["lastmod_count"] == 2
    assert r["has_duplicates"] is False
    assert r["referenced_in_robots"] is True
    assert r["is_index"] is False


def test_analyse_fixture_file():
    with open(os.path.join(FIXTURES_DIR, "sitemap_mock.xml")) as f:
        xml_content = f.read()
    mod = SitemapModule()
    r = mod.analyse(
        html="",
        url="https://example.com/",
        sitemap_xml=xml_content,
        robots_txt=ROBOTS_WITH,
    )
    assert r["valid_xml"] is True
    assert r["url_count"] == 3


# --- analyse: sitemap index ---


def test_analyse_sitemap_index():
    mod = SitemapModule()
    r = mod.analyse(
        html="",
        url="https://example.com/",
        sitemap_xml=SITEMAP_INDEX,
        robots_txt=ROBOTS_WITHOUT,
    )
    assert r["is_index"] is True
    assert r["url_count"] == 2
    assert r["lastmod_count"] == 1
    assert r["referenced_in_robots"] is False


# --- analyse: empty sitemap ---


def test_analyse_empty_sitemap():
    mod = SitemapModule()
    r = mod.analyse(
        html="",
        url="https://example.com/",
        sitemap_xml=EMPTY_SITEMAP,
        robots_txt=ROBOTS_WITHOUT,
    )
    assert r["valid_xml"] is True
    assert r["has_urls"] is False


# --- analyse: invalid XML ---


def test_analyse_invalid_xml():
    mod = SitemapModule()
    r = mod.analyse(
        html="",
        url="https://example.com/",
        sitemap_xml=INVALID_XML,
        robots_txt=ROBOTS_WITHOUT,
    )
    assert r["sitemap_exists"] is True
    assert r["valid_xml"] is False


# --- analyse: duplicates ---


def test_analyse_duplicate_urls():
    mod = SitemapModule()
    r = mod.analyse(
        html="",
        url="https://example.com/",
        sitemap_xml=DUPLICATE_SITEMAP,
        robots_txt=ROBOTS_WITHOUT,
    )
    assert r["has_duplicates"] is True
    assert r["duplicate_count"] == 1
    assert r["unique_url_count"] == 2


# --- analyse: cross-domain ---


def test_analyse_cross_domain_urls():
    mod = SitemapModule()
    r = mod.analyse(
        html="",
        url="https://example.com/",
        sitemap_xml=CROSS_DOMAIN_SITEMAP,
        robots_txt=ROBOTS_WITHOUT,
    )
    assert r["urls_match_domain"] is False
    assert "other-domain.com" in r["mismatched_urls"][0]


# --- analyse: no input ---


def test_analyse_no_sitemap_no_url():
    mod = SitemapModule()
    r = mod.analyse(html="", url="", robots_txt="")
    assert r["sitemap_exists"] is False


# --- scoring ---


def test_score_perfect():
    mod = SitemapModule()
    r = mod.score(_perfect_analysis())
    assert r["total"] == 100


def test_score_no_sitemap():
    mod = SitemapModule()
    r = mod.score(_empty_analysis())
    assert r["sitemap_exists"] == 0
    # urls_match_domain(10) + no_duplicates(10) + reasonable_size(5)
    assert r["total"] == 25


def test_score_breakdown():
    mod = SitemapModule()
    r = mod.score(_perfect_analysis())
    assert r["sitemap_exists"] == 25
    assert r["valid_xml"] == 15
    assert r["has_urls"] == 15
    assert r["urls_match_domain"] == 10
    assert r["has_lastmod"] == 10
    assert r["referenced_in_robots"] == 10
    assert r["no_duplicates"] == 10
    assert r["reasonable_size"] == 5


# --- findings ---


def test_finding_no_sitemap():
    mod = SitemapModule()
    mod.score(_empty_analysis())
    assert any("sitemap" in f["title"].lower() for f in mod.findings)


def test_finding_invalid_xml():
    a = _perfect_analysis()
    a["valid_xml"] = False
    mod = SitemapModule()
    mod.score(a)
    assert any("invalid xml" in f["title"].lower() for f in mod.findings)


def test_finding_duplicates():
    a = _perfect_analysis()
    a["has_duplicates"] = True
    a["duplicate_count"] = 3
    mod = SitemapModule()
    mod.score(a)
    assert any("duplicate" in f["title"].lower() for f in mod.findings)


def test_finding_missing_lastmod():
    a = _perfect_analysis()
    a["has_lastmod"] = False
    mod = SitemapModule()
    mod.score(a)
    assert any("lastmod" in f["title"].lower() for f in mod.findings)


def test_finding_not_in_robots():
    a = _perfect_analysis()
    a["referenced_in_robots"] = False
    mod = SitemapModule()
    mod.score(a)
    assert any("robots" in f["title"].lower() for f in mod.findings)


# --- robots.txt helper ---


def test_sitemaps_from_robots():
    assert SitemapModule._sitemaps_from_robots(ROBOTS_WITH) == [
        "https://example.com/sitemap.xml"
    ]


def test_sitemaps_from_robots_empty():
    assert SitemapModule._sitemaps_from_robots(ROBOTS_WITHOUT) == []
