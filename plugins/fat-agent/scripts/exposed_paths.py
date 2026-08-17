#!/usr/bin/env python3
"""Opt-in probe for well-known exposed/sensitive paths (post-launch QA).

Deploys routinely leak files that were never meant to be public: a committed
``.env``, an exposed ``.git`` directory, a leftover database backup, a
``phpinfo()`` page. This script checks a fixed, curated list of well-known
paths on ONE origin and reports what is reachable.

Authorisation & safety
-----------------------
This makes live requests, so it is **opt-in and same-origin only**, for sites
you own or are explicitly authorised to audit:

- Requires ``--confirm`` (or ``FAT_ALLOW_ACTIVE_PROBE=1``). Without it the
  script exits 0 with ``{"available": false}`` and does nothing.
- Only the curated list below is requested — no fuzzing, no brute force, no
  parameter tampering. One GET per path, a polite delay between requests.
- An SSRF guard blocks private / loopback / link-local / metadata hosts
  (``--allow-private`` for authorised staging/intranet audits only).
- Never follows cross-origin redirects off the target host.

It is a lightweight hygiene check (a few dozen GETs), not a vulnerability
scanner. Findings (module ``exposed_paths``) merge into the FAT punch list.

Uses only stdlib. Works on Python 3.8+.

Usage
-----
    python scripts/exposed_paths.py --url https://example.com --confirm \
        --output ./.fat-work/exposed_paths.json
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# (path, label, priority, why). Priority reflects worst-case exposure.
SENSITIVE_PATHS = [
    ("/.env", "Environment file", "P0", "Often holds live DB/API credentials."),
    ("/.env.local", "Local env file", "P0", "Same risk as .env."),
    ("/.env.production", "Production env file", "P0", "Production credentials."),
    ("/.git/config", "Git config", "P0", "Exposed .git lets the whole repo be reconstructed."),
    ("/.git/HEAD", "Git HEAD", "P0", "Confirms a fetchable .git directory."),
    ("/.svn/entries", "SVN metadata", "P1", "Source disclosure via exposed SVN."),
    ("/.hg/requires", "Mercurial metadata", "P1", "Source disclosure via exposed Hg."),
    ("/wp-config.php.bak", "WordPress config backup", "P0", "DB credentials in a served backup."),
    ("/config.php.bak", "PHP config backup", "P0", "Credentials in a served backup."),
    ("/.aws/credentials", "AWS credentials", "P0", "Cloud account keys."),
    ("/.npmrc", "npm config", "P1", "May contain registry auth tokens."),
    ("/.dockerenv", "Docker marker", "P3", "Container internals hint."),
    ("/docker-compose.yml", "Compose file", "P1", "Service topology + sometimes secrets."),
    ("/backup.zip", "Site backup archive", "P1", "Full-site archive left in webroot."),
    ("/backup.sql", "SQL dump", "P0", "Database dump left in webroot."),
    ("/db.sql", "SQL dump", "P0", "Database dump left in webroot."),
    ("/dump.sql", "SQL dump", "P0", "Database dump left in webroot."),
    ("/phpinfo.php", "phpinfo()", "P1", "Leaks full PHP/server configuration."),
    ("/info.php", "phpinfo()", "P1", "Leaks full PHP/server configuration."),
    ("/server-status", "Apache server-status", "P2", "Exposes request/traffic internals."),
    ("/.DS_Store", "macOS directory index", "P3", "Leaks the directory listing."),
    ("/.vscode/settings.json", "Editor config", "P3", "May leak paths/tokens."),
    ("/config.json", "App config", "P2", "May contain secrets depending on app."),
    ("/.well-known/security.txt", "security.txt", "INFO", "Good-practice contact file (presence is positive)."),
]

_BENIGN_STATUS = {404, 401, 403, 410}


def host_is_blocked(host, allow_private=False):
    """True if the host resolves to a private / loopback / link-local address."""
    if not host:
        return True
    if allow_private:
        return False
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return True
    except Exception:
        return False
    return False


def _probe(url, timeout=8):
    """GET a single URL, no redirect following. Returns (status, length, ctype).

    Overridable in tests. A network error yields status None.
    """

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(
        url, headers={"User-Agent": "fat-agent-exposed-paths/1.0"}, method="GET"
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read(4096)
            return (
                resp.status,
                len(body),
                resp.headers.get("Content-Type", ""),
                body,
            )
    except urllib.error.HTTPError as e:
        return (e.code, 0, "", b"")
    except Exception:
        return (None, 0, "", b"")


def _looks_like_real_hit(path, status, ctype, body):
    """Filter soft-404s: a 200 that's actually the styled HTML error page.

    Sensitive files are plain text / octet-stream, not ``text/html`` app shells.
    A ``.git/HEAD`` should literally start with ``ref:``; a 200 serving an HTML
    SPA for everything is not a real exposure.
    """
    if status != 200:
        return False
    low_ctype = (ctype or "").lower()
    if path == "/.git/HEAD":
        return body.strip().startswith(b"ref:") or body.strip().startswith(b"ref ")
    if path == "/.git/config":
        return b"[core]" in body
    if path.endswith(".sql"):
        return "text/html" not in low_ctype
    if path in ("/.env", "/.env.local", "/.env.production"):
        # env files are key=value text, never an HTML page
        return "text/html" not in low_ctype and b"<html" not in body.lower()
    return True


def scan(url, allow_private=False, delay=0.4, probe=None, paths=None):
    probe = probe or _probe
    paths = paths if paths is not None else SENSITIVE_PATHS
    parsed = urllib.parse.urlparse(url)
    base = "{0.scheme}://{0.netloc}".format(parsed)
    host = parsed.hostname

    if host_is_blocked(host, allow_private):
        return {
            "available": False,
            "reason": "blocked: private/internal host (SSRF guard). "
            "Use --allow-private only for authorised staging/intranet audits.",
        }

    exposed = []
    security_txt_present = False
    for i, (path, label, priority, why) in enumerate(paths):
        target = base + path
        status, length, ctype, body = probe(target)
        if path == "/.well-known/security.txt" and status == 200:
            security_txt_present = True
            if delay:
                time.sleep(delay)
            continue
        if priority != "INFO" and _looks_like_real_hit(path, status, ctype, body):
            exposed.append(
                {
                    "path": path,
                    "label": label,
                    "priority": priority,
                    "status": status,
                    "content_type": ctype,
                    "why": why,
                }
            )
        if delay and i < len(paths) - 1:
            time.sleep(delay)

    return {
        "available": True,
        "base": base,
        "paths_checked": len(paths),
        "exposed": exposed,
        "security_txt_present": security_txt_present,
        "findings": build_findings(exposed, security_txt_present),
    }


def build_findings(exposed, security_txt_present):
    findings = []
    for item in exposed:
        findings.append(
            {
                "priority": item["priority"],
                "title": "Exposed sensitive path: %s (%s)"
                % (item["path"], item["label"]),
                "description": "%s Returned HTTP %s. %s"
                % (item["label"], item["status"], item["why"]),
                "fix": _fix_for(item["path"]),
                "effort": "low",
                "module": "exposed_paths",
            }
        )
    if not security_txt_present:
        findings.append(
            {
                "priority": "P3",
                "title": "No /.well-known/security.txt",
                "description": "No security.txt found. It gives researchers a clear, "
                "standard way to report vulnerabilities responsibly.",
                "fix": "Publish /.well-known/security.txt with a Contact and Expires "
                "field (see securitytxt.org).",
                "effort": "low",
                "module": "exposed_paths",
            }
        )
    return findings


def _fix_for(path):
    if path.startswith("/.git") or path.startswith("/.svn") or path.startswith("/.hg"):
        return (
            "Block VCS directories at the edge (deny /.git, /.svn, /.hg) and never "
            "deploy them — build from CI artefacts, not a working checkout."
        )
    if path.startswith("/.env") or "config" in path or path.endswith(".bak"):
        return (
            "Remove the file from the webroot and rotate every credential in it. "
            "Keep config outside the served directory / in environment variables."
        )
    if path.endswith(".sql") or path.endswith(".zip"):
        return "Delete the archive/dump from the webroot; move backups off the web server."
    if path in ("/phpinfo.php", "/info.php"):
        return "Delete the file — it should never ship to production."
    if path == "/server-status":
        return "Restrict mod_status to localhost / trusted IPs, or disable it."
    return "Remove the file from the public webroot or block it at the edge."


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Opt-in probe for exposed sensitive paths (same-origin, authorised sites only)"
    )
    parser.add_argument("--url", required=True, help="Target site (one origin)")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required: confirm you own or are authorised to probe this site",
    )
    parser.add_argument(
        "--allow-private",
        action="store_true",
        help="Permit private/internal hosts (authorised staging/intranet only)",
    )
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--output", help="Write the full JSON result to a file")
    args = parser.parse_args(argv)

    confirmed = args.confirm or os.environ.get("FAT_ALLOW_ACTIVE_PROBE") == "1"
    if not confirmed:
        print(
            json.dumps(
                {
                    "available": False,
                    "reason": "Active probing is opt-in. Re-run with --confirm "
                    "(only on sites you own or are authorised to audit).",
                },
                indent=2,
            )
        )
        return 0

    result = scan(args.url, allow_private=args.allow_private, delay=args.delay)
    if args.output and result.get("available"):
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
