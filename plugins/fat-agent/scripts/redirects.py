#!/usr/bin/env python3
"""Redirect-chain & soft-404 analyser for fat-agent (Hobo-parity).

Follows a URL's redirect chain hop-by-hop (without the silent auto-follow that
hides problems) and reports:

- the full chain with status codes,
- **redirect chains** (> 1 hop waste crawl budget + link equity),
- **redirect loops**,
- **temporary (302/307) redirects** used where a permanent (301/308) is meant,
- **meta-refresh** redirects,
- **soft 404s** (a 200 response that's really a "not found" page).

Stdlib only. The chain-following logic is pure (inject a fetcher) so it's testable
without network.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request

_NOT_FOUND_RE = re.compile(
    r"page not found|not be found|doesn'?t exist|404 error|error 404|"
    r"no longer (?:exists|available)|page you (?:requested|are looking)",
    re.IGNORECASE,
)


def real_fetch(url, timeout=10):
    """Fetch one hop WITHOUT following redirects. Returns (status, location, body)."""

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "fat-agent-redirects/1.0"})
    try:
        resp = opener.open(req, timeout=timeout)
        body = resp.read(4096).decode("utf-8", errors="replace")
        return resp.status, resp.headers.get("Location"), body
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            return exc.code, exc.headers.get("Location"), ""
        body = ""
        try:
            body = exc.read(4096).decode("utf-8", errors="replace")
        except Exception:
            pass
        return exc.code, None, body
    except urllib.error.URLError as exc:
        return 0, None, f"error: {exc.reason}"


def follow(url, fetcher=real_fetch, max_hops=10):
    """Trace the redirect chain from url. Returns a structured report."""
    chain = []
    seen = set()
    current = url
    loop = False
    meta_refresh = False
    final_body = ""
    for _ in range(max_hops):
        status, location, body = fetcher(current)
        chain.append({"url": current, "status": status})
        final_body = body
        if current in seen:
            loop = True
            break
        seen.add(current)
        if status in (301, 302, 303, 307, 308) and location:
            current = urllib.parse.urljoin(current, location)
            continue
        # meta-refresh as a redirect
        m = re.search(
            r'<meta[^>]+http-equiv=["\']refresh["\'][^>]*content=["\'][^"\']*url=([^"\'>]+)',
            body,
            re.IGNORECASE,
        )
        if status == 200 and m:
            meta_refresh = True
            nxt = urllib.parse.urljoin(current, m.group(1).strip())
            if nxt in seen:
                loop = True
                break
            current = nxt
            continue
        break
    return _classify(url, chain, loop, meta_refresh, final_body)


def _classify(start, chain, loop, meta_refresh, final_body):
    hops = len(chain) - 1
    final = chain[-1]
    statuses = [c["status"] for c in chain[:-1]]
    issues = []
    if loop:
        issues.append({"priority": "P0", "issue": "Redirect loop"})
    if hops >= 2:
        issues.append(
            {
                "priority": "P2",
                "issue": f"Redirect chain ({hops} hops) — collapse to a single hop",
            }
        )
    if any(s in (302, 303, 307) for s in statuses):
        issues.append(
            {
                "priority": "P2",
                "issue": "Temporary redirect (302/307) used — use 301/308 if permanent",
            }
        )
    if meta_refresh:
        issues.append(
            {
                "priority": "P2",
                "issue": "Meta-refresh redirect — use an HTTP 301 instead",
            }
        )
    # Soft-404 only when the *title* is a short error title (e.g. "404 Page Not
    # Found") — not when "page not found" appears in the body of a legitimate
    # article about 404 errors. A real 404 page has a short error-y title.
    title_m = re.search(
        r"<title[^>]*>(.*?)</title>", final_body, re.IGNORECASE | re.DOTALL
    )
    title = re.sub(r"<[^>]+>", " ", title_m.group(1)) if title_m else ""
    soft_404 = (
        final["status"] == 200
        and bool(_NOT_FOUND_RE.search(title))
        and len(title.split()) <= 8
    )
    if soft_404:
        issues.append(
            {
                "priority": "P1",
                "issue": "Soft 404 — 'not found' page returns HTTP 200 (should be 404/410)",
            }
        )
    if final["status"] >= 400:
        issues.append(
            {"priority": "P1", "issue": f"Chain ends in HTTP {final['status']}"}
        )
    return {
        "start_url": start,
        "chain": chain,
        "hops": hops,
        "final_status": final["status"],
        "loop": loop,
        "meta_refresh": meta_refresh,
        "soft_404": soft_404,
        "issues": issues,
    }


def build_parser():
    p = argparse.ArgumentParser(
        description="Trace a URL's redirect chain and flag soft 404s."
    )
    p.add_argument("--url", required=True, help="URL to trace")
    p.add_argument("--max-hops", type=int, default=10)
    p.add_argument("--output", default=None)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    result = follow(args.url, max_hops=args.max_hops)
    text = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Redirect analysis written to {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
