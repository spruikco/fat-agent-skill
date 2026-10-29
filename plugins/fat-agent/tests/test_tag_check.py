"""Tests for the marketing-tag layer (3.13.0).

tag_check.py: request classification, dedupe of retried beacons, findings,
the WebSocket frame parser, plus one end-to-end run in a real headless
browser against a local page (skipped when no Chrome/Edge is installed).
analyse-html.py: static tag-ID extraction, duplicate installs, dead UA, and
"no analytics" raised from P3 to P1.
"""

import http.server
import struct
import sys
import threading
from importlib import import_module
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import tag_check as tc  # noqa: E402

analyse_html = import_module("analyse-html").analyse_html


def hits(url, method="GET", body=""):
    return [r for r in tc.classify(url, method, body) if r["kind"] == "hit"]


# ------------------------------------------------------------ classify


class TestClassify:
    def test_ga4_url_event(self):
        r = hits("https://www.google-analytics.com/g/collect?v=2&tid=G-ABC123&_p=1&_s=1&en=page_view&gcs=G111")
        assert [(x["vendor"], x["id"], x["event"], x["consent"]) for x in r] == [
            ("GA4", "G-ABC123", "page_view", "G111")
        ]

    def test_ga4_batched_body(self):
        body = "en=page_view&_et=1\r\nen=scroll&epn.percent_scrolled=90"
        r = hits("https://region1.google-analytics.com/g/collect?v=2&tid=G-ABC123&_p=9", "POST", body)
        assert [x["event"] for x in r] == ["page_view", "scroll"]

    def test_ga4_server_side_custom_domain(self):
        r = hits("https://sgtm.example.com.au/g/collect?v=2&tid=G-ZZZ999&en=page_view")
        assert r and r[0]["vendor"] == "GA4"

    def test_library_loads(self):
        recs = tc.classify("https://www.googletagmanager.com/gtm.js?id=GTM-AB12CD")
        assert recs[0]["vendor"] == "Google Tag Manager" and recs[0]["kind"] == "load"
        recs = tc.classify("https://www.googletagmanager.com/gtag/js?id=AW-12345")
        assert recs[0]["vendor"] == "Google Ads"

    def test_universal_analytics(self):
        r = hits("https://www.google-analytics.com/collect?v=1&tid=UA-123-1&t=pageview")
        assert r[0]["vendor"] == "Universal Analytics" and r[0]["id"] == "UA-123-1"

    def test_ads_conversion_vs_remarketing(self):
        conv = hits("https://www.googleadservices.com/pagead/conversion/853677730/?label=abcXYZ")
        rem = hits("https://googleads.g.doubleclick.net/pagead/viewthroughconversion/856156928/?random=1")
        assert conv[0]["event"] == "conversion:abcXYZ" and conv[0]["id"] == "AW-853677730"
        assert rem[0]["event"] == "remarketing"
        assert tc.is_conversion(conv[0]) and not tc.is_conversion(rem[0])

    def test_meta_get_and_multipart_post(self):
        g = hits("https://www.facebook.com/tr/?id=1234567890&ev=PageView")
        assert (g[0]["id"], g[0]["event"]) == ("1234567890", "PageView")
        body = '--x\r\nContent-Disposition: form-data; name="id"\r\n\r\n555666777\r\n--x\r\nContent-Disposition: form-data; name="ev"\r\n\r\nLead\r\n--x--'
        p = hits("https://www.facebook.com/tr/", "POST", body)
        assert (p[0]["id"], p[0]["event"]) == ("555666777", "Lead")
        assert tc.is_conversion(p[0]) and not tc.is_conversion(g[0])

    def test_linkedin_tiktok_uet_pinterest(self):
        li = hits("https://px.ads.linkedin.com/collect?pid=2218508&conversionId=99")
        assert li[0]["event"] == "conversion:99" and tc.is_conversion(li[0])
        tt = hits(
            "https://analytics.tiktok.com/api/v2/pixel",
            "POST",
            '{"event":"CompletePayment","context":{"pixel":{"code":"BRAQ1"}}}',
        )
        assert (tt[0]["id"], tt[0]["event"]) == ("BRAQ1", "CompletePayment") and tc.is_conversion(tt[0])
        uet = hits("https://bat.bing.com/action/0?ti=4068886&evt=custom&ea=submit_lead_form")
        assert uet[0]["event"] == "custom:submit_lead_form" and tc.is_conversion(uet[0])
        pin = hits("https://ct.pinterest.com/v3/?tid=2613&event=checkout")
        assert tc.is_conversion(pin[0])

    def test_session_tools_and_noise(self):
        assert tc.classify("https://www.clarity.ms/tag/t3nut6g5g3")[0]["id"] == "t3nut6g5g3"
        assert tc.classify("https://static.hotjar.com/c/hotjar-81093.js?sv=6")[0]["id"] == "81093"
        assert tc.classify("https://example.com/app.js") == []
        assert tc.classify("not a url") == []


# ------------------------------------------------------------ analysis


def ga4_hit(event, p="1", s="1", tid="G-ABC123"):
    return tc.classify(f"https://www.google-analytics.com/g/collect?v=2&tid={tid}&_p={p}&_s={s}&en={event}")


def summarise(records, **page):
    return tc.analyse_page({"url": "https://x.com/", "records": records, **page})


class TestAnalysis:
    def test_retried_beacon_is_one_hit(self):
        # a blocked beacon is retried with the same _p/_s: must not look like double counting
        s = summarise(ga4_hit("page_view") + ga4_hit("page_view"))
        assert s["hits"] == 1
        assert not [f for f in tc.as_findings([s]) if "times" in f["title"]]

    def test_real_double_page_view(self):
        s = summarise(ga4_hit("page_view", s="1") + ga4_hit("page_view", s="2"))
        titles = [f["title"] for f in tc.as_findings([s])]
        assert "GA4 G-ABC123 counts every page view 2 times" in titles

    def test_ga4_without_page_view(self):
        s = summarise(ga4_hit("scroll"))
        f = [x for x in tc.as_findings([s]) if "records no page views" in x["title"]]
        assert f and f[0]["priority"] == "P1"

    def test_loaded_but_silent_meta_is_p1(self):
        recs = tc.classify("https://connect.facebook.net/signals/config/1234567890?v=2")
        f = tc.as_findings([summarise(recs)])
        assert any(x["title"] == "Meta Pixel 1234567890 loads but sends nothing" and x["priority"] == "P1" for x in f)

    def test_silent_tag_softened_by_consent(self):
        recs = tc.classify("https://connect.facebook.net/signals/config/1234567890?v=2")
        state = {"gtag": [["consent", "default", '{"analytics_storage":"denied","ad_storage":"denied"}']]}
        f = tc.as_findings([summarise(recs, state=state)])
        assert any(x["title"] == "No tracking fires before cookie consent" for x in f)
        assert all(x["priority"] != "P1" for x in f)

    def test_registry_only_destination_is_not_flagged(self):
        s = summarise(ga4_hit("page_view"), state={"gtm": ["GTM-AAAA", "G-ABC123", "G-OTHER1"]})
        other = [t for t in s["tags"] if t["id"] == "G-OTHER1"][0]
        assert other["source"] == "registry" and not other["fired"]
        assert not [f for f in tc.as_findings([s]) if "G-OTHER1" in f["title"]]

    def test_idless_rows_fold_into_the_only_tag(self):
        recs = tc.classify("https://connect.facebook.net/en_US/fbevents.js") + tc.classify(
            "https://www.facebook.com/tr/?id=42424242&ev=PageView"
        )
        s = summarise(recs)
        assert [(t["vendor"], t["id"], t["fired"]) for t in s["tags"]] == [("Meta Pixel", "42424242", True)]

    def test_nothing_fires(self):
        f = tc.as_findings([summarise([])])
        assert [x["title"] for x in f] == ["No analytics hits fired"]

    def test_universal_analytics_in_registry(self):
        s = summarise(ga4_hit("page_view"), state={"gtm": ["UA-111-1"]})
        assert any(x["title"] == "Universal Analytics UA-111-1 still installed" for x in tc.as_findings([s]))

    def test_conversion_page(self):
        miss = summarise(ga4_hit("page_view"), conversion_page=True)
        assert any(x["title"].startswith("No conversion event fires") for x in tc.as_findings([miss]))
        ok = summarise(ga4_hit("page_view") + ga4_hit("generate_lead", s="2"), conversion_page=True)
        assert ok["conversions"] == ["GA4 G-ABC123 generate_lead"]
        assert not any(x["title"].startswith("No conversion") for x in tc.as_findings([ok]))

    def test_render_only_report(self):
        recs = tc.classify("https://www.googletagmanager.com/gtm.js?id=GTM-AAAA") + tc.classify(
            "https://www.facebook.com/tr/?id=42424242&ev=PageView"
        )
        rep = tc.build_report([{"url": "https://x.com/", "records": recs, "raw_html": "GTM-AAAA"}])
        assert rep["summary"]["render_only_tags"] == ["Meta Pixel 42424242"]
        assert rep["findings"] == [] and rep["module_scores"]["tag_check"]["hits"] == 1
        assert all(f["module"] == "tag_check" for f in rep["findings"])


# ------------------------------------------------------------ plumbing


class TestPlumbing:
    def test_frame_parser_handles_partial_and_extended(self):
        c = tc.CDP.__new__(tc.CDP)
        payload = b'{"id":1}' * 40  # 320 bytes -> 16-bit length
        frame = bytes([0x81, 126]) + struct.pack(">H", len(payload)) + payload
        c.buf = frame[:50]
        assert c._frame() is None  # incomplete: nothing consumed
        c.buf = frame + b"\x81"
        fin, op, data = c._frame()
        assert fin and op == 1 and data == payload and c.buf == b"\x81"

    def test_git_bash_path_rewrite_undone(self):
        assert tc._undo_msys_path("C:/Program Files/Git/thank-you") == "/thank-you"
        assert tc._undo_msys_path("/thank-you") == "/thank-you"
        assert tc._undo_msys_path("https://x.com/thanks") == "https://x.com/thanks"

    def test_browser_env_override(self, monkeypatch, tmp_path):
        fake = tmp_path / "chrome"
        fake.write_text("")
        monkeypatch.setenv("FAT_CHROME", str(fake))
        assert tc.find_browser() == str(fake)


# ------------------------------------------------------------ end to end

E2E_PAGE = b"""<!doctype html><html><head><title>t</title>
<script>
navigator.sendBeacon('/g/collect?v=2&tid=G-LOCAL1&_p=7&_s=1', 'en=page_view\\nen=generate_lead');
new Image().src = 'https://www.facebook.com/tr/?id=99887766&ev=Lead';
</script></head><body>ok</body></html>"""


@pytest.mark.skipif(tc.find_browser() is None, reason="no Chrome/Edge/Chromium installed")
def test_end_to_end_headless_browser():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(E2E_PAGE)

        def do_POST(self):
            self.send_response(204)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_port}/"
        rep = tc.build_report(tc.run(url, pages=["/thanks"], wait=1.0))
    finally:
        srv.shutdown()
    home, thanks = rep["pages"]
    ga4 = [t for t in home["tags"] if t["id"] == "G-LOCAL1"][0]
    assert ga4["events"] == ["page_view", "generate_lead"]
    assert "Meta Pixel 99887766 Lead" in thanks["conversions"]
    assert not any(f["title"].startswith("No conversion") for f in rep["findings"])


# ------------------------------------------------------------ static analyser

GTM = "<script>(function(w,d,s,l,i){w[l]=w[l]||[];j.src='https://www.googletagmanager.com/gtm.js?id='+i;})(window,document,'script','dataLayer','GTM-AB12CD');</script>"
GTAG = "<script async src='https://www.googletagmanager.com/gtag/js?id=G-ABC123'></script><script>gtag('js', new Date());gtag('config', 'G-ABC123');</script>"
PIXEL = "<script>fbq('init', '1234567890');fbq('track', 'PageView');</script>"


def static(head):
    r = analyse_html(f"<html lang='en'><head><title>Static tag test page title</title>{head}</head><body><h1>x</h1></body></html>")
    issues = [i for lvl in ("critical", "high", "medium", "low") for i in r["summary"][lvl]]
    return r, issues


class TestStaticTags:
    def test_ids_extracted(self):
        r, _ = static(GTM + GTAG + PIXEL + "<script>gtag('config','AW-555')</script>")
        ids = r["analytics"]["tag_ids"]
        assert ids["gtm"] == ["GTM-AB12CD"] and ids["ga4"] == ["G-ABC123"]
        assert ids["meta_pixel"] == ["1234567890"] and ids["google_ads"] == ["AW-555"]
        assert r["analytics"]["duplicate_tags"] == []

    def test_duplicates_flagged_high(self):
        r, _ = static(GTM + GTM + GTAG + GTAG + PIXEL + PIXEL)
        high = r["summary"]["high"]
        assert "GTM container GTM-AB12CD installed 2 times (every tag in it fires 2x)" in high
        assert "GA4 G-ABC123 configured 2 times (page views double-counted)" in high
        assert "Google tag library for G-ABC123 loaded 2 times" in high
        assert "Meta Pixel 1234567890 initialised 2 times (events double-counted)" in high

    def test_ua_only_is_high_and_leftover_is_low(self):
        r, _ = static("<script>ga('create', 'UA-1234-1', 'auto');</script><script src='https://www.google-analytics.com/analytics.js'></script>")
        assert any(i.startswith("Only Universal Analytics installed (UA-1234-1)") for i in r["summary"]["high"])
        r, _ = static(GTAG + "<script>gtag('config','UA-1234-1')</script>")
        assert any(i.startswith("Leftover Universal Analytics tag") for i in r["summary"]["low"])

    def test_no_analytics_is_high(self):
        r, _ = static("")
        assert "No analytics tracking detected" in r["summary"]["high"]

    def test_no_analytics_on_spa_is_medium_with_pointer(self):
        r = analyse_html("<html lang='en'><head><title>App</title><script type='module' src='/assets/index-abc.js'></script></head><body><div id='root'></div></body></html>")
        assert not any("No analytics" in i for i in r["summary"]["high"])
        assert any("No analytics tracking detected in server HTML" in i and "tag_check.py" in i for i in r["summary"]["medium"])


# ------------------------------------------------------------ public-only proxy (server-side runs)


class TestPublicOnly:
    def test_private_addresses(self):
        for ip in ("127.0.0.1", "10.1.2.3", "172.17.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "::1", "fd00::1", "::ffff:127.0.0.1", "0.0.0.0", "nonsense"):
            assert tc.private_address(ip), ip
        for ip in ("1.1.1.1", "142.250.70.78", "2606:4700:4700::1111"):
            assert not tc.private_address(ip), ip

    def _ask(self, proxy, raw):
        import socket as _s
        c = _s.create_connection(("127.0.0.1", proxy.port), timeout=5)
        c.sendall(raw)
        out = c.recv(200)
        c.close()
        return out

    def test_proxy_refuses_loopback_and_odd_ports(self):
        p = tc.PublicOnlyProxy()
        try:
            assert self._ask(p, b"CONNECT 127.0.0.1:443 HTTP/1.1\r\nHost: 127.0.0.1:443\r\n\r\n").startswith(b"HTTP/1.1 403")
            assert self._ask(p, b"GET http://localhost:80/ HTTP/1.1\r\nHost: localhost\r\n\r\n").startswith(b"HTTP/1.1 403")
            assert self._ask(p, b"CONNECT 1.1.1.1:22 HTTP/1.1\r\nHost: 1.1.1.1:22\r\n\r\n").startswith(b"HTTP/1.1 403")
            assert self._ask(p, b"GET ftp://x/ HTTP/1.1\r\n\r\n").startswith(b"HTTP/1.1 400")
            assert "127.0.0.1:443" in p.blocked and "1.1.1.1:22" in p.blocked
        finally:
            p.close()


@pytest.mark.skipif(tc.find_browser() is None, reason="no Chrome/Edge/Chromium installed")
def test_public_only_browser_cannot_reach_local_server():
    hit = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hit.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(E2E_PAGE)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        rep = tc.build_report(tc.run(f"http://127.0.0.1:{srv.server_port}/", wait=0.5, public_only=True))
    finally:
        srv.shutdown()
    assert hit == []  # the request never reached the local server
    assert rep["summary"]["blocked_private"] == [f"127.0.0.1:{srv.server_port}"]


class TestThankYouPageStatus:
    def test_404_thank_you_page_is_flagged_not_judged(self):
        s = summarise(ga4_hit("page_view"), conversion_page=True, status=404)
        titles = [f["title"] for f in tc.as_findings([s])]
        assert "Thank-you page returns 404: https://x.com/" in titles
        assert not any(t.startswith("No conversion event fires") for t in titles)

    def test_tiktok_engaged_session_is_not_a_conversion(self):
        r = hits("https://analytics.tiktok.com/api/v2/pixel", "POST", '{"event":"EngagedSession","context":{"pixel":{"code":"B1"}}}')
        assert not tc.is_conversion(r[0])
