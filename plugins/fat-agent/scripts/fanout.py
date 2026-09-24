#!/usr/bin/env python3
"""Query fan-out coverage: does the site answer the sub-queries AI search asks?

Google's AI Mode and AI Overviews "may use a 'query fan-out' technique, issuing
multiple related searches across subtopics" (Search Central, AI features doc).
A page that only answers the head query competes for a shrinking slice: Surfer's
Dec 2025 study (10k keywords, 33k fan-outs) found pages ranking for fan-out
sub-queries were 161% more likely to be cited in AI Overviews. So for each seed
query this:

1. **Builds a fan-out set** — typed sub-queries (definition, cost, comparison,
   process, evaluation, trust, local, recency, branded) from templates, plus
   optional live Google Autocomplete suggestions (`--autocomplete`, no key) and
   optional LLM-generated sub-queries (`--queries`, e.g. a Qforia-style JSON the
   agent writes in-session).
2. **Scores site coverage** against a sitecrawl.py DB (titles, H1s, H2/H3s,
   meta descriptions): each sub-query is a dedicated PAGE, a SECTION (heading),
   a MENTION, or a GAP.
3. **Exports the fan-out set** (`--export-queries`) so ai_visibility.py can
   check who actually gets cited for it off-site (Perplexity), which is where
   brand mentions and third-party coverage show up.

Seeds come from `--seed` (repeatable) or the top non-branded queries in a GSC
export (`--seeds-from-gsc`).

Usage:
    python scripts/fanout.py --db .fat-work/crawl/site.db \\
        --seed "seo agency melbourne" --location Melbourne --entity Spruik
    python scripts/fanout.py --db site.db --seeds-from-gsc gsc.json --top 5 \\
        --autocomplete --export-queries .fat-work/fanout_queries.txt --json
    python scripts/ai_visibility.py --domain example.com \\
        --queries .fat-work/fanout_queries.txt

Stdlib only. Correlational evidence: frame gaps as opportunities, not causes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

MODULE = "fanout"

_STOP = set(
    """a an and are as at be by can do does for from how i in is it its me my of
    on or our the to vs what when where which who why will with you your near""".split()
)

# (type, template). {q} = seed, {e} = entity, {loc} = location, {y} = year
TEMPLATES = [
    ("definition", "what is {q}"),
    ("process", "how does {q} work"),
    ("process", "how long does {q} take"),
    ("cost", "{q} cost"),
    ("cost", "how much does {q} cost"),
    ("comparison", "best {q}"),
    ("comparison", "{q} alternatives"),
    ("comparison", "how to choose {q}"),
    ("evaluation", "is {q} worth it"),
    ("evaluation", "{q} pros and cons"),
    ("evaluation", "{q} mistakes to avoid"),
    ("trust", "{q} reviews"),
    ("trust", "{q} case studies"),
    ("recency", "{q} {y}"),
    ("local", "{q} near me"),
]
LOCAL_TEMPLATES = [("local", "{q} in {loc}")]
ENTITY_TEMPLATES = [
    ("branded", "{e} reviews"),
    ("branded", "is {e} any good"),
    ("branded", "{e} alternatives"),
    ("branded", "{e} pricing"),
]
AUTOCOMPLETE_PREFIXES = ["", "how ", "best ", "why "]


def _stem(w: str) -> str:
    for suf in ("ies", "ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def tokens(text: str) -> set:
    return {
        _stem(w)
        for w in re.findall(r"[a-z0-9]+", (text or "").lower())
        if w not in _STOP and len(w) > 1
    }


def build_fanout(seed: str, entity: str = "", location: str = "", year: int = None) -> list:
    year = year or dt.date.today().year
    seed = " ".join(seed.lower().split())
    out = [{"query": seed, "type": "core"}]
    tpls = list(TEMPLATES)
    if location and location.lower() not in seed:
        tpls += LOCAL_TEMPLATES
    for typ, t in tpls:
        out.append({"query": t.format(q=seed, loc=location, y=year), "type": typ})
    if entity:
        for typ, t in ENTITY_TEMPLATES:
            out.append({"query": t.format(e=entity), "type": typ})
    return out


def autocomplete(seed: str, timeout: float = 6.0, delay: float = 0.5) -> list:
    """Live Google Autocomplete suggestions (no key). Fails soft to []."""
    found = []
    for prefix in AUTOCOMPLETE_PREFIXES:
        url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
            {"client": "firefox", "hl": "en", "q": prefix + seed}
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            found.extend(s for s in data[1] if isinstance(s, str))
        except Exception:  # noqa: BLE001 — network is optional
            continue
        time.sleep(delay)
    seen, out = set(), []
    for s in found:
        k = " ".join(s.lower().split())
        if k and k not in seen and k != seed.lower():
            seen.add(k)
            out.append({"query": k, "type": "autocomplete"})
    return out


def load_extra_queries(path: str) -> list:
    """LLM/agent-written fan-out: JSON [{query, type}] / ["q", ...] or one per line."""
    text = open(path, encoding="utf-8").read().strip()
    if text.startswith("["):
        out = []
        for item in json.loads(text):
            if isinstance(item, str):
                out.append({"query": item, "type": "llm"})
            elif isinstance(item, dict) and item.get("query"):
                out.append({"query": item["query"], "type": item.get("type", "llm")})
        return out
    return [{"query": ln.strip(), "type": "llm"} for ln in text.splitlines() if ln.strip()]


def seeds_from_gsc(path: str, top: int, brand_terms: list) -> list:
    """Top non-branded queries by impressions from a GSC export."""
    from gsc import load_rows

    with open(path, encoding="utf-8") as fh:
        rows = load_rows(json.load(fh))
    agg: dict = {}
    for r in rows:
        q = (r.get("query") or "").lower().strip()
        if not q or q.startswith("http"):
            continue
        if any(b and b.lower() in q for b in brand_terms):
            continue
        agg[q] = agg.get(q, 0) + r["impressions"]
    return [q for q, _ in sorted(agg.items(), key=lambda x: -x[1])[:top]]


def load_pages(con) -> list:
    cols = {r[1] for r in con.execute("PRAGMA table_info(pages)")}
    hsel = "headings" if "headings" in cols else "NULL"
    pages = []
    for url, title, h1, meta, heads in con.execute(
        f"SELECT url, title, h1, meta_desc, {hsel} FROM pages WHERE indexable=1"
    ):
        pages.append(
            {
                "url": url,
                "primary": tokens(f"{title or ''} {h1 or ''}"),
                "headings": [(h, tokens(h)) for h in (heads or "").split(" | ") if h],
                "all": tokens(f"{title or ''} {h1 or ''} {meta or ''} {heads or ''}"),
            }
        )
    return pages


def match(query: str, pages: list) -> dict:
    """Best coverage level for one sub-query: page > section > mention > gap."""
    q = tokens(query)
    if not q:
        return {"level": "gap", "url": None, "evidence": None}

    def frac(t):
        return len(q & t) / len(q)

    best = {"level": "gap", "url": None, "evidence": None, "score": 0.0}
    rank = {"page": 3, "section": 2, "mention": 1, "gap": 0}
    for p in pages:
        f = frac(p["primary"])
        if f >= 0.8:
            cand = {"level": "page", "url": p["url"], "evidence": "title/H1", "score": f}
        else:
            hbest = max(((frac(t), h) for h, t in p["headings"]), default=(0.0, None))
            if hbest[0] >= 0.8:
                cand = {"level": "section", "url": p["url"], "evidence": hbest[1],
                        "score": hbest[0]}
            elif frac(p["all"]) >= 0.6:
                cand = {"level": "mention", "url": p["url"], "evidence": "page text",
                        "score": frac(p["all"])}
            else:
                continue
        if (rank[cand["level"]], cand["score"]) > (rank[best["level"]], best["score"]):
            best = cand
    best.pop("score", None)
    return best


def analyse(seeds: list, pages: list, entity="", location="", extra=None, auto=False) -> dict:
    results = []
    findings = []
    for seed in seeds:
        fan = build_fanout(seed, entity, location)
        if auto:
            fan += autocomplete(seed)
        fan += [x for x in (extra or [])]
        seen, rows = set(), []
        for item in fan:
            k = item["query"].lower().strip()
            if k in seen:
                continue
            seen.add(k)
            rows.append({**item, **match(k, pages)})
        on_site = [r for r in rows if r["type"] != "branded"]
        covered = [r for r in on_site if r["level"] in ("page", "section")]
        pct = round(len(covered) / len(on_site) * 100) if on_site else 0
        by_type: dict = {}
        for r in on_site:
            t = by_type.setdefault(r["type"], {"total": 0, "covered": 0})
            t["total"] += 1
            t["covered"] += r["level"] in ("page", "section")
        missing_types = sorted(t for t, v in by_type.items() if v["covered"] == 0)
        gaps = [r["query"] for r in on_site if r["level"] in ("gap", "mention")]
        results.append(
            {
                "seed": seed,
                "coverage_pct": pct,
                "by_type": by_type,
                "missing_types": missing_types,
                "subqueries": rows,
            }
        )
        if pct < 60:
            findings.append(
                {
                    "priority": "P2" if pct < 40 else "P3",
                    "title": f"Low query fan-out coverage: '{seed}'",
                    "description": f"The site answers {len(covered)} of {len(on_site)} "
                    f"({pct}%) likely fan-out sub-queries for '{seed}' with a page or "
                    "section. AI Mode and AI Overviews split a question into related "
                    "searches and cite pages that answer those, so pages that only "
                    "target the head term miss most citations. Types with no coverage: "
                    + (", ".join(missing_types) or "none")
                    + ". Gaps: "
                    + "; ".join(gaps[:10]),
                    "fix": "Answer the gaps with genuinely useful sections on the "
                    "money page (pricing, process, comparisons, proof) or dedicated "
                    "guides. Use non-commodity content: real prices, timelines, "
                    "client results. Don't spin up a thin page per sub-query; that's "
                    "the scaled-content pattern.",
                    "effort": "medium",
                    "module": MODULE,
                }
            )
    return {"results": results, "findings": findings}


def format_human(res: dict) -> str:
    lines = []
    icon = {"page": "PAGE", "section": "SECT", "mention": "ment", "gap": " -- "}
    for r in res["results"]:
        lines.append(f"\nSeed: {r['seed']}  coverage {r['coverage_pct']}%")
        if r["missing_types"]:
            lines.append(f"  no coverage for: {', '.join(r['missing_types'])}")
        for s in r["subqueries"]:
            where = f"  {s['url']}" if s.get("url") else ""
            lines.append(f"  [{icon[s['level']]}] ({s['type']}) {s['query']}{where}")
    return "\n".join(lines).strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description="query fan-out coverage checker")
    ap.add_argument("--db", required=True, help="sitecrawl.py site.db")
    ap.add_argument("--seed", action="append", default=[], help="seed query (repeatable)")
    ap.add_argument("--seeds-from-gsc", help="GSC export JSON: use top non-branded queries")
    ap.add_argument("--top", type=int, default=5, help="seeds to take from GSC")
    ap.add_argument("--entity", default="", help="brand/entity name (branded fan-out)")
    ap.add_argument("--location", default="", help="primary location, e.g. Melbourne")
    ap.add_argument("--queries", help="extra LLM-written sub-queries (JSON or lines)")
    ap.add_argument("--autocomplete", action="store_true", help="add live Google Autocomplete")
    ap.add_argument("--export-queries", help="write the fan-out set for ai_visibility.py")
    ap.add_argument("--json", action="store_true", help="punchlist-ready JSON")
    args = ap.parse_args(argv)

    seeds = list(args.seed)
    if args.seeds_from_gsc:
        brand = [args.entity] if args.entity else []
        seeds += seeds_from_gsc(args.seeds_from_gsc, args.top, brand)
    if not seeds:
        print(json.dumps({"error": "give --seed or --seeds-from-gsc"}))
        return 1
    con = sqlite3.connect(args.db)
    pages = load_pages(con)
    extra = load_extra_queries(args.queries) if args.queries else None
    res = analyse(seeds, pages, args.entity, args.location, extra, args.autocomplete)

    if args.export_queries:
        qs = []
        for r in res["results"]:
            qs += [s["query"] for s in r["subqueries"] if s["query"] not in qs]
        with open(args.export_queries, "w", encoding="utf-8") as fh:
            fh.write("\n".join(qs) + "\n")

    if args.json:
        print(
            json.dumps(
                {
                    "findings": res["findings"],
                    "module_scores": {MODULE: {"results": res["results"]}},
                    "summary": {},
                },
                indent=2,
            )
        )
    else:
        print(format_human(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
