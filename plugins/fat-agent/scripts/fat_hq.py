#!/usr/bin/env python3
"""Send FAT Agent audits to FAT HQ (optional hosted dashboard).

FAT HQ keeps every audit, charts the score over time, re-checks sites on a
schedule and emails you when something breaks. The plugin works without it;
this script is only for people who have made an HQ account.

Commands:
  login KEY [--base URL]   Save a plugin key (made at <HQ>/app/keys) to
                           ~/.fat-agent/hq.json and check it works.
  upload [--scores PATH] [--url URL] [--gsc PATH]
                           Upload a scores.json (default ./.fat-work/scores.json).
                           The URL defaults to the one in ./.fat-work/punchlist.json.
                           If ./.fat-work/gsc_dates.json exists (gsc_fetch.py
                           --dimension date), its daily clicks and impressions go
                           too, so HQ can chart traffic against Google updates.
  status                   Show the account, plan and sites HQ knows about.
  logout                   Forget the saved key.

Environment overrides: FAT_HQ_KEY, FAT_HQ_URL. Stdlib only.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "https://fathq.prodimus.com.au"
CONFIG = os.path.join(os.path.expanduser("~"), ".fat-agent", "hq.json")
PLUGIN_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude-plugin", "plugin.json")


def plugin_version() -> str:
    try:
        with open(PLUGIN_JSON, encoding="utf-8") as f:
            return json.load(f).get("version", "")
    except (OSError, ValueError):
        return ""


def load_config() -> dict:
    cfg = {}
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        pass
    if os.environ.get("FAT_HQ_KEY"):
        cfg["key"] = os.environ["FAT_HQ_KEY"]
    if os.environ.get("FAT_HQ_URL"):
        cfg["base"] = os.environ["FAT_HQ_URL"]
    cfg.setdefault("base", DEFAULT_BASE)
    cfg["base"] = cfg["base"].rstrip("/")
    return cfg


def save_config(cfg: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump({"key": cfg["key"], "base": cfg["base"]}, f, indent=2)
    try:
        os.chmod(CONFIG, 0o600)
    except OSError:
        pass


def call(cfg: dict, method: str, path: str, body=None) -> dict:
    if not cfg.get("key"):
        raise SystemExit("No FAT HQ key. Make one at %s/app/keys, then run: python scripts/fat_hq.py login <key>" % cfg["base"])
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(cfg["base"] + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + cfg["key"])
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "FAT-Agent/%s fat_hq.py" % (plugin_version() or "dev"))
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("message", "")
        except ValueError:
            msg = ""
        raise SystemExit("FAT HQ said %s: %s" % (e.code, msg or e.reason))
    except urllib.error.URLError as e:
        raise SystemExit("Could not reach FAT HQ at %s (%s)" % (cfg["base"], e.reason))


def url_from_punchlist(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("url", "") or ""
    except (OSError, ValueError):
        return ""


def load_daily(path: str) -> list:
    """Daily rows from a gsc_fetch.py date export (or MCP wrapper). Empty if absent."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("rows", data.get("data", []))
    if isinstance(data, dict):
        data = data.get("rows", [])
    out = []
    for r in data or []:
        if not isinstance(r, dict):
            continue
        date = r.get("date") or (r.get("keys") or [None])[0]
        if isinstance(date, str) and len(date) >= 10 and date[4] == "-":
            out.append({"date": date[:10], "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0)})
    return out[-1000:]


def cmd_login(args) -> int:
    cfg = load_config()
    cfg["key"] = args.key.strip()
    if args.base:
        cfg["base"] = args.base.rstrip("/")
    me = call(cfg, "GET", "/v1/me")
    save_config(cfg)
    print("Connected to FAT HQ as %s (%s plan, %s of %s sites). Key saved to %s" % (
        me.get("email"), me.get("plan"), me.get("sites"), me.get("site_limit"), CONFIG))
    return 0


def cmd_upload(args) -> int:
    cfg = load_config()
    try:
        with open(args.scores, encoding="utf-8") as f:
            scores = json.load(f)
    except OSError:
        raise SystemExit("No scores file at %s. Run the audit first (it writes .fat-work/scores.json)." % args.scores)
    except ValueError:
        raise SystemExit("%s is not valid JSON" % args.scores)
    url = args.url or url_from_punchlist(args.punchlist)
    if not url:
        raise SystemExit("Which site is this? Pass --url https://example.com")
    payload = {"url": url, "scores": scores, "plugin_version": plugin_version()}
    daily = [] if args.no_gsc else load_daily(args.gsc)
    if daily:
        payload["gsc_daily"] = daily
    res = call(cfg, "POST", "/v1/audits", payload)
    if args.json:
        print(json.dumps(res, indent=2))
        return 0
    c = res.get("counts") or {}
    print("Uploaded to FAT HQ: %s scored %s (%s). P0 %s, P1 %s, P2 %s, P3 %s." % (
        res.get("host"), res.get("score"), res.get("grade"), c.get("P0", 0), c.get("P1", 0), c.get("P2", 0), c.get("P3", 0)))
    ch = res.get("changes")
    if ch:
        delta = ch.get("score_delta")
        print("Since last upload: %s fixed, %s new, %s came back%s." % (
            ch.get("fixed"), ch.get("new"), ch.get("regressed"),
            "" if delta is None else ", score %+d" % delta))
    if res.get("gsc_days"):
        print("Search Console: %s days of clicks and impressions sent." % res["gsc_days"])
    print("Case file: %s" % res.get("url"))
    return 0


def cmd_status(args) -> int:
    cfg = load_config()
    me = call(cfg, "GET", "/v1/me")
    sites = call(cfg, "GET", "/v1/sites").get("sites", [])
    print("%s, %s plan, %s of %s sites (%s)" % (me.get("email"), me.get("plan"), me.get("sites"), me.get("site_limit"), cfg["base"]))
    for s in sites:
        print("  %-40s score %-4s grade %-2s schedule %-7s last %s" % (
            s.get("host"), s.get("score") if s.get("score") is not None else "-", s.get("grade") or "-",
            s.get("schedule"), s.get("last_audit_at") or "never"))
    return 0


def cmd_logout(args) -> int:
    try:
        os.remove(CONFIG)
        print("Forgot the FAT HQ key.")
    except OSError:
        print("No saved key.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fat_hq.py", description="Send FAT Agent audits to FAT HQ.")
    sub = p.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("login", help="save a plugin key")
    lg.add_argument("key")
    lg.add_argument("--base", help="HQ address (default %s)" % DEFAULT_BASE)
    up = sub.add_parser("upload", help="upload a scores.json")
    up.add_argument("--scores", default=os.path.join(".fat-work", "scores.json"))
    up.add_argument("--punchlist", default=os.path.join(".fat-work", "punchlist.json"))
    up.add_argument("--url", help="site URL (defaults to the punch list's)")
    up.add_argument("--gsc", default=os.path.join(".fat-work", "gsc_dates.json"), help="Search Console date export to include")
    up.add_argument("--no-gsc", action="store_true", help="do not send Search Console data")
    up.add_argument("--json", action="store_true", help="print the raw response")
    sub.add_parser("status", help="show account and sites")
    sub.add_parser("logout", help="forget the saved key")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return {"login": cmd_login, "upload": cmd_upload, "status": cmd_status, "logout": cmd_logout}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
