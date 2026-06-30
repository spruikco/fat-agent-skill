import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.cookie_gdpr import CookieGDPRModule

# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------


def test_detect_true_for_form():
    html = "<html><body><form action='/submit'><input type='text'></form></body></html>"
    assert CookieGDPRModule.detect(html) is True


def test_detect_true_for_analytics():
    html = "<html><head><script src='https://www.googletagmanager.com/gtag/js'></script></head><body></body></html>"
    assert CookieGDPRModule.detect(html) is True


def test_detect_true_for_cookie_reference():
    html = "<html><body><script>document.cookie = 'foo=bar';</script></body></html>"
    assert CookieGDPRModule.detect(html) is True


def test_detect_false_for_plain_page():
    html = "<html><body><h1>Hello</h1><p>No tracking here.</p></body></html>"
    assert CookieGDPRModule.detect(html) is False


# ---------------------------------------------------------------------------
# analyse() tests
# ---------------------------------------------------------------------------


def test_analyse_detects_cookiebot():
    html = """<html><head>
    <script src="https://consent.cookiebot.com/uc.js"></script>
    </head><body>
    <a href="/privacy-policy">Privacy Policy</a>
    <a href="/cookie-policy">Cookie Policy</a>
    <p>Data controller: Acme Ltd</p>
    </body></html>"""
    mod = CookieGDPRModule()
    result = mod.analyse(html)
    assert result["has_consent_banner"] is True
    assert "cookiebot" in result["detected_banners"]
    assert result["has_privacy_policy_link"] is True
    assert result["has_cookie_policy"] is True
    assert result["has_data_controller_info"] is True


def test_analyse_detects_onetrust():
    html = '<html><head><script src="https://cdn.onetrust.com/scripttemplates/otSDKStub.js"></script></head><body></body></html>'
    mod = CookieGDPRModule()
    result = mod.analyse(html)
    assert result["has_consent_banner"] is True
    assert "onetrust" in result["detected_banners"]


def test_analyse_detects_complianz():
    html = (
        "<html><head><script>var cmplz_config = {};</script></head><body></body></html>"
    )
    mod = CookieGDPRModule()
    result = mod.analyse(html)
    assert result["has_consent_banner"] is True
    assert "complianz" in result["detected_banners"]


def test_analyse_no_consent():
    html = "<html><body><form><input type='email'></form></body></html>"
    mod = CookieGDPRModule()
    result = mod.analyse(html)
    assert result["has_consent_banner"] is False
    assert result["has_privacy_policy_link"] is False
    assert result["has_cookie_policy"] is False


def test_analyse_consent_before_tracking():
    html = '<html><body><script data-cookie-consent="analytics" src="tracker.js"></script></body></html>'
    mod = CookieGDPRModule()
    result = mod.analyse(html)
    assert result["consent_before_tracking"] is True


def test_analyse_privacy_link_variants():
    html = '<html><body><a href="/our-privacy-notice">Privacy</a></body></html>'
    mod = CookieGDPRModule()
    result = mod.analyse(html)
    assert result["has_privacy_policy_link"] is True


# ---------------------------------------------------------------------------
# score() tests
# ---------------------------------------------------------------------------


def test_score_perfect():
    mod = CookieGDPRModule()
    analysis = {
        "has_consent_banner": True,
        "has_privacy_policy_link": True,
        "has_cookie_policy": True,
        "consent_before_tracking": True,
        "has_data_controller_info": True,
    }
    result = mod.score(analysis)
    assert result["total"] == 100
    assert len(mod.findings) == 0


def test_score_zero():
    mod = CookieGDPRModule()
    analysis = {
        "has_consent_banner": False,
        "has_privacy_policy_link": False,
        "has_cookie_policy": False,
        "consent_before_tracking": False,
        "has_data_controller_info": False,
        "has_tracking": True,  # tracking present -> consent/tracking findings apply
    }
    result = mod.score(analysis)
    assert result["total"] == 0
    assert len(mod.findings) == 5


def test_no_consent_finding_without_tracking():
    # a site with NO tracking shouldn't be told it's missing a consent banner
    mod = CookieGDPRModule()
    mod.score(
        {
            "has_consent_banner": False,
            "has_privacy_policy_link": True,
            "has_cookie_policy": True,
            "consent_before_tracking": False,
            "has_data_controller_info": True,
            "has_tracking": False,
        }
    )
    assert not any("consent banner" in f["title"].lower() for f in mod.findings)


def test_score_partial():
    mod = CookieGDPRModule()
    analysis = {
        "has_consent_banner": True,
        "has_privacy_policy_link": True,
        "has_cookie_policy": False,
        "consent_before_tracking": False,
        "has_data_controller_info": False,
    }
    result = mod.score(analysis)
    assert result["total"] == 55
    assert result["has_consent_banner"] == 30
    assert result["has_privacy_policy_link"] == 25
