import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.performance import PerformanceModule

# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_always_true():
    assert PerformanceModule.detect("<html></html>") is True


def test_detect_always_true_empty():
    assert PerformanceModule.detect("") is True


# ---------------------------------------------------------------------------
# analyse()
# ---------------------------------------------------------------------------


def test_analyse_html_size():
    html = "<html><body>" + ("x" * 1024) + "</body></html>"
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["html_size_kb"] > 0


def test_analyse_render_blocking_scripts():
    html = (
        "<html><head>"
        '<script src="block.js"></script>'
        '<script src="async.js" async></script>'
        '<script src="defer.js" defer></script>'
        '<script src="module.js" type="module"></script>'
        "</head><body></body></html>"
    )
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["render_blocking_scripts"] == 1


def test_analyse_no_render_blocking():
    html = '<html><head><script src="ok.js" defer></script></head><body></body></html>'
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["render_blocking_scripts"] == 0


def test_analyse_lazy_loading():
    html = (
        "<html><body>"
        '<img src="a.jpg">'
        '<img src="b.jpg" loading="lazy">'
        '<img src="c.jpg" loading="lazy">'
        "</body></html>"
    )
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["images_total"] == 3
    assert result["images_lazy_loaded"] == 2


def test_analyse_modern_images():
    html = (
        "<html><body>"
        '<img src="a.webp">'
        '<img src="b.avif">'
        '<img src="c.jpg">'
        "</body></html>"
    )
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["images_modern_format"] == 2


def test_analyse_srcset():
    html = '<html><body><img src="a.jpg" srcset="a-2x.jpg 2x"></body></html>'
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["images_with_srcset"] == 1


def test_analyse_picture_elements():
    html = "<html><body><picture><source srcset='a.webp'><img src='a.jpg'></picture></body></html>"
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["picture_elements"] == 1


def test_analyse_inline_assets():
    big_script = "var x = " + "'a' + " * 200 + "'a';"
    html = (
        "<html><head><style>"
        + "body { margin: 0; padding: 0; }" * 40
        + "</style></head>"
        "<body><script>" + big_script + "</script></body></html>"
    )
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["inline_script_kb"] > 0
    assert result["inline_style_kb"] > 0


def test_analyse_preconnect():
    html = '<html><head><link rel="preconnect" href="https://fonts.gstatic.com"></head><body></body></html>'
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["has_preconnect"] is True


def test_analyse_preload():
    html = '<html><head><link rel="preload" href="style.css" as="style"></head><body></body></html>'
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["has_preload"] is True


def test_analyse_no_hints():
    html = "<html><head></head><body></body></html>"
    mod = PerformanceModule()
    result = mod.analyse(html)
    assert result["has_preconnect"] is False
    assert result["has_preload"] is False


# ---------------------------------------------------------------------------
# score()
# ---------------------------------------------------------------------------


def test_score_perfect_performance():
    analysis = {
        "html_size_kb": 20,
        "render_blocking_scripts": 0,
        "images_total": 0,
        "images_lazy_loaded": 0,
        "images_with_srcset": 0,
        "images_modern_format": 0,
        "picture_elements": 0,
        "inline_script_kb": 2,
        "inline_style_kb": 1,
        "has_preconnect": True,
        "has_preload": True,
    }
    mod = PerformanceModule()
    result = mod.score(analysis)
    assert result["total"] >= 85
    assert len(mod.findings) == 0


def test_score_poor_performance():
    analysis = {
        "html_size_kb": 300,
        "render_blocking_scripts": 6,
        "images_total": 10,
        "images_lazy_loaded": 0,
        "images_with_srcset": 0,
        "images_modern_format": 0,
        "picture_elements": 0,
        "inline_script_kb": 40,
        "inline_style_kb": 20,
        "has_preconnect": False,
        "has_preload": False,
    }
    mod = PerformanceModule()
    result = mod.score(analysis)
    assert result["total"] < 30
    priorities = [f["priority"] for f in mod.findings]
    assert "P1" in priorities
    assert "P2" in priorities


def test_score_render_blocking_finding():
    analysis = {
        "html_size_kb": 10,
        "render_blocking_scripts": 3,
        "images_total": 0,
        "images_lazy_loaded": 0,
        "images_with_srcset": 0,
        "images_modern_format": 0,
        "picture_elements": 0,
        "inline_script_kb": 0,
        "inline_style_kb": 0,
        "has_preconnect": True,
        "has_preload": True,
    }
    mod = PerformanceModule()
    mod.score(analysis)
    blocking_findings = [f for f in mod.findings if "blocking" in f["title"].lower()]
    assert len(blocking_findings) == 1
    assert blocking_findings[0]["priority"] == "P1"


def test_score_lazy_loading_partial():
    analysis = {
        "html_size_kb": 10,
        "render_blocking_scripts": 0,
        "images_total": 4,
        "images_lazy_loaded": 2,
        "images_with_srcset": 0,
        "images_modern_format": 0,
        "picture_elements": 0,
        "inline_script_kb": 0,
        "inline_style_kb": 0,
        "has_preconnect": True,
        "has_preload": True,
    }
    mod = PerformanceModule()
    result = mod.score(analysis)
    assert result["details"]["lazy_loading"]["score"] == 5
