"""Accessibility core audit module.

Analyses HTML for key accessibility signals: alt text, form labels, lang
attribute, landmarks, skip links, heading hierarchy, empty headings, and
ARIA roles. Scoring mirrors calculate-score.py's calculate_accessibility_score.
"""

from __future__ import annotations

import re

from modules import register_module
from modules.base import AuditModule

_LANDMARK_TAGS = {"main", "nav", "header", "footer", "aside"}
_LANDMARK_ROLES = {"main", "navigation", "banner", "contentinfo", "complementary"}

# form/div blocks that are hidden from assistive tech — their inputs are NOT a
# real labelling failure. Covers the bare `hidden` attribute (common on
# framework detection forms, e.g. Netlify), aria-hidden, and display:none.
_HIDDEN_BLOCK_RE = re.compile(
    r"<(form|div)\b[^>]*?"
    r'(?:\shidden(?:\s|=|>)|aria-hidden=["\']true["\']|display\s*:\s*none)'
    r"[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)


def _strip_hidden(html: str) -> str:
    """Remove hidden form/div blocks so their inputs don't count as unlabelled."""
    prev = None
    # loop to catch simple nesting (each pass removes the outermost matches)
    while prev != html:
        prev = html
        html = _HIDDEN_BLOCK_RE.sub("", html)
    return html


@register_module
class AccessibilityModule(AuditModule):
    MODULE_ID = "accessibility"
    DISPLAY_NAME = "Accessibility"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        imgs = re.findall(r"<img\s[^>]*>", html, re.IGNORECASE)
        img_total = len(imgs)
        img_missing_alt = 0
        for img in imgs:
            if not re.search(r'alt=["\']', img, re.IGNORECASE):
                img_missing_alt += 1

        # inputs inside hidden containers aren't exposed to assistive tech, so
        # they can't be a real labelling failure — scan the visible HTML only.
        visible_html = _strip_hidden(html)
        inputs = re.findall(
            r"<(?:input|select|textarea)\s[^>]*>",
            visible_html,
            re.IGNORECASE,
        )
        form_inputs_total = 0
        form_inputs_without_label = 0
        # an input is labelled by aria-label/labelledby/title, OR by a real
        # <label for="<id>"> that references its id — NOT by merely having an id.
        label_fors = set(
            re.findall(r'<label[^>]+for=["\']([^"\']+)', visible_html, re.IGNORECASE)
        )
        for inp in inputs:
            if re.search(r'type=["\']hidden["\']', inp, re.IGNORECASE):
                continue
            form_inputs_total += 1
            id_m = re.search(r'\bid=["\']([^"\']+)', inp, re.IGNORECASE)
            has_label = bool(
                re.search(r"aria-label\b|aria-labelledby|\btitle=", inp, re.IGNORECASE)
                or (id_m and id_m.group(1) in label_fors)
            )
            if not has_label:
                form_inputs_without_label += 1

        has_lang = bool(re.search(r"<html\s[^>]*lang=", html, re.IGNORECASE))

        landmarks_found = set()
        for tag in _LANDMARK_TAGS:
            if re.search(rf"<{tag}[\s>]", html, re.IGNORECASE):
                landmarks_found.add(tag)
        for role in _LANDMARK_ROLES:
            if re.search(r'role=["\']' + role + r'["\']', html, re.IGNORECASE):
                role_map = {
                    "navigation": "nav",
                    "banner": "header",
                    "contentinfo": "footer",
                    "complementary": "aside",
                }
                landmarks_found.add(role_map.get(role, role))

        has_skip_link = bool(
            re.search(
                r'<a\s[^>]*href=["\']#(main|content|main-content)["\']',
                html,
                re.IGNORECASE,
            )
        )

        heading_tags = re.findall(r"<(h[1-6])[\s>]", html, re.IGNORECASE)
        heading_hierarchy = [int(h[1]) for h in heading_tags]

        empty_headings = 0
        for m in re.finditer(
            r"<(h[1-6])[^>]*>(.*?)</\1>", html, re.IGNORECASE | re.DOTALL
        ):
            content = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if not content:
                empty_headings += 1

        aria_roles = re.findall(r'role=["\']([^"\']+)["\']', html, re.IGNORECASE)

        return {
            "img_total": img_total,
            "img_missing_alt": img_missing_alt,
            "form_inputs_total": form_inputs_total,
            "form_inputs_without_label": form_inputs_without_label,
            "has_lang_attribute": has_lang,
            "landmarks_found": sorted(landmarks_found),
            "has_skip_link": has_skip_link,
            "heading_hierarchy": heading_hierarchy,
            "empty_headings": empty_headings,
            "aria_roles": aria_roles,
        }

    def score(self, analysis: dict) -> dict:
        total = 0
        details = {}

        # images with alt text (18 points)
        img_total = analysis.get("img_total", 0)
        img_missing = analysis.get("img_missing_alt", 0)
        if img_total == 0:
            img_score = 18
        elif img_missing == 0:
            img_score = 18
        else:
            ratio = (img_total - img_missing) / img_total
            img_score = round(ratio * 18)
        details["images_alt"] = {"score": img_score, "max": 18}
        total += img_score

        # language attribute (5 points)
        lang = 5 if analysis.get("has_lang_attribute") else 0
        details["lang_attribute"] = {"score": lang, "max": 5}
        total += lang

        # form accessibility (13 points)
        form_total = analysis.get("form_inputs_total", 0)
        form_missing = analysis.get("form_inputs_without_label", 0)
        if form_total == 0:
            form_score = 13
        elif form_missing == 0:
            form_score = 13
        else:
            ratio = (form_total - form_missing) / form_total
            form_score = round(ratio * 13)
        details["form_accessibility"] = {"score": form_score, "max": 13}
        total += form_score

        # heading structure (10 points)
        heading_score = 10
        empty = analysis.get("empty_headings", 0)
        if empty > 0:
            heading_score = max(heading_score - (empty * 3), 0)
        details["heading_structure"] = {"score": heading_score, "max": 10}
        total += heading_score

        # skip navigation (5 points)
        skip = 5 if analysis.get("has_skip_link") else 0
        details["skip_navigation"] = {"score": skip, "max": 5}
        total += skip

        # landmark regions (10 points)
        landmarks = analysis.get("landmarks_found", [])
        expected = {"main", "nav", "header", "footer"}
        found = set(landmarks) & expected
        landmark_score = min(len(found) * 3, 10)
        details["landmarks"] = {"score": landmark_score, "max": 10}
        total += landmark_score

        if img_missing > 0:
            self.add_finding(
                priority="P1",
                title="Images missing alt text",
                description=f"{img_missing} of {img_total} images lack alt attributes.",
                fix="Add descriptive alt text to all images, or alt='' for decorative ones.",
                effort="low",
            )

        if not analysis.get("has_lang_attribute"):
            self.add_finding(
                priority="P1",
                title="Missing lang attribute on <html>",
                description="Screen readers need the lang attribute to select the correct voice.",
                fix='Add lang="en" (or appropriate language) to the <html> element.',
                effort="low",
            )

        if form_missing > 0:
            self.add_finding(
                priority="P1",
                title="Form inputs without labels",
                description=f"{form_missing} of {form_total} form inputs lack associated labels.",
                fix="Add <label> elements with for attributes or use aria-label.",
                effort="medium",
            )

        if not analysis.get("has_skip_link"):
            self.add_finding(
                priority="P2",
                title="Missing skip navigation link",
                description="No skip-to-content link found for keyboard users.",
                fix="Add an <a href='#main-content'> link as the first focusable element.",
                effort="low",
            )

        if analysis.get("empty_headings", 0) > 0:
            self.add_finding(
                priority="P2",
                title="Empty headings found",
                description=f"{analysis['empty_headings']} heading elements have no text content.",
                fix="Add text content to all headings or remove empty heading tags.",
                effort="low",
            )

        if not set(analysis.get("landmarks_found", [])) & {"main"}:
            self.add_finding(
                priority="P2",
                title="Missing <main> landmark",
                description="No <main> element or role='main' found.",
                fix="Wrap the primary page content in a <main> element.",
                effort="low",
            )

        return {"total": min(total, 61), "max": 61, "details": details}
