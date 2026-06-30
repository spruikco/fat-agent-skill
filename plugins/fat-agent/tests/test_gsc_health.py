#!/usr/bin/env python3
"""Tests for scripts/gsc_health.py — GSC health report analysis."""

import io
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import gsc_health

DATA = {
    "manual_actions": [{"type": "Thin content with little or no added value"}],
    "security_issues": [{"type": "Hacked: Content injection"}],
    "url_inspections": [
        {"url": "/a", "coverageState": "Submitted and indexed"},
        {"url": "/b", "coverageState": "Crawled - currently not indexed"},
        {"url": "/c", "coverageState": "Crawled - currently not indexed"},
        {"url": "/d", "coverageState": "Blocked by robots.txt"},
    ],
    "enhancements": {
        "Products": {"errors": 3, "warnings": 1},
        "Breadcrumbs": {"errors": 0},
    },
}


class TestAnalyse(unittest.TestCase):
    def setUp(self):
        self.r = gsc_health.analyse(DATA)

    def test_manual_action_p0(self):
        f = next(f for f in self.r["findings"] if "Manual action" in f["title"])
        self.assertEqual(f["priority"], "P0")

    def test_security_p0(self):
        self.assertTrue(
            any(
                f["priority"] == "P0" and "Security" in f["title"]
                for f in self.r["findings"]
            )
        )

    def test_index_coverage_counts(self):
        self.assertEqual(self.r["summary"]["urls_checked"], 4)
        self.assertEqual(self.r["summary"]["indexed"], 1)
        self.assertEqual(self.r["summary"]["not_indexed"], 3)

    def test_grouped_not_indexed_reason(self):
        f = next(f for f in self.r["findings"] if "currently not indexed" in f["title"])
        self.assertIn("2 URL", f["title"])  # two /b,/c grouped

    def test_enhancement_errors(self):
        self.assertEqual(self.r["summary"]["enhancement_errors"], 3)
        self.assertTrue(
            any("Products rich-result" in f["title"] for f in self.r["findings"])
        )

    def test_no_breadcrumb_error_finding(self):
        self.assertFalse(any("Breadcrumbs" in f["title"] for f in self.r["findings"]))

    def test_findings_sorted_p0_first(self):
        self.assertEqual(self.r["findings"][0]["priority"], "P0")

    def test_empty_is_safe(self):
        r = gsc_health.analyse({})
        self.assertTrue(r["available"])
        self.assertEqual(r["findings"], [])


class TestCLI(unittest.TestCase):
    def test_stdin(self):
        buf = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps(DATA))),
            patch("sys.stdout", buf),
        ):
            gsc_health.main([])
        out = json.loads(buf.getvalue())
        self.assertEqual(out["summary"]["manual_actions"], 1)


if __name__ == "__main__":
    unittest.main()
