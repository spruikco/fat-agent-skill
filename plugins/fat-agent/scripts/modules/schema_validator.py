"""Structured data (JSON-LD) validation audit module.

Extracts all JSON-LD blocks, validates JSON syntax, checks that @context is
schema.org, that @type is a known Schema.org type, and that required properties
are present for common types.
"""

from __future__ import annotations

import json
import re

from modules import register_module
from modules.base import AuditModule

_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

_SCHEMA_ORG_RE = re.compile(r"https?://schema\.org/?", re.IGNORECASE)

# known schema.org types and their required properties
_KNOWN_TYPES: dict[str, list[str]] = {
    "Organization": ["name", "url"],
    "LocalBusiness": ["name", "url"],
    "Article": ["headline", "author"],
    "NewsArticle": ["headline", "author"],
    "BlogPosting": ["headline", "author"],
    "FAQPage": ["mainEntity"],
    "Product": ["name"],
    "WebSite": ["name"],
    "WebPage": ["name"],
    "BreadcrumbList": ["itemListElement"],
    "Person": ["name"],
    "Event": ["name", "startDate"],
    "Recipe": ["name"],
    "Review": ["itemReviewed"],
    "HowTo": ["name", "step"],
    "VideoObject": ["name", "uploadDate"],
    "ImageObject": ["contentUrl"],
    "SoftwareApplication": ["name"],
    "Restaurant": ["name"],
    "Store": ["name"],
    "MedicalBusiness": ["name"],
    "Course": ["name", "provider"],
    "JobPosting": ["title", "datePosted"],
}

# lower-cased lookup for case-insensitive matching
_KNOWN_TYPES_LOWER: dict[str, list[str]] = {
    k.lower(): v for k, v in _KNOWN_TYPES.items()
}


@register_module
class SchemaValidatorModule(AuditModule):
    MODULE_ID = "schema_validator"
    DISPLAY_NAME = "Structured Data"

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------

    @classmethod
    def detect(cls, html: str) -> bool:
        """True if any <script type='application/ld+json'> block exists."""
        return bool(_JSON_LD_RE.search(html))

    # ------------------------------------------------------------------
    # analysis
    # ------------------------------------------------------------------

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        raw_blocks = _JSON_LD_RE.findall(html)
        has_structured_data = len(raw_blocks) > 0

        parsed: list[dict] = []
        valid_json = True
        for block in raw_blocks:
            try:
                data = json.loads(block)
            except (json.JSONDecodeError, ValueError):
                valid_json = False
                continue
            if isinstance(data, list):
                parsed.extend(d for d in data if isinstance(d, dict))
            elif isinstance(data, dict):
                parsed.append(data)

        # flatten @graph if present
        expanded: list[dict] = []
        for item in parsed:
            if "@graph" in item and isinstance(item["@graph"], list):
                expanded.extend(d for d in item["@graph"] if isinstance(d, dict))
            else:
                expanded.append(item)

        blocks_with_context = [d for d in parsed if d.get("@context") is not None]
        has_context = len(blocks_with_context) > 0 and all(
            _SCHEMA_ORG_RE.match(str(d.get("@context", "")))
            for d in blocks_with_context
        )

        types_found: list[str] = []
        known_types = True
        for d in expanded:
            schema_type = d.get("@type", "")
            if isinstance(schema_type, list):
                types_found.extend(schema_type)
                for t in schema_type:
                    if t.lower() not in _KNOWN_TYPES_LOWER:
                        known_types = False
            elif schema_type:
                types_found.append(schema_type)
                if schema_type.lower() not in _KNOWN_TYPES_LOWER:
                    known_types = False

        if not types_found:
            known_types = False

        # check required properties
        has_required_props = True
        for d in expanded:
            schema_type = d.get("@type", "")
            if isinstance(schema_type, list):
                check_types = schema_type
            else:
                check_types = [schema_type] if schema_type else []
            for t in check_types:
                required = _KNOWN_TYPES_LOWER.get(t.lower(), [])
                for prop in required:
                    if not d.get(prop):
                        has_required_props = False
                        break

        # duplicate types check
        type_counts: dict[str, int] = {}
        for t in types_found:
            key = t.lower()
            type_counts[key] = type_counts.get(key, 0) + 1
        no_duplicate_types = all(c == 1 for c in type_counts.values())

        return {
            "has_structured_data": has_structured_data,
            "valid_json": valid_json,
            "has_context": has_context,
            "known_types": known_types,
            "types_found": types_found,
            "has_required_props": has_required_props,
            "no_duplicate_types": no_duplicate_types,
            "blocks_count": len(raw_blocks),
            "parsed_count": len(expanded),
        }

    # ------------------------------------------------------------------
    # scoring
    # ------------------------------------------------------------------

    def score(self, analysis: dict) -> dict:
        weights = {
            "has_structured_data": 20,
            "valid_json": 20,
            "has_context": 15,
            "known_types": 15,
            "has_required_props": 20,
            "no_duplicate_types": 10,
        }

        result = {}
        total = 0
        for key, weight in weights.items():
            pts = weight if analysis.get(key) else 0
            result[key] = pts
            total += pts
        result["total"] = total

        if not analysis.get("has_structured_data"):
            self.add_finding(
                priority="P1",
                title="No structured data found",
                description="No JSON-LD structured data was found on the page. "
                "Structured data helps search engines understand content "
                "and can enable rich results.",
                fix="Add at least one <script type='application/ld+json'> block "
                "with valid Schema.org markup.",
                effort="medium",
            )

        if not analysis.get("valid_json"):
            self.add_finding(
                priority="P0",
                title="Invalid JSON in structured data",
                description="One or more JSON-LD blocks contain invalid JSON. "
                "Search engines will ignore malformed structured data.",
                fix="Validate your JSON-LD blocks with a JSON linter and fix "
                "syntax errors.",
                effort="low",
            )

        if analysis.get("has_structured_data") and not analysis.get("has_context"):
            self.add_finding(
                priority="P1",
                title="Missing or invalid @context in structured data",
                description="JSON-LD blocks were found but @context is not set to "
                "https://schema.org. Without the correct context, search "
                "engines cannot interpret the data.",
                fix='Set "@context": "https://schema.org" in every JSON-LD block.',
                effort="low",
            )

        if not analysis.get("known_types"):
            self.add_finding(
                priority="P2",
                title="Unknown @type in structured data",
                description="One or more @type values are not recognised Schema.org types. "
                "Using standard types ensures compatibility with search engines.",
                fix="Use well-known Schema.org types such as Organization, Article, "
                "Product, FAQPage, etc.",
                effort="low",
            )

        if not analysis.get("has_required_props"):
            self.add_finding(
                priority="P1",
                title="Missing required properties in structured data",
                description="One or more Schema.org types are missing required properties. "
                "Incomplete structured data may not qualify for rich results.",
                fix="Add the required properties for each @type (e.g. Organization "
                "needs name+url, Article needs headline+author).",
                effort="medium",
            )

        if not analysis.get("no_duplicate_types"):
            self.add_finding(
                priority="P3",
                title="Duplicate @type in structured data",
                description="The same Schema.org @type appears more than once. Duplicate "
                "types can confuse search engines about which is canonical.",
                fix="Consolidate duplicate @type blocks into a single JSON-LD object "
                "or ensure each serves a distinct purpose.",
                effort="low",
            )

        return result
