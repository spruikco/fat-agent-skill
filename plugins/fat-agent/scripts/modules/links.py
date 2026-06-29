"""Link checker audit module.

HTML-level link quality analysis: classifies internal vs external links,
validates anchor fragments, mailto/tel links, and checks rel attributes.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from modules import register_module
from modules.base import AuditModule

_MAILTO_RE = re.compile(r"^mailto:" + r"([^?]+)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HREF_RE = re.compile(r"<a\s[^>]*?href\s*=\s*[\"']([^\"']*)[\"'][^>]*>", re.IGNORECASE)
_REL_RE = re.compile(r"\brel\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
_ID_RE = re.compile(r'\bid\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _extract_ids(html: str) -> set[str]:
    return set(_ID_RE.findall(html))


def _is_external(href: str, base_domain: str) -> bool:
    parsed = urlparse(href)
    if not parsed.scheme and not parsed.netloc:
        return False
    if (
        parsed.netloc
        and base_domain
        and parsed.netloc.lower().rstrip("/") == base_domain.lower().rstrip("/")
    ):
        return False
    if parsed.netloc:
        return True
    return False


@register_module
class LinksModule(AuditModule):
    MODULE_ID = "links"
    DISPLAY_NAME = "Link Checker"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        base_domain = ""
        if url:
            parsed_url = urlparse(url)
            base_domain = parsed_url.netloc

        all_ids = _extract_ids(html)

        total_links = 0
        internal_count = 0
        external_count = 0
        empty_hrefs = 0
        broken_anchors: list[str] = []
        mailto_count = 0
        valid_mailto: list[str] = []
        invalid_mailto: list[str] = []
        tel_count = 0
        external_missing_noopener = 0

        for tag_match in re.finditer(r"<a\s[^>]*>", html, re.IGNORECASE):
            tag = tag_match.group(0)
            href_m = re.search(r'href\s*=\s*["\']([^"\']*)["\']', tag, re.IGNORECASE)
            if href_m is None:
                continue

            href = href_m.group(1).strip()
            total_links += 1

            if href == "" or href == "#":
                empty_hrefs += 1
                continue

            if href.lower().startswith("mailto:"):
                mailto_count += 1
                m = _MAILTO_RE.match(href)
                if m and _EMAIL_RE.match(m.group(1)):
                    valid_mailto.append(href)
                else:
                    invalid_mailto.append(href)
                continue

            if href.lower().startswith("tel:"):
                tel_count += 1
                continue

            if href.startswith("#"):
                fragment = href[1:]
                if fragment not in all_ids:
                    broken_anchors.append(href)
                internal_count += 1
                continue

            if _is_external(href, base_domain):
                external_count += 1
                rel_m = _REL_RE.search(tag)
                rel_val = rel_m.group(1).lower() if rel_m else ""
                if "noopener" not in rel_val or "noreferrer" not in rel_val:
                    external_missing_noopener += 1
            else:
                internal_count += 1

        return {
            "total_links": total_links,
            "internal_count": internal_count,
            "external_count": external_count,
            "empty_hrefs": empty_hrefs,
            "broken_anchors": broken_anchors,
            "external_missing_noopener": external_missing_noopener,
            "mailto_count": mailto_count,
            "valid_mailto": valid_mailto,
            "invalid_mailto": invalid_mailto,
            "tel_count": tel_count,
        }

    def score(self, analysis: dict) -> dict:
        total_links = analysis.get("total_links", 0)
        empty_hrefs = analysis.get("empty_hrefs", 0)
        broken_anchors = analysis.get("broken_anchors", [])
        external_missing = analysis.get("external_missing_noopener", 0)
        internal_count = analysis.get("internal_count", 0)
        external_count = analysis.get("external_count", 0)
        invalid_mailto = analysis.get("invalid_mailto", [])
        valid_mailto = analysis.get("valid_mailto", [])
        mailto_count = analysis.get("mailto_count", 0)

        no_empty_links = 20 if empty_hrefs == 0 else 0
        no_broken_anchors = 20 if len(broken_anchors) == 0 else 0
        external_links_have_noopener = 15 if external_missing == 0 else 0
        has_internal_links = 15 if internal_count > 0 else 0
        has_external_links = 10 if external_count > 0 else 0

        if mailto_count == 0:
            valid_mailto_format = 10
        elif len(invalid_mailto) == 0 and len(valid_mailto) > 0:
            valid_mailto_format = 10
        else:
            valid_mailto_format = 0

        reasonable = 0 < total_links <= 200
        reasonable_link_count = 10 if reasonable else 0

        total = (
            no_empty_links
            + no_broken_anchors
            + external_links_have_noopener
            + has_internal_links
            + valid_mailto_format
            + reasonable_link_count
            + has_external_links
        )

        if empty_hrefs > 0:
            self.add_finding(
                priority="P2",
                title="Empty or placeholder href attributes found",
                description=f'{empty_hrefs} link(s) have empty href="" or href="#" '
                "attributes. These create poor user experience and confuse "
                "screen readers.",
                fix="Replace empty hrefs with valid destinations or use a <button> "
                "element for JavaScript actions.",
                effort="low",
            )

        if broken_anchors:
            self.add_finding(
                priority="P1",
                title="Broken anchor fragment links detected",
                description=f"{len(broken_anchors)} anchor link(s) point to IDs that "
                f"do not exist in the page: {', '.join(broken_anchors)}.",
                fix="Add matching id attributes to the target elements or correct "
                "the fragment references.",
                effort="low",
            )

        if external_missing > 0:
            self.add_finding(
                priority="P2",
                title="External links missing rel noopener noreferrer",
                description=f"{external_missing} external link(s) lack "
                'rel="noopener noreferrer". This is a security risk as '
                "the target page can access window.opener.",
                fix='Add rel="noopener noreferrer" to all external links.',
                effort="low",
            )

        if internal_count == 0 and total_links > 0:
            self.add_finding(
                priority="P2",
                title="No internal links found",
                description="The page has no internal navigation links. Internal links "
                "help search engines crawl your site and improve user "
                "navigation.",
                fix="Add links to other pages on your site.",
                effort="low",
            )

        if invalid_mailto:
            self.add_finding(
                priority="P2",
                title="Invalid mailto link format",
                description=f"{len(invalid_mailto)} mailto link(s) have invalid email "
                f"addresses: {', '.join(invalid_mailto)}.",
                fix="Ensure mailto links contain valid email addresses.",
                effort="low",
            )

        if total_links == 0:
            self.add_finding(
                priority="P2",
                title="No links found on page",
                description="The page contains no links at all. Links are essential "
                "for navigation and SEO.",
                fix="Add relevant internal and external links to the page.",
                effort="medium",
            )
        elif total_links > 200:
            self.add_finding(
                priority="P3",
                title="Excessive number of links",
                description=f"The page contains {total_links} links, which exceeds "
                "the recommended maximum of 200. Too many links can "
                "dilute page authority and confuse users.",
                fix="Review and reduce the number of links to the most relevant ones.",
                effort="medium",
            )

        return {
            "total": total,
            "no_empty_links": no_empty_links,
            "no_broken_anchors": no_broken_anchors,
            "external_links_have_noopener": external_links_have_noopener,
            "has_internal_links": has_internal_links,
            "valid_mailto_format": valid_mailto_format,
            "reasonable_link_count": reasonable_link_count,
            "has_external_links": has_external_links,
        }
