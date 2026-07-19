"""Tests for ga4.py — GA4 behaviour layer."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from ga4 import analyse, as_findings, load_rows

GA4_UI_CSV = (
    "# ----------------------------------------\n"
    "# All Users\n"
    "# ----------------------------------------\n"
    "Landing page + query string,Sessions,Engagement rate,Key events\n"
    '/blog/ant-guide/?utm_source=x,"1,200",22.5%,0\n'
    "/services/pest-control/,300,61%,12\n"
    "/services/termite-inspection/,80,55%,0\n"
    "Grand total,1580,35%,12\n"
)


def _rows(tmp_path):
    p = os.path.join(str(tmp_path), "ga4.csv")
    with open(p, "w", encoding="utf-8-sig") as f:
        f.write(GA4_UI_CSV)
    return load_rows(p)


class TestIngestion:
    def test_ui_csv_preamble_percent_and_totals(self, tmp_path):
        rows = _rows(tmp_path)
        assert len(rows) == 3  # Grand total dropped
        top = rows[0]
        assert top["page"] == "/blog/ant-guide/"  # query string stripped
        assert top["sessions"] == 1200
        assert top["engagement_rate"] == 0.225

    def test_json_rows_with_fraction_rates(self, tmp_path):
        import json

        p = os.path.join(str(tmp_path), "ga4.json")
        json.dump(
            {"rows": [{"page": "/x/", "sessions": 10, "engagement rate": 0.8}]},
            open(p, "w"),
        )
        rows = load_rows(p)
        assert rows[0]["engagement_rate"] == 0.8


class TestAnalysis:
    def test_engagement_gap_and_money_no_conversions(self, tmp_path):
        result = analyse(_rows(tmp_path), min_sessions=50)
        gap_pages = [r["page"] for r in result["engagement_gaps"]]
        assert gap_pages == ["/blog/ant-guide/"]
        money = [r["page"] for r in result["money_no_conversions"]]
        assert money == ["/services/termite-inspection/"]

    def test_converting_money_page_not_flagged(self, tmp_path):
        result = analyse(_rows(tmp_path), min_sessions=50)
        assert "/services/pest-control/" not in [
            r["page"] for r in result["money_no_conversions"]
        ]

    def test_findings_shape(self, tmp_path):
        findings = as_findings(analyse(_rows(tmp_path), min_sessions=50))
        assert all(f["module"] == "ga4" for f in findings)
        titles = [f["title"] for f in findings]
        assert any(t.startswith("Engagement gap") for t in titles)
        assert any(t.startswith("Money page converting nothing") for t in titles)
