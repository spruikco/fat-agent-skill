#!/usr/bin/env python3
"""
FAT Agent CLI — unified entry point for the full audit pipeline.

Subcommands:
    audit   Fetch a URL, analyse HTML, calculate scores, optionally generate reports.
    crawl   Breadth-first multi-page crawler.
    bulk    Run audits against a JSON list of sites.
    gate    CI gate: check scored output against thresholds.

Examples:
    python fat_agent_cli.py audit https://example.com --profile full --output-dir ./reports
    python fat_agent_cli.py audit https://example.com --profile quick --format html
    python fat_agent_cli.py crawl https://example.com --depth 2 --max-pages 10
    python fat_agent_cli.py bulk sites.json --profile local --output-dir ./reports
    python fat_agent_cli.py gate scores.json --threshold 70 --fail-on P0
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


# helpers


def _run_script(name, args, stdin_data=None):
    """run a sibling script via subprocess, return (returncode, stdout, stderr)."""
    script_path = os.path.join(SCRIPTS_DIR, name)
    cmd = [sys.executable, script_path] + args
    proc = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def fetch_url(url):
    """fetch a url and return (html_content, headers_dict).

    raises on http errors or connection failures.
    """
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "FAT-Agent/1.0")
    with urllib.request.urlopen(req, timeout=30) as resp:
        headers = {k.lower(): v for k, v in resp.getheaders()}
        html = resp.read().decode("utf-8", errors="replace")
    return html, headers


def cmd_audit(args):
    """fetch url, analyse, score, and optionally generate reports."""
    url = args.url
    output_dir = args.output_dir or "."
    os.makedirs(output_dir, exist_ok=True)

    # fetch the page
    try:
        html, headers = fetch_url(url)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        print(f"Error fetching {url}: {exc}", file=sys.stderr)
        return 1

    # write temp files
    tmpdir = tempfile.mkdtemp(prefix="fat_agent_")
    html_path = os.path.join(tmpdir, "page.html")
    headers_path = os.path.join(tmpdir, "headers.json")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(headers_path, "w", encoding="utf-8") as f:
        json.dump(headers, f, indent=2)

    # run analyse-html.py
    profile = args.profile or "full"

    # build modules arg from profile
    try:
        from profiles import resolve_profile

        modules = resolve_profile(profile)
        modules_str = ",".join(modules)
    except ImportError:
        modules_str = "auto"

    analyse_args = [
        html_path,
        "--url",
        url,
        "--fetch",
        "--modules",
        modules_str,
    ]
    rc, analyse_out, analyse_err = _run_script("analyse-html.py", analyse_args)
    if analyse_err:
        print(analyse_err, file=sys.stderr, end="")
    if rc != 0:
        print(f"analyse-html.py failed (exit {rc})", file=sys.stderr)
        return 1

    # pipe through calculate-score.py
    rc, score_out, score_err = _run_script(
        "calculate-score.py", [], stdin_data=analyse_out
    )
    if score_err:
        print(score_err, file=sys.stderr, end="")
    if rc != 0:
        print(f"calculate-score.py failed (exit {rc})", file=sys.stderr)
        return 1

    # parse scored json
    try:
        scores = json.loads(score_out)
    except json.JSONDecodeError:
        print("Failed to parse scored output as JSON", file=sys.stderr)
        return 1

    # save scored json
    scores_path = os.path.join(output_dir, "scores.json")
    with open(scores_path, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2)

    # generate reports if --format specified
    fmt = args.format
    if fmt:
        if fmt in ("html", "all"):
            _run_script(
                "generate_html_dashboard.py",
                [
                    "--scores",
                    scores_path,
                    "--url",
                    url,
                    "--output-dir",
                    output_dir,
                ],
            )
        if fmt in ("docx", "pptx", "all"):
            report_fmt = "both" if fmt == "all" else fmt
            _run_script(
                "generate-report.py",
                [
                    "--scores",
                    scores_path,
                    "--url",
                    url,
                    "--output-dir",
                    output_dir,
                    "--format",
                    report_fmt,
                ],
            )

    # print summary
    overall = scores.get("overall_score", "N/A")
    seo = scores.get("seo", {}).get("score", "N/A")
    security = scores.get("security", {}).get("score", "N/A")
    accessibility = scores.get("accessibility", {}).get("score", "N/A")
    performance = scores.get("performance", {}).get("score", "N/A")

    print(f"\nFAT Agent Audit: {url}")
    print(f"  Overall:       {overall}")
    print(f"  SEO:           {seo}")
    print(f"  Security:      {security}")
    print(f"  Accessibility: {accessibility}")
    print(f"  Performance:   {performance}")
    print(f"\nScored JSON saved to {scores_path}")

    # exit code: non-zero if overall < 50
    if isinstance(overall, (int, float)) and overall < 50:
        return 1
    return 0


def cmd_crawl(args):
    """run the multi-page crawler."""
    crawl_args = ["--url", args.url]
    if args.depth is not None:
        crawl_args += ["--depth", str(args.depth)]
    if args.max_pages is not None:
        crawl_args += ["--max-pages", str(args.max_pages)]
    if args.output_dir:
        crawl_args += ["--output-dir", args.output_dir]

    rc, stdout, stderr = _run_script("crawl.py", crawl_args)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, file=sys.stderr, end="")
    return rc


def cmd_bulk(args):
    """run bulk audits from a sites json file."""
    bulk_args = ["--sites", args.sites_file]
    if args.output_dir:
        bulk_args += ["--output-dir", args.output_dir]
    if args.profile:
        bulk_args += ["--profile", args.profile]

    rc, stdout, stderr = _run_script("bulk_audit.py", bulk_args)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, file=sys.stderr, end="")
    return rc


def cmd_gate(args):
    """run the ci gate checker."""
    gate_args = ["--scores", args.scores_file]
    if args.threshold is not None:
        gate_args += ["--threshold", str(args.threshold)]
    if args.fail_on:
        gate_args += ["--fail-on", args.fail_on]

    rc, stdout, stderr = _run_script("ci_gate.py", gate_args)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, file=sys.stderr, end="")
    return rc


def build_parser():
    """build the top-level argparse parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="fat_agent_cli",
        description="FAT Agent — unified CLI for website auditing.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- audit ---
    audit_p = subparsers.add_parser(
        "audit", help="Fetch a URL, analyse, score, and generate reports"
    )
    audit_p.add_argument("url", help="URL to audit")
    audit_p.add_argument(
        "--profile",
        default="full",
        choices=["quick", "full", "seo", "security", "local", "ecommerce"],
        help="Audit profile (default: full)",
    )
    audit_p.add_argument("--output-dir", help="Directory for output files")
    audit_p.add_argument(
        "--format",
        choices=["html", "docx", "pptx", "all"],
        help="Report format to generate",
    )
    audit_p.set_defaults(func=cmd_audit)

    # --- crawl ---
    crawl_p = subparsers.add_parser("crawl", help="Breadth-first multi-page crawler")
    crawl_p.add_argument("url", help="Start URL to crawl")
    crawl_p.add_argument(
        "--depth", type=int, default=2, help="Max crawl depth (default: 2)"
    )
    crawl_p.add_argument(
        "--max-pages", type=int, default=10, help="Max pages to crawl (default: 10)"
    )
    crawl_p.add_argument("--output-dir", help="Directory to save crawled HTML files")
    crawl_p.set_defaults(func=cmd_crawl)

    # --- bulk ---
    bulk_p = subparsers.add_parser(
        "bulk", help="Run audits on a list of sites from a JSON file"
    )
    bulk_p.add_argument("sites_file", help="Path to JSON file with site list")
    bulk_p.add_argument(
        "--profile",
        default="full",
        choices=["quick", "full", "seo", "security", "local", "ecommerce"],
        help="Audit profile (default: full)",
    )
    bulk_p.add_argument("--output-dir", help="Directory for output files")
    bulk_p.set_defaults(func=cmd_bulk)

    # --- gate ---
    gate_p = subparsers.add_parser(
        "gate", help="CI gate: check scores against thresholds"
    )
    gate_p.add_argument("scores_file", help="Path to scored JSON file")
    gate_p.add_argument(
        "--threshold", type=int, default=70, help="Minimum passing score (default: 70)"
    )
    gate_p.add_argument(
        "--fail-on",
        help="Fail if findings at this priority level exist (e.g. P0)",
    )
    gate_p.set_defaults(func=cmd_gate)

    return parser


def main(argv=None):
    """entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 2

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
