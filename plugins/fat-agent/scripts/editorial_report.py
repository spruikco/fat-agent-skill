#!/usr/bin/env python3
"""Editorial audit report — the client's own brand, print-ready.

Renders the FAT audit as an A4-landscape, photography-led HTML deck in the
style of an agency proposal: the client's own hero imagery, logo, accent
colour and typeface (harvested by brandkit.py), one idea per slide, restrained
editorial layout. Print to PDF from any browser for the client deliverable.

Usage:
    python scripts/brandkit.py --url https://client.com --out ./.fat-work/brand
    python scripts/editorial_report.py \
        --scores ./.fat-work/scores.json \
        --sitewide ./.fat-work/sitewide.json \
        --brandkit ./.fat-work/brand/brandkit.json \
        --out ./.fat-work/audit-report.html
"""

import argparse
import base64
import datetime
import html as html_mod
import json
import os
import sys

PRIORITY_LABEL = {"P0": "Critical", "P1": "High", "P2": "Medium", "P3": "Low"}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
FINDINGS_PER_SLIDE = 4
MAX_FINDINGS = 12


def esc(s) -> str:
    return html_mod.escape(str(s or ""))


def img_data_uri(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    ext = os.path.splitext(path)[1].lower()
    mime = {
        ".png": "image/png",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".gif": "image/gif",
    }.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode('ascii')}"


def collect_findings(scores: dict, sitewide: dict) -> list:
    found = list(scores.get("findings") or []) + list(
        (sitewide or {}).get("findings") or []
    )
    found = [f for f in found if isinstance(f, dict) and f.get("title")]
    found.sort(key=lambda f: PRIORITY_ORDER.get(f.get("priority"), 9))
    return found


def category_scores(scores: dict) -> list:
    out = []
    for key, label in (
        ("seo", "SEO"),
        ("security", "Security"),
        ("performance", "Performance"),
        ("accessibility", "Accessibility"),
    ):
        cat = scores.get(key) or {}
        val = cat.get("score")
        note = ""
        if key == "performance":
            note = "heuristic"
        if key == "security" and cat.get("assessed") is False:
            val, note = None, "not assessed"
        out.append((label, val, note))
    return out


def render(scores, sitewide, kit, brand_name):
    site = kit.get("site_name", "Website")
    accent = kit.get("colors", {}).get("accent", "#1c211e")
    fonts = kit.get("fonts", {})
    primary_font = fonts.get("primary", "Plus Jakarta Sans")
    gfonts = fonts.get("google_fonts_url") or (
        "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:"
        "wght@300;400;500;600;700;800&display=swap"
    )
    local = kit.get("images", {}).get("local", {})
    heroes = [img_data_uri(p) for p in local.get("heroes", [])]
    heroes = [h for h in heroes if h]
    logo = img_data_uri(local.get("logo", ""))

    overall = scores.get("overall") or {}
    grade = overall.get("grade", "–")
    score = overall.get("score", "–")
    findings = collect_findings(scores, sitewide)
    shown = findings[:MAX_FINDINGS]
    p0 = sum(1 for f in findings if f.get("priority") == "P0")
    p1 = sum(1 for f in findings if f.get("priority") == "P1")
    today = datetime.date.today().strftime("%d %B %Y")

    def furniture(on_photo=False, page=None):
        cls = ' class="on-photo"' if on_photo else ""
        brand = (
            f'<div class="slide-brand"><img src="{logo}" alt=""></div>'
            if logo
            else f'<div class="slide-brand-text{" on-photo" if on_photo else ""}">{esc(brand_name)}</div>'
        )
        num = f'<div class="page-number">{page}</div>' if page else ""
        return f'<div class="client-word"{cls}>{esc(site)}</div>{brand}{num}'

    slides = []

    # ---- cover ----
    cover_bg = (
        f'<div class="bleed" style="background-image:url({heroes[0]})"></div>'
        '<div class="scrim"></div>'
        if heroes
        else ""
    )
    on_photo = bool(heroes)
    slides.append(f"""<div class="slide cover">{cover_bg}
  {furniture(on_photo=on_photo)}
  <div class="cover-inner{' on-photo' if on_photo else ''}">
    <div class="kicker">Site audit &amp; opportunity report</div>
    <h1>{esc(site)}</h1>
    <div class="cover-meta">{today}</div>
  </div>
</div>""")

    # ---- scorecard ----
    cats = "".join(f"""<div class="cat">
      <div class="cat-score">{val if val is not None else "–"}</div>
      <div class="cat-label">{label}{f'<span class="cat-note"> · {note}</span>' if note else ""}</div>
    </div>""" for label, val, note in category_scores(scores))
    slides.append(f"""<div class="slide">
  {furniture(page=2)}
  <div class="kicker accent">Where the site stands</div>
  <div class="score-row">
    <div class="grade-block">
      <div class="grade">{esc(grade)}</div>
      <div class="grade-sub">{esc(score)} / 100 overall</div>
    </div>
    <div class="cats">{cats}</div>
  </div>
  <p class="score-note">{p0} critical and {p1} high-priority items found.
  Scores follow the FAT method: SEO-weighted, capped by open critical issues.</p>
</div>""")

    # ---- findings slides ----
    page = 3
    for i in range(0, len(shown), FINDINGS_PER_SLIDE):
        batch = shown[i : i + FINDINGS_PER_SLIDE]
        items = "".join(f"""<div class="finding">
      <div class="badge {esc(f.get("priority", "P3"))}">{PRIORITY_LABEL.get(f.get("priority"), "Low")}</div>
      <div class="finding-body">
        <h3>{esc(f.get("title"))}</h3>
        <p>{esc((f.get("description") or "")[:260])}</p>
        <p class="fix">{esc((f.get("fix") or "")[:200])}</p>
      </div>
    </div>""" for f in batch)
        hero_side = ""
        hero_idx = 1 + (i // FINDINGS_PER_SLIDE)
        if hero_idx < len(heroes):
            hero_side = f'<div class="side-photo" style="background-image:url({heroes[hero_idx]})"></div>'
        slides.append(f"""<div class="slide{' with-photo' if hero_side else ''}">
  {hero_side}
  {furniture(page=page)}
  <div class="kicker accent">What we found{" · continued" if i else ""}</div>
  <div class="findings">{items}</div>
</div>""")
        page += 1

    # ---- close ----
    close_bg = (
        f'<div class="bleed" style="background-image:url({heroes[-1]})"></div>'
        '<div class="scrim"></div>'
        if len(heroes) > 1
        else ""
    )
    on_photo = bool(close_bg)
    slides.append(f"""<div class="slide cover">{close_bg}
  {furniture(on_photo=on_photo, page=page)}
  <div class="cover-inner{' on-photo' if on_photo else ''}">
    <div class="kicker">Next steps</div>
    <h2>Fix the {p0 + p1 or len(findings)} priority items first.</h2>
    <div class="cover-meta">Prepared with FAT Agent — every finding re-verified after fixes ship.</div>
  </div>
</div>""")

    css = f"""
:root {{ --ink:#1c211e; --body:#3a3f3c; --muted:#6f746e; --faint:#a9ada6;
  --hair:#e4e2db; --wash:#f7f6f2; --accent:{accent}; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'{primary_font}', 'Plus Jakarta Sans', -apple-system, Arial, sans-serif;
  color:var(--body); background:#efeeea; line-height:1.5; }}
.slide {{ background:#fff; width:297mm; height:210mm; position:relative; overflow:hidden;
  margin:24px auto; padding:16mm 20mm 18mm; page-break-after:always; page-break-inside:avoid;
  box-shadow:0 4px 10px rgba(0,0,0,.12); display:flex; flex-direction:column; justify-content:center; }}
.slide::after {{ content:''; position:absolute; bottom:0; left:0; right:0; height:3px; background:var(--accent); }}
.bleed {{ position:absolute; inset:0; background-size:cover; background-position:center; }}
.scrim {{ position:absolute; inset:0; background:linear-gradient(160deg, rgba(10,14,12,.72), rgba(10,14,12,.35)); }}
.client-word {{ position:absolute; top:12mm; right:20mm; font-size:8pt; font-weight:600;
  letter-spacing:.24em; text-transform:uppercase; color:var(--faint); z-index:6; }}
.client-word.on-photo {{ color:rgba(255,255,255,.85); }}
.slide-brand {{ position:absolute; bottom:8mm; right:20mm; z-index:6; }}
.slide-brand img {{ height:22px; width:auto; display:block; }}
.slide-brand-text {{ position:absolute; bottom:8mm; right:20mm; z-index:6; font-size:8pt;
  font-weight:700; letter-spacing:.2em; text-transform:uppercase; color:var(--faint); }}
.slide-brand-text.on-photo {{ color:rgba(255,255,255,.8); }}
.page-number {{ position:absolute; bottom:8mm; left:50%; transform:translateX(-50%);
  font-size:8pt; color:var(--faint); z-index:6; }}
.kicker {{ font-size:9pt; font-weight:600; letter-spacing:.22em; text-transform:uppercase;
  color:var(--muted); margin-bottom:8mm; }}
.kicker.accent {{ color:var(--accent); }}
.cover-inner {{ position:relative; z-index:5; max-width:180mm; }}
.cover-inner.on-photo, .cover-inner.on-photo .kicker, .cover-inner.on-photo .cover-meta {{ color:#fff; }}
.cover h1 {{ font-size:44pt; font-weight:800; letter-spacing:-.02em; color:var(--ink); line-height:1.05; }}
.cover-inner.on-photo h1, .cover-inner.on-photo h2 {{ color:#fff; }}
.cover h2 {{ font-size:30pt; font-weight:800; letter-spacing:-.01em; color:var(--ink); line-height:1.15; }}
.cover-meta {{ margin-top:8mm; font-size:11pt; color:var(--muted); }}
.score-row {{ display:flex; align-items:center; gap:18mm; }}
.grade {{ font-size:96pt; font-weight:800; color:var(--accent); line-height:1; }}
.grade-sub {{ font-size:11pt; color:var(--muted); margin-top:2mm; }}
.cats {{ display:grid; grid-template-columns:repeat(2, 1fr); gap:8mm 16mm; flex:1; }}
.cat-score {{ font-size:30pt; font-weight:700; color:var(--ink); }}
.cat-label {{ font-size:10pt; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }}
.cat-note {{ text-transform:none; letter-spacing:0; color:var(--faint); }}
.score-note {{ margin-top:12mm; font-size:11pt; color:var(--muted); max-width:170mm; }}
.findings {{ display:flex; flex-direction:column; gap:6mm; max-width:200mm; }}
.with-photo .findings {{ max-width:160mm; }}
.side-photo {{ position:absolute; top:0; right:0; bottom:0; width:85mm;
  background-size:cover; background-position:center; }}
.with-photo {{ padding-right:100mm; }}
.finding {{ display:flex; gap:6mm; align-items:flex-start; border-bottom:1px solid var(--hair); padding-bottom:5mm; }}
.badge {{ flex:0 0 auto; font-size:7.5pt; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  padding:1.5mm 3mm; border-radius:2mm; color:#fff; background:var(--muted); margin-top:1mm; }}
.badge.P0 {{ background:#8c2f22; }} .badge.P1 {{ background:#a96a1f; }}
.badge.P2 {{ background:var(--accent); }} .badge.P3 {{ background:var(--faint); }}
.finding h3 {{ font-size:12.5pt; font-weight:700; color:var(--ink); margin-bottom:1mm; }}
.finding p {{ font-size:9.5pt; color:var(--body); }}
.finding .fix {{ color:var(--muted); margin-top:1mm; }}
@media print {{ body {{ background:#fff; }} .slide {{ margin:0; box-shadow:none; }} }}
@page {{ size:297mm 210mm; margin:0; }}
"""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>{esc(site)} — Site Audit</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{esc(gfonts)}" rel="stylesheet">
<style>{css}</style></head>
<body>{"".join(slides)}</body></html>"""


def main():
    ap = argparse.ArgumentParser(description="editorial brand-led audit report")
    ap.add_argument("--scores", required=True)
    ap.add_argument("--sitewide", default="")
    ap.add_argument("--brandkit", required=True)
    ap.add_argument("--brand-name", default="FAT Agent")
    ap.add_argument("--out", default=os.path.join(".fat-work", "audit-report.html"))
    args = ap.parse_args()

    with open(args.scores, "r", encoding="utf-8") as f:
        scores = json.load(f)
    sitewide = {}
    if args.sitewide and os.path.exists(args.sitewide):
        with open(args.sitewide, "r", encoding="utf-8") as f:
            sitewide = json.load(f)
    with open(args.brandkit, "r", encoding="utf-8") as f:
        kit = json.load(f)

    doc = render(scores, sitewide, kit, args.brand_name)
    parent = os.path.dirname(args.out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"Editorial report written: {args.out} ({len(doc) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
