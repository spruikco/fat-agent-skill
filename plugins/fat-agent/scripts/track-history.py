#!/usr/bin/env python3
"""
FAT Agent Historical Audit Tracker
Reads/writes .fat-history.json to track audit scores over time.

Usage:
    python track-history.py --save <scores.json>    Append a new audit entry
    python track-history.py --show                  Print history table
    python track-history.py --diff                  Compare latest vs previous
    python track-history.py --trend                 Show score trend

Options:
    --file <path>   Path to history file (default: .fat-history.json)
    --url <url>     URL being audited (required for --save)
"""

import sys
import json
import os
from datetime import datetime, timezone


DEFAULT_HISTORY_FILE = ".fat-history.json"

# Use ASCII-safe arrows for Windows compatibility
UP_ARROW = "^"
DOWN_ARROW = "v"
RIGHT_ARROW = "->"


def load_history(filepath: str) -> dict:
    """Load history from JSON file, or return empty structure."""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"url": "", "history": []}


def save_history(filepath: str, history: dict):
    """Write history to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def add_entry(history: dict, scores: dict, url: str = "") -> dict:
    """Append a new audit entry to the history."""
    overall = scores.get("overall", {})
    seo = scores.get("seo", {}).get("score", 0)
    security = scores.get("security", {}).get("score", 0)
    a11y = scores.get("accessibility", {}).get("score", 0)
    perf = scores.get("performance", {}).get("score", 0)
    overall_score = overall.get("score", 0)
    grade = overall.get("grade", "?")

    summary = scores.get("summary", {})
    issues_found = summary.get("issues_found", 0)

    # Calculate issues resolved vs previous entry
    issues_resolved = 0
    if history["history"]:
        prev = history["history"][-1]
        prev_issues = prev.get("issues_found", 0)
        issues_resolved = max(0, prev_issues - issues_found)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scores": {
            "seo": seo,
            "security": security,
            "accessibility": a11y,
            "performance": perf,
            "overall": overall_score,
        },
        "grade": grade,
        "issues_found": issues_found,
        "issues_resolved": issues_resolved,
    }

    if url:
        history["url"] = url
    history["history"].append(entry)
    return entry


def format_table(history: dict) -> str:
    """Format history as an ASCII table."""
    entries = history.get("history", [])
    if not entries:
        return "No audit history found."

    url = history.get("url", "Unknown URL")
    lines = [
        f"FAT Audit History: {url}",
        f"{'='*80}",
        f"{'Date':<22} {'Grade':>5} {'Overall':>7} {'SEO':>5} {'Sec':>5} {'A11y':>5} {'Perf':>5} {'Issues':>6}",
        f"{'-'*80}",
    ]

    for entry in entries:
        ts = entry.get("timestamp", "")
        # Parse ISO timestamp, show date + time
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            date_str = ts[:16] if ts else "Unknown"

        scores = entry.get("scores", {})
        lines.append(
            f"{date_str:<22} "
            f"{entry.get('grade', '?'):>5} "
            f"{scores.get('overall', 0):>7} "
            f"{scores.get('seo', 0):>5} "
            f"{scores.get('security', 0):>5} "
            f"{scores.get('accessibility', 0):>5} "
            f"{scores.get('performance', 0):>5} "
            f"{entry.get('issues_found', 0):>6}"
        )

    lines.append(f"{'='*80}")
    lines.append(f"Total audits: {len(entries)}")
    return "\n".join(lines)


def format_diff(history: dict) -> str:
    """Compare latest vs previous entry."""
    entries = history.get("history", [])
    if len(entries) < 2:
        return "Need at least 2 audit entries for comparison."

    latest = entries[-1]
    previous = entries[-2]
    latest_scores = latest.get("scores", {})
    prev_scores = previous.get("scores", {})

    # Parse timestamps
    try:
        latest_dt = datetime.fromisoformat(latest["timestamp"].replace("Z", "+00:00"))
        prev_dt = datetime.fromisoformat(previous["timestamp"].replace("Z", "+00:00"))
        latest_date = latest_dt.strftime("%Y-%m-%d")
        prev_date = prev_dt.strftime("%Y-%m-%d")
    except (ValueError, KeyError):
        latest_date = "Latest"
        prev_date = "Previous"

    lines = [
        f"FAT Audit Comparison: {history.get('url', 'Unknown')}",
        f"{'='*60}",
        f"{'Category':<18} {prev_date:>12} {latest_date:>12} {'Delta':>8}",
        f"{'-'*60}",
    ]

    categories = [
        ("SEO", "seo"),
        ("Security", "security"),
        ("Accessibility", "accessibility"),
        ("Performance", "performance"),
        ("Overall", "overall"),
    ]

    for label, key in categories:
        prev_val = prev_scores.get(key, 0)
        latest_val = latest_scores.get(key, 0)
        delta = latest_val - prev_val
        arrow = UP_ARROW if delta > 0 else (DOWN_ARROW if delta < 0 else RIGHT_ARROW)
        delta_str = f"{arrow} {delta:+d}"
        lines.append(f"{label:<18} {prev_val:>12} {latest_val:>12} {delta_str:>8}")

    lines.append(f"{'-'*60}")
    lines.append(f"Grade: {previous.get('grade', '?')} {RIGHT_ARROW} {latest.get('grade', '?')}")
    lines.append(f"Issues: {previous.get('issues_found', 0)} {RIGHT_ARROW} {latest.get('issues_found', 0)}")

    resolved = latest.get("issues_resolved", 0)
    if resolved > 0:
        lines.append(f"Issues resolved since last audit: {resolved}")

    return "\n".join(lines)


def format_trend(history: dict) -> str:
    """Show score trend with directional arrows."""
    entries = history.get("history", [])
    if not entries:
        return "No audit history found."
    if len(entries) < 2:
        return "Need at least 2 entries for trend analysis."

    lines = [
        f"FAT Score Trend: {history.get('url', 'Unknown')}",
        f"{'='*50}",
    ]

    categories = [
        ("SEO", "seo"),
        ("Security", "security"),
        ("Accessibility", "accessibility"),
        ("Performance", "performance"),
        ("Overall", "overall"),
    ]

    for label, key in categories:
        scores = [e.get("scores", {}).get(key, 0) for e in entries]
        first = scores[0]
        last = scores[-1]
        delta = last - first
        arrow = UP_ARROW if delta > 0 else (DOWN_ARROW if delta < 0 else RIGHT_ARROW)

        # Simple ASCII sparkline
        if len(scores) >= 2:
            min_s = min(scores) if min(scores) != max(scores) else min(scores) - 1
            max_s = max(scores) if max(scores) != min_s else min_s + 1
            spark = ""
            for s in scores[-10:]:  # Last 10 entries
                normalised = (s - min_s) / (max_s - min_s) if max_s > min_s else 0.5
                if normalised >= 0.75:
                    spark += "#"
                elif normalised >= 0.5:
                    spark += "="
                elif normalised >= 0.25:
                    spark += "-"
                else:
                    spark += "_"
        else:
            spark = ""

        lines.append(f"{label:<15} {first:>3} {arrow} {last:>3} ({delta:+d})  {spark}")

    lines.append(f"{'='*50}")
    lines.append(f"Audits tracked: {len(entries)}")

    return "\n".join(lines)


def main():
    history_file = DEFAULT_HISTORY_FILE
    url = ""
    action = None
    scores_file = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--file" and i + 1 < len(args):
            history_file = args[i + 1]
            i += 2
        elif args[i] == "--url" and i + 1 < len(args):
            url = args[i + 1]
            i += 2
        elif args[i] == "--save" and i + 1 < len(args):
            action = "save"
            scores_file = args[i + 1]
            i += 2
        elif args[i] == "--show":
            action = "show"
            i += 1
        elif args[i] == "--diff":
            action = "diff"
            i += 1
        elif args[i] == "--trend":
            action = "trend"
            i += 1
        else:
            i += 1

    # Also support piped input for --save
    if action == "save":
        if scores_file == "-" or scores_file is None:
            scores = json.load(sys.stdin)
        else:
            with open(scores_file, "r", encoding="utf-8") as f:
                scores = json.load(f)

        history = load_history(history_file)
        entry = add_entry(history, scores, url=url)
        save_history(history_file, history)
        print(f"Saved audit entry: Grade {entry['grade']}, Score {entry['scores']['overall']}/100")
        print(f"History file: {os.path.abspath(history_file)}")

    elif action == "show":
        history = load_history(history_file)
        print(format_table(history))

    elif action == "diff":
        history = load_history(history_file)
        print(format_diff(history))

    elif action == "trend":
        history = load_history(history_file)
        print(format_trend(history))

    else:
        print("Usage:")
        print("  track-history.py --save <scores.json>  Save a new audit entry")
        print("  track-history.py --show                Print history table")
        print("  track-history.py --diff                Compare latest vs previous")
        print("  track-history.py --trend               Show score trend")
        print("")
        print("Options:")
        print("  --file <path>   History file (default: .fat-history.json)")
        print("  --url <url>     URL being audited")
        sys.exit(1)


if __name__ == "__main__":
    main()
