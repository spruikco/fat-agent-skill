"""Tests for gsc_fetch.py (direct Search Console export) and MCP-wrapped loaders."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import gsc_fetch
from gsc import load_rows
from update_impact import load_series

MCP_WRAPPED = {
    "_meta": {"source": "Google Search Console API (live data)"},
    "data": {
        "rows": [
            {"keys": ["https://e.com/a/"], "clicks": 3, "impressions": 40,
             "ctr": 7.5, "position": 4.2}
        ],
        "totalRows": 1,
    },
}


def test_load_rows_reads_mcp_wrapper():
    rows = load_rows(MCP_WRAPPED)
    assert len(rows) == 1 and rows[0]["clicks"] == 3


def test_update_impact_reads_mcp_wrapper():
    wrapped = {"_meta": {}, "data": {"rows": [{"keys": ["2026-01-01"], "clicks": 4}]}}
    assert load_series(json.dumps(wrapped))[0][1] == 4.0


def test_fetch_paginates(monkeypatch):
    calls = []

    def fake_post(url, body, token=None, form=False):
        calls.append(body["startRow"])
        n = gsc_fetch.PAGE_SIZE if body["startRow"] == 0 else 7
        return {"rows": [{"keys": [str(i)], "clicks": 1} for i in range(n)]}

    monkeypatch.setattr(gsc_fetch, "_post_json", fake_post)
    import datetime as dt

    rows = gsc_fetch.fetch("tok", "sc-domain:e.com", ["page"],
                           dt.date(2026, 1, 1), dt.date(2026, 3, 1))
    assert calls == [0, gsc_fetch.PAGE_SIZE]
    assert len(rows) == gsc_fetch.PAGE_SIZE + 7


def test_access_token_refreshes_from_saved_login(tmp_path, monkeypatch):
    tok = tmp_path / "oauth-token.json"
    tok.write_text(json.dumps({"refresh_token": "r1", "access_token": "old"}))
    sec = tmp_path / "secrets.json"
    sec.write_text(json.dumps({"installed": {"client_id": "c", "client_secret": "s",
                                             "token_uri": "https://t.example/token"}}))
    seen = {}

    def fake_post(url, body, token=None, form=False):
        seen.update(url=url, body=body, form=form)
        return {"access_token": "fresh"}

    monkeypatch.setattr(gsc_fetch, "_post_json", fake_post)
    monkeypatch.delenv("GSC_ACCESS_TOKEN", raising=False)

    class A:
        access_token = None
        token_file = str(tok)
        secrets_file = str(sec)

    assert gsc_fetch.access_token(A) == "fresh"
    assert seen["url"] == "https://t.example/token" and seen["form"]
    assert seen["body"]["refresh_token"] == "r1"
    # the saved login file is never rewritten
    assert json.loads(tok.read_text())["access_token"] == "old"


def test_explicit_token_wins(monkeypatch):
    class A:
        access_token = "direct"
        token_file = secrets_file = None

    assert gsc_fetch.access_token(A) == "direct"


def test_main_writes_standard_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(gsc_fetch, "access_token", lambda a: "t")
    monkeypatch.setattr(
        gsc_fetch, "fetch",
        lambda *a, **k: [{"keys": ["https://e.com/"], "clicks": 2, "impressions": 9}],
    )
    out = tmp_path / "p.json"
    assert gsc_fetch.main(["--site", "sc-domain:e.com", "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["dimensions"] == ["page"] and len(load_rows(data)) == 1
