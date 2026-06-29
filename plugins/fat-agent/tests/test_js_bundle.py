import os
import sys

# add the scripts directory to sys.path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.js_bundle import JSBundleModule

# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------


def test_detect_true_when_script_tags_present():
    html = '<html><body><script src="app.js"></script></body></html>'
    assert JSBundleModule.detect(html) is True


def test_detect_true_when_inline_script_present():
    html = "<html><body><script>console.log('hi');</script></body></html>"
    assert JSBundleModule.detect(html) is True


def test_detect_false_when_no_scripts():
    html = "<html><body><h1>Hello</h1></body></html>"
    assert JSBundleModule.detect(html) is False


def test_detect_false_for_empty_html():
    assert JSBundleModule.detect("") is False


# ---------------------------------------------------------------------------
# analyse() tests
# ---------------------------------------------------------------------------


def test_analyse_counts_external_scripts():
    html = """<html><head>
    <script src="/js/app.js"></script>
    <script src="/js/vendor.js"></script>
    <script src="https://cdn.example.com/lib.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert result["external_script_count"] == 3


def test_analyse_detects_heavy_libraries():
    html = """<html><head>
    <script src="https://cdn.jsdelivr.net/npm/moment@2.29.4/moment.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/lodash/lodash.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5/dist/js/bootstrap.min.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert "moment" in result["heavy_libraries"]
    assert "lodash" in result["heavy_libraries"]
    assert "jquery" in result["heavy_libraries"]
    assert "bootstrap.js" in result["heavy_libraries"]


def test_analyse_no_heavy_libraries_for_clean_page():
    html = """<html><head>
    <script src="/js/app.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert result["heavy_libraries"] == []


def test_analyse_lodash_submodule_not_flagged():
    """lodash-es should not be flagged as full lodash."""
    html = """<html><head>
    <script src="https://cdn.example.com/lodash-es.min.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert "lodash" not in result["heavy_libraries"]


def test_analyse_inline_script_size():
    inline_code = "x" * 5000
    html = f"<html><body><script>{inline_code}</script><script>var y = 1;</script></body></html>"
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert result["inline_script_total_chars"] == 5000 + len("var y = 1;")


def test_analyse_detects_webpack_chunks():
    html = """<html><head>
    <script src="/static/js/main.a1b2c3d4.chunk.js"></script>
    <script src="/static/js/vendors~main.abc123.chunk.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert "webpack" in result["bundler_detected"]


def test_analyse_detects_vite_chunks():
    html = """<html><head>
    <script type="module" src="/assets/index-BxKm3a4f.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert "vite" in result["bundler_detected"]


def test_analyse_detects_parcel():
    html = """<html><head>
    <script src="/index.abc12345.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert "parcel" in result["bundler_detected"]


def test_analyse_async_defer_detection():
    html = """<html><head>
    <script src="a.js" async></script>
    <script src="b.js" defer></script>
    <script src="c.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert result["scripts_with_async_or_defer"] == 2
    assert result["scripts_without_async_or_defer"] == 1


def test_analyse_module_type_scripts():
    html = """<html><head>
    <script type="module" src="app.js"></script>
    <script src="legacy.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert result["module_script_count"] == 1


def test_analyse_no_external_scripts():
    html = "<html><body><script>var x = 1;</script></body></html>"
    mod = JSBundleModule()
    result = mod.analyse(html)
    assert result["external_script_count"] == 0


# ---------------------------------------------------------------------------
# score() tests
# ---------------------------------------------------------------------------


def test_score_perfect():
    """A clean modern page with few scripts, async/defer, modules, bundler."""
    html = """<html><head>
    <script type="module" src="/assets/index-BxKm3a4f.js" async></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    analysis = mod.analyse(html)
    score = mod.score(analysis)
    assert score["total"] == 100


def test_score_heavy_libraries_penalty():
    html = """<html><head>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js" defer></script>
    <script type="module" src="/assets/index-abc123.js" defer></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    analysis = mod.analyse(html)
    score = mod.score(analysis)
    assert score["no_heavy_libraries"] == 0
    assert score["total"] < 100


def test_score_too_many_scripts():
    scripts = "\n".join(
        f'<script src="/js/chunk{i}.js" defer></script>' for i in range(20)
    )
    html = f"<html><head>{scripts}</head><body></body></html>"
    mod = JSBundleModule()
    analysis = mod.analyse(html)
    score = mod.score(analysis)
    assert score["reasonable_script_count"] == 0


def test_score_large_inline_script_penalty():
    inline_code = "x" * 15000
    html = f"""<html><head>
    <script type="module" src="/assets/app-abc123.js" async></script>
    </head><body><script>{inline_code}</script></body></html>"""
    mod = JSBundleModule()
    analysis = mod.analyse(html)
    score = mod.score(analysis)
    assert score["no_large_inline_scripts"] == 0


def test_score_no_async_defer_penalty():
    html = """<html><head>
    <script src="a.js"></script>
    <script src="b.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    analysis = mod.analyse(html)
    score = mod.score(analysis)
    assert score["scripts_have_async_or_defer"] == 0


def test_score_no_module_scripts():
    html = """<html><head>
    <script src="a.js" async></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    analysis = mod.analyse(html)
    score = mod.score(analysis)
    assert score["uses_modern_modules"] == 0


def test_score_findings_generated_for_heavy_libs():
    html = """<html><head>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    analysis = mod.analyse(html)
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any("heavy" in t.lower() or "library" in t.lower() for t in titles)


def test_score_findings_generated_for_no_async_defer():
    html = """<html><head>
    <script src="a.js"></script>
    <script src="b.js"></script>
    </head><body></body></html>"""
    mod = JSBundleModule()
    analysis = mod.analyse(html)
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any("async" in t.lower() or "defer" in t.lower() for t in titles)
