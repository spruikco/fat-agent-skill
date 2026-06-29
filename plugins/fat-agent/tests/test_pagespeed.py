#!/usr/bin/env python3
"""Tests for scripts/pagespeed.py - no real API calls."""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pagespeed

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_mock_response():
    with open(os.path.join(FIXTURES_DIR, "pagespeed_mock.json")) as f:
        return json.load(f)


class TestParsePagespeedResults(unittest.TestCase):
    """Test parse_pagespeed_results with mock data."""

    def setUp(self):
        self.mock_data = _load_mock_response()

    def test_performance_score(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        self.assertEqual(result["performance_score"], 91)

    def test_url_extracted(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        self.assertEqual(result["url"], "https://example.com/")

    def test_strategy_extracted(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        self.assertEqual(result["strategy"], "mobile")

    def test_fcp_metric(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        fcp = result["metrics"]["FCP"]
        self.assertAlmostEqual(fcp["value"], 1234.5)
        self.assertEqual(fcp["display"], "1.2 s")
        self.assertEqual(fcp["unit"], "millisecond")

    def test_lcp_metric(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        lcp = result["metrics"]["LCP"]
        self.assertAlmostEqual(lcp["value"], 1800.0)

    def test_cls_metric(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        cls = result["metrics"]["CLS"]
        self.assertAlmostEqual(cls["value"], 0.003)
        self.assertEqual(cls["unit"], "unitless")

    def test_inp_metric(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        inp = result["metrics"]["INP"]
        self.assertEqual(inp["value"], 150)

    def test_fid_metric(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        fid = result["metrics"]["FID"]
        self.assertEqual(fid["value"], 95)

    def test_ttfb_metric(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        ttfb = result["metrics"]["TTFB"]
        self.assertAlmostEqual(ttfb["value"], 45.0)

    def test_speed_index_metric(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        si = result["metrics"]["speed_index"]
        self.assertAlmostEqual(si["value"], 2100.5)

    def test_total_blocking_time_metric(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        tbt = result["metrics"]["total_blocking_time"]
        self.assertAlmostEqual(tbt["value"], 120.0)

    def test_field_data_present(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        self.assertIn("field_data", result)
        self.assertIn("CUMULATIVE_LAYOUT_SHIFT_SCORE", result["field_data"])

    def test_field_data_values(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        cls_field = result["field_data"]["CUMULATIVE_LAYOUT_SHIFT_SCORE"]
        self.assertEqual(cls_field["percentile"], 1)
        self.assertEqual(cls_field["category"], "FAST")

    def test_no_error_on_valid_response(self):
        result = pagespeed.parse_pagespeed_results(self.mock_data)
        self.assertIsNone(result["error"])


class TestParseEdgeCases(unittest.TestCase):
    """Test error handling for malformed or empty responses."""

    def test_empty_response(self):
        result = pagespeed.parse_pagespeed_results({})
        self.assertIsNotNone(result["error"])
        self.assertIsNone(result["performance_score"])

    def test_none_response(self):
        result = pagespeed.parse_pagespeed_results(None)
        self.assertEqual(result["error"], "Empty or invalid response")

    def test_non_dict_response(self):
        result = pagespeed.parse_pagespeed_results("not a dict")
        self.assertEqual(result["error"], "Empty or invalid response")

    def test_error_only_response(self):
        result = pagespeed.parse_pagespeed_results({"error": "rate limited"})
        self.assertEqual(result["error"], "rate limited")
        self.assertIsNone(result["performance_score"])

    def test_missing_audits(self):
        data = {
            "id": "https://example.com/",
            "lighthouseResult": {
                "configSettings": {"formFactor": "desktop"},
                "categories": {"performance": {"score": 0.75}},
                "audits": {},
            },
        }
        result = pagespeed.parse_pagespeed_results(data)
        self.assertEqual(result["performance_score"], 75)
        self.assertIsNone(result["metrics"]["FCP"]["value"])

    def test_missing_categories(self):
        data = {
            "id": "https://example.com/",
            "lighthouseResult": {
                "configSettings": {},
                "categories": {},
                "audits": {},
            },
        }
        result = pagespeed.parse_pagespeed_results(data)
        self.assertIsNone(result["performance_score"])
        self.assertIsNone(result["error"])

    def test_no_field_data(self):
        data = {
            "id": "https://example.com/",
            "loadingExperience": {"metrics": {}},
            "lighthouseResult": {
                "configSettings": {},
                "categories": {},
                "audits": {},
            },
        }
        result = pagespeed.parse_pagespeed_results(data)
        self.assertNotIn("field_data", result)


class TestFetchPagespeed(unittest.TestCase):
    """Test fetch_pagespeed with mocked network calls."""

    def test_invalid_strategy(self):
        result = pagespeed.fetch_pagespeed("https://example.com", strategy="tablet")
        self.assertIn("error", result)
        self.assertIn("Invalid strategy", result["error"])

    @patch("pagespeed.urllib.request.urlopen")
    def test_successful_fetch(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"id": "https://example.com/"}
        ).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = pagespeed.fetch_pagespeed("https://example.com", strategy="mobile")
        self.assertEqual(result["id"], "https://example.com/")

    @patch("pagespeed.urllib.request.urlopen")
    def test_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = pagespeed.urllib.error.URLError("Connection refused")
        result = pagespeed.fetch_pagespeed("https://example.com")
        self.assertIn("error", result)
        self.assertIn("Network error", result["error"])

    @patch("pagespeed.urllib.request.urlopen")
    def test_http_error(self, mock_urlopen):
        err = pagespeed.urllib.error.HTTPError(
            url="https://example.com",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=b"rate limited")),
        )
        err.read = MagicMock(return_value=b"rate limited")
        mock_urlopen.side_effect = err
        result = pagespeed.fetch_pagespeed("https://example.com")
        self.assertIn("error", result)
        self.assertIn("429", result["error"])


class TestFetchBothStrategies(unittest.TestCase):
    """Test fetch_both_strategies."""

    @patch("pagespeed.fetch_pagespeed")
    def test_returns_both_keys(self, mock_fetch):
        mock_fetch.return_value = _load_mock_response()
        result = pagespeed.fetch_both_strategies("https://example.com")
        self.assertIn("mobile", result)
        self.assertIn("desktop", result)
        self.assertEqual(mock_fetch.call_count, 2)

    @patch("pagespeed.fetch_pagespeed")
    def test_passes_api_key(self, mock_fetch):
        mock_fetch.return_value = _load_mock_response()
        pagespeed.fetch_both_strategies("https://example.com", api_key="test-key")
        for call in mock_fetch.call_args_list:
            self.assertEqual(call.kwargs.get("api_key"), "test-key")


class TestCLIArgParsing(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_required_url(self):
        with self.assertRaises(SystemExit):
            pagespeed.build_parser().parse_args([])

    def test_url_only(self):
        args = pagespeed.build_parser().parse_args(["--url", "https://example.com"])
        self.assertEqual(args.url, "https://example.com")
        self.assertEqual(args.strategy, "mobile")
        self.assertIsNone(args.output)
        self.assertIsNone(args.api_key)
        self.assertEqual(args.timeout, 60)

    def test_all_args(self):
        args = pagespeed.build_parser().parse_args(
            [
                "--url",
                "https://example.com",
                "--strategy",
                "both",
                "--api-key",
                "my-key",
                "--output",
                "/tmp/pagespeed.json",
                "--timeout",
                "30",
            ]
        )
        self.assertEqual(args.strategy, "both")
        self.assertEqual(args.api_key, "my-key")
        self.assertEqual(args.output, "/tmp/pagespeed.json")
        self.assertEqual(args.timeout, 30)

    def test_desktop_strategy(self):
        args = pagespeed.build_parser().parse_args(
            ["--url", "https://example.com", "--strategy", "desktop"]
        )
        self.assertEqual(args.strategy, "desktop")

    def test_invalid_strategy_rejected(self):
        with self.assertRaises(SystemExit):
            pagespeed.build_parser().parse_args(
                ["--url", "https://example.com", "--strategy", "tablet"]
            )


class TestStrategyValidation(unittest.TestCase):
    """Test strategy validation constants and logic."""

    def test_valid_strategies_tuple(self):
        self.assertEqual(pagespeed.VALID_STRATEGIES, ("mobile", "desktop"))

    def test_mobile_accepted(self):
        self.assertIn("mobile", pagespeed.VALID_STRATEGIES)

    def test_desktop_accepted(self):
        self.assertIn("desktop", pagespeed.VALID_STRATEGIES)

    def test_both_not_in_valid_strategies(self):
        self.assertNotIn("both", pagespeed.VALID_STRATEGIES)


if __name__ == "__main__":
    unittest.main()
