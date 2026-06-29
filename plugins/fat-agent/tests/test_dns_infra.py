import os
import sys
from unittest.mock import MagicMock

# add the scripts directory to sys.path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.dns_infra import DNSInfraModule

# ---------------------------------------------------------------------------
# detect() tests — module is opt-in, never auto-detected
# ---------------------------------------------------------------------------


def test_detect_always_returns_false():
    assert DNSInfraModule.detect("") is False
    assert DNSInfraModule.detect("<html><body>Hello</body></html>") is False
    assert (
        DNSInfraModule.detect(
            '<html><form action="/buy"><input type="email"></form></html>'
        )
        is False
    )


# ---------------------------------------------------------------------------
# module metadata
# ---------------------------------------------------------------------------


def test_module_id():
    assert DNSInfraModule.MODULE_ID == "dns_infra"


def test_display_name():
    assert DNSInfraModule.DISPLAY_NAME == "DNS & Infrastructure"


# ---------------------------------------------------------------------------
# score() tests — pre-built analysis dicts, no DNS/SSL lookups
# ---------------------------------------------------------------------------


def test_score_perfect():
    """All checks pass: SSL valid with >30 days, DNSSEC, CAA, CDN, HTTP/2."""
    analysis = {
        "ssl_valid": True,
        "ssl_days_remaining": 90,
        "has_dnssec": True,
        "has_caa_record": True,
        "has_cdn": True,
        "cdn_provider": "Cloudflare",
        "http2_support": True,
    }
    mod = DNSInfraModule()
    result = mod.score(analysis)
    assert result["total"] == 100


def test_score_all_failing():
    analysis = {
        "ssl_valid": False,
        "ssl_days_remaining": 0,
        "has_dnssec": False,
        "has_caa_record": False,
        "has_cdn": False,
        "cdn_provider": None,
        "http2_support": False,
    }
    mod = DNSInfraModule()
    result = mod.score(analysis)
    assert result["total"] == 0


def test_score_ssl_valid_but_expiring_soon():
    """SSL is valid but fewer than 30 days remaining — no bonus."""
    analysis = {
        "ssl_valid": True,
        "ssl_days_remaining": 15,
        "has_dnssec": False,
        "has_caa_record": False,
        "has_cdn": False,
        "cdn_provider": None,
        "http2_support": False,
    }
    mod = DNSInfraModule()
    result = mod.score(analysis)
    assert result["ssl_valid"] == 25
    assert result["ssl_days_remaining"] == 0
    assert result["total"] == 25


def test_score_ssl_valid_with_long_expiry():
    """SSL valid + >30 days remaining gives both points."""
    analysis = {
        "ssl_valid": True,
        "ssl_days_remaining": 60,
        "has_dnssec": False,
        "has_caa_record": False,
        "has_cdn": False,
        "cdn_provider": None,
        "http2_support": False,
    }
    mod = DNSInfraModule()
    result = mod.score(analysis)
    assert result["ssl_valid"] == 25
    assert result["ssl_days_remaining"] == 15
    assert result["total"] == 40


def test_score_dnssec_only():
    analysis = {
        "ssl_valid": False,
        "ssl_days_remaining": 0,
        "has_dnssec": True,
        "has_caa_record": False,
        "has_cdn": False,
        "cdn_provider": None,
        "http2_support": False,
    }
    mod = DNSInfraModule()
    result = mod.score(analysis)
    assert result["has_dnssec"] == 15
    assert result["total"] == 15


def test_score_cdn_and_http2():
    analysis = {
        "ssl_valid": False,
        "ssl_days_remaining": 0,
        "has_dnssec": False,
        "has_caa_record": False,
        "has_cdn": True,
        "cdn_provider": "Fastly",
        "http2_support": True,
    }
    mod = DNSInfraModule()
    result = mod.score(analysis)
    assert result["has_cdn"] == 15
    assert result["http2_support"] == 15
    assert result["total"] == 30


def test_score_individual_breakdown():
    """Verify each key in the returned dict."""
    analysis = {
        "ssl_valid": True,
        "ssl_days_remaining": 45,
        "has_dnssec": True,
        "has_caa_record": True,
        "has_cdn": True,
        "cdn_provider": "CloudFront",
        "http2_support": True,
    }
    mod = DNSInfraModule()
    result = mod.score(analysis)
    assert result["ssl_valid"] == 25
    assert result["ssl_days_remaining"] == 15
    assert result["has_dnssec"] == 15
    assert result["has_caa_record"] == 15
    assert result["has_cdn"] == 15
    assert result["http2_support"] == 15
    assert result["total"] == 100


# ---------------------------------------------------------------------------
# score() — findings generation
# ---------------------------------------------------------------------------


def test_score_generates_finding_for_invalid_ssl():
    analysis = {
        "ssl_valid": False,
        "ssl_days_remaining": 0,
        "has_dnssec": True,
        "has_caa_record": True,
        "has_cdn": True,
        "cdn_provider": "Cloudflare",
        "http2_support": True,
    }
    mod = DNSInfraModule()
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any("SSL" in t or "ssl" in t.lower() for t in titles)


def test_score_generates_finding_for_missing_dnssec():
    analysis = {
        "ssl_valid": True,
        "ssl_days_remaining": 90,
        "has_dnssec": False,
        "has_caa_record": True,
        "has_cdn": True,
        "cdn_provider": "Cloudflare",
        "http2_support": True,
    }
    mod = DNSInfraModule()
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any("DNSSEC" in t for t in titles)


def test_score_generates_finding_for_missing_caa():
    analysis = {
        "ssl_valid": True,
        "ssl_days_remaining": 90,
        "has_dnssec": True,
        "has_caa_record": False,
        "has_cdn": True,
        "cdn_provider": "Cloudflare",
        "http2_support": True,
    }
    mod = DNSInfraModule()
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any("CAA" in t for t in titles)


def test_score_generates_finding_for_expiring_ssl():
    analysis = {
        "ssl_valid": True,
        "ssl_days_remaining": 10,
        "has_dnssec": True,
        "has_caa_record": True,
        "has_cdn": True,
        "cdn_provider": "Cloudflare",
        "http2_support": True,
    }
    mod = DNSInfraModule()
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any("expir" in t.lower() or "renew" in t.lower() for t in titles)


# ---------------------------------------------------------------------------
# CDN detection — mock subprocess/headers, verify detect_cdn logic
# ---------------------------------------------------------------------------


def test_cdn_detection_cloudflare():
    mod = DNSInfraModule()
    headers = {"cf-ray": "abc123", "server": "cloudflare"}
    provider = mod._detect_cdn(headers)
    assert provider == "Cloudflare"


def test_cdn_detection_fastly():
    mod = DNSInfraModule()
    headers = {"x-served-by": "cache-lhr1234", "x-cache": "HIT"}
    provider = mod._detect_cdn(headers)
    assert provider == "Fastly"


def test_cdn_detection_cloudfront():
    mod = DNSInfraModule()
    headers = {"x-amz-cf-id": "some-id-123"}
    provider = mod._detect_cdn(headers)
    assert provider == "CloudFront"


def test_cdn_detection_akamai():
    mod = DNSInfraModule()
    headers = {"server": "AkamaiGHost"}
    provider = mod._detect_cdn(headers)
    assert provider == "Akamai"


def test_cdn_detection_generic_x_cdn():
    mod = DNSInfraModule()
    headers = {"x-cdn": "KeyCDN"}
    provider = mod._detect_cdn(headers)
    assert provider == "KeyCDN"


def test_cdn_detection_none():
    mod = DNSInfraModule()
    headers = {"server": "nginx", "content-type": "text/html"}
    provider = mod._detect_cdn(headers)
    assert provider is None


def test_cdn_detection_empty_headers():
    mod = DNSInfraModule()
    provider = mod._detect_cdn({})
    assert provider is None


def test_cdn_detection_none_headers():
    mod = DNSInfraModule()
    provider = mod._detect_cdn(None)
    assert provider is None


# ---------------------------------------------------------------------------
# analyse() with mocked subprocess — no real network calls
# --------------------------------------------------------------------------


def test_analyse_uses_headers_for_cdn(monkeypatch):
    """analyse() should detect CDN from the provided headers dict."""
    mod = DNSInfraModule()

    # mock all subprocess calls to avoid real dns/ssl lookups
    mock_run = MagicMock()
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
    monkeypatch.setattr("subprocess.run", mock_run)

    headers = {"cf-ray": "abc123", "server": "cloudflare"}
    result = mod.analyse(
        html="<html></html>",
        url="https://example.com",
        headers=headers,
    )
    assert result["has_cdn"] is True
    assert result["cdn_provider"] == "Cloudflare"


def test_analyse_no_url_returns_safe_defaults(monkeypatch):
    """analyse() with empty URL still returns a valid dict."""
    mod = DNSInfraModule()

    mock_run = MagicMock()
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
    monkeypatch.setattr("subprocess.run", mock_run)

    result = mod.analyse(html="<html></html>", url="", headers={})
    assert result["ssl_valid"] is False
    assert result["has_dnssec"] is False
    assert result["has_caa_record"] is False
    assert result["has_cdn"] is False
    assert result["http2_support"] is False
