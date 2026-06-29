#!/usr/bin/env python3
"""Tests for scripts/gsc.py — GSC behavioural analysis."""

import io
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import gsc

ROWS = [
    {
        "query": "acme widgets",
        "page": "/p",
        "clicks": 100,
        "impressions": 1000,
        "ctr": 0.10,
        "position": 3.0,
    },
    {
        "query": "blue widget online",
        "page": "/b",
        "clicks": 5,
        "impressions": 800,
        "ctr": 0.006,
        "position": 8.0,
    },
    {
        "query": "widget guide",
        "page": "/g",
        "clicks": 0,
        "impressions": 500,
        "ctr": 0.0,
        "position": 12.0,
    },
    {
        "query": "cheap widgets near me",
        "page": "/n",
        "clicks": 2,
        "impressions": 50,
        "ctr": 0.04,
        "position": 6.0,
    },
]

API_SHAPE = {
    "rows": [
        {
            "keys": ["acme brand", "/x"],
            "clicks": 50,
            "impressions": 200,
            "ctr": 0.25,
            "position": 1.2,
        }
    ]
}


class TestLoad(unittest.TestCase):
    def test_api_keys_shape(self):
        rows = gsc.load_rows(API_SHAPE)
        self.assertEqual(rows[0]["query"], "acme brand")
        self.assertEqual(rows[0]["page"], "/x")

    def test_ctr_derived_when_missing(self):
        rows = gsc.load_rows([{"query": "x", "clicks": 10, "impressions": 100}])
        self.assertAlmostEqual(rows[0]["ctr"], 0.1)


class TestBenchmark(unittest.TestCase):
    def test_curve(self):
        self.assertGreater(gsc.ctr_benchmark(1), gsc.ctr_benchmark(5))
        self.assertGreater(gsc.ctr_benchmark(5), gsc.ctr_benchmark(15))


class TestAnalyse(unittest.TestCase):
    def setUp(self):
        self.r = gsc.analyse(ROWS, brand_terms=["acme"], min_impressions=10)

    def test_striking_distance(self):
        qs = [s["query"] for s in self.r["striking_distance"]]
        self.assertIn("blue widget online", qs)  # pos 8, 800 impr
        self.assertIn("widget guide", qs)  # pos 12, 500 impr
        self.assertNotIn("acme widgets", qs)  # pos 3 — already top

    def test_low_ctr_flagged(self):
        qs = [s["query"] for s in self.r["low_ctr"]]
        self.assertIn("blue widget online", qs)  # pos 8 but 0.6% ctr

    def test_impressions_no_clicks(self):
        qs = [s["query"] for s in self.r["impressions_no_clicks"]]
        self.assertIn("widget guide", qs)

    def test_branded_share(self):
        # acme widgets = 100 of 107 clicks branded
        self.assertGreater(self.r["summary"]["branded_share"], 0.9)

    def test_opportunity_keywords_report_shape(self):
        ok = self.r["opportunity_keywords"]
        self.assertTrue(ok)
        for k in ("keyword", "volume", "position", "url", "priority"):
            self.assertIn(k, ok[0])

    def test_min_impressions_filters(self):
        r = gsc.analyse(ROWS, min_impressions=600)
        qs = [s["query"] for s in r["striking_distance"]]
        self.assertIn("blue widget online", qs)
        self.assertNotIn("widget guide", qs)  # 500 impr < 600


class TestCLI(unittest.TestCase):
    def test_stdin(self):
        buf = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps(ROWS))),
            patch("sys.stdout", buf),
        ):
            gsc.main(["--brand", "acme"])
        out = json.loads(buf.getvalue())
        self.assertTrue(out["available"])
        self.assertEqual(out["summary"]["query_count"], 4)


if __name__ == "__main__":
    unittest.main()
