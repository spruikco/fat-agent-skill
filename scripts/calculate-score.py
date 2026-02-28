#!/usr/bin/env python3
"""
FAT Agent Score Calculator
Takes JSON output from analyse-html.py and produces scored audit report.

Usage:
    python calculate-score.py <path-to-json-file>
    python analyse-html.py index.html | python calculate-score.py

Output: JSON report with SEO, Security, Accessibility, and Overall FAT scores.
"""

import sys
import json


def calculate_seo_score(seo: dict, performance: dict) -> dict:
    """
    SEO Score (0-100) based on seo-checklist.md weightings:
      Title & Meta:              18 points
      Headings & Content:        13 points
      Images:                    10 points
      Technical (robots, etc.):  20 points
      Structured Data:           10 points
      Social / OG Tags:          10 points
      Mobile & Performance:      13 points
      i18n & Charset:             6 points
    """
    score = 0
    details = {}

    # Title & Meta (18 points)
    title_meta = 0
    if seo.get("title_tag"):
        title_meta += 5
        length = seo.get("title_length", 0)
        if 50 <= length <= 60:
            title_meta += 5
        elif 30 <= length <= 70:
            title_meta += 3
        elif length > 0:
            title_meta += 1
    if seo.get("meta_description"):
        title_meta += 4
        length = seo.get("meta_description_length", 0)
        if 150 <= length <= 160:
            title_meta += 4
        elif 120 <= length <= 170:
            title_meta += 3
        elif length > 0:
            title_meta += 1
    # Penalise duplicate titles/descriptions
    if seo.get("duplicate_title_tags", 1) > 1:
        title_meta = max(title_meta - 3, 0)
    if seo.get("duplicate_meta_descriptions", 1) > 1:
        title_meta = max(title_meta - 3, 0)
    details["title_meta"] = {"score": title_meta, "max": 18}
    score += title_meta

    # Headings & Content (13 points)
    headings = 0
    h1_count = seo.get("h1_count", 0)
    if h1_count == 1:
        headings += 8
    elif h1_count > 1:
        headings += 3
    hierarchy = seo.get("heading_hierarchy", [])
    if hierarchy:
        is_logical = True
        for i in range(1, len(hierarchy)):
            if hierarchy[i] > hierarchy[i - 1] + 1:
                is_logical = False
                break
        if is_logical:
            headings += 5
        else:
            headings += 2
    details["headings_content"] = {"score": headings, "max": 13}
    score += headings

    # Images (10 points)
    images = 0
    img_total = seo.get("img_total", 0)
    img_missing = seo.get("img_missing_alt", 0)
    if img_total == 0:
        images = 10
    elif img_missing == 0:
        images = 10
    else:
        ratio = (img_total - img_missing) / img_total
        images = round(ratio * 10)
    details["images"] = {"score": images, "max": 10}
    score += images

    # Technical SEO (20 points)
    technical = 0
    if seo.get("has_canonical"):
        technical += 5
    # Penalise duplicate canonicals
    if seo.get("duplicate_canonicals", 1) > 1:
        technical = max(technical - 3, 0)
    if seo.get("has_robots_meta"):
        content = seo.get("robots_content", "")
        if "noindex" not in content:
            technical += 5
        else:
            technical += 2
    else:
        technical += 5  # No robots meta is fine (defaults to index)
    if seo.get("has_favicon"):
        technical += 5
    # Sitemap and robots.txt can't be checked from HTML alone — give partial
    technical += 5
    details["technical"] = {"score": technical, "max": 20}
    score += technical

    # Structured Data (10 points)
    structured = 0
    json_ld_count = seo.get("json_ld_count", 0)
    if json_ld_count >= 1:
        structured += 7
    if json_ld_count >= 2:
        structured += 3
    details["structured_data"] = {"score": structured, "max": 10}
    score += structured

    # Social / OG Tags (10 points)
    social = 0
    og = seo.get("og_tags", {})
    twitter = seo.get("twitter_tags", {})
    og_keys = ["og:title", "og:description", "og:image", "og:url"]
    og_present = sum(1 for k in og_keys if k in og)
    social += min(og_present * 2, 6)
    if twitter:
        social += 4
    details["social"] = {"score": social, "max": 10}
    score += social

    # Mobile & Performance Signals (13 points)
    mobile_perf = 0
    if performance.get("has_preconnect"):
        mobile_perf += 2
    if performance.get("has_preload"):
        mobile_perf += 2
    blocking = performance.get("render_blocking_scripts", 0)
    if blocking == 0:
        mobile_perf += 3
    elif blocking <= 2:
        mobile_perf += 1
    html_kb = performance.get("html_size_kb", 0)
    if html_kb <= 100:
        mobile_perf += 4
    elif html_kb <= 200:
        mobile_perf += 2
    else:
        mobile_perf += 1
    # Viewport validation
    if seo.get("viewport_valid"):
        mobile_perf += 2
    details["mobile_performance"] = {"score": mobile_perf, "max": 13}
    score += mobile_perf

    # i18n & Charset (6 points)
    i18n = 0
    if seo.get("has_charset"):
        i18n += 3
    hreflang = seo.get("hreflang_tags", [])
    if hreflang:
        i18n += 3
    else:
        i18n += 1  # Partial credit — not every site needs hreflang
    details["i18n_charset"] = {"score": i18n, "max": 6}
    score += i18n

    return {"score": min(score, 100), "max": 100, "details": details}


def calculate_security_score(headers: dict, html_security: dict = None) -> dict:
    """
    Security Score (0-100) based on security-headers.md weightings:
      CSP:                  30 points
      HSTS:                 18 points
      X-Content-Type:       8 points
      X-Frame-Options:      8 points  (or CSP frame-ancestors)
      Referrer-Policy:      8 points
      Permissions-Policy:   13 points
      Mixed content:        10 points (from HTML analysis)
      Link safety:          5 points  (noopener on _blank)

    Takes a dict of response headers (lowercase keys) and optional
    html_security dict from analyse-html.py's security section.
    """
    score = 0
    details = {}
    html_sec = html_security or {}

    # Mixed content from HTML (10 points) — always available
    mixed = 10
    if html_sec.get("has_mixed_content"):
        mixed = 0
    details["mixed_content"] = {"score": mixed, "max": 10}
    score += mixed

    # Link safety — noopener (5 points)
    link_safety = 5
    ext_total = html_sec.get("external_links_total", 0)
    ext_no_opener = html_sec.get("external_links_without_noopener", 0)
    if ext_total > 0 and ext_no_opener > 0:
        ratio = (ext_total - ext_no_opener) / ext_total
        link_safety = round(ratio * 5)
    details["link_safety"] = {"score": link_safety, "max": 5}
    score += link_safety

    if not headers:
        return {
            "score": score,
            "max": 100,
            "details": details,
            "note": "No response headers available — header-based scoring incomplete",
        }

    h = {k.lower(): v for k, v in headers.items()}

    # CSP (30 points)
    csp = 0
    if "content-security-policy" in h:
        csp = 30
    elif "content-security-policy-report-only" in h:
        csp = 13
    details["csp"] = {"score": csp, "max": 30}
    score += csp

    # HSTS (18 points)
    hsts = 0
    hsts_val = h.get("strict-transport-security", "")
    if hsts_val:
        hsts = 8
        if "includesubdomains" in hsts_val.lower():
            hsts += 5
        if "preload" in hsts_val.lower():
            hsts += 5
    details["hsts"] = {"score": hsts, "max": 18}
    score += hsts

    # X-Content-Type-Options (8 points)
    xcto = 0
    if h.get("x-content-type-options", "").lower() == "nosniff":
        xcto = 8
    details["x_content_type_options"] = {"score": xcto, "max": 8}
    score += xcto

    # X-Frame-Options (8 points)
    xfo = 0
    xfo_val = h.get("x-frame-options", "").upper()
    if xfo_val in ("DENY", "SAMEORIGIN"):
        xfo = 8
    elif "content-security-policy" in h and "frame-ancestors" in h["content-security-policy"]:
        xfo = 8
    details["x_frame_options"] = {"score": xfo, "max": 8}
    score += xfo

    # Referrer-Policy (8 points)
    rp = 0
    rp_val = h.get("referrer-policy", "")
    if rp_val:
        rp = 8
    details["referrer_policy"] = {"score": rp, "max": 8}
    score += rp

    # Permissions-Policy (13 points)
    pp = 0
    if "permissions-policy" in h:
        pp = 13
    details["permissions_policy"] = {"score": pp, "max": 13}
    score += pp

    return {"score": min(score, 100), "max": 100, "details": details}


def calculate_accessibility_score(a11y: dict) -> dict:
    """
    Accessibility Score (0-100) based on accessibility-guide.md:
      Images with alt text:             18 points
      Language attribute:                5 points
      Form accessibility:               13 points
      Heading structure:                 10 points
      Skip navigation:                  5 points
      Landmark regions:                 10 points
      Image dimensions (CLS):           4 points
      Empty headings penalty:           5 points
      Keyboard accessibility (user):    12 points — defaults to partial
      Focus visibility (user):          9 points — defaults to partial
      Contrast (user):                  9 points — defaults to partial
    """
    score = 0
    details = {}

    # Images with alt text (18 points)
    img_total = a11y.get("img_total", 0)
    img_missing = a11y.get("img_missing_alt", 0)
    if img_total == 0:
        img_score = 18
    elif img_missing == 0:
        img_score = 18
    else:
        ratio = (img_total - img_missing) / img_total
        img_score = round(ratio * 18)
    details["images_alt"] = {"score": img_score, "max": 18}
    score += img_score

    # Language attribute (5 points)
    lang = 5 if a11y.get("has_lang_attribute") else 0
    details["lang_attribute"] = {"score": lang, "max": 5}
    score += lang

    # Form accessibility (13 points)
    form_total = a11y.get("form_inputs_total", 0)
    form_missing = a11y.get("form_inputs_without_label", 0)
    if form_total == 0:
        form_score = 13
    elif form_missing == 0:
        form_score = 13
    else:
        ratio = (form_total - form_missing) / form_total
        form_score = round(ratio * 13)
    details["form_accessibility"] = {"score": form_score, "max": 13}
    score += form_score

    # Heading structure (10 points)
    heading_score = 10
    empty = a11y.get("empty_headings", 0)
    if empty > 0:
        heading_score = max(heading_score - (empty * 3), 0)
    details["heading_structure"] = {"score": heading_score, "max": 10}
    score += heading_score

    # Skip navigation (5 points)
    skip = 5 if a11y.get("has_skip_link") else 0
    details["skip_navigation"] = {"score": skip, "max": 5}
    score += skip

    # Landmark regions (10 points)
    landmarks = a11y.get("landmarks_found", [])
    expected = {"main", "nav", "header", "footer"}
    found = set(landmarks) & expected
    landmark_score = min(len(found) * 3, 10)
    details["landmarks"] = {"score": landmark_score, "max": 10}
    score += landmark_score

    # Image dimensions for CLS prevention (4 points)
    img_dims = 0
    img_with_dims = a11y.get("img_with_dimensions", 0)
    if img_total == 0:
        img_dims = 4
    elif img_with_dims >= img_total:
        img_dims = 4
    elif img_with_dims > 0:
        ratio = img_with_dims / img_total
        img_dims = round(ratio * 4)
    details["image_dimensions"] = {"score": img_dims, "max": 4}
    score += img_dims

    # Empty headings deduction (5 points — start with full, lose per empty)
    empty_score = 5
    if empty > 0:
        empty_score = max(5 - (empty * 2), 0)
    details["empty_headings"] = {"score": empty_score, "max": 5}
    score += empty_score

    # User-reported scores default to partial credit (not tested)
    keyboard = a11y.get("keyboard_score", 7)
    details["keyboard"] = {"score": keyboard, "max": 12, "note": "user-reported or default"}
    score += keyboard

    focus = a11y.get("focus_score", 5)
    details["focus_visibility"] = {"score": focus, "max": 9, "note": "user-reported or default"}
    score += focus

    contrast = a11y.get("contrast_score", 5)
    details["contrast"] = {"score": contrast, "max": 9, "note": "user-reported or default"}
    score += contrast

    return {"score": min(score, 100), "max": 100, "details": details}


def calculate_performance_score(performance: dict) -> dict:
    """
    Performance Score (0-100) — new dimension covering:
      HTML size:                15 points
      Render-blocking scripts:  15 points
      Image optimisation:       20 points
      Resource hints:           15 points
      Font loading:             15 points
      Inline asset size:        10 points
      Lazy loading:             10 points
    """
    score = 0
    details = {}

    # HTML size (15 points)
    html_kb = performance.get("html_size_kb", 0)
    if html_kb <= 50:
        html_pts = 15
    elif html_kb <= 100:
        html_pts = 12
    elif html_kb <= 200:
        html_pts = 7
    else:
        html_pts = 2
    details["html_size"] = {"score": html_pts, "max": 15}
    score += html_pts

    # Render-blocking scripts (15 points)
    blocking = performance.get("render_blocking_scripts", 0)
    if blocking == 0:
        block_pts = 15
    elif blocking <= 1:
        block_pts = 10
    elif blocking <= 2:
        block_pts = 6
    elif blocking <= 4:
        block_pts = 3
    else:
        block_pts = 0
    details["render_blocking"] = {"score": block_pts, "max": 15}
    score += block_pts

    # Image optimisation (20 points)
    img_total = performance.get("images_total", 0)
    img_pts = 0
    if img_total == 0:
        img_pts = 20
    else:
        # Srcset / picture elements (10 points)
        srcset = performance.get("images_with_srcset", 0)
        picture = performance.get("picture_elements", 0)
        responsive = srcset + picture
        if responsive >= img_total:
            img_pts += 10
        elif responsive > 0:
            img_pts += round((responsive / img_total) * 10)
        # Modern formats (10 points)
        modern = performance.get("images_modern_format", 0)
        if modern >= img_total:
            img_pts += 10
        elif modern > 0:
            img_pts += round((modern / img_total) * 10)
        else:
            img_pts += 3  # Partial — not everyone uses WebP/AVIF yet
    details["image_optimisation"] = {"score": img_pts, "max": 20}
    score += img_pts

    # Resource hints (15 points)
    hints = 0
    if performance.get("has_preconnect"):
        hints += 8
    if performance.get("has_preload"):
        hints += 7
    details["resource_hints"] = {"score": hints, "max": 15}
    score += hints

    # Font loading (15 points)
    font_pts = 0
    if performance.get("has_font_display_swap"):
        font_pts += 7
    if performance.get("has_google_fonts_preconnect"):
        font_pts += 4
    if performance.get("font_preloads", 0) > 0:
        font_pts += 4
    # If no font-related signals at all, give partial credit
    if font_pts == 0:
        font_pts = 5  # Many sites don't need font optimisation
    details["font_loading"] = {"score": font_pts, "max": 15}
    score += font_pts

    # Inline asset size (10 points)
    inline_script_kb = performance.get("inline_script_kb", 0)
    inline_style_kb = performance.get("inline_style_kb", 0)
    total_inline = inline_script_kb + inline_style_kb
    if total_inline <= 10:
        inline_pts = 10
    elif total_inline <= 30:
        inline_pts = 7
    elif total_inline <= 50:
        inline_pts = 4
    else:
        inline_pts = 1
    details["inline_assets"] = {"score": inline_pts, "max": 10}
    score += inline_pts

    # Lazy loading (10 points)
    lazy = performance.get("images_lazy_loaded", 0)
    if img_total == 0:
        lazy_pts = 10
    elif img_total <= 1:
        lazy_pts = 10  # Single image pages don't need lazy loading
    else:
        # At least some below-fold images should be lazy
        if lazy > 0:
            ratio = lazy / img_total
            lazy_pts = round(ratio * 10)
            lazy_pts = max(lazy_pts, 5)  # At least partial credit for trying
        else:
            lazy_pts = 3  # Some credit — not all sites need it
    details["lazy_loading"] = {"score": lazy_pts, "max": 10}
    score += lazy_pts

    return {"score": min(score, 100), "max": 100, "details": details}


def calculate_fat_score(seo_score: int, security_score: int, a11y_score: int, perf_score: int = None) -> dict:
    """
    Overall FAT Score — weighted composite:
      SEO:            30%
      Security:       25%
      Accessibility:  30%
      Performance:    15%

    If performance score not available, uses original 3-category weighting.
    """
    if perf_score is not None:
        weighted = (seo_score * 0.30) + (security_score * 0.25) + (a11y_score * 0.30) + (perf_score * 0.15)
        weights = {"seo": 0.30, "security": 0.25, "accessibility": 0.30, "performance": 0.15}
    else:
        weighted = (seo_score * 0.35) + (security_score * 0.30) + (a11y_score * 0.35)
        weights = {"seo": 0.35, "security": 0.30, "accessibility": 0.35}

    overall = round(weighted)

    if overall >= 90:
        grade = "A"
    elif overall >= 75:
        grade = "B"
    elif overall >= 60:
        grade = "C"
    elif overall >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": overall,
        "max": 100,
        "grade": grade,
        "weights": weights,
    }


def calculate_scores(report: dict, headers: dict | None = None) -> dict:
    """
    Main entry point. Takes a full analyse-html.py report and optional
    HTTP response headers dict.

    Returns scored JSON report.
    """
    seo = report.get("seo", {})
    a11y = report.get("accessibility", {})
    performance = report.get("performance", {})
    html_security = report.get("security", {})

    # Merge image data into SEO for the scorer
    seo_input = {**seo, "img_total": a11y.get("img_total", 0), "img_missing_alt": a11y.get("img_missing_alt", 0)}

    seo_result = calculate_seo_score(seo_input, performance)
    security_result = calculate_security_score(headers or {}, html_security)
    a11y_result = calculate_accessibility_score(a11y)
    perf_result = calculate_performance_score(performance)
    fat_result = calculate_fat_score(
        seo_result["score"],
        security_result["score"],
        a11y_result["score"],
        perf_result["score"],
    )

    return {
        "seo": seo_result,
        "security": security_result,
        "accessibility": a11y_result,
        "performance": perf_result,
        "overall": fat_result,
        "summary": report.get("summary", {}),
    }


def main():
    if len(sys.argv) >= 2:
        filepath = sys.argv[1]
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    # Support optional headers file as second arg
    headers = None
    if len(sys.argv) >= 3:
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            headers = json.load(f)

    # If data has a top-level "report" key, unwrap it
    report = data.get("report", data) if isinstance(data, dict) else data

    result = calculate_scores(report, headers)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
