"""Tests for generate_html_dashboard.py — HTML dashboard report generator."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from generate_html_dashboard import generate_dashboard, grade_from_score


class TestGradeFromScore:
    """Test grade calculation from numeric scores."""

    def test_grade_a(self):
        assert grade_from_score(90) == "A"
        assert grade_from_score(95) == "A"
        assert grade_from_score(100) == "A"

    def test_grade_b(self):
        assert grade_from_score(80) == "B"
        assert grade_from_score(85) == "B"
        assert grade_from_score(89) == "B"

    def test_grade_c(self):
        assert grade_from_score(70) == "C"
        assert grade_from_score(75) == "C"
        assert grade_from_score(79) == "C"

    def test_grade_d(self):
        assert grade_from_score(60) == "D"
        assert grade_from_score(65) == "D"
        assert grade_from_score(69) == "D"

    def test_grade_f(self):
        assert grade_from_score(0) == "F"
        assert grade_from_score(30) == "F"
        assert grade_from_score(59) == "F"

    def test_boundary_values(self):
        assert grade_from_score(90) == "A"
        assert grade_from_score(89) == "B"
        assert grade_from_score(80) == "B"
        assert grade_from_score(79) == "C"
        assert grade_from_score(70) == "C"
        assert grade_from_score(69) == "D"
        assert grade_from_score(60) == "D"
        assert grade_from_score(59) == "F"


MOCK_SCORES = {
    "overall_score": 72,
    "seo_score": 85,
    "security_score": 60,
    "accessibility_score": 78,
    "performance_score": 65,
    "findings": [
        {
            "category": "SEO",
            "issue": "Missing meta description",
            "priority": "P1",
            "detail": "No meta description tag found.",
        },
        {
            "category": "Security",
            "issue": "Missing Content-Security-Policy header",
            "priority": "P2",
            "detail": "CSP header not set. <code>add_header Content-Security-Policy</code>",
        },
        {
            "category": "Accessibility",
            "issue": "Images missing alt attributes",
            "priority": "P1",
            "detail": "3 images lack alt text.",
        },
    ],
    "module_scores": {
        "links": {"score": 90, "label": "Link Health"},
        "local_seo": {"score": 45, "label": "Local SEO"},
        "email_deliverability": {"score": 82, "label": "Email Deliverability"},
    },
}


class TestGenerateDashboard:
    """Test HTML dashboard generation."""

    def test_generates_html_file(self, tmp_path):
        output = generate_dashboard(
            scores=MOCK_SCORES,
            url="https://example.com",
            output_dir=str(tmp_path),
        )
        assert os.path.isfile(output)
        assert output.endswith(".html")

    def test_html_contains_url(self, tmp_path):
        output = generate_dashboard(
            scores=MOCK_SCORES,
            url="https://example.com",
            output_dir=str(tmp_path),
        )
        with open(output) as f:
            html = f.read()
        assert "https://example.com" in html

    def test_html_contains_scores(self, tmp_path):
        output = generate_dashboard(
            scores=MOCK_SCORES,
            url="https://example.com",
            output_dir=str(tmp_path),
        )
        with open(output) as f:
            html = f.read()
        assert "72" in html  # overall
        assert "85" in html  # seo
        assert "60" in html  # security
        assert "78" in html  # accessibility
        assert "65" in html  # performance

    def test_html_contains_grades(self, tmp_path):
        output = generate_dashboard(
            scores=MOCK_SCORES,
            url="https://example.com",
            output_dir=str(tmp_path),
        )
        with open(output) as f:
            html = f.read()
        # 72 -> C grade
        assert "grade-c" in html.lower() or "Grade: C" in html

    def test_html_contains_findings(self, tmp_path):
        output = generate_dashboard(
            scores=MOCK_SCORES,
            url="https://example.com",
            output_dir=str(tmp_path),
        )
        with open(output) as f:
            html = f.read()
        assert "Missing meta description" in html
        assert "Missing Content-Security-Policy" in html
        assert "Images missing alt attributes" in html

    def test_html_contains_module_scores(self, tmp_path):
        output = generate_dashboard(
            scores=MOCK_SCORES,
            url="https://example.com",
            output_dir=str(tmp_path),
        )
        with open(output) as f:
            html = f.read()
        assert "Link Health" in html
        assert "Local SEO" in html
        assert "Email Deliverability" in html

    def test_client_facing_hides_code(self, tmp_path):
        output = generate_dashboard(
            scores=MOCK_SCORES,
            url="https://example.com",
            output_dir=str(tmp_path),
            client_facing=True,
        )
        with open(output) as f:
            html = f.read()
        # code snippets should be stripped in client-facing mode
        assert "<code>" not in html
        assert "add_header Content-Security-Policy" not in html

    def test_client_facing_still_has_issues(self, tmp_path):
        output = generate_dashboard(
            scores=MOCK_SCORES,
            url="https://example.com",
            output_dir=str(tmp_path),
            client_facing=True,
        )
        with open(output) as f:
            html = f.read()
        # non-code findings should remain
        assert "Missing meta description" in html
        assert "Images missing alt attributes" in html

    def test_charts_embedded_as_base64(self, tmp_path):
        # create a fake chart png (1x1 pixel)
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()
        import base64

        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
            "nGNgYPgPAAEDAQAIicLsAAAABJRU5ErkJggg=="
        )
        (charts_dir / "chart_fat_scores.png").write_bytes(png_data)
        output = generate_dashboard(
            scores=MOCK_SCORES,
            url="https://example.com",
            output_dir=str(tmp_path),
            charts_dir=str(charts_dir),
        )
        with open(output) as f:
            html = f.read()
        assert "data:image/png;base64," in html

    def test_no_findings_produces_empty_table(self, tmp_path):
        scores = {**MOCK_SCORES, "findings": []}
        output = generate_dashboard(
            scores=scores,
            url="https://example.com",
            output_dir=str(tmp_path),
        )
        with open(output) as f:
            html = f.read()
        assert "No findings" in html or "<tbody" in html

    def test_no_module_scores(self, tmp_path):
        scores = {k: v for k, v in MOCK_SCORES.items() if k != "module_scores"}
        output = generate_dashboard(
            scores=scores,
            url="https://example.com",
            output_dir=str(tmp_path),
        )
        assert os.path.isfile(output)

    def test_html_is_self_contained(self, tmp_path):
        output = generate_dashboard(
            scores=MOCK_SCORES,
            url="https://example.com",
            output_dir=str(tmp_path),
        )
        with open(output) as f:
            html = f.read()
        assert "<style>" in html
        assert "</html>" in html
        # no external stylesheet references
        assert 'rel="stylesheet"' not in html
