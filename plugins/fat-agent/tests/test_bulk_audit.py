"""Tests for bulk_audit.py helper functions."""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from bulk_audit import load_sites, generate_summary, print_comparison_table


class TestLoadSites:
    """Test loading site lists from JSON files."""

    def test_load_valid_sites_file(self, tmp_path):
        sites = [
            {"url": "https://example.com", "name": "Example"},
            {"url": "https://test.org", "name": "Test"},
        ]
        sites_file = tmp_path / "sites.json"
        sites_file.write_text(json.dumps(sites))
        result = load_sites(str(sites_file))
        assert len(result) == 2
        assert result[0]["url"] == "https://example.com"
        assert result[1]["name"] == "Test"

    def test_load_empty_list(self, tmp_path):
        sites_file = tmp_path / "empty.json"
        sites_file.write_text("[]")
        result = load_sites(str(sites_file))
        assert result == []

    def test_load_missing_file_raises(self):
        try:
            load_sites("/nonexistent/path/sites.json")
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_load_invalid_json_raises(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json at all")
        try:
            load_sites(str(bad_file))
            assert False, "Expected json.JSONDecodeError"
        except json.JSONDecodeError:
            pass


class TestGenerateSummary:
    """Test summary generation from audit results."""

    def _make_result(
        self,
        name,
        url,
        seo=70,
        security=80,
        accessibility=75,
        performance=60,
        overall=71,
        grade="B",
    ):
        return {
            "name": name,
            "url": url,
            "scores": {
                "seo": {"score": seo, "max": 100},
                "security": {"score": security, "max": 100},
                "accessibility": {"score": accessibility, "max": 100},
                "performance": {"score": performance, "max": 100},
                "overall": {"score": overall, "max": 100, "grade": grade},
            },
        }

    def test_summary_has_all_sites(self):
        results = [
            self._make_result("Site A", "https://a.com", overall=80, grade="B"),
            self._make_result("Site B", "https://b.com", overall=60, grade="C"),
        ]
        summary = generate_summary(results)
        assert len(summary["sites"]) == 2

    def test_summary_computes_average(self):
        results = [
            self._make_result("A", "https://a.com", overall=80, grade="B"),
            self._make_result("B", "https://b.com", overall=60, grade="C"),
        ]
        summary = generate_summary(results)
        assert summary["average_overall"] == 70

    def test_summary_finds_best_and_worst(self):
        results = [
            self._make_result("Low", "https://low.com", overall=40, grade="D"),
            self._make_result("High", "https://high.com", overall=90, grade="A"),
            self._make_result("Mid", "https://mid.com", overall=65, grade="C"),
        ]
        summary = generate_summary(results)
        assert summary["best"]["name"] == "High"
        assert summary["worst"]["name"] == "Low"

    def test_summary_empty_results(self):
        summary = generate_summary([])
        assert summary["sites"] == []
        assert summary["average_overall"] == 0
        assert summary["best"] is None
        assert summary["worst"] is None

    def test_summary_single_site(self):
        results = [self._make_result("Only", "https://only.com", overall=55, grade="C")]
        summary = generate_summary(results)
        assert summary["best"]["name"] == "Only"
        assert summary["worst"]["name"] == "Only"
        assert summary["average_overall"] == 55


class TestPrintComparisonTable:
    """Test the console table output format."""

    def _make_result(
        self,
        name,
        url,
        seo=70,
        security=80,
        accessibility=75,
        performance=60,
        overall=71,
        grade="B",
    ):
        return {
            "name": name,
            "url": url,
            "scores": {
                "seo": {"score": seo, "max": 100},
                "security": {"score": security, "max": 100},
                "accessibility": {"score": accessibility, "max": 100},
                "performance": {"score": performance, "max": 100},
                "overall": {"score": overall, "max": 100, "grade": grade},
            },
        }

    def test_table_contains_site_names(self, capsys):
        results = [
            self._make_result("Alpha", "https://alpha.com"),
            self._make_result("Beta", "https://beta.com"),
        ]
        print_comparison_table(results)
        output = capsys.readouterr().out
        assert "Alpha" in output
        assert "Beta" in output

    def test_table_contains_column_headers(self, capsys):
        results = [self._make_result("Test", "https://test.com")]
        print_comparison_table(results)
        output = capsys.readouterr().out
        assert "SEO" in output
        assert "Security" in output
        assert "Overall" in output

    def test_table_contains_scores(self, capsys):
        results = [self._make_result("Test", "https://test.com", seo=85, overall=72)]
        print_comparison_table(results)
        output = capsys.readouterr().out
        assert "85" in output
        assert "72" in output

    def test_table_empty_results(self, capsys):
        print_comparison_table([])
        output = capsys.readouterr().out
        assert "No results" in output or output.strip() == ""
