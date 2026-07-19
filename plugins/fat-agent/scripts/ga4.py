#!/usr/bin/env python3
"""GA4 behaviour layer — what visitors DO after search delivers them.

GSC says what ranks; GA4 says whether it works. Ingests a GA4 landing-page
report exactly as exported (UI CSV with its # preamble, or JSON rows from an
analytics MCP/API) and finds the behaviour gaps rankings can't show:

  engagement gap     real traffic, poor engagement — content/UX problem,
                     not a ranking problem
  money page, no     a page that sells receives sessions but records zero
  conversions        key events — measurement or persuasion is broken

Usage:
    python scripts/ga4.py --data ./.fat-work/ga4.csv [--base-url https://x.com]
        [--min-sessions 50] [--json]
"""

import argparse
import csv
import io
import json
import re
import sys

from link_opportunities import MONEY_DEFAULT

MODULE = "ga4"
MAX_FINDINGS = 10

PAGE_KEYS = ("landing page + query string", "landing page", "page path", "page")
SESSION_KEYS = ("sessions",)
ENGAGE_KEYS = ("engagement rate", "engaged sessions rate")
CONV_KEYS = ("key events", "conversions", "conversion events")


def _num(v):
    s = str(v or "0").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0


def _pick(row, keys):
    for k in keys:
        if k in row:
            return row[k]
    return None


def load_rows(path):
    """GA4 UI CSV (skips the # comment preamble) or JSON rows — as exported."""
    if path.lower().endswith(".csv"):
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = [ln for ln in f.read().splitlines() if not ln.startswith("#")]
        # the header row is the first line naming a page-ish column
        start = next(
            (
                i
                for i, ln in enumerate(lines)
                if any(k in ln.lower() for k in ("landing page", "page path"))
            ),
            0,
        )
        raw = list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("rows", data) if isinstance(data, dict) else data

    out = []
    for r in raw or []:
        row = {(k or "").strip().lower(): v for k, v in r.items()}
        page = _pick(row, PAGE_KEYS)
        if page is None or str(page).lower() in ("", "grand total"):
            continue
        rate = _num(_pick(row, ENGAGE_KEYS))
        if rate > 1:  # UI exports percentages, APIs export fractions
            rate /= 100
        out.append(
            {
                "page": str(page).split("?")[0],
                "sessions": int(_num(_pick(row, SESSION_KEYS))),
                "engagement_rate": round(rate, 3),
                "conversions": int(_num(_pick(row, CONV_KEYS))),
            }
        )
    out.sort(key=lambda r: -r["sessions"])
    return out


def analyse(rows, min_sessions=50):
    money_re = re.compile(MONEY_DEFAULT, re.IGNORECASE)
    engagement_gaps = [
        r
        for r in rows
        if r["sessions"] >= min_sessions and 0 < r["engagement_rate"] < 0.35
    ]
    money_no_conv = [
        r
        for r in rows
        if money_re.search(r["page"])
        and r["sessions"] >= max(20, min_sessions // 2)
        and r["conversions"] == 0
    ]
    return {
        "pages": len(rows),
        "sessions": sum(r["sessions"] for r in rows),
        "engagement_gaps": engagement_gaps,
        "money_no_conversions": money_no_conv,
    }


def as_findings(result):
    findings = []
    for r in result["engagement_gaps"][:MAX_FINDINGS]:
        findings.append(
            {
                "priority": "P2",
                "title": f"Engagement gap: {r['page']}",
                "description": f"{r['sessions']} sessions but only "
                f"{round(r['engagement_rate'] * 100)}% engagement — visitors arrive "
                "and leave. A content/UX problem, not a ranking problem.",
                "fix": "Match the page's opening to the queries that land here; "
                "check speed, intrusive elements, and intent fit.",
                "effort": "medium",
                "module": MODULE,
            }
        )
    for r in result["money_no_conversions"][:MAX_FINDINGS]:
        findings.append(
            {
                "priority": "P2",
                "title": f"Money page converting nothing: {r['page']}",
                "description": f"{r['sessions']} sessions, zero key events. Either "
                "conversion tracking is broken on this page or the page isn't "
                "persuading.",
                "fix": "Verify the key event fires here; if it does, rework the "
                "offer/CTA above the fold.",
                "effort": "medium",
                "module": MODULE,
            }
        )
    return findings


def main():
    ap = argparse.ArgumentParser(description="GA4 behaviour analysis")
    ap.add_argument("--data", required=True, help="GA4 landing-page CSV or JSON")
    ap.add_argument("--min-sessions", type=int, default=50)
    ap.add_argument("--json", action="store_true", help="emit punchlist-ready JSON")
    args = ap.parse_args()

    rows = load_rows(args.data)
    result = analyse(rows, args.min_sessions)
    findings = as_findings(result)

    if args.json:
        print(
            json.dumps(
                {
                    "findings": findings,
                    "module_scores": {
                        MODULE: {
                            "pages": result["pages"],
                            "sessions": result["sessions"],
                            "engagement_gaps": len(result["engagement_gaps"]),
                            "money_no_conversions": len(result["money_no_conversions"]),
                        }
                    },
                    "summary": {},
                },
                indent=2,
            )
        )
        return 0

    print(
        f"{result['pages']} landing pages · {result['sessions']} sessions · "
        f"{len(result['engagement_gaps'])} engagement gaps · "
        f"{len(result['money_no_conversions'])} money pages converting nothing"
    )
    for f in findings:
        print(f"\n{f['priority']} — {f['title']}")
        print(f"  {f['description']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
