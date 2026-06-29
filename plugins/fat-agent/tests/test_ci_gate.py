"""Tests for ci_gate.py pre-deploy CI gate script."""

import sys
import os
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from ci_gate import check_score, check_priority_findings, build_arg_parser

# --- fixtures ---


def _make_scores(overall=85, findings=None):
    """Build a minimal scored JSON structure."""
    return {
        "overall_score": overall,
        "findings": findings or [],
    }


def _write_scores_file(tmp_path, scores):
    path = os.path.join(tmp_path, "scores.json")
    with open(path, "w") as f:
        json.dump(scores, f)
    return path


# --- check_score tests ---


class TestCheckScore:
    """Test overall score threshold checking."""

    def test_passing_score(self):
        scores = _make_scores(overall=80)
        passed, reason = check_score(scores, threshold=70)
        assert passed is True
        assert reason == ""

    def test_exact_threshold_passes(self):
        scores = _make_scores(overall=70)
        passed, reason = check_score(scores, threshold=70)
        assert passed is True

    def test_failing_score_below_threshold(self):
        scores = _make_scores(overall=55)
        passed, reason = check_score(scores, threshold=70)
        assert passed is False
        assert "55" in reason
        assert "70" in reason

    def test_custom_threshold(self):
        scores = _make_scores(overall=89)
        passed, _ = check_score(scores, threshold=90)
        assert passed is False

    def test_zero_score(self):
        scores = _make_scores(overall=0)
        passed, reason = check_score(scores, threshold=1)
        assert passed is False

    def test_perfect_score(self):
        scores = _make_scores(overall=100)
        passed, _ = check_score(scores, threshold=100)
        assert passed is True


# --- check_priority_findings tests ---


class TestCheckPriorityFindings:
    """Test priority-level finding detection."""

    def test_no_findings_passes(self):
        scores = _make_scores(findings=[])
        passed, found = check_priority_findings(scores, fail_on="P0")
        assert passed is True
        assert found == []

    def test_p0_finding_triggers_failure(self):
        scores = _make_scores(
            findings=[
                {"priority": "P0", "module": "security", "message": "Missing HTTPS"},
                {"priority": "P1", "module": "seo", "message": "No meta desc"},
            ]
        )
        passed, found = check_priority_findings(scores, fail_on="P0")
        assert passed is False
        assert len(found) == 1
        assert found[0]["priority"] == "P0"

    def test_p1_fail_on_catches_p1(self):
        scores = _make_scores(
            findings=[
                {"priority": "P1", "module": "a11y", "message": "Low contrast"},
            ]
        )
        passed, found = check_priority_findings(scores, fail_on="P1")
        assert passed is False
        assert len(found) == 1

    def test_p1_not_caught_by_p0_filter(self):
        scores = _make_scores(
            findings=[
                {"priority": "P1", "module": "seo", "message": "Title too long"},
            ]
        )
        passed, found = check_priority_findings(scores, fail_on="P0")
        assert passed is True
        assert found == []

    def test_multiple_p0_findings(self):
        scores = _make_scores(
            findings=[
                {"priority": "P0", "module": "security", "message": "No HTTPS"},
                {"priority": "P0", "module": "security", "message": "XSS vuln"},
                {"priority": "P2", "module": "perf", "message": "Slow LCP"},
            ]
        )
        passed, found = check_priority_findings(scores, fail_on="P0")
        assert passed is False
        assert len(found) == 2

    def test_no_fail_on_always_passes(self):
        scores = _make_scores(
            findings=[
                {"priority": "P0", "module": "security", "message": "Critical"},
            ]
        )
        passed, found = check_priority_findings(scores, fail_on=None)
        assert passed is True
        assert found == []


# --- arg parser tests ---


class TestArgParser:
    """Test CLI argument parsing."""

    def test_defaults(self):
        parser = build_arg_parser()
        args = parser.parse_args(["--scores", "scores.json"])
        assert args.scores == "scores.json"
        assert args.threshold == 70
        assert args.fail_on is None

    def test_custom_args(self):
        parser = build_arg_parser()
        args = parser.parse_args(
            [
                "--scores",
                "out.json",
                "--threshold",
                "85",
                "--fail-on",
                "P0",
            ]
        )
        assert args.scores == "out.json"
        assert args.threshold == 85
        assert args.fail_on == "P0"


# --- integration / exit code tests ---

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "ci_gate.py")


class TestExitCodes:
    """Test end-to-end exit codes via subprocess."""

    def test_passing_exits_0(self, tmp_path):
        scores = _make_scores(overall=80, findings=[])
        path = _write_scores_file(str(tmp_path), scores)
        result = subprocess.run(
            [sys.executable, SCRIPT, "--scores", path, "--threshold", "70"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["pass"] is True

    def test_low_score_exits_1(self, tmp_path):
        scores = _make_scores(overall=50, findings=[])
        path = _write_scores_file(str(tmp_path), scores)
        result = subprocess.run(
            [sys.executable, SCRIPT, "--scores", path, "--threshold", "70"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert output["pass"] is False
        assert "score" in output["reason"].lower() or "50" in output["reason"]

    def test_p0_findings_exits_2(self, tmp_path):
        scores = _make_scores(
            overall=90,
            findings=[
                {"priority": "P0", "module": "security", "message": "No HSTS"},
            ],
        )
        path = _write_scores_file(str(tmp_path), scores)
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
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
        assert result.returncode == 2
        output = json.loads(result.stdout)
        assert output["pass"] is False
        assert len(output["priority_findings"]) == 1

    def test_both_failures_priority_takes_precedence(self, tmp_path):
        """When both score and priority fail, exit code 2 (priority) wins."""
        scores = _make_scores(
            overall=30,
            findings=[
                {"priority": "P0", "module": "security", "message": "Critical"},
            ],
        )
        path = _write_scores_file(str(tmp_path), scores)
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
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
        assert result.returncode == 2


class TestJSONOutput:
    """Test the JSON summary output format."""

    def test_output_has_required_fields(self, tmp_path):
        scores = _make_scores(overall=75, findings=[])
        path = _write_scores_file(str(tmp_path), scores)
        result = subprocess.run(
            [sys.executable, SCRIPT, "--scores", path, "--threshold", "70"],
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        assert "pass" in output
        assert "score" in output
        assert "threshold" in output
        assert "priority_findings" in output
        assert "reason" in output

    def test_output_types(self, tmp_path):
        scores = _make_scores(overall=75, findings=[])
        path = _write_scores_file(str(tmp_path), scores)
        result = subprocess.run(
            [sys.executable, SCRIPT, "--scores", path, "--threshold", "70"],
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        assert isinstance(output["pass"], bool)
        assert isinstance(output["score"], int)
        assert isinstance(output["threshold"], int)
        assert isinstance(output["priority_findings"], list)
        assert isinstance(output["reason"], str)
