#!/usr/bin/env python3
"""Internal-link opportunities: route authority from content to money pages.

Joins the real crawl link graph (sitecrawl.py's SQLite) with optional Search
Console data to find content pages that earn attention but never pass it on —
blog posts and guides with zero internal links to any money page (services,
products, pricing, booking). With GSC data, pages are ranked by real
impressions and matched to the best-fitting money page for each query.

This is graph analysis over the site's actual links, not guesswork over a
keyword tool's estimates.

Usage:
    python scripts/link_opportunities.py --db ./.fat-work/crawl/site.db \
        [--gsc ./.fat-work/gsc.json] [--money-pattern REGEX] [--content-pattern REGEX]
"""

import argparse
import json
import re
import sqlite3
import sys
from urllib.parse import urlparse

MODULE = "link_opportunities"
MAX_FINDINGS = 15

MONEY_DEFAULT = r"/(services?|pricing|products?|shop|store|book|booking|quote|get-started|contact|packages?|plans?)(/|$)"
CONTENT_DEFAULT = r"/(blog|guides?|resources?|news|articles?|learn|insights?)(/|$)"


def page_sets(con, money_re, content_re):
    money, content = [], []
    for (url,) in con.execute(
        "SELECT url FROM pages WHERE status=200 AND content_type='text/html'"
    ):
        path = urlparse(url).path
        if money_re.search(path):
            money.append(url)
        elif content_re.search(path):
            content.append(url)
    return money, content


def outlinks(con, source):
    return {
        row[0]
        for row in con.execute(
            "SELECT DISTINCT target FROM links WHERE source=? AND type='internal'",
            (source,),
        )
    }


def load_gsc(path):
    """query/page rows -> {page_url: [(query, impressions, position), ...]}"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("rows", data) if isinstance(data, dict) else data
    by_page = {}
    for r in rows or []:
        page = r.get("page") or r.get("url") or ""
        query = r.get("query") or r.get("keys", [""])[0]
        if not page or not query:
            continue
        by_page.setdefault(page, []).append(
            (query, r.get("impressions", 0), r.get("position", 0))
        )
    for page in by_page:
        by_page[page].sort(key=lambda t: -t[1])
    return by_page


def _terms(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - {
        "the",
        "a",
        "an",
        "in",
        "for",
        "and",
        "of",
        "to",
        "au",
        "com",
        "www",
    }


def best_money_target(queries, money_pages):
    """Money page whose URL shares the most terms with the page's top queries."""
    qterms = set()
    for q, _, _ in queries[:5]:
        qterms |= _terms(q)
    best, best_score = None, 0
    for m in money_pages:
        score = len(qterms & _terms(urlparse(m).path))
        if score > best_score:
            best, best_score = m, score
    return best


def analyse(con, money_re, content_re, gsc_by_page=None):
    money, content = page_sets(con, money_re, content_re)
    money_set = set(money)
    gaps = []
    for url in content:
        linked_money = outlinks(con, url) & money_set
        if linked_money:
            continue
        queries = (gsc_by_page or {}).get(url, [])
        impressions = sum(q[1] for q in queries)
        gaps.append(
            {
                "url": url,
                "impressions": impressions,
                "top_queries": [q[0] for q in queries[:3]],
                "suggested_target": (
                    best_money_target(queries, money)
                    if queries
                    else (money[0] if money else None)
                ),
            }
        )
    gaps.sort(key=lambda g: -g["impressions"])
    return {
        "money_pages": len(money),
        "content_pages": len(content),
        "gaps": gaps,
    }


def as_findings(result) -> list:
    findings = []
    for g in result["gaps"][:MAX_FINDINGS]:
        path = urlparse(g["url"]).path
        desc = "This content page links to zero money pages — authority it earns stops here."
        if g["impressions"]:
            desc += f" It earns {g['impressions']} search impressions"
            if g["top_queries"]:
                desc += f" (top queries: {', '.join(g['top_queries'])})"
            desc += "."
        fix = "Add a contextual internal link to the most relevant money page"
        if g["suggested_target"]:
            fix += f" — suggested: {g['suggested_target']}"
        findings.append(
            {
                "priority": "P2",
                "title": f"Money-page link gap: {path}",
                "description": desc,
                "fix": fix,
                "effort": "low",
                "module": MODULE,
            }
        )
    hidden = len(result["gaps"]) - len(findings)
    if hidden > 0:
        findings.append(
            {
                "priority": "P3",
                "title": "Further money-page link gaps",
                "description": f"{hidden} more content pages link to zero money pages "
                "(showing the top pages only — query the crawl DB for the rest).",
                "fix": "Work through the remainder after the top pages are linked.",
                "effort": "medium",
                "module": MODULE,
            }
        )
    return findings


def main():
    ap = argparse.ArgumentParser(description="internal-link opportunity analysis")
    ap.add_argument("--db", required=True, help="sitecrawl.py site.db")
    ap.add_argument("--gsc", default="", help="GSC export json (query/page rows)")
    ap.add_argument("--money-pattern", default=MONEY_DEFAULT)
    ap.add_argument("--content-pattern", default=CONTENT_DEFAULT)
    ap.add_argument("--json", action="store_true", help="emit punchlist-ready JSON")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    try:
        gsc = load_gsc(args.gsc) if args.gsc else None
        result = analyse(
            con,
            re.compile(args.money_pattern, re.IGNORECASE),
            re.compile(args.content_pattern, re.IGNORECASE),
            gsc,
        )
    finally:
        con.close()

    findings = as_findings(result)
    if args.json:
        print(
            json.dumps(
                {
                    "findings": findings,
                    "module_scores": {
                        MODULE: {
                            "money_pages": result["money_pages"],
                            "content_pages": result["content_pages"],
                            "gaps": len(result["gaps"]),
                        }
                    },
                    "summary": {},
                },
                indent=2,
            )
        )
        return 0

    print(
        f"{result['content_pages']} content pages · {result['money_pages']} money pages · "
        f"{len(result['gaps'])} with zero money-page links"
    )
    for f in findings:
        print(f"\n{f['priority']} — {f['title']}")
        print(f"  {f['description']}")
        print(f"  Fix: {f['fix']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
