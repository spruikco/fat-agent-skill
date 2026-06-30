#!/usr/bin/env python3
"""Tests for v2.6.0 policy/judgement checks: Discover readiness + self-serving reviews."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.content_depth import ContentDepthModule
from modules.schema_validator import SchemaValidatorModule


def cd_titles(html, url):
    m = ContentDepthModule()
    m.score(m.analyse(html, url))
    return [f["title"] for f in m.findings]


def sv_titles(html):
    m = SchemaValidatorModule()
    m.score(m.analyse(html, "https://x.example/"))
    return [f["title"] for f in m.findings]


class TestDiscover(unittest.TestCase):
    def test_article_without_discover_flagged(self):
        html = "<article><h1>News</h1><p>" + " ".join(["w"] * 50) + "</p></article>"
        self.assertTrue(
            any(
                "Discover" in t for t in cd_titles(html, "https://x.example/news/story")
            )
        )

    def test_article_with_discover_ok(self):
        html = (
            '<head><meta name="robots" content="max-image-preview:large">'
            '<meta property="og:image" content="/big.jpg">'
            '<link rel="alternate" type="application/rss+xml" href="/feed"></head>'
            "<article><h1>News</h1><p>" + " ".join(["w"] * 50) + "</p></article>"
        )
        self.assertFalse(
            any(
                "Discover" in t for t in cd_titles(html, "https://x.example/news/story")
            )
        )


class TestSelfServingReview(unittest.TestCase):
    def test_org_with_aggregaterating_flagged(self):
        html = (
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Organization","name":"Acme","url":"https://x",'
            '"aggregateRating":{"@type":"AggregateRating","ratingValue":"5","reviewCount":"99"}}'
            "</script>"
        )
        self.assertTrue(any("Self-serving review" in t for t in sv_titles(html)))

    def test_localbusiness_with_review_flagged(self):
        html = (
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"LocalBusiness","name":"Joe",'
            '"review":[{"@type":"Review","reviewRating":{"ratingValue":"5"}}]}'
            "</script>"
        )
        self.assertTrue(any("Self-serving review" in t for t in sv_titles(html)))

    def test_product_aggregaterating_allowed(self):
        html = (
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Product","name":"Widget",'
            '"aggregateRating":{"@type":"AggregateRating","ratingValue":"4.5","reviewCount":"12"}}'
            "</script>"
        )
        self.assertFalse(any("Self-serving review" in t for t in sv_titles(html)))


if __name__ == "__main__":
    unittest.main()
