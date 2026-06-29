#!/usr/bin/env python3
"""Tests for the AI Search / GEO module."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules import ai_search as ai
from modules.ai_search import AISearchModule

ROBOTS_BLOCK_AI = """
User-agent: GPTBot
Disallow: /

User-agent: *
Allow: /
"""

ROBOTS_WILDCARD_BLOCK = """
User-agent: *
Disallow: /
"""

ROBOTS_OPEN = """
User-agent: *
Disallow: /admin/
Sitemap: https://x.example/sitemap.xml
"""

RICH_HTML = """
<html><body>
<h2>Overview</h2><h3>Details</h3>
<details><summary>Q?</summary>A.</details>
<ul><li>a</li><li>b</li><li>c</li></ul>
<table><tr><td>x</td></tr></table>
<script type="application/ld+json">{"@type":"Organization","sameAs":["https://en.wikipedia.org/wiki/X"]}</script>
</body></html>
"""


class TestRobotsParsing(unittest.TestCase):
    def test_specific_block_beats_wildcard_allow(self):
        self.assertEqual(ai.bot_posture(ROBOTS_BLOCK_AI, "gptbot"), "blocked")
        self.assertEqual(ai.bot_posture(ROBOTS_BLOCK_AI, "perplexitybot"), "allowed")

    def test_wildcard_block_applies_to_all(self):
        self.assertEqual(ai.bot_posture(ROBOTS_WILDCARD_BLOCK, "gptbot"), "blocked")
        self.assertEqual(ai.bot_posture(ROBOTS_WILDCARD_BLOCK, "ccbot"), "blocked")

    def test_no_robots_means_allowed(self):
        self.assertEqual(ai.bot_posture("", "gptbot"), "allowed")

    def test_partial_disallow(self):
        self.assertEqual(ai.bot_posture(ROBOTS_OPEN, "gptbot"), "partial")

    def test_report_shape(self):
        rep = ai.ai_bot_report(ROBOTS_BLOCK_AI)
        self.assertEqual(rep["GPTBot"], "blocked")
        self.assertIn("PerplexityBot", rep)


class TestReadiness(unittest.TestCase):
    def test_extraction(self):
        ex = ai.extraction_readiness(RICH_HTML)
        self.assertTrue(ex["has_faq"])
        self.assertTrue(ex["has_lists"])
        self.assertTrue(ex["has_tables"])
        self.assertTrue(ex["has_headings"])

    def test_entity(self):
        ent = ai.entity_clarity(RICH_HTML)
        self.assertTrue(ent["organization"])
        self.assertTrue(ent["sameAs"])
        self.assertTrue(ent["knowledge_graph_link"])


class TestModule(unittest.TestCase):
    def test_analyse_uses_injected_robots_no_network(self):
        a = AISearchModule().analyse(
            RICH_HTML, "https://x.example/", robots_txt=ROBOTS_BLOCK_AI, llms_txt=None
        )
        self.assertIn("GPTBot", a["blocked_bots"])
        self.assertFalse(a["llms_txt"])

    def test_findings_flag_blocked_bots(self):
        m = AISearchModule()
        m.score(
            m.analyse(
                RICH_HTML,
                "https://x.example/",
                robots_txt=ROBOTS_WILDCARD_BLOCK,
                llms_txt="x",
            )
        )
        self.assertTrue(any("blocked in robots.txt" in f["title"] for f in m.findings))

    def test_open_robots_no_block_finding(self):
        m = AISearchModule()
        m.score(
            m.analyse(
                RICH_HTML, "https://x.example/", robots_txt=ROBOTS_OPEN, llms_txt="x"
            )
        )
        self.assertFalse(any("blocked in robots.txt" in f["title"] for f in m.findings))


if __name__ == "__main__":
    unittest.main()
