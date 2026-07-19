"""Tests for punchlist.py — persistent, compaction-safe punch list."""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from importlib import import_module

from punchlist import (
    extract_findings,
    find_item,
    finding_id,
    format_status,
    load_punchlist,
    save_punchlist,
    scanned_modules,
    update_punchlist,
)

score_mod = import_module("calculate-score")

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "punchlist.py")


def _finding(
    module="technical_seo", title="Meta-refresh redirect in use", priority="P2"
):
    return {
        "module": module,
        "priority": priority,
        "title": title,
        "description": "desc",
        "fix": "fix it",
        "effort": "low",
    }


def _scores(findings=None, module_scores=None, security_assessed=True):
    scores = {
        "findings": findings if findings is not None else [],
        "security": {"score": 50, "assessed": security_assessed},
        "summary": {},
    }
    if module_scores is not None:
        scores["module_scores"] = module_scores
    return scores


def _fresh():
    return {"version": 1, "url": "", "updated": "", "items": []}


class TestFindingId:
    def test_stable(self):
        assert finding_id("seo", "Missing title") == finding_id("seo", "Missing title")

    def test_module_distinguishes(self):
        assert finding_id("seo", "Missing title") != finding_id("a11y", "Missing title")

    def test_empty_module_is_core(self):
        assert finding_id("", "Thing") == finding_id("core", "Thing")


class TestExtractFindings:
    def test_flat_findings(self):
        out = extract_findings(_scores(findings=[_finding()]))
        assert len(out) == 1
        assert out[0]["title"] == "Meta-refresh redirect in use"
        assert out[0]["id"] == finding_id(
            "technical_seo", "Meta-refresh redirect in use"
        )

    def test_summary_bucket_fallback(self):
        scores = {
            "summary": {"critical": ["No HTTPS"], "high": [], "medium": ["Small thing"]}
        }
        out = extract_findings(scores)
        priorities = {f["title"]: f["priority"] for f in out}
        assert priorities == {"No HTTPS": "P0", "Small thing": "P2"}

    def test_dedupes_by_id(self):
        out = extract_findings(_scores(findings=[_finding(), _finding()]))
        assert len(out) == 1

    def test_skips_untitled(self):
        out = extract_findings(_scores(findings=[{"module": "seo", "priority": "P1"}]))
        assert out == []


class TestScannedModules:
    def test_core_always_scanned(self):
        scanned = scanned_modules(_scores())
        for mid in ("seo", "security", "accessibility", "performance", "core"):
            assert mid in scanned

    def test_security_excluded_when_not_assessed(self):
        scanned = scanned_modules(_scores(security_assessed=False))
        assert "security" not in scanned

    def test_module_scores_included_but_errors_excluded(self):
        scanned = scanned_modules(
            _scores(module_scores={"eeat": {"total": 80}, "video": {"error": "boom"}})
        )
        assert "eeat" in scanned
        assert "video" not in scanned


class TestUpdatePunchlist:
    def test_new_finding_opens(self):
        punch = _fresh()
        stats = update_punchlist(punch, _scores(findings=[_finding()]), now="T1")
        assert stats["new"] == 1
        item = punch["items"][0]
        assert item["status"] == "open"
        assert item["first_seen"] == "T1"
        assert item["last_seen"] == "T1"

    def test_repeat_updates_last_seen_no_dupes(self):
        punch = _fresh()
        scores = _scores(
            findings=[_finding()], module_scores={"technical_seo": {"total": 70}}
        )
        update_punchlist(punch, scores, now="T1")
        stats = update_punchlist(punch, scores, now="T2")
        assert len(punch["items"]) == 1
        assert stats["still_open"] == 1
        assert punch["items"][0]["first_seen"] == "T1"
        assert punch["items"][0]["last_seen"] == "T2"

    def test_absent_from_rescanned_module_resolves(self):
        punch = _fresh()
        update_punchlist(
            punch,
            _scores(
                findings=[_finding()], module_scores={"technical_seo": {"total": 70}}
            ),
            now="T1",
        )
        stats = update_punchlist(
            punch,
            _scores(findings=[], module_scores={"technical_seo": {"total": 100}}),
            now="T2",
        )
        assert stats["resolved"] == 1
        assert punch["items"][0]["status"] == "resolved"
        assert punch["items"][0]["resolved_at"] == "T2"

    def test_absent_module_not_rescanned_stays_open(self):
        punch = _fresh()
        update_punchlist(
            punch,
            _scores(
                findings=[_finding()], module_scores={"technical_seo": {"total": 70}}
            ),
            now="T1",
        )
        # quick-profile rescan: technical_seo not scored this run
        stats = update_punchlist(punch, _scores(findings=[]), now="T2")
        assert stats["skipped"] == 1
        assert punch["items"][0]["status"] == "open"

    def test_resolved_finding_reappearing_reopens_as_regression(self):
        punch = _fresh()
        scored = _scores(
            findings=[_finding()], module_scores={"technical_seo": {"total": 70}}
        )
        update_punchlist(punch, scored, now="T1")
        update_punchlist(
            punch,
            _scores(findings=[], module_scores={"technical_seo": {"total": 100}}),
            now="T2",
        )
        stats = update_punchlist(punch, scored, now="T3")
        assert stats["reopened"] == 1
        item = punch["items"][0]
        assert item["status"] == "open"
        assert "resolved_at" not in item
        assert any("Regression" in n["text"] for n in item["notes"])

    def test_wontfix_survives_updates(self):
        punch = _fresh()
        update_punchlist(punch, _scores(findings=[_finding()]), now="T1")
        punch["items"][0]["status"] = "wontfix"
        update_punchlist(punch, _scores(findings=[_finding()]), now="T2")
        assert punch["items"][0]["status"] == "wontfix"

    def test_priority_recalibration_refreshes(self):
        punch = _fresh()
        update_punchlist(punch, _scores(findings=[_finding(priority="P2")]), now="T1")
        update_punchlist(punch, _scores(findings=[_finding(priority="P1")]), now="T2")
        assert punch["items"][0]["priority"] == "P1"

    def test_url_recorded(self):
        punch = _fresh()
        update_punchlist(punch, _scores(), url="https://example.com", now="T1")
        assert punch["url"] == "https://example.com"
        assert punch["updated"] == "T1"


class TestFindItem:
    def test_prefix_match(self):
        punch = _fresh()
        update_punchlist(punch, _scores(findings=[_finding()]), now="T1")
        full_id = punch["items"][0]["id"]
        assert find_item(punch, full_id[:6])["id"] == full_id

    def test_no_match(self):
        assert find_item(_fresh(), "zzzzzz") is None


class TestFormatStatus:
    def test_groups_by_priority_and_counts(self):
        punch = _fresh()
        update_punchlist(
            punch,
            _scores(
                findings=[
                    _finding(title="Broken canonical", priority="P0"),
                    _finding(title="Slow images", priority="P2"),
                ]
            ),
            url="https://example.com",
            now="T1",
        )
        text = format_status(punch)
        assert "https://example.com" in text
        assert "P0 — 1 open" in text
        assert "Broken canonical" in text
        assert "2 open · 0 resolved · 0 wontfix" in text

    def test_empty_list(self):
        assert "No open items" in format_status(_fresh())


class TestPersistence:
    def test_round_trip(self, tmp_path):
        path = os.path.join(str(tmp_path), ".fat-work", "punchlist.json")
        punch = _fresh()
        update_punchlist(punch, _scores(findings=[_finding()]), now="T1")
        save_punchlist(path, punch)
        loaded = load_punchlist(path)
        assert loaded["items"][0]["title"] == "Meta-refresh redirect in use"

    def test_load_missing_returns_fresh(self, tmp_path):
        loaded = load_punchlist(os.path.join(str(tmp_path), "nope.json"))
        assert loaded["items"] == []


class TestCalculateScoreEmitsFindings:
    """calculate-score.py must emit the merged flat findings list."""

    def test_module_findings_emitted(self):
        report = {
            "seo": {},
            "accessibility": {},
            "performance": {},
            "security": {},
            "modules": {
                "technical_seo": {
                    "x_robots_noindex": True,
                    "canonical_host_issue": "",
                    "meta_refresh": False,
                    "interstitial": {"intrusive": False},
                    "images": {
                        "total": 0,
                        "legacy": 0,
                        "next_gen": 0,
                        "missing_dims": 0,
                    },
                }
            },
        }
        result = score_mod.calculate_scores(report)
        titles = [f["title"] for f in result["findings"]]
        assert "Header-level noindex (X-Robots-Tag)" in titles
        # and the punch list can consume it directly
        punch = _fresh()
        stats = update_punchlist(punch, result, now="T1")
        assert stats["new"] >= 1

    def test_no_modules_emits_empty_list(self):
        result = score_mod.calculate_scores(
            {"seo": {}, "accessibility": {}, "performance": {}, "security": {}}
        )
        assert result["findings"] == []


class TestCiGateAdvisoryFindings:
    """Advisory-module findings in the flat list must not fail the gate when
    overall.blocking says there is nothing blocking."""

    def test_blocking_zero_beats_flat_advisory_p0(self):
        from ci_gate import check_priority_findings

        scores = {
            "overall": {"score": 90, "blocking": {"p0": 0, "p1": 0}},
            "findings": [
                {"priority": "P0", "title": "Advisory thing", "module": "pwa"}
            ],
        }
        passed, matched = check_priority_findings(scores, "P0")
        assert passed is True
        assert matched == []

    def test_legacy_shape_still_gates_on_flat_findings(self):
        from ci_gate import check_priority_findings

        scores = {"findings": [{"priority": "P0", "title": "Bad"}]}
        passed, matched = check_priority_findings(scores, "P0")
        assert passed is False


class TestCli:
    def _run(self, tmp_path, *argv):
        return subprocess.run(
            [sys.executable, SCRIPT, "--file", os.path.join(str(tmp_path), "pl.json")]
            + list(argv),
            capture_output=True,
            text=True,
        )

    def test_update_status_resolve_note_flow(self, tmp_path):
        scores_path = os.path.join(str(tmp_path), "scores.json")
        with open(scores_path, "w", encoding="utf-8") as f:
            json.dump(_scores(findings=[_finding()]), f)

        result = self._run(
            tmp_path, "update", "--scores", scores_path, "--url", "https://example.com"
        )
        assert result.returncode == 0
        assert "1 new" in result.stdout

        result = self._run(tmp_path, "status", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        item_id = data["items"][0]["id"]

        result = self._run(tmp_path, "note", item_id, "--text", "Client chose option B")
        assert result.returncode == 0

        result = self._run(
            tmp_path, "resolve", item_id, "--note", "Fixed in commit abc"
        )
        assert result.returncode == 0
        assert "resolved" in result.stdout

        result = self._run(tmp_path, "status")
        assert "1 resolved" in result.stdout

    def test_resolve_unknown_id_errors(self, tmp_path):
        result = self._run(tmp_path, "resolve", "deadbeef00")
        assert result.returncode == 1
