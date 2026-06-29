#!/usr/bin/env python3
"""PageSpeed Insights API integration for fat-agent.

Fetches real CrUX field data from the free PageSpeed Insights API.
Uses only stdlib (urllib.request + json) - no external dependencies.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://www.googleapis.com/pagespeedonline/v5/runPagespeedTest"
VALID_STRATEGIES = ("mobile", "desktop")


def _empty_result(error=None):
    """Return a result dict with all None values."""
    return {
        "url": None,
        "strategy": None,
        "performance_score": None,
        "metrics": {
            "FCP": None,
            "LCP": None,
            "CLS": None,
            "INP": None,
            "FID": None,
            "TTFB": None,
            "speed_index": None,
            "total_blocking_time": None,
        },
        "error": error,
    }


def fetch_pagespeed(url, strategy="mobile", api_key=None, timeout=60):
    """Call the PageSpeed Insights API for a single URL and strategy.

    Args:
        url: The page URL to test.
        strategy: 'mobile' or 'desktop'.
        api_key: Optional API key for higher quotas.
        timeout: Request timeout in seconds.

    Returns:
        Raw JSON response as a dict, or a dict with an 'error' key on failure.
    """
    if strategy not in VALID_STRATEGIES:
        return {
            "error": f"Invalid strategy '{strategy}'. Must be one of {VALID_STRATEGIES}"
        }

    params = {"url": url, "strategy": strategy}
    if api_key:
        params["key"] = api_key

    request_url = f"{API_BASE}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(
            request_url, headers={"User-Agent": "fat-agent-pagespeed/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return {"error": f"HTTP {exc.code}: {body[:500]}"}
    except urllib.error.URLError as exc:
        return {"error": f"Network error: {exc.reason}"}
    except Exception as exc:
        return {"error": f"Unexpected error: {exc}"}


def parse_pagespeed_results(data):
    """Extract key metrics from a PageSpeed Insights API response.

    Args:
        data: Raw API response dict.

    Returns:
        Parsed result dict with performance score and core metrics.
    """
    if not data or not isinstance(data, dict):
        return _empty_result(error="Empty or invalid response")

    if "error" in data and "lighthouseResult" not in data:
        return _empty_result(error=data["error"])

    result = _empty_result()

    # URL and strategy
    result["url"] = data.get("id")
    lhr = data.get("lighthouseResult", {})
    config = lhr.get("configSettings", {})
    form_factor = config.get("formFactor") or config.get("emulatedFormFactor")
    result["strategy"] = form_factor

    # performance score (0-100)
    categories = lhr.get("categories", {})
    perf = categories.get("performance", {})
    score = perf.get("score")
    if score is not None:
        result["performance_score"] = round(score * 100)

    # audits-based metrics
    audits = lhr.get("audits", {})
    metric_map = {
        "FCP": "first-contentful-paint",
        "LCP": "largest-contentful-paint",
        "CLS": "cumulative-layout-shift",
        "INP": "interaction-to-next-paint",
        "FID": "max-potential-fid",
        "TTFB": "server-response-time",
        "speed_index": "speed-index",
        "total_blocking_time": "total-blocking-time",
    }

    for key, audit_id in metric_map.items():
        audit = audits.get(audit_id, {})
        display = audit.get("displayValue")
        numeric = audit.get("numericValue")
        unit = audit.get("numericUnit")
        result["metrics"][key] = {
            "value": numeric,
            "display": display,
            "unit": unit,
        }

    # also try crux field data if available
    loading_exp = data.get("loadingExperience", {})
    crux_metrics = loading_exp.get("metrics", {})
    if crux_metrics:
        result["field_data"] = {}
        for crux_key, crux_val in crux_metrics.items():
            result["field_data"][crux_key] = {
                "percentile": crux_val.get("percentile"),
                "category": crux_val.get("category"),
            }

    result["error"] = None
    return result


def fetch_both_strategies(url, api_key=None, timeout=60):
    """Fetch PageSpeed results for both mobile and desktop.

    Args:
        url: The page URL to test.
        api_key: Optional API key.
        timeout: Request timeout in seconds.

    Returns:
        Dict with 'mobile' and 'desktop' keys, each containing parsed results.
    """
    combined = {}
    for strategy in VALID_STRATEGIES:
        raw = fetch_pagespeed(url, strategy=strategy, api_key=api_key, timeout=timeout)
        combined[strategy] = parse_pagespeed_results(raw)
    return combined


def build_parser():
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Fetch PageSpeed Insights data for a URL.",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL to test (e.g. https://example.com)",
    )
    parser.add_argument(
        "--strategy",
        choices=["mobile", "desktop", "both"],
        default="mobile",
        help="Test strategy (default: mobile)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional PageSpeed Insights API key",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write JSON results to this file path",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Request timeout in seconds (default: 60)",
    )
    return parser


def main(argv=None):
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.strategy == "both":
        results = fetch_both_strategies(
            args.url, api_key=args.api_key, timeout=args.timeout
        )
    else:
        raw = fetch_pagespeed(
            args.url, strategy=args.strategy, api_key=args.api_key, timeout=args.timeout
        )
        results = parse_pagespeed_results(raw)

    output_json = json.dumps(results, indent=2)

    if args.output:
        try:
            with open(args.output, "w") as f:
                f.write(output_json)
            print(f"Results written to {args.output}")
        except OSError as exc:
            print(f"Error writing output file: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
