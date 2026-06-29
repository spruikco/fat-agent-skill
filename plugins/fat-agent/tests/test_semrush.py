#!/usr/bin/env python3
"""Tests for scripts/semrush.py - no real API calls, no real key."""

import io
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import semrush

FAKE_KEY = "deadbeefdeadbeefdeadbeefdeadbeef"

DOMAIN_RANKS_CSV = (
    "Database;Domain;Rank;Organic Keywords;Organic Traffic;Organic Cost;"
    "Adwords Keywords;Adwords Traffic;Adwords Cost\n"
    "au;example.com;12345;641;1200;2000;0;0;0\n"
)

RANK_HISTORY_CSV = (
    "Rank;Organic Keywords;Organic Traffic;Organic Cost;"
    "Adwords Keywords;Adwords Traffic;Adwords Cost;Date\n"
    "15000;500;800;1500;0;0;0;20240401\n"
    "12345;641;1200;2000;0;0;0;20240601\n"
)

DOMAIN_ORGANIC_CSV = (
    "Keyword;Position;Previous Position;Position Difference;Search Volume;CPC;"
    "Url;Traffic (%);Traffic Cost (%);Competition;Number of Results;Trends\n"
    "example query;1;2;1;720;1.50;https://example.com/;14.70;10.00;0.50;1000000;0.1\n"
    "another term;5;5;0;300;0.80;https://example.com/x;5.00;3.00;0.40;500000;0.2\n"
    "deep page;45;40;-5;90;0.30;https://example.com/y;1.00;0.50;0.20;200000;0.3\n"
)

BACKLINKS_CSV = "Authority Score;Total Backlinks;Referring Domains\n22;1300;164\n"


def _fake_request(params, key, base=semrush.ANALYTICS_BASE, timeout=30):
    """Stand-in for semrush._request keyed on the report type."""
    report = params.get("type")
    return {
        "domain_ranks": DOMAIN_RANKS_CSV,
        "domain_rank_history": RANK_HISTORY_CSV,
        "domain_organic": DOMAIN_ORGANIC_CSV,
        "backlinks_overview": BACKLINKS_CSV,
    }[report]


class TestKeyResolution(unittest.TestCase):
    def test_cli_key_wins(self):
        self.assertEqual(semrush.get_api_key("abc"), "abc")

    def test_env_key_used(self):
        with patch.dict(os.environ, {semrush.ENV_VAR: "  envkey  "}):
            self.assertEqual(semrush.get_api_key(), "envkey")

    def test_no_key_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(semrush.get_api_key())


class TestRedaction(unittest.TestCase):
    def test_redacts_plain_key(self):
        out = semrush._redact(f"WRONG KEY {FAKE_KEY} supplied", FAKE_KEY)
        self.assertNotIn(FAKE_KEY, out)
        self.assertIn("***REDACTED***", out)

    def test_handles_empty(self):
        self.assertEqual(semrush._redact("", FAKE_KEY), "")
        self.assertIsNone(semrush._redact(None, FAKE_KEY))


class TestParsing(unittest.TestCase):
    def test_parse_csv(self):
        rows = semrush._parse_csv(DOMAIN_RANKS_CSV)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Organic Keywords"], "641")

    def test_parse_csv_empty(self):
        self.assertEqual(semrush._parse_csv(""), [])

    def test_fmt_month(self):
        self.assertEqual(semrush._fmt_month("20240401"), "Apr 24")
        self.assertEqual(semrush._fmt_month("2024-06-01"), "Jun 24")

    def test_pct_change(self):
        self.assertEqual(semrush._pct_change(800, 1200), "+50%")
        self.assertEqual(semrush._pct_change(1200, 800), "-33.3%")
        self.assertEqual(semrush._pct_change(0, 100), "")

    def test_position_distribution(self):
        rows = semrush._parse_csv(DOMAIN_ORGANIC_CSV)
        dist = semrush._position_distribution(rows)
        self.assertEqual(dist["top3"], 1)
        self.assertEqual(dist["4-10"], 1)
        self.assertEqual(dist["21-50"], 1)


class TestBuilders(unittest.TestCase):
    def test_traffic_trend_sorted_oldest_first(self):
        trend = semrush.build_traffic_trend(semrush._parse_csv(RANK_HISTORY_CSV))
        self.assertEqual([p["month"] for p in trend], ["Apr 24", "Jun 24"])
        self.assertEqual(trend[0]["organic"], 800)
        self.assertEqual(trend[-1]["organic"], 1200)

    def test_top_keywords(self):
        kws = semrush.build_top_keywords(semrush._parse_csv(DOMAIN_ORGANIC_CSV))
        self.assertEqual(kws[0]["keyword"], "example query")
        self.assertEqual(kws[0]["position"], 1)
        self.assertEqual(kws[0]["volume"], 720)
        self.assertEqual(kws[0]["traffic_pct"], "14.70%")


class TestBuildSemrushJson(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(semrush, "_request", side_effect=_fake_request)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_overview_fields(self):
        data = semrush.build_semrush_json("example.com", "au", FAKE_KEY)
        self.assertTrue(data["available"])
        self.assertEqual(data["organic_keywords"], 641)
        self.assertEqual(data["organic_traffic"], 1200)
        self.assertEqual(data["traffic_cost"], 2000)

    def test_trends_and_change(self):
        data = semrush.build_semrush_json("example.com", "au", FAKE_KEY)
        self.assertEqual(data["traffic_change"], "+50%")
        self.assertEqual(len(data["traffic_trend"]), 2)
        self.assertEqual(len(data["keywords_trend"]), 2)

    def test_backlinks(self):
        data = semrush.build_semrush_json("example.com", "au", FAKE_KEY)
        self.assertEqual(data["authority_score"], 22)
        self.assertEqual(data["backlinks"], 1300)
        self.assertEqual(data["referring_domains"], 164)

    def test_schema_matches_chart_consumer_keys(self):
        data = semrush.build_semrush_json("example.com", "au", FAKE_KEY)
        for key in (
            "domain",
            "authority_score",
            "organic_traffic",
            "traffic_change",
            "organic_keywords",
            "keywords_change",
            "referring_domains",
            "backlinks",
            "traffic_cost",
            "traffic_trend",
            "keywords_trend",
            "position_distribution",
            "top_keywords",
        ):
            self.assertIn(key, data)

    def test_key_never_in_output(self):
        data = semrush.build_semrush_json("example.com", "au", FAKE_KEY)
        self.assertNotIn(FAKE_KEY, json.dumps(data))


class TestRequestErrors(unittest.TestCase):
    def test_api_error_body_raises_redacted(self):
        body = f"ERROR 120 :: WRONG KEY - ID PAIR {FAKE_KEY}"

        class _Resp:
            def read(self_inner):
                return body.encode("utf-8")

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

        with patch("urllib.request.urlopen", return_value=_Resp()):
            with self.assertRaises(semrush.SemrushError) as ctx:
                semrush._request({"type": "domain_ranks", "domain": "x"}, FAKE_KEY)
        self.assertNotIn(FAKE_KEY, str(ctx.exception))

    def test_partial_failure_is_non_fatal(self):
        def flaky(params, key, base=semrush.ANALYTICS_BASE, timeout=30):
            if params.get("type") == "domain_rank_history":
                raise semrush.SemrushError("ERROR 50 :: NOTHING FOUND")
            return _fake_request(params, key, base, timeout)

        with patch.object(semrush, "_request", side_effect=flaky):
            data = semrush.build_semrush_json("example.com", "au", FAKE_KEY)
        self.assertTrue(data["available"])  # overview still succeeded
        self.assertIn("history_error", data)
        self.assertEqual(data["traffic_trend"], [])


class TestMain(unittest.TestCase):
    def test_no_key_outputs_unavailable(self):
        buf = io.StringIO()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sys.stdout", buf),
            patch("sys.stderr", io.StringIO()),
        ):
            semrush.main(["--domain", "example.com"])
        result = json.loads(buf.getvalue())
        self.assertFalse(result["available"])
        self.assertIn(semrush.ENV_VAR, result["reason"])

    def test_main_with_key_emits_data(self):
        buf = io.StringIO()
        with (
            patch.object(semrush, "_request", side_effect=_fake_request),
            patch("sys.stdout", buf),
        ):
            semrush.main(["--domain", "example.com", "--api-key", FAKE_KEY])
        result = json.loads(buf.getvalue())
        self.assertTrue(result["available"])
        self.assertEqual(result["organic_keywords"], 641)
        self.assertNotIn(FAKE_KEY, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
