#!/usr/bin/env python3
"""
FAT Agent Bulk Site Auditor
Reads a JSON file of sites and runs analysis on each.

Usage:
    python bulk_audit.py --sites path/to/sites.json --output-dir ./results
    python bulk_audit.py --sites sites.json --output-dir ./results --profile quick

Input format (sites.json):
    [{"url": "https://example.com", "name": "Example Site"}, ...]

Output:
    - Per-site JSON files in the output directory
    - portfolio_summary.json with all scores
    - Console comparison table
"""

import sys
import os
import json
import argparse
import subprocess
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timezone

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_sites(path: str) -> list[dict]:
    """Load a list of site dicts from a JSON file.

    Each entry must have at least 'url' and 'name' keys.

    Raises:
        FileNotFoundError: if the file does not exist.
        json.JSONDecodeError: if the file is not valid JSON.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_single_audit(
    url: str, name: str, output_dir: str, profile: str = "full"
) -> dict:
    """Run analyse-html.py and calculate-score.py for a single site.

    Fetches the HTML from the URL, pipes it through the analysis pipeline,
    and writes the per-site result JSON to output_dir.

    Returns a result dict with name, url, scores, and any errors.
    """
    result = {"name": name, "url": url, "scores": None, "error": None}

    try:
        # fetch the page html
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "FAT-Agent/1.0 (bulk-audit)")
        with urllib.request.urlopen(req, timeout=30) as resp:
            html_content = resp.read().decode("utf-8", errors="replace")
            response_headers = {k.lower(): v for k, v in resp.getheaders()}
    except Exception as e:
        result["error"] = f"Fetch failed: {e}"
        _write_site_result(result, output_dir, name)
        return result

    try:
        # write html to temp file for analyse-html.py
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as tmp_html:
            tmp_html.write(html_content)
            tmp_html_path = tmp_html.name

        # write headers to temp file for calculate-score.py
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp_headers:
            json.dump(response_headers, tmp_headers)
            tmp_headers_path = tmp_headers.name

        # run analyse-html.py
        analyse_script = os.path.join(SCRIPTS_DIR, "analyse-html.py")
        analyse_cmd = [
            sys.executable,
            analyse_script,
            "--url",
            url,
            "--fetch",
            tmp_html_path,
        ]
        analyse_result = subprocess.run(
            analyse_cmd, capture_output=True, text=True, timeout=60
        )
        if analyse_result.returncode != 0:
            result["error"] = f"analyse-html.py failed: {analyse_result.stderr.strip()}"
            _write_site_result(result, output_dir, name)
            return result

        analysis_json = analyse_result.stdout

        # write analysis output to temp file for calculate-score.py
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp_analysis:
            tmp_analysis.write(analysis_json)
            tmp_analysis_path = tmp_analysis.name

        # run calculate-score.py
        score_script = os.path.join(SCRIPTS_DIR, "calculate-score.py")
        score_cmd = [
            sys.executable,
            score_script,
            tmp_analysis_path,
            tmp_headers_path,
        ]
        score_result = subprocess.run(
            score_cmd, capture_output=True, text=True, timeout=60
        )
        if score_result.returncode != 0:
            result["error"] = (
                f"calculate-score.py failed: {score_result.stderr.strip()}"
            )
            _write_site_result(result, output_dir, name)
            return result

        scores = json.loads(score_result.stdout)
        result["scores"] = scores

    except subprocess.TimeoutExpired:
        result["error"] = "Audit timed out"
    except Exception as e:
        result["error"] = f"Audit error: {e}"
    finally:
        # clean up temp files
        for p in [tmp_html_path, tmp_headers_path, tmp_analysis_path]:
            try:
                os.unlink(p)
            except (OSError, UnboundLocalError):
                pass

    _write_site_result(result, output_dir, name)
    return result


def _write_site_result(result: dict, output_dir: str, name: str) -> None:
    """Write a per-site result JSON file to the output directory."""
    if not output_dir:
        return
    os.makedirs(output_dir, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    filepath = os.path.join(output_dir, f"{safe_name}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


def generate_summary(results: list[dict]) -> dict:
    """Generate a portfolio summary from a list of audit results.

    Returns a dict with:
        - sites: list of per-site score summaries
        - average_overall: mean overall score across all sites
        - best: site with highest overall score (or None)
        - worst: site with lowest overall score (or None)
        - timestamp: ISO timestamp of generation
    """
    if not results:
        return {
            "sites": [],
            "average_overall": 0,
            "best": None,
            "worst": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    site_summaries = []
    for r in results:
        scores = r.get("scores") or {}
        overall = scores.get("overall", {})
        site_summaries.append(
            {
                "name": r["name"],
                "url": r["url"],
                "overall_score": overall.get("score", 0),
                "grade": overall.get("grade", "N/A"),
                "seo": scores.get("seo", {}).get("score", 0),
                "security": scores.get("security", {}).get("score", 0),
                "accessibility": scores.get("accessibility", {}).get("score", 0),
                "performance": scores.get("performance", {}).get("score", 0),
                "error": r.get("error"),
            }
        )

    scored = [s for s in site_summaries if s["error"] is None]
    if scored:
        avg = round(sum(s["overall_score"] for s in scored) / len(scored))
        best = max(scored, key=lambda s: s["overall_score"])
        worst = min(scored, key=lambda s: s["overall_score"])
    else:
        avg = 0
        best = None
        worst = None

    return {
        "sites": site_summaries,
        "average_overall": avg,
        "best": best,
        "worst": worst,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def print_comparison_table(results: list[dict]) -> None:
    """Print a formatted comparison table of audit results to stdout."""
    if not results:
        print("No results to display.")
        return

    # column widths
    name_w = max(len(r["name"]) for r in results)
    name_w = max(name_w, 4)

    headers = ["Name", "SEO", "Security", "A11y", "Perf", "Overall", "Grade"]
    col_widths = [name_w, 5, 10, 6, 6, 9, 7]

    def fmt_row(cols):
        return " | ".join(str(c).ljust(w) for c, w in zip(cols, col_widths))

    header_line = fmt_row(headers)
    separator = "-+-".join("-" * w for w in col_widths)

    print(header_line)
    print(separator)

    for r in results:
        scores = r.get("scores") or {}
        overall = scores.get("overall", {})
        cols = [
            r["name"],
            scores.get("seo", {}).get("score", "-"),
            scores.get("security", {}).get("score", "-"),
            scores.get("accessibility", {}).get("score", "-"),
            scores.get("performance", {}).get("score", "-"),
            overall.get("score", "-"),
            overall.get("grade", "ERR") if not r.get("error") else "ERR",
        ]
        print(fmt_row(cols))


def main():
    parser = argparse.ArgumentParser(description="FAT Agent Bulk Site Auditor")
    parser.add_argument(
        "--sites", required=True, help="Path to JSON file with site list"
    )
    parser.add_argument(
        "--output-dir",
        default="./bulk_audit_results",
        help="Directory for per-site result files",
    )
    parser.add_argument(
        "--profile",
        default="full",
        help="Audit profile to use (quick, full, seo, security, local, ecommerce)",
    )
    args = parser.parse_args()

    sites = load_sites(args.sites)
    if not sites:
        print("No sites found in input file.", file=sys.stderr)
        sys.exit(1)

    print(f"Auditing {len(sites)} site(s) with profile '{args.profile}'...\n")

    results = []
    for i, site in enumerate(sites, 1):
        url = site["url"]
        name = site.get("name", url)
        print(f"[{i}/{len(sites)}] {name} ({url})...", end=" ", flush=True)
        result = run_single_audit(url, name, args.output_dir, args.profile)
        results.append(result)
        if result["error"]:
            print(f"ERROR: {result['error']}")
        else:
            overall = result["scores"].get("overall", {})
            print(f"{overall.get('grade', '?')} ({overall.get('score', '?')}/100)")

    print()
    print_comparison_table(results)

    # write portfolio summary
    summary = generate_summary(results)
    os.makedirs(args.output_dir, exist_ok=True)
    summary_path = os.path.join(args.output_dir, "portfolio_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nPortfolio summary written to: {summary_path}")


if __name__ == "__main__":
    main()
