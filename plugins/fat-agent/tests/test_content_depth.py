#!/usr/bin/env python3
"""Tests for the Content Depth & Quality module."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.content_depth import ContentDepthModule, lead_answer_present

YMYL = "<html><head><title>Best Mortgage Loan Rates</title></head><body><article><h1>Mortgage Guide</h1><p>x</p></article></body></html>"
RICH = (
    "<article><h1>Widget Review</h1>"
    "<p>We tested the widget for two weeks. It is great and costs about 20% less than rivals, "
    "delivering strong value for most buyers in our hands-on testing over many days.</p>"
    "<table><tr><td>spec</td></tr></table><figure><img src='a.jpg'></figure>"
    "<time datetime='2026-06-01'>Updated June 2026</time></article>"
)


class TestSignals(unittest.TestCase):
    def test_ymyl_detected(self):
        a = ContentDepthModule().analyse(YMYL, "https://x.example/mortgage-guide")
        self.assertTrue(a["ymyl"])

    def test_non_ymyl(self):
        a = ContentDepthModule().analyse("<h1>Cat toys</h1>", "https://x.example/toys")
        self.assertFalse(a["ymyl"])

    def test_freshness_and_originality(self):
        a = ContentDepthModule().analyse(RICH, "https://x.example/blog/review")
        self.assertTrue(a["has_freshness"])
        self.assertGreaterEqual(a["originality_score"], 2)
        self.assertTrue(a["firsthand"])

    def test_ad_heavy(self):
        ads = (
            "<article><h1>x</h1>"
            + '<ins class="adsbygoogle"></ins>' * 5
            + "<p>tiny</p></article>"
        )
        a = ContentDepthModule().analyse(ads, "https://x.example/blog/p")
        self.assertTrue(a["ad_heavy"])

    def test_lead_answer(self):
        good = "<h1>Q</h1><p>" + " ".join(["word"] * 40) + "</p><h2>more</h2>"
        self.assertTrue(lead_answer_present(good))
        self.assertFalse(lead_answer_present("<h1>Q</h1><p>too short</p>"))


class TestFindings(unittest.TestCase):
    def _titles(self, html, url):
        m = ContentDepthModule()
        m.score(m.analyse(html, url))
        return [f["title"] for f in m.findings]

    def test_ymyl_finding(self):
        self.assertTrue(
            any(
                "YMYL" in t
                for t in self._titles(YMYL, "https://x.example/mortgage-guide")
            )
        )

    def test_thin_rehash_flags_originality(self):
        thin = "<article><h1>Topic</h1><p>" + " ".join(["text"] * 50) + "</p></article>"
        self.assertTrue(
            any(
                "originality" in t.lower()
                for t in self._titles(thin, "https://x.example/blog/p")
            )
        )

    def test_review_without_firsthand(self):
        # a genuine review page (rating evidence present) but no first-hand testing
        rev = (
            "<article><h1>Laptop Review: Model X</h1>"
            '<div class="star-rating">Rating: 4 out of 5</div><p>'
            + " ".join(["buy"] * 40)
            + "</p></article>"
        )
        self.assertTrue(
            any(
                "first-hand" in t.lower()
                for t in self._titles(rev, "https://x.example/laptop-review")
            )
        )

    def test_superlative_title_alone_is_not_a_review(self):
        # "Best Plumber in Sydney" with no rating evidence must NOT be flagged a review
        page = "<h1>Best Plumber in Sydney</h1><p>" + " ".join(["call"] * 30) + "</p>"
        self.assertFalse(
            any(
                "first-hand" in t.lower()
                for t in self._titles(page, "https://x.example/")
            )
        )

    def test_rich_review_no_firsthand_finding(self):
        self.assertFalse(
            any(
                "first-hand" in t.lower()
                for t in self._titles(RICH, "https://x.example/blog/review")
            )
        )


if __name__ == "__main__":
    unittest.main()
