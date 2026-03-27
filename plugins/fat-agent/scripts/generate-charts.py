#!/usr/bin/env python3
"""
generate-charts.py — Generate visual charts from FAT Agent audit data.

Reads scored JSON (from calculate-score.py) and optional SEMrush-style
traffic/keyword data, then outputs PNG chart images for embedding in
Word/PowerPoint reports.

Usage:
    # Generate charts from scored audit JSON
    python analyse-html.py page.html | python calculate-score.py | python generate-charts.py --output-dir ./charts

    # With supplementary SEMrush data file
    python generate-charts.py --scores scores.json --semrush semrush.json --output-dir ./charts

    # Generate only specific charts
    python generate-charts.py --scores scores.json --charts fat-scores,pagespeed

Output:
    PNG image files in the specified output directory:
      chart_fat_scores.png      — FAT score bars + issues donut
      chart_pagespeed.png       — Mobile vs Desktop PageSpeed comparison
      chart_traffic_trend.png   — Organic traffic over time (requires --semrush)
      chart_keywords_trend.png  — Keywords trend + SERP distribution (requires --semrush)
      chart_top_keywords.png    — Top keywords by volume (requires --semrush)
      chart_overview.png        — Domain metrics dashboard (requires --semrush)

Options:
    --scores FILE       Path to scored JSON (or pipe via stdin)
    --semrush FILE      Path to supplementary SEMrush data JSON
    --output-dir DIR    Output directory for chart images (default: ./charts)
    --charts LIST       Comma-separated list of charts to generate (default: all)
    --dpi NUMBER        Image DPI (default: 200)
    --font FONT         Font family name (default: auto-detect)
    --brand IMAGE       Path to brand/logo image for overview chart

Dependencies:
    matplotlib (pip install matplotlib)
    Pillow     (pip install Pillow)    — optional, for brand image support

SEMrush Data Format (--semrush):
    {
      "domain": "example.com",
      "authority_score": 22,
      "organic_traffic": 1200,
      "traffic_change": "-12%",
      "organic_keywords": 641,
      "keywords_change": "-2.7%",
      "referring_domains": 164,
      "backlinks": 1300,
      "traffic_cost": 2000,
      "traffic_trend": [
        {"month": "Apr 24", "organic": 800, "paid": 0, "branded": 200},
        ...
      ],
      "keywords_trend": [
        {"month": "Apr 24", "total": 350, "top3": 30, "top10": 60},
        ...
      ],
      "position_distribution": {"top3": 86, "4-10": 73, "11-20": 132, "21-50": 323, "51-100": 27},
      "top_keywords": [
        {"keyword": "example query", "position": 1, "volume": 720, "traffic_pct": "14.7%"},
        ...
      ],
      "competitors": [
        {"domain": "competitor.com", "mentions": 7},
        ...
      ]
    }
"""

import sys
import json
import os
import argparse

# Defer matplotlib import to provide helpful error if missing
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    from matplotlib.patches import Patch
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


# ---------- colour palette ----------
DARK = '#1A1A2E'
RED = '#C0392B'
ORANGE = '#E67E22'
YELLOW = '#F39C12'
GREEN = '#27AE60'
BLUE = '#2980B9'
TEAL = '#1ABC9C'
GRAY = '#2C3E50'
LGRAY = '#ECF0F1'
MGRAY = '#7F8C8D'
WHITE = '#FFFFFF'


def _setup_font(font_name=None):
    """Try to use the requested font, fall back gracefully."""
    if font_name:
        try:
            plt.rcParams['font.family'] = font_name
            return
        except Exception:
            pass
    for candidate in ['Plus Jakarta Sans', 'Calibri', 'Segoe UI', 'Helvetica Neue', 'Arial']:
        try:
            from matplotlib import font_manager
            matches = [f for f in font_manager.findSystemFonts() if candidate.lower().replace(' ', '') in f.lower().replace(' ', '')]
            if matches:
                plt.rcParams['font.family'] = candidate
                return
        except Exception:
            continue
    plt.rcParams['font.family'] = 'sans-serif'


def _clean_ax(ax):
    """Apply consistent clean styling to an axis."""
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(LGRAY)
    ax.spines['bottom'].set_color(LGRAY)


# ---------- chart generators ----------

def chart_fat_scores(scores, output_dir, dpi=200):
    """FAT Agent score bars + issues priority donut."""
    seo = scores.get('seo', {}).get('score', 0)
    sec = scores.get('security', {}).get('score', 0)
    a11y = scores.get('accessibility', {}).get('score', 0)
    perf = scores.get('performance', {}).get('score', 0)
    overall = scores.get('overall', {}).get('score', 0)

    summary = scores.get('summary', {})
    n_crit = len(summary.get('critical', []))
    n_high = len(summary.get('high', []))
    n_med = len(summary.get('medium', []))
    n_low = len(summary.get('low', []))
    total = summary.get('issues_found', n_crit + n_high + n_med + n_low)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), gridspec_kw={'width_ratios': [3, 2]})
    fig.patch.set_facecolor(WHITE)

    # Score bars
    categories = ['SEO', 'Security', 'Accessibility', 'Performance', 'Overall']
    vals = [seo, sec, a11y, perf, overall]
    colors = [ORANGE if v >= 60 else RED for v in vals]
    colors = [GREEN if v >= 80 else c for v, c in zip(vals, colors)]

    y = np.arange(len(categories))
    ax1.set_facecolor(WHITE)
    ax1.barh(y, [100]*len(vals), color=LGRAY, height=0.5)
    bars = ax1.barh(y, vals, color=colors, height=0.5)
    ax1.set_yticks(y)
    ax1.set_yticklabels(categories, fontsize=11, fontweight='bold')
    ax1.invert_yaxis()
    ax1.set_xlim(0, 105)
    ax1.set_title('FAT Agent Scores', fontsize=15, fontweight='bold', color=GRAY, pad=12)
    for bar, v in zip(bars, vals):
        ax1.text(v + 2, bar.get_y() + bar.get_height()/2,
                 f'{v}/100', va='center', fontsize=11, fontweight='bold', color=GRAY)
    ax1.axvline(x=90, color=GREEN, linestyle='--', alpha=0.3)
    ax1.axvline(x=60, color=YELLOW, linestyle='--', alpha=0.3)
    ax1.text(91, -0.5, 'A', fontsize=8, color=GREEN)
    ax1.text(61, -0.5, 'D', fontsize=8, color=YELLOW)
    _clean_ax(ax1)

    # Issues donut
    ax2.set_facecolor(WHITE)
    if total > 0:
        sizes = [max(n_crit, 0), max(n_high, 0), max(n_med, 0), max(n_low, 0)]
        # Ensure at least one non-zero for pie chart
        if sum(sizes) == 0:
            sizes = [1, 0, 0, 0]
        labels = [f'P0 Critical\n({n_crit})', f'P1 High\n({n_high})',
                  f'P2 Medium\n({n_med})', f'P3 Low\n({n_low})']
        issue_colors = [RED, ORANGE, YELLOW, GREEN]
        # Filter out zero-sized slices
        filtered = [(s, l, c) for s, l, c in zip(sizes, labels, issue_colors) if s > 0]
        if filtered:
            f_sizes, f_labels, f_colors = zip(*filtered)
            wedges, texts, autotexts = ax2.pie(f_sizes, labels=f_labels, colors=f_colors,
                                                autopct='%1.0f%%', startangle=90,
                                                textprops={'fontsize': 9})
            for at in autotexts:
                at.set_fontsize(9)
                at.set_fontweight('bold')
                at.set_color(WHITE)
    ax2.set_title(f'{total} Issues Found', fontsize=14, fontweight='bold', color=GRAY, pad=12)

    plt.tight_layout()
    path = os.path.join(output_dir, 'chart_fat_scores.png')
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor=WHITE)
    plt.close()
    return path


def chart_pagespeed(scores, output_dir, dpi=200, mobile=None, desktop=None):
    """PageSpeed mobile vs desktop bar comparison.

    If mobile/desktop dicts aren't provided, uses placeholder data from the
    scores dict (PageSpeed data isn't part of the standard pipeline — it's
    typically fetched separately via fetch-pagespeed.py).
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    fig.patch.set_facecolor(WHITE)

    categories = ['Performance', 'SEO', 'Accessibility', 'Best\nPractices']

    # Defaults if not provided
    mob_scores = [
        mobile.get('performance', 0) if mobile else 0,
        mobile.get('seo', 0) if mobile else scores.get('seo', {}).get('score', 0),
        mobile.get('accessibility', 0) if mobile else scores.get('accessibility', {}).get('score', 0),
        mobile.get('best_practices', 0) if mobile else 73,
    ]
    desk_scores = [
        desktop.get('performance', 0) if desktop else 0,
        desktop.get('seo', 0) if desktop else scores.get('seo', {}).get('score', 0),
        desktop.get('accessibility', 0) if desktop else scores.get('accessibility', {}).get('score', 0),
        desktop.get('best_practices', 0) if desktop else 73,
    ]

    def _color(v):
        if v >= 90: return GREEN
        if v >= 50: return ORANGE
        return RED

    for ax, data, title, title_color in [
        (ax1, mob_scores, 'Mobile', RED),
        (ax2, desk_scores, 'Desktop', ORANGE)
    ]:
        colors = [_color(v) for v in data]
        bars = ax.bar(categories, data, color=colors, width=0.6, edgecolor=WHITE, linewidth=0.5)
        ax.set_title(title, fontsize=16, fontweight='bold', color=title_color, pad=12)
        ax.set_ylim(0, 105)
        ax.axhline(y=90, color=GREEN, linestyle='--', alpha=0.4, linewidth=1)
        ax.text(3.5, 91, 'Good (90+)', fontsize=7, color=GREEN, alpha=0.6)
        for bar, v in zip(bars, data):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                    str(v), ha='center', va='bottom', fontsize=12, fontweight='bold', color=GRAY)
        ax.set_facecolor(WHITE)
        ax.tick_params(labelsize=9)
        _clean_ax(ax)
        ax.set_ylabel('Score', fontsize=10, color=MGRAY)

    fig.suptitle('PageSpeed Insights Scores', fontsize=15, fontweight='bold', color=GRAY, y=1.02)
    plt.tight_layout()
    path = os.path.join(output_dir, 'chart_pagespeed.png')
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor=WHITE)
    plt.close()
    return path


def chart_traffic_trend(semrush, output_dir, dpi=200):
    """Organic traffic over time line chart."""
    trend = semrush.get('traffic_trend', [])
    if not trend:
        return None

    months = [t['month'] for t in trend]
    organic = [t.get('organic', 0) for t in trend]
    paid = [t.get('paid', 0) for t in trend]
    branded = [t.get('branded', 0) for t in trend]

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor(WHITE)
    ax.set_facecolor(WHITE)

    ax.fill_between(months, organic, alpha=0.15, color=BLUE)
    ax.plot(months, organic, color=BLUE, linewidth=2.5, marker='o', markersize=5, label='Organic Traffic')
    if any(b > 0 for b in branded):
        ax.fill_between(months, branded, alpha=0.1, color=GREEN)
        ax.plot(months, branded, color=GREEN, linewidth=1.5, label='Branded Traffic', linestyle='--')
    if any(p > 0 for p in paid):
        ax.plot(months, paid, color=RED, linewidth=1.5, label='Paid Traffic')

    domain = semrush.get('domain', '')
    ax.set_title(f'Organic Traffic Trend{" — " + domain if domain else ""}',
                 fontsize=16, fontweight='bold', color=GRAY, pad=15)
    ax.set_ylabel('Est. Monthly Traffic', fontsize=11, color=MGRAY)
    ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
    ax.tick_params(axis='x', rotation=30, labelsize=9)
    ax.tick_params(axis='y', labelsize=9)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    _clean_ax(ax)

    # Annotate peak and current
    peak_val = max(organic)
    peak_idx = organic.index(peak_val)
    current_val = organic[-1]
    change = semrush.get('traffic_change', '')

    ax.annotate(f'Peak: {peak_val:,}', xy=(peak_idx, peak_val), fontsize=9,
                color=GREEN, fontweight='bold', xytext=(peak_idx, peak_val * 1.08), ha='center')
    if change:
        ax.annotate(f'Current: {current_val:,}\n({change})', xy=(len(months)-1, current_val),
                    fontsize=9, color=RED, fontweight='bold',
                    xytext=(len(months)-1.8, current_val * 0.5), ha='center',
                    arrowprops=dict(arrowstyle='->', color=RED, lw=1.5))

    plt.tight_layout()
    path = os.path.join(output_dir, 'chart_traffic_trend.png')
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor=WHITE)
    plt.close()
    return path


def chart_keywords_trend(semrush, output_dir, dpi=200):
    """Keywords trend line + SERP position distribution bars."""
    kw_trend = semrush.get('keywords_trend', [])
    pos_dist = semrush.get('position_distribution', {})
    if not kw_trend and not pos_dist:
        return None

    has_trend = bool(kw_trend)
    has_dist = bool(pos_dist)
    ncols = (1 if has_trend else 0) + (1 if has_dist else 0)
    if ncols == 0:
        return None

    ratios = []
    if has_trend: ratios.append(3)
    if has_dist: ratios.append(2)

    fig, axes = plt.subplots(1, ncols, figsize=(12 if ncols == 2 else 7, 4.5),
                              gridspec_kw={'width_ratios': ratios} if ncols == 2 else {})
    fig.patch.set_facecolor(WHITE)
    if ncols == 1:
        axes = [axes]

    ax_idx = 0
    if has_trend:
        ax = axes[ax_idx]; ax_idx += 1
        ax.set_facecolor(WHITE)
        months = [t['month'] for t in kw_trend]
        total = [t.get('total', 0) for t in kw_trend]
        top3 = [t.get('top3', 0) for t in kw_trend]
        top10 = [t.get('top10', 0) for t in kw_trend]

        ax.fill_between(months, total, alpha=0.12, color=BLUE)
        ax.plot(months, total, color=BLUE, linewidth=2.5, marker='o', markersize=5, label='Total Keywords')
        if any(v > 0 for v in top3):
            ax.plot(months, top3, color=GREEN, linewidth=1.5, marker='s', markersize=3, label='Top 3')
        if any(v > 0 for v in top10):
            ax.plot(months, top10, color=ORANGE, linewidth=1.5, marker='^', markersize=3, label='Top 4-10')

        ax.set_title('Organic Keywords Trend', fontsize=14, fontweight='bold', color=GRAY, pad=12)
        ax.set_ylabel('Number of Keywords', fontsize=10, color=MGRAY)
        ax.legend(fontsize=8, framealpha=0.9)
        ax.tick_params(axis='x', rotation=30, labelsize=8)
        ax.tick_params(axis='y', labelsize=9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        _clean_ax(ax)

        current = total[-1]
        change = semrush.get('keywords_change', '')
        if change:
            ax.annotate(f'Current: {current:,}\n({change})', xy=(len(months)-1, current),
                        fontsize=9, color=RED, fontweight='bold',
                        xytext=(len(months)-2, current * 0.6), ha='center',
                        arrowprops=dict(arrowstyle='->', color=RED, lw=1.5))

    if has_dist:
        ax = axes[ax_idx]
        ax.set_facecolor(WHITE)
        positions = list(pos_dist.keys())
        counts = list(pos_dist.values())
        bar_colors = [GREEN, TEAL, BLUE, ORANGE, MGRAY][:len(positions)]

        bars = ax.barh(positions, counts, color=bar_colors, height=0.6, edgecolor=WHITE, linewidth=0.5)
        ax.set_title('SERP Position Distribution', fontsize=14, fontweight='bold', color=GRAY, pad=12)
        ax.set_xlabel('Keywords', fontsize=10, color=MGRAY)
        ax.invert_yaxis()
        ax.tick_params(labelsize=9)
        _clean_ax(ax)

        for bar, count in zip(bars, counts):
            ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height()/2,
                    str(count), va='center', fontsize=10, fontweight='bold', color=GRAY)

    plt.tight_layout()
    path = os.path.join(output_dir, 'chart_keywords_trend.png')
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor=WHITE)
    plt.close()
    return path


def chart_top_keywords(semrush, output_dir, dpi=200):
    """Top keywords horizontal bar chart coloured by position."""
    kws = semrush.get('top_keywords', [])
    if not kws:
        return None

    # Take top 12 by volume
    kws = sorted(kws, key=lambda k: k.get('volume', 0), reverse=True)[:12]

    fig, ax = plt.subplots(figsize=(10, max(3, len(kws) * 0.5 + 1)))
    fig.patch.set_facecolor(WHITE)
    ax.set_facecolor(WHITE)

    keywords = [k['keyword'] for k in kws]
    volumes = [k.get('volume', 0) for k in kws]
    positions = [k.get('position', 100) for k in kws]
    colors = [GREEN if p <= 3 else ORANGE if p <= 10 else RED for p in positions]

    y_pos = np.arange(len(keywords))
    bars = ax.barh(y_pos, volumes, color=colors, height=0.6, edgecolor=WHITE, linewidth=0.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(keywords, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel('Monthly Search Volume', fontsize=11, color=MGRAY)
    ax.set_title('Top Ranking Keywords by Search Volume', fontsize=15, fontweight='bold', color=GRAY, pad=15)

    for bar, vol, pos in zip(bars, volumes, positions):
        ax.text(bar.get_width() + 10, bar.get_y() + bar.get_height()/2,
                f'{vol:,}  (#{pos})', va='center', fontsize=9, color=GRAY)

    _clean_ax(ax)
    ax.grid(axis='x', alpha=0.2, linestyle='--')

    legend_elements = [Patch(facecolor=GREEN, label='Position 1-3'),
                       Patch(facecolor=ORANGE, label='Position 4-10'),
                       Patch(facecolor=RED, label='Position 11+')]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=9)

    plt.tight_layout()
    path = os.path.join(output_dir, 'chart_top_keywords.png')
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor=WHITE)
    plt.close()
    return path


def chart_overview(semrush, output_dir, dpi=200):
    """Domain metrics dashboard (coloured cards)."""
    domain = semrush.get('domain', 'Unknown')
    metrics = [
        ('Authority\nScore', str(semrush.get('authority_score', '?')),
         'Average' if semrush.get('authority_score', 0) < 40 else 'Good', ORANGE),
        ('Organic\nTraffic', str(semrush.get('organic_traffic', '?')),
         semrush.get('traffic_change', ''), RED if '-' in str(semrush.get('traffic_change', '')) else GREEN),
        ('Keywords', str(semrush.get('organic_keywords', '?')),
         semrush.get('keywords_change', ''), YELLOW),
        ('Ref.\nDomains', str(semrush.get('referring_domains', '?')), '', BLUE),
        ('Backlinks', str(semrush.get('backlinks', '?')), '', TEAL),
        ('Traffic\nCost', f"${semrush.get('traffic_cost', '?'):,}" if isinstance(semrush.get('traffic_cost'), (int, float)) else str(semrush.get('traffic_cost', '?')),
         'USD/mo', GREEN),
    ]

    fig, axes = plt.subplots(1, len(metrics), figsize=(13, 2.2))
    fig.patch.set_facecolor(DARK)

    for ax, (label, value, sub, color) in zip(axes, metrics):
        ax.set_facecolor(color)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.text(0.5, 0.62, value, ha='center', va='center', fontsize=22, fontweight='bold', color=WHITE)
        ax.text(0.5, 0.28, label, ha='center', va='center', fontsize=8, color=WHITE, alpha=0.9)
        if sub:
            ax.text(0.5, 0.08, sub, ha='center', va='center', fontsize=7, color=WHITE, alpha=0.7)
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.suptitle(f'SEMrush Domain Overview  —  {domain}', fontsize=13,
                 fontweight='bold', color=WHITE, y=1.02)
    plt.tight_layout()
    path = os.path.join(output_dir, 'chart_overview.png')
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor=DARK)
    plt.close()
    return path


# ---------- main ----------

CHART_REGISTRY = {
    'fat-scores': ('chart_fat_scores', False),    # (func_name, needs_semrush)
    'pagespeed': ('chart_pagespeed', False),
    'traffic-trend': ('chart_traffic_trend', True),
    'keywords-trend': ('chart_keywords_trend', True),
    'top-keywords': ('chart_top_keywords', True),
    'overview': ('chart_overview', True),
}


def main():
    if not HAS_MATPLOTLIB:
        print("Error: matplotlib is required for chart generation.", file=sys.stderr)
        print("Install with: pip install matplotlib", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description='Generate FAT Agent audit charts')
    parser.add_argument('--scores', help='Path to scored JSON file (default: stdin)')
    parser.add_argument('--semrush', help='Path to SEMrush data JSON file')
    parser.add_argument('--output-dir', default='./charts', help='Output directory (default: ./charts)')
    parser.add_argument('--charts', help='Comma-separated chart names (default: all available)')
    parser.add_argument('--dpi', type=int, default=200, help='Image DPI (default: 200)')
    parser.add_argument('--font', help='Font family name')
    args = parser.parse_args()

    _setup_font(args.font)

    # Load scores
    scores = {}
    if args.scores:
        with open(args.scores, 'r') as f:
            scores = json.load(f)
    elif not sys.stdin.isatty():
        scores = json.load(sys.stdin)

    # Load SEMrush data
    semrush = {}
    if args.semrush:
        with open(args.semrush, 'r') as f:
            semrush = json.load(f)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Determine which charts to generate
    if args.charts:
        requested = [c.strip() for c in args.charts.split(',')]
    else:
        requested = list(CHART_REGISTRY.keys())

    generated = []
    skipped = []

    for chart_name in requested:
        if chart_name not in CHART_REGISTRY:
            print(f"Warning: Unknown chart '{chart_name}', skipping", file=sys.stderr)
            skipped.append(chart_name)
            continue

        func_name, needs_semrush = CHART_REGISTRY[chart_name]
        if needs_semrush and not semrush:
            skipped.append(chart_name)
            continue

        try:
            func = globals()[func_name]
            if needs_semrush:
                path = func(semrush, args.output_dir, args.dpi)
            else:
                path = func(scores, args.output_dir, args.dpi)

            if path:
                generated.append(path)
                print(f"Generated: {path}")
            else:
                skipped.append(chart_name)
        except Exception as e:
            print(f"Error generating {chart_name}: {e}", file=sys.stderr)
            skipped.append(chart_name)

    # Output summary as JSON
    result = {
        "generated": generated,
        "skipped": skipped,
        "output_dir": args.output_dir,
        "total": len(generated)
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
