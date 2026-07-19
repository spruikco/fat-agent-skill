#!/usr/bin/env python3
"""Site-level audit over a sitecrawl.py database.

Runs the checks that only make sense across a whole crawl — duplicate titles/
descriptions/content, orphan pages, broken internal links, site-wide status
and speed problems — and emits standard FAT findings that flow straight into
the punch list and reports.

Finding titles are deliberately stable (counts live in the description), so
punchlist.py's (module, title) identity holds across re-crawls and resolved
items auto-close on a clean rescan.

Usage:
    python scripts/sitewide.py --db ./.fat-work/crawl/site.db            # human
    python scripts/sitewide.py --db ./.fat-work/crawl/site.db --json \
        > ./.fat-work/sitewide.json                                      # for punchlist
    python scripts/punchlist.py update --scores ./.fat-work/sitewide.json

Drill-down (SELECT-only, capped rows — token-cheap by design):
    python scripts/sitewide.py --db site.db \
        --query "SELECT url,title FROM pages WHERE title_len>60"
"""

import argparse
import json
import sqlite3
import sys

MODULE = "sitewide"
SAMPLE_LIMIT = 8  # example URLs per finding — enough to act on, cheap to read
QUERY_ROW_CAP = 50

# (key, priority, title, why, fix, effort, count_sql, sample_sql)
CHECKS = [
    (
        "server_5xx",
        "P0",
        "Server errors (5xx) found in crawl",
        "5xx responses block indexing and signal instability to crawlers.",
        "Check server logs for the failing routes and fix the underlying errors.",
        "high",
        "SELECT COUNT(*) FROM pages WHERE status>=500",
        "SELECT url FROM pages WHERE status>=500",
    ),
    (
        "broken_internal_links",
        "P0",
        "Internal links point at broken pages",
        "Links to dead pages leak link equity, waste crawl budget, and dead-end "
        "users.",
        "Update or remove each link, or restore/redirect the target page.",
        "medium",
        "SELECT COUNT(*) FROM links l JOIN pages p ON p.url=l.target "
        "WHERE l.type='internal' AND p.status>=400 AND p.status NOT IN (403,429)",
        "SELECT DISTINCT l.source || '  ->  ' || l.target FROM links l "
        "JOIN pages p ON p.url=l.target "
        "WHERE l.type='internal' AND p.status>=400 AND p.status NOT IN (403,429)",
    ),
    (
        "broken_4xx",
        "P1",
        "Broken pages (4xx) found in crawl",
        "Reachable dead pages frustrate users and waste crawl budget.",
        "Restore the page, 301 it to the best replacement, or remove links to it.",
        "medium",
        "SELECT COUNT(*) FROM pages WHERE status>=400 AND status<500 "
        "AND status NOT IN (403,429)",
        "SELECT url FROM pages WHERE status>=400 AND status<500 "
        "AND status NOT IN (403,429)",
    ),
    (
        "fetch_errors",
        "P1",
        "Pages failed to fetch during crawl",
        "Timeouts and connection errors mean content is intermittently "
        "unreachable for users and crawlers.",
        "Investigate hosting stability / timeouts for the affected URLs.",
        "medium",
        "SELECT COUNT(*) FROM pages WHERE error IS NOT NULL "
        "AND error NOT LIKE 'blocked%'",
        "SELECT url || '  (' || error || ')' FROM pages WHERE error IS NOT NULL "
        "AND error NOT LIKE 'blocked%'",
    ),
    (
        "duplicate_title",
        "P1",
        "Duplicate titles across pages",
        "Pages sharing a title compete against each other and dilute relevance.",
        "Give each indexable page a unique, descriptive title.",
        "medium",
        "SELECT COALESCE(SUM(c-1),0) FROM (SELECT COUNT(*) c FROM pages "
        "WHERE indexable=1 AND title IS NOT NULL AND title<>'' "
        "GROUP BY title HAVING c>1)",
        "SELECT title || '  (' || COUNT(*) || ' pages)' FROM pages "
        "WHERE indexable=1 AND title IS NOT NULL AND title<>'' "
        "GROUP BY title HAVING COUNT(*)>1 ORDER BY COUNT(*) DESC",
    ),
    (
        "duplicate_content",
        "P1",
        "Duplicate page content across URLs",
        "Identical body content on multiple URLs splits ranking signals between "
        "them.",
        "Consolidate with canonicals or 301s, or differentiate the content.",
        "medium",
        "SELECT COALESCE(SUM(c-1),0) FROM (SELECT COUNT(*) c FROM pages "
        "WHERE indexable=1 AND content_hash IS NOT NULL "
        "GROUP BY content_hash HAVING c>1)",
        "SELECT GROUP_CONCAT(url, '  =  ') FROM pages "
        "WHERE indexable=1 AND content_hash IS NOT NULL "
        "GROUP BY content_hash HAVING COUNT(*)>1",
    ),
    (
        "duplicate_meta_desc",
        "P2",
        "Duplicate meta descriptions across pages",
        "Unique descriptions lift click-through from search results.",
        "Write a unique description for each indexable page.",
        "medium",
        "SELECT COALESCE(SUM(c-1),0) FROM (SELECT COUNT(*) c FROM pages "
        "WHERE indexable=1 AND meta_desc IS NOT NULL AND meta_desc<>'' "
        "GROUP BY meta_desc HAVING c>1)",
        "SELECT meta_desc || '  (' || COUNT(*) || ' pages)' FROM pages "
        "WHERE indexable=1 AND meta_desc IS NOT NULL AND meta_desc<>'' "
        "GROUP BY meta_desc HAVING COUNT(*)>1 ORDER BY COUNT(*) DESC",
    ),
    (
        "orphan_pages",
        "P2",
        "Orphan pages (no inbound internal links)",
        "Pages with no internal links in are hard for users and crawlers to "
        "discover, and rarely rank.",
        "Link to each orphan from relevant pages (navigation, related content, "
        "or hub pages).",
        "medium",
        "SELECT COUNT(*) FROM pages p WHERE p.status=200 "
        "AND p.content_type='text/html' AND NOT EXISTS "
        "(SELECT 1 FROM links l WHERE l.type='internal' AND l.target=p.url)",
        "SELECT url FROM pages p WHERE p.status=200 "
        "AND p.content_type='text/html' AND NOT EXISTS "
        "(SELECT 1 FROM links l WHERE l.type='internal' AND l.target=p.url)",
    ),
    (
        "thin_content",
        "P2",
        "Thin content pages across the site",
        "Indexable pages under 200 words rarely rank and can read as "
        "low-quality at site level.",
        "Expand, merge, or noindex the thin pages.",
        "high",
        "SELECT COUNT(*) FROM pages WHERE indexable=1 AND word_count>0 "
        "AND word_count<200",
        "SELECT url || '  (' || word_count || ' words)' FROM pages "
        "WHERE indexable=1 AND word_count>0 AND word_count<200 "
        "ORDER BY word_count",
    ),
    (
        "slow_pages",
        "P2",
        "Slow server responses (>2s) in crawl",
        "Slow responses drag Core Web Vitals and crawl rate down site-wide.",
        "Profile the slow routes (server timing, caching, database queries).",
        "high",
        "SELECT COUNT(*) FROM pages WHERE response_ms>2000",
        "SELECT url || '  (' || response_ms || 'ms)' FROM pages "
        "WHERE response_ms>2000 ORDER BY response_ms DESC",
    ),
    (
        "internal_redirects",
        "P3",
        "Internal links resolve through redirects",
        "Redirect hops slow crawling and users; internal links should point at "
        "final URLs.",
        "Update internal links to link the destination URL directly.",
        "low",
        "SELECT COUNT(*) FROM pages WHERE status>=300 AND status<400",
        "SELECT url || '  ->  ' || COALESCE(redirect_to,'?') FROM pages "
        "WHERE status>=300 AND status<400",
    ),
]


def run_checks(con) -> list:
    findings = []
    for key, priority, title, why, fix, effort, count_sql, sample_sql in CHECKS:
        count = con.execute(count_sql).fetchone()[0] or 0
        if not count:
            continue
        samples = [str(r[0]) for r in con.execute(sample_sql).fetchmany(SAMPLE_LIMIT)]
        shown = "; ".join(samples)
        more = count - len(samples)
        description = f"{count} affected. {why}"
        if shown:
            description += f" Examples: {shown}"
            if more > 0:
                description += f" (+{more} more — query the crawl DB for the full list)"
        findings.append(
            {
                "priority": priority,
                "title": title,
                "description": description,
                "fix": fix,
                "effort": effort,
                "module": MODULE,
                "count": count,
                "key": key,
            }
        )
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    findings.sort(key=lambda f: order.get(f["priority"], 9))
    return findings


def crawl_stats(con) -> dict:
    def q1(sql):
        return con.execute(sql).fetchone()[0]

    return {
        "pages": q1("SELECT COUNT(*) FROM pages"),
        "indexable": q1("SELECT COUNT(*) FROM pages WHERE indexable=1"),
        "internal_links": q1("SELECT COUNT(*) FROM links WHERE type='internal'"),
        "in_sitemap": q1("SELECT COUNT(*) FROM pages WHERE in_sitemap=1"),
    }


def as_scores_shape(findings: list, stats: dict) -> dict:
    """Package findings in the scores.json shape punchlist.py consumes.

    module_scores carries a 'sitewide' entry so the punch list treats the
    module as scanned — a clean re-crawl then auto-resolves fixed findings.
    """
    return {
        "findings": findings,
        "module_scores": {MODULE: {"checks_run": len(CHECKS), "stats": stats}},
        "summary": {},
    }


def format_human(findings: list, stats: dict) -> str:
    lines = [
        f"Site-wide audit — {stats['pages']} pages crawled, "
        f"{stats['indexable']} indexable, {stats['internal_links']} internal links"
    ]
    if not findings:
        lines.append("No site-level issues found.")
    for f in findings:
        lines.append(f"\n{f['priority']} — {f['title']} ({f['count']} affected)")
        lines.append(f"  {f['description']}")
        lines.append(f"  Fix: {f['fix']}")
    return "\n".join(lines)


def run_query(con, sql: str) -> list:
    """SELECT-only, row-capped drill-down."""
    if not sql.strip().lower().startswith("select"):
        raise ValueError("only SELECT queries are allowed")
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchmany(QUERY_ROW_CAP)
    return [dict(zip(cols, r)) for r in rows]


def main():
    ap = argparse.ArgumentParser(description="site-level audit over a crawl DB")
    ap.add_argument("--db", required=True, help="path to sitecrawl.py site.db")
    ap.add_argument("--json", action="store_true", help="emit punchlist-ready JSON")
    ap.add_argument("--query", help="run a capped SELECT against the crawl DB")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    try:
        if args.query:
            try:
                print(json.dumps(run_query(con, args.query), indent=2, default=str))
            except (ValueError, sqlite3.Error) as e:
                print(json.dumps({"error": str(e)}))
                return 1
            return 0

        findings = run_checks(con)
        stats = crawl_stats(con)
        if args.json:
            print(json.dumps(as_scores_shape(findings, stats), indent=2))
        else:
            print(format_human(findings, stats))
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
