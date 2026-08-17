#!/usr/bin/env python3
"""AI-crawler hit analysis from server access logs.

`ai_search` checks whether robots.txt *permits* the AI crawlers. This answers
the harder question with ground truth: **are they actually visiting?** Point it
at an access log (Nginx/Apache combined or common format) and it reports which
AI bots hit the site, how often, when they were last seen, and — the useful
finding — which answer engines have *never* crawled despite being allowed.

A blank result for the answer bots (OAI-SearchBot, PerplexityBot,
Google-Extended, ChatGPT-User) means your content isn't being pulled into AI
answers yet, even if nothing is blocking it — usually a discovery / sitemap /
internal-link problem, or the site is simply too new.

Pairs with `ai_visibility.py`: logs show whether the bots *fetch*; the citation
check shows whether that fetching *turns into citations*.

Uses only stdlib. Works on Python 3.8+.

Usage
-----
    python scripts/ai_crawler_logs.py --log /var/log/nginx/access.log \
        --output ./.fat-work/ai_crawler_logs.json

    zcat access.log.*.gz | python scripts/ai_crawler_logs.py --log -
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# Bot label -> substring matched (case-insensitive) in the User-Agent.
ANSWER_BOTS = {
    "OAI-SearchBot": "oai-searchbot",
    "ChatGPT-User": "chatgpt-user",
    "PerplexityBot": "perplexitybot",
    "Perplexity-User": "perplexity-user",
    "Google-Extended": "google-extended",
}
TRAINING_BOTS = {
    "GPTBot": "gptbot",
    "ClaudeBot": "claudebot",
    "anthropic-ai": "anthropic-ai",
    "CCBot": "ccbot",
    "Bytespider": "bytespider",
    "Amazonbot": "amazonbot",
    "Applebot-Extended": "applebot-extended",
    "Meta-ExternalAgent": "meta-externalagent",
    "Google-CloudVertexBot": "google-cloudvertexbot",
}
AI_BOTS = {**ANSWER_BOTS, **TRAINING_BOTS}

# Combined/common log line: ... [10/Oct/2025:13:55:36 +0000] "GET /x HTTP/1.1"
# 200 1234 "ref" "User-Agent"
_LINE_RE = re.compile(
    r'\[(?P<time>[^\]]+)\]\s+"(?P<method>[A-Z]+)\s+(?P<path>\S+)[^"]*"'
    r'\s+(?P<status>\d{3})\s+\S+'
    r'(?:\s+"[^"]*"\s+"(?P<ua>[^"]*)")?'
)


def _match_bot(ua_lower):
    for label, token in AI_BOTS.items():
        if token in ua_lower:
            return label
    return None


def parse_lines(lines):
    """Aggregate AI-bot hits from an iterable of log lines."""
    stats = {}
    total_lines = 0
    matched_lines = 0
    for raw in lines:
        total_lines += 1
        m = _LINE_RE.search(raw)
        if not m:
            continue
        ua = (m.group("ua") or "").lower()
        if not ua:
            continue
        label = _match_bot(ua)
        if not label:
            continue
        matched_lines += 1
        entry = stats.setdefault(
            label, {"hits": 0, "last_seen": None, "sample_paths": [], "statuses": {}}
        )
        entry["hits"] += 1
        entry["last_seen"] = m.group("time")  # last wins == most recent in tail-order
        status = m.group("status")
        entry["statuses"][status] = entry["statuses"].get(status, 0) + 1
        if len(entry["sample_paths"]) < 5:
            path = m.group("path")
            if path not in entry["sample_paths"]:
                entry["sample_paths"].append(path)
    return stats, total_lines, matched_lines


def build_report(stats, total_lines, matched_lines):
    seen = set(stats)
    answer_seen = [b for b in ANSWER_BOTS if b in seen]
    answer_missing = [b for b in ANSWER_BOTS if b not in seen]
    training_seen = [b for b in TRAINING_BOTS if b in seen]

    findings = []
    if not answer_seen:
        findings.append(
            {
                "priority": "P2",
                "title": "No AI answer-engine crawlers seen in the logs",
                "description": "None of %s appear in the access log. If robots.txt "
                "isn't blocking them (check ai_search), the site likely isn't being "
                "discovered — a sitemap, internal-link, or freshness gap."
                % ", ".join(ANSWER_BOTS),
                "fix": "Confirm the answer bots are allowed, submit an up-to-date XML "
                "sitemap, strengthen internal links to key pages, and re-check the "
                "logs in a few weeks.",
                "effort": "medium",
                "module": "ai_crawler_logs",
            }
        )
    elif answer_missing:
        findings.append(
            {
                "priority": "P3",
                "title": "Some answer engines not yet crawling: %s"
                % ", ".join(answer_missing),
                "description": "Seen: %s. Not seen: %s."
                % (", ".join(answer_seen), ", ".join(answer_missing)),
                "fix": "Make sure these bots are allowed and your key pages are "
                "reachable and in the sitemap.",
                "effort": "low",
                "module": "ai_crawler_logs",
            }
        )
    # Bots hitting mostly errors are wasting their crawl on you.
    for label, entry in stats.items():
        err = sum(v for s, v in entry["statuses"].items() if s[0] in "45")
        if entry["hits"] >= 10 and err / entry["hits"] > 0.5:
            findings.append(
                {
                    "priority": "P2",
                    "title": "%s mostly hitting errors (%d/%d 4xx/5xx)"
                    % (label, err, entry["hits"]),
                    "description": "This AI crawler is spending its budget on broken "
                    "URLs, so little usable content is being ingested.",
                    "fix": "Fix or redirect the URLs this bot requests (see "
                    "sample_paths); prune dead links from the sitemap.",
                    "effort": "medium",
                    "module": "ai_crawler_logs",
                }
            )

    return {
        "available": True,
        "lines_parsed": total_lines,
        "ai_bot_hits": matched_lines,
        "bots_seen": stats,
        "answer_bots_seen": answer_seen,
        "answer_bots_missing": answer_missing,
        "training_bots_seen": training_seen,
        "findings": findings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyse AI-crawler hits from server access logs"
    )
    parser.add_argument(
        "--log",
        required=True,
        help="Access log path, or '-' to read from stdin (e.g. zcat ... | ...)",
    )
    parser.add_argument("--output", help="Write the full JSON result to a file")
    args = parser.parse_args(argv)

    if args.log == "-":
        stats, total, matched = parse_lines(sys.stdin)
    else:
        try:
            with open(args.log, encoding="utf-8", errors="replace") as f:
                stats, total, matched = parse_lines(f)
        except OSError as e:
            print(
                json.dumps({"available": False, "reason": "Cannot read log: %s" % e})
            )
            return 1

    report = build_report(stats, total, matched)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
