#!/usr/bin/env python3
"""Persistent punch list for FAT audits.

Maintains a `punchlist.json` file (default: `./.fat-work/punchlist.json`) so
audit state survives context compaction, session restarts, and handoffs between
machines or agents. The conversation is disposable; this file is not.

Commands:
  update   Merge the findings from a scores.json (calculate-score.py output)
           into the punch list. New findings open; findings that have vanished
           from a rescanned module auto-resolve; resolved findings that
           reappear are re-opened and flagged as regressions. Findings whose
           module was NOT scanned this run are left untouched (a quick-profile
           rescan must not "resolve" a full-profile finding).
  status   Show open items grouped by priority, plus resolved/wontfix counts.
           `--json` emits the machine-readable form.
  resolve  Manually mark an item resolved (or `--wontfix`), with an optional
           note recording why.
  note     Attach a decision note to an item — the "why we chose this fix"
           layer that otherwise evaporates with the conversation.

Item identity is a stable hash of (module, title), so the same check on the
same page maps to the same id across runs.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

DEFAULT_PATH = os.path.join(".fat-work", "punchlist.json")

CORE_MODULES = ("seo", "security", "accessibility", "performance")

# summary-bucket fallback for scores files without a flat findings list
SUMMARY_PRIORITY = {"critical": "P0", "high": "P1", "medium": "P2", "low": "P3"}

OPEN = "open"
RESOLVED = "resolved"
WONTFIX = "wontfix"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def finding_id(module: str, title: str) -> str:
    """Stable short id for a finding: hash of module + title."""
    raw = f"{module or 'core'}|{(title or '').strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def extract_findings(scores: dict) -> list:
    """Pull a flat findings list out of a scores.json structure.

    Prefers the top-level `findings` list (emitted by calculate-score.py);
    falls back to the `summary` priority buckets for older/bare-pipe shapes.
    Deduplicates by id.
    """
    out: dict[str, dict] = {}

    for f in scores.get("findings") or []:
        if not isinstance(f, dict) or not f.get("title"):
            continue
        fid = finding_id(f.get("module", "core"), f["title"])
        out.setdefault(
            fid,
            {
                "id": fid,
                "module": f.get("module", "core"),
                "priority": f.get("priority", "P3"),
                "title": f["title"],
                "description": f.get("description", ""),
                "fix": f.get("fix", ""),
                "effort": f.get("effort", ""),
            },
        )

    summary = scores.get("summary")
    if isinstance(summary, dict):
        for bucket, priority in SUMMARY_PRIORITY.items():
            for item in summary.get(bucket) or []:
                if not isinstance(item, str) or not item.strip():
                    continue
                fid = finding_id("core", item)
                out.setdefault(
                    fid,
                    {
                        "id": fid,
                        "module": "core",
                        "priority": priority,
                        "title": item.strip(),
                        "description": "",
                        "fix": "",
                        "effort": "",
                    },
                )

    return list(out.values())


def scanned_modules(scores: dict) -> set:
    """Which modules were actually assessed in this scores.json?

    Only findings from these modules may auto-resolve when absent. Security is
    excluded when it was not assessed (no response headers fetched).
    """
    scanned = set(CORE_MODULES)
    scanned.add("core")  # the summary buckets

    security = scores.get("security")
    if isinstance(security, dict) and security.get("assessed") is False:
        scanned.discard("security")

    module_scores = scores.get("module_scores")
    if isinstance(module_scores, dict):
        for mid, result in module_scores.items():
            if isinstance(result, dict) and "error" not in result:
                scanned.add(mid)

    return scanned


def load_punchlist(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data
    return {"version": 1, "url": "", "updated": "", "items": []}


def save_punchlist(path: str, punch: dict) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(punch, f, indent=2, ensure_ascii=False)
        f.write("\n")


def update_punchlist(punch: dict, scores: dict, url: str = "", now: str = "") -> dict:
    """Merge current findings into the punch list. Returns a stats dict."""
    now = now or utc_now()
    current = {f["id"]: f for f in extract_findings(scores)}
    scanned = scanned_modules(scores)
    existing = {item["id"]: item for item in punch["items"]}

    stats = {"new": 0, "still_open": 0, "resolved": 0, "reopened": 0, "skipped": 0}

    for fid, f in current.items():
        item = existing.get(fid)
        if item is None:
            f = dict(f)
            f.update({"status": OPEN, "first_seen": now, "last_seen": now, "notes": []})
            punch["items"].append(f)
            stats["new"] += 1
            continue
        item["last_seen"] = now
        # refresh mutable fields — priorities/wording can be recalibrated upstream
        for key in ("priority", "description", "fix", "effort"):
            if f.get(key):
                item[key] = f[key]
        if item["status"] == RESOLVED:
            item["status"] = OPEN
            item.pop("resolved_at", None)
            item.setdefault("notes", []).append(
                {
                    "at": now,
                    "text": "Regression: finding reappeared after being resolved.",
                }
            )
            stats["reopened"] += 1
        elif item["status"] == OPEN:
            stats["still_open"] += 1

    for fid, item in existing.items():
        if fid in current or item["status"] != OPEN:
            continue
        if item.get("module", "core") in scanned:
            item["status"] = RESOLVED
            item["resolved_at"] = now
            item.setdefault("notes", []).append(
                {
                    "at": now,
                    "text": "Auto-resolved: absent from a rescan of its module.",
                }
            )
            stats["resolved"] += 1
        else:
            stats["skipped"] += 1

    if url:
        punch["url"] = url
    punch["updated"] = now
    return stats


def find_item(punch: dict, item_id: str) -> dict | None:
    for item in punch["items"]:
        if item["id"] == item_id or item["id"].startswith(item_id):
            return item
    return None


def format_status(punch: dict) -> str:
    items = punch["items"]
    open_items = [i for i in items if i["status"] == OPEN]
    resolved = sum(1 for i in items if i["status"] == RESOLVED)
    wontfix = sum(1 for i in items if i["status"] == WONTFIX)

    lines = []
    header = "FAT punch list"
    if punch.get("url"):
        header += f" — {punch['url']}"
    if punch.get("updated"):
        header += f" (updated {punch['updated']})"
    lines.append(header)

    if not open_items:
        lines.append("No open items. ")
    for priority in ("P0", "P1", "P2", "P3"):
        bucket = [i for i in open_items if i.get("priority") == priority]
        if not bucket:
            continue
        lines.append(f"\n{priority} — {len(bucket)} open")
        for i in bucket:
            effort = f" [{i['effort']}]" if i.get("effort") else ""
            notes = (
                f" ({len(i['notes'])} note{'s' if len(i['notes']) != 1 else ''})"
                if i.get("notes")
                else ""
            )
            lines.append(f"  {i['id']}  {i['title']} ({i['module']}){effort}{notes}")
    other = [i for i in open_items if i.get("priority") not in ("P0", "P1", "P2", "P3")]
    for i in other:
        lines.append(f"  {i['id']}  {i['title']} ({i['module']})")

    lines.append(f"\n{len(open_items)} open · {resolved} resolved · {wontfix} wontfix")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="persistent punch list for FAT audits")
    parser.add_argument(
        "--file",
        default=DEFAULT_PATH,
        help=f"punch list path (default: {DEFAULT_PATH})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_update = sub.add_parser("update", help="merge a scores.json into the punch list")
    p_update.add_argument("--scores", required=True, help="path to scores.json")
    p_update.add_argument(
        "--url", default="", help="audited URL (recorded in the file)"
    )

    p_status = sub.add_parser("status", help="show the punch list")
    p_status.add_argument("--json", action="store_true", help="emit raw JSON")

    p_resolve = sub.add_parser("resolve", help="manually mark an item resolved")
    p_resolve.add_argument("id", help="item id (or unique prefix)")
    p_resolve.add_argument(
        "--wontfix", action="store_true", help="mark wontfix instead"
    )
    p_resolve.add_argument("--note", default="", help="why it was resolved")

    p_note = sub.add_parser("note", help="attach a decision note to an item")
    p_note.add_argument("id", help="item id (or unique prefix)")
    p_note.add_argument("--text", required=True, help="the note")

    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    punch = load_punchlist(args.file)

    if args.command == "update":
        with open(args.scores, "r", encoding="utf-8") as f:
            scores = json.load(f)
        stats = update_punchlist(punch, scores, url=args.url)
        save_punchlist(args.file, punch)
        print(
            f"Punch list updated: {stats['new']} new, {stats['still_open']} still open, "
            f"{stats['resolved']} resolved, {stats['reopened']} reopened"
            + (f", {stats['skipped']} not rescanned" if stats["skipped"] else "")
        )
        return 0

    if args.command == "status":
        if args.json:
            print(json.dumps(punch, indent=2, ensure_ascii=False))
        else:
            print(format_status(punch))
        return 0

    # resolve / note need an existing item
    item = find_item(punch, args.id)
    if item is None:
        print(f"No punch list item matching id '{args.id}'", file=sys.stderr)
        return 1

    now = utc_now()
    if args.command == "resolve":
        item["status"] = WONTFIX if args.wontfix else RESOLVED
        item["resolved_at"] = now
        if args.note:
            item.setdefault("notes", []).append({"at": now, "text": args.note})
        save_punchlist(args.file, punch)
        print(f"{item['id']} marked {item['status']}: {item['title']}")
        return 0

    if args.command == "note":
        item.setdefault("notes", []).append({"at": now, "text": args.text})
        save_punchlist(args.file, punch)
        print(f"Note added to {item['id']}: {item['title']}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
