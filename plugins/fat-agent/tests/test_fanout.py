"""Tests for fanout.py — query fan-out generation and site coverage scoring."""

import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import fanout
from fanout import analyse, build_fanout, load_extra_queries, load_pages, match, tokens
from sitecrawl import SCHEMA, PageParser


def _db(pages):
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    for url, title, h1, heads in pages:
        con.execute(
            "INSERT INTO pages (url,status,indexable,title,h1,headings) VALUES (?,?,?,?,?,?)",
            (url, 200, 1, title, h1, heads),
        )
    return con


SITE = [
    ("https://e.com/", "SEO Agency Melbourne | Acme", "SEO Agency Melbourne",
     "What is SEO? | How does SEO work | Our results"),
    ("https://e.com/pricing/", "SEO Agency Melbourne Cost & Pricing", "SEO pricing",
     None),
]


def test_build_fanout_types():
    fan = build_fanout("SEO agency", entity="Acme", location="Melbourne", year=2026)
    types = {f["type"] for f in fan}
    assert {"core", "definition", "cost", "comparison", "local", "branded"} <= types
    queries = [f["query"] for f in fan]
    assert "seo agency in Melbourne" in queries
    assert "seo agency 2026" in queries
    assert "acme reviews".lower() in [q.lower() for q in queries]


def test_location_template_skipped_when_seed_has_location():
    fan = build_fanout("seo agency melbourne", location="Melbourne")
    assert not any(q["query"].endswith("in Melbourne") for q in fan)


def test_tokens_stem_and_drop_stopwords():
    assert tokens("How does SEO work for agencies") == {"seo", "work", "agency"}


def test_match_levels():
    pages = load_pages(_db(SITE))
    assert match("seo agency melbourne", pages)["level"] == "page"
    assert match("seo agency melbourne cost", pages)["url"] == "https://e.com/pricing/"
    sec = match("how does seo work", pages)
    assert sec["level"] == "section" and sec["evidence"] == "How does SEO work"
    assert match("seo agency melbourne case studies", pages)["level"] in ("mention", "gap")
    assert match("bakery opening hours", pages)["level"] == "gap"


def test_analyse_reports_gaps_and_finding():
    pages = load_pages(_db(SITE))
    res = analyse(["seo agency melbourne"], pages, entity="Acme")
    r = res["results"][0]
    assert 0 < r["coverage_pct"] < 60
    assert "trust" in r["missing_types"]
    f = res["findings"][0]
    assert f["title"] == "Low query fan-out coverage: 'seo agency melbourne'"
    # branded sub-queries are off-site territory: excluded from on-site coverage
    assert all(s["type"] != "branded" for s in r["subqueries"] if s["level"] == "page")


def test_well_covered_seed_no_finding():
    heads = " | ".join(
        q["query"] for q in build_fanout("seo audit") if q["type"] != "core"
    )
    pages = load_pages(_db([("https://e.com/a/", "SEO audit", "SEO audit", heads)]))
    res = analyse(["seo audit"], pages)
    assert res["results"][0]["coverage_pct"] == 100
    assert res["findings"] == []


def test_extra_queries_formats(tmp_path):
    j = tmp_path / "q.json"
    j.write_text(json.dumps([{"query": "seo for dentists", "type": "specification"}, "x y"]))
    assert load_extra_queries(str(j)) == [
        {"query": "seo for dentists", "type": "specification"},
        {"query": "x y", "type": "llm"},
    ]
    t = tmp_path / "q.txt"
    t.write_text("a b\n\nc d\n")
    assert [q["query"] for q in load_extra_queries(str(t))] == ["a b", "c d"]


def test_autocomplete_fails_soft(monkeypatch):
    def boom(*a, **k):
        raise OSError("offline")

    monkeypatch.setattr(fanout.urllib.request, "urlopen", boom)
    monkeypatch.setattr(fanout.time, "sleep", lambda s: None)
    assert fanout.autocomplete("seo") == []


def test_seeds_from_gsc_skips_branded(tmp_path):
    p = tmp_path / "gsc.json"
    p.write_text(json.dumps({"rows": [
        {"keys": ["acme seo"], "clicks": 50, "impressions": 900},
        {"keys": ["seo agency melbourne"], "clicks": 5, "impressions": 800},
        {"keys": ["local seo"], "clicks": 1, "impressions": 100},
    ]}))
    assert fanout.seeds_from_gsc(str(p), 5, ["Acme"]) == [
        "seo agency melbourne", "local seo"
    ]


def test_parser_collects_headings():
    p = PageParser("https://e.com/")
    p.feed("<h1>Top</h1><h2>What is SEO?</h2><p>x</p><h3>Pricing <b>2026</b></h3>")
    assert p.headings == ["What is SEO?", "Pricing 2026"]


def test_cli_export(tmp_path, capsys):
    db = tmp_path / "site.db"
    con = sqlite3.connect(str(db))
    con.executescript(SCHEMA)
    con.execute(
        "INSERT INTO pages (url,status,indexable,title,h1) VALUES (?,?,?,?,?)",
        ("https://e.com/", 200, 1, "SEO audit", "SEO audit"),
    )
    con.commit()
    con.close()
    out = tmp_path / "q.txt"
    assert fanout.main(["--db", str(db), "--seed", "seo audit",
                        "--export-queries", str(out), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["module_scores"]["fanout"]["results"][0]["seed"] == "seo audit"
    assert "seo audit cost" in out.read_text().splitlines()
