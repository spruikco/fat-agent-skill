"""Tests for sitewide.py — site-level checks over a synthetic crawl DB."""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from punchlist import update_punchlist
from sitecrawl import SCHEMA
from sitewide import as_scores_shape, crawl_stats, run_checks, run_query

import pytest


def _db():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    return con


def _page(con, url, **kw):
    row = {
        "url": url,
        "status": 200,
        "content_type": "text/html",
        "indexable": 1,
        "title": f"Title {url}",
        "meta_desc": f"Desc {url}",
        "content_hash": f"hash-{url}",
        "word_count": 500,
        "response_ms": 100,
        "in_sitemap": 0,
    }
    row.update(kw)
    cols = ",".join(row)
    con.execute(
        f"INSERT INTO pages ({cols}) VALUES ({','.join('?' * len(row))})",
        list(row.values()),
    )


def _link(con, source, target):
    con.execute(
        "INSERT INTO links VALUES (?,?,?,?,?)", (source, target, "a", "", "internal")
    )


def _keys(findings):
    return {f["key"] for f in findings}


class TestChecks:
    def test_clean_site_no_findings(self):
        con = _db()
        _page(con, "https://e.com/")
        _page(con, "https://e.com/a")
        _link(con, "https://e.com/", "https://e.com/a")
        _link(con, "https://e.com/a", "https://e.com/")
        assert run_checks(con) == []

    def test_broken_internal_links_p0(self):
        con = _db()
        _page(con, "https://e.com/")
        _page(con, "https://e.com/dead", status=404, indexable=0)
        _link(con, "https://e.com/", "https://e.com/dead")
        _link(con, "https://e.com/dead", "https://e.com/")
        findings = {f["key"]: f for f in run_checks(con)}
        assert findings["broken_internal_links"]["priority"] == "P0"
        assert "https://e.com/dead" in findings["broken_internal_links"]["description"]
        assert "broken_4xx" in findings

    def test_403_and_429_not_treated_as_broken(self):
        con = _db()
        _page(con, "https://e.com/")
        _page(con, "https://e.com/waf", status=403, indexable=0)
        _link(con, "https://e.com/", "https://e.com/waf")
        _link(con, "https://e.com/waf", "https://e.com/")
        keys = _keys(run_checks(con))
        assert "broken_internal_links" not in keys
        assert "broken_4xx" not in keys

    def test_server_5xx_p0(self):
        con = _db()
        _page(con, "https://e.com/boom", status=500, indexable=0)
        _link(con, "https://e.com/x", "https://e.com/boom")
        findings = {f["key"]: f for f in run_checks(con)}
        assert findings["server_5xx"]["priority"] == "P0"

    def test_duplicate_title_only_counts_indexable(self):
        con = _db()
        _page(con, "https://e.com/a", title="Same")
        _page(con, "https://e.com/b", title="Same")
        _page(con, "https://e.com/c", title="Same", indexable=0)
        for u in ("a", "b", "c"):
            _link(con, "https://e.com/", f"https://e.com/{u}")
        findings = {f["key"]: f for f in run_checks(con)}
        assert findings["duplicate_title"]["count"] == 1  # extras beyond the first

    def test_duplicate_content_clusters(self):
        con = _db()
        _page(con, "https://e.com/a", content_hash="samehash")
        _page(con, "https://e.com/b", content_hash="samehash")
        for u in ("a", "b"):
            _link(con, "https://e.com/", f"https://e.com/{u}")
        assert "duplicate_content" in _keys(run_checks(con))

    def test_orphan_pages(self):
        con = _db()
        _page(con, "https://e.com/")
        _page(con, "https://e.com/orphan", in_sitemap=1)
        _link(con, "https://e.com/x", "https://e.com/")
        findings = {f["key"]: f for f in run_checks(con)}
        assert "https://e.com/orphan" in findings["orphan_pages"]["description"]

    def test_thin_slow_and_redirects(self):
        con = _db()
        _page(con, "https://e.com/thin", word_count=50)
        _page(con, "https://e.com/slow", response_ms=3500)
        _page(
            con,
            "https://e.com/old",
            status=301,
            indexable=0,
            redirect_to="https://e.com/new",
        )
        for u in ("thin", "slow", "old"):
            _link(con, "https://e.com/", f"https://e.com/{u}")
        keys = _keys(run_checks(con))
        assert {"thin_content", "slow_pages", "internal_redirects"} <= keys


class TestSitemapChecks:
    def test_sitemap_redirect_is_not_an_internal_link_finding(self):
        """A 301 that only the sitemap points at must NOT be blamed on
        internal links — that mislabel cost a real diagnosis (spruik.co)."""
        con = _db()
        _page(
            con,
            "https://e.com/old",
            status=301,
            indexable=0,
            redirect_to="https://e.com/new",
            in_sitemap=1,
        )
        findings = {f["key"]: f for f in run_checks(con)}
        assert "sitemap_redirects" in findings
        assert "internal_redirects" not in findings

    def test_linked_redirect_still_counts_as_internal(self):
        con = _db()
        _page(
            con,
            "https://e.com/old",
            status=301,
            indexable=0,
            redirect_to="https://e.com/new",
        )
        _link(con, "https://e.com/", "https://e.com/old")
        assert "internal_redirects" in _keys(run_checks(con))

    def test_sitemap_broken_urls(self):
        con = _db()
        _page(con, "https://e.com/ghost", status=404, indexable=0, in_sitemap=1)
        _page(con, "https://e.com/waf", status=403, indexable=0, in_sitemap=1)
        findings = {f["key"]: f for f in run_checks(con)}
        assert findings["sitemap_broken"]["count"] == 1  # 403 excluded
        assert findings["sitemap_broken"]["priority"] == "P1"

    def test_sitemap_fetch_error_counts_as_broken(self):
        con = _db()
        _page(
            con,
            "https://e.com/dead",
            status=None,
            indexable=0,
            in_sitemap=1,
            error="timed out",
        )
        assert "sitemap_broken" in _keys(run_checks(con))

    def test_slash_hop_pattern_flagged_as_systemic(self):
        con = _db()
        for i in range(5):
            _page(
                con,
                f"https://e.com/page{i}",
                status=301,
                indexable=0,
                redirect_to=f"https://e.com/page{i}/",
                in_sitemap=1,
            )
        findings = {f["key"]: f for f in run_checks(con)}
        desc = findings["sitemap_redirects"]["description"]
        assert "SYSTEMIC: 5 of 5 are pure trailing-slash hops" in desc

    def test_non_slash_redirects_not_flagged_systemic(self):
        con = _db()
        _page(
            con,
            "https://e.com/old",
            status=301,
            indexable=0,
            redirect_to="https://e.com/completely-different",
            in_sitemap=1,
        )
        findings = {f["key"]: f for f in run_checks(con)}
        assert "SYSTEMIC" not in findings["sitemap_redirects"]["description"]

    def test_fetch_errors_but_not_ssrf_blocks(self):
        con = _db()
        _page(con, "https://e.com/t", status=None, indexable=0, error="timed out")
        _page(
            con,
            "https://e.com/b",
            status=None,
            indexable=0,
            error="blocked: private/internal host (SSRF guard)",
        )
        findings = {f["key"]: f for f in run_checks(con)}
        assert findings["fetch_errors"]["count"] == 1

    def test_sample_cap_notes_remainder(self):
        con = _db()
        for i in range(12):
            _page(con, f"https://e.com/dead{i}", status=404, indexable=0)
        findings = {f["key"]: f for f in run_checks(con)}
        assert "+4 more" in findings["broken_4xx"]["description"]

    def test_findings_sorted_by_priority(self):
        con = _db()
        _page(con, "https://e.com/thin", word_count=50)  # P2
        _page(con, "https://e.com/boom", status=500, indexable=0)  # P0
        _link(con, "https://e.com/", "https://e.com/thin")
        _link(con, "https://e.com/", "https://e.com/boom")
        findings = run_checks(con)
        assert findings[0]["priority"] == "P0"


class TestPunchlistIntegration:
    def test_findings_flow_and_auto_resolve(self):
        con = _db()
        _page(con, "https://e.com/")
        _page(con, "https://e.com/dead", status=404, indexable=0)
        _link(con, "https://e.com/", "https://e.com/dead")
        _link(con, "https://e.com/dead", "https://e.com/")
        scores = as_scores_shape(run_checks(con), crawl_stats(con))

        punch = {"version": 1, "url": "", "updated": "", "items": []}
        stats = update_punchlist(punch, scores, now="T1")
        assert stats["new"] >= 2  # broken links + broken pages

        # clean re-crawl: link fixed, dead page gone
        con2 = _db()
        _page(con2, "https://e.com/")
        _page(con2, "https://e.com/a")
        _link(con2, "https://e.com/", "https://e.com/a")
        _link(con2, "https://e.com/a", "https://e.com/")
        clean = as_scores_shape(run_checks(con2), crawl_stats(con2))
        stats = update_punchlist(punch, clean, now="T2")
        assert stats["resolved"] >= 2
        assert all(i["status"] == "resolved" for i in punch["items"])

    def test_titles_stable_across_counts(self):
        """Counts change between crawls — identity must not."""
        con_a = _db()
        _page(con_a, "https://e.com/dead1", status=404, indexable=0)
        con_b = _db()
        _page(con_b, "https://e.com/dead1", status=404, indexable=0)
        _page(con_b, "https://e.com/dead2", status=404, indexable=0)
        title_a = [f["title"] for f in run_checks(con_a) if f["key"] == "broken_4xx"]
        title_b = [f["title"] for f in run_checks(con_b) if f["key"] == "broken_4xx"]
        assert title_a == title_b


class TestQuery:
    def test_select_capped(self):
        con = _db()
        for i in range(60):
            _page(con, f"https://e.com/p{i}")
        rows = run_query(con, "SELECT url FROM pages")
        assert len(rows) == 50

    def test_non_select_refused(self):
        con = _db()
        with pytest.raises(ValueError):
            run_query(con, "DELETE FROM pages")
