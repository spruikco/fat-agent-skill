#!/usr/bin/env python3
"""lighthouse CLI integration wrapper for fat-agent."""

import argparse
import json
import os
import shutil
import subprocess
import sys


def _empty_result(error=None):
    """return a result dict with all None values and available=False."""
    result = {
        "available": False,
        "url": None,
        "lighthouse_version": None,
        "scores": {
            "performance": None,
            "accessibility": None,
            "best_practices": None,
            "seo": None,
        },
        "core_web_vitals": {
            "LCP": None,
            "CLS": None,
            "INP": None,
            "FCP": None,
            "TTFB": None,
        },
        "error": error,
    }
    return result


def check_lighthouse_available():
    """check whether the lighthouse CLI is on PATH."""
    return shutil.which("lighthouse") is not None


def parse_lighthouse_results(json_path):
    """extract scores and core web vitals from a lighthouse JSON report."""
    if not os.path.isfile(json_path):
        return _empty_result(error=f"file not found: {json_path}")

    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return _empty_result(error=str(exc))

    categories = data.get("categories", {})
    audits = data.get("audits", {})

    def _score(cat_id):
        cat = categories.get(cat_id, {})
        raw = cat.get("score")
        if raw is None:
            return None
        return int(round(raw * 100))

    def _audit_value(audit_id):
        audit = audits.get(audit_id, {})
        return audit.get("numericValue")

    return {
        "available": True,
        "url": data.get("requestedUrl"),
        "lighthouse_version": data.get("lighthouseVersion"),
        "scores": {
            "performance": _score("performance"),
            "accessibility": _score("accessibility"),
            "best_practices": _score("best-practices"),
            "seo": _score("seo"),
        },
        "core_web_vitals": {
            "LCP": _audit_value("largest-contentful-paint"),
            "CLS": _audit_value("cumulative-layout-shift"),
            "INP": _audit_value("experimental-interaction-to-next-paint"),
            "FCP": _audit_value("first-contentful-paint"),
            "TTFB": _audit_value("server-response-time"),
        },
        "error": None,
    }


def run_lighthouse(url, output_path):
    """run lighthouse CLI against a url and return parsed results."""
    if not check_lighthouse_available():
        return _empty_result(error="lighthouse CLI not found")

    cmd = [
        "lighthouse",
        url,
        "--output",
        "json",
        "--output-path",
        output_path,
        "--chrome-flags=--headless --no-sandbox",
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except Exception as exc:
        return _empty_result(error=str(exc))

    return parse_lighthouse_results(output_path)


def build_arg_parser():
    """build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Run Lighthouse audit and extract scores + Core Web Vitals"
    )
    parser.add_argument("--url", required=True, help="URL to audit")
    parser.add_argument(
        "--output",
        default="lighthouse_report.json",
        help="path for the JSON report (default: lighthouse_report.json)",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    result = run_lighthouse(args.url, args.output)
    print(json.dumps(result, indent=2))
    if not result["available"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
