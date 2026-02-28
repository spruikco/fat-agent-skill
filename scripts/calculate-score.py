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
      Title & Meta:              20 points
      Headings & Content:        15 points
      Images:                    10 points
      Technical (robots, etc.):  20 points
      Structured Data:           10 points
      Social / OG Tags:          10 points
      Mobile & Performance:      15 points
    """
    score = 0
    details = {}

    # Title & Meta (20 points)
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
        title_meta += 5
        length = seo.get("meta_description_length", 0)
        if 150 <= length <= 160:
            title_meta += 5
        elif 120 <= length <= 170:
            title_meta += 3
        elif length > 0:
            title_meta += 1
    details["title_meta"] = {"score": title_meta, "max": 20}
    score += title_meta

    # Headings & Content (15 points)
    headings = 0
    h1_count = seo.get("h1_count", 0)
    if h1_count == 1:
        headings += 10
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
    details["headings_content"] = {"score": headings, "max": 15}
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
    else:
        social += 0
    details["social"] = {"score": social, "max": 10}
    score += social

    # Mobile & Performance Signals (15 points)
    mobile_perf = 0
    if performance.get("has_preconnect"):
        mobile_perf += 3
    if performance.get("has_preload"):
        mobile_perf += 3
    blocking = performance.get("render_blocking_scripts", 0)
    if blocking == 0:
        mobile_perf += 4
    elif blocking <= 2:
        mobile_perf += 2
    html_kb = performance.get("html_size_kb", 0)
    if html_kb <= 100:
        mobile_perf += 5
    elif html_kb <= 200:
        mobile_perf += 3
    else:
        mobile_perf += 1
    details["mobile_performance"] = {"score": mobile_perf, "max": 15}
    score += mobile_perf

    return {"score": score, "max": 100, "details": details}


def calculate_security_score(headers: dict) -> dict:
    """
    Security Score (0-100) based on security-headers.md weightings:
      CSP:                  35 points
      HSTS:                 20 points
      X-Content-Type:       10 points
      X-Frame-Options:      10 points  (or CSP frame-ancestors)
      Referrer-Policy:      10 points
      Permissions-Policy:   15 points

    Takes a dict of response headers (lowercase keys).
    If no headers provided, scores based on what analyse-html.py can detect.
    """
    score = 0
    details = {}

    if not headers:
        return {
            "score": 0,
            "max": 100,
            "details": {},
            "note": "No response headers available — security scoring requires HTTP headers",
        }

    h = {k.lower(): v for k, v in headers.items()}

    # CSP (35 points)
    csp = 0
    if "content-security-policy" in h:
        csp = 35
    elif "content-security-policy-report-only" in h:
        csp = 15
    details["csp"] = {"score": csp, "max": 35}
    score += csp

    # HSTS (20 points)
    hsts = 0
    hsts_val = h.get("strict-transport-security", "")
    if hsts_val:
        hsts = 10
        if "includesubdomains" in hsts_val.lower():
            hsts += 5
        if "preload" in hsts_val.lower():
            hsts += 5
    details["hsts"] = {"score": hsts, "max": 20}
    score += hsts

    # X-Content-Type-Options (10 points)
    xcto = 0
    if h.get("x-content-type-options", "").lower() == "nosniff":
        xcto = 10
    details["x_content_type_options"] = {"score": xcto, "max": 10}
    score += xcto

    # X-Frame-Options (10 points)
    xfo = 0
    xfo_val = h.get("x-frame-options", "").upper()
    if xfo_val in ("DENY", "SAMEORIGIN"):
        xfo = 10
    elif "content-security-policy" in h and "frame-ancestors" in h["content-security-policy"]:
        xfo = 10
    details["x_frame_options"] = {"score": xfo, "max": 10}
    score += xfo

    # Referrer-Policy (10 points)
    rp = 0
    rp_val = h.get("referrer-policy", "")
    if rp_val:
        rp = 10
    details["referrer_policy"] = {"score": rp, "max": 10}
    score += rp

    # Permissions-Policy (15 points)
    pp = 0
    if "permissions-policy" in h:
        pp = 15
    details["permissions_policy"] = {"score": pp, "max": 15}
    score += pp

    return {"score": score, "max": 100, "details": details}


def calculate_accessibility_score(a11y: dict) -> dict:
    """
    Accessibility Score (0-100) based on accessibility-guide.md:
      Images with alt text:             20 points
      Language attribute:                5 points
      Form accessibility:               15 points
      Heading structure:                 10 points
      Skip navigation:                  5 points
      Landmark regions:                 10 points
      Keyboard accessibility (user):    15 points — defaults to partial
      Focus visibility (user):          10 points — defaults to partial
      Contrast (user):                  10 points — defaults to partial
    """
    score = 0
    details = {}

    # Images with alt text (20 points)
    img_total = a11y.get("img_total", 0)
    img_missing = a11y.get("img_missing_alt", 0)
    if img_total == 0:
        img_score = 20
    elif img_missing == 0:
        img_score = 20
    else:
        ratio = (img_total - img_missing) / img_total
        img_score = round(ratio * 20)
    details["images_alt"] = {"score": img_score, "max": 20}
    score += img_score

    # Language attribute (5 points)
    lang = 5 if a11y.get("has_lang_attribute") else 0
    details["lang_attribute"] = {"score": lang, "max": 5}
    score += lang

    # Form accessibility (15 points)
    form_total = a11y.get("form_inputs_total", 0)
    form_missing = a11y.get("form_inputs_without_label", 0)
    if form_total == 0:
        form_score = 15
    elif form_missing == 0:
        form_score = 15
    else:
        ratio = (form_total - form_missing) / form_total
        form_score = round(ratio * 15)
    details["form_accessibility"] = {"score": form_score, "max": 15}
    score += form_score

    # Heading structure (10 points)
    # Reuse heading info from SEO data if available via parent report
    heading_score = 10  # Default — will be adjusted below if data available
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

    # User-reported scores default to partial credit (not tested)
    keyboard = a11y.get("keyboard_score", 8)
    details["keyboard"] = {"score": keyboard, "max": 15, "note": "user-reported or default"}
    score += keyboard

    focus = a11y.get("focus_score", 5)
    details["focus_visibility"] = {"score": focus, "max": 10, "note": "user-reported or default"}
    score += focus

    contrast = a11y.get("contrast_score", 5)
    details["contrast"] = {"score": contrast, "max": 10, "note": "user-reported or default"}
    score += contrast

    return {"score": min(score, 100), "max": 100, "details": details}


def calculate_fat_score(seo_score: int, security_score: int, a11y_score: int) -> dict:
    """
    Overall FAT Score — weighted composite:
      SEO:            35%
      Security:       30%
      Accessibility:  35%
    """
    weighted = (seo_score * 0.35) + (security_score * 0.30) + (a11y_score * 0.35)
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
        "weights": {"seo": 0.35, "security": 0.30, "accessibility": 0.35},
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

    # Merge image data into SEO for the scorer
    seo_input = {**seo, "img_total": a11y.get("img_total", 0), "img_missing_alt": a11y.get("img_missing_alt", 0)}

    seo_result = calculate_seo_score(seo_input, performance)
    security_result = calculate_security_score(headers or {})
    a11y_result = calculate_accessibility_score(a11y)
    fat_result = calculate_fat_score(seo_result["score"], security_result["score"], a11y_result["score"])

    return {
        "seo": seo_result,
        "security": security_result,
        "accessibility": a11y_result,
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
