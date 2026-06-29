#!/usr/bin/env python3
"""Google Search Console behavioural analysis for fat-agent.

The 2024 Content Warehouse leak confirmed NavBoost — Google's click-based system
(CTR, dwell, last-longest-click) is one of its strongest ranking inputs. A URL-only
audit can't see it, but GSC can. This turns a GSC performance export into the
behavioural insights that matter:

- **Striking-distance** keywords (positions ~5-20 with real impressions): the
  fastest ranking wins.
- **Low-CTR** queries (good position, click-through well below the positional
  benchmark): a title/meta/intent problem, not a ranking one.
- **Impressions, ~no clicks**: snippet or intent mismatch.
- **Branded vs non-branded** share: a proxy for brand strength.

It also emits `opportunity_keywords` in the shape generate-report.py consumes, so
GSC wins flow straight into the deck.

Input is a GSC performance export (no API/auth here — fetch the rows via the GSC
MCP, the Search Console API, or a manual CSV→JSON export, then pass them in).
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys

# Rough organic CTR-by-position benchmark (desktop+mobile blended).
_CTR_BENCHMARK = {
    1: 0.27,
    2: 0.15,
    3: 0.11,
    4: 0.08,
    5: 0.06,
    6: 0.045,
    7: 0.035,
    8: 0.03,
    9: 0.025,
    10: 0.022,
}


def ctr_benchmark(position):
    """Expected CTR for an average organic result at this position."""
    if position is None:
        return 0.0
    p = int(round(position))
    if p <= 1:
        return _CTR_BENCHMARK[1]
    if p in _CTR_BENCHMARK:
        return _CTR_BENCHMARK[p]
    if p <= 20:
        return 0.015
    return 0.008


def load_rows(data):
    """Normalise GSC export shapes into a list of row dicts.

    Accepts: a list of rows, {"rows": [...]}, or the GSC API shape where each row
    has {"keys": [query, ...], clicks, impressions, ctr, position}.
    """
    if isinstance(data, dict):
        data = data.get("rows", data.get("data", []))
    rows = []
    for r in data or []:
        if not isinstance(r, dict):
            continue
        query = r.get("query")
        page = r.get("page")
        if query is None and isinstance(r.get("keys"), list) and r["keys"]:
            query = r["keys"][0]
            if len(r["keys"]) > 1:
                page = r["keys"][1]
        clicks = float(r.get("clicks", 0) or 0)
        impressions = float(r.get("impressions", 0) or 0)
        ctr = r.get("ctr")
        ctr = (
            float(ctr)
            if ctr is not None
            else (clicks / impressions if impressions else 0.0)
        )
        position = r.get("position")
        position = float(position) if position is not None else None
        rows.append(
            {
                "query": query or "",
                "page": page or "",
                "clicks": clicks,
                "impressions": impressions,
                "ctr": ctr,
                "position": position,
            }
        )
    return rows


def is_branded(query, brand_terms):
    q = (query or "").lower()
    return any(b for b in brand_terms if b and b in q)


def analyse(rows, brand_terms=None, min_impressions=10):
    brand_terms = [b.lower().strip() for b in (brand_terms or []) if b.strip()]
    rows = [r for r in rows if r["query"]]

    total_clicks = sum(r["clicks"] for r in rows)
    total_impr = sum(r["impressions"] for r in rows)
    positioned = [r for r in rows if r["position"] is not None]
    avg_position = (
        sum(r["position"] * r["impressions"] for r in positioned)
        / sum(r["impressions"] for r in positioned)
        if any(r["impressions"] for r in positioned)
        else None
    )

    branded_clicks = sum(
        r["clicks"] for r in rows if is_branded(r["query"], brand_terms)
    )
    branded_share = (branded_clicks / total_clicks) if total_clicks else None

    striking = [
        r
        for r in rows
        if r["position"] is not None
        and 4.5 < r["position"] <= 20
        and r["impressions"] >= min_impressions
    ]
    striking.sort(key=lambda r: r["impressions"], reverse=True)

    low_ctr = [
        r
        for r in rows
        if r["position"] is not None
        and r["position"] <= 10
        and r["impressions"] >= max(min_impressions, 20)
        and r["ctr"] < 0.5 * ctr_benchmark(r["position"])
    ]
    low_ctr.sort(key=lambda r: r["impressions"], reverse=True)

    no_clicks = [
        r
        for r in rows
        if r["clicks"] == 0 and r["impressions"] >= max(min_impressions, 20)
    ]
    no_clicks.sort(key=lambda r: r["impressions"], reverse=True)

    # report-compatible opportunity_keywords (top striking-distance wins)
    opportunity_keywords = [
        {
            "keyword": r["query"],
            "volume": int(r["impressions"]),
            "position": round(r["position"], 1),
            "url": r["page"],
            "priority": "high" if r["position"] <= 10 else "medium",
        }
        for r in striking[:20]
    ]

    return {
        "available": True,
        "summary": {
            "total_clicks": int(total_clicks),
            "total_impressions": int(total_impr),
            "avg_ctr": round(total_clicks / total_impr, 4) if total_impr else None,
            "avg_position": (
                round(avg_position, 1) if avg_position is not None else None
            ),
            "branded_share": (
                round(branded_share, 3) if branded_share is not None else None
            ),
            "query_count": len(rows),
        },
        "striking_distance": [_slim(r) for r in striking[:25]],
        "low_ctr": [_slim(r, ctr_benchmark(r["position"])) for r in low_ctr[:25]],
        "impressions_no_clicks": [_slim(r) for r in no_clicks[:25]],
        "opportunity_keywords": opportunity_keywords,
    }


def _slim(r, benchmark=None):
    out = {
        "query": r["query"],
        "page": r["page"],
        "clicks": int(r["clicks"]),
        "impressions": int(r["impressions"]),
        "ctr": round(r["ctr"], 4),
        "position": round(r["position"], 1) if r["position"] is not None else None,
    }
    if benchmark is not None:
        out["benchmark_ctr"] = round(benchmark, 4)
    return out


def build_parser():
    p = argparse.ArgumentParser(
        description="Analyse a GSC performance export for behavioural SEO wins."
    )
    p.add_argument("--data", help="GSC export JSON file (default: stdin)")
    p.add_argument(
        "--brand",
        action="append",
        default=[],
        help="Brand term(s) for branded-share (repeatable)",
    )
    p.add_argument(
        "--min-impressions",
        type=int,
        default=10,
        help="Min impressions to consider (default: 10)",
    )
    p.add_argument(
        "--output", default=None, help="Write JSON to this file instead of stdout"
    )
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    raw = open(args.data, encoding="utf-8").read() if args.data else sys.stdin.read()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Invalid GSC JSON: {exc}", file=sys.stderr)
        sys.exit(1)
    result = analyse(
        load_rows(data), brand_terms=args.brand, min_impressions=args.min_impressions
    )
    text = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"GSC analysis written to {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
