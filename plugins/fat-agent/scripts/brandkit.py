#!/usr/bin/env python3
"""Extract a client brand kit from their live site — for editorial reports.

Harvests, from the audited site's own HTML/CSS: the logo, Open Graph and hero
images, the colour palette (dominant saturated colour becomes the accent), and
the font stack (Google Fonts link + first font-family). The editorial report
then renders the audit in the client's own visual language instead of a
generic template.

Usage:
    python scripts/brandkit.py --url https://example.com \
        --out ./.fat-work/brand           # writes brandkit.json + images/
"""

import argparse
import colorsys
import json
import os
import re
import sys
from collections import Counter
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

UA = "FATAgent/1.0 (+https://github.com/spruikco/fat-agent-skill)"
MAX_IMAGES = 6
MAX_IMG_BYTES = 4_000_000

HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
FONT_LINK_RE = re.compile(
    r'<link[^>]+href=["\']([^"\']*fonts\.googleapis\.com/css2?[^"\']*)["\']',
    re.IGNORECASE,
)
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*['\"]?([^;'\",}]+)", re.IGNORECASE)
IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ATTR_RE = re.compile(r"""([a-zA-Z\-]+)\s*=\s*["']([^"']*)["']""")
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)
CSS_LINK_RE = re.compile(
    r'<link[^>]+rel=["\'][^"\']*stylesheet[^"\']*["\'][^>]*href=["\']([^"\']+)["\']'
    r'|<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\'][^"\']*stylesheet',
    re.IGNORECASE,
)

GENERIC_FONTS = {
    "sans-serif",
    "serif",
    "monospace",
    "system-ui",
    "-apple-system",
    "inherit",
    "initial",
    "var",
    "arial",
    "helvetica",
}


def fetch(url: str, binary: bool = False, timeout: float = 15.0):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read(MAX_IMG_BYTES)
        if binary:
            return raw, resp.headers.get_content_type()
        return raw.decode("utf-8", errors="replace"), resp.headers.get_content_type()


def _saturation(hex_colour: str) -> tuple:
    """(is_usable_accent_sort_key) — prefer saturated, mid-lightness colours."""
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    hue, lightness, sat = colorsys.rgb_to_hls(r, g, b)
    return sat, 1 - abs(lightness - 0.45)


def extract_palette(css_text: str) -> dict:
    counts = Counter(m.group(0).lower() for m in HEX_RE.finditer(css_text))

    # ignore near-white/near-black boilerplate for the accent pick
    def usable(c):
        sat, mid = _saturation(c)
        return sat > 0.25 and mid > 0.35

    candidates = [(c, n) for c, n in counts.most_common(80) if usable(c)]
    accent = candidates[0][0] if candidates else "#1c211e"
    return {
        "accent": accent,
        "palette": [c for c, _ in counts.most_common(12)],
    }


def extract_fonts(html: str, css_text: str) -> dict:
    google_links = FONT_LINK_RE.findall(html)
    families = []
    for m in FONT_FAMILY_RE.finditer(css_text + html):
        fam = m.group(1).split(",")[0].strip().strip("'\"")
        if fam and fam.lower() not in GENERIC_FONTS and not fam.startswith("--"):
            if fam not in families:
                families.append(fam)
    return {
        "google_fonts_url": google_links[0] if google_links else "",
        "families": families[:4],
        "primary": families[0] if families else "Plus Jakarta Sans",
    }


def find_images(html: str, base_url: str) -> dict:
    logo = ""
    heroes = []
    for tag in IMG_RE.findall(html):
        attrs = {k.lower(): v for k, v in ATTR_RE.findall(tag)}
        src = attrs.get("src", "")
        if not src or src.startswith("data:"):
            continue
        blob = " ".join([src, attrs.get("alt", ""), attrs.get("class", "")]).lower()
        if not logo and "logo" in blob:
            logo = urljoin(base_url, src)
        elif re.search(r"\.(jpe?g|png|webp)(\?|$)", src, re.IGNORECASE):
            heroes.append(urljoin(base_url, src))

    m = OG_IMAGE_RE.search(html)
    og = urljoin(base_url, (m.group(1) or m.group(2))) if m else ""
    if og and og not in heroes:
        heroes.insert(0, og)

    seen, uniq = set(), []
    for h in heroes:
        if h not in seen:
            seen.add(h)
            uniq.append(h)
    return {"logo": logo, "og_image": og, "heroes": uniq[:MAX_IMAGES]}


def download_images(images: dict, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    local = {"logo": "", "heroes": []}
    targets = [("logo", images["logo"])] if images["logo"] else []
    targets += [(f"hero-{i + 1}", u) for i, u in enumerate(images["heroes"])]
    for name, url in targets:
        try:
            raw, ctype = fetch(url, binary=True)
        except Exception:
            continue
        ext = {
            "image/png": ".png",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
            "image/gif": ".gif",
        }.get(ctype, ".jpg")
        path = os.path.join(out_dir, name + ext)
        with open(path, "wb") as f:
            f.write(raw)
        if name == "logo":
            local["logo"] = path
        else:
            local["heroes"].append(path)
    return local


def build_brandkit(url: str, out_dir: str) -> dict:
    html, _ = fetch(url)
    base = url

    css_text = ""
    css_urls = []
    for m in CSS_LINK_RE.finditer(html):
        href = m.group(1) or m.group(2)
        if href:
            css_urls.append(urljoin(base, href))
    for css_url in css_urls[:4]:
        try:
            body, _ = fetch(css_url)
            css_text += body[:400_000]
        except Exception:
            continue
    # inline <style> blocks count too
    css_text += " ".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL))

    site_name = ""
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if m:
        site_name = m.group(1).split("|")[0].split("–")[0].strip()

    images = find_images(html, base)
    local = download_images(images, os.path.join(out_dir, "images"))

    kit = {
        "url": url,
        "site_name": site_name or urlparse(url).netloc,
        "colors": extract_palette(css_text),
        "fonts": extract_fonts(html, css_text),
        "images": {**images, "local": local},
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "brandkit.json"), "w", encoding="utf-8") as f:
        json.dump(kit, f, indent=2)
    return kit


def main():
    ap = argparse.ArgumentParser(description="extract a client brand kit")
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", default=os.path.join(".fat-work", "brand"))
    args = ap.parse_args()
    kit = build_brandkit(args.url, args.out)
    summary = {
        "site_name": kit["site_name"],
        "accent": kit["colors"]["accent"],
        "primary_font": kit["fonts"]["primary"],
        "logo": kit["images"]["local"]["logo"],
        "heroes": len(kit["images"]["local"]["heroes"]),
        "brandkit": os.path.join(args.out, "brandkit.json"),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
