"""Tests for the google_guidelines module and the site-wide guideline checks."""

import datetime as dt
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules import detect_modules
from modules.google_guidelines import (
    GoogleGuidelinesModule,
    place_list_runs,
    title_is_stuffed,
)
from sitecrawl import SCHEMA, PageParser, simhash64
from sitewide import _url_shape, near_duplicate_clusters, run_checks

TODAY = dt.date(2026, 9, 24)
GOOD_HEAD = (
    "<head><title>Plumber in Carlton | Acme Plumbing</title>"
    '<meta name="description" content="Licensed Carlton plumbers for blocked drains, '
    'hot water and gas fitting. Same-day call-outs, upfront pricing, 20 years local.">'
    '<link rel="icon" href="/favicon.png"></head>'
)


def run(html, url="https://acme.example/services/", headers=None):
    m = GoogleGuidelinesModule()
    a = m.analyse(html, url=url, headers=headers, today=TODAY)
    s = m.score(a)
    return a, s, {f["title"]: f for f in m.findings}


def titles(html, **kw):
    return set(run(html, **kw)[2])


def body(text):
    return f"<html>{GOOD_HEAD}<body><main><h1>Plumbing</h1><p>{text}</p></main></body></html>"


# --------------------------------------------------------------------------- #
class TestRegistry:
    def test_always_enabled(self):
        assert "google_guidelines" in detect_modules("<html></html>")


class TestCleanPage:
    def test_clean_page_has_no_findings(self):
        html = body("We fixed a burst pipe in Lygon Street last week. " * 20)
        _, score, found = run(html)
        assert found == {}
        assert score["total"] == 100


class TestSpamPolicies:
    def test_ai_leak_flagged(self):
        assert "Unedited AI output on page (scaled content abuse risk)" in titles(
            body("As an AI language model, I can say plumbing matters.")
        )

    def test_template_placeholder_flagged(self):
        assert "Unedited AI output on page (scaled content abuse risk)" in titles(
            body("The best plumber in [City] for all your needs.")
        )

    def test_conditional_redirect_flagged(self):
        html = body("ok") + (
            "<script>if (navigator.userAgent.indexOf('Googlebot') < 0) "
            "{ window.location.href = 'https://spam.example'; }</script>"
        )
        assert "Conditional JavaScript redirect (sneaky redirect risk)" in titles(html)

    def test_back_button_hijack_flagged(self):
        html = body("ok") + (
            "<script>history.pushState(null,'',location.href);"
            "window.addEventListener('popstate', function(){ "
            "window.location.href='/recommended'; });</script>"
        )
        a, _, found = run(html)
        assert a["back_button_hijack"]
        assert found["Back button hijacking (spam policy, enforced Jun 2026)"][
            "priority"
        ] == "P1"

    def test_spa_pushstate_is_only_a_soft_note(self):
        html = body("ok") + (
            "<script>function go(u){history.pushState({},'',u)}"
            "function back(u){history.replaceState({},'',u)}</script>"
        )
        t = titles(html)
        assert "Back button hijacking (spam policy, enforced Jun 2026)" not in t
        assert "History manipulation in page scripts (verify)" in t

    def test_hidden_text_flagged(self):
        hidden = " ".join(["plumber carlton"] * 20)
        html = body("visible") + f'<div style="display:none">{hidden}</div>'
        assert "Possible hidden text (verify)" in titles(html)

    def test_hidden_modal_not_flagged(self):
        hidden = " ".join(["subscribe now"] * 20)
        html = body("visible") + f'<div class="modal" style="display:none">{hidden}</div>'
        assert "Possible hidden text (verify)" not in titles(html)

    def test_location_list_stuffing(self):
        places = ", ".join(
            "Carlton Fitzroy Richmond Collingwood Brunswick Coburg Northcote "
            "Preston Thornbury Abbotsford Kew Hawthorn".split()
        )
        html = body("We service " + places + " and more.")
        a, _, found = run(html)
        assert a["place_list_max"] >= 10
        assert "Location list stuffing (doorway / keyword stuffing signal)" in found

    def test_short_place_list_ok(self):
        assert place_list_runs("We cover Carlton, Fitzroy and Richmond.") == 0

    def test_keyword_repetition(self):
        html = body(("plumber " * 30) + ("we fix pipes in homes " * 60))
        assert "Keyword repetition in body copy" in titles(html)

    def test_unqualified_affiliate_links(self):
        html = body(
            '<a href="https://amzn.to/abc">buy</a>'
            '<a href="https://shop.example/p?aff_id=9" rel="sponsored">ok</a>'
        )
        a, _, found = run(html)
        assert a["unqualified_affiliate_links"] == ["https://amzn.to/abc"]
        assert 'Affiliate/paid links missing rel="sponsored"' in found

    def test_filler_phrasing(self):
        html = body(
            "In today's fast-paced digital landscape, look no further. "
            "We unlock the power of seamless plumbing."
        )
        assert "Generic filler phrasing (low-effort content signal)" in titles(html)


class TestSnippets:
    def test_stuffed_title(self):
        assert title_is_stuffed("SEO Melbourne | SEO Agency | Best SEO | SEO Services")
        assert title_is_stuffed("A | B | C | D | E")
        assert not title_is_stuffed("Plumber in Carlton | Acme Plumbing")

    def test_long_title(self):
        html = (
            "<html><head><title>" + "Acme plumbing services for every home "
            "and business across the whole of Melbourne</title></head><body></body></html>"
        )
        assert "Title likely truncated in results" in titles(html)

    def test_meta_lengths(self):
        short = '<html><head><meta name="description" content="Plumbing."></head></html>'
        assert "Meta description too short" in titles(short)
        long_ = (
            '<html><head><meta name="description" content="' + " ".join(f"w{i}x" for i in range(60)) + '"></head></html>'
        )
        assert "Meta description likely truncated" in titles(long_)

    def test_nosnippet_flags_ai_overviews(self):
        html = body("x").replace(
            "<head>", '<head><meta name="robots" content="index, nosnippet">'
        )
        assert "Snippets suppressed (also removes page from AI Overviews)" in titles(html)

    def test_nosnippet_via_header(self):
        found = titles(body("x"), headers={"X-Robots-Tag": "max-snippet:0"})
        assert "Snippets suppressed (also removes page from AI Overviews)" in found

    def test_body_robots_noindex_is_p0(self):
        html = body('x<meta name="robots" content="noindex">')
        _, _, found = run(html)
        assert found["noindex robots meta inside <body>"]["priority"] == "P0"

    def test_head_robots_not_body(self):
        html = body("x").replace(
            "<head>", '<head><meta name="robots" content="noindex">'
        )
        assert "noindex robots meta inside <body>" not in titles(html)

    def test_html_over_2mb(self):
        html = body("x" * (2 * 1024 * 1024 + 10))
        assert "HTML exceeds Googlebot's 2MB indexing limit" in titles(html)


class TestStructuredData:
    def _ld(self, obj):
        import json

        return body("x").replace(
            "</head>",
            f'<script type="application/ld+json">{json.dumps(obj)}</script></head>',
        )

    def test_faq_is_retired(self):
        a, _, found = run(self._ld({"@type": "FAQPage", "mainEntity": []}))
        assert a["retired_rich_results"] == ["FAQPage"]
        assert "7 May 2026" in found["Markup for retired rich results"]["description"]

    def test_search_action_retired(self):
        a, _, found = run(
            self._ld(
                {
                    "@type": "WebSite",
                    "name": "Acme",
                    "potentialAction": {"@type": "SearchAction"},
                }
            )
        )
        assert a["search_action"]
        assert "Markup for retired rich results" in found

    def test_graph_nesting_walked(self):
        a, _, _ = run(self._ld({"@graph": [{"@type": ["Thing", "HowTo"]}]}))
        assert a["retired_rich_results"] == ["HowTo"]

    def test_future_dates(self):
        found = titles(self._ld({"@type": "Article", "datePublished": "2027-01-01"}))
        assert "Structured data dates are in the future" in found

    def test_inverted_dates(self):
        found = titles(
            self._ld(
                {
                    "@type": "Article",
                    "datePublished": "2026-05-01",
                    "dateModified": "2026-01-01",
                }
            )
        )
        assert "dateModified is earlier than datePublished" in found

    def test_homepage_site_name(self):
        assert "No WebSite site-name markup on homepage" in titles(
            body("x"), url="https://acme.example/"
        )
        ok = self._ld({"@type": "WebSite", "name": "Acme", "url": "https://acme.example/"})
        assert "No WebSite site-name markup on homepage" not in titles(
            ok, url="https://acme.example/"
        )


class TestFavicon:
    def test_missing(self):
        html = "<html><head><title>x</title></head><body></body></html>"
        assert "No favicon declared" in titles(html)

    def test_svg_only(self):
        html = body("x").replace("/favicon.png", "/favicon.svg")
        assert "Favicon is SVG only" in titles(html)


# --------------------------------------------------------------------------- #
# crawler fingerprint + site-wide checks
# --------------------------------------------------------------------------- #
TEMPLATE = (
    "Looking for a trusted SEO agency in {place}? Our team helps {place} businesses "
    "grow with technical audits, content strategy, link building and local search. "
    "We have worked with hundreds of clients and deliver monthly reporting, clear "
    "pricing and no lock-in contracts. Book a free strategy call with our consultants "
    "today and find out how we can help your business win more customers online."
)


def test_simhash_template_pages_are_close():
    a = int(simhash64(TEMPLATE.format(place="Carlton")), 16)
    b = int(simhash64(TEMPLATE.format(place="Fitzroy")), 16)
    c = int(simhash64(" ".join(f"unrelated{i} words about gardening" for i in range(40))), 16)
    assert bin(a ^ b).count("1") <= 8
    assert bin(a ^ c).count("1") > 16


def test_simhash_needs_enough_words():
    assert simhash64("too short") is None


def test_parser_excludes_chrome_and_records_schema():
    p = PageParser("https://e.com/")
    p.feed(
        "<html><body><nav>Home About Contact</nav><main><p>Hello world</p></main>"
        '<footer>Copyright</footer><script type="application/ld+json">'
        '{"@type":"FAQPage"}</script></body></html>'
    )
    assert p.main_word_count == 2
    assert p.schema_types == {"FAQPage"}


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
        "title": f"Title for {url}",
        "meta_desc": "A perfectly reasonable description " + "x" * 100,
        "meta_desc_len": 135,
        "h1_count": 1,
        "content_hash": f"hash-{url}",
        "word_count": 500,
        "response_ms": 100,
        "in_sitemap": 0,
    }
    row.update(kw)
    con.execute(
        f"INSERT INTO pages ({','.join(row)}) VALUES ({','.join('?' * len(row))})",
        list(row.values()),
    )
    con.execute(
        "INSERT INTO links VALUES (?,?,?,?,?)", ("https://e.com/", url, "a", "", "internal")
    )


SUBURBS = [
    "Carlton", "Fitzroy", "Richmond", "Collingwood", "Brunswick", "Coburg",
    "Northcote", "Preston", "Thornbury", "Abbotsford", "Kew", "Hawthorn",
]


def _doorway_site(con):
    _page(con, "https://e.com/")
    for s in SUBURBS:
        _page(
            con,
            f"https://e.com/local/seo-agency-in-{s.lower()}/",
            simhash=simhash64(TEMPLATE.format(place=s)),
            main_word_count=70,
        )


def test_doorway_cluster_detected():
    con = _db()
    _doorway_site(con)
    clusters = near_duplicate_clusters(con)
    assert len(clusters) == 1 and clusters[0]["size"] == len(SUBURBS)
    assert clusters[0]["shape"] == "/local/seo-agency-in-{*}/"
    found = {f["key"]: f for f in run_checks(con)}
    assert found["doorway_templates"]["priority"] == "P1"
    assert "scaled_content_share" not in found  # needs >= 20 pages


def test_scaled_share_flagged_when_most_of_site_templated():
    con = _db()
    _page(con, "https://e.com/")
    for i in range(25):
        _page(
            con,
            f"https://e.com/{i}/seo/",
            simhash=simhash64(TEMPLATE.format(place=f"Town{i}")),
        )
    found = {f["key"] for f in run_checks(con)}
    assert "scaled_content_share" in found


def test_clusters_do_not_chain_through_intermediate_pages():
    # A~B and B~C are each within threshold, but A and C are far apart:
    # single-linkage would merge all three into one "template".
    con = _db()
    a = 0
    b = (1 << 7) - 1  # 7 bits from A
    c = b | (((1 << 7) - 1) << 7)  # 7 bits from B, 14 from A
    # different sections so the shape-merge can't legitimately rejoin them
    for i, h in enumerate([a] * 3 + [b] + [c] * 3):
        section = "alpha" if i < 4 else "beta"
        _page(con, f"https://e.com/{section}/p{i}/", simhash="%016x" % h)
    sizes = sorted(cl["size"] for cl in near_duplicate_clusters(con))
    assert sizes == [3, 4]  # never one cluster of 7


def test_old_crawl_db_without_simhash_is_tolerated():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE pages (url TEXT, indexable INTEGER)")
    assert near_duplicate_clusters(con) == []


def test_url_shape_suffix():
    assert (
        _url_shape(["https://e.com/melbourne/seo/", "https://e.com/sydney/seo/"])
        == "/{*}/seo/"
    )


def test_slash_duplicates_and_hygiene():
    con = _db()
    _page(con, "https://e.com/")
    _page(con, "https://e.com/a")
    _page(con, "https://e.com/a/")
    _page(con, "https://e.com/b", title=None, h1_count=0, meta_desc=None, meta_desc_len=0)
    _page(con, "https://e.com/c", title="SEO | SEO Agency | SEO Melbourne | Best SEO")
    keys = {f["key"] for f in run_checks(con)}
    assert {
        "slash_duplicates",
        "missing_title",
        "missing_h1",
        "missing_meta_desc",
        "title_stuffing",
    } <= keys


def test_reputation_sections_and_retired_schema():
    con = _db()
    _page(con, "https://e.com/")
    for i in range(3):
        _page(con, f"https://e.com/coupons/brand-{i}/", schema_types="FAQPage,Organization")
    found = {f["key"]: f for f in run_checks(con)}
    assert "/coupons/" in found["site_reputation_sections"]["description"]
    assert "FAQPage on 3 pages" in found["retired_rich_results"]["description"]
