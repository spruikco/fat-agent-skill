"""SEO core audit module.

Thin wrapper that extracts key SEO signals from raw HTML and scores them
using the same weighting logic as calculate-score.py's calculate_seo_score.
"""

from __future__ import annotations

import re

from modules import register_module
from modules.base import AuditModule


@register_module
class SEOModule(AuditModule):
    MODULE_ID = "seo"
    DISPLAY_NAME = "SEO"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL
        )
        title_tag = title_match.group(1).strip() if title_match else ""
        title_length = len(title_tag)

        meta_desc = ""
        meta_match = re.search(
            r'<meta\s[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
            html,
            re.IGNORECASE,
        )
        if not meta_match:
            meta_match = re.search(
                r'<meta\s[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']',
                html,
                re.IGNORECASE,
            )
        if meta_match:
            meta_desc = meta_match.group(1).strip()
        meta_description_length = len(meta_desc)

        h1_count = len(re.findall(r"<h1[\s>]", html, re.IGNORECASE))

        has_canonical = bool(
            re.search(r'<link[^>]*rel=["\']canonical["\']', html, re.IGNORECASE)
        )

        og_tags = {}
        for m in re.finditer(
            r'<meta\s[^>]*property=["\']([^"\']+)["\'][^>]*content=["\']([^"\']*)["\']',
            html,
            re.IGNORECASE,
        ):
            prop = m.group(1)
            if prop.startswith("og:"):
                og_tags[prop] = m.group(2)

        robots_match = re.search(
            r'<meta\s[^>]*name=["\']robots["\'][^>]*content=["\']([^"\']*)["\']',
            html,
            re.IGNORECASE,
        )
        has_robots_meta = bool(robots_match)
        robots_content = robots_match.group(1) if robots_match else ""

        json_ld_count = len(
            re.findall(
                r'<script[^>]*type=["\']application/ld\+json["\']',
                html,
                re.IGNORECASE,
            )
        )

        return {
            "title_tag": title_tag,
            "title_length": title_length,
            "meta_description": meta_desc,
            "meta_description_length": meta_description_length,
            "h1_count": h1_count,
            "has_canonical": has_canonical,
            "og_tags": og_tags,
            "has_robots_meta": has_robots_meta,
            "robots_content": robots_content,
            "json_ld_count": json_ld_count,
        }

    def score(self, analysis: dict) -> dict:
        total = 0
        details = {}

        # title & meta (18 points)
        title_meta = 0
        if analysis.get("title_tag"):
            title_meta += 5
            length = analysis.get("title_length", 0)
            if 50 <= length <= 60:
                title_meta += 5
            elif 30 <= length <= 70:
                title_meta += 3
            elif length > 0:
                title_meta += 1
        if analysis.get("meta_description"):
            title_meta += 4
            length = analysis.get("meta_description_length", 0)
            if 150 <= length <= 160:
                title_meta += 4
            elif 120 <= length <= 170:
                title_meta += 3
            elif length > 0:
                title_meta += 1
        details["title_meta"] = {"score": title_meta, "max": 18}
        total += title_meta

        # headings (8 points)
        headings = 0
        h1_count = analysis.get("h1_count", 0)
        if h1_count == 1:
            headings = 8
        elif h1_count > 1:
            headings = 3
        details["headings"] = {"score": headings, "max": 8}
        total += headings

        # canonical (5 points)
        canonical = 5 if analysis.get("has_canonical") else 0
        details["canonical"] = {"score": canonical, "max": 5}
        total += canonical

        # structured data (10 points)
        structured = 0
        json_ld = analysis.get("json_ld_count", 0)
        if json_ld >= 1:
            structured += 7
        if json_ld >= 2:
            structured += 3
        details["structured_data"] = {"score": structured, "max": 10}
        total += structured

        # og tags (10 points)
        og = analysis.get("og_tags", {})
        og_keys = ["og:title", "og:description", "og:image", "og:url"]
        og_present = sum(1 for k in og_keys if k in og)
        social = min(og_present * 2, 8) + (2 if len(og) > 0 else 0)
        social = min(social, 10)
        details["social"] = {"score": social, "max": 10}
        total += social

        # robots meta (5 points)
        robots = 5
        if analysis.get("has_robots_meta"):
            content = analysis.get("robots_content", "")
            if "noindex" in content.lower():
                robots = 0
                self.add_finding(
                    priority="P0",
                    title="Page is set to noindex",
                    description="The robots meta tag contains noindex, preventing search engine indexing.",
                    fix="Remove noindex from the robots meta tag if this page should be indexed.",
                    effort="low",
                )
        details["robots"] = {"score": robots, "max": 5}
        total += robots

        if not analysis.get("title_tag"):
            self.add_finding(
                priority="P0",
                title="Missing title tag",
                description="No <title> tag found. This is critical for SEO.",
                fix="Add a unique, descriptive title tag between 50-60 characters.",
                effort="low",
            )

        if not analysis.get("meta_description"):
            self.add_finding(
                priority="P1",
                title="Missing meta description",
                description="No meta description found. Search engines use this for snippets.",
                fix="Add a meta description between 150-160 characters.",
                effort="low",
            )

        h1 = analysis.get("h1_count", 0)
        if h1 == 0:
            self.add_finding(
                priority="P1",
                title="Missing H1 heading",
                description="No H1 heading found on the page.",
                fix="Add a single H1 heading that describes the page content.",
                effort="low",
            )
        elif h1 > 1:
            self.add_finding(
                priority="P2",
                title="Multiple H1 headings",
                description=f"Found {h1} H1 headings. Best practice is exactly one.",
                fix="Reduce to a single H1 and use H2-H6 for subheadings.",
                effort="low",
            )

        if not analysis.get("has_canonical"):
            self.add_finding(
                priority="P2",
                title="Missing canonical URL",
                description="No canonical link found. This can cause duplicate content issues.",
                fix="Add a <link rel='canonical'> pointing to the preferred URL.",
                effort="low",
            )

        if analysis.get("json_ld_count", 0) == 0:
            self.add_finding(
                priority="P2",
                title="No structured data found",
                description="No JSON-LD structured data detected.",
                fix="Add relevant JSON-LD schema (Organization, WebPage, etc.).",
                effort="medium",
            )

        if not analysis.get("og_tags"):
            self.add_finding(
                priority="P3",
                title="No Open Graph tags found",
                description="No og: meta tags detected. Social sharing will lack rich previews.",
                fix="Add og:title, og:description, og:image, and og:url meta tags.",
                effort="low",
            )

        # sub-scores sum to 56 (title_meta 18 + headings 8 + canonical 5 +
        # structured 10 + social 10 + robots 5); max was wrongly 61 → a perfect
        # page could never reach 100%.
        return {"total": min(total, 56), "max": 56, "details": details}
