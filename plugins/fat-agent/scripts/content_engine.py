#!/usr/bin/env python3
"""The Content Engine — turn search data into a prioritised content roadmap.

The audit layers find what's broken; this finds what's missing. It clusters
real GSC queries into topics (hub-and-spoke), maps each cluster against the
site's actual pages (GSC page data + the crawl inventory), and classifies
every cluster into an action:

  defend       ranking top-10 — keep it strong
  optimise     striking distance (pos 5–20) — title/meta/content polish
  rework       covered but weak (pos >20) — substantial improvement
  consolidate  cannibalised — multiple pages split one cluster's demand
  create       real demand, no dedicated page — new content brief
  refresh      clicks decayed vs a previous period (needs --previous)

Each `create`/`rework` gets a brief skeleton: working title, target queries,
suggested H2s from the cluster's own long-tails, and a suggested money-page
link. Claude drafts the full briefs/outlines from this data — the script
supplies evidence, not prose.

Usage:
    python scripts/content_engine.py --gsc ./.fat-work/gsc.json \
        [--db ./.fat-work/crawl/site.db] [--previous ./.fat-work/gsc-prev.json] \
        [--brand "acme"] [--json | --roadmap ./.fat-work/roadmap.json]
"""

import argparse
import csv
import io
import json
import re
import sqlite3
import sys
import zipfile
from urllib.parse import urlparse

from link_opportunities import MONEY_DEFAULT, _terms, best_money_target

MODULE = "content_engine"
MAX_QUERIES = 5000
JACCARD_JOIN = 0.5
MAX_BRIEF_FINDINGS = 12
DECAY_DROP = 0.4


def _num(v):
    """GSC UI exports write '1,234' and '3.4%' — parse both."""
    s = str(v or "0").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0


def _rows_from_csv(text):
    """Parse a GSC UI 'Queries.csv' (or any csv with query/clicks/impressions/
    position columns). 'Top queries' is what the UI export calls the column."""
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for row in reader:
        r = {(k or "").strip().lower(): v for k, v in row.items()}
        q = r.get("top queries") or r.get("query") or r.get("queries")
        if not q:
            continue
        out.append(
            {
                "query": q,
                "page": r.get("page") or r.get("top pages") or "",
                "clicks": int(_num(r.get("clicks"))),
                "impressions": int(_num(r.get("impressions"))),
                "position": _num(r.get("position")),
            }
        )
    return out


def load_rows(path):
    """Accept whatever the user has: the GSC UI export ZIP as downloaded,
    a Queries.csv from inside it, or API/MCP JSON. Zero reshaping required."""
    lower = path.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            name = next(
                (n for n in z.namelist() if "quer" in n.lower() and n.endswith(".csv")),
                None,
            )
            if not name:
                raise SystemExit("No queries CSV found inside the GSC export zip")
            data = _rows_from_csv(z.read(name).decode("utf-8-sig", errors="replace"))
    elif lower.endswith(".csv"):
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            data = _rows_from_csv(f.read())
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    rows = data.get("rows", data) if isinstance(data, dict) else data
    out = []
    for r in rows or []:
        q = r.get("query") or (r.get("keys") or [""])[0]
        if not q:
            continue
        out.append(
            {
                "query": q.lower().strip(),
                "page": r.get("page") or "",
                "clicks": r.get("clicks", 0) or 0,
                "impressions": r.get("impressions", 0) or 0,
                "position": float(r.get("position", 0) or 0),
            }
        )
    out.sort(key=lambda r: -r["impressions"])
    return out[:MAX_QUERIES]


def _stem(term):
    return term[:-1] if len(term) > 3 and term.endswith("s") else term


def qterms(query, brand_terms):
    return {_stem(t) for t in _terms(query)} - brand_terms


def cluster_queries(rows, brand=""):
    """Greedy Jaccard clustering, seeded by impression-ranked queries."""
    brand_terms = {_stem(t) for t in _terms(brand)} if brand else set()
    clusters = []
    for r in rows:
        terms = qterms(r["query"], brand_terms)
        if not terms:
            continue
        placed = False
        for c in clusters:
            union = c["terms"] | terms
            if union and len(c["terms"] & terms) / len(union) >= JACCARD_JOIN:
                c["rows"].append(r)
                c["terms"] |= terms
                placed = True
                break
        if not placed:
            clusters.append({"label": r["query"], "terms": set(terms), "rows": [r]})
    return clusters


def crawl_inventory(db_path):
    """Existing pages + money pages from the crawl DB (optional but better)."""
    money_re = re.compile(MONEY_DEFAULT, re.IGNORECASE)
    pages, money = {}, []
    con = sqlite3.connect(db_path)
    try:
        for url, title, wc in con.execute(
            "SELECT url, title, word_count FROM pages "
            "WHERE status=200 AND content_type='text/html'"
        ):
            pages[url] = {"title": title or "", "word_count": wc or 0}
            if money_re.search(urlparse(url).path):
                money.append(url)
    finally:
        con.close()
    return pages, money


def classify(cluster, prev_clicks=None):
    rows = cluster["rows"]
    impressions = sum(r["impressions"] for r in rows)
    clicks = sum(r["clicks"] for r in rows)
    by_page = {}
    for r in rows:
        if r["page"]:
            by_page.setdefault(r["page"], 0)
            by_page[r["page"]] += r["impressions"]
    pages = sorted(by_page.items(), key=lambda kv: -kv[1])
    weighted_pos = (
        sum(r["position"] * r["impressions"] for r in rows) / impressions
        if impressions
        else 0
    )

    if (
        prev_clicks is not None
        and prev_clicks > 20
        and clicks < prev_clicks * (1 - DECAY_DROP)
    ):
        action = "refresh"
    elif len(pages) >= 2 and pages[1][1] >= impressions * 0.2:
        action = "consolidate"
    elif not pages:
        action = "create"
    elif weighted_pos and weighted_pos <= 4.5:
        action = "defend"
    elif weighted_pos <= 20:
        action = "optimise"
    else:
        action = "rework"

    return {
        "label": cluster["label"],
        "action": action,
        "impressions": impressions,
        "clicks": clicks,
        "avg_position": round(weighted_pos, 1),
        "queries": [r["query"] for r in rows[:8]],
        "pages": [p for p, _ in pages[:3]],
    }


def infer_pages(rows, inventory):
    """UI exports lack query→page pairs; recover them from the crawl.

    Best term-overlap match of each query against page URL slugs + titles.
    Marks inferred rows so downstream copy can stay honest about certainty.
    """
    if not inventory:
        return rows
    page_terms = {
        url: _terms(urlparse(url).path.replace("-", " ") + " " + meta["title"])
        for url, meta in inventory.items()
    }
    for r in rows:
        if r["page"]:
            continue
        qt = {_stem(t) for t in _terms(r["query"])}
        best, best_n = "", 0
        for url, terms in page_terms.items():
            n = len(qt & {_stem(t) for t in terms})
            if n > best_n:
                best, best_n = url, n
        if best_n >= 2 or (qt and best_n == len(qt)):
            r["page"] = best
            r["inferred"] = True
    return rows


def build_roadmap(rows, brand="", db_path="", prev_rows=None):
    if db_path:
        inv, _ = crawl_inventory(db_path)
        rows = infer_pages(rows, inv)
        if prev_rows:
            prev_rows = infer_pages(prev_rows, inv)
    clusters = cluster_queries(rows, brand)
    prev_by_label = {}
    if prev_rows:
        for c in cluster_queries(prev_rows, brand):
            prev_by_label[c["label"]] = sum(r["clicks"] for r in c["rows"])

    inventory, money = ({}, [])
    if db_path:
        inventory, money = crawl_inventory(db_path)

    items = []
    for c in clusters:
        item = classify(c, prev_by_label.get(c["label"]))
        if item["action"] in ("create", "rework", "refresh"):
            head = item["queries"][0] if item["queries"] else item["label"]
            item["brief"] = {
                "working_title": head.title()[:60],
                "target_queries": item["queries"][:5],
                "suggested_h2s": [q.capitalize() for q in item["queries"][1:6]],
                "link_to_money_page": (
                    best_money_target([(q, 1, 0) for q in item["queries"][:5]], money)
                    if money
                    else None
                ),
            }
        items.append(item)

    items.sort(key=lambda i: -i["impressions"])
    summary = {}
    for i in items:
        summary[i["action"]] = summary.get(i["action"], 0) + 1
    return {"clusters": items, "summary": summary, "total_queries": len(rows)}


ACTION_FINDING = {
    "create": ("P1", "New content: no page answers this demand"),
    "rework": ("P2", "Rework: page exists but ranks nowhere"),
    "consolidate": ("P2", "Consolidate: pages cannibalising each other"),
    "refresh": ("P2", "Refresh: cluster traffic has decayed"),
}


def as_findings(roadmap):
    findings = []
    actionable = [c for c in roadmap["clusters"] if c["action"] in ACTION_FINDING]
    for c in actionable[:MAX_BRIEF_FINDINGS]:
        priority, stem = ACTION_FINDING[c["action"]]
        desc = (
            f"Topic “{c['label']}”: {c['impressions']} impressions, "
            f"{c['clicks']} clicks, avg position {c['avg_position'] or 'n/a'}. "
            f"Queries: {', '.join(c['queries'][:4])}."
        )
        fix = "Draft from the brief in the roadmap"
        brief = c.get("brief") or {}
        if brief.get("working_title"):
            fix = f"Brief: “{brief['working_title']}”"
            if brief.get("link_to_money_page"):
                fix += f"; link to {brief['link_to_money_page']}"
        elif c["action"] == "consolidate" and len(c["pages"]) >= 2:
            fix = f"Merge/canonicalise: {c['pages'][0]} ← {c['pages'][1]}"
        findings.append(
            {
                "priority": priority,
                "title": f"{stem}: {c['label']}",
                "description": desc,
                "fix": fix,
                "effort": "high" if c["action"] in ("create", "rework") else "medium",
                "module": MODULE,
            }
        )
    return findings


def main():
    ap = argparse.ArgumentParser(description="content engine — search data to roadmap")
    ap.add_argument("--gsc", required=True, help="GSC export json (query/page rows)")
    ap.add_argument("--db", default="", help="sitecrawl site.db (page inventory)")
    ap.add_argument("--previous", default="", help="earlier-period GSC export (decay)")
    ap.add_argument(
        "--brand", default="", help="brand terms to exclude from clustering"
    )
    ap.add_argument("--roadmap", default="", help="write full roadmap JSON here")
    ap.add_argument("--json", action="store_true", help="emit punchlist-ready JSON")
    args = ap.parse_args()

    rows = load_rows(args.gsc)
    prev = load_rows(args.previous) if args.previous else None
    roadmap = build_roadmap(rows, args.brand, args.db, prev)

    if args.roadmap:
        with open(args.roadmap, "w", encoding="utf-8") as f:
            json.dump(roadmap, f, indent=2)

    if args.json:
        print(
            json.dumps(
                {
                    "findings": as_findings(roadmap),
                    "module_scores": {MODULE: {"summary": roadmap["summary"]}},
                    "summary": {},
                },
                indent=2,
            )
        )
        return 0

    s = roadmap["summary"]
    print(
        f"{roadmap['total_queries']} queries -> {len(roadmap['clusters'])} topic clusters: "
        + ", ".join(f"{v} {k}" for k, v in sorted(s.items()))
    )
    for c in roadmap["clusters"][:15]:
        line = (
            f"  [{c['action']:<11}] {c['label']}  · {c['impressions']} imp "
            f"· pos {c['avg_position'] or '-'}"
        )
        print(line)
        if c.get("brief"):
            print(f"               brief: {c['brief']['working_title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
