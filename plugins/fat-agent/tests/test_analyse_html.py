"""ported critical-path tests for analyse-html.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from importlib import import_module

analyse_mod = import_module("analyse-html")
analyse_html = analyse_mod.analyse_html

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def realistic_report():
    html = (FIXTURES_DIR / "realistic_site.html").read_text()
    return analyse_html(html)


MINIMAL_HTML = """\
<!DOCTYPE html>
<html>
<head></head>
<body></body>
</html>
"""

BROKEN_HTML = """\
<!DOCTYPE html>
<html>
<head>
    <script src="/js/blocking.js"></script>
</head>
<body>
    <div>
        <h2>Welcome</h2>
        <h4>Skipped h3</h4>
        <img src="hero.jpg">
        <form>
            <input type="text" name="email">
            <select name="country"></select>
        </form>
    </div>
</body>
</html>
"""

SPA_NEXTJS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>My Next.js App - Home Page Title Here Now</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>
</head>
<body>
    <div id="__next">
        <main><p>Loading...</p></main>
    </div>
</body>
</html>
"""

SPA_REACT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>React App With Good Title Length Here Now</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <div id="root" data-reactroot>
        <main><p>Loading...</p></main>
    </div>
</body>
</html>
"""


class TestOutputKeys:
    """verify analyse-html.py produces expected top-level keys."""

    def test_has_seo_section(self, realistic_report):
        assert "seo" in realistic_report

    def test_has_accessibility_section(self, realistic_report):
        assert "accessibility" in realistic_report

    def test_has_performance_section(self, realistic_report):
        assert "performance" in realistic_report

    def test_has_security_section(self, realistic_report):
        assert "security" in realistic_report

    def test_has_summary_section(self, realistic_report):
        assert "summary" in realistic_report

    def test_has_analytics_section(self, realistic_report):
        assert "analytics" in realistic_report

    def test_has_pwa_section(self, realistic_report):
        assert "pwa" in realistic_report

    def test_has_privacy_section(self, realistic_report):
        assert "privacy" in realistic_report


class TestSEOKeys:
    """verify seo section has all expected keys."""

    def test_title_tag(self, realistic_report):
        seo = realistic_report["seo"]
        assert seo["title_tag"] is not None
        assert seo["title_length"] > 0

    def test_meta_description(self, realistic_report):
        seo = realistic_report["seo"]
        assert seo["meta_description"] is not None
        assert seo["meta_description_length"] > 0

    def test_h1_count(self, realistic_report):
        assert realistic_report["seo"]["h1_count"] == 1

    def test_heading_hierarchy(self, realistic_report):
        hierarchy = realistic_report["seo"]["heading_hierarchy"]
        assert hierarchy[0] == 1

    def test_canonical(self, realistic_report):
        assert realistic_report["seo"]["has_canonical"] is True

    def test_json_ld(self, realistic_report):
        assert realistic_report["seo"]["json_ld_count"] >= 2

    def test_og_tags(self, realistic_report):
        og = realistic_report["seo"]["og_tags"]
        assert "og:title" in og
        assert "og:image" in og

    def test_twitter_tags(self, realistic_report):
        assert "twitter:card" in realistic_report["seo"]["twitter_tags"]

    def test_hreflang(self, realistic_report):
        tags = realistic_report["seo"]["hreflang_tags"]
        assert len(tags) >= 2

    def test_charset(self, realistic_report):
        assert realistic_report["seo"]["has_charset"] is True

    def test_viewport_valid(self, realistic_report):
        assert realistic_report["seo"]["viewport_valid"] is True

    def test_favicon(self, realistic_report):
        assert realistic_report["seo"]["has_favicon"] is True


class TestMinimalHTML:
    """verify empty/minimal html flags all critical issues."""

    def test_missing_title(self):
        r = analyse_html(MINIMAL_HTML)
        assert r["seo"]["title_tag"] is None
        assert "Missing <title> tag" in r["summary"]["critical"]

    def test_missing_h1(self):
        r = analyse_html(MINIMAL_HTML)
        assert r["seo"]["h1_count"] == 0
        assert "No <h1> tag found" in r["summary"]["critical"]

    def test_missing_lang(self):
        r = analyse_html(MINIMAL_HTML)
        assert r["accessibility"]["has_lang_attribute"] is False
        assert "Missing <html lang> attribute" in r["summary"]["critical"]

    def test_missing_meta_desc(self):
        r = analyse_html(MINIMAL_HTML)
        assert "Missing meta description" in r["summary"]["high"]

    def test_missing_canonical(self):
        r = analyse_html(MINIMAL_HTML)
        assert "Missing canonical URL" in r["summary"]["high"]


class TestBrokenHTML:
    """verify broken html detects issues correctly."""

    def test_no_h1(self):
        r = analyse_html(BROKEN_HTML)
        assert r["seo"]["h1_count"] == 0

    def test_skipped_hierarchy(self):
        r = analyse_html(BROKEN_HTML)
        assert r["seo"]["heading_hierarchy"] == [2, 4]

    def test_images_missing_alt(self):
        r = analyse_html(BROKEN_HTML)
        assert r["accessibility"]["img_missing_alt"] >= 1

    def test_form_inputs_without_labels(self):
        r = analyse_html(BROKEN_HTML)
        assert r["accessibility"]["form_inputs_without_label"] >= 1

    def test_hidden_form_inputs_excluded(self):
        """Inputs inside a hidden container (framework detection forms) are
        not exposed to assistive tech and must not count as unlabelled."""
        html = (
            "<!DOCTYPE html><html lang='en'><body>"
            "<form name='detect' data-netlify='true' hidden>"
            "<input type='text' name='a'><input type='email' name='b'>"
            "<textarea name='c'></textarea></form>"
            "<form><input type='text' aria-label='Name'></form>"
            "</body></html>"
        )
        r = analyse_html(html)
        assert r["accessibility"]["form_inputs_total"] == 1
        assert r["accessibility"]["form_inputs_without_label"] == 0

    def test_visible_input_after_hidden_block_still_counts(self):
        """The hidden marker must clear on close — a later visible unlabelled
        input is still flagged."""
        html = (
            "<!DOCTYPE html><html lang='en'><body>"
            "<div hidden><input type='text' name='x'></div>"
            "<form><input type='text' name='y'></form>"
            "</body></html>"
        )
        r = analyse_html(html)
        assert r["accessibility"]["form_inputs_without_label"] == 1

    def test_render_blocking_scripts(self):
        r = analyse_html(BROKEN_HTML)
        assert r["performance"]["render_blocking_scripts"] >= 1


class TestSPADetection:
    """verify spa framework detection works."""

    def test_nextjs_detected(self):
        r = analyse_html(SPA_NEXTJS_HTML)
        assert r["seo"]["spa_detected"] is True
        assert "Next.js" in r["seo"]["spa_indicators"]

    def test_react_detected(self):
        r = analyse_html(SPA_REACT_HTML)
        assert r["seo"]["spa_detected"] is True
        assert "React" in r["seo"]["spa_indicators"]

    def test_static_html_not_spa(self, realistic_report):
        assert realistic_report["seo"]["spa_detected"] is False

    def test_spa_missing_h1_not_critical(self):
        """spa with missing h1 should be high not critical."""
        r = analyse_html(SPA_NEXTJS_HTML)
        assert r["seo"]["h1_count"] == 0
        critical_h1 = [i for i in r["summary"]["critical"] if "h1" in i.lower()]
        assert len(critical_h1) == 0
        high_h1 = [i for i in r["summary"]["high"] if "No <h1>" in i]
        assert len(high_h1) == 1
