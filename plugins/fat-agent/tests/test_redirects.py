#!/usr/bin/env python3
"""Tests for scripts/redirects.py — chain/loop/soft-404 (no network)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import redirects


def make_fetcher(table):
    """table: url -> (status, location, body)."""

    def fetch(url, timeout=10):
        return table.get(url, (200, None, "OK page content"))

    return fetch


class TestFollow(unittest.TestCase):
    def test_single_301_ok(self):
        t = {
            "http://x.example/old": (301, "https://x.example/new", ""),
            "https://x.example/new": (200, None, "Welcome"),
        }
        r = redirects.follow("http://x.example/old", make_fetcher(t))
        self.assertEqual(r["hops"], 1)
        self.assertEqual(r["final_status"], 200)
        self.assertEqual(r["issues"], [])

    def test_chain_flagged(self):
        t = {
            "https://x/a": (301, "https://x/b", ""),
            "https://x/b": (301, "https://x/c", ""),
            "https://x/c": (200, None, "end"),
        }
        r = redirects.follow("https://x/a", make_fetcher(t))
        self.assertEqual(r["hops"], 2)
        self.assertTrue(any("chain" in i["issue"].lower() for i in r["issues"]))

    def test_loop_detected(self):
        t = {
            "https://x/1": (302, "https://x/2", ""),
            "https://x/2": (302, "https://x/1", ""),
        }
        r = redirects.follow("https://x/1", make_fetcher(t))
        self.assertTrue(r["loop"])
        self.assertTrue(any(i["priority"] == "P0" for i in r["issues"]))

    def test_temporary_redirect_flagged(self):
        t = {"https://x/a": (302, "https://x/b", ""), "https://x/b": (200, None, "ok")}
        r = redirects.follow("https://x/a", make_fetcher(t))
        self.assertTrue(any("temporary" in i["issue"].lower() for i in r["issues"]))

    def test_soft_404(self):
        t = {"https://x/missing": (200, None, "<h1>Page not found</h1> sorry")}
        r = redirects.follow("https://x/missing", make_fetcher(t))
        self.assertTrue(r["soft_404"])
        self.assertTrue(any("soft 404" in i["issue"].lower() for i in r["issues"]))

    def test_meta_refresh(self):
        t = {
            "https://x/a": (
                200,
                None,
                '<meta http-equiv="refresh" content="0;url=https://x/b">',
            ),
            "https://x/b": (200, None, "real"),
        }
        r = redirects.follow("https://x/a", make_fetcher(t))
        self.assertTrue(r["meta_refresh"])


if __name__ == "__main__":
    unittest.main()
