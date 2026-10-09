"""Tests for sitecrawl.py — stdlib site-wide crawler (units + live local crawl)."""

import json
import os
import sqlite3
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from sitecrawl import PageParser, detect_charset, in_scope, normalise

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "sitecrawl.py")
SITEWIDE = os.path.join(os.path.dirname(__file__), "..", "scripts", "sitewide.py")


class TestNormalise:
    def test_strips_fragment_and_tracking(self):
        assert (
            normalise("https://example.com/page?utm_source=x&id=2#top")
            == "https://example.com/page?id=2"
        )

    def test_default_ports_stripped(self):
        assert normalise("https://example.com:443/") == "https://example.com/"
        assert normalise("http://example.com:80/") == "http://example.com/"

    def test_non_http_none(self):
        assert normalise("mailto:x@example.com") is None
        assert normalise("javascript:void(0)") is None

    def test_empty_path_becomes_root(self):
        assert normalise("https://example.com") == "https://example.com/"

    def test_query_sorted_for_stability(self):
        assert normalise("https://e.com/p?b=2&a=1") == normalise(
            "https://e.com/p?a=1&b=2"
        )


class TestInScope:
    def test_exact_host(self):
        assert in_scope("https://example.com/x", "example.com", False)
        assert not in_scope("https://blog.example.com/x", "example.com", False)

    def test_subdomains_flag(self):
        assert in_scope("https://blog.example.com/x", "www.example.com", True)
        assert not in_scope("https://other.com/x", "example.com", True)


class TestDetectCharset:
    def test_bom_wins(self):
        assert detect_charset(b"\xef\xbb\xbfhello", "latin-1") == "utf-8"

    def test_header_charset(self):
        assert detect_charset(b"hello", "iso-8859-1") == "iso-8859-1"

    def test_meta_charset_sniffed(self):
        assert detect_charset(b'<meta charset="windows-1252">', None) == "windows-1252"

    def test_default_utf8(self):
        assert detect_charset(b"hello", None) == "utf-8"


PAGE = """<html lang="en-AU"><head>
<title>My  Test   Page</title>
<meta name="description" content="A description.">
<meta name="robots" content="index,follow">
<meta name="viewport" content="width=device-width">
<meta property="og:title" content="OG">
<link rel="canonical" href="/canon">
<script type="application/ld+json">{"@type": "Organization"}</script>
</head><body>
<h1>Main Heading</h1><h2>Sub</h2>
<img src="a.png" alt="ok"><img src="b.png">
<a href="/inner">Inner link</a>
<a href="https://other.com/x" target="_blank">Unsafe</a>
<p>Body words here for counting.</p>
<script>ignored_words_here()</script>
</body></html>"""


class TestPageParser:
    def _parse(self, html=PAGE, base="https://example.com/page"):
        p = PageParser(base)
        p.feed(html)
        return p

    def test_title_whitespace_collapsed(self):
        assert self._parse().title == "My Test Page"

    def test_meta_and_lang_and_viewport(self):
        p = self._parse()
        assert p.meta_desc == "A description."
        assert p.meta_robots == "index,follow"
        assert p.html_lang == "en-AU"
        assert p.viewport == "width=device-width"
        assert p.og_present == 1

    def test_canonical_absolutised(self):
        assert self._parse().canonical == "https://example.com/canon"

    def test_h1_and_images(self):
        p = self._parse()
        assert p.h1 == ["Main Heading"]
        assert p.images == 2
        assert p.images_no_alt == 1

    def test_links_with_anchors(self):
        p = self._parse()
        targets = {t: a for t, a, _ in p.links}
        assert targets["https://example.com/inner"] == "Inner link"
        assert "https://other.com/x" in targets

    def test_blank_no_noopener_counted(self):
        assert self._parse().blank_no_noopener == 1

    def test_jsonld_counted_but_excluded_from_words(self):
        p = self._parse()
        assert p.jsonld_count == 1
        assert "organization" not in " ".join(p._text_chunks)

    def test_script_text_excluded_from_word_count(self):
        p = self._parse()
        assert "ignored_words_here" not in " ".join(p._text_chunks)
        assert p.word_count > 0

    def test_content_hash_stable_across_whitespace(self):
        a = self._parse("<body><p>Same   text</p></body>")
        b = self._parse("<body><p>Same text</p></body>")
        assert a.content_hash == b.content_hash


# --------------------------------------------------------------------------- #
# Live crawl against a local stdlib HTTP server
# --------------------------------------------------------------------------- #
DUP_BODY = "<html><head><title>Duplicate Title</title></head><body><p>Exactly the same body content for both pages.</p></body></html>"

SITE = {
    "/": (
        200,
        "<html><head><title>Home</title></head><body>"
        '<a href="/about">About</a> <a href="/missing">Broken</a>'
        ' <a href="/dup1">D1</a> <a href="/dup2">D2</a>'
        ' <a href="/redirect">Old</a>'
        "<p>Welcome to the test site home page with words.</p></body></html>",
    ),
    "/about": (
        200,
        "<html><head><title>About</title></head><body>"
        '<a href="/">Home</a><p>About page content here.</p></body></html>',
    ),
    "/dup1": (200, DUP_BODY),
    "/dup2": (200, DUP_BODY),
    "/orphan": (
        200,
        "<html><head><title>Orphan</title></head><body>"
        "<p>No internal links point here.</p></body></html>",
    ),
    "/sitemap.xml": (
        200,
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>{base}/</loc></url><url><loc>{base}/about</loc></url>"
        "<url><loc>{base}/orphan</loc></url></urlset>",
    ),
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        base = f"http://{self.headers['Host']}"
        if self.path == "/redirect":
            self.send_response(301)
            self.send_header("Location", "/about")
            self.end_headers()
            return
        entry = SITE.get(self.path)
        if entry is None:
            self.send_response(404)
            ct = "text/html"
            body = b"<html><body>not found</body></html>"
        else:
            self.send_response(200)
            ct = "application/xml" if self.path.endswith(".xml") else "text/html"
            body = entry[1].replace("{base}", base).encode()
        self.send_header("Content-Type", f"{ct}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep pytest output clean


def _crawl(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    out_dir = os.path.join(str(tmp_path), "crawl")
    try:
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                base + "/",
                "--allow-private",
                "--max-urls",
                "50",
                "--concurrency",
                "4",
                "--timeout",
                "5",
                "--out",
                out_dir,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout), os.path.join(out_dir, "site.db"), base


class TestLiveCrawl:
    def test_crawl_and_sitewide_audit(self, tmp_path):
        summary, db_path, base = _crawl(tmp_path)

        assert summary["pages"] >= 7  # home, about, dup1/2, orphan, redirect, missing
        assert summary["in_sitemap"] == 3
        assert os.path.exists(db_path)

        con = sqlite3.connect(db_path)
        page = {
            u: (s, r)
            for u, s, r in con.execute("SELECT url, status, index_reason FROM pages")
        }
        assert page[base + "/"][0] == 200
        assert page[base + "/missing"][0] == 404
        assert page[base + "/redirect"][1].startswith("redirect")
        # orphan was discovered via the sitemap despite having no inbound links
        assert page[base + "/orphan"][0] == 200
        # the link graph recorded the broken internal link
        broken = con.execute(
            "SELECT COUNT(*) FROM links l JOIN pages p ON p.url=l.target "
            "WHERE l.type='internal' AND p.status=404"
        ).fetchone()[0]
        assert broken >= 1
        con.close()

        # sitewide audit over the real crawl
        result = subprocess.run(
            [sys.executable, SITEWIDE, "--db", db_path, "--json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        titles = {f["title"]: f for f in data["findings"]}
        assert "Internal links point at broken pages" in titles
        assert titles["Internal links point at broken pages"]["priority"] == "P0"
        assert "Duplicate titles across pages" in titles
        assert "Duplicate page content across URLs" in titles
        assert "Orphan pages (no inbound internal links)" in titles
        assert "Internal links resolve through redirects" in titles
        assert "sitewide" in data["module_scores"]

        # capped SELECT drill-down works, non-SELECT is refused
        q = subprocess.run(
            [
                sys.executable,
                SITEWIDE,
                "--db",
                db_path,
                "--query",
                "SELECT url FROM pages WHERE status=404",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert q.returncode == 0
        assert any("/missing" in row["url"] for row in json.loads(q.stdout))
        bad = subprocess.run(
            [
                sys.executable,
                SITEWIDE,
                "--db",
                db_path,
                "--query",
                "DELETE FROM pages",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert bad.returncode == 1


class TestRobotsFetch:
    """robots.txt is fetched with the crawl UA and read per RFC 9309."""

    def _patch(self, monkeypatch, responses):
        import sitecrawl

        calls = []

        def fake_fetch(url, opener, ua, timeout, retries=2, allow_private=False):
            calls.append((url, ua))
            return responses.pop(0)

        monkeypatch.setattr(sitecrawl, "fetch", fake_fetch)
        return sitecrawl, calls

    def test_uses_crawl_user_agent(self, monkeypatch):
        sitecrawl, calls = self._patch(
            monkeypatch,
            [{"status": 200, "raw": b"User-agent: *\nDisallow: /private\n"}],
        )
        rp, note = sitecrawl.load_robots("https://e.com/", None, "MyBot/2.0", 5)
        assert calls == [("https://e.com/robots.txt", "MyBot/2.0")]
        assert note is None
        assert rp.can_fetch("MyBot/2.0", "https://e.com/page")
        assert not rp.can_fetch("MyBot/2.0", "https://e.com/private/x")

    def test_4xx_means_allow_all(self, monkeypatch):
        # Cloudflare Browser Integrity Check answers unknown UAs with 403 (1010).
        # RFC 9309: any 4xx means "no robots.txt", not "disallow everything".
        sitecrawl, _ = self._patch(monkeypatch, [{"status": 403, "location": None}])
        rp, note = sitecrawl.load_robots("https://e.com/", None, "ua", 5)
        assert note is None
        assert rp.can_fetch("ua", "https://e.com/anything")

    def test_5xx_means_disallow_all_with_note(self, monkeypatch):
        sitecrawl, _ = self._patch(monkeypatch, [{"status": 503, "location": None}])
        rp, note = sitecrawl.load_robots("https://e.com/", None, "ua", 5)
        assert not rp.can_fetch("ua", "https://e.com/")
        assert "503" in note and "--ignore-robots" in note

    def test_unreachable_means_disallow_all(self, monkeypatch):
        sitecrawl, _ = self._patch(
            monkeypatch, [{"status": None, "error": "timed out", "location": None}]
        )
        rp, note = sitecrawl.load_robots("https://e.com/", None, "ua", 5)
        assert not rp.can_fetch("ua", "https://e.com/")
        assert "timed out" in note

    def test_redirect_followed(self, monkeypatch):
        sitecrawl, calls = self._patch(
            monkeypatch,
            [
                {"status": 301, "location": "https://www.e.com/robots.txt"},
                {"status": 200, "raw": b"User-agent: *\nDisallow: /\n"},
            ],
        )
        rp, _ = sitecrawl.load_robots("https://e.com/", None, "ua", 5)
        assert calls[1][0] == "https://www.e.com/robots.txt"
        assert not rp.can_fetch("ua", "https://e.com/x")


class TestCloudflareCdnCgiLinks:
    def test_is_cdn_internal(self):
        from sitecrawl import is_cdn_internal

        assert is_cdn_internal("https://e.com/cdn-cgi/l/email-protection")
        assert not is_cdn_internal("https://e.com/contact")

    def test_email_protection_links_not_crawled_or_recorded(self):
        import argparse

        from sitecrawl import Crawl, consume

        args = argparse.Namespace(subdomains=False, max_urls=50)
        ctx = Crawl(args, "e.com")
        body = (
            "<html><body><a href='/cdn-cgi/l/email-protection#abc'>Email</a>"
            "<a href='/about'>About</a></body></html>"
        )
        r = {
            "status": 200,
            "headers": None,
            "body": body,
            "content_type": "text/html",
            "ms": 1,
            "size": len(body),
            "location": None,
            "error": None,
        }
        consume("https://e.com/", 0, r, ctx)
        targets = [row[1] for row in ctx.link_rows]
        assert targets == ["https://e.com/about"]
        assert all("/cdn-cgi/" not in u for u, _ in ctx.frontier)
