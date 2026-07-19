"""Tests for link_opportunities.py, brandkit.py, editorial_report.py."""

import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from brandkit import extract_fonts, extract_palette, find_images
from editorial_report import collect_findings, render
from link_opportunities import (
    CONTENT_DEFAULT,
    MONEY_DEFAULT,
    analyse,
    as_findings,
    best_money_target,
)
from sitecrawl import SCHEMA

MONEY_RE = re.compile(MONEY_DEFAULT, re.IGNORECASE)
CONTENT_RE = re.compile(CONTENT_DEFAULT, re.IGNORECASE)


def _db():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    return con


def _page(con, url):
    con.execute(
        "INSERT INTO pages (url, status, content_type, indexable) VALUES (?,200,'text/html',1)",
        (url,),
    )


def _link(con, source, target):
    con.execute(
        "INSERT INTO links VALUES (?,?,?,?,?)", (source, target, "a", "", "internal")
    )


class TestLinkOpportunities:
    def test_gap_detected_and_linked_page_excluded(self):
        con = _db()
        _page(con, "https://e.com/services/pest-control/")
        _page(con, "https://e.com/blog/ants-guide/")  # no money link -> gap
        _page(con, "https://e.com/blog/spiders-guide/")  # links money -> fine
        _link(
            con,
            "https://e.com/blog/spiders-guide/",
            "https://e.com/services/pest-control/",
        )
        result = analyse(con, MONEY_RE, CONTENT_RE)
        assert result["money_pages"] == 1
        assert result["content_pages"] == 2
        gaps = [g["url"] for g in result["gaps"]]
        assert gaps == ["https://e.com/blog/ants-guide/"]

    def test_gsc_ranks_and_suggests_target(self):
        con = _db()
        _page(con, "https://e.com/services/termite-inspection/")
        _page(con, "https://e.com/services/rodent-control/")
        _page(con, "https://e.com/blog/termite-signs/")
        gsc = {
            "https://e.com/blog/termite-signs/": [
                ("termite inspection cost", 900, 11.0)
            ]
        }
        result = analyse(con, MONEY_RE, CONTENT_RE, gsc)
        gap = result["gaps"][0]
        assert gap["impressions"] == 900
        assert gap["suggested_target"] == "https://e.com/services/termite-inspection/"

    def test_best_money_target_term_overlap(self):
        target = best_money_target(
            [("hire seo agency", 100, 5.0)],
            ["https://e.com/services/seo-agency/", "https://e.com/services/plumbing/"],
        )
        assert target == "https://e.com/services/seo-agency/"

    def test_findings_shape_and_cap(self):
        con = _db()
        _page(con, "https://e.com/services/x/")
        for i in range(20):
            _page(con, f"https://e.com/blog/post-{i}/")
        result = analyse(con, MONEY_RE, CONTENT_RE)
        findings = as_findings(result)
        assert len(findings) == 16  # 15 capped + 1 summary
        assert all(f["module"] == "link_opportunities" for f in findings)
        assert findings[0]["title"].startswith("Money-page link gap: /blog/")
        assert "5 more content pages" in findings[-1]["description"]


class TestBrandkit:
    def test_palette_prefers_saturated_accent(self):
        css = (
            ".a{color:#ffffff}.b{color:#ffffff}.c{background:#e63946}.d{color:#000000}"
        )
        colors = extract_palette(css)
        assert colors["accent"] == "#e63946"
        assert "#ffffff" in colors["palette"]

    def test_fonts_google_link_and_family(self):
        html = '<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;700" rel="stylesheet">'
        css = "body{font-family:'Sora', sans-serif} h1{font-family:Arial}"
        fonts = extract_fonts(html, css)
        assert "Sora" in fonts["google_fonts_url"]
        assert fonts["primary"] == "Sora"
        assert "Arial" not in fonts["families"]

    def test_images_logo_og_and_dedupe(self):
        html = (
            '<meta property="og:image" content="/og.jpg">'
            '<img src="/img/logo.svg" alt="Acme logo">'
            '<img src="/hero.jpg"><img src="/hero.jpg">'
        )
        images = find_images(html, "https://e.com/")
        assert images["logo"] == "https://e.com/img/logo.svg"
        assert images["heroes"][0] == "https://e.com/og.jpg"
        assert images["heroes"].count("https://e.com/hero.jpg") == 1


class TestEditorialReport:
    KIT = {
        "site_name": "Acme Pest Co",
        "colors": {"accent": "#e63946"},
        "fonts": {"primary": "Sora", "google_fonts_url": ""},
        "images": {"local": {"logo": "", "heroes": []}},
    }
    SCORES = {
        "overall": {"score": 72, "grade": "B"},
        "seo": {"score": 80},
        "security": {"score": 60, "assessed": True},
        "performance": {"score": 65},
        "accessibility": {"score": 85},
        "findings": [
            {"priority": "P2", "title": "Minor thing", "description": "d", "fix": "f"},
            {"priority": "P0", "title": "Broken thing", "description": "d", "fix": "f"},
        ],
    }

    def test_render_contains_brand_and_findings_sorted(self):
        html = render(self.SCORES, {}, self.KIT, "FAT Agent")
        assert "Acme Pest Co" in html
        assert "#e63946" in html
        assert "'Sora'" in html
        assert html.index("Broken thing") < html.index("Minor thing")
        assert ">B<" in html  # grade rendered

    def test_no_heroes_no_crash_and_print_ready(self):
        html = render(self.SCORES, {}, self.KIT, "FAT Agent")
        assert "@page" in html and "page-break-after" in html

    def test_collect_merges_sitewide(self):
        merged = collect_findings(
            self.SCORES, {"findings": [{"priority": "P1", "title": "Site thing"}]}
        )
        titles = [f["title"] for f in merged]
        assert titles[0] == "Broken thing"
        assert "Site thing" in titles

    def test_escapes_html_in_titles(self):
        scores = dict(self.SCORES)
        scores["findings"] = [
            {
                "priority": "P0",
                "title": "<script>x</script>",
                "description": "",
                "fix": "",
            }
        ]
        html = render(scores, {}, self.KIT, "FAT Agent")
        assert "<script>x</script>" not in html
        assert "&lt;script&gt;" in html
