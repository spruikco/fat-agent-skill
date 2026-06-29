#!/usr/bin/env python3
"""Tests for the E-E-A-T & Trust module."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.eeat import EEATModule

ARTICLE_WITH_AUTHOR = """
<html><body>
<article>
  <p class="byline">By Jane Smith</p>
  <a href="/authors/jane-smith">Jane Smith</a>
  <p>Per <a href="https://www.nih.gov/study">the NIH study</a> ...</p>
</article>
<script type="application/ld+json">{"@type":"Article","author":{"@type":"Person","name":"Jane Smith"}}</script>
<footer><a href="/about">About</a><a href="/contact">Contact</a><a href="/privacy">Privacy</a></footer>
</body></html>
"""

ANON_ARTICLE = """
<html><body>
<article><h1>Some post</h1><p>/blog/ content with no author and no citations.</p></article>
</body></html>
"""


class TestSignals(unittest.TestCase):
    def test_author_signals(self):
        a = EEATModule().analyse(ARTICLE_WITH_AUTHOR, "https://x.example/blog/post")
        self.assertTrue(a["author"]["byline"])
        self.assertTrue(a["author"]["author_page"])
        self.assertTrue(a["author"]["schema_author"])

    def test_trust_pages(self):
        a = EEATModule().analyse(ARTICLE_WITH_AUTHOR, "https://x.example/blog/post")
        self.assertTrue(a["trust_pages"]["about"])
        self.assertTrue(a["trust_pages"]["contact"])
        self.assertTrue(a["trust_pages"]["privacy"])

    def test_outbound_citation_counts_external_nonsocial(self):
        a = EEATModule().analyse(ARTICLE_WITH_AUTHOR, "https://x.example/blog/post")
        self.assertGreaterEqual(a["outbound_citations"], 1)

    def test_outbound_excludes_own_host_and_social(self):
        html = (
            '<a href="https://x.example/page">self</a>'
            '<a href="https://facebook.com/x">fb</a>'
            '<a href="https://ref.example/cite">cite</a>'
        )
        a = EEATModule().analyse(
            "<article>" + html + "</article>", "https://x.example/blog/p"
        )
        self.assertEqual(a["outbound_citations"], 1)


class TestFindings(unittest.TestCase):
    def _titles(self, html, url):
        m = EEATModule()
        m.score(m.analyse(html, url))
        return [f["title"] for f in m.findings]

    def test_anon_article_flags_author(self):
        titles = self._titles(ANON_ARTICLE, "https://x.example/blog/post")
        self.assertTrue(any("author byline" in t.lower() for t in titles))

    def test_anon_article_flags_missing_trust_pages(self):
        titles = self._titles(ANON_ARTICLE, "https://x.example/blog/post")
        self.assertTrue(any("trust page" in t.lower() for t in titles))

    def test_well_signposted_article_no_author_finding(self):
        titles = self._titles(ARTICLE_WITH_AUTHOR, "https://x.example/blog/post")
        self.assertFalse(any("no author byline" in t.lower() for t in titles))

    def test_score_higher_for_trusted_page(self):
        m1 = EEATModule()
        good = m1.score(m1.analyse(ARTICLE_WITH_AUTHOR, "https://x.example/blog/post"))
        m2 = EEATModule()
        bad = m2.score(m2.analyse(ANON_ARTICLE, "https://x.example/blog/post"))
        self.assertGreater(good["total"], bad["total"])


if __name__ == "__main__":
    unittest.main()
