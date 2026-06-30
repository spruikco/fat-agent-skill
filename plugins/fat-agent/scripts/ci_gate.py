#!/usr/bin/env python3
"""
pre-deploy CI gate for FAT Agent scored audit output.

checks audit scores against configurable thresholds and priority filters.

usage:
    python ci_gate.py --scores scores.json --threshold 70 --fail-on P0

exit codes:
    0 = pass
    1 = score below threshold
    2 = priority findings found
"""

import argparse
import json
import sys


def check_score(scores, threshold):
    """check overall score against threshold.

    returns (passed: bool, reason: str).
    """
    # overall is nested ({"overall": {"score": N}}); fall back to legacy flat key.
    overall_obj = scores.get("overall")
    if isinstance(overall_obj, dict) and isinstance(
        overall_obj.get("score"), (int, float)
    ):
        overall = overall_obj["score"]
    else:
        overall = scores.get("overall_score", 0)
    overall = overall if isinstance(overall, (int, float)) else 0
    if overall >= threshold:
        return True, ""
    return False, f"score {overall} is below threshold {threshold}"


def check_priority_findings(scores, fail_on):
    """check for findings at the specified priority level.

    returns (passed: bool, matching_findings: list).
    """
    if fail_on is None:
        return True, []

    # The grade-cap exposes blocking P0/P1 counts on overall.blocking; use those
    # (top-level "findings" isn't emitted by calculate-score). Fall back to legacy.
    overall_obj = scores.get("overall", {})
    blocking = overall_obj.get("blocking", {}) if isinstance(overall_obj, dict) else {}
    count = 0
    if fail_on == "P0":
        count = blocking.get("p0", 0)
    elif fail_on == "P1":
        count = blocking.get("p0", 0) + blocking.get("p1", 0)
    if count:
        return False, [{"priority": fail_on, "count": count}]

    findings = scores.get("findings", [])
    matched = [f for f in findings if f.get("priority") == fail_on]
    if matched:
        return False, matched
    return True, []


def build_arg_parser():
    """build the cli argument parser."""
    parser = argparse.ArgumentParser(
        description="pre-deploy CI gate for FAT Agent audit scores"
    )
    parser.add_argument(
        "--scores",
        required=True,
        help="path to scored JSON output file",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=70,
        help="minimum overall score to pass (default: 70)",
    )
    parser.add_argument(
        "--fail-on",
        default=None,
        help="fail if any findings at this priority level exist (e.g. P0)",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    with open(args.scores, "r") as f:
        scores = json.load(f)

    score_passed, score_reason = check_score(scores, args.threshold)
    priority_passed, priority_findings = check_priority_findings(scores, args.fail_on)

    overall_pass = score_passed and priority_passed

    # priority failure takes precedence for exit code
    if not priority_passed:
        exit_code = 2
        reason = f"{len(priority_findings)} {args.fail_on} finding(s) found"
    elif not score_passed:
        exit_code = 1
        reason = score_reason
    else:
        exit_code = 0
        reason = ""

    summary = {
        "pass": overall_pass,
        "score": scores.get("overall_score", 0),
        "threshold": args.threshold,
        "priority_findings": priority_findings,
        "reason": reason,
    }

    print(json.dumps(summary))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
