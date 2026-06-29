"""Content quality audit module.

Checks word count, readability (flesch-kincaid), title/h1 keyword overlap,
placeholder text, empty paragraphs, heading-to-content ratio, and copyright
year freshness.
"""

from __future__ import annotations

import re
from datetime import datetime

from modules import register_module
from modules.base import AuditModule
from modules._content_quality_helpers import (
    BodyTextExtractor,
    TagTextExtractor,
    flesch_kincaid_grade,
    extract_keywords,
    _NBSP_RE,
    _LOREM_RE,
    _COPYRIGHT_RE,
)


@register_module
class ContentQualityModule(AuditModule):
    MODULE_ID = "content_quality"
    DISPLAY_NAME = "Content Quality"
    ALWAYS_ENABLED = True

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        body_extractor = BodyTextExtractor()
        body_extractor.feed(html)
        body_text = " ".join(body_extractor.text_parts)

        tag_extractor = TagTextExtractor()
        tag_extractor.feed(html)

        words = re.findall(r"\S+", body_text)
        word_count = len(words)

        fk_grade = flesch_kincaid_grade(body_text)

        title_keywords = extract_keywords(tag_extractor.title_text)
        h1_keywords: set[str] = set()
        for h1 in tag_extractor.h1_texts:
            h1_keywords |= extract_keywords(h1)
        title_h1_overlap = (
            bool(title_keywords & h1_keywords)
            if title_keywords and h1_keywords
            else False
        )

        has_placeholder = bool(_LOREM_RE.search(html))

        empty_paragraphs = 0
        for p in tag_extractor.paragraphs:
            cleaned = _NBSP_RE.sub("", p).strip()
            if not cleaned:
                empty_paragraphs += 1

        heading_count = len(tag_extractor.headings)
        heading_ratio_ok = True
        if heading_count > 0 and word_count > 0:
            words_per_heading = word_count / heading_count
            if words_per_heading < 40:
                heading_ratio_ok = False
        elif heading_count > 0 and word_count == 0:
            heading_ratio_ok = False

        copyright_match = _COPYRIGHT_RE.search(html)
        copyright_year: int | None = None
        copyright_current = False
        if copyright_match:
            copyright_year = int(copyright_match.group(1))
            current_year = datetime.now().year
            copyright_current = copyright_year >= current_year - 1

        meta_desc = tag_extractor.meta_description
        duplicate_title_desc = False
        if tag_extractor.title_text and meta_desc:
            if tag_extractor.title_text.strip().lower() == meta_desc.strip().lower():
                duplicate_title_desc = True

        return {
            "word_count": word_count,
            "fk_grade": fk_grade,
            "title_text": tag_extractor.title_text,
            "h1_texts": tag_extractor.h1_texts,
            "title_h1_overlap": title_h1_overlap,
            "has_placeholder": has_placeholder,
            "empty_paragraphs": empty_paragraphs,
            "heading_count": heading_count,
            "heading_ratio_ok": heading_ratio_ok,
            "copyright_year": copyright_year,
            "copyright_current": copyright_current,
            "duplicate_title_desc": duplicate_title_desc,
            "meta_description": meta_desc,
        }

    def score(self, analysis: dict) -> dict:
        result = {}
        total = 0

        adequate = analysis.get("word_count", 0) >= 300
        pts = 25 if adequate else 0
        result["adequate_word_count"] = pts
        total += pts

        pts = 0 if analysis.get("has_placeholder") else 20
        result["no_placeholder_text"] = pts
        total += pts

        pts = 15 if analysis.get("title_h1_overlap") else 0
        result["title_h1_overlap"] = pts
        total += pts

        fk = analysis.get("fk_grade")
        pts = 15 if fk is not None and 6.0 <= fk <= 14.0 else 0
        result["good_readability"] = pts
        total += pts

        pts = 10 if analysis.get("empty_paragraphs", 0) == 0 else 0
        result["no_empty_paragraphs"] = pts
        total += pts

        pts = 10 if analysis.get("copyright_current") else 0
        result["current_copyright"] = pts
        total += pts

        pts = 5 if analysis.get("heading_ratio_ok") else 0
        result["reasonable_heading_ratio"] = pts
        total += pts

        result["total"] = total

        self._add_findings(analysis, adequate)

        return result

    def _add_findings(self, analysis: dict, adequate: bool):
        if not adequate:
            self.add_finding(
                priority="P1",
                title="Thin content detected",
                description=f"Page has only {analysis.get('word_count', 0)} words of "
                f"body content (excluding navigation). Pages with fewer "
                f"than 300 words are considered thin content by search engines.",
                fix="Add meaningful, relevant content to reach at least 300 words. "
                "Focus on addressing user intent and providing value.",
                effort="medium",
            )

        if analysis.get("has_placeholder"):
            self.add_finding(
                priority="P0",
                title="Placeholder text detected",
                description="Lorem ipsum or other placeholder text was found on the page. "
                "This indicates unfinished content that should never be live.",
                fix="Replace all placeholder text with real content before publishing.",
                effort="low",
            )

        if not analysis.get("title_h1_overlap"):
            self.add_finding(
                priority="P2",
                title="Title and H1 do not share key terms",
                description="The page title and main H1 heading do not share significant "
                "keywords. Aligning these helps search engines understand "
                "the page topic.",
                fix="Ensure the page title and H1 share the primary target keyword "
                "or topic phrase.",
                effort="low",
            )

        fk = analysis.get("fk_grade")
        if fk is not None and fk > 14.0:
            self.add_finding(
                priority="P2",
                title="Content readability is very high grade level",
                description=f"Flesch-Kincaid grade level is {fk}, meaning the text "
                f"requires an advanced reading level. Most web content "
                f"should target grades 6-12 for broad accessibility.",
                fix="Simplify sentence structure and use shorter, more common words "
                "to improve readability.",
                effort="medium",
            )
        elif fk is not None and fk < 6.0:
            self.add_finding(
                priority="P3",
                title="Content readability is very low grade level",
                description=f"Flesch-Kincaid grade level is {fk}. While simple text "
                f"is accessible, overly simplistic content may lack depth.",
                fix="Consider whether the content provides sufficient detail and "
                "expertise for the target audience.",
                effort="low",
            )

        if analysis.get("empty_paragraphs", 0) > 0:
            count = analysis["empty_paragraphs"]
            self.add_finding(
                priority="P2",
                title=f"{count} empty paragraph(s) found",
                description=f"Found {count} paragraph element(s) containing only "
                f"whitespace or &nbsp;. These create unnecessary gaps and "
                f"are a sign of sloppy markup.",
                fix="Remove empty <p> tags or replace them with proper CSS spacing.",
                effort="low",
            )

        if not analysis.get("heading_ratio_ok"):
            self.add_finding(
                priority="P2",
                title="High heading-to-content ratio",
                description="The page has many headings relative to the amount of body "
                "text. This may indicate stub content or over-structured "
                "pages with little substance.",
                fix="Add more content under each heading, or consolidate headings "
                "where the content is thin.",
                effort="medium",
            )

        if analysis.get("copyright_year") is not None and not analysis.get(
            "copyright_current"
        ):
            self.add_finding(
                priority="P2",
                title=f"Outdated copyright year ({analysis['copyright_year']})",
                description=f"The copyright notice shows {analysis['copyright_year']}. "
                f"An outdated year signals a neglected or unmaintained site.",
                fix="Update the copyright year to the current year, or use a "
                "dynamic solution that updates automatically.",
                effort="low",
            )

        if analysis.get("duplicate_title_desc"):
            self.add_finding(
                priority="P2",
                title="Title and meta description are identical",
                description="The page title and meta description contain the same text. "
                "Each should serve a distinct purpose in search results.",
                fix="Write a unique meta description that complements (not duplicates) "
                "the title tag.",
                effort="low",
            )
