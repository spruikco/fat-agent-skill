import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.security import SecurityModule

# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_always_true():
    assert SecurityModule.detect("<html></html>") is True


def test_detect_always_true_empty():
    assert SecurityModule.detect("") is True


# ---------------------------------------------------------------------------
# analyse()
# ---------------------------------------------------------------------------


def test_analyse_no_mixed_content():
    html = '<html><body><img src="https://example.com/img.jpg"></body></html>'
    mod = SecurityModule()
    result = mod.analyse(html)
    assert result["has_mixed_content"] is False
    assert result["mixed_content_count"] == 0


def test_analyse_detects_mixed_content():
    html = '<html><body><img src="http://example.com/img.jpg"></body></html>'
    mod = SecurityModule()
    result = mod.analyse(html)
    assert result["has_mixed_content"] is True
    assert result["mixed_content_count"] == 1


def test_analyse_detects_noopener_missing():
    html = (
        '<html><body><a href="https://evil.com" target="_blank">Link</a></body></html>'
    )
    mod = SecurityModule()
    result = mod.analyse(html)
    assert result["external_links_total"] == 1
    assert result["external_links_without_noopener"] == 1


def test_analyse_noopener_present():
    html = '<html><body><a href="https://safe.com" target="_blank" rel="noopener noreferrer">Link</a></body></html>'
    mod = SecurityModule()
    result = mod.analyse(html)
    assert result["external_links_total"] == 1
    assert result["external_links_without_noopener"] == 0


def test_analyse_inline_event_handlers():
    html = '<html><body><button onclick="alert(1)">Click</button><div onmouseover="foo()"></div></body></html>'
    mod = SecurityModule()
    result = mod.analyse(html)
    assert result["inline_event_handlers"] == 2


def test_analyse_with_headers():
    html = "<html><body></body></html>"
    headers = {
        "Strict-Transport-Security": "max-age=31536000",
        "Content-Security-Policy": "default-src 'self'",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=()",
    }
    mod = SecurityModule()
    result = mod.analyse(html, headers=headers)
    assert result["has_hsts"] is True
    assert result["has_csp"] is True
    assert result["has_x_frame_options"] is True
    assert result["has_x_content_type_options"] is True
    assert result["has_referrer_policy"] is True
    assert result["has_permissions_policy"] is True
    assert result["headers_available"] is True


def test_analyse_without_headers():
    html = "<html><body></body></html>"
    mod = SecurityModule()
    result = mod.analyse(html)
    assert result["headers_available"] is False
    assert result["has_hsts"] is False


# ---------------------------------------------------------------------------
# score()
# ---------------------------------------------------------------------------


def test_score_perfect_with_headers():
    analysis = {
        "has_mixed_content": False,
        "mixed_content_count": 0,
        "external_links_total": 0,
        "external_links_without_noopener": 0,
        "inline_event_handlers": 0,
        "has_hsts": True,
        "has_csp": True,
        "has_x_frame_options": True,
        "has_x_content_type_options": True,
        "has_referrer_policy": True,
        "has_permissions_policy": True,
        "headers_available": True,
    }
    mod = SecurityModule()
    result = mod.score(analysis)
    assert result["total"] == 100
    assert len(mod.findings) == 0


def test_score_no_headers_partial():
    analysis = {
        "has_mixed_content": False,
        "mixed_content_count": 0,
        "external_links_total": 2,
        "external_links_without_noopener": 1,
        "inline_event_handlers": 0,
        "has_hsts": False,
        "has_csp": False,
        "has_x_frame_options": False,
        "has_x_content_type_options": False,
        "has_referrer_policy": False,
        "has_permissions_policy": False,
        "headers_available": False,
    }
    mod = SecurityModule()
    result = mod.score(analysis)
    assert result["total"] < 20
    assert "note" in result


def test_score_mixed_content_finding():
    analysis = {
        "has_mixed_content": True,
        "mixed_content_count": 3,
        "external_links_total": 0,
        "external_links_without_noopener": 0,
        "inline_event_handlers": 0,
        "has_hsts": True,
        "has_csp": True,
        "has_x_frame_options": True,
        "has_x_content_type_options": True,
        "has_referrer_policy": True,
        "has_permissions_policy": True,
        "headers_available": True,
    }
    mod = SecurityModule()
    mod.score(analysis)
    p0 = [f for f in mod.findings if f["priority"] == "P0"]
    assert len(p0) == 1
    assert "mixed content" in p0[0]["title"].lower()


def test_score_missing_all_headers_findings():
    analysis = {
        "has_mixed_content": False,
        "mixed_content_count": 0,
        "external_links_total": 0,
        "external_links_without_noopener": 0,
        "inline_event_handlers": 0,
        "has_hsts": False,
        "has_csp": False,
        "has_x_frame_options": False,
        "has_x_content_type_options": False,
        "has_referrer_policy": False,
        "has_permissions_policy": False,
        "headers_available": True,
    }
    mod = SecurityModule()
    mod.score(analysis)
    priorities = [f["priority"] for f in mod.findings]
    assert "P1" in priorities
    assert "P2" in priorities
    assert "P3" in priorities
