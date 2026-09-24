"""Tests for jev.py — client wire format, retries, caching, backends and tasks."""

import json
import os
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import jev
from sitecrawl import SCHEMA, simhash64


# --------------------------------------------------------------------------- #
# A tiny Jev-wire-compatible server (stands in for TypeSafe or OpenJev)
# --------------------------------------------------------------------------- #
class _Handler(BaseHTTPRequestHandler):
    calls = []
    fail_first = 0

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.calls.append({"path": self.path, "auth": self.headers.get("Authorization"),
                               "body": body})
        if _Handler.fail_first > 0:
            _Handler.fail_first -= 1
            self.send_response(429)
            self.send_header("retry-after", "0")
            self.end_headers()
            return
        text = json.dumps(body["state"]).lower()
        answers = {}
        for qid, q in body["questions"].items():
            if q["type"] == "noul":
                answers[qid] = {"type": "noul", "noul": 0.9 if "office" in text else 0.1}
            elif q["type"] == "score":
                n = len(q["criteria"])
                answers[qid] = {"type": "score", "score": 1.0, "confidence": 0.7,
                                "legend": {str(i): c for i, c in enumerate(q["criteria"])},
                                "probabilities": {str(i): 1.0 / n for i in range(n)}}
        out = json.dumps({"model": "jev-1.13.0", "answers": answers,
                          "usage": {"input_tokens": 100, "output_tokens": 5}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)


@pytest.fixture()
def server():
    _Handler.calls = []
    _Handler.fail_first = 0
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_client_wire_format_and_usage(server):
    c = jev.JevClient(server, api_key="k", workers=2)
    a = c.ask("our Carlton office", {"q": jev.DOORWAY_QUESTIONS["local_substance"]})
    call = _Handler.calls[0]
    assert call["path"] == "/v1/systemone"
    assert call["auth"] == "Bearer k"
    assert call["body"]["model"] == "jev-latest"
    assert a["q"]["noul"] == 0.9
    assert c.served_by == "jev-1.13.0" and c.usage["input_tokens"] == 100


def test_no_key_sends_no_auth_header(server):
    jev.JevClient(server).ask("x", {"q": jev.FANOUT_QUESTION["answers_query"]})
    assert _Handler.calls[0]["auth"] is None


def test_retries_on_429(server, monkeypatch):
    monkeypatch.setattr(jev.time, "sleep", lambda s: None)
    _Handler.fail_first = 2
    a = jev.JevClient(server).ask("office", {"q": jev.DOORWAY_QUESTIONS["local_substance"]})
    assert a["q"]["noul"] == 0.9 and len(_Handler.calls) == 3


def test_cache_avoids_repeat_calls(server, tmp_path):
    cache = str(tmp_path / "c.json")
    qs = {"q": jev.DOORWAY_QUESTIONS["local_substance"]}
    jev.JevClient(server, cache_path=cache).ask_many([("a", "office", qs)])
    c2 = jev.JevClient(server, cache_path=cache)
    c2.ask_many([("a", "office", qs)])
    assert len(_Handler.calls) == 1 and c2.usage["cached"] == 1


def test_errors_are_per_item(monkeypatch):
    c = jev.JevClient("http://127.0.0.1:9", retries=0)
    out = c.ask_many([("a", "x", {"q": jev.FANOUT_QUESTION["answers_query"]})])
    assert "error" in out["a"]


def test_resolve_backend(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_BASE_URL", raising=False)
    assert jev.resolve_backend("auto")[0] == "agent"
    assert jev.resolve_backend("auto", api_key="k") == ("typesafe", jev.DEFAULT_BASE, "k")
    assert jev.resolve_backend("auto", base_url="http://h:1")[:2] == ("local", "http://h:1")
    assert jev.resolve_backend("local")[1] == "http://localhost:8000"
    with pytest.raises(SystemExit):
        jev.resolve_backend("typesafe")


def test_location_hint():
    assert jev._location_hint(
        "https://e.com/local/seo-agency-in-st-kilda-melbourne/",
        "/local/seo-agency-in-{*}/") == "st kilda melbourne"
    assert jev._location_hint("https://e.com/perth/seo/", "/{*}/seo/") == "perth"


# --------------------------------------------------------------------------- #
# Tasks over a synthetic crawl
# --------------------------------------------------------------------------- #
TEMPLATE = (
    "Looking for a trusted SEO agency in {p}? Our team helps {p} businesses grow "
    "with technical audits, content strategy, link building and local search. We "
    "have worked with hundreds of clients and deliver monthly reporting, clear "
    "pricing and no lock-in contracts. Book a free strategy call with our "
    "consultants today and find out how we can help your business win online."
)
PLACES = ["Carlton", "Fitzroy", "Richmond", "Kew"]


def _crawl(tmp_path):
    db = str(tmp_path / "site.db")
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    for pl in PLACES:
        text = TEMPLATE.format(p=pl)
        if pl == "Carlton":
            text += " Visit our Carlton office on Lygon Street."
        con.execute(
            "INSERT INTO pages (url,status,indexable,title,h1,headings,simhash,"
            "main_excerpt) VALUES (?,?,?,?,?,?,?,?)",
            (f"https://e.com/local/seo-in-{pl.lower()}/", 200, 1, f"SEO {pl}",
             f"SEO agency {pl}", "What is SEO? | SEO pricing",
             simhash64(TEMPLATE.format(p=pl)), text),
        )
    con.commit()
    return db, con


def test_doorway_end_to_end_with_gsc(server, tmp_path, capsys):
    db, _ = _crawl(tmp_path)
    gsc = tmp_path / "gsc.json"
    gsc.write_text(json.dumps({"rows": [
        {"keys": ["https://e.com/local/seo-in-fitzroy/"], "clicks": 3, "impressions": 90},
        {"keys": ["https://e.com/local/seo-in-richmond/"], "clicks": 0, "impressions": 40},
        {"keys": ["https://e.com/local/seo-in-kew/"], "clicks": 0, "impressions": 3},
    ]}))
    out = tmp_path / "out.json"
    rc = jev.main(["doorway", "--db", db, "--gsc", str(gsc), "--backend", "local",
                   "--base-url", server, "--cache", str(tmp_path / "c.json"),
                   "--out", str(out)])
    assert rc == 0
    res = json.loads(out.read_text())
    verdicts = {p["url"].split("-in-")[1].strip("/"): p["verdict"]
                for g in res["groups"] for p in g["pages"]}
    assert verdicts == {"carlton": "keep", "fitzroy": "improve",
                        "richmond": "improve", "kew": "prune"}
    assert res["findings"][0]["module"] == "jev"
    state = _Handler.calls[0]["body"]["state"]["page"]
    assert state["location_hint"] and state["text_excerpt"]


def test_agent_backend_roundtrip(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_BASE_URL", raising=False)
    db, _ = _crawl(tmp_path)
    batch = tmp_path / "batch.json"
    assert jev.main(["doorway", "--db", db, "--export", str(batch)]) == 0
    items = json.loads(batch.read_text())
    assert len(items) == 4 and set(items[0]["questions"]) == {"local_substance",
                                                             "originality"}
    # the agent answers in the Jev shape
    answers = {it["id"]: {"local_substance": {"type": "noul", "noul": 0.05},
                          "originality": {"type": "score", "score": 0.5,
                                          "legend": {"0": "a", "1": "b"}}}
               for it in items}
    ans_file = tmp_path / "answers.json"
    ans_file.write_text(json.dumps(answers))
    out = tmp_path / "out.json"
    assert jev.main(["doorway", "--db", db, "--answers", str(ans_file),
                     "--out", str(out)]) == 0
    res = json.loads(out.read_text())
    assert res["backend"] == "agent"
    assert all(p["verdict"] == "prune" for g in res["groups"] for p in g["pages"])


def test_fanout_task(server, tmp_path):
    db, _ = _crawl(tmp_path)
    out = tmp_path / "f.json"
    assert jev.main(["fanout", "--db", db, "--seed", "seo agency carlton",
                     "--backend", "local", "--base-url", server,
                     "--cache", str(tmp_path / "c.json"), "--out", str(out)]) == 0
    res = json.loads(out.read_text())
    subs = res["results"][0]["subqueries"]
    assert subs and all("answered" in s for s in subs)
    # the fake server says only the page mentioning an office answers anything
    answered = {s["best_url"] for s in subs if s["answered"]}
    assert answered <= {"https://e.com/local/seo-in-carlton/"}


def test_ping_agent(monkeypatch, capsys):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_BASE_URL", raising=False)
    assert jev.main(["ping"]) == 0
    assert json.loads(capsys.readouterr().out)["backend"] == "agent"


def test_ping_server(server, capsys):
    assert jev.main(["ping", "--backend", "local", "--base-url", server]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["model"] == "jev-1.13.0"


def test_per_cluster_sampling(tmp_path):
    db, con = _crawl(tmp_path)
    from sitewide import near_duplicate_clusters

    clusters = near_duplicate_clusters(con)
    assert len(jev.doorway_items(con, clusters, per_cluster=2)) == 2
    assert len(jev.doorway_items(con, clusters)) == 4


def test_hub_page_without_location_is_not_judged(tmp_path):
    db, con = _crawl(tmp_path)
    clusters = [{"shape": "/local/seo-in-{*}/", "size": 2,
                 "urls": ["https://e.com/local/seo-in-carlton/", "https://e.com/local/"]}]
    ids = [i for i, _, _ in jev.doorway_items(con, clusters)]
    assert ids == ["https://e.com/local/seo-in-carlton/"]
