#!/usr/bin/env python3
"""Tests for the v2.9.0 score-composition redesign (calculate-score.py)."""

import importlib.util
import os
import sys

_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "calculate-score.py")
_spec = importlib.util.spec_from_file_location("calc_score", _PATH)
cs = importlib.util.module_from_spec(_spec)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
_spec.loader.exec_module(cs)


class TestBlockingCap:
    def test_p0_caps_grade_at_d(self):
        s = cs.calculate_fat_score(95, 95, 95, 95, findings=[{"priority": "P0"}])
        assert s["score"] <= 59 and s["grade"] in ("D", "F")
        assert s["cap_applied"] and s["blocking"]["p0"] == 1 and s["has_blocking_issue"]

    def test_p1_does_not_cap(self):
        # only a P0 caps now — a P1 alone must NOT force the grade down
        s = cs.calculate_fat_score(98, 98, 98, 98, findings=[{"priority": "P1"}])
        assert s["score"] == 98 and not s["cap_applied"]

    def test_clean_page_not_capped(self):
        s = cs.calculate_fat_score(95, 95, 95, 95, findings=[{"priority": "P3"}])
        assert s["score"] == 95 and not s["cap_applied"]


class TestWeights:
    def test_accessibility_below_seo(self):
        w = cs.calculate_fat_score(0, 0, 100, 0)["weights"]
        assert w["seo"] > w["accessibility"]  # not equal anymore
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_seo_dominant(self):
        # SEO is the heaviest single category
        w = cs.calculate_fat_score(50, 50, 50, 50)["weights"]
        assert w["seo"] == max(w.values())


class TestSecurityRenormalisation:
    def test_unassessed_security_excluded(self):
        # security 0 but not assessed -> excluded, so overall stays high
        s = cs.calculate_fat_score(90, 0, 90, 90, assessed={"security": False})
        assert "security" not in s["assessed_categories"]
        assert s["score"] >= 85  # not dragged down by the absent security 0

    def test_no_headers_security_marked_not_assessed(self):
        r = cs.calculate_security_score({}, {})
        assert r["assessed"] is False

    def test_scores_excludes_security_from_grade_without_headers(self):
        report = {
            "seo": {},
            "accessibility": {},
            "performance": {},
            "security": {},
        }
        out = cs.calculate_scores(report, headers=None)
        assert out["security"]["assessed"] is False
        assert "security" not in out["overall"]["assessed_categories"]


class TestHeuristicLabel:
    def test_performance_labelled_heuristic(self):
        r = cs.calculate_performance_score({})
        assert r["measured"] is False and r["method"] == "html-heuristic"


class TestModuleFolding:
    def test_modules_scored_and_findings_gate_grade(self):
        # a module that emits a P0 must cap the overall grade via calculate_scores
        from modules.technical_seo import TechnicalSEOModule

        analysis = TechnicalSEOModule().analyse(
            "<html></html>", "https://x.example/", headers={"X-Robots-Tag": "noindex"}
        )
        report = {
            "seo": {"title_tag": "T", "h1_count": 1},
            "accessibility": {},
            "performance": {},
            "security": {},
            "modules": {"technical_seo": analysis},
        }
        out = cs.calculate_scores(report, headers={"content-type": "text/html"})
        assert "module_scores" in out and "technical_seo" in out["module_scores"]
        assert out["overall"]["blocking"]["p0"] >= 1
        assert out["overall"]["score"] <= 59  # noindex header can't grade well

    def test_malformed_module_analysis_does_not_crash(self):
        report = {
            "seo": {},
            "accessibility": {},
            "performance": {},
            "security": {},
            "modules": {"technical_seo": {"only": "partial"}},
        }
        out = cs.calculate_scores(report, headers={"x": "y"})  # must not raise
        assert "error" in out["module_scores"]["technical_seo"]


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
