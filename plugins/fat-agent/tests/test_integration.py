"""integration tests for the full fat agent pipeline."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
ANALYSE_SCRIPT = str(SCRIPTS_DIR / "analyse-html.py")
SCORE_SCRIPT = str(SCRIPTS_DIR / "calculate-score.py")
CI_GATE_SCRIPT = str(SCRIPTS_DIR / "ci_gate.py")
REALISTIC_HTML = FIXTURES_DIR / "realistic_site.html"

sys.path.insert(0, str(SCRIPTS_DIR))

from importlib import import_module  # noqa: E402

analyse_mod = import_module("analyse-html")
analyse_html = analyse_mod.analyse_html

score_mod = import_module("calculate-score")
calculate_scores = score_mod.calculate_scores

from modules import CORE_MODULES, detect_modules  # noqa: E402
from profiles import PROFILES, resolve_profile  # noqa: E402


def _write_scores(scores_dict):
    """write a scores dict to a temp file and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(scores_dict, f)
    f.close()
    return f.name


@pytest.fixture
def realistic_html():
    return REALISTIC_HTML.read_text()


@pytest.fixture
def realistic_analysis(realistic_html):
    return analyse_html(realistic_html)


@pytest.fixture
def realistic_scores(realistic_analysis):
    return calculate_scores(realistic_analysis)


class TestAnalyseHTMLSubprocess:
    """run analyse-html.py as a subprocess and validate output."""

    def test_produces_valid_json(self):
        result = subprocess.run(
            [sys.executable, ANALYSE_SCRIPT, str(REALISTIC_HTML)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_output_has_required_sections(self):
        result = subprocess.run(
            [sys.executable, ANALYSE_SCRIPT, str(REALISTIC_HTML)],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        for section in ("seo", "accessibility", "performance", "security", "summary"):
            assert section in data, f"missing section: {section}"

    def test_seo_section_has_core_keys(self):
        result = subprocess.run(
            [sys.executable, ANALYSE_SCRIPT, str(REALISTIC_HTML)],
            capture_output=True,
            text=True,
        )
        seo = json.loads(result.stdout)["seo"]
        for key in (
            "title_tag",
            "title_length",
            "meta_description",
            "h1_count",
            "has_canonical",
            "json_ld_count",
            "og_tags",
        ):
            assert key in seo, f"missing seo key: {key}"


class TestCalculateScoreSubprocess:
    """run calculate-score.py on analyse-html.py output via subprocess."""

    def test_scores_analysis_output(self):
        analyse_result = subprocess.run(
            [sys.executable, ANALYSE_SCRIPT, str(REALISTIC_HTML)],
            capture_output=True,
            text=True,
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(analyse_result.stdout)
            path = f.name
        try:
            score_result = subprocess.run(
                [sys.executable, SCORE_SCRIPT, path],
                capture_output=True,
                text=True,
            )
            assert score_result.returncode == 0, f"stderr: {score_result.stderr}"
            scores = json.loads(score_result.stdout)
            for section in (
                "seo",
                "security",
                "accessibility",
                "performance",
                "overall",
            ):
                assert section in scores
            assert "grade" in scores["overall"]
            assert 0 <= scores["overall"]["score"] <= 100
        finally:
            os.unlink(path)

    def test_pipe_analyse_to_score(self):
        """pipe analyse-html.py stdout into calculate-score.py stdin."""
        analyse = subprocess.run(
            [sys.executable, ANALYSE_SCRIPT, str(REALISTIC_HTML)],
            capture_output=True,
            text=True,
        )
        assert analyse.returncode == 0
        score_result = subprocess.run(
            [sys.executable, SCORE_SCRIPT],
            input=analyse.stdout,
            capture_output=True,
            text=True,
        )
        assert score_result.returncode == 0, f"stderr: {score_result.stderr}"
        scores = json.loads(score_result.stdout)
        assert 0 <= scores["overall"]["score"] <= 100


class TestModuleSystemEndToEnd:
    """test that the module system works with realistic html."""

    def test_detect_core_modules(self, realistic_html):
        modules = detect_modules(realistic_html)
        for mod in CORE_MODULES:
            assert mod in modules

    def test_local_seo_detected(self, realistic_html):
        modules = detect_modules(realistic_html)
        assert "local_seo" in modules

    def test_email_deliverability_detected(self, realistic_html):
        modules = detect_modules(realistic_html)
        assert "email_deliverability" in modules

    def test_all_score_categories_present(self, realistic_scores):
        for cat in ("seo", "security", "accessibility", "performance"):
            assert realistic_scores[cat]["score"] >= 0
        assert realistic_scores["overall"]["grade"] in ("A", "B", "C", "D", "F")

    def test_scores_reasonably(self, realistic_scores):
        assert realistic_scores["overall"]["score"] >= 50

    def test_structured_data_extracted(self, realistic_analysis):
        assert realistic_analysis["seo"]["json_ld_count"] >= 2
        assert "LocalBusiness" in realistic_analysis["seo"]["json_ld_types"]


class TestProfileIntegration:
    """test profile resolution with module detection."""

    def test_quick_profile(self):
        modules = resolve_profile("quick")
        assert "seo" in modules
        assert "security" in modules
        assert len(modules) <= 5

    def test_seo_subset_of_full(self):
        full = resolve_profile("full")
        for mod in resolve_profile("seo"):
            assert mod in full

    def test_ecommerce_profile(self):
        assert "ecommerce" in resolve_profile("ecommerce")

    def test_local_profile(self):
        assert "local_seo" in resolve_profile("local")

    def test_unknown_falls_back_to_full(self):
        assert resolve_profile("nonexistent_xyz") == PROFILES["full"]

    def test_profile_filters_detected(self, realistic_html):
        detected = set(detect_modules(realistic_html))
        profile_mods = set(resolve_profile("quick"))
        filtered = detected & profile_mods
        assert "seo" in filtered
        assert "security" in filtered


class TestCIGateIntegration:
    """test ci_gate.py with scored output."""

    def test_passing_exits_0(self, realistic_scores):
        path = _write_scores(
            {"overall_score": realistic_scores["overall"]["score"], "findings": []}
        )
        try:
            r = subprocess.run(
                [sys.executable, CI_GATE_SCRIPT, "--scores", path, "--threshold", "30"],
                capture_output=True,
                text=True,
            )
            assert r.returncode == 0
            assert json.loads(r.stdout)["pass"] is True
        finally:
            os.unlink(path)

    def test_failing_exits_1(self):
        path = _write_scores({"overall_score": 20, "findings": []})
        try:
            r = subprocess.run(
                [sys.executable, CI_GATE_SCRIPT, "--scores", path, "--threshold", "70"],
                capture_output=True,
                text=True,
            )
            assert r.returncode == 1
            assert json.loads(r.stdout)["pass"] is False
        finally:
            os.unlink(path)

    def test_p0_exits_2(self):
        path = _write_scores(
            {
                "overall_score": 90,
                "findings": [
                    {"priority": "P0", "module": "security", "message": "No HTTPS"}
                ],
            }
        )
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    CI_GATE_SCRIPT,
                    "--scores",
                    path,
                    "--threshold",
                    "70",
                    "--fail-on",
                    "P0",
                ],
                capture_output=True,
                text=True,
            )
            assert r.returncode == 2
            out = json.loads(r.stdout)
            assert out["pass"] is False
            assert len(out["priority_findings"]) == 1
        finally:
            os.unlink(path)

    def test_p1_not_caught_by_p0(self):
        path = _write_scores(
            {
                "overall_score": 90,
                "findings": [
                    {"priority": "P1", "module": "seo", "message": "Title too long"}
                ],
            }
        )
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    CI_GATE_SCRIPT,
                    "--scores",
                    path,
                    "--threshold",
                    "70",
                    "--fail-on",
                    "P0",
                ],
                capture_output=True,
                text=True,
            )
            assert r.returncode == 0
        finally:
            os.unlink(path)


class TestFullPipeline:
    """html file -> analyse -> score -> ci gate end-to-end."""

    def test_html_to_verdict(self):
        analyse_r = subprocess.run(
            [sys.executable, ANALYSE_SCRIPT, str(REALISTIC_HTML)],
            capture_output=True,
            text=True,
        )
        assert analyse_r.returncode == 0
        analysis = json.loads(analyse_r.stdout)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(analysis, f)
            analysis_path = f.name

        try:
            score_r = subprocess.run(
                [sys.executable, SCORE_SCRIPT, analysis_path],
                capture_output=True,
                text=True,
            )
            assert score_r.returncode == 0
            scores = json.loads(score_r.stdout)

            gate_input = {
                "overall_score": scores["overall"]["score"],
                "findings": [],
            }
            gate_path = _write_scores(gate_input)
            try:
                gate_r = subprocess.run(
                    [
                        sys.executable,
                        CI_GATE_SCRIPT,
                        "--scores",
                        gate_path,
                        "--threshold",
                        "30",
                    ],
                    capture_output=True,
                    text=True,
                )
                assert gate_r.returncode == 0
                verdict = json.loads(gate_r.stdout)
                assert verdict["pass"] is True
                assert verdict["score"] >= 30
            finally:
                os.unlink(gate_path)
        finally:
            os.unlink(analysis_path)
