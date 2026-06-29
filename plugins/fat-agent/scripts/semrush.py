#!/usr/bin/env python3
"""SEMrush Analytics API integration for fat-agent.

Pulls domain authority, organic keyword/traffic figures, the historical trend,
and top keyword positions from the SEMrush Analytics API, then emits a
``semrush.json`` file in the exact shape consumed by ``generate-charts.py`` and
``generate-report.py``.

Security model
--------------
The API key is read from the ``SEMRUSH_API_KEY`` environment variable (or the
``--api-key`` flag for ad-hoc use). It is **never** hardcoded, never written to
the output JSON, and is redacted from every error message and log line — the
request URL (which embeds the key) is never surfaced. If no key is available the
script exits 0 with ``{"available": false}`` so the audit pipeline can continue
without SEMrush enrichment.

Uses only stdlib (urllib + json) — no external dependencies. Works on Python 3.8+.
"""

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# Classic Analytics API (domain reports). Key-based, semicolon-delimited CSV.
ANALYTICS_BASE = "https://api.semrush.com/"
# Backlinks Analytics API (v1). Same key, different path and column model.
BACKLINKS_BASE = "https://api.semrush.com/analytics/v1/"

ENV_VAR = "SEMRUSH_API_KEY"


class SemrushError(Exception):
    """Raised on an API or transport failure (message is always key-redacted)."""


def get_api_key(cli_key=None):
    """Resolve the API key from the CLI flag or the environment.

    Never returns a hardcoded default — absence of a key is a valid state.
    """
    if cli_key:
        return cli_key
    key = os.environ.get(ENV_VAR)
    return key.strip() if key else None


def _redact(text, key):
    """Strip the API key from any string before it is shown or logged."""
    if not text:
        return text
    text = str(text)
    if key:
        text = text.replace(key, "***REDACTED***")
        text = text.replace(urllib.parse.quote(key), "***REDACTED***")
    return text


def _request(params, key, base=ANALYTICS_BASE, timeout=30):
    """Perform a single GET and return the response body as text.

    Raises SemrushError with a key-redacted message on any failure. The request
    URL is deliberately never included in raised messages.
    """
    query = dict(params)
    query["key"] = key
    request_url = f"{base}?{urllib.parse.urlencode(query)}"
    try:
        req = urllib.request.Request(
            request_url, headers={"User-Agent": "fat-agent-semrush/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        raise SemrushError(f"HTTP {exc.code}: {_redact(detail, key)[:300]}") from None
    except urllib.error.URLError as exc:
        raise SemrushError(f"Network error: {_redact(exc.reason, key)}") from None
    except Exception as exc:  # noqa: BLE001 - defensive, message is redacted
        raise SemrushError(f"Unexpected error: {_redact(exc, key)}") from None

    # The SEMrush API returns plain-text "ERROR ## :: MESSAGE" with HTTP 200.
    if body.strip().upper().startswith("ERROR"):
        raise SemrushError(_redact(body.strip(), key))
    return body


def _parse_csv(text):
    """Parse SEMrush's semicolon-delimited CSV into a list of dict rows."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    headers = [h.strip() for h in lines[0].split(";")]
    rows = []
    for line in lines[1:]:
        values = line.split(";")
        rows.append(
            {
                headers[i]: values[i].strip()
                for i in range(min(len(headers), len(values)))
            }
        )
    return rows


def _get(row, *names, default=None):
    """Fetch a value from a row trying several candidate header spellings."""
    for name in names:
        if name in row and row[name] != "":
            return row[name]
    return default


def _to_int(value, default=None):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _fmt_month(date_str):
    """Format a SEMrush date (YYYYMMDD or YYYY-MM-DD) as e.g. 'Apr 24'."""
    if not date_str:
        return ""
    raw = date_str.replace("-", "").strip()
    try:
        dt = datetime.datetime.strptime(raw[:8], "%Y%m%d")
        return dt.strftime("%b %y")
    except ValueError:
        return date_str


def _pct_change(old, new):
    """Return a signed percentage-change string, e.g. '+5.3%' or '-12%'."""
    if not old:
        return ""
    pct = (new - old) / old * 100
    rounded = round(pct, 1)
    if rounded == int(rounded):
        rounded = int(rounded)
    sign = "+" if rounded >= 0 else ""
    return f"{sign}{rounded}%"


def _position_distribution(rows):
    """Bucket organic positions into the distribution the charts expect."""
    dist = {"top3": 0, "4-10": 0, "11-20": 0, "21-50": 0, "51-100": 0}
    for row in rows:
        pos = _to_int(_get(row, "Position", "Pos"))
        if pos is None:
            continue
        if pos <= 3:
            dist["top3"] += 1
        elif pos <= 10:
            dist["4-10"] += 1
        elif pos <= 20:
            dist["11-20"] += 1
        elif pos <= 50:
            dist["21-50"] += 1
        elif pos <= 100:
            dist["51-100"] += 1
    return dist


def fetch_domain_ranks(domain, database, key, timeout=30):
    """Current organic overview for a domain."""
    text = _request(
        {"type": "domain_ranks", "domain": domain, "database": database},
        key,
        timeout=timeout,
    )
    rows = _parse_csv(text)
    return rows[0] if rows else {}


def fetch_rank_history(domain, database, key, limit=24, timeout=30):
    """Historical organic figures (one row per period)."""
    text = _request(
        {
            "type": "domain_rank_history",
            "domain": domain,
            "database": database,
            "display_limit": limit,
        },
        key,
        timeout=timeout,
    )
    return _parse_csv(text)


def fetch_domain_organic(domain, database, key, limit=30, timeout=30):
    """Top organic keyword positions (sorted by traffic share)."""
    text = _request(
        {
            "type": "domain_organic",
            "domain": domain,
            "database": database,
            "display_limit": limit,
            "display_sort": "tr_desc",
        },
        key,
        timeout=timeout,
    )
    return _parse_csv(text)


def fetch_backlinks_overview(domain, key, timeout=30):
    """Authority score, total backlinks and referring domains (best-effort).

    Lives on a different API path and is not available on every plan, so callers
    treat failure here as non-fatal.
    """
    text = _request(
        {
            "type": "backlinks_overview",
            "target": domain,
            "target_type": "root_domain",
            "export_columns": "ascore,total,domains_num",
        },
        key,
        base=BACKLINKS_BASE,
        timeout=timeout,
    )
    rows = _parse_csv(text)
    return rows[0] if rows else {}


def build_traffic_trend(history_rows):
    """Map rank-history rows to the traffic_trend chart series (oldest first)."""
    points = []
    for row in history_rows:
        date = _get(row, "Date")
        points.append(
            {
                "_sort": (date or "").replace("-", ""),
                "month": _fmt_month(date),
                "organic": _to_int(_get(row, "Organic Traffic", "Ot"), 0),
                "paid": _to_int(_get(row, "Adwords Traffic", "At"), 0),
                "branded": 0,
            }
        )
    points.sort(key=lambda p: p["_sort"])
    for p in points:
        p.pop("_sort", None)
    return points


def build_keywords_trend(history_rows):
    """Map rank-history rows to the keywords_trend chart series (oldest first)."""
    points = []
    for row in history_rows:
        date = _get(row, "Date")
        points.append(
            {
                "_sort": (date or "").replace("-", ""),
                "month": _fmt_month(date),
                "total": _to_int(_get(row, "Organic Keywords", "Or"), 0),
            }
        )
    points.sort(key=lambda p: p["_sort"])
    for p in points:
        p.pop("_sort", None)
    return points


def build_top_keywords(organic_rows):
    """Map domain_organic rows to the top_keywords chart series."""
    keywords = []
    for row in organic_rows:
        kw = _get(row, "Keyword", "Ph")
        if not kw:
            continue
        traffic_pct = _get(row, "Traffic (%)", "Tr", default="")
        keywords.append(
            {
                "keyword": kw,
                "position": _to_int(_get(row, "Position", "Pos"), 0),
                "volume": _to_int(_get(row, "Search Volume", "Nq"), 0),
                "traffic_pct": f"{traffic_pct}%" if traffic_pct else "",
            }
        )
    return keywords


def build_semrush_json(
    domain, database="au", key=None, history_limit=24, keyword_limit=30, timeout=30
):
    """Assemble the full semrush.json payload from the API.

    The current-overview call (domain_ranks) gates availability. History,
    keyword and backlink calls are best-effort: a failure leaves their section
    empty rather than failing the whole audit.
    """
    overview = fetch_domain_ranks(domain, database, key, timeout=timeout)

    data = {
        "available": True,
        "domain": domain,
        "database": database,
        "organic_keywords": _to_int(_get(overview, "Organic Keywords", "Or")),
        "organic_traffic": _to_int(_get(overview, "Organic Traffic", "Ot")),
        "traffic_cost": _to_int(_get(overview, "Organic Cost", "Oc")),
        "authority_score": None,
        "referring_domains": None,
        "backlinks": None,
        "traffic_change": "",
        "keywords_change": "",
        "traffic_trend": [],
        "keywords_trend": [],
        "position_distribution": {},
        "top_keywords": [],
        "competitors": [],
    }

    # History (best-effort) -> trends + change figures.
    try:
        history = fetch_rank_history(
            domain, database, key, limit=history_limit, timeout=timeout
        )
        data["traffic_trend"] = build_traffic_trend(history)
        data["keywords_trend"] = build_keywords_trend(history)
        if len(data["traffic_trend"]) >= 2:
            data["traffic_change"] = _pct_change(
                data["traffic_trend"][0]["organic"],
                data["traffic_trend"][-1]["organic"],
            )
        if len(data["keywords_trend"]) >= 2:
            data["keywords_change"] = _pct_change(
                data["keywords_trend"][0]["total"], data["keywords_trend"][-1]["total"]
            )
    except SemrushError as exc:
        data["history_error"] = str(exc)

    # Keyword positions (best-effort) -> top keywords + distribution.
    try:
        organic = fetch_domain_organic(
            domain, database, key, limit=keyword_limit, timeout=timeout
        )
        data["top_keywords"] = build_top_keywords(organic)
        data["position_distribution"] = _position_distribution(organic)
    except SemrushError as exc:
        data["keywords_error"] = str(exc)

    # Backlinks (best-effort, different plan tier) -> authority + link counts.
    try:
        backlinks = fetch_backlinks_overview(domain, key, timeout=timeout)
        data["authority_score"] = _to_int(_get(backlinks, "Authority Score", "ascore"))
        data["backlinks"] = _to_int(_get(backlinks, "Total Backlinks", "total"))
        data["referring_domains"] = _to_int(
            _get(backlinks, "Referring Domains", "domains_num")
        )
    except SemrushError as exc:
        data["backlinks_error"] = str(exc)

    return data


def build_parser():
    parser = argparse.ArgumentParser(
        description="Fetch SEMrush domain data and emit a semrush.json for the FAT pipeline.",
    )
    parser.add_argument(
        "--domain", required=True, help="Domain to analyse, e.g. example.com"
    )
    parser.add_argument(
        "--database",
        default="au",
        help="SEMrush database code (au, us, uk, ...). Default: au",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help=f"SEMrush API key. Defaults to the {ENV_VAR} environment variable.",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=24,
        help="Number of history periods (default: 24)",
    )
    parser.add_argument(
        "--keyword-limit",
        type=int,
        default=30,
        help="Number of top keywords (default: 30)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Per-request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--output", default=None, help="Write JSON to this file instead of stdout"
    )
    return parser


def main(argv=None):
    """CLI entry point. Always emits JSON to stdout (or --output)."""
    parser = build_parser()
    args = parser.parse_args(argv)

    key = get_api_key(args.api_key)
    if not key:
        result = {
            "available": False,
            "reason": f"No SEMrush API key. Set the {ENV_VAR} environment variable "
            f"or pass --api-key to enable SEMrush enrichment.",
        }
    else:
        try:
            result = build_semrush_json(
                args.domain,
                database=args.database,
                key=key,
                history_limit=args.history_limit,
                keyword_limit=args.keyword_limit,
                timeout=args.timeout,
            )
        except SemrushError as exc:
            # Core call failed — report gracefully so the audit can continue.
            result = {"available": False, "reason": _redact(str(exc), key)}

    output_json = json.dumps(result, indent=2)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)
            print(f"SEMrush data written to {args.output}")
        except OSError as exc:
            print(f"Error writing output file: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(output_json)

    if not result.get("available"):
        print(result.get("reason", "SEMrush enrichment unavailable."), file=sys.stderr)


if __name__ == "__main__":
    main()
