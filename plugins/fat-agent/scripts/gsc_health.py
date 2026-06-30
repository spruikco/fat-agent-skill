#!/usr/bin/env python3
"""Google Search Console *health* analysis for fat-agent (Bundle E).

Where `gsc.py` reads the Performance report (clicks/queries — NavBoost proxy),
this reads the *health* reports a URL-only audit can't see — and which often hide
the most damaging problems:

- **Manual Actions** — a human penalty (P0).
- **Security Issues** — hacked content / malware / deceptive pages (P0).
- **Index Coverage / URL Inspection** — indexed vs excluded and *why*
  (Discovered/Crawled-currently-not-indexed, blocked by robots, noindex, soft 404,
  redirect, duplicate-without-canonical, crawl anomaly).
- **Enhancements / Rich Results** — structured-data errors per result type.

No API/auth here — gather each report via the GSC MCP (`mcp__gsc__*`) or the
Search Console API, assemble them into one JSON, and pass it in. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys

# URL-Inspection coverage states that mean "not indexed", with a priority + hint.
_NOT_INDEXED = {
    "submitted and indexed": None,
    "indexed, not submitted in sitemap": None,
    "discovered - currently not indexed": (
        "P1",
        "Crawl-budget/quality signal — Google chose not to index. Improve internal links + content depth.",
    ),
    "crawled - currently not indexed": (
        "P1",
        "Google crawled but didn't index — usually a quality/duplication signal.",
    ),
    "duplicate without user-selected canonical": (
        "P2",
        "Set a clear canonical; consolidate duplicates.",
    ),
    "duplicate, google chose different canonical than user": (
        "P2",
        "Your canonical was overridden — align signals (internal links, sitemap, hreflang).",
    ),
    "excluded by 'noindex' tag": ("P2", "Remove noindex if the page should rank."),
    "blocked by robots.txt": (
        "P1",
        "Unblock in robots.txt if the page should be indexed.",
    ),
    "soft 404": ("P1", "Return a real 404/410 or add real content."),
    "not found (404)": ("P2", "Fix or redirect broken URLs that should exist."),
    "page with redirect": (None, None),
    "blocked due to unauthorized request (401)": (
        "P2",
        "Auth-gated — exclude from sitemap if intentional.",
    ),
    "crawl anomaly": ("P2", "Investigate server responses / intermittent errors."),
}


def _norm(s):
    return (s or "").strip().lower()


def analyse(data):
    data = data or {}
    findings = []
    summary = {}

    # --- Manual actions (P0) ---
    manual = data.get("manual_actions") or []
    summary["manual_actions"] = len(manual)
    for ma in manual:
        desc = ma.get("type") or ma.get("reason") or "Manual action"
        findings.append(
            {
                "priority": "P0",
                "title": f"Manual action: {desc}",
                "description": "Google has applied a manual action — pages or the whole site are "
                "demoted or removed until fixed and a reconsideration request is filed.",
                "fix": "Resolve the violation, then submit a reconsideration request in GSC.",
            }
        )

    # --- Security issues (P0) ---
    security = data.get("security_issues") or []
    summary["security_issues"] = len(security)
    for si in security:
        desc = si.get("type") or si.get("reason") or "Security issue"
        findings.append(
            {
                "priority": "P0",
                "title": f"Security issue: {desc}",
                "description": "GSC reports a security problem (hacked content, malware, or social "
                "engineering). This triggers browser warnings and ranking suppression.",
                "fix": "Clean the site, patch the entry point, then request a review in GSC.",
            }
        )

    # --- Index coverage / URL inspection ---
    inspections = data.get("url_inspections") or []
    reasons = {}
    indexed = 0
    for ins in inspections:
        state = _norm(
            ins.get("coverageState") or ins.get("verdict") or ins.get("indexingState")
        )
        mapped = _NOT_INDEXED.get(
            state, ("P3", "Unrecognised coverage state — review in URL Inspection.")
        )
        if mapped is None or (isinstance(mapped, tuple) and mapped[0] is None):
            indexed += 1
            continue
        reasons.setdefault(
            state, {"count": 0, "priority": mapped[0], "hint": mapped[1]}
        )
        reasons[state]["count"] += 1
    summary["urls_checked"] = len(inspections)
    summary["indexed"] = indexed
    summary["not_indexed"] = len(inspections) - indexed
    for state, info in sorted(reasons.items(), key=lambda kv: -kv[1]["count"]):
        findings.append(
            {
                "priority": info["priority"],
                "title": f'{info["count"]} URL(s): {state}',
                "description": f"{info['count']} inspected URL(s) are not indexed ({state}).",
                "fix": info["hint"],
            }
        )

    # --- Enhancements / rich-result errors ---
    enh = data.get("enhancements") or {}
    enh_errors = 0
    for rtype, counts in enh.items():
        errors = (
            counts.get("errors", 0) if isinstance(counts, dict) else int(counts or 0)
        )
        enh_errors += errors
        if errors:
            findings.append(
                {
                    "priority": "P2",
                    "title": f"{errors} {rtype} rich-result error(s)",
                    "description": f"Search Console's {rtype} enhancement report shows {errors} "
                    "error(s), making those pages ineligible for the rich result.",
                    "fix": f"Fix the {rtype} structured-data errors flagged in GSC and validate.",
                }
            )
    summary["enhancement_errors"] = enh_errors

    findings.sort(key=lambda f: f["priority"])
    return {"available": True, "summary": summary, "findings": findings}


def build_parser():
    p = argparse.ArgumentParser(
        description="Analyse assembled GSC health reports (index/manual/security/enhancements)."
    )
    p.add_argument("--data", help="GSC health JSON file (default: stdin)")
    p.add_argument("--output", default=None)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    raw = open(args.data, encoding="utf-8").read() if args.data else sys.stdin.read()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Invalid GSC health JSON: {exc}", file=sys.stderr)
        sys.exit(1)
    result = analyse(data)
    text = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"GSC health analysis written to {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
