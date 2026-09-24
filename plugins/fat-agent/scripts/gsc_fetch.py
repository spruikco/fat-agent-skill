#!/usr/bin/env python3
"""Fetch full Search Console Performance data straight to disk.

GSC MCP servers cap rows (often 500) to protect the conversation context,
which is fine for a chat but useless for a site-wide audit: page-level triage
needs every URL. This calls the Search Console API directly, pages through
25,000-row batches, and writes JSON in the shape gsc.py / sitewide.py --gsc /
fanout.py / update_impact.py all read. Nothing large enters the context.

Auth (first match wins):
1. ``--access-token`` or ``GSC_ACCESS_TOKEN`` — a raw OAuth bearer token.
2. A saved OAuth token + client secrets (the files an OAuth-mode GSC MCP
   server already created — e.g. suganthan-gsc-mcp's ``~/.gsc-mcp/oauth-token.json``
   and ``GSC_OAUTH_SECRETS_FILE``). The refresh token is exchanged for a fresh
   access token on every run; the saved file is never modified.

Usage:
    python scripts/gsc_fetch.py --site sc-domain:example.com --dimension page \\
        --days 90 --out .fat-work/gsc_pages.json
    python scripts/gsc_fetch.py --site sc-domain:example.com --dimension date \\
        --days 480 --out .fat-work/gsc_dates.json      # for update_impact.py
    python scripts/gsc_fetch.py --site sc-domain:example.com \\
        --dimension query --dimension page --days 90 --out .fat-work/gsc_qp.json
    python scripts/gsc_fetch.py --list-sites          # which properties you can read

Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://searchconsole.googleapis.com/webmasters/v3"
TOKEN_URI = "https://oauth2.googleapis.com/token"
PAGE_SIZE = 25000
MAX_ROWS = 500000
DEFAULT_TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".gsc-mcp", "oauth-token.json")
DEFAULT_SECRETS_FILE = os.path.join(os.path.expanduser("~"), ".gsc", "gsc-oauth-secrets.json")


def _post_json(url, body, token=None, form=False):
    if form:
        data = urllib.parse.urlencode(body).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _get_json(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def access_token(args) -> str:
    tok = args.access_token or os.environ.get("GSC_ACCESS_TOKEN")
    if tok:
        return tok
    token_file = args.token_file or os.environ.get("GSC_OAUTH_TOKEN_FILE") or DEFAULT_TOKEN_FILE
    secrets_file = (
        args.secrets_file or os.environ.get("GSC_OAUTH_SECRETS_FILE") or DEFAULT_SECRETS_FILE
    )
    try:
        saved = json.load(open(token_file, encoding="utf-8"))
        secrets = json.load(open(secrets_file, encoding="utf-8"))
    except OSError as e:
        raise SystemExit(
            json.dumps({"error": f"no GSC credentials: {e}. Pass --access-token, or "
                        "point --token-file/--secrets-file at an OAuth login."})
        )
    client = secrets.get("installed") or secrets.get("web") or secrets
    res = _post_json(
        client.get("token_uri", TOKEN_URI),
        {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "refresh_token": saved["refresh_token"],
            "grant_type": "refresh_token",
        },
        form=True,
    )
    return res["access_token"]


def list_sites(token) -> list:
    data = _get_json(f"{API}/sites", token)
    return [
        {"site": s["siteUrl"], "permission": s.get("permissionLevel")}
        for s in data.get("siteEntry", [])
    ]


def fetch(token, site, dimensions, start, end, search_type="web", row_cap=MAX_ROWS) -> list:
    url = f"{API}/sites/{urllib.parse.quote(site, safe='')}/searchAnalytics/query"
    rows, start_row = [], 0
    while start_row < row_cap:
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": dimensions,
            "rowLimit": PAGE_SIZE,
            "startRow": start_row,
            "type": search_type,
            "dataState": "final",
        }
        batch = _post_json(url, body, token).get("rows", [])
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start_row += PAGE_SIZE
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="full GSC export to disk")
    ap.add_argument("--site", help="property, e.g. sc-domain:example.com or https://example.com/")
    ap.add_argument("--dimension", action="append", default=[],
                    help="page | query | date | country | device (repeatable)")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--search-type", default="web")
    ap.add_argument("--out", help="output JSON (default stdout)")
    ap.add_argument("--list-sites", action="store_true")
    ap.add_argument("--access-token")
    ap.add_argument("--token-file")
    ap.add_argument("--secrets-file")
    args = ap.parse_args(argv)

    try:
        token = access_token(args)
        if args.list_sites:
            print(json.dumps(list_sites(token), indent=2))
            return 0
        if not args.site:
            ap.error("--site is required (or use --list-sites)")
        dims = args.dimension or ["page"]
        end = dt.date.today() - dt.timedelta(days=3)  # GSC finalises ~2-3 days late
        start = end - dt.timedelta(days=args.days - 1)
        rows = fetch(token, args.site, dims, start, end, args.search_type)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        print(json.dumps({"error": f"HTTP {e.code}", "detail": detail}))
        return 1

    out = {
        "site": args.site,
        "dimensions": dims,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "rows": rows,
    }
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh)
        clicks = sum(r.get("clicks", 0) for r in rows)
        print(json.dumps({"rows": len(rows), "clicks": clicks, "out": args.out,
                          "window": f"{start} to {end}"}))
    else:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
