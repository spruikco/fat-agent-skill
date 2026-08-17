#!/usr/bin/env python3
"""Live AI-search visibility (AEO/GEO citation) checker for fat-agent.

The `ai_search` module audits *readiness* (crawler posture, llms.txt,
extraction, entity). This script measures the thing that actually matters:
**does the site get cited when an answer engine answers the queries that
matter?** It runs a query set through the Perplexity API, collects the
citations each answer used, and reports:

- **Citation rate** — % of tested queries where the target domain is cited.
- **Citation rank** — where in the citation list the domain appears.
- **Share of voice** — the domain's citations as a share of all citations
  across the query set.
- **Competitor intel** — which domains ARE being cited for your queries
  (these are the sources the answer engines trust for your topics).

Findings are emitted in the standard FAT shape (module ``ai_visibility``) so
they merge straight into the punch list, and `--save-history` appends a
timestamped snapshot so citation rate can be tracked audit-over-audit.

Security model
--------------
The API key is read from the ``PERPLEXITY_API_KEY`` environment variable (or
``--api-key`` for ad-hoc use). It is never hardcoded, never written to the
output JSON, and is redacted from every error message. If no key is available
the script exits 0 with ``{"available": false}`` so the audit pipeline can
continue — SKILL.md documents the browser-automation fallback for spot checks.

Uses only stdlib (urllib + json). Works on Python 3.8+.

Usage
-----
    python scripts/ai_visibility.py --domain example.com \
        --queries queries.txt --output ai_visibility.json

    # inline queries, competitor share-of-voice, history tracking:
    python scripts/ai_visibility.py --domain example.com \
        --query "best pest control adelaide" --query "termite inspection cost" \
        --competitors rivalone.com.au,rivaltwo.com.au --save-history
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.perplexity.ai/chat/completions"
DEFAULT_MODEL = "sonar"
ENV_VAR = "PERPLEXITY_API_KEY"
HISTORY_FILE = ".fat-ai-visibility-history.json"

# Community / UGC platforms answer engines lean on heavily. Being cited FROM
# these is a distinct, winnable channel (seed a helpful answer, earn a mention)
# separate from out-ranking a competitor's own site.
COMMUNITY_PLATFORMS = {
    "reddit.com": "Reddit",
    "quora.com": "Quora",
    "youtube.com": "YouTube",
    "medium.com": "Medium",
    "stackexchange.com": "Stack Exchange",
    "stackoverflow.com": "Stack Overflow",
    "linkedin.com": "LinkedIn",
    "wikipedia.org": "Wikipedia",
    "g2.com": "G2",
    "trustpilot.com": "Trustpilot",
    "producthunt.com": "Product Hunt",
    "github.com": "GitHub",
    "facebook.com": "Facebook",
    "yelp.com": "Yelp",
    "tripadvisor.com": "TripAdvisor",
}


def classify_channels(top_domains):
    """Split top-cited domains into community platforms vs everything else."""
    community, competitors = [], []
    for item in top_domains:
        domain = item["domain"]
        label = None
        for suffix, name in COMMUNITY_PLATFORMS.items():
            if domain == suffix or domain.endswith("." + suffix):
                label = name
                break
        if label:
            community.append({**item, "platform": label})
        else:
            competitors.append(item)
    return community, competitors


class VisibilityError(Exception):
    """Raised on an API or transport failure (message is always key-redacted)."""


def get_api_key(cli_key=None):
    if cli_key:
        return cli_key
    key = os.environ.get(ENV_VAR)
    return key.strip() if key else None


def _redact(text, key):
    if not text:
        return text
    text = str(text)
    if key:
        text = text.replace(key, "***REDACTED***")
    return text


def registrable_domain(url_or_host):
    """Normalise a URL or hostname to a comparable domain (heuristic, no PSL).

    Strips scheme, path, port and a leading ``www.``. ``example.com`` and
    ``https://www.example.com/page`` both become ``example.com``.
    """
    if not url_or_host:
        return ""
    value = url_or_host.strip().lower()
    if "//" in value:
        value = urllib.parse.urlparse(value).netloc or value
    value = value.split("/")[0].split(":")[0]
    if value.startswith("www."):
        value = value[4:]
    return value


def _post_json(payload, api_key, timeout=45):
    """POST the chat request to the Perplexity API. Overridable in tests."""
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
            "User-Agent": "fat-agent-ai-visibility/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise VisibilityError(
            _redact("Perplexity API HTTP %s: %s" % (e.code, body), api_key)
        )
    except Exception as e:
        raise VisibilityError(_redact("Perplexity API request failed: %s" % e, api_key))


def extract_citations(response):
    """Pull the cited URLs out of a Perplexity chat response.

    The API has shipped citations as a top-level ``citations`` list of URLs
    and, more recently, as ``search_results`` (list of dicts with ``url``).
    Accept both; preserve order (order == citation rank).
    """
    urls = []
    for item in response.get("citations") or []:
        if isinstance(item, str):
            urls.append(item)
        elif isinstance(item, dict) and item.get("url"):
            urls.append(item["url"])
    if not urls:
        for item in response.get("search_results") or []:
            if isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])
    return urls


def check_query(query, api_key, model=DEFAULT_MODEL, post=None):
    """Run one query and report the citation picture for it."""
    post = post or _post_json
    response = post(
        {
            "model": model,
            "messages": [{"role": "user", "content": query}],
        },
        api_key,
    )
    urls = extract_citations(response)
    domains = [registrable_domain(u) for u in urls]
    return {"query": query, "citation_urls": urls, "citation_domains": domains}


def analyse_results(domain, results, competitors=None):
    """Aggregate per-query results into rates, share of voice and top sources."""
    target = registrable_domain(domain)
    competitors = [registrable_domain(c) for c in (competitors or []) if c.strip()]

    per_query = []
    total_citations = 0
    target_citations = 0
    domain_counts = {}
    competitor_hits = {c: 0 for c in competitors}

    for r in results:
        domains = r["citation_domains"]
        total_citations += len(domains)
        rank = None
        for i, d in enumerate(domains, start=1):
            domain_counts[d] = domain_counts.get(d, 0) + 1
            if d == target:
                target_citations += 1
                if rank is None:
                    rank = i
        for c in competitor_hits:
            if c in domains:
                competitor_hits[c] += 1
        per_query.append(
            {
                "query": r["query"],
                "cited": rank is not None,
                "citation_rank": rank,
                "citations": domains,
            }
        )

    cited_queries = sum(1 for q in per_query if q["cited"])
    n = len(per_query)
    top_domains = sorted(domain_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top_other = [
        {"domain": d, "citations": c} for d, c in top_domains if d != target
    ][:10]
    community, competitors = classify_channels(top_other)

    return {
        "domain": target,
        "queries_tested": n,
        "queries_cited": cited_queries,
        "citation_rate": round(cited_queries / n, 3) if n else 0.0,
        "share_of_voice": (
            round(target_citations / total_citations, 3) if total_citations else 0.0
        ),
        "total_citations_seen": total_citations,
        "top_cited_domains": top_other,
        "top_competitor_domains": competitors,
        "community_channels": community,
        "competitor_citation_queries": competitor_hits,
        "per_query": per_query,
    }


def build_findings(summary):
    """Emit findings in the standard FAT shape (module ``ai_visibility``)."""
    findings = []
    n = summary["queries_tested"]
    rate = summary["citation_rate"]
    if n >= 3 and summary["queries_cited"] == 0:
        findings.append(
            {
                "priority": "P1",
                "title": "Not cited by Perplexity for any tested query",
                "description": (
                    "Across %d target queries, %s was never among the cited sources. "
                    "The site is effectively invisible in AI answers for its own topics."
                    % (n, summary["domain"])
                ),
                "fix": (
                    "Work the ai_search readiness findings first (answer-bot access, "
                    "extraction-ready summaries, entity schema), then build citable "
                    "assets for these queries: direct-answer intros, original data or "
                    "stats, and topic pages matching the query language. Re-test after "
                    "indexing."
                ),
                "effort": "high",
                "module": "ai_visibility",
            }
        )
    elif n >= 3 and rate < 0.34:
        findings.append(
            {
                "priority": "P2",
                "title": "Low AI citation rate (%d%% of tested queries)"
                % round(rate * 100),
                "description": (
                    "%s is cited for %d of %d tested queries. The uncited queries "
                    "show where answer engines prefer other sources."
                    % (summary["domain"], summary["queries_cited"], n)
                ),
                "fix": (
                    "For each uncited query, compare the pages that WERE cited (see "
                    "top_cited_domains): match their directness and structure, add a "
                    "concise lead answer, and cover the sub-questions they answer."
                ),
                "effort": "medium",
                "module": "ai_visibility",
            }
        )
    community, competitors = classify_channels(summary["top_cited_domains"])
    if competitors:
        top = ", ".join(
            "%s (%d)" % (d["domain"], d["citations"]) for d in competitors[:5]
        )
        findings.append(
            {
                "priority": "P3",
                "title": "Competitor sites answer engines trust for your queries",
                "description": (
                    "Most-cited competitor/other domains across the query set: %s. "
                    "These are the pages to study and out-answer." % top
                ),
                "fix": (
                    "For each, open the cited page and match its directness and "
                    "structure on your own equivalent page, then cover the "
                    "sub-questions it answers."
                ),
                "effort": "medium",
                "module": "ai_visibility",
            }
        )
    if community:
        chan = ", ".join(
            "%s (%d)" % (d["platform"], d["citations"]) for d in community[:5]
        )
        findings.append(
            {
                "priority": "P3",
                "title": "Community platforms are citation channels for your queries",
                "description": (
                    "Answer engines cite these community/UGC platforms for your "
                    "topics: %s. A helpful presence there is a citation channel in "
                    "its own right, separate from your own site ranking." % chan
                ),
                "fix": (
                    "Seed genuinely useful answers (no spam) in the relevant threads/"
                    "subreddits/Q&A, and earn mentions on the review and listing "
                    "platforms that keep appearing."
                ),
                "effort": "medium",
                "module": "ai_visibility",
            }
        )
    return findings


def load_queries(args):
    queries = list(args.query or [])
    if args.queries:
        with open(args.queries, encoding="utf-8") as f:
            text = f.read()
        stripped = text.strip()
        if stripped.startswith("["):
            queries.extend(str(q) for q in json.loads(stripped))
        else:
            queries.extend(
                line.strip() for line in text.splitlines() if line.strip()
            )
    # dedupe, preserve order
    seen = set()
    out = []
    for q in queries:
        if q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


def save_history(summary, path=HISTORY_FILE):
    history = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append(
        {
            "date": datetime.date.today().isoformat(),
            "domain": summary["domain"],
            "queries_tested": summary["queries_tested"],
            "citation_rate": summary["citation_rate"],
            "share_of_voice": summary["share_of_voice"],
        }
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Live AI-search citation check via the Perplexity API"
    )
    parser.add_argument("--domain", required=True, help="Target domain to look for")
    parser.add_argument(
        "--queries", help="File of queries: one per line, or a JSON list"
    )
    parser.add_argument(
        "--query", action="append", help="Inline query (repeatable)"
    )
    parser.add_argument(
        "--competitors", default="", help="Comma-separated competitor domains"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key", help="Perplexity API key (prefer the env var)")
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Seconds between API calls"
    )
    parser.add_argument("--output", help="Write the full JSON result to a file")
    parser.add_argument(
        "--save-history",
        action="store_true",
        help="Append a snapshot to %s for trend tracking" % HISTORY_FILE,
    )
    args = parser.parse_args(argv)

    api_key = get_api_key(args.api_key)
    if not api_key:
        result = {
            "available": False,
            "reason": "No %s set — skipping live citation check." % ENV_VAR,
        }
        print(json.dumps(result, indent=2))
        return 0

    queries = load_queries(args)
    if not queries:
        print(
            json.dumps(
                {"available": False, "reason": "No queries provided."}, indent=2
            )
        )
        return 0

    results = []
    errors = []
    for i, q in enumerate(queries):
        try:
            results.append(check_query(q, api_key, model=args.model))
        except VisibilityError as e:
            errors.append({"query": q, "error": str(e)})
        if args.delay and i < len(queries) - 1:
            time.sleep(args.delay)

    if not results:
        print(
            json.dumps(
                {
                    "available": False,
                    "reason": "All queries failed.",
                    "errors": errors,
                },
                indent=2,
            )
        )
        return 1

    competitors = [c for c in args.competitors.split(",") if c.strip()]
    summary = analyse_results(args.domain, results, competitors)
    output = {
        "available": True,
        "engine": "perplexity",
        "model": args.model,
        "summary": summary,
        "findings": build_findings(summary),
        "errors": errors,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
    if args.save_history:
        save_history(summary)

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
