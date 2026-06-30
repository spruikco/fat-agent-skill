#!/usr/bin/env python3
"""Tests for the Technical SEO depth module."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules import technical_seo as ts
from modules.technical_seo import TechnicalSEOModule


class TestCanonicalHost(unittest.TestCase):
    def test_www_vs_non_www_is_expected_consolidation(self):
        # auditing the apex while the page canonicalises to www is CORRECT, not a finding
        html = '<link rel="canonical" href="https://www.x.example/p">'
        self.assertIsNone(ts.canonical_host_issue(html, "https://x.example/p"))

    def test_http_to_https_is_expected(self):
        # auditing http:// while the page canonicalises to https is CORRECT
        html = '<link rel="canonical" href="https://x.example/p">'
        self.assertIsNone(ts.canonical_host_issue(html, "http://x.example/p"))

    def test_www_prefix_strip_does_not_mangle_hosts(self):
        # regression for the lstrip("www.") footgun — w-leading hosts aren't www variants
        html = '<link rel="canonical" href="https://west.example/p">'
        self.assertIn(
            "different host", ts.canonical_host_issue(html, "https://east.example/p")
        )

    def test_foreign_host(self):
        html = '<link rel="canonical" href="https://other.example/p">'
        self.assertIn(
            "different host", ts.canonical_host_issue(html, "https://x.example/p")
        )

    def test_same_host_ok(self):
        html = '<link rel="canonical" href="https://x.example/p">'
        self.assertIsNone(ts.canonical_host_issue(html, "https://x.example/p"))

    def test_relative_canonical_ok(self):
        html = '<link rel="canonical" href="/p">'
        self.assertIsNone(ts.canonical_host_issue(html, "https://x.example/p"))


class TestImages(unittest.TestCase):
    def test_legacy_without_nextgen(self):
        html = '<img src="/a.jpg"><img src="/b.png" width="10" height="10">'
        s = ts.image_signals(html)
        self.assertEqual(s["legacy"], 2)
        self.assertEqual(s["next_gen"], 0)

    def test_missing_dims(self):
        html = '<img src="/a.webp"><img src="/b.webp" width="1" height="1">'
        s = ts.image_signals(html)
        self.assertEqual(s["missing_dims"], 1)
        self.assertEqual(s["next_gen"], 2)

    def test_picture_nextgen(self):
        html = '<picture><source type="image/avif" srcset="a.avif"><img src="a.jpg"></picture>'
        self.assertTrue(ts.image_signals(html)["has_picture_nextgen"])


class TestModule(unittest.TestCase):
    def test_x_robots_header_noindex(self):
        a = TechnicalSEOModule().analyse(
            "<html></html>",
            "https://x.example/",
            headers={"X-Robots-Tag": "noindex, nofollow"},
        )
        self.assertTrue(a["x_robots_noindex"])

    def test_header_lookup_case_insensitive(self):
        a = TechnicalSEOModule().analyse(
            "<html></html>", "https://x.example/", headers={"x-robots-tag": "noindex"}
        )
        self.assertTrue(a["x_robots_noindex"])

    def test_noindex_header_finding_p0(self):
        m = TechnicalSEOModule()
        m.score(
            m.analyse(
                "<html></html>",
                "https://x.example/",
                headers={"X-Robots-Tag": "noindex"},
            )
        )
        f = next(f for f in m.findings if "X-Robots-Tag" in f["title"])
        self.assertEqual(f["priority"], "P0")

    def test_meta_refresh_finding(self):
        m = TechnicalSEOModule()
        m.score(
            m.analyse(
                '<meta http-equiv="refresh" content="0;url=/x">', "https://x.example/"
            )
        )
        self.assertTrue(any("Meta-refresh" in f["title"] for f in m.findings))

    def test_clean_page_high_score(self):
        html = '<link rel="canonical" href="https://x.example/p"><img src="/a.webp" width="1" height="1">'
        m = TechnicalSEOModule()
        s = m.score(m.analyse(html, "https://x.example/p", headers={}))
        self.assertGreaterEqual(s["total"], 85)


if __name__ == "__main__":
    unittest.main()
