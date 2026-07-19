#!/usr/bin/env python3
"""Site-wide crawler for FAT Agent — a token-cheap, stdlib-only site crawl.

Crawls a site concurrently and writes every page and every internal/external
link into a SQLite database (pages + links tables), printing only a compact
JSON summary to stdout. The heavy data stays on disk where `sitewide.py` runs
site-level audits (duplicate titles/content, orphan pages, broken internal
links) and capped SQL drill-downs — nothing large ever needs to enter the
conversation context.

Derived from Froggy (Spruik's internal crawler) — same author, trimmed to the
audit-relevant core: no JS rendering (use render_js.py for individual SPA
pages), no CSV/HTML export (FAT has its own report pipeline).

Usage:
    python scripts/sitecrawl.py https://example.com --max-urls 300 \
        --out ./.fat-work/crawl

Then:
    python scripts/sitewide.py --db ./.fat-work/crawl/site.db
"""

import argparse
import gzip
import hashlib
import ipaddress
import json
import os
import re
import socket
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urldefrag, urlencode, urljoin, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)
from urllib.robotparser import RobotFileParser

MAX_BODY_BYTES = 3_000_000  # don't download more than ~3MB of any one page
MAX_DECOMPRESS_BYTES = 30_000_000  # cap gunzipped sitemap size (zip-bomb guard)
RETRY_STATUSES = {429, 503}  # transient — worth a backoff+retry (not 403)
MAX_SITEMAPS = 20
MAX_SITEMAP_URLS = 5000
DEFAULT_UA = "FATAgent/1.0 (+https://github.com/spruikco/fat-agent-skill)"

# Tracking / session params that create duplicate URLs — stripped during
# normalisation so ?utm_*, gclid, etc. don't crawl as separate pages.
TRACKING_PARAMS = {
    "gclid",
    "gclsrc",
    "dclid",
    "fbclid",
    "msclkid",
    "yclid",
    "twclid",
    "mc_cid",
    "mc_eid",
    "_hsenc",
    "_hsmi",
    "igshid",
    "vero_id",
    "vero_conv",
    "ref",
    "ref_src",
    "mkt_tok",
    "s_kwcid",
    "gbraid",
    "wbraid",
}
TRACKING_PREFIXES = ("utm_", "pk_", "piwik_", "matomo_")


# --------------------------------------------------------------------------- #
# SSRF guard — never let a crawl reach internal hosts (loopback / private /
# link-local, incl. the cloud metadata endpoint). Cached per host.
# --------------------------------------------------------------------------- #
_host_block_cache: dict[str, bool] = {}


def host_is_blocked(host: str | None, allow_private: bool = False) -> bool:
    """True if the host resolves to a private / loopback / link-local address."""
    if not host:
        return True
    if allow_private:
        return False
    if host in _host_block_cache:
        return _host_block_cache[host]
    blocked = False
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                blocked = True
                break
    except Exception:
        blocked = False  # unresolvable → let fetch surface the real network error
    _host_block_cache[host] = blocked
    return blocked


# --------------------------------------------------------------------------- #
# Charset detection — the HTTP header often omits it; sniff the meta tag so
# non-UTF-8 pages don't mojibake their titles / word counts.
# --------------------------------------------------------------------------- #
_META_CHARSET_RE = re.compile(
    rb"""<meta[^>]+charset=["']?\s*([a-zA-Z0-9_\-]+)"""
    rb"""|<meta[^>]+content=["'][^"']*charset=\s*([a-zA-Z0-9_\-]+)""",
    re.IGNORECASE,
)


def detect_charset(raw: bytes, header_charset: str | None) -> str:
    if raw[:3] == b"\xef\xbb\xbf":
        return "utf-8"
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if header_charset:
        return header_charset
    m = _META_CHARSET_RE.search(raw[:4096])
    if m:
        cs = (m.group(1) or m.group(2) or b"").decode("ascii", "replace").strip()
        if cs:
            return cs.lower()
    return "utf-8"


# --------------------------------------------------------------------------- #
# URL helpers
# --------------------------------------------------------------------------- #
def _clean_query(query: str) -> str:
    if not query:
        return ""
    kept = [
        (k, v)
        for k, v in parse_qsl(query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
        and not k.lower().startswith(TRACKING_PREFIXES)
    ]
    return urlencode(sorted(kept))


def normalise(url: str) -> str | None:
    """Canonical crawl key: defrag, drop tracking params, strip default ports."""
    url = urldefrag(url)[0]
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return None
    netloc = p.netloc.lower()
    netloc = (
        re.sub(r":80$", "", netloc)
        if p.scheme == "http"
        else re.sub(r":443$", "", netloc)
    )
    path = p.path or "/"
    query = _clean_query(p.query)
    return f"{p.scheme}://{netloc}{path}" + (f"?{query}" if query else "")


def reg_domain(host: str) -> str:
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def in_scope(url: str, start_host: str, allow_subdomains: bool) -> bool:
    host = urlparse(url).netloc.lower()
    if host == start_host:
        return True
    if allow_subdomains:
        return reg_domain(host) == reg_domain(start_host)
    return False


def coerce_url(url: str) -> str:
    """Accept bare 'example.com' and assume https://."""
    url = (url or "").strip()
    if url and not urlparse(url).scheme:
        url = "https://" + url
    return url


def safe_url(url: str) -> str:
    """Percent-encode spaces/control chars so http.client accepts the request."""
    return re.sub(r"[\x00-\x20]", lambda m: "%%%02X" % ord(m.group(0)), url)


# --------------------------------------------------------------------------- #
# HTTP fetch — no auto-redirect (each hop is recorded as its own row)
# --------------------------------------------------------------------------- #
class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # surface the 3xx as an HTTPError instead of following it


def make_opener(insecure: bool = False):
    handlers: list = [_NoRedirect()]
    if insecure:
        import ssl

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(HTTPSHandler(context=ctx))
    return build_opener(*handlers)


def fetch(url, opener, ua, timeout, retries=2, allow_private=False):
    """Return dict with status/headers/body/content_type/ms/size/location/error.

    Retries transient failures (429/503/network) with exponential backoff.
    Any unexpected error becomes an error row — never crashes the crawl.
    """
    if host_is_blocked(urlparse(url).hostname, allow_private):
        return {
            "status": None,
            "headers": None,
            "body": None,
            "content_type": None,
            "ms": 0,
            "size": 0,
            "location": None,
            "error": "blocked: private/internal host (SSRF guard)",
        }
    req = Request(
        safe_url(url),
        headers={
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
        },
    )
    t0 = time.time()
    last = None
    for attempt in range(retries + 1):
        try:
            resp = opener.open(req, timeout=timeout)
            raw = resp.read(MAX_BODY_BYTES + 1)
            truncated = len(raw) > MAX_BODY_BYTES
            raw = raw[:MAX_BODY_BYTES]
            ms = int((time.time() - t0) * 1000)
            ctype = resp.headers.get_content_type()
            charset = detect_charset(raw, resp.headers.get_content_charset())
            body = (
                raw.decode(charset, errors="replace") if ctype == "text/html" else None
            )
            return {
                "status": resp.status,
                "headers": resp.headers,
                "body": body,
                "content_type": ctype,
                "ms": ms,
                "size": len(raw),
                "location": None,
                "error": None,
                "truncated": truncated,
                "raw": raw,
            }
        except HTTPError as e:
            ms = int((time.time() - t0) * 1000)
            loc = e.headers.get("Location") if e.headers else None
            last = {
                "status": e.code,
                "headers": e.headers,
                "body": None,
                "content_type": e.headers.get_content_type() if e.headers else None,
                "ms": ms,
                "size": 0,
                "location": urljoin(url, loc) if loc else None,
                "error": None,
            }
            if e.code in RETRY_STATUSES and attempt < retries:
                ra = e.headers.get("Retry-After") if e.headers else None
                delay = 0.6 * (2**attempt)
                if ra and ra.strip().isdigit():
                    delay = min(float(ra.strip()), 30.0)
                time.sleep(delay)
                continue
            return last
        except (URLError, TimeoutError, ConnectionError, OSError) as e:
            ms = int((time.time() - t0) * 1000)
            last = {
                "status": None,
                "headers": None,
                "body": None,
                "content_type": None,
                "ms": ms,
                "size": 0,
                "location": None,
                "error": str(e)[:300],
            }
            if attempt < retries:
                time.sleep(0.6 * (2**attempt))
                continue
            return last
        except Exception as e:  # malformed URL, decode errors — never crash
            ms = int((time.time() - t0) * 1000)
            return {
                "status": None,
                "headers": None,
                "body": None,
                "content_type": None,
                "ms": ms,
                "size": 0,
                "location": None,
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            }
    return last


# --------------------------------------------------------------------------- #
# HTML parsing
# --------------------------------------------------------------------------- #
class PageParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.title_parts = []
        self.in_title = False
        self.meta_desc = None
        self.meta_robots = None
        self.canonical = None
        self.h1 = []
        self.in_h1 = False
        self._h1_buf = []
        self.h2_count = 0
        self.hreflang = 0
        self.images = 0
        self.images_no_alt = 0
        self.links = []  # (target_abs, anchor, rel)
        self._skip_depth = 0
        self._text_words = 0
        self._text_chunks = []  # for content hash (bounded)
        self._in_a = False
        self._a_href = None
        self._a_rel = None
        self._a_buf = []
        self.html_lang = None
        self.viewport = None
        self.og_present = 0
        self.jsonld_count = 0
        self.blank_no_noopener = 0
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        # JSON-LD — count it, but keep it out of the body word count
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_jsonld = True
            self.jsonld_count += 1
            self._skip_depth += 1
            return
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag == "html":
            self.html_lang = (a.get("lang") or "").strip() or None
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            name = a.get("name", "").lower()
            prop = a.get("property", "").lower()
            if name == "description" and self.meta_desc is None:
                self.meta_desc = a.get("content", "").strip()
            elif name == "robots" and self.meta_robots is None:
                self.meta_robots = a.get("content", "").strip()
            elif name == "viewport" and self.viewport is None:
                self.viewport = a.get("content", "").strip()
            if prop in ("og:title", "og:image", "og:description", "og:url", "og:type"):
                self.og_present = 1
        elif tag == "link":
            rel = a.get("rel", "").lower()
            if "canonical" in rel and a.get("href"):
                self.canonical = urljoin(self.base, a["href"])
            if "alternate" in rel and a.get("hreflang"):
                self.hreflang += 1
        elif tag == "h1":
            self.in_h1 = True
            self._h1_buf = []
        elif tag == "h2":
            self.h2_count += 1
        elif tag == "img":
            self.images += 1
            if not a.get("alt", "").strip():
                self.images_no_alt += 1
        elif tag == "a" and a.get("href"):
            self._in_a = True
            self._a_href = urljoin(self.base, urldefrag(a["href"])[0])
            self._a_rel = a.get("rel", "")
            self._a_buf = []
            if a.get("target", "").lower() == "_blank":
                rel = a.get("rel", "").lower()
                if "noopener" not in rel and "noreferrer" not in rel:
                    self.blank_no_noopener += 1

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in self.SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self.in_title = False
        elif tag == "h1":
            self.in_h1 = False
            txt = " ".join("".join(self._h1_buf).split())
            if txt:
                self.h1.append(txt)
        elif tag == "a" and self._in_a:
            anchor = " ".join("".join(self._a_buf).split())[:200]
            self.links.append((self._a_href, anchor, self._a_rel))
            self._in_a = False
            self._a_href = None

    def handle_data(self, data):
        if self._in_jsonld:
            return
        if self.in_title:
            self.title_parts.append(data)
        if self.in_h1:
            self._h1_buf.append(data)
        if self._in_a:
            self._a_buf.append(data)
        if self._skip_depth == 0:
            words = data.split()
            if words:
                self._text_words += len(words)
                if len(self._text_chunks) < 4000:  # bound memory for hashing
                    self._text_chunks.append(data.strip().lower())

    @property
    def title(self):
        return " ".join("".join(self.title_parts).split()) or None

    @property
    def word_count(self):
        return self._text_words

    @property
    def content_hash(self):
        text = re.sub(r"\s+", " ", " ".join(c for c in self._text_chunks if c))
        return (
            hashlib.md5(text.encode("utf-8", "replace")).hexdigest() if text else None
        )


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE pages (
  url TEXT PRIMARY KEY, status INTEGER, redirect_to TEXT,
  content_type TEXT, depth INTEGER, response_ms INTEGER, size_bytes INTEGER,
  title TEXT, title_len INTEGER, meta_desc TEXT, meta_desc_len INTEGER,
  h1 TEXT, h1_count INTEGER, h2_count INTEGER, hreflang_count INTEGER,
  meta_robots TEXT, x_robots TEXT, canonical TEXT, canonical_self INTEGER,
  word_count INTEGER, content_hash TEXT, images INTEGER, images_no_alt INTEGER,
  internal_links INTEGER, external_links INTEGER,
  html_lang TEXT, viewport TEXT, og_present INTEGER,
  jsonld_count INTEGER, blank_no_noopener INTEGER,
  sec_headers TEXT, truncated INTEGER,
  indexable INTEGER, index_reason TEXT, in_sitemap INTEGER, error TEXT
);
CREATE TABLE links (source TEXT, target TEXT, anchor TEXT, rel TEXT, type TEXT);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX idx_links_target ON links(target);
CREATE INDEX idx_pages_status ON pages(status);
CREATE INDEX idx_pages_hash ON pages(content_hash);
"""

PAGE_COLS = [
    "url",
    "status",
    "redirect_to",
    "content_type",
    "depth",
    "response_ms",
    "size_bytes",
    "title",
    "title_len",
    "meta_desc",
    "meta_desc_len",
    "h1",
    "h1_count",
    "h2_count",
    "hreflang_count",
    "meta_robots",
    "x_robots",
    "canonical",
    "canonical_self",
    "word_count",
    "content_hash",
    "images",
    "images_no_alt",
    "internal_links",
    "external_links",
    "html_lang",
    "viewport",
    "og_present",
    "jsonld_count",
    "blank_no_noopener",
    "sec_headers",
    "truncated",
    "indexable",
    "index_reason",
    "in_sitemap",
    "error",
]


def init_db(path: str) -> sqlite3.Connection:
    if os.path.exists(path):
        os.remove(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


# --------------------------------------------------------------------------- #
# Sitemap discovery — needed so orphan pages (no inbound internal links) can be
# discovered at all: by definition a link-following crawl can't reach them.
# --------------------------------------------------------------------------- #
def _sitemap_body(url, opener, ua, timeout, allow_private):
    r = fetch(url, opener, ua, timeout, retries=1, allow_private=allow_private)
    raw = r.get("raw")
    if r.get("error") or not raw:
        return None
    if url.endswith(".gz") or raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw[:MAX_DECOMPRESS_BYTES])[:MAX_DECOMPRESS_BYTES]
        except Exception:
            return None
    return raw


def discover_sitemap_urls(
    start_url, robots_sitemaps, opener, ua, timeout, allow_private
):
    """Return the set of URLs listed in the site's sitemap(s). Best-effort."""
    origin = "{0.scheme}://{0.netloc}".format(urlparse(start_url))
    queue = deque(robots_sitemaps or [origin + "/sitemap.xml"])
    visited: set[str] = set()
    found: set[str] = set()
    while queue and len(visited) < MAX_SITEMAPS and len(found) < MAX_SITEMAP_URLS:
        sm = queue.popleft()
        if sm in visited:
            continue
        visited.add(sm)
        raw = _sitemap_body(sm, opener, ua, timeout, allow_private)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            continue
        is_index = root.tag.split("}")[-1].lower() == "sitemapindex"
        locs = [
            e.text.strip()
            for e in root.iter()
            if e.tag.split("}")[-1].lower() == "loc" and e.text and e.text.strip()
        ]
        if is_index:
            queue.extend(loc for loc in locs if loc not in visited)
        else:
            for loc in locs:
                found.add(loc)
                if len(found) >= MAX_SITEMAP_URLS:
                    break
    return found


# --------------------------------------------------------------------------- #
# Crawl
# --------------------------------------------------------------------------- #
class Crawl:
    def __init__(self, args, start_host):
        self.args = args
        self.start_host = start_host
        self.seen: set[str] = set()
        self.frontier: deque = deque()
        self.rows: list[dict] = []
        self.link_rows: list[tuple] = []
        self.errors = 0
        self.sitemap_urls: set[str] = set()


def consume(url, depth, r, ctx: Crawl):
    """Turn one fetch result into a page row (+ discovered links). Mutates ctx.

    Runs on the main thread only, so mutating shared state is safe.
    """
    args, start_host = ctx.args, ctx.start_host

    if r["error"]:
        ctx.errors += 1
        ctx.rows.append(
            {
                "url": url,
                "status": None,
                "error": r["error"],
                "depth": depth,
                "response_ms": r["ms"],
                "indexable": 0,
                "index_reason": "fetch error",
            }
        )
        return

    status = r["status"]
    x_robots = r["headers"].get("X-Robots-Tag") if r["headers"] else None
    row = {
        "url": url,
        "status": status,
        "depth": depth,
        "response_ms": r["ms"],
        "size_bytes": r["size"],
        "content_type": r["content_type"],
        "x_robots": x_robots,
    }

    if status and 300 <= status < 400:
        row["redirect_to"] = r["location"]
        row["indexable"] = 0
        row["index_reason"] = f"redirect ({status})"
        if r["location"]:
            nu = normalise(r["location"])
            if (
                nu
                and nu not in ctx.seen
                and in_scope(nu, start_host, args.subdomains)
                and len(ctx.seen) < args.max_urls
            ):
                ctx.seen.add(nu)
                ctx.frontier.append((nu, depth + 1))
        ctx.rows.append(row)
        return

    if status is None or status >= 400:
        row["indexable"] = 0
        row["index_reason"] = f"status {status}"
        ctx.rows.append(row)
        return

    if r["body"] is None:
        row["indexable"] = 0
        row["index_reason"] = "non-HTML"
        ctx.rows.append(row)
        return

    p = PageParser(url)
    try:
        p.feed(r["body"])
    except Exception:
        pass

    internal = external = 0
    for tgt, anchor, rel in p.links:
        nt = normalise(tgt)
        if not nt:
            continue
        is_internal = in_scope(nt, start_host, args.subdomains)
        ctx.link_rows.append(
            (url, nt, anchor, rel, "internal" if is_internal else "external")
        )
        if is_internal:
            internal += 1
            if nt not in ctx.seen and len(ctx.seen) < args.max_urls:
                ctx.seen.add(nt)
                ctx.frontier.append((nt, depth + 1))
        else:
            external += 1

    robots_val = (p.meta_robots or "") + " " + (x_robots or "")
    noindex = "noindex" in robots_val.lower()
    canon_self = 1 if (p.canonical is None or normalise(p.canonical) == url) else 0
    if noindex:
        indexable, reason = 0, "noindex"
    elif not canon_self:
        indexable, reason = 0, "canonicalised elsewhere"
    else:
        indexable, reason = 1, "indexable"

    hdrs = r["headers"]
    csp_val = (hdrs.get("Content-Security-Policy") if hdrs else "") or ""
    sec = []
    if hdrs and hdrs.get("Strict-Transport-Security"):
        sec.append("hsts")
    if hdrs and hdrs.get("Content-Security-Policy"):
        sec.append("csp")
    if hdrs and hdrs.get("X-Content-Type-Options"):
        sec.append("xcto")
    if (hdrs and hdrs.get("X-Frame-Options")) or "frame-ancestors" in csp_val.lower():
        sec.append("xfo")
    if hdrs and hdrs.get("Referrer-Policy"):
        sec.append("referrer")

    row.update(
        {
            "title": p.title,
            "title_len": len(p.title) if p.title else 0,
            "meta_desc": p.meta_desc,
            "meta_desc_len": len(p.meta_desc) if p.meta_desc else 0,
            "h1": " | ".join(p.h1)[:500] if p.h1 else None,
            "h1_count": len(p.h1),
            "h2_count": p.h2_count,
            "hreflang_count": p.hreflang,
            "meta_robots": p.meta_robots,
            "canonical": p.canonical,
            "canonical_self": canon_self,
            "word_count": p.word_count,
            "content_hash": p.content_hash,
            "images": p.images,
            "images_no_alt": p.images_no_alt,
            "internal_links": internal,
            "external_links": external,
            "html_lang": p.html_lang,
            "viewport": p.viewport,
            "og_present": p.og_present,
            "jsonld_count": p.jsonld_count,
            "blank_no_noopener": p.blank_no_noopener,
            "sec_headers": ",".join(sec),
            "truncated": 1 if r.get("truncated") else 0,
            "indexable": indexable,
            "index_reason": reason,
        }
    )
    ctx.rows.append(row)


def crawl_site(ctx: Crawl, rp, opener):
    """Concurrent stdlib crawl with adaptive throttling when the site pushes back."""
    args = ctx.args
    throttle = [args.delay]

    def process(url, depth):
        if rp and not rp.can_fetch(args.user_agent, url):
            return ("robots", url, depth, None)
        if throttle[0]:
            time.sleep(throttle[0])
        return (
            "ok",
            url,
            depth,
            fetch(
                url,
                opener,
                args.user_agent,
                args.timeout,
                allow_private=args.allow_private,
            ),
        )

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        while ctx.frontier and len(ctx.rows) < args.max_urls:
            conc = (
                max(2, args.concurrency // 3)
                if throttle[0] >= 1.0
                else args.concurrency
            )
            batch = []
            while (
                ctx.frontier
                and len(batch) < conc
                and len(ctx.rows) + len(batch) < args.max_urls
            ):
                batch.append(ctx.frontier.popleft())
            before = len(ctx.rows)
            for fut in [pool.submit(process, u, d) for u, d in batch]:
                kind, url, depth, r = fut.result()
                if kind == "robots":
                    ctx.rows.append(
                        {
                            "url": url,
                            "status": None,
                            "error": "blocked by robots.txt",
                            "depth": depth,
                            "index_reason": "robots disallow",
                            "indexable": 0,
                        }
                    )
                else:
                    consume(url, depth, r, ctx)
            # adapt: mostly 403/429 → slow down; clean wave → speed back up
            wave = ctx.rows[before:]
            blocked = sum(1 for w in wave if w.get("status") in (403, 429))
            if wave and blocked / len(wave) >= 0.3:
                throttle[0] = min((throttle[0] or 0.0) + 1.0, 6.0)
            elif blocked == 0 and throttle[0] > args.delay:
                throttle[0] = max(args.delay, throttle[0] - 0.25)
            # circuit-breaker: maxed delay and still ~all blocked → hard block
            if throttle[0] >= 6.0 and wave and blocked / len(wave) >= 0.9:
                ctx.frontier.clear()


def write_db(con, ctx: Crawl, start_url, elapsed):
    for row in ctx.rows:
        row["in_sitemap"] = 1 if row["url"] in ctx.sitemap_urls else 0
        con.execute(
            f"INSERT OR REPLACE INTO pages ({','.join(PAGE_COLS)}) "
            f"VALUES ({','.join('?' * len(PAGE_COLS))})",
            [row.get(c) for c in PAGE_COLS],
        )
    con.executemany("INSERT INTO links VALUES (?,?,?,?,?)", ctx.link_rows)
    con.executemany(
        "INSERT INTO meta VALUES (?,?)",
        [
            ("start_url", start_url),
            ("elapsed_s", f"{elapsed:.1f}"),
            ("sitemap_urls", str(len(ctx.sitemap_urls))),
        ],
    )
    con.commit()


def summary(con) -> dict:
    def q1(sql):
        return con.execute(sql).fetchone()[0]

    statuses = {
        str(row[0]): row[1]
        for row in con.execute(
            "SELECT COALESCE(status,'error'), COUNT(*) FROM pages GROUP BY status"
        )
    }
    return {
        "pages": q1("SELECT COUNT(*) FROM pages"),
        "indexable": q1("SELECT COUNT(*) FROM pages WHERE indexable=1"),
        "errors": q1("SELECT COUNT(*) FROM pages WHERE error IS NOT NULL"),
        "statuses": statuses,
        "internal_links": q1("SELECT COUNT(*) FROM links WHERE type='internal'"),
        "avg_response_ms": q1(
            "SELECT CAST(COALESCE(AVG(response_ms),0) AS INTEGER) FROM pages "
            "WHERE response_ms IS NOT NULL"
        ),
        "in_sitemap": q1("SELECT COUNT(*) FROM pages WHERE in_sitemap=1"),
    }


def build_arg_parser():
    ap = argparse.ArgumentParser(description="FAT Agent site-wide crawler")
    ap.add_argument("url", help="start URL (bare domains get https://)")
    ap.add_argument("--max-urls", type=int, default=300, help="crawl cap (default 300)")
    ap.add_argument("--concurrency", type=int, default=8, help="parallel fetches")
    ap.add_argument("--delay", type=float, default=0.0, help="politeness delay (s)")
    ap.add_argument("--timeout", type=float, default=15.0, help="per-request timeout")
    ap.add_argument("--subdomains", action="store_true", help="also crawl subdomains")
    ap.add_argument("--ignore-robots", action="store_true", help="ignore robots.txt")
    ap.add_argument("--no-sitemap", action="store_true", help="skip sitemap discovery")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification")
    ap.add_argument(
        "--allow-private",
        action="store_true",
        help="allow crawling private/loopback hosts (staging & intranet audits)",
    )
    ap.add_argument("--user-agent", default=DEFAULT_UA)
    ap.add_argument(
        "--out",
        default=os.path.join(".fat-work", "crawl"),
        help="output directory (default ./.fat-work/crawl)",
    )
    return ap


def main():
    args = build_arg_parser().parse_args()
    start = coerce_url(args.url)
    nu = normalise(start)
    if not nu:
        print(json.dumps({"error": f"not a crawlable URL: {args.url}"}))
        return 1
    start = nu
    start_host = urlparse(start).netloc.lower()
    opener = make_opener(args.insecure)

    rp = None
    robots_sitemaps = None
    if not args.ignore_robots:
        rp = RobotFileParser()
        rp.set_url("{0.scheme}://{0.netloc}/robots.txt".format(urlparse(start)))
        try:
            rp.read()
            robots_sitemaps = rp.site_maps()
        except Exception:
            rp = None  # unreadable robots.txt → crawl politely anyway

    ctx = Crawl(args, start_host)
    ctx.seen.add(start)
    ctx.frontier.append((start, 0))

    if not args.no_sitemap:
        for loc in discover_sitemap_urls(
            start,
            robots_sitemaps,
            opener,
            args.user_agent,
            args.timeout,
            args.allow_private,
        ):
            nl = normalise(loc)
            if nl:
                ctx.sitemap_urls.add(nl)
                if (
                    nl not in ctx.seen
                    and in_scope(nl, start_host, args.subdomains)
                    and len(ctx.seen) < args.max_urls
                ):
                    ctx.seen.add(nl)
                    ctx.frontier.append((nl, 0))

    t0 = time.time()
    crawl_site(ctx, rp, opener)
    elapsed = time.time() - t0

    db_path = os.path.join(args.out, "site.db")
    con = init_db(db_path)
    write_db(con, ctx, start, elapsed)

    out = summary(con)
    out["db"] = db_path
    out["elapsed_s"] = round(elapsed, 1)
    print(json.dumps(out, indent=2))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
