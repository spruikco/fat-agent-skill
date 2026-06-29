import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from pathlib import Path

from modules.i18n import I18nModule

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


def _make_module():
    return I18nModule()


# --- analyse() ---


def test_analyse_extracts_hreflang_tags():
    mod = _make_module()
    result = mod.analyse(_read("i18n.html"), url="https://example.com/en/")
    assert len(result["hreflang_tags"]) == 3
    langs = [t["lang"] for t in result["hreflang_tags"]]
    assert "en" in langs
    assert "de" in langs
    assert "x-default" in langs


def test_analyse_detects_x_default():
    mod = _make_module()
    result = mod.analyse(_read("i18n.html"), url="https://example.com/en/")
    assert result["has_x_default"] is True


def test_analyse_detects_self_referencing():
    mod = _make_module()
    result = mod.analyse(_read("i18n.html"), url="https://example.com/en/")
    assert result["self_referencing_hreflang"] is True


def test_analyse_no_self_referencing_when_url_mismatch():
    mod = _make_module()
    result = mod.analyse(_read("i18n.html"), url="https://example.com/fr/")
    assert result["self_referencing_hreflang"] is False


def test_analyse_detects_lang_attribute():
    mod = _make_module()
    result = mod.analyse(_read("i18n.html"), url="https://example.com/en/")
    assert result["has_lang_attribute"] is True
    assert result["lang_attribute"] == "en"


def test_analyse_detects_content_language_header():
    mod = _make_module()
    result = mod.analyse(
        _read("i18n.html"),
        url="https://example.com/en/",
        headers={"Content-Language": "en"},
    )
    assert result["has_content_language_header"] is True
    assert result["content_language"] == "en"


def test_analyse_no_content_language_header():
    mod = _make_module()
    result = mod.analyse(_read("i18n.html"), url="https://example.com/en/")
    assert result["has_content_language_header"] is False


def test_analyse_validates_language_codes():
    mod = _make_module()
    result = mod.analyse(_read("i18n.html"), url="https://example.com/en/")
    assert result["valid_language_codes"] is True
    assert result["invalid_codes"] == []


def test_analyse_detects_locale_patterns():
    mod = _make_module()
    result = mod.analyse(_read("i18n.html"), url="https://example.com/en/")
    locales = result["locale_patterns"]
    assert "en" in locales
    assert "de" in locales


def test_analyse_rtl_support_not_present():
    mod = _make_module()
    result = mod.analyse(_read("i18n.html"), url="https://example.com/en/")
    assert result["has_rtl_support"] is False


def test_analyse_no_lang_attribute():
    html = "<html><head></head><body></body></html>"
    mod = _make_module()
    result = mod.analyse(html, url="https://example.com/")
    assert result["has_lang_attribute"] is False
    assert result["lang_attribute"] is None


def test_analyse_rtl_detection():
    html = '<html lang="ar" dir="rtl"><head></head><body></body></html>'
    mod = _make_module()
    result = mod.analyse(html, url="https://example.com/")
    assert result["has_rtl_support"] is True
    assert result["rtl_language_detected"] is True


def test_analyse_rtl_language_without_dir_attribute():
    html = '<html lang="ar"><head></head><body></body></html>'
    mod = _make_module()
    result = mod.analyse(html, url="https://example.com/")
    assert result["rtl_language_detected"] is True
    assert result["has_rtl_support"] is False


def test_analyse_invalid_language_code():
    html = """<html lang="en"><head>
    <link rel="alternate" hreflang="zzzz" href="https://example.com/zzzz/">
    </head><body></body></html>"""
    mod = _make_module()
    result = mod.analyse(html, url="https://example.com/")
    assert result["valid_language_codes"] is False
    assert "zzzz" in result["invalid_codes"]


# --- score() ---


def test_score_perfect_i18n_fixture():
    mod = _make_module()
    analysis = mod.analyse(
        _read("i18n.html"),
        url="https://example.com/en/",
        headers={"Content-Language": "en"},
    )
    score_result = mod.score(analysis)
    # has_lang_attribute: 20, hreflang_tags_present: 20, has_x_default: 15,
    # self_referencing_hreflang: 15, valid_language_codes: 10,
    # has_content_language_header: 10 = 90
    # rtl_support is N/A (no RTL lang), so not deducted
    assert score_result["total"] == 90


def test_score_no_i18n():
    html = "<html><head></head><body></body></html>"
    mod = _make_module()
    analysis = mod.analyse(html, url="https://example.com/")
    score_result = mod.score(analysis)
    assert score_result["total"] == 0


def test_score_lang_attribute_only():
    html = "<html lang='en'><head></head><body></body></html>"
    mod = _make_module()
    analysis = mod.analyse(html, url="https://example.com/")
    score_result = mod.score(analysis)
    assert score_result["total"] == 20


def test_score_rtl_language_with_support():
    html = """<html lang="ar" dir="rtl"><head>
    <link rel="alternate" hreflang="ar" href="https://example.com/ar/">
    <link rel="alternate" hreflang="x-default" href="https://example.com/">
    </head><body></body></html>"""
    mod = _make_module()
    analysis = mod.analyse(
        html,
        url="https://example.com/ar/",
        headers={"Content-Language": "ar"},
    )
    score_result = mod.score(analysis)
    # lang_attr: 20, hreflang_present: 20, x_default: 15,
    # self_ref: 15, valid_codes: 10, content_lang: 10, rtl: 10 = 100
    assert score_result["total"] == 100


def test_score_rtl_language_without_support():
    html = """<html lang="ar"><head>
    <link rel="alternate" hreflang="ar" href="https://example.com/ar/">
    <link rel="alternate" hreflang="x-default" href="https://example.com/">
    </head><body></body></html>"""
    mod = _make_module()
    analysis = mod.analyse(
        html,
        url="https://example.com/ar/",
        headers={"Content-Language": "ar"},
    )
    score_result = mod.score(analysis)
    # lang_attr: 20, hreflang_present: 20, x_default: 15,
    # self_ref: 15, valid_codes: 10, content_lang: 10, rtl: 0 = 90
    assert score_result["total"] == 90


def test_score_breakdown_keys():
    mod = _make_module()
    analysis = mod.analyse(_read("i18n.html"), url="https://example.com/en/")
    score_result = mod.score(analysis)
    assert "breakdown" in score_result
    breakdown = score_result["breakdown"]
    assert "has_lang_attribute" in breakdown
    assert "hreflang_tags_present" in breakdown
    assert "has_x_default" in breakdown
    assert "self_referencing_hreflang" in breakdown
    assert "valid_language_codes" in breakdown
    assert "has_content_language_header" in breakdown


# --- findings ---


def test_findings_missing_lang_attribute():
    html = "<html><head></head><body></body></html>"
    mod = _make_module()
    analysis = mod.analyse(html, url="https://example.com/")
    mod.score(analysis)
    priorities = [f["priority"] for f in mod.findings]
    assert "P1" in priorities


def test_findings_missing_x_default():
    html = """<html lang="en"><head>
    <link rel="alternate" hreflang="en" href="https://example.com/en/">
    </head><body></body></html>"""
    mod = _make_module()
    analysis = mod.analyse(html, url="https://example.com/en/")
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any("x-default" in t.lower() for t in titles)


def test_findings_rtl_missing():
    html = '<html lang="ar"><head></head><body></body></html>'
    mod = _make_module()
    analysis = mod.analyse(html, url="https://example.com/")
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any("rtl" in t.lower() for t in titles)


# --- detect() ---


def test_detect_positive():
    assert I18nModule.detect(_read("i18n.html")) is True


def test_detect_negative():
    html = "<html><head></head><body>No i18n here</body></html>"
    assert I18nModule.detect(html) is False


# --- module metadata ---


def test_module_id():
    assert I18nModule.MODULE_ID == "i18n"


def test_display_name():
    assert I18nModule.DISPLAY_NAME == "Internationalisation"
