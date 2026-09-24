"""Regression tests for false positives and gaps found auditing vend16.com (v3.9.0).

A server-rendered Node marketing site behind Caddy exposed a batch of analyser
false positives (tables, SVG titles, @graph JSON-LD, HEAD-only fetching,
preconnect, font-display, first-party analytics, noopener, decorative SVGs)
plus tooling gaps (lighthouse via npx, PageSpeed error messages, schema logo
and subscription pricing).
"""

import http.server
import subprocess
import sys
import threading
from importlib import import_module
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

analyse_mod = import_module("analyse-html")
analyse_html = analyse_mod.analyse_html
calc = import_module("calculate-score")
import lighthouse  # noqa: E402
import pagespeed  # noqa: E402
import suggest_schema as ss  # noqa: E402
from modules.links import LinksModule  # noqa: E402
from modules.performance import PerformanceModule  # noqa: E402
from modules.security import SecurityModule  # noqa: E402

HEAD = (
    '<html lang="en"><head><meta charset="utf-8"><title>{title}</title>{extra}</head>'
)


def page(body="", extra="", title="Vend16: in-app purchases, sorted for apps"):
    return HEAD.format(title=title, extra=extra) + f"<body>{body}</body></html>"


def all_issues(report):
    s = report["summary"]
    return s["critical"] + s["high"] + s["medium"] + s["low"]


# 1. per-table <th> tracking
def test_multiple_tables_all_with_th_not_flagged():
    body = (
        '<table><tr><th scope="row">Plan</th><td>1</td></tr></table>'
        "<table><thead><tr><th>Price</th></tr></thead></table>"
        '<table><tr><th class="x">Tier</th></tr></table>'
    )
    r = analyse_html(page(body))
    assert r["accessibility"]["tables_total"] == 3
    assert r["accessibility"]["tables_without_th"] == 0
    assert not any("header cells" in i for i in all_issues(r))


def test_only_headerless_tables_counted():
    body = (
        "<table><tr><th>A</th></tr></table>"
        "<table><tr><td>no header</td></tr></table>"
        "<table><tr><td>outer<table><tr><th>inner</th></tr></table></td></tr></table>"
    )
    r = analyse_html(page(body))
    assert r["accessibility"]["tables_without_th"] == 2


# 2. <title> inside inline <svg>
def test_svg_title_is_not_document_title():
    body = "<svg role='img'><title>Logo mark</title><path d='M0 0'/></svg>" * 2
    r = analyse_html(page(body))
    assert r["seo"]["title_tag"] == "Vend16: in-app purchases, sorted for apps"
    assert r["seo"]["duplicate_title_tags"] == 1
    assert r["accessibility"]["svg_without_accessible_name"] == 0
    assert not any("Duplicate <title>" in i for i in all_issues(r))


# 3. JSON-LD @graph
GRAPH = (
    '<script type="application/ld+json">{"@context":"https://schema.org","@graph":['
    '{"@type":"Organization","name":"Vend16","logo":"https://vend16.com/poster.png"},'
    '{"@type":["SoftwareApplication","WebApplication"],"name":"Vend16"}]}</script>\n'
)


def test_jsonld_graph_types_are_walked():
    r = analyse_html(page(extra=GRAPH))
    assert r["seo"]["json_ld_types"] == [
        "Organization",
        "SoftwareApplication",
        "WebApplication",
    ]


def test_jsonld_top_level_array_walked():
    extra = (
        '<script type="application/ld+json">[{"@type":"WebSite"},'
        '{"@type":"Organization"}]</script>'
    )
    r = analyse_html(page(extra=extra))
    assert r["seo"]["json_ld_types"] == ["WebSite", "Organization"]


def test_suggest_schema_sees_organization_in_graph():
    html = page(extra=GRAPH)
    assert "organization" in ss.present_types(html)
    org = ss.recommend(html, "https://vend16.com")["recommendations"][0]
    assert org["status"] == "incomplete"


# 4 + 5. --fetch: HEAD fallback to GET, and fetching the body when no file given
class _Handler(http.server.BaseHTTPRequestHandler):
    BODY = page("<h1>Hello</h1><p>" + "word " * 50 + "</p>").encode()

    def do_HEAD(self):
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Strict-Transport-Security", "max-age=31536000")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(self.BODY)

    def log_message(self, *a):
        pass


@pytest.fixture
def head404_server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


def test_fetch_page_falls_back_to_get(head404_server):
    res = analyse_mod.fetch_page(head404_server)
    assert res["head_status"] == 404
    assert res["get_status"] == 200
    assert "strict-transport-security" in res["headers"]


def test_head_error_get_ok_is_a_finding(head404_server):
    res = analyse_mod.fetch_page(head404_server)
    r = analyse_html(
        page("<h1>x</h1>"),
        page_url=head404_server,
        response_headers=res["headers"],
        fetch_info={"head_status": 404, "get_status": 200},
    )
    assert r["security"]["response_headers_available"] is True
    assert r["security"]["has_hsts"] is True
    assert any("HEAD request returns 404" in i for i in r["summary"]["medium"])


def test_cli_fetch_without_file_analyses_fetched_body(head404_server):
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "analyse-html.py"),
            "--fetch",
            "--url",
            head404_server,
        ],
        input="",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    import json

    r = json.loads(out.stdout)
    assert r["seo"]["title_tag"] == "Vend16: in-app purchases, sorted for apps"
    assert r["seo"]["h1_count"] == 1
    assert r["fetch"]["head_status"] == 404


def test_cli_empty_input_errors_clearly():
    out = subprocess.run(
        [sys.executable, str(SCRIPTS / "analyse-html.py")],
        input="",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 2
    assert "no HTML to analyse" in out.stderr


# 6. preconnect only when there are third-party render-critical origins
def test_no_preconnect_needed_when_all_first_party():
    extra = (
        '<link rel="stylesheet" href="/css/site.css"><script src="/app.js"></script>'
    )
    r = analyse_html(page(extra=extra), page_url="https://vend16.com/")
    assert r["performance"]["preconnect_needed"] is False
    assert not any("preconnect" in i for i in all_issues(r))


def test_preconnect_flagged_for_third_party_stylesheet():
    extra = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=X">'
    r = analyse_html(page(extra=extra), page_url="https://vend16.com/")
    assert "https://fonts.gstatic.com" in r["performance"]["third_party_render_origins"]
    assert any("preconnect" in i for i in r["summary"]["low"])


def test_async_third_party_script_does_not_need_preconnect():
    extra = '<script async src="https://www.googletagmanager.com/gtag/js"></script>'
    r = analyse_html(page(extra=extra), page_url="https://vend16.com/")
    assert r["performance"]["preconnect_needed"] is False


def test_score_credits_preconnect_when_not_needed():
    base = {"has_preconnect": False, "preconnect_needed": False}
    needed = {"has_preconnect": False, "preconnect_needed": True}
    s1 = calc.calculate_performance_score(base)
    s2 = calc.calculate_performance_score(needed)
    assert s1["details"]["resource_hints"]["score"] > (
        s2["details"]["resource_hints"]["score"]
    )


def test_performance_module_hint_finding_only_with_third_party():
    mod = PerformanceModule()
    a = mod.analyse(
        page(extra='<link rel="stylesheet" href="/s.css">'), url="https://v.com/"
    )
    assert a["preconnect_needed"] is False
    mod.score(a)
    assert not any("resource hints" in f["title"] for f in mod.findings)

    mod2 = PerformanceModule()
    a2 = mod2.analyse(
        page(extra='<link rel="stylesheet" href="https://cdn.example.net/s.css">'),
        url="https://v.com/",
    )
    mod2.score(a2)
    assert any("resource hints" in f["title"] for f in mod2.findings)


# 7. font-display via Google Fonts URL or inline @font-face
def test_google_fonts_display_swap_satisfies_font_display():
    extra = (
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2?family=Caveat&amp;display=swap">'
    )
    r = analyse_html(page(extra=extra))
    assert r["performance"]["has_font_display_swap"] is True


def test_inline_font_face_font_display():
    extra = "<style>@font-face{font-family:X;src:url(/x.woff2);font-display: optional}</style>"
    r = analyse_html(page(extra=extra))
    assert r["performance"]["has_font_display_swap"] is True


# 8. privacy-first / self-hosted analytics
@pytest.mark.parametrize(
    "tag,provider",
    [
        ('<script defer data-website-id="abc" src="/u/v.js"></script>', "Umami"),
        (
            '<script defer data-domain="x.com" src="https://plausible.io/js/script.js"></script>',
            "Plausible",
        ),
        (
            '<script src="https://cdn.usefathom.com/script.js" data-site="ABC"></script>',
            "Fathom Analytics",
        ),
        (
            '<script async src="https://scripts.simpleanalyticscdn.com/latest.js"></script>',
            "Simple Analytics",
        ),
        (
            "<script>var _paq = window._paq || [];_paq.push(['trackPageView']);</script>",
            "Matomo",
        ),
        ("<script>posthog.init('phc_x')</script>", "PostHog"),
        (
            "<script defer src='https://static.cloudflareinsights.com/beacon.min.js' "
            "data-cf-beacon='{}'></script>",
            "Cloudflare Web Analytics",
        ),
    ],
)
def test_analytics_providers_detected(tag, provider):
    r = analyse_html(page(extra=tag))
    assert r["analytics"]["has_analytics"] is True
    assert provider in r["analytics"]["providers"]
    assert "No analytics tracking detected" not in all_issues(r)


# 9. noopener only matters for target=_blank
def test_links_module_ignores_external_links_without_target_blank():
    html = page('<a href="https://github.com/x">gh</a><a href="https://x.com/y">x</a>')
    a = LinksModule().analyse(html, url="https://vend16.com")
    assert a["external_count"] == 2
    assert a["external_missing_noopener"] == 0


def test_noreferrer_counts_as_noopener():
    html = page(
        '<a href="https://a.com" target="_blank" rel="noreferrer">a</a>'
        '<a href="https://b.com" target="_blank">b</a>'
    )
    r = analyse_html(html, page_url="https://vend16.com")
    assert r["security"]["external_links_without_noopener"] == 1
    assert (
        LinksModule().analyse(html, url="https://vend16.com")[
            "external_missing_noopener"
        ]
        == 1
    )
    assert SecurityModule().analyse(html)["external_links_without_noopener"] == 1


# 10. decorative SVGs
def test_svg_inside_aria_hidden_parent_is_decorative():
    body = (
        '<div aria-hidden="true"><span><svg><path d="M0 0"/></svg></span></div>'
        '<svg role="presentation"><path d="M0 0"/></svg>'
        '<svg><svg><path d="M0 0"/></svg><title>Named</title></svg>'
    )
    r = analyse_html(page(body))
    assert r["accessibility"]["svg_total"] == 3
    assert r["accessibility"]["svg_without_accessible_name"] == 0


def test_unnamed_visible_svg_still_flagged():
    r = analyse_html(page('<svg><path d="M0 0"/></svg>'))
    assert r["accessibility"]["svg_without_accessible_name"] == 1


# 11. lighthouse via npx, pagespeed errors
def _which(found):
    return lambda name: found.get(name)


def test_lighthouse_falls_back_to_npx():
    with patch("shutil.which", side_effect=_which({"npx": "/usr/bin/npx"})):
        assert lighthouse.lighthouse_command() == ["/usr/bin/npx", "-y", "lighthouse"]
        with (
            patch("subprocess.run") as run,
            patch(
                "lighthouse.parse_lighthouse_results", return_value={"available": True}
            ),
        ):
            res = lighthouse.run_lighthouse("https://vend16.com", "out.json")
        cmd = run.call_args[0][0]
        assert cmd[:3] == ["/usr/bin/npx", "-y", "lighthouse"]
        assert "https://vend16.com" in cmd
        assert res["available"] is True


def test_lighthouse_missing_everything_explains_fix():
    with patch("shutil.which", return_value=None):
        res = lighthouse.run_lighthouse("https://vend16.com", "out.json")
    assert res["available"] is False
    assert "npx" in res["error"]


def test_pagespeed_404_html_body_gives_actionable_message():
    err = pagespeed.urllib.error.HTTPError(
        url="x", code=404, msg="Not Found", hdrs={}, fp=None
    )
    err.read = MagicMock(
        return_value=b"<!DOCTYPE html><html>Error 404 (Not Found)</html>"
    )
    with patch("pagespeed.urllib.request.urlopen", side_effect=err):
        res = pagespeed.fetch_pagespeed("https://vend16.com")
    assert "404" in res["error"]
    assert "<html" not in res["error"].lower()
    assert "--api-key" in res["error"]


def test_pagespeed_rejects_url_without_scheme():
    res = pagespeed.fetch_pagespeed("vend16.com")
    assert "https://" in res["error"]


# 13 + 14. schema: square logo, subscription billing period, no fake ratings
def test_org_logo_never_uses_og_image():
    html = page(
        extra='<meta property="og:image" content="https://vend16.com/poster.png">'
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
    )
    org = ss.gen_organization(ss.gather_signals(html, "https://vend16.com"))
    assert org["logo"] == "https://vend16.com/apple-touch-icon.png"
    assert org["image"] == "https://vend16.com/poster.png"


def test_existing_wide_logo_flagged():
    rec = ss.recommend(page(extra=GRAPH), "https://vend16.com")["recommendations"][0]
    assert "square logo" in rec["reason"]


def test_subscription_offer_gets_billing_duration_and_no_fake_rating():
    html = page(
        '<h1>Pro plan</h1><p class="price">$29 / month</p>'
        "<button>Add to cart</button>",
        extra='<meta property="product:price:amount" content="29">',
    )
    sig = ss.gather_signals(html, "https://vend16.com/pricing")
    assert sig["billing_duration"] == "P1M"
    product = ss.gen_product(sig)
    spec = product["offers"]["priceSpecification"]
    assert spec["@type"] == "UnitPriceSpecification"
    assert spec["billingDuration"] == "P1M"
    assert "aggregateRating" not in product


# 16. sitemap lists HTML only; llms.txt links distinct
def test_sitemap_flags_non_html_entries():
    from modules.sitemap import SitemapModule

    xml = (
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://vend16.com/</loc></url>"
        "<url><loc>https://vend16.com/llms.txt</loc></url></urlset>"
    )
    mod = SitemapModule()
    a = mod.analyse("", "https://vend16.com/", sitemap_xml=xml, robots_txt="")
    assert a["non_html_urls"] == ["https://vend16.com/llms.txt"]
    mod.score(a)
    assert any("non-HTML" in f["title"] for f in mod.findings)


def test_llms_txt_repeated_links_flagged():
    from modules.ai_search import AISearchModule

    llms = (
        "# Vend16\n\n> In-app purchases, sorted.\n\n## Docs\n"
        "- [Overview](https://vend16.com/llms.txt)\n"
        "- [Pricing](https://vend16.com/llms.txt)\n"
        "- [Docs](https://vend16.com/llms.txt)\n"
    )
    mod = AISearchModule()
    a = mod.analyse(
        page("<h1>Vend16</h1>"),
        "https://vend16.com/",
        robots_txt="User-agent: *\nAllow: /",
        llms_txt=llms,
        wikidata_hit=True,
    )
    assert a["llms_validation"]["unique_link_count"] == 1
    mod.score(a)
    assert any("repeat the same" in f["title"] for f in mod.findings)


# 17. account pages: noindex with no canonical to the homepage
def test_noindex_login_with_homepage_canonical_is_conflict():
    from modules.technical_seo import TechnicalSEOModule

    html = page(
        extra='<meta name="robots" content="noindex"><link rel="canonical" href="https://vend16.com/">'
    )
    mod = TechnicalSEOModule()
    a = mod.analyse(html, url="https://vend16.com/login")
    assert a["noindex_canonical_conflict"]
    mod.score(a)
    assert any("canonicalises to another URL" in f["title"] for f in mod.findings)


def test_noindex_without_canonical_is_fine():
    from modules.technical_seo import TechnicalSEOModule

    html = page(extra='<meta name="robots" content="noindex">')
    assert (
        TechnicalSEOModule().analyse(html, url="https://vend16.com/login")[
            "noindex_canonical_conflict"
        ]
        is None
    )
