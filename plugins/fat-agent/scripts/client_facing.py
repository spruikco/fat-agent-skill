"""Client-facing text transformation utilities for reports.

Replaces technical jargon with plain-English equivalents suitable
for non-technical clients receiving audit reports.
"""

import re

CLIENT_FACING_MAP = {
    "P0": "Urgent",
    "P1": "Important",
    "P2": "Recommended",
    "P3": "Nice to Have",
    "HSTS": "Browser security header",
    "CSP": "Content security policy",
    "meta description": "search result snippet text",
    "JSON-LD": "structured data for search engines",
    "alt text": "image description for accessibility",
    "CLS": "layout shift (things jumping around)",
    "LCP": "page load speed",
    "ARIA": "accessibility markup",
    "hreflang": "language/region targeting tags",
    "canonical": "preferred page URL for search engines",
    "robots.txt": "search engine crawling rules",
    "sitemap": "page index for search engines",
    "DNSSEC": "domain security verification",
    "CAA": "certificate authority restrictions",
    "SPF": "email sender verification",
    "DKIM": "email signature verification",
    "DMARC": "email authentication policy",
}

_BUSINESS_IMPACT = {
    "Urgent": "This issue is actively harming your business and needs immediate attention.",
    "Important": "This issue could be causing lost visitors or revenue and should be addressed soon.",
    "Recommended": "Fixing this will improve your site's performance or visibility in search results.",
    "Nice to Have": "A minor improvement that would polish your site's overall quality.",
}


def transform_text(text, mapping=None):
    """Replace all jargon terms in text with their plain-English equivalents."""
    if mapping is None:
        mapping = CLIENT_FACING_MAP
    for term, replacement in mapping.items():
        text = text.replace(term, replacement)
    return text


def strip_code_blocks(text):
    """Remove markdown fenced code blocks and inline code from text."""
    # remove fenced code blocks (``` ... ```)
    text = re.sub(r"```[^\n]*\n.*?```", "", text, flags=re.DOTALL)
    # remove inline code (`...`)
    text = re.sub(r"`[^`]+`", "", text)
    return text


def transform_finding(finding):
    """Transform a finding dict for client consumption.

    - Replaces jargon in priority and title
    - Strips code blocks from fix field
    - Adds a business_impact field based on priority
    """
    result = dict(finding)

    result["priority"] = transform_text(result.get("priority", ""))
    result["title"] = transform_text(result.get("title", ""))

    if "fix" in result:
        result["fix"] = strip_code_blocks(transform_text(result["fix"]))

    priority_label = result["priority"]
    result["business_impact"] = _BUSINESS_IMPACT.get(
        priority_label,
        "This issue may affect your site's quality or visitor experience.",
    )

    return result
