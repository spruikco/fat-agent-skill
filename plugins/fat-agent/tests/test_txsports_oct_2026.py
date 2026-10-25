"""Regression tests from the second txsports.com.au audit (25 Oct 2026, 3.13.0).

Each test pins a false positive the audit hit on a real Next.js 16 shop, or a
check the audit needed and the plugin did not have.
"""

import json
import os
import sqlite3
import subprocess
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
FIX = HERE / "fixtures" / "txsports_oct_2026"
sys.path.insert(0, str(SCRIPTS))

from modules.accessibility import AccessibilityModule  # noqa: E402
from modules.cookie_gdpr import CookieGDPRModule  # noqa: E402
from modules.ecommerce import EcommerceModule  # noqa: E402
from modules.eeat import EEATModule  # noqa: E402
from modules.email_deliverability import (  # noqa: E402
    EmailDeliverabilityModule,
    organisational_domain,
)
from modules.pwa import PWAModule  # noqa: E402
from modules.sitemap import SitemapModule  # noqa: E402
from modules.technical_seo import TechnicalSEOModule  # noqa: E402
from sitecrawl import SCHEMA  # noqa: E402
from sitewide import run_checks  # noqa: E402

import merchant_feed  # noqa: E402

analyse_mod = import_module("analyse-html")


def _read(name):
    return (FIX / name).read_text(encoding="utf-8")


def _titles(mod):
    return {f["title"]: f for f in mod.findings}


# --------------------------------------------------------------------------- #
# 1. --help on the two pipeline scripts
# --------------------------------------------------------------------------- #
def test_help_flags_exit_zero():
    for script in ("analyse-html.py", "calculate-score.py"):
        for flag in ("--help", "-h"):
            r = subprocess.run(
                [sys.executable, str(SCRIPTS / script), flag],
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert r.returncode == 0, (script, flag, r.stderr)
            assert "Usage" in r.stdout


# --------------------------------------------------------------------------- #
# 2. implicit labels and honeypots
# --------------------------------------------------------------------------- #
def test_module_counts_wrapped_labels_and_skips_honeypot():
    a = AccessibilityModule().analyse(_read("club_store_inputs.html"))
    # search (for=), select (wrapped), 3 radios (wrapped), email (for=), and the
    # one genuinely unlabelled text input; the honeypot is not counted at all
    assert a["form_inputs_total"] == 7
    assert a["form_inputs_without_label"] == 1


def test_analyser_counts_wrapped_labels_and_skips_honeypot():
    report = analyse_mod.analyse_html(_read("club_store_inputs.html"))
    acc = report["accessibility"]
    assert acc["form_inputs_total"] == 7
    assert acc["form_inputs_without_label"] == 1


def test_analyser_id_without_matching_label_is_unlabelled():
    html = '<html lang="en"><body><input id="q" type="text"></body></html>'
    acc = analyse_mod.analyse_html(html)["accessibility"]
    assert acc["form_inputs_without_label"] == 1
    html = html.replace("<input", '<label for="q">Search</label><input')
    acc = analyse_mod.analyse_html(html)["accessibility"]
    assert acc["form_inputs_without_label"] == 0


# --------------------------------------------------------------------------- #
# 3. Organization entity: LocalBusiness subtypes count
# --------------------------------------------------------------------------- #
def test_eeat_accepts_sportsactivitylocation_as_organization():
    mod = EEATModule()
    a = mod.analyse(_read("product_page.html"), url="https://txsports.com.au/product/x")
    assert a["org"]["organization"] is True
    mod.score(a)
    assert "No Organization entity markup" not in _titles(mod)


def test_eeat_reads_graph_and_type_lists():
    html = (
        '<script type="application/ld+json">{"@context":"https://schema.org","@graph":['
        '{"@type":"WebSite","name":"x"},{"@type":["SportsTeam","Thing"],"name":"Club"}]}'
        "</script>"
    )
    mod = EEATModule()
    assert mod.analyse(html)["org"]["organization"] is True


def test_eeat_still_flags_pages_without_any_entity():
    html = '<script type="application/ld+json">{"@type":"WebPage","name":"x"}</script>'
    mod = EEATModule()
    a = mod.analyse(html)
    assert a["org"]["organization"] is False


# --------------------------------------------------------------------------- #
# 4. shipping info from Product JSON-LD
# --------------------------------------------------------------------------- #
def test_ecommerce_counts_offer_shipping_details():
    mod = EcommerceModule()
    a = mod.analyse(
        _read("product_page.html"),
        url="https://txsports.com.au/product/tx-football-track-jacket",
    )
    assert a["shipping_policy"] is True
    mod.score(a)
    assert "No shipping information on the product page" not in _titles(mod)


# --------------------------------------------------------------------------- #
# 5. service worker priority
# --------------------------------------------------------------------------- #
def test_service_worker_is_p3_without_manifest_and_p2_with_one():
    mod = PWAModule()
    mod.score(mod.analyse("<html><head></head></html>"))
    assert _titles(mod)["No service worker registration found"]["priority"] == "P3"
    mod = PWAModule()
    mod.score(
        mod.analyse('<html><head><link rel="manifest" href="/m.json"></head></html>')
    )
    assert _titles(mod)["No service worker registration found"]["priority"] == "P2"


# --------------------------------------------------------------------------- #
# 6. cookie / consent, region-aware
# --------------------------------------------------------------------------- #
_AU_PAGE = (
    '<html lang="en-AU"><head><script>window.dataLayer=[];function gtag(){dataLayer.push(arguments)}'
    "gtag('consent','default',{ad_storage:'denied',analytics_storage:'denied'});</script>"
    '<script async src="https://www.googletagmanager.com/gtm.js?id=GTM-X"></script></head>'
    '<body><a href="/privacy">Privacy</a></body></html>'
)


def test_consent_mode_counts_as_consent_gating():
    a = CookieGDPRModule().analyse(_AU_PAGE, url="https://txsports.com.au/")
    assert a["consent_mode"] is True
    assert a["has_consent_banner"] is True
    assert a["consent_before_tracking"] is True


def test_custom_banner_detected():
    html = '<div role="dialog" aria-label="Cookie consent" class="tx-consent-banner">Cookies</div>'
    assert "custom" in CookieGDPRModule().analyse(html)["detected_banners"]


def test_au_site_cookie_policy_is_p3():
    mod = CookieGDPRModule()
    a = mod.analyse(_AU_PAGE, url="https://txsports.com.au/")
    assert a["region"] == "au_nz"
    mod.score(a)
    f = _titles(mod)["No cookie policy link found"]
    assert f["priority"] == "P3"
    assert "Privacy Act" in f["description"]


def test_eu_targeting_keeps_gdpr_priorities():
    html = _AU_PAGE.replace(
        "<head>", '<head><link rel="alternate" hreflang="de" href="/de">'
    )
    mod = CookieGDPRModule()
    a = mod.analyse(html, url="https://example.com.au/")
    assert a["region"] == "default"
    mod.score(a)
    assert _titles(mod)["No cookie policy link found"]["priority"] == "P1"


# --------------------------------------------------------------------------- #
# 7. SPF / DMARC on the organisational domain
# --------------------------------------------------------------------------- #
def test_organisational_domain():
    assert organisational_domain("data.txsports.com.au") == "txsports.com.au"
    assert organisational_domain("www.example.co.nz") == "example.co.nz"
    assert organisational_domain("a.b.example.co.uk") == "example.co.uk"
    assert organisational_domain("www.example.com") == "example.com"
    assert organisational_domain("txsports.com.au") == "txsports.com.au"
    assert organisational_domain("127.0.0.1") == "127.0.0.1"


def test_subdomain_falls_back_to_org_domain(monkeypatch):
    mod = EmailDeliverabilityModule()
    asked = []

    def spf(domain):
        asked.append(("spf", domain))
        return {"found": domain == "txsports.com.au", "record": "v=spf1 -all"}

    def dmarc(domain):
        asked.append(("dmarc", domain))
        return {"found": domain == "txsports.com.au", "policy": "reject"}

    monkeypatch.setattr(mod, "_check_spf", spf)
    monkeypatch.setattr(mod, "_check_dkim", lambda d: {"found": False})
    monkeypatch.setattr(mod, "_check_dmarc", dmarc)
    a = mod.analyse(
        "<form><input type=email></form>", url="https://data.txsports.com.au/"
    )
    assert a["spf"]["found"] and a["dmarc"]["found"]
    assert a["spf_domain"] == "txsports.com.au"
    assert ("spf", "data.txsports.com.au") in asked
    mod.score(a)
    assert "Missing SPF record" not in _titles(mod)
    assert "Missing DMARC record" not in _titles(mod)


def test_missing_records_name_both_domains(monkeypatch):
    mod = EmailDeliverabilityModule()
    for name in ("_check_spf", "_check_dkim", "_check_dmarc"):
        monkeypatch.setattr(mod, name, lambda d: {"found": False})
    mod.score(mod.analyse("", url="https://data.example.com.au/"))
    desc = _titles(mod)["Missing SPF record"]["description"]
    assert "data.example.com.au" in desc and "example.com.au" in desc


# --------------------------------------------------------------------------- #
# 8 + 11. site-level indexation checks
# --------------------------------------------------------------------------- #
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
        "index_reason": "indexable",
        "title": f"Title {url}",
        "meta_desc": f"Desc {url} " + "x" * 110,
        "meta_desc_len": 130,
        "h1_count": 1,
        "content_hash": f"hash-{url}",
        "word_count": 500,
        "response_ms": 100,
        "in_sitemap": 0,
        "canonical": url,
    }
    row.update(kw)
    cols = ",".join(row)
    con.execute(
        f"INSERT INTO pages ({cols}) VALUES ({','.join('?' * len(row))})",
        list(row.values()),
    )


def _by_key(findings):
    return {f["key"]: f for f in findings if "key" in f}


def test_noindex_pages_in_sitemap():
    con = _db()
    _page(con, "https://t.au/")
    for i in range(3):
        _page(
            con,
            f"https://t.au/league/club/vic-afl:club-{i}",
            in_sitemap=1,
            indexable=0,
            index_reason="noindex",
        )
    f = _by_key(run_checks(con))["sitemap_noindex"]
    assert f["priority"] == "P1" and f["count"] == 3
    assert "/league/club/{*} (3)" in f["description"]


def test_error_state_pages_served_as_200():
    con = _db()
    _page(con, "https://t.au/")
    for i in range(12):
        _page(
            con,
            f"https://t.au/league/phq:{i:04d}",
            in_sitemap=1,
            title=f"Over 60s Division {i} results, table and fixtures | TX Sports",
            main_excerpt="We couldn't load this league It may have moved, or the results "
            "service is busy. Try again in a minute. League centre",
        )
    _page(con, "https://t.au/about", main_excerpt="We make kits. Not found in stores.")
    f = _by_key(run_checks(con))["soft_error_pages"]
    assert f["priority"] == "P0" and f["count"] == 12


def test_error_state_below_threshold_is_p1():
    con = _db()
    _page(
        con,
        "https://t.au/x",
        main_excerpt="Something went wrong. Please try again later.",
    )
    assert _by_key(run_checks(con))["soft_error_pages"]["priority"] == "P1"


def test_canonical_to_home_page():
    con = _db()
    _page(con, "https://t.au/", canonical="https://t.au")
    for p in ("a", "b", "c"):
        _page(
            con,
            f"https://t.au/{p}",
            canonical="https://t.au",
            indexable=0,
            index_reason="canonicalised elsewhere",
        )
    for p in ("cart", "checkout", "404"):
        _page(
            con,
            f"https://t.au/{p}",
            canonical="https://t.au/",
            indexable=0,
            index_reason="noindex",
        )
    keys = _by_key(run_checks(con))
    assert keys["canonical_to_home"]["priority"] == "P1"
    assert keys["canonical_to_home"]["count"] == 3
    assert keys["noindex_canonical_to_home"]["priority"] == "P2"


def test_junior_player_pages_flagged_only_when_indexable():
    con = _db()
    _page(con, "https://t.au/league/player/1", title="Sam Smith, Under 12 Girls: goals")
    _page(
        con,
        "https://t.au/league/player/2",
        title="Player | TX Sports",
        indexable=0,
        index_reason="noindex",
    )
    _page(
        con, "https://t.au/league/club/x", title="Titans Junior Basketball Club results"
    )
    f = _by_key(run_checks(con))["junior_player_pages"]
    assert f["count"] == 1 and "player/1" in f["description"]


# --------------------------------------------------------------------------- #
# 9. Merchant feed
# --------------------------------------------------------------------------- #
def test_feed_validation_findings():
    items = merchant_feed.parse_feed((FIX / "merchant_feed.xml").read_bytes())
    assert len(items) == 6
    assert items[0]["shipping"][0]["price"] == "12.00 AUD"
    findings, stats = merchant_feed.validate_items(items, "https://txsports.com.au")
    titles = {f["title"]: f for f in findings}
    assert "price (1" in titles["Feed items missing required attributes"]["description"]
    assert "Invalid availability values in feed" in titles
    assert "Malformed prices in feed" in titles
    assert stats["duplicate_ids"] == 1
    assert (
        "tradexco.com.au" in titles["Feed links point at another host"]["description"]
    )
    assert (
        "80977"
        in titles["Variant groups with duplicate or missing variant attributes"][
            "description"
        ]
    )
    assert "Apparel items missing apparel attributes" in titles
    # 9001 and 9002 (first) send neither gtin/mpn nor identifier_exists=no
    assert titles["Feed items without unique product identifiers"]["count"] == 2


def test_landing_page_shipping_mismatch():
    item = merchant_feed.parse_feed((FIX / "merchant_feed.xml").read_bytes())[0]
    item["price"] = "70.00 AUD"
    facts = merchant_feed.page_offer_facts(_read("product_page.html"))
    assert facts["product"] is True and facts["prices"] == [70.0]
    result = merchant_feed.compare_item(item, facts)
    assert result["price_mismatch"] is None
    assert (
        "12.0" in result["shipping_mismatch"] and "9.0" in result["shipping_mismatch"]
    )
    rows = [
        {
            "url": "https://t.au/p",
            "status": 200,
            "noindex": False,
            "product_schema": True,
            **result,
        }
    ]
    titles = {f["title"] for f in merchant_feed.landing_findings(rows)}
    assert "Landing page shipping rate does not match the feed" in titles


def test_landing_page_price_mismatch_and_broken():
    facts = {"product": True, "prices": [45.0], "ranges": [], "shipping": []}
    r = merchant_feed.compare_item({"price": "40.00 AUD"}, facts)
    assert r["price_mismatch"]
    assert (
        merchant_feed.compare_item(
            {"price": "50.00 AUD", "sale_price": "45.00 AUD"}, facts
        )["price_mismatch"]
        is None
    )
    rows = [
        {"url": "https://t.au/a", "status": 404, "noindex": False},
        {"url": "https://t.au/b", "status": 200, "noindex": True},
    ]
    f = {x["title"]: x for x in merchant_feed.landing_findings(rows)}
    assert f["Feed landing pages broken or not indexable"]["count"] == 2


def test_feed_parse_error_is_a_finding():
    out = merchant_feed.run(b"<rss><channel><item><g:id>1</item>", sample=0)
    assert out["findings"][0]["title"] == "Merchant feed could not be fetched or parsed"


def test_feed_findings_merge_into_punchlist():
    from punchlist import update_punchlist

    out = merchant_feed.run(
        (FIX / "merchant_feed.xml").read_bytes(),
        site="https://txsports.com.au",
        sample=0,
    )
    out = json.loads(json.dumps(out))  # what punchlist.py reads back from disk
    punch = {"version": 1, "url": "", "updated": "", "items": []}
    stats = update_punchlist(punch, out, now="T1")
    assert stats["new"] >= 5
    assert {i["module"] for i in punch["items"]} == {"merchant_feed"}


def test_pick_sample_distinct_links():
    items = [{"link": f"https://t.au/{i % 3}"} for i in range(9)]
    assert len(merchant_feed.pick_sample(items, 20)) == 3
    assert merchant_feed.pick_sample(items, 0) == []


# --------------------------------------------------------------------------- #
# 10. Next.js error shell + duplicate robots tags
# --------------------------------------------------------------------------- #
def test_next_error_shell_on_404_is_p3():
    mod = TechnicalSEOModule()
    a = mod.analyse(_read("next_error_404.html"), url="https://txsports.com.au/missing")
    assert a["next_error_shell"] == "not_found"
    mod.score(a)
    t = _titles(mod)
    assert t["Next.js error shell served (__next_error__)"]["priority"] == "P3"
    assert t["Multiple robots meta tags with different values"]["priority"] == "P3"


def test_next_error_shell_on_real_page_is_p1():
    html = '<html id="__next_error__"><head><title>Shop | X</title></head><body></body></html>'
    mod = TechnicalSEOModule()
    mod.score(mod.analyse(html, url="https://x.com/shop"))
    assert (
        _titles(mod)["Next.js error shell served (__next_error__)"]["priority"] == "P1"
    )


def test_single_robots_tag_not_flagged():
    html = '<html lang="en"><head><meta name="robots" content="index, follow"></head></html>'
    mod = TechnicalSEOModule()
    mod.score(mod.analyse(html, url="https://x.com/"))
    assert "Multiple robots meta tags with different values" not in _titles(mod)


# --------------------------------------------------------------------------- #
# 12. every declared sitemap is read
# --------------------------------------------------------------------------- #
_URLSET = (
    '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "{}</urlset>"
)
_INDEX = (
    '<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<sitemap><loc>https://t.au/sitemap-products.xml</loc></sitemap>"
    "<sitemap><loc>https://t.au/sitemap-broken.xml</loc></sitemap></sitemapindex>"
)


def _fake_fetch(pages):
    return staticmethod(lambda url, timeout=10: pages.get(url))


def test_robots_sitemaps_beyond_the_first_are_checked(monkeypatch):
    pages = {
        "https://t.au/sitemap.xml": _URLSET.format(
            "<url><loc>https://t.au/</loc></url>"
        ),
        "https://t.au/robots.txt": "User-agent: *\nSitemap: https://t.au/sitemap.xml\n"
        "Sitemap: https://t.au/league/sitemap.xml\n",
        "https://t.au/league/sitemap.xml": _URLSET.format(
            "".join(f"<url><loc>https://t.au/league/{i}</loc></url>" for i in range(4))
        ),
    }
    monkeypatch.setattr(SitemapModule, "_fetch", _fake_fetch(pages))
    mod = SitemapModule()
    a = mod.analyse("", url="https://t.au/")
    assert [s["url"] for s in a["other_sitemaps"]] == [
        "https://t.au/league/sitemap.xml"
    ]
    assert a["page_url_total"] == 5


def test_sitemap_index_children_checked_and_broken_flagged(monkeypatch):
    pages = {
        "https://t.au/sitemap.xml": _INDEX,
        "https://t.au/robots.txt": "Sitemap: https://t.au/sitemap.xml\nSitemap: https://t.au/empty.xml\n",
        "https://t.au/sitemap-products.xml": _URLSET.format(
            "<url><loc>https://t.au/p/1</loc></url><url><loc>https://t.au/p/2</loc></url>"
        ),
        "https://t.au/empty.xml": _URLSET.format(""),
    }
    monkeypatch.setattr(SitemapModule, "_fetch", _fake_fetch(pages))
    mod = SitemapModule()
    a = mod.analyse("", url="https://t.au/")
    assert a["is_index"] and a["page_url_total"] == 2
    mod.score(a)
    t = _titles(mod)
    assert (
        "sitemap-broken.xml"
        in t["Declared sitemap unreachable or invalid"]["description"]
    )
    assert "empty.xml" in t["Declared sitemap lists no URLs"]["description"]


def test_sitemap_xml_argument_never_fetches(monkeypatch):
    def boom(url, timeout=10):
        raise AssertionError("network fetch in replay mode: " + url)

    monkeypatch.setattr(SitemapModule, "_fetch", staticmethod(boom))
    a = SitemapModule().analyse(
        "",
        url="https://t.au/",
        sitemap_xml=_INDEX,
        robots_txt="Sitemap: https://t.au/sitemap.xml\nSitemap: https://t.au/other.xml\n",
    )
    assert a["other_sitemaps"] == []


def test_fixture_dir_exists():
    assert os.path.isdir(FIX)


# --------------------------------------------------------------------------- #
# 14. no "Missing canonical" on noindex pages
# --------------------------------------------------------------------------- #
_NO_CANON = (
    '<html lang="en-AU"><head><title>Your cart | TX Sports</title>{robots}</head>'
    "<body><main><h1>Your cart</h1></main></body></html>"
)


def _high(report):
    return report["summary"]["high"]


def test_core_seo_skips_canonical_on_noindex_meta():
    html = _NO_CANON.format(robots='<meta name="robots" content="noindex, nofollow"/>')
    report = analyse_mod.analyse_html(html)
    assert report["seo"]["noindex"] is True
    assert "Missing canonical URL" not in _high(report)
    calc = import_module("calculate-score")
    noindex_tech = calc.calculate_seo_score(report["seo"], report["performance"])[
        "details"
    ]["technical"]["score"]
    indexable = analyse_mod.analyse_html(_NO_CANON.format(robots=""))
    assert "Missing canonical URL" in _high(indexable)
    index_tech = calc.calculate_seo_score(indexable["seo"], indexable["performance"])[
        "details"
    ]["technical"]["score"]
    assert noindex_tech == index_tech + 5 - 3  # +5 canonical, -3 for noindex robots


def test_core_seo_skips_canonical_on_x_robots_tag():
    report = analyse_mod.analyse_html(
        _NO_CANON.format(robots=""),
        response_headers={"x-robots-tag": "noindex", "strict-transport-security": "x"},
    )
    assert report["seo"]["noindex"] is True
    assert "Missing canonical URL" not in _high(report)


def test_core_seo_reads_every_robots_tag():
    # Next.js 404s carry two robots tags; noindex in either one counts
    html = _NO_CANON.format(
        robots='<meta name="robots" content="noindex"/><meta name="robots" content="follow"/>'
    )
    assert analyse_mod.analyse_html(html)["seo"]["noindex"] is True


def test_seo_module_skips_canonical_on_noindex():
    from modules.seo import SEOModule

    mod = SEOModule()
    a = mod.analyse(_NO_CANON.format(robots=""), headers={"X-Robots-Tag": "noindex"})
    assert a["noindex"] is True
    result = mod.score(a)
    assert "Missing canonical URL" not in _titles(mod)
    assert result["details"]["canonical"]["score"] == 5
    mod = SEOModule()
    mod.score(mod.analyse(_NO_CANON.format(robots="")))
    assert "Missing canonical URL" in _titles(mod)


# --------------------------------------------------------------------------- #
# 15. failed or error-page fetches don't report every header missing
# --------------------------------------------------------------------------- #
def test_headers_not_assessed_reason():
    reason = analyse_mod.headers_not_assessed_reason
    assert "request failed" in reason(
        {"headers": {}, "error": "GET failed: timed out", "headers_status": None}
    )
    assert "HTTP 503" in reason(
        {"headers": {"server": "cloudflare"}, "headers_status": 503, "error": None}
    )
    # a real 404 that carries the site's headers is still assessed
    assert (
        reason(
            {
                "headers": {"strict-transport-security": "max-age=1"},
                "headers_status": 404,
                "error": None,
            }
        )
        is None
    )
    assert reason({"headers": {"server": "x"}, "headers_status": 200}) is None
    assert reason({"headers": {}, "error": None}) is None


def test_fetch_page_records_header_status():
    import io
    import urllib.error

    def opener(req, timeout=10):
        if req.get_method() == "HEAD":
            raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, io.BytesIO())
        raise TimeoutError("timed out")

    got = analyse_mod.fetch_page("https://t.au/x", opener=opener)
    assert got["headers"] == {} and "timed out" in got["error"]
    assert "request failed" in analyse_mod.headers_not_assessed_reason(got)


def test_unassessed_headers_are_not_reported_missing():
    report = analyse_mod.analyse_html(
        _NO_CANON.format(robots=""),
        response_headers={},
        fetch_info={"headers_not_assessed": "the request failed (timed out)"},
    )
    assert not [i for i in _high(report) if i.startswith("Missing security header")]
    assert any("Security headers not assessed" in i for i in report["summary"]["low"])
    calc = import_module("calculate-score")
    sec = calc.calculate_scores(report)["security"]
    assert sec.get("assessed") is False
