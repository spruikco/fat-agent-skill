"""Depth checks added to the security module (findings-only)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.security import SecurityModule

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _analyse_and_score(html, url="", headers=None):
    mod = SecurityModule()
    analysis = mod.analyse(html, url=url, headers=headers)
    mod.score(analysis)
    return analysis, mod


# ---------------------------------------------------------------------------
# CSP quality
# ---------------------------------------------------------------------------


def test_csp_weaknesses_detected():
    headers = {
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'"
        )
    }
    analysis, mod = _analyse_and_score("<html></html>", headers=headers)
    assert "unsafe-inline" in analysis["csp_weaknesses"]
    assert "unsafe-eval" in analysis["csp_weaknesses"]
    assert any("CSP present but weakened" in f["title"] for f in mod.findings)


def test_csp_wildcard_source_detected():
    headers = {"Content-Security-Policy": "script-src * 'self'"}
    analysis, _ = _analyse_and_score("<html></html>", headers=headers)
    assert "wildcard-source" in analysis["csp_weaknesses"]


def test_csp_strict_no_weaknesses():
    headers = {"Content-Security-Policy": "default-src 'self'; script-src 'self'"}
    analysis, mod = _analyse_and_score("<html></html>", headers=headers)
    assert analysis["csp_weaknesses"] == []
    assert not any("weakened" in f["title"] for f in mod.findings)


# ---------------------------------------------------------------------------
# HSTS quality
# ---------------------------------------------------------------------------


def test_hsts_short_max_age_flagged():
    headers = {"Strict-Transport-Security": "max-age=300"}
    analysis, mod = _analyse_and_score("<html></html>", headers=headers)
    assert analysis["hsts_max_age"] == 300
    assert any("max-age too short" in f["title"] for f in mod.findings)


def test_hsts_missing_include_subdomains_flagged():
    headers = {"Strict-Transport-Security": "max-age=31536000"}
    analysis, mod = _analyse_and_score("<html></html>", headers=headers)
    assert analysis["hsts_include_subdomains"] is False
    assert any("includeSubDomains" in f["title"] for f in mod.findings)


def test_hsts_strong_not_flagged():
    headers = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload"
    }
    _, mod = _analyse_and_score("<html></html>", headers=headers)
    assert not any(
        "HSTS" in f["title"] and f["priority"] in ("P2", "P3") for f in mod.findings
    )


# ---------------------------------------------------------------------------
# Set-Cookie flags
# ---------------------------------------------------------------------------


def test_cookie_missing_flags_detected():
    headers = {"Set-Cookie": "session=abc123; Path=/"}
    analysis, mod = _analyse_and_score("<html></html>", headers=headers)
    assert set(analysis["cookie_missing_flags"]) == {"secure", "httponly", "samesite"}
    assert any("Cookies set without" in f["title"] for f in mod.findings)


def test_cookie_hardened_not_flagged():
    headers = {"Set-Cookie": "session=abc; Secure; HttpOnly; SameSite=Lax"}
    analysis, mod = _analyse_and_score("<html></html>", headers=headers)
    assert analysis["cookie_missing_flags"] == []
    assert not any("Cookies set without" in f["title"] for f in mod.findings)


# ---------------------------------------------------------------------------
# server version disclosure
# ---------------------------------------------------------------------------


def test_server_version_disclosure_detected():
    headers = {"Server": "nginx/1.18.0"}
    analysis, mod = _analyse_and_score("<html></html>", headers=headers)
    assert "nginx/1.18.0" in analysis["server_version_header"]
    assert any("Server version disclosed" in f["title"] for f in mod.findings)


def test_server_no_version_not_flagged():
    headers = {"Server": "cloudflare"}
    analysis, _ = _analyse_and_score("<html></html>", headers=headers)
    assert analysis["server_version_header"] == ""


def test_x_powered_by_version_detected():
    headers = {"X-Powered-By": "PHP/8.1.2"}
    analysis, _ = _analyse_and_score("<html></html>", headers=headers)
    assert "PHP/8.1.2" in analysis["server_version_header"]


# ---------------------------------------------------------------------------
# Subresource Integrity
# ---------------------------------------------------------------------------


def test_sri_missing_on_cross_origin_script():
    html = '<script src="https://cdn.example.net/lib.js"></script>'
    analysis, mod = _analyse_and_score(html, url="https://mysite.com/")
    assert analysis["scripts_missing_sri"] == 1
    assert any("Subresource Integrity" in f["title"] for f in mod.findings)


def test_sri_present_not_flagged():
    html = (
        '<script src="https://cdn.example.net/lib.js" '
        'integrity="sha384-abc" crossorigin="anonymous"></script>'
    )
    analysis, _ = _analyse_and_score(html, url="https://mysite.com/")
    assert analysis["scripts_missing_sri"] == 0


def test_sri_same_origin_script_not_counted():
    html = '<script src="https://mysite.com/app.js"></script>'
    analysis, _ = _analyse_and_score(html, url="https://mysite.com/")
    assert analysis["scripts_missing_sri"] == 0


def test_sri_relative_script_not_counted():
    html = '<script src="/assets/app.js"></script>'
    analysis, _ = _analyse_and_score(html, url="https://mysite.com/")
    assert analysis["scripts_missing_sri"] == 0


def test_sri_protocol_relative_counted():
    html = '<script src="//cdn.example.net/lib.js"></script>'
    analysis, _ = _analyse_and_score(html, url="https://mysite.com/")
    assert analysis["scripts_missing_sri"] == 1


# ---------------------------------------------------------------------------
# exposed secrets
# ---------------------------------------------------------------------------


def test_exposed_stripe_key_is_p0():
    html = '<script>var k = "sk_live_a1B2c3D4e5F6g7H8";</script>'
    analysis, mod = _analyse_and_score(html)
    assert analysis["exposed_secrets"]
    assert analysis["exposed_secrets"][0]["type"] == "Stripe live secret key"
    p0 = [f for f in mod.findings if f["priority"] == "P0"]
    assert any("Secret exposed" in f["title"] for f in p0)


def test_exposed_secret_never_echoed_in_full():
    token = "sk_live_" + "a" * 24
    html = "<script>var k = '%s';</script>" % token
    analysis, mod = _analyse_and_score(html)
    assert token not in analysis["exposed_secrets"][0]["hint"]
    assert token not in json.dumps(mod.findings)


def test_google_api_key_is_p2_verify_restrictions():
    html = (
        '<script src="https://maps.googleapis.com/maps/api/js?key=AIza'
        + "B" * 35
        + '"></script>'
    )
    analysis, mod = _analyse_and_score(html)
    assert any(
        s["type"].startswith("Google API key") for s in analysis["exposed_secrets"]
    )
    assert any(
        f["priority"] == "P2" and "verify restrictions" in f["title"]
        for f in mod.findings
    )


def test_aws_key_detected():
    html = "<script>var a = 'AKIAIOSFODNN7EXAMPLE';</script>"
    analysis, _ = _analyse_and_score(html)
    assert any(s["type"] == "AWS access key ID" for s in analysis["exposed_secrets"])


def test_private_key_block_detected():
    html = "<pre>-----BEGIN RSA PRIVATE KEY-----</pre>"
    analysis, _ = _analyse_and_score(html)
    assert any(s["type"] == "Private key block" for s in analysis["exposed_secrets"])


def test_clean_page_no_secrets():
    analysis, _ = _analyse_and_score("<html><body>Hello</body></html>")
    assert analysis["exposed_secrets"] == []


# ---------------------------------------------------------------------------
# source maps
# ---------------------------------------------------------------------------


def test_sourcemap_reference_flagged():
    html = "<script>//# sourceMappingURL=app.js.map</script>"
    analysis, mod = _analyse_and_score(html)
    assert analysis["sourcemap_refs"] == 1
    assert any("Source maps referenced" in f["title"] for f in mod.findings)


# ---------------------------------------------------------------------------
# scoring parity
# ---------------------------------------------------------------------------


def test_deep_findings_run_without_headers_too():
    html = '<script src="https://cdn.example.net/lib.js"></script>'
    _, mod = _analyse_and_score(html, url="https://mysite.com/")
    assert any("Subresource Integrity" in f["title"] for f in mod.findings)


def test_score_totals_unchanged_by_depth_checks():
    headers = {
        "Strict-Transport-Security": "max-age=300",
        "Content-Security-Policy": "script-src 'unsafe-inline'",
        "Set-Cookie": "a=b",
        "Server": "nginx/1.18.0",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=()",
    }
    mod = SecurityModule()
    analysis = mod.analyse("<html></html>", headers=headers)
    result = mod.score(analysis)
    # every scored bucket is presence-based and all headers are present, so the
    # weakened CSP / short HSTS / bare cookie cost findings, never points
    assert result["total"] == 100
