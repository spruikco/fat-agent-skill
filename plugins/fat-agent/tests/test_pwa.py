import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.pwa import PWAModule

# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------


def test_detect_true_for_manifest():
    html = "<html><head><link rel='manifest' href='/manifest.json'></head><body></body></html>"
    assert PWAModule.detect(html) is True


def test_detect_true_for_service_worker():
    html = "<html><body><script>navigator.serviceWorker.register('/sw.js');</script></body></html>"
    assert PWAModule.detect(html) is True


def test_detect_true_for_workbox():
    html = "<html><body><script src='/workbox-sw.js'></script></body></html>"
    assert PWAModule.detect(html) is True


def test_detect_false_for_plain_page():
    html = "<html><body><h1>Hello</h1></body></html>"
    assert PWAModule.detect(html) is False


# ---------------------------------------------------------------------------
# analyse() tests
# ---------------------------------------------------------------------------


def test_analyse_full_pwa():
    html = """<html><head>
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#317EFB">
    <link rel="apple-touch-icon" href="/icon-192.png">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    </head><body>
    <script>navigator.serviceWorker.register('/sw.js');</script>
    </body></html>"""
    mod = PWAModule()
    result = mod.analyse(html)
    assert result["has_manifest"] is True
    assert result["has_theme_color"] is True
    assert result["has_apple_touch_icon"] is True
    assert result["has_service_worker"] is True
    assert result["has_viewport"] is True


def test_analyse_manifest_only():
    html = "<html><head><link rel='manifest' href='/manifest.json'></head><body></body></html>"
    mod = PWAModule()
    result = mod.analyse(html)
    assert result["has_manifest"] is True
    assert result["has_theme_color"] is False
    assert result["has_service_worker"] is False


def test_analyse_no_pwa_signals():
    html = "<html><body><p>Plain page</p></body></html>"
    mod = PWAModule()
    result = mod.analyse(html)
    assert result["has_manifest"] is False
    assert result["has_theme_color"] is False
    assert result["has_apple_touch_icon"] is False
    assert result["has_service_worker"] is False
    assert result["has_viewport"] is False


def test_analyse_service_worker_via_sw_js():
    html = "<html><body><script src='sw.js'></script></body></html>"
    mod = PWAModule()
    result = mod.analyse(html)
    assert result["has_service_worker"] is True


# ---------------------------------------------------------------------------
# score() tests
# ---------------------------------------------------------------------------


def test_score_perfect():
    mod = PWAModule()
    analysis = {
        "has_manifest": True,
        "has_theme_color": True,
        "has_apple_touch_icon": True,
        "has_service_worker": True,
        "has_viewport": True,
    }
    result = mod.score(analysis)
    assert result["total"] == 100
    assert len(mod.findings) == 0


def test_score_zero():
    mod = PWAModule()
    analysis = {
        "has_manifest": False,
        "has_theme_color": False,
        "has_apple_touch_icon": False,
        "has_service_worker": False,
        "has_viewport": False,
    }
    result = mod.score(analysis)
    assert result["total"] == 0
    assert len(mod.findings) == 5


def test_score_partial():
    mod = PWAModule()
    analysis = {
        "has_manifest": True,
        "has_theme_color": False,
        "has_apple_touch_icon": True,
        "has_service_worker": False,
        "has_viewport": True,
    }
    result = mod.score(analysis)
    assert result["total"] == 60
    assert result["has_manifest"] == 30
    assert result["has_apple_touch_icon"] == 15
    assert result["has_viewport"] == 15
