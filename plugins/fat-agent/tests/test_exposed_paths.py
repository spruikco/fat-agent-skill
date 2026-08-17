import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import exposed_paths as ep  # noqa: E402


def make_probe(responses):
    """responses: dict path -> (status, ctype, body_bytes)."""

    def probe(url, timeout=8):
        path = "/" + url.split("/", 3)[3] if url.count("/") >= 3 else "/"
        status, ctype, body = responses.get(path, (404, "text/html", b"Not found"))
        return status, len(body), ctype, body

    return probe


# ---------------------------------------------------------------------------
# gate / SSRF
# ---------------------------------------------------------------------------


def test_main_without_confirm_is_noop(capsys, monkeypatch):
    monkeypatch.delenv("FAT_ALLOW_ACTIVE_PROBE", raising=False)
    rc = ep.main(["--url", "https://example.com"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["available"] is False
    assert "opt-in" in out["reason"].lower()


def test_env_var_confirms(monkeypatch):
    # host_is_blocked would allow example.com; use a fake probe via scan directly
    result = ep.scan(
        "https://example.com",
        probe=make_probe({}),
        delay=0,
    )
    assert result["available"] is True


def test_ssrf_blocks_localhost():
    result = ep.scan("http://127.0.0.1:8080", probe=make_probe({}), delay=0)
    assert result["available"] is False
    assert "SSRF" in result["reason"]


def test_ssrf_allow_private_override():
    result = ep.scan(
        "http://127.0.0.1", probe=make_probe({}), delay=0, allow_private=True
    )
    assert result["available"] is True


# ---------------------------------------------------------------------------
# detection
# ---------------------------------------------------------------------------


def test_exposed_env_file_is_p0():
    probe = make_probe(
        {"/.env": (200, "text/plain", b"DB_PASSWORD=secret\nAPI_KEY=abc")}
    )
    result = ep.scan("https://example.com", probe=probe, delay=0)
    hits = [e for e in result["exposed"] if e["path"] == "/.env"]
    assert hits and hits[0]["priority"] == "P0"
    assert any(
        f["priority"] == "P0" and "/.env" in f["title"] for f in result["findings"]
    )


def test_git_head_requires_ref_prefix():
    # An HTML soft-404 served at 200 must NOT count as a real hit.
    probe = make_probe({"/.git/HEAD": (200, "text/html", b"<html>404</html>")})
    result = ep.scan("https://example.com", probe=probe, delay=0)
    assert not any(e["path"] == "/.git/HEAD" for e in result["exposed"])


def test_git_head_real_hit():
    probe = make_probe({"/.git/HEAD": (200, "text/plain", b"ref: refs/heads/main")})
    result = ep.scan("https://example.com", probe=probe, delay=0)
    assert any(e["path"] == "/.git/HEAD" for e in result["exposed"])


def test_env_html_soft_404_filtered():
    probe = make_probe({"/.env": (200, "text/html", b"<html>not found</html>")})
    result = ep.scan("https://example.com", probe=probe, delay=0)
    assert not any(e["path"] == "/.env" for e in result["exposed"])


def test_clean_site_only_security_txt_finding():
    result = ep.scan("https://example.com", probe=make_probe({}), delay=0)
    assert result["exposed"] == []
    # security.txt absent → one P3 finding
    assert result["findings"] == [
        f for f in result["findings"] if f["priority"] == "P3"
    ]
    assert any("security.txt" in f["title"] for f in result["findings"])


def test_security_txt_present_no_finding():
    probe = make_probe(
        {"/.well-known/security.txt": (200, "text/plain", b"Contact: mailto:x@y.com")}
    )
    result = ep.scan("https://example.com", probe=probe, delay=0)
    assert result["security_txt_present"] is True
    assert not any("security.txt" in f["title"] for f in result["findings"])


def test_sql_dump_detected():
    probe = make_probe({"/backup.sql": (200, "application/octet-stream", b"INSERT INTO")})
    result = ep.scan("https://example.com", probe=probe, delay=0)
    assert any(e["path"] == "/backup.sql" for e in result["exposed"])


def test_findings_carry_module_tag():
    probe = make_probe({"/.env": (200, "text/plain", b"X=1")})
    result = ep.scan("https://example.com", probe=probe, delay=0)
    assert all(f["module"] == "exposed_paths" for f in result["findings"])
