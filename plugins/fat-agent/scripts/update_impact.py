#!/usr/bin/env python3
"""Line a traffic series up against Google's named ranking/spam updates.

"Why did we drop?" is the first question after a core or spam update, and the
answer starts with a date. This takes a clicks (or traffic) time series and
reports, for each Google update, the change from the window before it to the
window after its rollout, ranking the updates by impact. It turns
"traffic fell sometime in winter" into "down 48% across the June 2026 spam
update window", which points at the right FAT findings (see
references/google-guidelines.md).

Input (auto-detected, file or stdin):
- GSC Performance export with a date dimension: rows of {"keys": ["2026-06-01"],
  "clicks": 12, ...} or {"date": "2026-06-01", "clicks": 12}.
- SEMrush domain_rank_history text/CSV (Date;Rank;Organic Keywords;Organic
  Traffic;...), monthly rows like 20260615 — coarse, but it works.
- A plain list of {"date": ..., "value": ...}.

Usage:
    python scripts/update_impact.py --data gsc_by_date.json
    python scripts/update_impact.py --data semrush_history.csv --since 2025-01-01
    python scripts/update_impact.py --data gsc_by_date.json --json > .fat-work/update_impact.json

Correlation, not causation: word findings as "consistent with", never
"caused by". Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
import sys

MODULE = "update_impact"

# (name, start, rollout days, kind) — from the Google Search Status Dashboard.
GOOGLE_UPDATES = [
    ("March 2024 core update", "2024-03-05", 45, "core"),
    ("March 2024 spam update", "2024-03-05", 15, "spam"),
    ("June 2024 spam update", "2024-06-20", 7, "spam"),
    ("August 2024 core update", "2024-08-15", 19, "core"),
    ("November 2024 core update", "2024-11-11", 24, "core"),
    ("December 2024 core update", "2024-12-12", 6, "core"),
    ("December 2024 spam update", "2024-12-19", 7, "spam"),
    ("March 2025 core update", "2025-03-13", 14, "core"),
    ("June 2025 core update", "2025-06-30", 17, "core"),
    ("August 2025 spam update", "2025-08-26", 27, "spam"),
    ("December 2025 core update", "2025-12-11", 18, "core"),
    ("February 2026 Discover core update", "2026-02-05", 22, "discover"),
    ("March 2026 spam update", "2026-03-24", 1, "spam"),
    ("March 2026 core update", "2026-03-27", 12, "core"),
    ("May 2026 core update", "2026-05-21", 12, "core"),
    ("June 2026 spam update", "2026-06-24", 2, "spam"),
    ("August 2026 spam update", "2026-08-18", 3, "spam"),
]

# What to look at in the FAT findings when a drop lines up with each kind.
LOOK_AT = {
    "core": "site-wide quality: 'Templated near-duplicate pages', 'Large share of "
    "site is templated pages', thin content, E-E-A-T and content-depth findings",
    "spam": "spam-policy findings: doorway/scaled content, keyword stuffing, hidden "
    "text, sneaky redirects, back button hijacking, unqualified affiliate links, "
    "site reputation sections",
    "discover": "Discover readiness: large images, clickbait titles, originality",
}

WINDOW_DAYS = 28  # compare the 4 weeks before start with the 4 weeks after rollout
DROP_PCT = -20.0  # a change at or below this is worth a finding


def _date(value) -> dt.date | None:
    s = str(value).strip()
    for pat, fmt in ((r"^\d{4}-\d{2}-\d{2}", "%Y-%m-%d"), (r"^\d{8}$", "%Y%m%d")):
        m = re.match(pat, s)
        if m:
            try:
                return dt.datetime.strptime(m.group(0), fmt).date()
            except ValueError:
                return None
    return None


def load_series(text: str) -> list:
    """Return [(date, value)] sorted by date from any supported input shape."""
    text = text.strip()
    points = []
    if text.startswith("{") or text.startswith("["):
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("rows", data.get("data", []))
        for r in data or []:
            if not isinstance(r, dict):
                continue
            d = r.get("date")
            if d is None and isinstance(r.get("keys"), list) and r["keys"]:
                d = r["keys"][0]
            v = r.get("clicks", r.get("value", r.get("traffic")))
            day = _date(d) if d is not None else None
            if day and v is not None:
                points.append((day, float(v)))
    else:  # SEMrush-style delimited text
        delim = ";" if text.count(";") >= text.count(",") else ","
        reader = csv.reader(io.StringIO(text), delimiter=delim)
        header = [h.strip().lower() for h in next(reader, [])]
        di = next((i for i, h in enumerate(header) if h in ("date", "dt")), 0)
        vi = next(
            (i for i, h in enumerate(header) if h in ("organic traffic", "ot", "clicks")),
            None,
        )
        if vi is None:
            vi = len(header) - 1
        for row in reader:
            if len(row) <= max(di, vi):
                continue
            day = _date(row[di])
            try:
                val = float(row[vi])
            except ValueError:
                continue
            if day:
                points.append((day, val))
    agg: dict = {}
    for d, v in points:  # GSC may repeat a date across pages/queries — sum them
        agg[d] = agg.get(d, 0.0) + v
    return sorted(agg.items())


def _granularity(series) -> int:
    if len(series) < 2:
        return 1
    gaps = sorted((b[0] - a[0]).days for a, b in zip(series, series[1:]))
    return gaps[len(gaps) // 2]


def _rate(series, start: dt.date, end: dt.date):
    """Average daily value over [start, end); None if no points fall inside."""
    vals = [v for d, v in series if start <= d < end]
    if not vals:
        return None
    return sum(vals) / len(vals)


def analyse(series: list, since: dt.date | None = None) -> dict:
    gran = _granularity(series)
    # monthly data (SEMrush) needs wider windows or every window is empty
    window = max(WINDOW_DAYS, gran * 2)
    first = series[0][0] if series else None
    last = series[-1][0] if series else None
    impacts = []
    for name, start_s, days, kind in GOOGLE_UPDATES:
        start = dt.date.fromisoformat(start_s)
        end = start + dt.timedelta(days=days)
        if since and start < since:
            continue
        if not first or start - dt.timedelta(days=window) < first or end > last:
            continue
        before = _rate(series, start - dt.timedelta(days=window), start)
        after = _rate(series, end, end + dt.timedelta(days=window))
        if before is None or after is None:
            continue
        change = ((after - before) / before * 100) if before else None
        impacts.append(
            {
                "update": name,
                "kind": kind,
                "start": start_s,
                "rollout_end": end.isoformat(),
                "before_avg": round(before, 1),
                "after_avg": round(after, 1),
                "change_pct": round(change, 1) if change is not None else None,
            }
        )
    impacts.sort(key=lambda i: (i["change_pct"] is None, i["change_pct"] or 0))
    findings = []
    for imp in impacts:
        if imp["change_pct"] is None or imp["change_pct"] > DROP_PCT:
            continue
        findings.append(
            {
                "priority": "P1" if imp["change_pct"] <= -40 else "P2",
                "title": f"Traffic drop across the {imp['update']}",
                "description": f"Average traffic went from {imp['before_avg']} to "
                f"{imp['after_avg']} ({imp['change_pct']}%) comparing the window "
                f"before {imp['start']} with the window after rollout ended "
                f"{imp['rollout_end']}. That's consistent with this "
                f"{imp['kind']} update affecting the site (correlation, not proof: "
                "check seasonality and site changes in the same window).",
                "fix": f"Prioritise {LOOK_AT[imp['kind']]}.",
                "effort": "high",
                "module": MODULE,
            }
        )
    return {
        "granularity_days": gran,
        "window_days": window,
        "series_start": first.isoformat() if first else None,
        "series_end": last.isoformat() if last else None,
        "impacts": impacts,
        "findings": findings,
    }


def format_human(res: dict) -> str:
    lines = [
        f"Update impact: {res['series_start']} to {res['series_end']} "
        f"({res['granularity_days']}-day points, ±{res['window_days']}-day windows)"
    ]
    if not res["impacts"]:
        lines.append("No Google update falls far enough inside the series to measure.")
    for i in res["impacts"]:
        pct = "n/a" if i["change_pct"] is None else f"{i['change_pct']:+.1f}%"
        lines.append(
            f"  {pct:>8}  {i['update']} ({i['start']}): "
            f"{i['before_avg']} -> {i['after_avg']}"
        )
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="traffic vs Google update timeline")
    ap.add_argument("--data", help="GSC-by-date JSON or SEMrush history (default stdin)")
    ap.add_argument("--since", help="ignore updates before YYYY-MM-DD")
    ap.add_argument("--json", action="store_true", help="punchlist-ready JSON")
    args = ap.parse_args(argv)
    text = open(args.data, encoding="utf-8").read() if args.data else sys.stdin.read()
    series = load_series(text)
    if not series:
        print(json.dumps({"error": "no dated rows found in input"}))
        return 1
    res = analyse(series, _date(args.since) if args.since else None)
    if args.json:
        out = {
            "findings": res["findings"],
            "module_scores": {MODULE: {"impacts": res["impacts"]}},
            "summary": {},
        }
        print(json.dumps(out, indent=2))
    else:
        print(format_human(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
