"""ported critical-path tests for calculate-score.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from importlib import import_module

score_mod = import_module("calculate-score")
calculate_scores = score_mod.calculate_scores
calculate_seo_score = score_mod.calculate_seo_score
calculate_security_score = score_mod.calculate_security_score
calculate_accessibility_score = score_mod.calculate_accessibility_score
calculate_performance_score = score_mod.calculate_performance_score
calculate_fat_score = score_mod.calculate_fat_score

analyse_mod = import_module("analyse-html")
analyse_html = analyse_mod.analyse_html

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def realistic_scores():
    html = (FIXTURES_DIR / "realistic_site.html").read_text()
    report = analyse_html(html)
    return calculate_scores(report)


class TestScoreRanges:
    """all category scores must be in 0-100 range."""

    def test_seo_in_range(self, realistic_scores):
        assert 0 <= realistic_scores["seo"]["score"] <= 100

    def test_security_in_range(self, realistic_scores):
        assert 0 <= realistic_scores["security"]["score"] <= 100

    def test_accessibility_in_range(self, realistic_scores):
        assert 0 <= realistic_scores["accessibility"]["score"] <= 100

    def test_performance_in_range(self, realistic_scores):
        assert 0 <= realistic_scores["performance"]["score"] <= 100

    def test_overall_in_range(self, realistic_scores):
        assert 0 <= realistic_scores["overall"]["score"] <= 100


class TestGradeAssignment:
    """verify grade boundaries are correct."""

    def test_grade_a(self):
        s = calculate_fat_score(95, 95, 95, 95)
        assert s["grade"] == "A"
        assert s["score"] >= 90

    def test_grade_b(self):
        s = calculate_fat_score(80, 75, 75, 75)
        assert s["grade"] == "B"

    def test_grade_c(self):
        s = calculate_fat_score(65, 60, 60, 60)
        assert s["grade"] == "C"

    def test_grade_d(self):
        s = calculate_fat_score(50, 30, 50, 40)
        assert s["grade"] == "D"

    def test_grade_f(self):
        s = calculate_fat_score(20, 0, 30, 10)
        assert s["grade"] == "F"

    def test_perfect_is_100_a(self):
        s = calculate_fat_score(100, 100, 100, 100)
        assert s["score"] == 100
        assert s["grade"] == "A"

    def test_weights_sum_to_1(self):
        s = calculate_fat_score(100, 100, 100, 100)
        assert abs(sum(s["weights"].values()) - 1.0) < 0.001

    def test_three_category_fallback(self):
        s = calculate_fat_score(100, 100, 100)
        assert s["score"] == 100
        assert "performance" not in s["weights"]
        assert abs(sum(s["weights"].values()) - 1.0) < 0.001


class TestSecurityScoring:
    """verify security score calculation."""

    def test_no_headers_gives_html_only_scores(self):
        html_sec = {
            "has_mixed_content": False,
            "external_links_total": 0,
            "external_links_without_noopener": 0,
        }
        s = calculate_security_score({}, html_sec)
        assert s["details"]["mixed_content"]["score"] == 10
        assert s["details"]["link_safety"]["score"] == 5
        assert s["score"] == 15

    def test_mixed_content_penalty(self):
        s = calculate_security_score({}, {"has_mixed_content": True})
        assert s["details"]["mixed_content"]["score"] == 0

    def test_noopener_penalty(self):
        html_sec = {
            "external_links_total": 4,
            "external_links_without_noopener": 4,
        }
        s = calculate_security_score({}, html_sec)
        assert s["details"]["link_safety"]["score"] == 0

    def test_perfect_headers_score_100(self):
        headers = {
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": (
                "max-age=31536000; includeSubDomains; preload"
            ),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=()",
        }
        html_sec = {
            "has_mixed_content": False,
            "external_links_total": 0,
            "external_links_without_noopener": 0,
        }
        s = calculate_security_score(headers, html_sec)
        assert s["score"] == 100

    def test_partial_hsts(self):
        full = calculate_security_score(
            {
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload"
            }
        )
        partial = calculate_security_score(
            {"Strict-Transport-Security": "max-age=31536000"}
        )
        assert full["details"]["hsts"]["score"] == 18
        assert partial["details"]["hsts"]["score"] == 8

    def test_csp_report_only_partial(self):
        s = calculate_security_score(
            {"Content-Security-Policy-Report-Only": "default-src 'self'"}
        )
        assert s["details"]["csp"]["score"] == 13

    def test_frame_ancestors_counts_as_xfo(self):
        s = calculate_security_score(
            {"Content-Security-Policy": "frame-ancestors 'none'"}
        )
        assert s["details"]["x_frame_options"]["score"] == 8


class TestSEOScoring:
    """verify seo score calculation details."""

    def test_title_length_tiers(self):
        perfect = calculate_seo_score({"title_tag": "A" * 55, "title_length": 55}, {})
        ok = calculate_seo_score({"title_tag": "A" * 35, "title_length": 35}, {})
        short = calculate_seo_score({"title_tag": "A", "title_length": 1}, {})
        assert (
            perfect["details"]["title_meta"]["score"]
            > ok["details"]["title_meta"]["score"]
            > short["details"]["title_meta"]["score"]
        )

    def test_duplicate_title_penalty(self):
        clean = calculate_seo_score(
            {"title_tag": "A" * 55, "title_length": 55, "duplicate_title_tags": 1}, {}
        )
        dup = calculate_seo_score(
            {"title_tag": "A" * 55, "title_length": 55, "duplicate_title_tags": 2}, {}
        )
        assert (
            clean["details"]["title_meta"]["score"]
            > dup["details"]["title_meta"]["score"]
        )

    def test_structured_data_tiers(self):
        two = calculate_seo_score({"json_ld_count": 2}, {})
        one = calculate_seo_score({"json_ld_count": 1}, {})
        none = calculate_seo_score({"json_ld_count": 0}, {})
        assert (
            two["details"]["structured_data"]["score"]
            > one["details"]["structured_data"]["score"]
            > none["details"]["structured_data"]["score"]
        )

    def test_full_og_tags_score(self):
        seo = {
            "og_tags": {
                "og:title": "T",
                "og:description": "D",
                "og:image": "I",
                "og:url": "U",
            },
            "twitter_tags": {"twitter:card": "summary"},
        }
        s = calculate_seo_score(seo, {})
        assert s["details"]["social"]["score"] == 10


class TestAccessibilityScoring:
    """verify accessibility score calculation."""

    def test_no_images_full_score(self):
        s = calculate_accessibility_score({"img_total": 0, "img_missing_alt": 0})
        assert s["details"]["images_alt"]["score"] == 18

    def test_all_images_alt_full_score(self):
        s = calculate_accessibility_score({"img_total": 5, "img_missing_alt": 0})
        assert s["details"]["images_alt"]["score"] == 18

    def test_skip_link_scoring(self):
        with_skip = calculate_accessibility_score({"has_skip_link": True})
        without = calculate_accessibility_score({"has_skip_link": False})
        assert with_skip["details"]["skip_navigation"]["score"] == 5
        assert without["details"]["skip_navigation"]["score"] == 0

    def test_landmarks_scoring(self):
        full = calculate_accessibility_score(
            {"landmarks_found": ["main", "nav", "header", "footer"]}
        )
        assert full["details"]["landmarks"]["score"] == 10

    def test_empty_headings_penalty(self):
        clean = calculate_accessibility_score({"empty_headings": 0})
        dirty = calculate_accessibility_score({"empty_headings": 3})
        clean_total = (
            clean["details"]["heading_structure"]["score"]
            + clean["details"]["empty_headings"]["score"]
        )
        dirty_total = (
            dirty["details"]["heading_structure"]["score"]
            + dirty["details"]["empty_headings"]["score"]
        )
        assert clean_total > dirty_total


class TestPerformanceScoring:
    """verify performance score calculation."""

    def test_no_images_full_image_score(self):
        s = calculate_performance_score({"images_total": 0})
        assert s["details"]["image_optimisation"]["score"] == 20

    def test_render_blocking_tiers(self):
        clean = calculate_performance_score({"render_blocking_scripts": 0})
        heavy = calculate_performance_score({"render_blocking_scripts": 5})
        assert clean["details"]["render_blocking"]["score"] == 15
        assert heavy["details"]["render_blocking"]["score"] == 0

    def test_font_loading_full_score(self):
        s = calculate_performance_score(
            {
                "has_font_display_swap": True,
                "has_google_fonts_preconnect": True,
                "font_preloads": 1,
            }
        )
        assert s["details"]["font_loading"]["score"] == 15

    def test_no_font_signals_partial(self):
        s = calculate_performance_score(
            {
                "has_font_display_swap": False,
                "has_google_fonts_preconnect": False,
                "font_preloads": 0,
            }
        )
        assert s["details"]["font_loading"]["score"] == 5
