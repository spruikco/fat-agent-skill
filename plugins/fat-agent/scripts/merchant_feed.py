#!/usr/bin/env python3
"""Google Merchant Center feed validator for FAT Agent.

Merchant Center disapproves products for problems no page-level audit sees: a
feed item missing a required attribute, a malformed price, or a landing page
whose structured data disagrees with the feed (price or shipping rate). This
script reads a Merchant feed (RSS 2.0 or Atom with the ``g:`` namespace),
validates every item, then samples landing pages and compares what the page
says with what the feed says.

Real case behind it: txsports.com.au's feed sent shipping at $12.00 AUD (what
checkout charges) while every product page's Product JSON-LD said $9. Google
compares the two and can disapprove products for "mismatched shipping".

Checks
------
Feed (every item):
- required attributes: id, title, description, link, image_link, availability,
  price, brand; condition is recommended
- unique product identifiers: gtin, or mpn, or identifier_exists=no
- availability values (in_stock, out_of_stock, preorder, backorder)
- price / sale_price format ("12.00 AUD")
- duplicate ids
- link host matches the site
- variant groups (item_group_id): every variant carries the attribute that
  makes it different (size/color/...) and no two variants share them
- apparel attributes (color, size, gender, age_group) on apparel items

Landing pages (a sample, default 20 distinct links):
- HTTP 200 without redirects, indexable (no noindex meta / X-Robots-Tag)
- Product JSON-LD present
- JSON-LD price equals the feed price (sale price counts)
- JSON-LD shippingDetails rate equals the feed's g:shipping price

Respects robots.txt, waits between requests, refuses private hosts (SSRF
guard) and sends the crawler's User-Agent (Cloudflare's Browser Integrity
Check answers Python's default one with 403). Stdlib only, Python 3.8+.

Usage
-----
    python scripts/merchant_feed.py --url https://example.com/feeds/google.xml \
        --output ./.fat-work/merchant_feed.json
    python scripts/merchant_feed.py --file feed.xml --site https://example.com --sample 0
    python scripts/punchlist.py update --scores ./.fat-work/merchant_feed.json
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitecrawl import (  # noqa: E402
    DEFAULT_UA,
    fetch,
    host_is_blocked,
    load_robots,
    make_opener,
    safe_url,
)

MODULE = "merchant_feed"
G_NS = "http://base.google.com/ns/1.0"
ATOM_NS = "http://www.w3.org/2005/Atom"
MAX_FEED_BYTES = 80_000_000
SAMPLE_LIMIT = 8

REQUIRED = ("id", "title", "description", "link", "image_link", "availability", "price")
AVAILABILITY = {
    "in_stock",
    "out_of_stock",
    "preorder",
    "backorder",
    # older spellings Merchant Center still accepts
    "in stock",
    "out of stock",
    "available for order",
}
PRICE_RE = re.compile(r"^\s*\d+(?:\.\d{1,2})?\s+[A-Z]{3}\s*$")
VARIANT_ATTRS = (
    "color",
    "size",
    "pattern",
    "material",
    "age_group",
    "gender",
    "size_type",
)
APPAREL_ATTRS = ("color", "size", "gender", "age_group")
# Google product taxonomy: Apparel & Accessories (166) and its main clothing
# branches. Text categories are matched by word instead.
APPAREL_CATEGORY_IDS = {
    "166",
    "1604",
    "5322",
    "212",
    "204",
    "207",
    "209",
    "5182",
    "5388",
}
APPAREL_WORDS_RE = re.compile(
    r"apparel|clothing|uniform|jersey|shirt|shorts|socks", re.I
)
NOINDEX_META_RE = re.compile(
    r'<meta[^>]+name=["\'](?:robots|googlebot)["\'][^>]*content=["\'][^"\']*noindex',
    re.IGNORECASE,
)
JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


# --------------------------------------------------------------------------- #
# Feed parsing
# --------------------------------------------------------------------------- #
def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def parse_feed(raw: bytes) -> list:
    """Items as dicts of attribute -> value (or list for repeated g:shipping).

    Reads RSS 2.0 (<item>) and Atom (<entry>). g: attributes and plain RSS
    title/link/description are merged; g: wins when both are present.
    """
    root = ET.fromstring(raw)
    nodes = [e for e in root.iter() if _local(e.tag) in ("item", "entry")]
    items = []
    for node in nodes:
        item: dict = {"shipping": []}
        for child in node:
            name = _local(child.tag)
            ns = child.tag[1:].split("}", 1)[0] if child.tag.startswith("{") else ""
            if name == "shipping":
                ship = {_local(c.tag): _text(c) for c in child}
                item["shipping"].append(ship)
                continue
            if ns == ATOM_NS and name == "link":
                href = child.get("href")
                if href and "link" not in item:
                    item["link"] = href.strip()
                continue
            value = _text(child)
            if ns == G_NS or name not in item:
                item[name] = value
        items.append(item)
    return items


def _num(price: str):
    m = re.match(r"\s*(\d+(?:\.\d+)?)", price or "")
    return float(m.group(1)) if m else None


def _host(url: str) -> str:
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _is_apparel(item: dict) -> bool:
    cat = item.get("google_product_category", "")
    if cat.strip() in APPAREL_CATEGORY_IDS:
        return True
    if APPAREL_WORDS_RE.search(cat):
        return True
    return False


def _finding(priority, title, description, fix, effort="medium", count=0):
    return {
        "priority": priority,
        "title": title,
        "description": description,
        "fix": fix,
        "effort": effort,
        "module": MODULE,
        "count": count,
    }


def _examples(values) -> str:
    vals = list(values)
    shown = "; ".join(str(v) for v in vals[:SAMPLE_LIMIT])
    more = len(vals) - min(len(vals), SAMPLE_LIMIT)
    return shown + (f" (+{more} more)" if more > 0 else "")


def validate_items(items: list, site: str = "") -> tuple:
    """Feed-level findings and stats for a parsed feed."""
    findings = []
    stats = {"items": len(items)}
    if not items:
        findings.append(
            _finding(
                "P1",
                "Merchant feed has no items",
                "The feed parsed but lists no <item> or <entry> elements, so Merchant "
                "Center has nothing to show.",
                "Check the feed generator (a data source that failed can return an "
                "empty but valid feed).",
                "low",
            )
        )
        return findings, stats

    missing = Counter()
    missing_examples = defaultdict(list)
    for it in items:
        for f in REQUIRED + ("brand",):
            if not it.get(f):
                missing[f] += 1
                if len(missing_examples[f]) < 3:
                    missing_examples[f].append(it.get("id") or it.get("link") or "?")
    stats["missing_required"] = dict(missing)
    if missing:
        detail = ", ".join(
            f"{f} ({n}, e.g. {', '.join(missing_examples[f])})"
            for f, n in missing.most_common()
        )
        findings.append(
            _finding(
                "P1",
                "Feed items missing required attributes",
                f"Merchant Center disapproves items without these: {detail}.",
                "Fill the attribute in the feed generator for every item (brand can "
                "be the store's own brand for own-label goods).",
                "medium",
                sum(missing.values()),
            )
        )

    no_condition = sum(1 for it in items if not it.get("condition"))
    if no_condition:
        findings.append(
            _finding(
                "P3",
                "Feed items without a condition",
                f"{no_condition} items have no g:condition. Google assumes new, but "
                "states it as recommended for every item.",
                "Send g:condition (new, refurbished or used).",
                "low",
                no_condition,
            )
        )

    bad_avail = [
        (it.get("id"), it.get("availability"))
        for it in items
        if it.get("availability") and it["availability"].lower() not in AVAILABILITY
    ]
    if bad_avail:
        findings.append(
            _finding(
                "P1",
                "Invalid availability values in feed",
                f"{len(bad_avail)} items use an availability Merchant Center does not "
                "accept (in_stock, out_of_stock, preorder, backorder). Examples: "
                + _examples(f"{i}={v}" for i, v in bad_avail),
                "Map stock states to the four accepted values.",
                "low",
                len(bad_avail),
            )
        )

    bad_price = [
        (it.get("id"), f, it.get(f))
        for it in items
        for f in ("price", "sale_price")
        if it.get(f) and not PRICE_RE.match(it[f])
    ]
    if bad_price:
        findings.append(
            _finding(
                "P1",
                "Malformed prices in feed",
                f"{len(bad_price)} price values are not in the '12.00 AUD' form "
                "(number, space, ISO 4217 currency). Examples: "
                + _examples(f"{i} {f}='{v}'" for i, f, v in bad_price),
                "Format prices as <amount> <CURRENCY>, e.g. 49.95 AUD.",
                "low",
                len(bad_price),
            )
        )

    ids = Counter(it.get("id") for it in items if it.get("id"))
    dups = [i for i, n in ids.items() if n > 1]
    stats["duplicate_ids"] = len(dups)
    if dups:
        findings.append(
            _finding(
                "P1",
                "Duplicate item ids in feed",
                f"{len(dups)} ids appear more than once; Merchant Center keeps one and "
                "drops or overwrites the others. Examples: " + _examples(dups),
                "Give every item (each variant) its own stable id, e.g. the variant SKU "
                "or database id.",
                "low",
                len(dups),
            )
        )

    no_ident = [
        it.get("id")
        for it in items
        if not it.get("gtin")
        and not it.get("mpn")
        and (it.get("identifier_exists") or "").lower() not in ("no", "false")
    ]
    if no_ident:
        findings.append(
            _finding(
                "P2",
                "Feed items without unique product identifiers",
                f"{len(no_ident)} items have no gtin or mpn and do not set "
                "identifier_exists=no. Merchant Center limits their performance and can "
                "disapprove branded products. Examples: " + _examples(no_ident),
                "Send the GTIN (barcode) or the manufacturer part number; for custom or "
                "own-label goods that have neither, send identifier_exists=no.",
                "medium",
                len(no_ident),
            )
        )

    if site:
        site_host = _host(site)
        off = [
            it.get("link")
            for it in items
            if it.get("link") and _host(it["link"]) != site_host
        ]
        if off:
            findings.append(
                _finding(
                    "P2",
                    "Feed links point at another host",
                    f"{len(off)} item links are not on {site_host}. Merchant Center needs "
                    "landing pages on the claimed, verified domain (a feed still sending "
                    "the old domain after a migration is the usual cause). Examples: "
                    + _examples(off),
                    "Build feed links from the live site's base URL.",
                    "low",
                    len(off),
                )
            )

    groups = defaultdict(list)
    for it in items:
        if it.get("item_group_id"):
            groups[it["item_group_id"]].append(it)
    stats["variant_groups"] = len(groups)
    clashes, bare = [], []
    for gid, members in groups.items():
        if len(members) < 2:
            continue
        combos = Counter(tuple(m.get(a, "") for a in VARIANT_ATTRS) for m in members)
        if any(n > 1 for n in combos.values()):
            clashes.append(gid)
        if any(not any(m.get(a) for a in VARIANT_ATTRS) for m in members):
            bare.append(gid)
    if clashes or bare:
        findings.append(
            _finding(
                "P2",
                "Variant groups with duplicate or missing variant attributes",
                f"{len(clashes)} item groups have two variants with the same "
                f"size/colour/etc., and {len(bare)} have variants with none of them. "
                "Google cannot tell those variants apart and may merge or disapprove "
                "them. Groups: " + _examples(clashes + bare),
                "Give every variant in an item_group_id the attribute that makes it "
                "different (size, color, material, pattern).",
                "medium",
                len(clashes) + len(bare),
            )
        )

    apparel = [it for it in items if _is_apparel(it)]
    stats["apparel_items"] = len(apparel)
    if apparel:
        gaps = Counter(a for it in apparel for a in APPAREL_ATTRS if not it.get(a))
        if gaps:
            findings.append(
                _finding(
                    "P2",
                    "Apparel items missing apparel attributes",
                    f"Of {len(apparel)} apparel items, missing: "
                    + ", ".join(f"{a} ({n})" for a, n in gaps.most_common())
                    + ". Required for apparel in Brazil, France, Germany, Japan, the UK "
                    "and the US, and used for filtering everywhere else.",
                    "Send color, size, gender and age_group on every apparel variant.",
                    "medium",
                    sum(gaps.values()),
                )
            )
    return findings, stats


# --------------------------------------------------------------------------- #
# Landing pages
# --------------------------------------------------------------------------- #
def _walk(data):
    stack = [data]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            yield x
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)


def _types(node) -> set:
    t = node.get("@type")
    names = t if isinstance(t, list) else [t]
    return {n.rsplit("/", 1)[-1] for n in names if isinstance(n, str)}


def page_offer_facts(html: str) -> dict:
    """Product presence, offer prices and shipping rates from a page's JSON-LD."""
    out = {"product": False, "prices": [], "ranges": [], "shipping": []}
    for block in JSON_LD_RE.findall(html or ""):
        try:
            data = json.loads(block)
        except (ValueError, TypeError):
            continue
        for node in _walk(data):
            types = _types(node)
            if "Product" in types or "ProductGroup" in types:
                out["product"] = True
            if "AggregateOffer" in types:
                lo, hi = _num(str(node.get("lowPrice", ""))), _num(
                    str(node.get("highPrice", ""))
                )
                if lo is not None:
                    out["ranges"].append((lo, hi if hi is not None else lo))
            elif "Offer" in types and node.get("price") is not None:
                p = _num(str(node.get("price")))
                if p is not None:
                    out["prices"].append(p)
            if "OfferShippingDetails" in types:
                rates = node.get("shippingRate")
                for rate in rates if isinstance(rates, list) else [rates]:
                    if isinstance(rate, dict) and rate.get("value") is not None:
                        v = _num(str(rate.get("value")))
                        if v is not None:
                            out["shipping"].append(v)
    return out


def compare_item(item: dict, facts: dict) -> dict:
    """Price and shipping agreement between one feed item and its page."""
    result = {"price_mismatch": None, "shipping_mismatch": None}
    feed_prices = [
        p
        for p in (_num(item.get("price")), _num(item.get("sale_price")))
        if p is not None
    ]
    page_prices = facts["prices"]
    ranges = facts["ranges"]
    if feed_prices and (page_prices or ranges):
        ok = any(
            abs(fp - pp) < 0.01 for fp in feed_prices for pp in page_prices
        ) or any(
            lo - 0.01 <= fp <= hi + 0.01 for fp in feed_prices for lo, hi in ranges
        )
        if not ok:
            result["price_mismatch"] = (
                f"feed {item.get('price')}"
                + (
                    f" (sale {item.get('sale_price')})"
                    if item.get("sale_price")
                    else ""
                )
                + f" vs page {sorted(set(page_prices)) or ranges}"
            )
    feed_ship = [
        _num(s.get("price"))
        for s in item.get("shipping") or []
        if s.get("price") and _num(s.get("price")) is not None
    ]
    if feed_ship and facts["shipping"]:
        if not any(abs(a - b) < 0.01 for a in feed_ship for b in facts["shipping"]):
            result["shipping_mismatch"] = (
                f"feed shipping {sorted(set(feed_ship))} vs page shippingDetails "
                f"{sorted(set(facts['shipping']))}"
            )
    return result


def pick_sample(items: list, n: int) -> list:
    """Up to n items with distinct links, spread across the feed."""
    seen, uniq = set(), []
    for it in items:
        link = it.get("link")
        if link and link not in seen:
            seen.add(link)
            uniq.append(it)
    if n <= 0 or not uniq:
        return []
    if len(uniq) <= n:
        return uniq
    step = len(uniq) / n
    return [uniq[int(i * step)] for i in range(n)]


def check_landing_pages(
    sample, opener, ua, timeout, delay, robots=None, allow_private=False
):
    rows = []
    for i, item in enumerate(sample):
        url = item["link"]
        row = {"id": item.get("id"), "url": url}
        if robots is not None and not robots.can_fetch(ua, url):
            row["skipped"] = "robots.txt disallows"
            rows.append(row)
            continue
        r = fetch(url, opener, ua, timeout, retries=1, allow_private=allow_private)
        hops = 0
        while (
            r.get("status")
            and 300 <= r["status"] < 400
            and r.get("location")
            and hops < 5
        ):
            hops += 1
            r = fetch(
                r["location"],
                opener,
                ua,
                timeout,
                retries=1,
                allow_private=allow_private,
            )
        row["status"] = r.get("status")
        row["redirects"] = hops
        row["error"] = r.get("error")
        body = r.get("body") or ""
        xr = ""
        if r.get("headers") is not None:
            xr = (r["headers"].get("X-Robots-Tag") or "").lower()
        row["noindex"] = bool(NOINDEX_META_RE.search(body)) or "noindex" in xr
        if row["status"] == 200 and body:
            facts = page_offer_facts(body)
            row["product_schema"] = facts["product"]
            row.update(compare_item(item, facts))
        rows.append(row)
        if delay and i < len(sample) - 1:
            time.sleep(delay)
    return rows


def landing_findings(rows: list) -> list:
    findings = []
    checked = [r for r in rows if not r.get("skipped")]
    if not checked:
        return findings
    broken = [r for r in checked if r.get("status") != 200 or r.get("noindex")]
    if broken:
        findings.append(
            _finding(
                "P1",
                "Feed landing pages broken or not indexable",
                f"{len(broken)} of {len(checked)} sampled feed links do not end in an "
                "indexable 200 page; Merchant Center disapproves items whose landing "
                "page is unavailable or blocked. Examples: "
                + _examples(
                    f"{r['url']} ({'noindex' if r.get('noindex') else r.get('status') or r.get('error')})"
                    for r in broken
                ),
                "Fix or remove the items, and keep feed links pointed at live product "
                "pages.",
                "medium",
                len(broken),
            )
        )
    redirected = [r for r in checked if r.get("redirects")]
    if redirected:
        findings.append(
            _finding(
                "P2",
                "Feed links redirect",
                f"{len(redirected)} of {len(checked)} sampled feed links redirect before "
                "reaching the product page. Google wants the final URL in the feed. "
                "Examples: " + _examples(r["url"] for r in redirected),
                "Send the final (canonical) product URL in g:link.",
                "low",
                len(redirected),
            )
        )
    ok = [r for r in checked if r.get("status") == 200 and not r.get("noindex")]
    no_schema = [r for r in ok if r.get("product_schema") is False]
    if no_schema:
        findings.append(
            _finding(
                "P2",
                "Feed landing pages missing Product structured data",
                f"{len(no_schema)} of {len(ok)} sampled landing pages have no Product "
                "JSON-LD, so Google cannot confirm price and availability from the page "
                "(used for automatic item updates and free listings). Examples: "
                + _examples(r["url"] for r in no_schema),
                "Add Product JSON-LD with offers (price, priceCurrency, availability).",
                "medium",
                len(no_schema),
            )
        )
    price = [r for r in ok if r.get("price_mismatch")]
    if price:
        findings.append(
            _finding(
                "P1",
                "Landing page price does not match the feed",
                f"{len(price)} of {len(ok)} sampled pages show a different price in "
                "their structured data than the feed sends. Merchant Center disapproves "
                "for 'mismatched value (page crawl) [price]'. Examples: "
                + _examples(f"{r['url']}: {r['price_mismatch']}" for r in price),
                "Make the feed and the page read price from the same source; send "
                "sale_price when the page shows a sale.",
                "medium",
                len(price),
            )
        )
    ship = [r for r in ok if r.get("shipping_mismatch")]
    if ship:
        findings.append(
            _finding(
                "P1",
                "Landing page shipping rate does not match the feed",
                f"{len(ship)} of {len(ok)} sampled pages declare a different shipping "
                "rate in Product JSON-LD (offers.shippingDetails) than the feed's "
                "g:shipping price. Google compares the two and can disapprove for "
                "mismatched shipping. Examples: "
                + _examples(f"{r['url']}: {r['shipping_mismatch']}" for r in ship),
                "Use one shipping constant for the feed, the structured data and the "
                "checkout default rate (or configure shipping in Merchant Center and "
                "drop it from both).",
                "low",
                len(ship),
            )
        )
    return findings


# --------------------------------------------------------------------------- #
# Feed fetch + CLI
# --------------------------------------------------------------------------- #
def fetch_feed(url, ua, timeout=60, allow_private=False):
    """Return (bytes, error). Follows up to 5 same-site redirects."""
    opener = make_opener()
    for _ in range(6):
        if host_is_blocked(urlparse(url).hostname, allow_private):
            return None, "blocked: private/internal host (SSRF guard)"
        req = Request(
            safe_url(url),
            headers={"User-Agent": ua, "Accept": "application/xml,text/xml,*/*;q=0.8"},
        )
        try:
            resp = opener.open(req, timeout=timeout)
            raw = resp.read(MAX_FEED_BYTES + 1)
            if len(raw) > MAX_FEED_BYTES:
                return None, f"feed larger than {MAX_FEED_BYTES // 1_000_000}MB"
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            return raw, None
        except HTTPError as e:
            loc = e.headers.get("Location") if e.headers else None
            if 300 <= e.code < 400 and loc:
                nxt = urljoin(url, loc)
                if _host(nxt) != _host(url):
                    return None, f"redirects off-site to {nxt}"
                url = nxt
                continue
            return None, f"HTTP {e.code}"
        except (URLError, OSError, ValueError) as e:
            return None, str(e)[:200]
    return None, "too many redirects"


def run(
    raw: bytes,
    site: str = "",
    sample: int = 20,
    ua: str = DEFAULT_UA,
    timeout: int = 20,
    delay: float = 0.5,
    ignore_robots: bool = False,
    allow_private: bool = False,
    feed_url: str = "",
) -> dict:
    try:
        items = parse_feed(raw)
    except ET.ParseError as e:
        return {
            "available": True,
            "feed": feed_url,
            "findings": [
                _finding(
                    "P1",
                    "Merchant feed could not be fetched or parsed",
                    f"The feed is not well-formed XML ({e}). Merchant Center rejects "
                    "the whole fetch.",
                    "Validate the generator's output (unescaped & in titles or URLs is "
                    "the usual cause).",
                    "low",
                )
            ],
        }
    findings, stats = validate_items(items, site)
    rows = []
    chosen = pick_sample(items, sample)
    if chosen:
        opener = make_opener()
        robots = None
        if not ignore_robots:
            robots, _ = load_robots(
                chosen[0]["link"], opener, ua, timeout, allow_private
            )
        rows = check_landing_pages(
            chosen, opener, ua, timeout, delay, robots, allow_private
        )
        findings.extend(landing_findings(rows))
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    findings.sort(key=lambda f: order.get(f["priority"], 9))
    return {
        "available": True,
        "feed": feed_url,
        "site": site,
        "stats": stats,
        "samples": rows,
        "findings": findings,
        "page_url": site or feed_url,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a Google Merchant Center feed")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="feed URL to fetch")
    src.add_argument("--file", help="local feed file (RSS or Atom)")
    ap.add_argument(
        "--site", default="", help="site base URL (default: the feed's origin)"
    )
    ap.add_argument(
        "--sample", type=int, default=20, help="landing pages to check (0 = none)"
    )
    ap.add_argument(
        "--delay", type=float, default=0.5, help="seconds between page fetches"
    )
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--user-agent", default=DEFAULT_UA)
    ap.add_argument("--ignore-robots", action="store_true")
    ap.add_argument(
        "--allow-private",
        action="store_true",
        help="permit private/loopback hosts (authorised staging audits only)",
    )
    ap.add_argument("--output", help="write the JSON result here as well")
    args = ap.parse_args(argv)

    if args.url:
        raw, err = fetch_feed(
            args.url, args.user_agent, allow_private=args.allow_private
        )
        site = args.site or "{0.scheme}://{0.netloc}".format(urlparse(args.url))
        if err:
            result = {
                "available": True,
                "feed": args.url,
                "findings": [
                    _finding(
                        "P1",
                        "Merchant feed could not be fetched or parsed",
                        f"Fetching {args.url} failed: {err}. Merchant Center reports the "
                        "same fetch failure and keeps stale data, then expires the items.",
                        "Make the feed URL return HTTP 200 to crawlers (check bot "
                        "protection and robots.txt) and keep it under Google's size limit.",
                        "low",
                    )
                ],
            }
            print(json.dumps(result, indent=2))
            return 1
    else:
        with open(args.file, "rb") as f:
            raw = f.read()
        site = args.site
    result = run(
        raw,
        site=site,
        sample=args.sample,
        ua=args.user_agent,
        timeout=args.timeout,
        delay=args.delay,
        ignore_robots=args.ignore_robots,
        allow_private=args.allow_private,
        feed_url=args.url or args.file,
    )
    text = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
