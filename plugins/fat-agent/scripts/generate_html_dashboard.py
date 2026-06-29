#!/usr/bin/env python3
"""
generate_html_dashboard.py — Generate self-contained HTML dashboard reports.

Uses string.Template (stdlib only, no Jinja2) to produce a single HTML file
with inline CSS, embedded chart images, and colour-coded grades.

Usage:
    python generate_html_dashboard.py --scores scores.json --url example.com --output-dir ./reports
    python generate_html_dashboard.py --scores scores.json --url example.com --output-dir ./reports --client-facing
    python generate_html_dashboard.py --scores scores.json --url example.com --output-dir ./reports --charts-dir ./charts

Options:
    --scores FILE       Path to scored JSON
    --url URL           The audited site URL
    --output-dir DIR    Output directory (default: ./reports)
    --client-facing     Simplify language, hide code snippets
    --charts-dir DIR    Directory containing chart PNG images to embed as base64
"""

import os
import json
import argparse
import base64
import re
import glob
from string import Template
from datetime import date

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "templates"
)


def grade_from_score(score: int) -> str:
    """Return letter grade from numeric score."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def _colour_for_grade(grade: str) -> str:
    """Return CSS colour hex for a grade."""
    return {
        "A": "#16a34a",
        "B": "#2563eb",
        "C": "#ca8a04",
        "D": "#ea580c",
        "F": "#dc2626",
    }.get(grade, "#64748b")


def _strip_code_snippets(text: str) -> str:
    """Remove <code>...</code> blocks and their content from a string."""
    return re.sub(r"<code>.*?</code>", "", text, flags=re.DOTALL).strip()


def _build_findings_table(findings: list, client_facing: bool = False) -> str:
    """Build HTML table rows for findings."""
    if not findings:
        return '<table><thead><tr><th>Category</th><th>Issue</th><th>Priority</th></tr></thead><tbody><tr><td colspan="3" style="text-align:center;color:#94a3b8;">No findings</td></tr></tbody></table>'

    rows = []
    for f in findings:
        cat = f.get("category", "")
        issue = f.get("issue", "")
        priority = f.get("priority", "")
        detail = f.get("detail", "")

        if client_facing:
            detail = _strip_code_snippets(detail)
            issue = _strip_code_snippets(issue)

        priority_class = f"priority-{priority.lower()}" if priority else ""
        display_text = issue
        if detail and not client_facing:
            display_text = f"{issue}<br><small style='color:#64748b'>{detail}</small>"
        elif detail and client_facing:
            display_text = (
                f"{issue}<br><small style='color:#64748b'>{detail}</small>"
                if detail
                else issue
            )

        rows.append(
            f"<tr><td>{cat}</td><td>{display_text}</td>"
            f'<td class="{priority_class}">{priority}</td></tr>'
        )

    return (
        "<table>"
        "<thead><tr><th>Category</th><th>Issue</th><th>Priority</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


def _build_module_scores_section(module_scores: dict) -> str:
    """Build the module scores HTML section."""
    if not module_scores:
        return ""

    rows = []
    for key, info in sorted(
        module_scores.items(), key=lambda x: x[1].get("score", 0), reverse=True
    ):
        score = info.get("score", 0)
        label = info.get("label", key)
        grade = grade_from_score(score)
        rows.append(
            f'<div class="module-row">'
            f'<span class="module-label">{label}</span>'
            f'<div class="module-bar"><div class="fill grade-{grade.lower()}" style="width:{score}%"></div></div>'
            f'<span class="module-value">{score}</span>'
            f"</div>"
        )

    return (
        '<div class="module-scores">'
        "<h2>Module Scores</h2>" + "".join(rows) + "</div>"
    )


def _build_charts_section(charts_dir: str) -> str:
    """Embed chart PNGs as base64 images."""
    if not charts_dir or not os.path.isdir(charts_dir):
        return ""

    images = []
    for png_path in sorted(glob.glob(os.path.join(charts_dir, "*.png"))):
        with open(png_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        name = os.path.splitext(os.path.basename(png_path))[0].replace("_", " ").title()
        images.append(
            f"<div><h3>{name}</h3>"
            f'<img src="data:image/png;base64,{b64}" alt="{name}"></div>'
        )

    if not images:
        return ""

    return '<div class="charts"><h2>Charts</h2>' + "".join(images) + "</div>"


def generate_dashboard(
    scores: dict,
    url: str,
    output_dir: str,
    charts_dir: str = None,
    client_facing: bool = False,
    modules: list = None,
) -> str:
    """
    Generate a self-contained HTML dashboard report.

    Returns the path to the generated HTML file.
    """
    os.makedirs(output_dir, exist_ok=True)

    overall_score = scores.get("overall_score", 0)
    seo_score = scores.get("seo_score", 0)
    security_score = scores.get("security_score", 0)
    accessibility_score = scores.get("accessibility_score", 0)
    performance_score = scores.get("performance_score", 0)
    findings = scores.get("findings", [])
    module_scores = scores.get("module_scores", {})

    overall_grade = grade_from_score(overall_score)
    seo_grade = grade_from_score(seo_score)
    security_grade = grade_from_score(security_score)
    accessibility_grade = grade_from_score(accessibility_score)
    performance_grade = grade_from_score(performance_score)

    css_path = os.path.join(TEMPLATES_DIR, "dashboard.css")
    with open(css_path, "r") as f:
        css = f.read()

    template_path = os.path.join(TEMPLATES_DIR, "dashboard.html")
    with open(template_path, "r") as f:
        template_str = f.read()

    tmpl = Template(template_str)

    html = tmpl.safe_substitute(
        css=css,
        url=url,
        date=date.today().isoformat(),
        overall_score=overall_score,
        overall_grade=overall_grade,
        overall_grade_lower=overall_grade.lower(),
        seo_score=seo_score,
        seo_grade_lower=seo_grade.lower(),
        security_score=security_score,
        security_grade_lower=security_grade.lower(),
        accessibility_score=accessibility_score,
        accessibility_grade_lower=accessibility_grade.lower(),
        performance_score=performance_score,
        performance_grade_lower=performance_grade.lower(),
        findings_table=_build_findings_table(findings, client_facing=client_facing),
        module_scores_section=_build_module_scores_section(module_scores),
        charts_section=_build_charts_section(charts_dir) if charts_dir else "",
    )

    output_path = os.path.join(output_dir, "FAT_Dashboard.html")
    with open(output_path, "w") as f:
        f.write(html)

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate HTML dashboard report")
    parser.add_argument("--scores", required=True, help="Path to scored JSON file")
    parser.add_argument("--url", required=True, help="Audited site URL")
    parser.add_argument("--output-dir", default="./reports", help="Output directory")
    parser.add_argument(
        "--client-facing",
        action="store_true",
        help="Client-facing mode: simpler language, no code",
    )
    parser.add_argument(
        "--charts-dir", default=None, help="Directory with chart PNGs to embed"
    )
    args = parser.parse_args()

    with open(args.scores, "r") as f:
        scores = json.load(f)

    output = generate_dashboard(
        scores=scores,
        url=args.url,
        output_dir=args.output_dir,
        charts_dir=args.charts_dir,
        client_facing=args.client_facing,
    )
    print(f"Dashboard generated: {output}")


if __name__ == "__main__":
    main()
