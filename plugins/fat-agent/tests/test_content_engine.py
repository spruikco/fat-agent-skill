"""Tests for content_engine.py — query clustering, classification, roadmap."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from content_engine import as_findings, build_roadmap, cluster_queries
from editorial_report import render, roadmap_slide


def _row(query, page="", clicks=0, impressions=100, position=15.0):
    return {
        "query": query,
        "page": page,
        "clicks": clicks,
        "impressions": impressions,
        "position": position,
    }


def _actions(roadmap):
    return {c["label"]: c["action"] for c in roadmap["clusters"]}


class TestClustering:
    def test_related_queries_cluster_together(self):
        rows = [
            _row("termite inspection cost", impressions=900),
            _row("termite inspection price", impressions=300),
            _row("rodent control adelaide", impressions=200),
        ]
        clusters = cluster_queries(rows)
        assert len(clusters) == 2
        assert len(clusters[0]["rows"]) == 2  # both termite queries

    def test_brand_terms_excluded(self):
        rows = [_row("acme pest control"), _row("acme reviews")]
        clusters = cluster_queries(rows, brand="acme")
        labels = {c["label"] for c in clusters}
        assert "acme pest control" in labels  # still clustered, minus brand term
        # brand term did not force the two into one cluster
        assert len(clusters) == 2

    def test_plural_stemming_joins(self):
        clusters = cluster_queries([_row("pest inspections"), _row("pest inspection")])
        assert len(clusters) == 1


class TestClassification:
    def test_create_when_no_page(self):
        roadmap = build_roadmap([_row("possum removal guide", page="")])
        assert _actions(roadmap)["possum removal guide"] == "create"
        brief = roadmap["clusters"][0]["brief"]
        assert brief["working_title"].startswith("Possum Removal")

    def test_defend_optimise_rework_by_position(self):
        roadmap = build_roadmap(
            [
                _row("ant control", page="https://e.com/a/", position=3.0),
                _row("bee removal", page="https://e.com/b/", position=12.0),
                _row("flea treatment", page="https://e.com/c/", position=35.0),
            ]
        )
        actions = _actions(roadmap)
        assert actions["ant control"] == "defend"
        assert actions["bee removal"] == "optimise"
        assert actions["flea treatment"] == "rework"

    def test_consolidate_when_two_pages_split_cluster(self):
        roadmap = build_roadmap(
            [
                _row("spider control", page="https://e.com/a/", impressions=500),
                _row("spider control sydney", page="https://e.com/b/", impressions=400),
            ]
        )
        assert list(_actions(roadmap).values()) == ["consolidate"]

    def test_refresh_on_decay(self):
        prev = [_row("cockroach bait", page="https://e.com/r/", clicks=100)]
        now = [_row("cockroach bait", page="https://e.com/r/", clicks=20)]
        roadmap = build_roadmap(now, prev_rows=prev)
        assert _actions(roadmap)["cockroach bait"] == "refresh"

    def test_summary_counts(self):
        roadmap = build_roadmap([_row("x guide", page=""), _row("y tips", page="")])
        assert roadmap["summary"]["create"] == 2


class TestFindings:
    def test_findings_shape_and_priorities(self):
        roadmap = build_roadmap(
            [
                _row("wasp nest removal", page="", impressions=800),
                _row("silverfish treatment", page="https://e.com/s/", position=40.0),
            ]
        )
        findings = {f["title"]: f for f in as_findings(roadmap)}
        create = next(v for k, v in findings.items() if k.startswith("New content"))
        assert create["priority"] == "P1"
        assert create["module"] == "content_engine"
        rework = next(v for k, v in findings.items() if k.startswith("Rework"))
        assert rework["priority"] == "P2"

    def test_defend_clusters_emit_no_findings(self):
        roadmap = build_roadmap([_row("ok", page="https://e.com/", position=2.0)])
        assert as_findings(roadmap) == []


class TestDeckIntegration:
    KIT = {
        "site_name": "Acme",
        "colors": {"accent": "#e63946"},
        "fonts": {"primary": "Sora", "google_fonts_url": ""},
        "images": {"local": {"logo": "", "heroes": []}},
    }
    SCORES = {"overall": {"score": 70, "grade": "B"}, "findings": []}

    def test_roadmap_slide_rendered(self):
        roadmap = build_roadmap([_row("wasp nest removal", page="", impressions=800)])
        html = render(self.SCORES, {}, self.KIT, "FAT", roadmap)
        assert "Content roadmap" in html
        assert "Wasp Nest Removal" in html

    def test_empty_roadmap_no_slide(self):
        assert roadmap_slide({"clusters": []}, lambda **k: "", 3) == ""
        html = render(self.SCORES, {}, self.KIT, "FAT", None)
        assert "Content roadmap" not in html
