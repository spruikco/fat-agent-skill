#!/usr/bin/env python3
"""
FAT Agent Badge Generator
Generates shields.io-style SVG score badges for READMEs.

Usage:
    python generate-badge.py <scores.json>
    python generate-badge.py <scores.json> --output badge.svg
    python generate-badge.py <scores.json> --category seo
    python generate-badge.py <scores.json> --image assets/social-preview.png
    python generate-badge.py <scores.json> --image assets/social-preview.png --width 250
    python analyse-html.py page.html | python calculate-score.py | python generate-badge.py

Options:
    --output, -o    Write SVG to file instead of stdout
    --category, -c  Generate badge for a specific category:
                    seo, security, accessibility, performance
                    (default: overall FAT score with grade)
    --style, -s     Badge style: flat (default), flat-square
    --image, -i     Path to PNG image to display above the score bar
    --width, -w     Badge width in pixels (default: auto for text badges,
                    200 for image badges)

Output: SVG badge string (or file).
"""

import sys
import json
import base64
import struct

# Shields.io-compatible colour palette
GRADE_COLOURS = {
    "A": "#4c1",
    "B": "#97ca00",
    "C": "#dfb317",
    "D": "#fe7d37",
    "F": "#e05d44",
}

CATEGORY_LABELS = {
    "seo": "SEO",
    "security": "Security",
    "accessibility": "A11y",
    "performance": "Perf",
}


def score_to_colour(score):
    """Map a 0-100 score to a shields.io colour."""
    if score >= 90:
        return GRADE_COLOURS["A"]
    elif score >= 75:
        return GRADE_COLOURS["B"]
    elif score >= 60:
        return GRADE_COLOURS["C"]
    elif score >= 40:
        return GRADE_COLOURS["D"]
    else:
        return GRADE_COLOURS["F"]


def _text_width(text, font_size=11):
    """Approximate text width in pixels for Verdana at given size.

    Uses per-character width estimates derived from Verdana metrics.
    Accurate enough for badge layout — matches shields.io output.
    """
    narrow = set("1Iijl!|:;.,'\"`")
    wide = set("MWmw@%")
    total = 0.0
    for ch in text:
        if ch == " ":
            total += 3.3
        elif ch in narrow:
            total += 4.5
        elif ch in wide:
            total += 9.0
        elif ch.isupper():
            total += 7.5
        elif ch.isdigit():
            total += 6.5
        else:
            total += 6.3
    return total


def _png_dimensions(data):
    """Read width and height from PNG header bytes."""
    w = struct.unpack(">I", data[16:20])[0]
    h = struct.unpack(">I", data[20:24])[0]
    return w, h


def _bar_halves(label, value, bar_width):
    """Calculate label/value half widths for the score bar.

    When bar_width exceeds the natural text width, the halves are
    scaled proportionally to fill the available space.
    """
    padding = 12
    label_text_w = _text_width(label) + padding * 2
    value_text_w = _text_width(value) + padding * 2
    natural = label_text_w + value_text_w

    if bar_width and bar_width > natural:
        ratio = label_text_w / natural
        label_w = round(bar_width * ratio)
        value_w = bar_width - label_w
        return label_w, value_w, bar_width
    else:
        label_w = int(label_text_w)
        value_w = int(value_text_w)
        return label_w, value_w, label_w + value_w


def generate_badge_svg(label, value, colour, style="flat"):
    """Generate a shields.io-style SVG badge.

    Args:
        label: Left-hand text (e.g., "FAT", "SEO")
        value: Right-hand text (e.g., "A 92", "85")
        colour: Hex colour for the value background
        style: "flat" (default) or "flat-square"

    Returns:
        SVG string.
    """
    label_width, value_width, total_width = _bar_halves(label, value, None)
    label_x = round(label_width / 2, 1)
    value_x = round(label_width + value_width / 2, 1)
    rx = "0" if style == "flat-square" else "3"

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" '
        f'height="20" role="img" aria-label="{label}: {value}">\n'
        f"  <title>{label}: {value}</title>\n"
        f'  <linearGradient id="s" x2="0" y2="100%">\n'
        f'    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>\n'
        f'    <stop offset="1" stop-opacity=".1"/>\n'
        f"  </linearGradient>\n"
        f'  <clipPath id="r">\n'
        f'    <rect width="{total_width}" height="20" rx="{rx}" fill="#fff"/>\n'
        f"  </clipPath>\n"
        f'  <g clip-path="url(#r)">\n'
        f'    <rect width="{label_width}" height="20" fill="#555"/>\n'
        f'    <rect x="{label_width}" width="{value_width}" height="20" fill="{colour}"/>\n'
        f'    <rect width="{total_width}" height="20" fill="url(#s)"/>\n'
        f"  </g>\n"
        f'  <g fill="#fff" text-anchor="middle" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">\n'
        f'    <text x="{label_x}" y="15" fill="#010101" fill-opacity=".3">{label}</text>\n'
        f'    <text x="{label_x}" y="14">{label}</text>\n'
        f'    <text x="{value_x}" y="15" fill="#010101" fill-opacity=".3">{value}</text>\n'
        f'    <text x="{value_x}" y="14">{value}</text>\n'
        f"  </g>\n"
        f"</svg>\n"
    )


def generate_badge_with_image(image_path, scores, width=200, style="flat"):
    """Generate an SVG badge with character image, overall bar, and category breakdown.

    Layout (top to bottom):
        1. Character image (scaled to *width*)
        2. Overall bar  — "FAT | A 94"  (label + grade/score)
        3. Category bar — "SEO 95 | Sec 100 | A11y 92 | Perf 88"
           Each segment colour-coded by its own score.

    The whole badge is clipped to a single rounded rectangle.

    Args:
        image_path: Path to a PNG file.
        scores: Full scores dict from calculate-score.py.
        width: Badge width in pixels (image is scaled to fit).
        style: "flat" (rounded) or "flat-square".

    Returns:
        SVG string with embedded base64 image.
    """
    # --- extract scores ---
    overall = scores.get("overall", {})
    grade = overall.get("grade", "F")
    overall_score = overall.get("score", 0)
    overall_colour = GRADE_COLOURS.get(grade, GRADE_COLOURS["F"])
    label, value = "FAT", f"{grade} {overall_score}"

    categories = [
        ("SEO", scores.get("seo", {}).get("score", 0)),
        ("Sec", scores.get("security", {}).get("score", 0)),
        ("A11y", scores.get("accessibility", {}).get("score", 0)),
        ("Perf", scores.get("performance", {}).get("score", 0)),
    ]

    # --- image ---
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    img_b64 = base64.b64encode(img_bytes).decode("ascii")
    img_w, img_h = _png_dimensions(img_bytes)
    scale = width / img_w
    scaled_h = round(img_h * scale)

    # --- layout ---
    main_bar_h = 24
    cat_bar_h = 20
    total_height = scaled_h + main_bar_h + cat_bar_h

    # overall bar halves
    label_w, value_w, _ = _bar_halves(label, value, width)
    label_x = round(label_w / 2, 1)
    value_x = round(label_w + value_w / 2, 1)
    main_y = scaled_h
    main_text_y = main_y + round(main_bar_h * 0.67)
    main_shadow_y = main_text_y + 1

    # category bar — 4 equal segments
    cat_y = main_y + main_bar_h
    seg_w = width / len(categories)
    cat_text_y = cat_y + round(cat_bar_h * 0.7)
    cat_shadow_y = cat_text_y + 1

    rx = "0" if style == "flat-square" else "6"

    # build aria description
    cat_desc = ", ".join(f"{c[0]} {c[1]}" for c in categories)
    aria = f"{label}: {value} ({cat_desc})"

    # --- category segment rects + text ---
    cat_rects = ""
    cat_texts = ""
    for i, (cat_label, cat_score) in enumerate(categories):
        x = round(i * seg_w, 1)
        w = round((i + 1) * seg_w) - round(i * seg_w)  # avoid sub-pixel gaps
        colour = score_to_colour(cat_score)
        cx = round(x + w / 2, 1)
        txt = f"{cat_label} {cat_score}"
        cat_rects += (
            f'    <rect x="{x}" y="{cat_y}" width="{w}" '
            f'height="{cat_bar_h}" fill="{colour}"/>\n'
        )
        cat_texts += (
            f'    <text x="{cx}" y="{cat_shadow_y}" fill="#010101" fill-opacity=".3">{txt}</text>\n'
            f'    <text x="{cx}" y="{cat_text_y}">{txt}</text>\n'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg"\n'
        f'     xmlns:xlink="http://www.w3.org/1999/xlink"\n'
        f'     width="{width}" height="{total_height}"\n'
        f'     role="img" aria-label="{aria}">\n'
        f"  <title>{aria}</title>\n"
        f'  <linearGradient id="s" x2="0" y2="100%">\n'
        f'    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>\n'
        f'    <stop offset="1" stop-opacity=".1"/>\n'
        f"  </linearGradient>\n"
        f'  <clipPath id="r">\n'
        f'    <rect width="{width}" height="{total_height}" rx="{rx}" fill="#fff"/>\n'
        f"  </clipPath>\n"
        f'  <g clip-path="url(#r)">\n'
        f'    <image href="data:image/png;base64,{img_b64}"\n'
        f'           width="{width}" height="{scaled_h}"\n'
        f'           preserveAspectRatio="xMidYMid slice"/>\n'
        # overall bar
        f'    <rect y="{main_y}" width="{label_w}" height="{main_bar_h}" fill="#555"/>\n'
        f'    <rect x="{label_w}" y="{main_y}" width="{value_w}" height="{main_bar_h}" fill="{overall_colour}"/>\n'
        f'    <rect y="{main_y}" width="{width}" height="{main_bar_h}" fill="url(#s)"/>\n'
        # category segments
        f"{cat_rects}"
        f'    <rect y="{cat_y}" width="{width}" height="{cat_bar_h}" fill="url(#s)"/>\n'
        f"  </g>\n"
        # overall text
        f'  <g fill="#fff" text-anchor="middle"\n'
        f'     font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">\n'
        f'    <text x="{label_x}" y="{main_shadow_y}" fill="#010101" fill-opacity=".3">{label}</text>\n'
        f'    <text x="{label_x}" y="{main_text_y}">{label}</text>\n'
        f'    <text x="{value_x}" y="{main_shadow_y}" fill="#010101" fill-opacity=".3">{value}</text>\n'
        f'    <text x="{value_x}" y="{main_text_y}">{value}</text>\n'
        f"  </g>\n"
        # category text
        f'  <g fill="#fff" text-anchor="middle"\n'
        f'     font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="10">\n'
        f"{cat_texts}"
        f"  </g>\n"
        f"</svg>\n"
    )


def generate_badge(scores, category=None, style="flat",
                   image_path=None, width=None):
    """Generate a badge from a FAT scores dict.

    Args:
        scores: Dict from calculate-score.py output.
        category: None for overall, or "seo"/"security"/"accessibility"/"performance".
        style: Badge style.
        image_path: Optional path to PNG to embed above the bar.
        width: Badge width (only used when image_path is set; default 200).

    Returns:
        SVG string.
    """
    if category:
        cat = category.lower()
        if cat not in CATEGORY_LABELS:
            raise ValueError(
                f"Unknown category '{cat}'. "
                f"Valid: {', '.join(CATEGORY_LABELS.keys())}"
            )
        label = CATEGORY_LABELS[cat]
        section = scores.get(cat, {})
        score = section.get("score", 0)
        value = str(score)
        colour = score_to_colour(score)
    else:
        overall = scores.get("overall", {})
        score = overall.get("score", 0)
        grade = overall.get("grade", "F")
        label = "FAT"
        value = f"{grade} {score}"
        colour = GRADE_COLOURS.get(grade, GRADE_COLOURS["F"])

    if image_path:
        return generate_badge_with_image(
            image_path, scores,
            width=width or 200, style=style,
        )
    return generate_badge_svg(label, value, colour, style=style)


def main():
    filepath = None
    output = None
    category = None
    style = "flat"
    image = None
    width = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ("--output", "-o") and i + 1 < len(args):
            output = args[i + 1]
            i += 2
        elif args[i] in ("--category", "-c") and i + 1 < len(args):
            category = args[i + 1]
            i += 2
        elif args[i] in ("--style", "-s") and i + 1 < len(args):
            style = args[i + 1]
            i += 2
        elif args[i] in ("--image", "-i") and i + 1 < len(args):
            image = args[i + 1]
            i += 2
        elif args[i] in ("--width", "-w") and i + 1 < len(args):
            width = int(args[i + 1])
            i += 2
        elif args[i] in ("--help", "-h"):
            print(__doc__.strip())
            sys.exit(0)
        else:
            filepath = args[i]
            i += 1

    if filepath:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    svg = generate_badge(data, category=category, style=style,
                         image_path=image, width=width)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(svg)
    else:
        print(svg, end="")


if __name__ == "__main__":
    main()
