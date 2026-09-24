"""Tests for update_impact.py and the GSC cross-reference in sitewide.py."""

import datetime as dt
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.google_guidelines import title_is_stuffed
from sitecrawl import SCHEMA, simhash64
from sitewide import load_gsc_pages, run_checks, triage, url_key
from update_impact import analyse, load_series


# --------------------------------------------------------------------------- #
# update_impact
# --------------------------------------------------------------------------- #
def _daily(start, days, fn):
    d0 = dt.date.fromisoformat(start)
    return [
        {"keys": [(d0 + dt.timedelta(days=i)).isoformat()], "clicks": fn(i)}
        for i in range(days)
    ]


def test_drop_lines_up_with_spam_update():
    # flat 100/day, then 40/day from the August 2026 spam update onwards
    cut = (dt.date(2026, 8, 18) - dt.date(2026, 6, 1)).days
    rows = _daily("2026-06-01", 120, lambda i: 100 if i < cut else 40)
    res = analyse(load_series(json.dumps({"rows": rows})))
    worst = res["impacts"][0]
    assert worst["update"] == "August 2026 spam update"
    assert worst["change_pct"] == -60.0
    f = res["findings"][0]
    assert f["priority"] == "P1" and "consistent with" in f["description"]


def test_flat_series_no_findings():
    rows = _daily("2026-01-01", 250, lambda i: 50)
    res = analyse(load_series(json.dumps(rows)))
    assert res["impacts"] and res["findings"] == []


def test_semrush_monthly_history():
    text = (
        "Date;Rank;Organic Keywords;Organic Traffic;Organic Cost\n"
        "20260815;1;690;196;12\n20260715;1;799;210;45\n20260615;1;681;146;31\n"
        "20260515;1;402;284;216\n20260415;1;298;274;209\n20260315;1;184;269;21\n"
        "20260215;1;186;230;0\n20260115;1;161;204;0\n"
    )
    series = load_series(text)
    assert series[0] == (dt.date(2026, 1, 15), 204.0)
    res = analyse(series)
    assert res["granularity_days"] >= 28
    assert any(i["update"] == "May 2026 core update" for i in res["impacts"])


def test_gsc_rows_summed_per_date():
    rows = [
        {"keys": ["2026-01-01", "/a"], "clicks": 3},
        {"keys": ["2026-01-01", "/b"], "clicks": 4},
    ]
    assert load_series(json.dumps(rows)) == [(dt.date(2026, 1, 1), 7.0)]


# --------------------------------------------------------------------------- #
# GSC cross-reference
# --------------------------------------------------------------------------- #
def test_url_key_normalises():
    assert url_key("https://www.E.com/a/") == url_key("http://e.com/a") == "e.com/a"
    assert url_key("https://e.com/") == "e.com/"


def test_load_gsc_pages_aggregates(tmp_path):
    p = tmp_path / "gsc.json"
    p.write_text(
        json.dumps(
            {
                "rows": [
                    {"keys": ["seo carlton", "https://e.com/a/"], "clicks": 2,
                     "impressions": 10, "position": 4},
                    {"keys": ["seo agency", "https://e.com/a"], "clicks": 1,
                     "impressions": 30, "position": 8},
                    {"keys": ["https://e.com/b/"], "clicks": 0, "impressions": 5},
                ]
            }
        )
    )
    pages = load_gsc_pages(str(p))
    assert pages["e.com/a"]["clicks"] == 3
    assert pages["e.com/a"]["position"] == 7.0
    assert pages["e.com/b"]["impressions"] == 5


def test_triage_buckets():
    gsc = {"e.com/a": {"clicks": 5, "impressions": 50},
           "e.com/b": {"clicks": 0, "impressions": 9}}
    t = triage(["https://e.com/a/", "https://e.com/b/", "https://e.com/c/"], gsc)
    assert t == {"keep": ["https://e.com/a/"], "improve": ["https://e.com/b/"],
                 "prune": ["https://e.com/c/"], "clicks": 5}


TEMPLATE = (
    "Looking for a trusted SEO agency in {p}? Our team helps {p} businesses grow "
    "with technical audits, content strategy, link building and local search. We "
    "have worked with hundreds of clients and deliver monthly reporting, clear "
    "pricing and no lock-in contracts. Book a free strategy call with our "
    "consultants today and find out how we can help your business win online."
)


def test_doorway_finding_carries_gsc_triage():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    places = ["Carlton", "Fitzroy", "Richmond", "Kew", "Coburg"]
    for pl in places:
        u = f"https://e.com/local/seo-in-{pl.lower()}/"
        con.execute(
            "INSERT INTO pages (url,status,indexable,title,meta_desc,meta_desc_len,"
            "h1_count,simhash,content_hash,content_type) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (u, 200, 1, f"SEO {pl}", "d" * 130, 130, 1,
             simhash64(TEMPLATE.format(p=pl)), u, "text/html"),
        )
        con.execute("INSERT INTO links VALUES (?,?,?,?,?)", ("x", u, "", "", "internal"))
    gsc = {"e.com/local/seo-in-carlton": {"clicks": 12, "impressions": 300}}
    found = {f["key"]: f for f in run_checks(con, gsc)}
    d = found["doorway_templates"]
    assert "keep 1, improve 0, prune 4" in d["description"]
    assert d["clusters"][0]["triage"]["keep"] == ["https://e.com/local/seo-in-carlton/"]
    assert found["gsc_zero_impressions"]["count"] == 4


def test_title_stuffing_tolerates_normal_titles():
    assert not title_is_stuffed(
        "Claude Code Agency (US, AU) | Opus 4.7 Builds, Agents & MCP | Spruik"
    )
    assert not title_is_stuffed("Perth Digital Marketing | SEO, Google Ads, Social | Spruik")
    assert title_is_stuffed("SEO Perth | SEO, Google Ads, Social Media, Web Design, PPC")
