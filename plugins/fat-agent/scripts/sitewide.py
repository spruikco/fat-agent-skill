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
import os
import re
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules.google_guidelines import (  # noqa: E402
    META_MAX,
    META_MIN,
    RETIRED_RICH_RESULTS,
    TITLE_MAX,
    title_is_stuffed,
)

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
        "final URLs. (Only counts redirects that at least one internal link "
        "actually points at — sitemap-only redirects are a separate finding.)",
        "Update internal links to link the destination URL directly.",
        "low",
        "SELECT COUNT(*) FROM pages p WHERE p.status>=300 AND p.status<400 "
        "AND EXISTS (SELECT 1 FROM links l WHERE l.type='internal' "
        "AND l.target=p.url)",
        "SELECT p.url || '  ->  ' || COALESCE(p.redirect_to,'?') FROM pages p "
        "WHERE p.status>=300 AND p.status<400 "
        "AND EXISTS (SELECT 1 FROM links l WHERE l.type='internal' "
        "AND l.target=p.url)",
    ),
    (
        "sitemap_redirects",
        "P1",
        "Sitemap lists redirecting URLs",
        "Sitemaps must list final canonical URLs. Every redirecting entry "
        "makes crawlers pay an extra fetch per URL per crawl and delays "
        "discovery — and Google treats sitemap URLs as canonical hints.",
        "Regenerate the sitemap to emit final URLs. Check EVERY sitemap "
        "generator: sites often have several (e.g. a Next.js app/sitemap.ts "
        "route silently shadows public/sitemap.xml).",
        "low",
        "SELECT COUNT(*) FROM pages WHERE in_sitemap=1 "
        "AND status>=300 AND status<400",
        "SELECT url || '  ->  ' || COALESCE(redirect_to,'?') FROM pages "
        "WHERE in_sitemap=1 AND status>=300 AND status<400",
    ),
    (
        "slash_duplicates",
        "P1",
        "Same page indexable with and without trailing slash",
        "Both /page and /page/ return 200 and self-canonicalise, so Google sees two "
        "URLs competing for the same query and splits signals between them.",
        "Pick one form site-wide: 301 the other and make canonicals, sitemaps and "
        "internal links agree.",
        "low",
        "SELECT COUNT(*) FROM pages a JOIN pages b ON b.url = a.url || '/' "
        "WHERE a.status=200 AND b.status=200 AND a.indexable=1 AND b.indexable=1",
        "SELECT a.url || '  +  ' || b.url FROM pages a JOIN pages b "
        "ON b.url = a.url || '/' WHERE a.status=200 AND b.status=200 "
        "AND a.indexable=1 AND b.indexable=1",
    ),
    (
        "missing_title",
        "P1",
        "Indexable pages missing a title",
        "Without a title Google invents one from the page, usually badly.",
        "Give every indexable page a unique, descriptive title.",
        "low",
        "SELECT COUNT(*) FROM pages WHERE indexable=1 AND (title IS NULL OR title='')",
        "SELECT url FROM pages WHERE indexable=1 AND (title IS NULL OR title='')",
    ),
    (
        "missing_meta_desc",
        "P2",
        "Indexable pages missing a meta description",
        "Google falls back to scraping page text for the snippet, which rarely sells "
        "the click.",
        "Write a unique 120-160 character description for each page.",
        "medium",
        "SELECT COUNT(*) FROM pages WHERE indexable=1 "
        "AND (meta_desc IS NULL OR meta_desc='')",
        "SELECT url FROM pages WHERE indexable=1 AND (meta_desc IS NULL OR meta_desc='')",
    ),
    (
        "missing_h1",
        "P2",
        "Indexable pages missing an H1",
        "The H1 is one of the main signals Google uses to understand the page and to "
        "build its title link.",
        "Add one descriptive H1 per page.",
        "low",
        "SELECT COUNT(*) FROM pages WHERE indexable=1 AND COALESCE(h1_count,0)=0",
        "SELECT url FROM pages WHERE indexable=1 AND COALESCE(h1_count,0)=0",
    ),
    (
        "long_titles",
        "P3",
        "Titles likely truncated in results",
        f"Titles over {TITLE_MAX} characters get cut off, and long titles are "
        "rewritten by Google more often.",
        "Front-load the topic and trim to about 50-60 characters.",
        "low",
        f"SELECT COUNT(*) FROM pages WHERE indexable=1 AND title_len>{TITLE_MAX}",
        f"SELECT url || '  (' || title_len || ')' FROM pages WHERE indexable=1 "
        f"AND title_len>{TITLE_MAX} ORDER BY title_len DESC",
    ),
    (
        "meta_desc_length",
        "P3",
        "Meta descriptions too short or too long",
        f"Under {META_MIN} characters is usually replaced by Google; over {META_MAX} "
        "gets truncated.",
        "Aim for 120-160 characters that summarise the page and the reason to click.",
        "low",
        f"SELECT COUNT(*) FROM pages WHERE indexable=1 AND meta_desc_len>0 "
        f"AND (meta_desc_len<{META_MIN} OR meta_desc_len>{META_MAX})",
        f"SELECT url || '  (' || meta_desc_len || ')' FROM pages WHERE indexable=1 "
        f"AND meta_desc_len>0 AND (meta_desc_len<{META_MIN} OR meta_desc_len>{META_MAX})",
    ),
    (
        "sitemap_broken",
        "P1",
        "Sitemap lists broken URLs",
        "The sitemap is telling search engines to index URLs that do not "
        "exist. Usually a generator emitting page combinations that were "
        "never built.",
        "Fix the sitemap generator so it only emits URLs that resolve — "
        "audit any hardcoded city/service/category combination lists.",
        "medium",
        "SELECT COUNT(*) FROM pages WHERE in_sitemap=1 "
        "AND ((status>=400 AND status NOT IN (403,429)) "
        "OR (error IS NOT NULL AND error NOT LIKE 'blocked%'))",
        "SELECT url || '  (' || COALESCE(CAST(status AS TEXT), error) || ')' "
        "FROM pages WHERE in_sitemap=1 "
        "AND ((status>=400 AND status NOT IN (403,429)) "
        "OR (error IS NOT NULL AND error NOT LIKE 'blocked%'))",
    ),
]

# Systemic-pattern annotations: when most of a redirect finding is the SAME
# transformation (target = URL + '/'), the real bug is one link/sitemap
# generator, not N individual URLs — say so instead of listing them.
SLASH_HOP_SQL = {
    "internal_redirects": (
        "SELECT COUNT(*) FROM pages p WHERE p.status>=300 AND p.status<400 "
        "AND p.redirect_to = p.url || '/' "
        "AND EXISTS (SELECT 1 FROM links l WHERE l.type='internal' "
        "AND l.target=p.url)"
    ),
    "sitemap_redirects": (
        "SELECT COUNT(*) FROM pages WHERE in_sitemap=1 "
        "AND status>=300 AND status<400 AND redirect_to = url || '/'"
    ),
}


def run_checks(con, gsc: dict = None) -> list:
    findings = []
    for key, priority, title, why, fix, effort, count_sql, sample_sql in CHECKS:
        count = con.execute(count_sql).fetchone()[0] or 0
        if not count:
            continue
        samples = [str(r[0]) for r in con.execute(sample_sql).fetchmany(SAMPLE_LIMIT)]
        shown = "; ".join(samples)
        more = count - len(samples)
        description = f"{count} affected. {why}"
        if key in SLASH_HOP_SQL:
            hops = con.execute(SLASH_HOP_SQL[key]).fetchone()[0] or 0
            if hops:
                description += (
                    f" SYSTEMIC: {hops} of {count} are pure trailing-slash hops "
                    "(target = URL + '/') — one generator emits non-slash URLs; "
                    "fix it once rather than treating these as individual issues."
                )
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
    findings.extend(guideline_checks(con, gsc))
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    findings.sort(key=lambda f: order.get(f["priority"], 9))
    return findings


# --------------------------------------------------------------------------- #
# Google guideline patterns that only show up across a crawl
# --------------------------------------------------------------------------- #
NEAR_DUP_BITS = 8  # simhash Hamming distance: templates sit ~2-6 apart, unrelated ~30
MIN_CLUSTER = 3
SCALED_SHARE = 0.30  # share of indexable pages that are templated → site-level risk


def _columns(con) -> set:
    return {r[1] for r in con.execute("PRAGMA table_info(pages)")}


def _url_shape(urls: list) -> str:
    """Collapse a cluster's URLs into one pattern: /local/seo-agency-in-{*}/."""
    from urllib.parse import urlparse

    paths = [urlparse(u).path for u in urls]
    split = [p.strip("/").split("/") for p in paths]
    depth = Counter(len(x) for x in split).most_common(1)[0][0]
    same = [x for x in split if len(x) == depth]
    out = []
    for i in range(depth):
        segs = {x[i] for x in same}
        if len(segs) == 1:
            out.append(segs.pop())
            continue
        pre = os.path.commonprefix(list(segs))
        suf = os.path.commonprefix([x[::-1] for x in segs])[::-1]
        if len(pre) + len(suf) >= min(len(x) for x in segs):
            suf = ""
        out.append(pre + "{*}" + suf)
    return "/" + "/".join(out) + ("/" if paths[0].endswith("/") else "")


def near_duplicate_clusters(con) -> list:
    """Seed (leader) clustering over simhash fingerprints of indexable pages.

    Every member must be within NEAR_DUP_BITS of its cluster's seed page.
    Union-find was tried first and chained unrelated templates together
    through intermediate pages (A~B~C with A and C 19 bits apart), so a
    single-linkage approach over-reports; seeding keeps each group honest.

    Returns clusters (largest first) as dicts: urls, size, avg_words, shape.
    Older crawl DBs without a simhash column simply return [].
    """
    if "simhash" not in _columns(con):
        return []
    rows = con.execute(
        "SELECT url, simhash, COALESCE(main_word_count, word_count, 0) FROM pages "
        "WHERE indexable=1 AND simhash IS NOT NULL ORDER BY url"
    ).fetchall()
    seeds: list = []  # (hash, [row indexes])
    for i, row in enumerate(rows):
        h = int(row[1], 16)
        best, best_d = None, NEAR_DUP_BITS + 1
        for s in seeds:
            d = bin(h ^ s[0]).count("1")
            if d < best_d:
                best, best_d = s, d
        if best is None:
            seeds.append((h, [i]))
        else:
            best[1].append(i)
    # One template often yields several seeds (members drift past the threshold
    # from any single seed). Groups that are each internally near-identical AND
    # share a URL shape are the same template: report them as one line.
    by_shape: dict = {}
    for _, idxs in seeds:
        if len(idxs) < MIN_CLUSTER:
            continue
        shape = _url_shape([rows[i][0] for i in idxs])
        by_shape.setdefault(shape, []).extend(idxs)
    clusters = []
    for shape, idxs in by_shape.items():
        urls = sorted(rows[i][0] for i in idxs)
        words = [rows[i][2] for i in idxs]
        clusters.append(
            {
                "urls": urls,
                "size": len(urls),
                "avg_words": round(sum(words) / len(words)),
                "shape": shape,
            }
        )
    clusters.sort(key=lambda c: -c["size"])
    return clusters


# Topics that typically turn up as third-party "parasite" sections
_REPUTATION_RE = re.compile(
    r"(?:^|[/_-])(coupons?|promo-?codes?|discount-?codes?|vouchers?|casinos?|pokies|"
    r"betting|gambling|slots|payday|loans?|cbd|vapes?|essay|dating|crypto|"
    r"best-[a-z-]+-(?:reviews?|of-20\d\d)|sponsored|partners?-content)(?:$|[/_-])",
    re.IGNORECASE,
)


def reputation_sections(con, min_pages: int = 3) -> list:
    """First-path-segment sections whose URLs look like off-topic third-party
    content (coupons, casino, loans, CBD, 'best X' reviews)."""
    from urllib.parse import urlparse

    hits: Counter = Counter()
    for (url,) in con.execute("SELECT url FROM pages WHERE indexable=1"):
        path = urlparse(url).path
        if _REPUTATION_RE.search(path):
            seg = path.strip("/").split("/")[0]
            hits["/" + seg + "/"] += 1
    return [(s, c) for s, c in hits.most_common() if c >= min_pages]


# --------------------------------------------------------------------------- #
# Search Console cross-reference: real clicks decide keep / improve / prune
# --------------------------------------------------------------------------- #
KEEP_CLICKS = 1  # any real clicks in the export window = the page earns its place


def url_key(url: str) -> str:
    """Scheme-, www- and trailing-slash-insensitive key so GSC and crawl URLs meet."""
    from urllib.parse import urlparse

    u = urlparse(url.strip())
    host = u.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host + (u.path.rstrip("/") or "/") + (("?" + u.query) if u.query else "")


def load_gsc_pages(path: str) -> dict:
    """GSC Performance export (page dimension, or query+page) → {url_key: totals}.

    Accepts every shape gsc.py accepts. Rows are summed per page, so a
    query+page export works too; position is impression-weighted.
    """
    from gsc import load_rows

    with open(path, encoding="utf-8") as fh:
        rows = load_rows(json.load(fh))
    pages: dict = {}
    for r in rows:
        page = r.get("page") or ""
        if not page and str(r.get("query", "")).startswith("http"):
            page = r["query"]  # page-only export: the single key is the URL
        if not page:
            continue
        agg = pages.setdefault(
            url_key(page), {"clicks": 0.0, "impressions": 0.0, "_pos": 0.0}
        )
        agg["clicks"] += r["clicks"]
        agg["impressions"] += r["impressions"]
        if r.get("position") is not None:
            agg["_pos"] += r["position"] * r["impressions"]
    for agg in pages.values():
        imp = agg["impressions"]
        agg["position"] = round(agg.pop("_pos") / imp, 1) if imp else None
    return pages


def triage(urls: list, gsc: dict) -> dict:
    """Split URLs by what Search Console says they earn."""
    keep, improve, prune = [], [], []
    for u in urls:
        g = gsc.get(url_key(u))
        if g and g["clicks"] >= KEEP_CLICKS:
            keep.append((u, g["clicks"]))
        elif g and g["impressions"] > 0:
            improve.append((u, g["impressions"]))
        else:
            prune.append((u, 0))
    keep.sort(key=lambda x: -x[1])
    improve.sort(key=lambda x: -x[1])
    return {
        "keep": [u for u, _ in keep],
        "improve": [u for u, _ in improve],
        "prune": [u for u, _ in prune],
        "clicks": sum(c for _, c in keep),
    }


def gsc_checks(con, gsc: dict) -> list:
    """Site-level findings that only exist once GSC data is joined to the crawl."""
    findings = []
    idx = [u for (u,) in con.execute("SELECT url FROM pages WHERE indexable=1")]
    dead = [u for u in idx if not (gsc.get(url_key(u)) or {}).get("impressions")]
    if idx and dead:
        share = round(len(dead) / len(idx) * 100)
        findings.append(
            {
                "priority": "P1" if share >= 40 and len(dead) >= 50 else "P2",
                "title": "Indexable pages with no search impressions",
                "description": f"{len(dead)} of {len(idx)} crawled indexable pages "
                f"({share}%) got zero impressions in the Search Console export. "
                "Pages Google won't show for anything are dead weight in the "
                "site-wide quality assessment. Examples: "
                + "; ".join(dead[:SAMPLE_LIMIT]),
                "fix": "Merge, 301 or noindex the ones that can't be made genuinely "
                "useful; improve and internally link the rest. (Check the export "
                "covered all pages: use the page dimension and a high row limit.)",
                "effort": "high",
                "module": MODULE,
                "count": len(dead),
                "key": "gsc_zero_impressions",
            }
        )
    return findings


def guideline_checks(con, gsc: dict = None) -> list:
    """Spam-policy / guideline patterns that need the whole crawl to see."""
    findings = []
    cols = _columns(con)
    indexable = con.execute("SELECT COUNT(*) FROM pages WHERE indexable=1").fetchone()[0]

    clusters = near_duplicate_clusters(con)
    if clusters:
        in_clusters = sum(c["size"] for c in clusters)
        if gsc:
            for c in clusters:
                c["triage"] = triage(c["urls"], gsc)

        def _label(c):
            label = f"{c['shape']} ({c['size']} pages, ~{c['avg_words']} words each"
            t = c.get("triage")
            if t:
                label += (
                    f"; GSC: keep {len(t['keep'])}, improve {len(t['improve'])}, "
                    f"prune {len(t['prune'])}, {int(t['clicks'])} clicks total"
                )
            return label + ")"

        top = "; ".join(_label(c) for c in clusters[:SAMPLE_LIMIT])
        findings.append(
            {
                "priority": "P1" if in_clusters >= 10 else "P2",
                "title": "Templated near-duplicate pages (doorway page risk)",
                "description": f"{in_clusters} indexable pages fall into {len(clusters)} "
                "groups whose main content is almost identical (only a place or service "
                "name swapped). Google's spam policies name exactly this as doorway "
                "abuse: many similar pages targeting city or region variations that "
                "funnel to the same thing. Core and spam updates since March 2024 have "
                f"hit this pattern hard. Groups: {top}",
                "fix": "Keep a location/service page only where you can add genuinely "
                "local substance (local clients, case studies, photos, staff, pricing, "
                "FAQs that differ). Merge or 301 the rest into one strong hub page, or "
                "noindex them while you rewrite.",
                "effort": "high",
                "module": MODULE,
                "count": in_clusters,
                "key": "doorway_templates",
                "clusters": [
                    {k: c[k] for k in ("shape", "size", "avg_words", "triage") if k in c}
                    for c in clusters
                ],
            }
        )
        if gsc:
            findings[-1]["fix"] = (
                "Use the GSC triage per group: KEEP pages that earn clicks and make "
                "them genuinely local; IMPROVE pages with impressions but no clicks "
                "(title/meta, then content); PRUNE pages with no impressions by "
                "merging/301ing into the hub or noindexing. The full keep/improve/"
                "prune URL lists are in the JSON output (clusters[].triage)."
            )
        if indexable and in_clusters / indexable >= SCALED_SHARE and in_clusters >= 20:
            share = round(in_clusters / indexable * 100)
            findings.append(
                {
                    "priority": "P1",
                    "title": "Large share of site is templated pages (scaled content risk)",
                    "description": f"{share}% of indexable pages ({in_clusters} of "
                    f"{indexable}) are templated near-duplicates. Google's helpfulness "
                    "signals have been site-wide since March 2024: a big block of "
                    "low-value pages can drag down the pages that are good. That's the "
                    "usual shape of a core-update drop.",
                    "fix": "Prune: consolidate, noindex or delete the weakest templated "
                    "pages first, then rebuild the survivors with unique content. Watch "
                    "Search Console for recovery after the next core update.",
                    "effort": "high",
                    "module": MODULE,
                    "count": in_clusters,
                    "key": "scaled_content_share",
                }
            )

    sections = reputation_sections(con)
    if sections:
        n = sum(c for _, c in sections)
        findings.append(
            {
                "priority": "P2",
                "title": "Possible site reputation abuse sections (verify)",
                "description": f"{n} indexable pages sit in sections whose URLs look like "
                "the third-party content Google's site reputation abuse policy targets "
                "(coupons, gambling, loans, CBD, 'best X' reviews): "
                + ", ".join(f"{s} ({c} pages)" for s, c in sections[:SAMPLE_LIMIT])
                + ". It only applies if the content is published mainly to exploit "
                "your site's ranking signals with little first-party oversight. Since "
                "30 Aug 2026 Google no longer demotes these via manual action in the "
                "EEA but still does elsewhere, including Australia.",
                "fix": "If it's third-party or off-topic, move it off the domain or "
                "noindex it. If it's genuinely yours, make the first-party ownership "
                "and editorial oversight obvious.",
                "effort": "medium",
                "module": MODULE,
                "count": n,
                "key": "site_reputation_sections",
            }
        )

    stuffed = [
        (u, t)
        for u, t in con.execute(
            "SELECT url, title FROM pages WHERE indexable=1 AND title IS NOT NULL"
        )
        if title_is_stuffed(t)
    ]
    if stuffed:
        findings.append(
            {
                "priority": "P2",
                "title": "Keyword-stuffed titles across pages",
                "description": f"{len(stuffed)} affected. Titles that repeat terms or "
                "string keyword fragments together are rewritten by Google and read as "
                "keyword stuffing. Examples: "
                + "; ".join(f"{t[:80]} ({u})" for u, t in stuffed[:SAMPLE_LIMIT]),
                "fix": "One clear title per page: primary topic, one qualifier, brand.",
                "effort": "medium",
                "module": MODULE,
                "count": len(stuffed),
                "key": "title_stuffing",
            }
        )

    if "schema_types" in cols:
        retired = Counter()
        for (types,) in con.execute(
            "SELECT schema_types FROM pages WHERE indexable=1 AND schema_types IS NOT NULL"
        ):
            for t in types.split(","):
                if t in RETIRED_RICH_RESULTS:
                    retired[t] += 1
        if retired:
            total = sum(retired.values())
            findings.append(
                {
                    "priority": "P3",
                    "title": "Markup for retired rich results across the site",
                    "description": f"{total} page-level uses of structured data Google no "
                    "longer shows as rich results: "
                    + ", ".join(f"{t} on {c} pages" for t, c in retired.most_common())
                    + ". Harmless, but it won't earn SERP features.",
                    "fix": "Stop generating it for new pages. Put schema effort into "
                    "types that still produce results.",
                    "effort": "low",
                    "module": MODULE,
                    "count": total,
                    "key": "retired_rich_results",
                }
            )
    if gsc:
        findings.extend(gsc_checks(con, gsc))
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
    ap.add_argument(
        "--gsc",
        help="GSC Performance export JSON (page dimension) to triage templated "
        "pages by real clicks and flag zero-impression pages",
    )
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

        gsc = load_gsc_pages(args.gsc) if args.gsc else None
        findings = run_checks(con, gsc)
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
