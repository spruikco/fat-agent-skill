#!/usr/bin/env python3
"""
generate-report.py — Generate Word (.docx) and PowerPoint (.pptx) audit reports.

Reads scored JSON (from calculate-score.py), optional SEMrush data, and
optional chart images to produce professional branded reports.

Usage:
    # Generate both reports from scored JSON
    python analyse-html.py page.html | python calculate-score.py | \\
        python generate-report.py --url example.com --output-dir ./reports

    # With SEMrush data and charts
    python generate-report.py --scores scores.json --semrush semrush.json \\
        --charts-dir ./charts --brand logo.png --output-dir ./reports

    # Word only
    python generate-report.py --scores scores.json --format docx

Options:
    --scores FILE       Path to scored JSON (or pipe via stdin)
    --semrush FILE      Path to supplementary SEMrush data JSON
    --url URL           The audited site URL (for report title)
    --output-dir DIR    Output directory (default: ./reports)
    --format FORMAT     Output format: docx, pptx, or both (default: both)
    --charts-dir DIR    Directory containing chart PNG images
    --brand IMAGE       Path to brand/logo image for cover pages
    --font FONT         Font family name (default: Plus Jakarta Sans)
    --pagespeed FILE    Path to PageSpeed data JSON (mobile + desktop)

Dependencies:
    python-docx (pip install python-docx)
    python-pptx (pip install python-pptx)
    Pillow      (pip install Pillow)     — optional, for image handling

Output:
    FAT_Audit_Report.docx       — Comprehensive Word report
    FAT_Audit_Presentation.pptx — Executive summary PowerPoint
"""

import sys
import json
import os
import argparse
from datetime import date

# Defer imports for helpful error messages
MISSING_DEPS = []
try:
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import nsdecls
    from docx.oxml import parse_xml
except ImportError:
    MISSING_DEPS.append('python-docx')

try:
    from pptx import Presentation
    from pptx.util import Inches as PInches, Pt as PPt
    from pptx.dml.color import RGBColor as PRGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.enum.shapes import MSO_SHAPE
except ImportError:
    MISSING_DEPS.append('python-pptx')

# ---------- Constants ----------
FONT = 'Plus Jakarta Sans'

# Word colors
DARK_GRAY = RGBColor(0x2C, 0x3E, 0x50) if 'python-docx' not in MISSING_DEPS else None
ACCENT_RED = RGBColor(0xC0, 0x39, 0x2B) if 'python-docx' not in MISSING_DEPS else None
MID_GRAY = RGBColor(0x7F, 0x8C, 0x8D) if 'python-docx' not in MISSING_DEPS else None
WHITE = RGBColor(0xFF, 0xFF, 0xFF) if 'python-docx' not in MISSING_DEPS else None

# PPTX colors
if 'python-pptx' not in MISSING_DEPS:
    P_DARK = PRGBColor(0x1A, 0x1A, 0x2E)
    P_RED = PRGBColor(0xC0, 0x39, 0x2B)
    P_ORANGE = PRGBColor(0xE6, 0x7E, 0x22)
    P_YELLOW = PRGBColor(0xF3, 0x9C, 0x12)
    P_GREEN = PRGBColor(0x27, 0xAE, 0x60)
    P_WHITE = PRGBColor(0xFF, 0xFF, 0xFF)
    P_GRAY = PRGBColor(0x2C, 0x3E, 0x50)
    P_MGRAY = PRGBColor(0x7F, 0x8C, 0x8D)
    P_LGRAY = PRGBColor(0xEC, 0xF0, 0xF1)
    P_BLUE = PRGBColor(0x29, 0x80, 0xB9)


# ---------- Helper Functions ----------

def _set_cell_shading(cell, color_hex):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def _set_cell(cell, text, bold=False, color=None, size=10, alignment=None, font=FONT):
    cell.text = ""
    p = cell.paragraphs[0]
    if alignment:
        p.alignment = alignment
    run = p.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = font
    if color:
        run.font.color.rgb = color
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)


def _make_table(doc, headers):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    for i, h in enumerate(headers):
        _set_cell(table.rows[0].cells[i], h, bold=True, color=WHITE, size=9,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_shading(table.rows[0].cells[i], "2C3E50")
    return table


def _add_check_row(table, check, result, detail, status):
    row = table.add_row()
    for i, val in enumerate([check, result, detail, status]):
        _set_cell(row.cells[i], val, size=8, bold=(i == 0),
                  alignment=WD_ALIGN_PARAGRAPH.CENTER if i > 0 else None)
    colors = {"PASS": "D5F5E3", "FAIL": "FADBD8", "WARNING": "FDEBD0", "N/A": "F2F3F4"}
    _set_cell_shading(row.cells[3], colors.get(status, "F2F3F4"))


def _heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for r in h.runs:
        r.font.color.rgb = DARK_GRAY
        r.font.name = FONT
    return h


def _para(doc, text, bold=False, color=None, size=10):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = FONT
    if color:
        run.font.color.rgb = color
    return p


def _insert_chart(doc, charts_dir, filename, caption, width=6.0):
    """Insert a chart image with caption if the file exists."""
    if not charts_dir:
        return False
    path = os.path.join(charts_dir, filename)
    if not os.path.exists(path):
        return False
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(path, width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap.add_run(caption)
    run.font.size = Pt(9)
    run.font.italic = True
    run.font.name = FONT
    return True


# ---------- PPTX Helpers ----------

def _ptb(slide, left, top, width, height, text, size=18, color=P_WHITE, bold=False, align=PP_ALIGN.LEFT):
    txBox = slide.shapes.add_textbox(PInches(left), PInches(top), PInches(width), PInches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = PPt(size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = FONT
    p.alignment = align


def _prect(slide, left, top, width, height, color):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, PInches(left), PInches(top),
                                    PInches(width), PInches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def _pcard(slide, left, top, width, height, label, score, color):
    _prect(slide, left, top, width, height, color)
    _ptb(slide, left, top + 0.12, width, height * 0.55, str(score), 28, P_WHITE, True, PP_ALIGN.CENTER)
    _ptb(slide, left, top + height * 0.55, width, height * 0.4, label, 10, P_WHITE, True, PP_ALIGN.CENTER)


def _pheader(slide, title, brand=None):
    _prect(slide, 0, 0, 13.333, 1.1, P_DARK)
    if brand and os.path.exists(brand):
        slide.shapes.add_picture(brand, PInches(0.3), PInches(0.05), PInches(1.0), PInches(1.0))
    _ptb(slide, 1.4 if brand else 0.5, 0.25, 10, 0.6, title, 28, P_WHITE, True)


def _pbullet(slide, x, y, text, size, text_color, dot_color):
    _prect(slide, x, y + 0.07, 0.1, 0.1, dot_color)
    _ptb(slide, x + 0.15, y, 11.0, 0.3, text, size, text_color)


# ---------- Word Report Generator ----------

def generate_docx(scores, url, output_dir, charts_dir=None, semrush=None, brand=None,
                  pagespeed=None, font=FONT):
    global FONT
    FONT = font

    doc = Document()
    style = doc.styles['Normal']
    style.font.name = FONT
    style.font.size = Pt(10)
    style.font.color.rgb = DARK_GRAY

    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # --- Cover ---
    for _ in range(3):
        doc.add_paragraph()
    if brand and os.path.exists(brand):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(brand, width=Inches(3))
        doc.add_paragraph()

    for text, sz, clr, bld in [
        ("FAT AGENT AUDIT REPORT", 28, DARK_GRAY, True),
        ("Fix  |  Audit  |  Test", 16, MID_GRAY, False),
        ("", 10, None, False),
        (url or "Website Audit", 20, ACCENT_RED, True),
        (f"Audit Date: {date.today().strftime('%d %B %Y')}", 12, MID_GRAY, False),
        ("CONFIDENTIAL", 10, ACCENT_RED, True),
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if text:
            run = p.add_run(text)
            run.bold = bld
            run.font.size = Pt(sz)
            run.font.name = FONT
            if clr:
                run.font.color.rgb = clr
    doc.add_page_break()

    # --- Scoring Summary ---
    _heading(doc, "1. Scoring Summary")

    overall = scores.get('overall', {})
    seo_score = scores.get('seo', {}).get('score', 0)
    sec_score = scores.get('security', {}).get('score', 0)
    a11y_score = scores.get('accessibility', {}).get('score', 0)
    perf_score = scores.get('performance', {}).get('score', 0)
    fat_score = overall.get('score', 0)
    grade = overall.get('grade', '?')

    score_table = _make_table(doc, ["Category", "FAT Score", "Grade"])
    for cat, sc in [("SEO", seo_score), ("Security", sec_score),
                    ("Accessibility", a11y_score), ("Performance", perf_score),
                    ("Overall", fat_score)]:
        row = score_table.add_row()
        g = 'A' if sc >= 90 else 'B' if sc >= 75 else 'C' if sc >= 60 else 'D' if sc >= 40 else 'F'
        for i, v in enumerate([cat, f"{sc}/100", g]):
            _set_cell(row.cells[i], v, size=10, bold=(i == 0),
                      alignment=WD_ALIGN_PARAGRAPH.CENTER)
        grade_colors = {"A": "D5F5E3", "B": "D6EAF8", "C": "FDEBD0", "D": "F5CBA7", "F": "FADBD8"}
        _set_cell_shading(row.cells[2], grade_colors.get(g, "F2F3F4"))

    _insert_chart(doc, charts_dir, 'chart_fat_scores.png',
                  'Figure: FAT Agent Score Breakdown & Issue Distribution', 6.0)

    doc.add_page_break()

    # --- Findings ---
    _heading(doc, "2. All Findings")
    summary = scores.get('summary', {})
    all_issues = []
    for prio, label in [('critical', 'P0'), ('high', 'P1'), ('medium', 'P2'), ('low', 'P3')]:
        for issue in summary.get(prio, []):
            all_issues.append((label, issue))

    if all_issues:
        findings_table = _make_table(doc, ["#", "Priority", "Finding"])
        for idx, (prio, issue) in enumerate(all_issues, 1):
            row = findings_table.add_row()
            _set_cell(row.cells[0], str(idx), size=9, alignment=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell(row.cells[1], prio, bold=True, size=9, color=WHITE,
                      alignment=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell(row.cells[2], issue, size=8)
            color_map = {"P0": "C0392B", "P1": "E67E22", "P2": "F39C12", "P3": "27AE60"}
            _set_cell_shading(row.cells[1], color_map.get(prio, "7F8C8D"))
    else:
        _para(doc, "No issues found — congratulations!", color=RGBColor(0x27, 0xAE, 0x60), bold=True)

    doc.add_page_break()

    # --- SEO Breakdown ---
    _heading(doc, "3. SEO Score Breakdown")
    seo_details = scores.get('seo', {}).get('details', {})
    if seo_details:
        seo_table = _make_table(doc, ["Category", "Score", "Max"])
        for cat, data in seo_details.items():
            row = seo_table.add_row()
            label = cat.replace('_', ' ').title()
            sc = data.get('score', 0)
            mx = data.get('max', 0)
            _set_cell(row.cells[0], label, bold=True, size=9)
            _set_cell(row.cells[1], str(sc), size=9, alignment=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell(row.cells[2], str(mx), size=9, alignment=WD_ALIGN_PARAGRAPH.CENTER)
            if sc >= mx:
                _set_cell_shading(row.cells[1], "D5F5E3")
            elif sc >= mx * 0.6:
                _set_cell_shading(row.cells[1], "FDEBD0")
            else:
                _set_cell_shading(row.cells[1], "FADBD8")

    doc.add_page_break()

    # --- SEMrush Section ---
    if semrush:
        _heading(doc, "4. SEMrush Domain Intelligence")
        domain = semrush.get('domain', url or '')
        sem_table = doc.add_table(rows=0, cols=2)
        sem_table.style = 'Table Grid'
        for label, value in [
            ("Domain", domain),
            ("Authority Score", f"{semrush.get('authority_score', '?')}/100"),
            ("Organic Traffic", f"{semrush.get('organic_traffic', '?')}/month ({semrush.get('traffic_change', '')})"),
            ("Organic Keywords", f"{semrush.get('organic_keywords', '?')} ({semrush.get('keywords_change', '')})"),
            ("Referring Domains", str(semrush.get('referring_domains', '?'))),
            ("Backlinks", str(semrush.get('backlinks', '?'))),
        ]:
            row = sem_table.add_row()
            _set_cell(row.cells[0], label, bold=True, size=10)
            _set_cell(row.cells[1], value, size=10)
            _set_cell_shading(row.cells[0], "F2F3F4")

        doc.add_paragraph()

        # --- Backlink Quality Analysis (Wave 4) ---
        bq = semrush.get("backlink_quality")
        if bq:
            _heading(doc, "Backlink Quality Analysis", level=2)
            # Authority distribution warning
            auth_dist = bq.get("referring_domains_by_authority", {})
            if auth_dist:
                low_auth = auth_dist.get("0-10", 0)
                total_domains = sum(auth_dist.values()) if auth_dist.values() else 1
                if total_domains > 0 and (low_auth / total_domains) > 0.5:
                    pct = round((low_auth / total_domains) * 100, 1)
                    _para(doc,
                          f"WARNING: {pct}% of referring domains have Authority Score 0-10. "
                          "This indicates a high proportion of low-quality backlinks, which "
                          "may negatively impact search rankings. Consider a link audit and "
                          "disavow strategy.",
                          bold=True, color=ACCENT_RED, size=10)
            # Geographic concentration warning
            country_dist = bq.get("referring_domains_by_country", {})
            if country_dist:
                total_country = sum(country_dist.values()) if country_dist.values() else 1
                for country, count in country_dist.items():
                    if total_country > 0 and (count / total_country) > 0.7:
                        pct = round((count / total_country) * 100, 1)
                        _para(doc,
                              f"NOTE: {pct}% of referring domains are from {country}. "
                              "High geographic concentration may indicate unnatural link "
                              "patterns if this doesn't match your target market.",
                              color=MID_GRAY, size=10)
                        break

        _insert_chart(doc, charts_dir, 'chart_overview.png', 'Figure: Domain Overview Metrics', 6.5)
        _insert_chart(doc, charts_dir, 'chart_traffic_trend.png', 'Figure: Organic Traffic Trend', 6.0)
        _insert_chart(doc, charts_dir, 'chart_keywords_trend.png', 'Figure: Keywords Trend & SERP Distribution', 6.0)
        _insert_chart(doc, charts_dir, 'chart_top_keywords.png', 'Figure: Top Keywords by Volume', 5.5)
        doc.add_page_break()

    # --- PageSpeed ---
    if pagespeed:
        _heading(doc, "5. PageSpeed Performance")
        _insert_chart(doc, charts_dir, 'chart_pagespeed.png', 'Figure: PageSpeed Mobile vs Desktop', 5.5)

    # --- Footer ---
    doc.add_paragraph()
    if brand and os.path.exists(brand):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(brand, width=Inches(1.2))
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"Report generated by FAT Agent | {date.today().strftime('%d %B %Y')}")
    run.font.size = Pt(8)
    run.font.color.rgb = MID_GRAY
    run.font.name = FONT

    filename = f"FAT_Audit_Report_{url.replace('.', '_').replace('/', '')}.docx" if url else "FAT_Audit_Report.docx"
    path = os.path.join(output_dir, filename)
    doc.save(path)
    return path


# ---------- PPTX Report Generator ----------

def generate_pptx(scores, url, output_dir, charts_dir=None, semrush=None, brand=None,
                  pagespeed=None, font=FONT):
    global FONT
    FONT = font

    prs = Presentation()
    prs.slide_width = PInches(13.333)
    prs.slide_height = PInches(7.5)

    overall = scores.get('overall', {})
    seo_score = scores.get('seo', {}).get('score', 0)
    sec_score = scores.get('security', {}).get('score', 0)
    a11y_score = scores.get('accessibility', {}).get('score', 0)
    perf_score = scores.get('performance', {}).get('score', 0)
    fat_score = overall.get('score', 0)
    grade = overall.get('grade', '?')

    def _grade_color(sc):
        if sc >= 80: return P_GREEN
        if sc >= 60: return P_ORANGE
        return P_RED

    def add_bg(slide, color=P_WHITE):
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = color

    # --- Slide 1: Title ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, P_DARK)
    if brand and os.path.exists(brand):
        slide.shapes.add_picture(brand, PInches(4.9), PInches(0.3), PInches(3.5), PInches(3.5))
    _ptb(slide, 0.5, 4.0, 12.3, 1.0, "FAT AGENT AUDIT REPORT", 40, P_WHITE, True, PP_ALIGN.CENTER)
    _ptb(slide, 0.5, 4.8, 12.3, 0.5, "Fix  |  Audit  |  Test", 20, P_MGRAY, False, PP_ALIGN.CENTER)
    _ptb(slide, 0.5, 5.5, 12.3, 0.6, url or "Website Audit", 28, P_RED, True, PP_ALIGN.CENTER)
    _ptb(slide, 0.5, 6.3, 12.3, 0.5, date.today().strftime("%d %B %Y"), 14, P_MGRAY, False, PP_ALIGN.CENTER)

    # --- Slide 2: Executive Summary ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    _pheader(slide, "Executive Summary", brand)
    _pcard(slide, 0.3, 1.5, 2.4, 1.3, f"SEO\n{seo_score}/100", grade if seo_score == fat_score else ('A' if seo_score >= 90 else 'C+' if seo_score >= 70 else 'D'), _grade_color(seo_score))
    _pcard(slide, 2.9, 1.5, 2.4, 1.3, f"PERFORMANCE\n{perf_score}/100", "F" if perf_score < 40 else "D", _grade_color(perf_score))
    _pcard(slide, 5.5, 1.5, 2.4, 1.3, f"SECURITY\n{sec_score}/100", "F" if sec_score < 40 else "D", _grade_color(sec_score))
    _pcard(slide, 8.1, 1.5, 2.4, 1.3, f"ACCESSIBILITY\n{a11y_score}/100", "D" if a11y_score < 60 else "B", _grade_color(a11y_score))
    _pcard(slide, 10.7, 1.5, 2.4, 1.3, f"OVERALL\n{fat_score}/100", grade, _grade_color(fat_score))

    summary = scores.get('summary', {})
    all_issues = []
    for prio_key in ['critical', 'high', 'medium', 'low']:
        for issue in summary.get(prio_key, []):
            all_issues.append(issue)

    _ptb(slide, 0.5, 3.2, 12.3, 0.4, f"Key Findings ({summary.get('issues_found', len(all_issues))} Issues)", 20, P_GRAY, True)
    y = 3.7
    prio_colors = [P_RED] * len(summary.get('critical', [])) + \
                  [P_ORANGE] * len(summary.get('high', [])) + \
                  [P_YELLOW] * len(summary.get('medium', [])) + \
                  [P_GREEN] * len(summary.get('low', []))
    for i, issue in enumerate(all_issues[:10]):
        color = prio_colors[i] if i < len(prio_colors) else P_MGRAY
        _pbullet(slide, 0.7, y, issue[:100], 11, P_GRAY, color)
        y += 0.34

    # --- Chart slides (if charts exist) ---
    chart_slides = [
        ('chart_overview.png', 'SEMrush Domain Overview'),
        ('chart_traffic_trend.png', 'Organic Traffic Trend'),
        ('chart_keywords_trend.png', 'Keyword Rankings Over Time'),
        ('chart_top_keywords.png', 'Top Ranking Keywords'),
        ('chart_pagespeed.png', 'PageSpeed Performance'),
        ('chart_fat_scores.png', 'FAT Agent Score Summary'),
    ]

    for filename, title in chart_slides:
        if not charts_dir:
            continue
        chart_path = os.path.join(charts_dir, filename)
        if not os.path.exists(chart_path):
            continue

        slide = prs.slides.add_slide(prs.slide_layouts[6])
        add_bg(slide)
        _pheader(slide, title, brand)
        slide.shapes.add_picture(chart_path, PInches(0.3), PInches(1.3), PInches(12.7), PInches(5.2))
        source = f"Source: FAT Agent Audit | {url or 'Website'} | {date.today().strftime('%B %Y')}"
        _ptb(slide, 0.5, 6.7, 12.3, 0.4, source, 9, P_MGRAY, False, PP_ALIGN.CENTER)

    # --- Closing slide ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, P_DARK)
    if brand and os.path.exists(brand):
        slide.shapes.add_picture(brand, PInches(4.9), PInches(0.5), PInches(3.5), PInches(3.5))
    _ptb(slide, 0.5, 4.2, 12.3, 0.8, "Thank You", 40, P_WHITE, True, PP_ALIGN.CENTER)
    _ptb(slide, 0.5, 5.0, 12.3, 0.5, "FAT Agent Audit Complete", 20, P_MGRAY, False, PP_ALIGN.CENTER)
    _ptb(slide, 0.5, 5.6, 12.3, 0.5, url or "", 24, P_RED, True, PP_ALIGN.CENTER)
    _ptb(slide, 0.5, 6.3, 12.3, 0.5, f"Report Date: {date.today().strftime('%d %B %Y')}", 14, P_MGRAY, False, PP_ALIGN.CENTER)

    filename = f"FAT_Audit_Presentation_{url.replace('.', '_').replace('/', '')}.pptx" if url else "FAT_Audit_Presentation.pptx"
    path = os.path.join(output_dir, filename)
    prs.save(path)
    return path


# ---------- Main ----------

def main():
    if MISSING_DEPS:
        print(f"Error: Missing dependencies: {', '.join(MISSING_DEPS)}", file=sys.stderr)
        print(f"Install with: pip install {' '.join(MISSING_DEPS)}", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description='Generate FAT Agent audit reports')
    parser.add_argument('--scores', help='Path to scored JSON file (default: stdin)')
    parser.add_argument('--semrush', help='Path to SEMrush data JSON file')
    parser.add_argument('--url', help='Audited site URL')
    parser.add_argument('--output-dir', default='./reports', help='Output directory')
    parser.add_argument('--format', default='both', choices=['docx', 'pptx', 'both'])
    parser.add_argument('--charts-dir', help='Directory containing chart PNG images')
    parser.add_argument('--brand', help='Path to brand/logo image')
    parser.add_argument('--font', default='Plus Jakarta Sans', help='Font family')
    parser.add_argument('--pagespeed', help='Path to PageSpeed data JSON')
    args = parser.parse_args()

    # Load scores
    scores = {}
    if args.scores:
        with open(args.scores, 'r') as f:
            scores = json.load(f)
    elif not sys.stdin.isatty():
        scores = json.load(sys.stdin)

    if not scores:
        print("Error: No scores data provided. Pipe from calculate-score.py or use --scores", file=sys.stderr)
        sys.exit(1)

    semrush = None
    if args.semrush:
        with open(args.semrush, 'r') as f:
            semrush = json.load(f)

    pagespeed = None
    if args.pagespeed:
        with open(args.pagespeed, 'r') as f:
            pagespeed = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    results = {}
    if args.format in ('docx', 'both'):
        path = generate_docx(scores, args.url, args.output_dir, args.charts_dir,
                             semrush, args.brand, pagespeed, args.font)
        results['docx'] = path
        print(f"Word report: {path}")

    if args.format in ('pptx', 'both'):
        path = generate_pptx(scores, args.url, args.output_dir, args.charts_dir,
                             semrush, args.brand, pagespeed, args.font)
        results['pptx'] = path
        print(f"PowerPoint:  {path}")

    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
