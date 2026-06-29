"""Internationalisation audit module.

Checks for hreflang tags, x-default presence, self-referencing hreflang,
valid language codes, locale routing patterns, RTL support, lang attribute
on html element, and Content-Language header.
"""

from __future__ import annotations

import re

from modules import register_module
from modules.base import AuditModule

# ISO 639-1 two-letter codes (subset covering common web languages)
_VALID_LANG_CODES = {
    "aa",
    "ab",
    "af",
    "ak",
    "am",
    "an",
    "ar",
    "as",
    "av",
    "ay",
    "az",
    "ba",
    "be",
    "bg",
    "bh",
    "bi",
    "bm",
    "bn",
    "bo",
    "br",
    "bs",
    "ca",
    "ce",
    "ch",
    "co",
    "cr",
    "cs",
    "cu",
    "cv",
    "cy",
    "da",
    "de",
    "dv",
    "dz",
    "ee",
    "el",
    "en",
    "eo",
    "es",
    "et",
    "eu",
    "fa",
    "ff",
    "fi",
    "fj",
    "fo",
    "fr",
    "fy",
    "ga",
    "gd",
    "gl",
    "gn",
    "gu",
    "gv",
    "ha",
    "he",
    "hi",
    "ho",
    "hr",
    "ht",
    "hu",
    "hy",
    "hz",
    "ia",
    "id",
    "ie",
    "ig",
    "ii",
    "ik",
    "in",
    "io",
    "is",
    "it",
    "iu",
    "ja",
    "jv",
    "ka",
    "kg",
    "ki",
    "kj",
    "kk",
    "kl",
    "km",
    "kn",
    "ko",
    "kr",
    "ks",
    "ku",
    "kv",
    "kw",
    "ky",
    "la",
    "lb",
    "lg",
    "li",
    "ln",
    "lo",
    "lt",
    "lu",
    "lv",
    "mg",
    "mh",
    "mi",
    "mk",
    "ml",
    "mn",
    "mr",
    "ms",
    "mt",
    "my",
    "na",
    "nb",
    "nd",
    "ne",
    "ng",
    "nl",
    "nn",
    "no",
    "nr",
    "nv",
    "ny",
    "oc",
    "oj",
    "om",
    "or",
    "os",
    "pa",
    "pi",
    "pl",
    "ps",
    "pt",
    "qu",
    "rm",
    "rn",
    "ro",
    "ru",
    "rw",
    "sa",
    "sc",
    "sd",
    "se",
    "sg",
    "si",
    "sk",
    "sl",
    "sm",
    "sn",
    "so",
    "sq",
    "sr",
    "ss",
    "st",
    "su",
    "sv",
    "sw",
    "ta",
    "te",
    "tg",
    "th",
    "ti",
    "tk",
    "tl",
    "tn",
    "to",
    "tr",
    "ts",
    "tt",
    "tw",
    "ty",
    "ug",
    "uk",
    "ur",
    "uz",
    "ve",
    "vi",
    "vo",
    "wa",
    "wo",
    "xh",
    "yi",
    "yo",
    "za",
    "zh",
    "zu",
}

# RTL language codes
_RTL_LANGUAGES = {"ar", "he", "fa", "ur", "yi", "ps", "sd", "ug", "ku", "dv"}

_HREFLANG_RE = re.compile(
    r'<link[^>]+hreflang=["\']([^"\']+)["\'][^>]+href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_HREFLANG_RE_ALT = re.compile(
    r'<link[^>]+href=["\']([^"\']+)["\'][^>]+hreflang=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

_LOCALE_PATH_RE = re.compile(r'href=["\'][^"\']*?/([a-z]{2})/', re.IGNORECASE)

_LANG_ATTR_RE = re.compile(r"<html[^>]+lang=[\"']([^\"']+)[\"']", re.IGNORECASE)

_DIR_RTL_RE = re.compile(r'dir=["\']rtl["\']', re.IGNORECASE)


@register_module
class I18nModule(AuditModule):
    MODULE_ID = "i18n"
    DISPLAY_NAME = "Internationalisation"

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------

    @classmethod
    def detect(cls, html: str) -> bool:
        """Return True when hreflang tags or language-switcher patterns are found."""
        if re.search(r"hreflang=", html, re.IGNORECASE):
            return True
        if re.search(r"lang-selector|language-switcher", html, re.IGNORECASE):
            return True
        return False

    # ------------------------------------------------------------------
    # analysis
    # ------------------------------------------------------------------

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        headers = headers or {}

        hreflang_tags = []
        for match in _HREFLANG_RE.finditer(html):
            hreflang_tags.append({"lang": match.group(1), "href": match.group(2)})
        # alternate attribute order (href before hreflang)
        for match in _HREFLANG_RE_ALT.finditer(html):
            entry = {"lang": match.group(2), "href": match.group(1)}
            if not any(
                t["lang"] == entry["lang"] and t["href"] == entry["href"]
                for t in hreflang_tags
            ):
                hreflang_tags.append(entry)

        has_x_default = any(t["lang"] == "x-default" for t in hreflang_tags)

        # self-referencing hreflang
        self_referencing = False
        if url:
            norm_url = url.rstrip("/")
            for tag in hreflang_tags:
                if tag["lang"] == "x-default":
                    continue
                if tag["href"].rstrip("/") == norm_url:
                    self_referencing = True
                    break

        # lang attribute on <html> element
        lang_match = _LANG_ATTR_RE.search(html)
        has_lang_attribute = lang_match is not None
        lang_attribute = lang_match.group(1) if lang_match else None

        content_language_raw = headers.get("Content-Language") or headers.get(
            "content-language"
        )
        has_content_language_header = content_language_raw is not None
        content_language = content_language_raw if content_language_raw else None

        invalid_codes = []
        non_default_tags = [t for t in hreflang_tags if t["lang"] != "x-default"]
        for tag in non_default_tags:
            lang_code = tag["lang"].split("-")[0].lower()
            if lang_code not in _VALID_LANG_CODES:
                invalid_codes.append(tag["lang"])
        valid_language_codes = len(invalid_codes) == 0 and len(non_default_tags) > 0

        locale_patterns = set()
        for match in _LOCALE_PATH_RE.finditer(html):
            code = match.group(1).lower()
            if code in _VALID_LANG_CODES:
                locale_patterns.add(code)

        primary_lang = (
            (lang_attribute or "").split("-")[0].lower() if lang_attribute else ""
        )
        rtl_language_detected = primary_lang in _RTL_LANGUAGES
        # check hreflang tags for rtl languages too
        if not rtl_language_detected:
            for tag in non_default_tags:
                tag_lang = tag["lang"].split("-")[0].lower()
                if tag_lang in _RTL_LANGUAGES:
                    rtl_language_detected = True
                    break

        has_rtl_support = bool(_DIR_RTL_RE.search(html))

        return {
            "hreflang_tags": hreflang_tags,
            "has_x_default": has_x_default,
            "self_referencing_hreflang": self_referencing,
            "has_lang_attribute": has_lang_attribute,
            "lang_attribute": lang_attribute,
            "has_content_language_header": has_content_language_header,
            "content_language": content_language,
            "valid_language_codes": valid_language_codes,
            "invalid_codes": invalid_codes,
            "locale_patterns": sorted(locale_patterns),
            "has_rtl_support": has_rtl_support,
            "rtl_language_detected": rtl_language_detected,
        }

    # ------------------------------------------------------------------
    # scoring
    # ------------------------------------------------------------------

    def score(self, analysis: dict) -> dict:
        breakdown = {}

        # has_lang_attribute: 20
        lang_attr_score = 20 if analysis.get("has_lang_attribute") else 0
        breakdown["has_lang_attribute"] = lang_attr_score

        # hreflang_tags_present: 20
        hreflang_score = 20 if analysis.get("hreflang_tags") else 0
        breakdown["hreflang_tags_present"] = hreflang_score

        # has_x_default: 15
        x_default_score = 15 if analysis.get("has_x_default") else 0
        breakdown["has_x_default"] = x_default_score

        # self_referencing_hreflang: 15
        self_ref_score = 15 if analysis.get("self_referencing_hreflang") else 0
        breakdown["self_referencing_hreflang"] = self_ref_score

        # valid_language_codes: 10
        valid_codes_score = 10 if analysis.get("valid_language_codes") else 0
        breakdown["valid_language_codes"] = valid_codes_score

        # has_content_language_header: 10
        content_lang_score = 10 if analysis.get("has_content_language_header") else 0
        breakdown["has_content_language_header"] = content_lang_score

        # rtl_support: 10 (only scored when RTL language detected)
        rtl_score = 0
        if analysis.get("rtl_language_detected"):
            rtl_score = 10 if analysis.get("has_rtl_support") else 0
            breakdown["rtl_support"] = rtl_score

        total = (
            lang_attr_score
            + hreflang_score
            + x_default_score
            + self_ref_score
            + valid_codes_score
            + content_lang_score
            + rtl_score
        )

        if not analysis.get("has_lang_attribute"):
            self.add_finding(
                priority="P1",
                title="Missing lang attribute on <html> element",
                description="The <html> element does not have a lang attribute. "
                "This is essential for screen readers and search engines "
                "to identify the page language.",
                fix='Add lang="xx" to the <html> element, e.g. <html lang="en">.',
                effort="low",
            )

        if not analysis.get("hreflang_tags"):
            self.add_finding(
                priority="P2",
                title="No hreflang tags found",
                description="No hreflang link tags were detected. For multilingual "
                "sites, hreflang tags help search engines serve the correct "
                "language version to users.",
                fix="Add <link rel='alternate' hreflang='xx' href='...'> for each "
                "language version of the page.",
                effort="medium",
            )

        if analysis.get("hreflang_tags") and not analysis.get("has_x_default"):
            self.add_finding(
                priority="P2",
                title="Missing x-default hreflang tag",
                description="Hreflang tags are present but no x-default was found. "
                "The x-default tag tells search engines which URL to use "
                "when no language matches.",
                fix='Add <link rel="alternate" hreflang="x-default" href="..."> '
                "pointing to your default/fallback page.",
                effort="low",
            )

        if analysis.get("hreflang_tags") and not analysis.get(
            "self_referencing_hreflang"
        ):
            self.add_finding(
                priority="P2",
                title="No self-referencing hreflang tag",
                description="The current page URL does not appear in the hreflang set. "
                "Each page should include a hreflang tag pointing to itself.",
                fix="Ensure every page lists itself in the hreflang tags.",
                effort="low",
            )

        if analysis.get("invalid_codes"):
            codes = ", ".join(analysis["invalid_codes"])
            self.add_finding(
                priority="P2",
                title="Invalid language codes in hreflang tags",
                description=f"The following hreflang codes are not valid ISO 639-1: {codes}.",
                fix="Use valid ISO 639-1 two-letter language codes (optionally with "
                "regional subtag, e.g. en-GB).",
                effort="low",
            )

        if not analysis.get("has_content_language_header"):
            self.add_finding(
                priority="P3",
                title="Missing Content-Language HTTP header",
                description="The Content-Language header was not found in the response. "
                "While not critical, it provides an additional signal for "
                "language detection.",
                fix="Set the Content-Language header on your server to match the "
                "page language.",
                effort="low",
            )

        if analysis.get("rtl_language_detected") and not analysis.get(
            "has_rtl_support"
        ):
            self.add_finding(
                priority="P1",
                title="RTL language detected without dir='rtl' support",
                description="An RTL language was detected but the page does not use "
                "dir='rtl'. This causes layout issues for RTL readers.",
                fix='Add dir="rtl" to the <html> element or relevant containers '
                "when serving RTL content.",
                effort="medium",
            )

        return {
            "total": total,
            "breakdown": breakdown,
        }
