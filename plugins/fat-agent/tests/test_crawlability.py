#!/usr/bin/env python3
"""Tests for the Crawlability & Indexation module."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules import crawlability as cr
from modules.crawlability import CrawlabilityModule

ROBOTS_BLOCK_ASSETS = "User-agent: *\nDisallow: /assets/\nDisallow: /static/js/\n"
HTML_ASSETS = (
    '<link rel="stylesheet" href="/assets/app.css">'
    '<script src="/static/js/app.js"></script>'
    '<script src="/ok/main.js"></script>'
)


class TestRobotsAssetBlocking(unittest.TestCase):
    def test_path_disallowed_prefix(self):
        rules = [("disallow", "/assets/")]
        self.assertTrue(cr.path_disallowed(rules, "/assets/app.css"))
        self.assertFalse(cr.path_disallowed(rules, "/ok/main.js"))

    def test_allow_overrides_longer(self):
        rules = [("disallow", "/a/"), ("allow", "/a/keep.js")]
        self.assertFalse(cr.path_disallowed(rules, "/a/keep.js"))
        self.assertTrue(cr.path_disallowed(rules, "/a/other.js"))

    def test_blocked_assets(self):
        paths = cr._asset_paths(HTML_ASSETS, "https://x.example")
        blocked = cr.blocked_assets(ROBOTS_BLOCK_ASSETS, paths)
        blocked_paths = {p for _, p in blocked}
        self.assertIn("/assets/app.css", blocked_paths)
        self.assertIn("/static/js/app.js", blocked_paths)
        self.assertNotIn("/ok/main.js", blocked_paths)


class TestSignals(unittest.TestCase):
    def test_faceted_links(self):
        html = '<a href="/p?sort=price">a</a><a href="/p?color=red">b</a><a href="/clean">c</a>'
        self.assertEqual(cr.faceted_links(html), 2)

    def test_js_only_nav(self):
        html = '<a onclick="go()" href="#">x</a><a>nohref</a><a href="/real">ok</a>'
        self.assertEqual(cr.js_only_nav(html), 2)

    def test_pagination_signals(self):
        pg = cr.pagination_signals(
            '<div class="pagination"><a href="/list?page=2">Next</a></div>'
        )
        self.assertTrue(pg["page_param_links"])
        self.assertTrue(pg["pagination_block"])


class TestModule(unittest.TestCase):
    def test_blocked_assets_finding(self):
        m = CrawlabilityModule()
        m.score(
            m.analyse(HTML_ASSETS, "https://x.example/", robots_txt=ROBOTS_BLOCK_ASSETS)
        )
        self.assertTrue(any("render resources" in f["title"] for f in m.findings))

    def test_clean_no_findings(self):
        m = CrawlabilityModule()
        m.score(
            m.analyse(
                '<a href="/real">ok</a>',
                "https://x.example/",
                robots_txt="User-agent: *\nAllow: /",
            )
        )
        self.assertEqual(m.findings, [])

    def test_faceted_finding(self):
        many = "".join(f'<a href="/p?sort={i}">x</a>' for i in range(35))
        m = CrawlabilityModule()
        m.score(m.analyse(many, "https://x.example/", robots_txt=""))
        self.assertTrue(any("faceted" in f["title"].lower() for f in m.findings))


if __name__ == "__main__":
    unittest.main()
