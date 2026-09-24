"""Tests for fat_hq.py (optional FAT HQ uploads) against a local fake HQ."""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import fat_hq

GOOD_KEY = "fathq_testkey"
RECEIVED = []


class FakeHQ(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authed(self):
        if self.headers.get("Authorization") != "Bearer " + GOOD_KEY:
            self._send(401, {"error": "unauthorized", "message": "Missing or invalid FAT HQ key"})
            return False
        return True

    def do_GET(self):
        if not self._authed():
            return
        if self.path == "/v1/me":
            return self._send(200, {"email": "a@b.com", "plan": "pro", "sites": 1, "site_limit": 10})
        if self.path == "/v1/sites":
            return self._send(200, {"sites": [{"host": "e.com", "score": 80, "grade": "B", "schedule": "weekly", "last_audit_at": "2026-09-24"}]})
        self._send(404, {})

    def do_POST(self):
        if not self._authed():
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        RECEIVED.append(body)
        self._send(201, {"host": "e.com", "score": 80, "grade": "B", "counts": {"P0": 1, "P1": 2, "P2": 3, "P3": 4},
                         "changes": {"fixed": 2, "new": 1, "regressed": 0, "score_delta": -3}, "url": "http://hq/app/sites/x"})


@pytest.fixture()
def hq(tmp_path, monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), FakeHQ)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    monkeypatch.setattr(fat_hq, "CONFIG", str(tmp_path / "home" / "hq.json"))
    monkeypatch.delenv("FAT_HQ_KEY", raising=False)
    monkeypatch.delenv("FAT_HQ_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    RECEIVED.clear()
    yield "http://127.0.0.1:%d" % srv.server_address[1]
    srv.shutdown()


def _work(tmp_path, url="https://e.com/"):
    os.makedirs(tmp_path / ".fat-work", exist_ok=True)
    (tmp_path / ".fat-work" / "scores.json").write_text(json.dumps({"overall": {"score": 80}, "findings": []}))
    (tmp_path / ".fat-work" / "punchlist.json").write_text(json.dumps({"version": 1, "url": url, "items": []}))


def test_upload_without_key_explains(hq, tmp_path):
    _work(tmp_path)
    with pytest.raises(SystemExit) as e:
        fat_hq.main(["upload"])
    assert "fat_hq.py login" in str(e.value)


def test_login_saves_key_and_upload_uses_punchlist_url(hq, tmp_path, capsys):
    _work(tmp_path)
    assert fat_hq.main(["login", GOOD_KEY, "--base", hq]) == 0
    saved = json.loads(open(fat_hq.CONFIG).read())
    assert saved == {"key": GOOD_KEY, "base": hq}
    assert fat_hq.main(["upload"]) == 0
    out = capsys.readouterr().out
    assert "e.com scored 80" in out and "2 fixed, 1 new" in out and "score -3" in out
    assert RECEIVED[0]["url"] == "https://e.com/"
    assert RECEIVED[0]["scores"]["overall"]["score"] == 80
    assert "plugin_version" in RECEIVED[0]


def test_bad_key_is_not_saved(hq, tmp_path):
    with pytest.raises(SystemExit) as e:
        fat_hq.main(["login", "wrong", "--base", hq])
    assert "401" in str(e.value)
    assert not os.path.exists(fat_hq.CONFIG)


def test_env_overrides_and_status(hq, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FAT_HQ_KEY", GOOD_KEY)
    monkeypatch.setenv("FAT_HQ_URL", hq)
    assert fat_hq.main(["status"]) == 0
    assert "e.com" in capsys.readouterr().out


def test_upload_needs_a_url(hq, tmp_path, monkeypatch):
    monkeypatch.setenv("FAT_HQ_KEY", GOOD_KEY)
    monkeypatch.setenv("FAT_HQ_URL", hq)
    _work(tmp_path, url="")
    with pytest.raises(SystemExit) as e:
        fat_hq.main(["upload"])
    assert "--url" in str(e.value)


def test_upload_includes_gsc_dates_when_present(hq, tmp_path, monkeypatch):
    monkeypatch.setenv("FAT_HQ_KEY", GOOD_KEY)
    monkeypatch.setenv("FAT_HQ_URL", hq)
    _work(tmp_path)
    (tmp_path / ".fat-work" / "gsc_dates.json").write_text(json.dumps(
        {"_meta": {}, "data": {"rows": [{"keys": ["2026-09-01"], "clicks": 5, "impressions": 90}, {"keys": ["query"], "clicks": 1}]}}))
    assert fat_hq.main(["upload"]) == 0
    assert RECEIVED[-1]["gsc_daily"] == [{"date": "2026-09-01", "clicks": 5, "impressions": 90}]
    assert fat_hq.main(["upload", "--no-gsc"]) == 0
    assert "gsc_daily" not in RECEIVED[-1]
