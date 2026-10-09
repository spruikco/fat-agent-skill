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
same page maps to the same id across runs. Page-level scores files carry the
audited page (`page_url`, or `update --page`); findings from a page other than
the site URL also hash the page, and auto-resolution only touches items from
the page that was re-scanned. Merging audits of several pages of one site
therefore never resolves page A's findings because page B did not repeat them.
Items written before page scoping (no `page` field) are adopted by the first
page that reports them again, and are auto-resolved only by a rescan of the
site URL itself.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

DEFAULT_PATH = os.path.join(".fat-work", "punchlist.json")

CORE_MODULES = ("seo", "security", "accessibility", "performance")

# summary-bucket fallback for scores files without a flat findings list
SUMMARY_PRIORITY = {"critical": "P0", "high": "P1", "medium": "P2", "low": "P3"}

OPEN = "open"
RESOLVED = "resolved"
WONTFIX = "wontfix"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def finding_id(module: str, title: str, page: str = "") -> str:
    """Stable short id for a finding: hash of module + title (+ page, when the
    finding belongs to a page other than the site URL)."""
    raw = f"{module or 'core'}|{(title or '').strip()}"
    if page:
        raw += f"|{page}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def normalise_page(url: str) -> str:
    """Comparable form of a page URL: lower-case scheme/host, no fragment, no
    trailing slash (the root stays '/')."""
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return url
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    )


def _item_key(item: dict) -> tuple:
    return (
        item.get("module") or "core",
        (item.get("title") or "").strip(),
        item.get("page") or "",
    )


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
    scanned = set()
    # Core categories count as scanned only when this scores file actually
    # contains them — module-only files (sitewide/content-engine/ga4 JSON)
    # must not auto-resolve core findings they never re-checked.
    if isinstance(scores.get("seo"), dict) and "score" in scores["seo"]:
        scanned |= set(CORE_MODULES)
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


def update_punchlist(
    punch: dict, scores: dict, url: str = "", now: str = "", page: str = ""
) -> dict:
    """Merge current findings into the punch list. Returns a stats dict.

    `page` (or the scores file's `page_url`) scopes the merge to one audited
    page: only that page's items can auto-resolve.
    """
    now = now or utc_now()
    page = normalise_page(page or scores.get("page_url") or "")
    site = normalise_page(url or punch.get("url") or "")
    id_page = "" if (not page or page == site) else page
    scanned = scanned_modules(scores)

    current = []
    for f in extract_findings(scores):
        f = dict(f)
        f["id"] = finding_id(f["module"], f["title"], id_page)
        if page:
            f["page"] = page
        current.append(f)

    by_key = {}
    by_id = {}
    for item in punch["items"]:
        by_key.setdefault(_item_key(item), item)
        by_id.setdefault(item["id"], item)
    matched = set()

    stats = {"new": 0, "still_open": 0, "resolved": 0, "reopened": 0, "skipped": 0}

    for f in current:
        key = _item_key(f)
        item = by_key.get(key)
        if item is None and page:
            # adopt an item written before page scoping (no page recorded)
            legacy = by_key.get((key[0], key[1], ""))
            if legacy is not None and "page" not in legacy:
                item = legacy
                item["page"] = page
                by_key.pop((key[0], key[1], ""), None)
                by_key[key] = item
        if item is None:
            item = by_id.get(f["id"])
        if item is None:
            f.update({"status": OPEN, "first_seen": now, "last_seen": now, "notes": []})
            punch["items"].append(f)
            by_key[key] = f
            by_id.setdefault(f["id"], f)
            matched.add(id(f))
            stats["new"] += 1
            continue
        if id(item) in matched:
            continue
        matched.add(id(item))
        item["last_seen"] = now
        # refresh mutable fields — priorities/wording can be recalibrated upstream
        for k in ("priority", "description", "fix", "effort"):
            if f.get(k):
                item[k] = f[k]
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

    for item in punch["items"]:
        if id(item) in matched or item["status"] != OPEN:
            continue
        item_page = item.get("page")
        if page:
            # legacy (unscoped) items only resolve on a rescan of the site URL
            in_scope = item_page == page or (item_page is None and page == site)
        else:
            in_scope = not item_page
        if in_scope and item.get("module", "core") in scanned:
            item["status"] = RESOLVED
            item["resolved_at"] = now
            item.setdefault("notes", []).append(
                {
                    "at": now,
                    "text": "Auto-resolved: absent from a rescan of its module"
                    + (" on this page." if item_page else "."),
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
            where = f" [{i['page']}]" if i.get("page") else ""
            lines.append(
                f"  {i['id']}  {i['title']} ({i['module']}){where}{effort}{notes}"
            )
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
    p_update.add_argument(
        "--page",
        default="",
        help="page this scores file covers (default: its page_url). Only that "
        "page's items auto-resolve",
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
        stats = update_punchlist(punch, scores, url=args.url, page=args.page)
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
