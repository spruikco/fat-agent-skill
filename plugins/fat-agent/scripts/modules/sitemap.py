"""Sitemap Analysis audit module.

Fetches and parses XML sitemaps, checking structure, validity,
URL coverage, lastmod dates, duplicates, and robots.txt references.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError

from modules import register_module
from modules.base import AuditModule

_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


@register_module
class SitemapModule(AuditModule):
    MODULE_ID = "sitemap"
    DISPLAY_NAME = "Sitemap Analysis"
    ALWAYS_ENABLED = True

    # ------------------------------------------------------------------
    # detection — always enabled
    # ------------------------------------------------------------------

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    # ------------------------------------------------------------------
    # analysis
    # ------------------------------------------------------------------

    def analyse(
        self,
        html: str,
        url: str = "",
        headers: dict = None,
        *,
        sitemap_xml: str | None = None,
        robots_txt: str | None = None,
        **kwargs,
    ) -> dict:
        domain = self._extract_domain(url)
        base_url = self._extract_base_url(url)

        raw_sitemap: str | None = sitemap_xml
        sitemap_source: str | None = None
        robots_content: str | None = robots_txt

        if raw_sitemap is None and base_url:
            for path in ("/sitemap.xml", "/sitemap_index.xml"):
                candidate = base_url + path
                content = self._fetch(candidate)
                if content:
                    raw_sitemap = content
                    sitemap_source = candidate
                    break

            # fall back to sitemaps listed in robots.txt
            if raw_sitemap is None:
                if robots_content is None:
                    robots_content = self._fetch(base_url + "/robots.txt")
                if robots_content:
                    for sm_url in self._sitemaps_from_robots(robots_content):
                        content = self._fetch(sm_url)
                        if content:
                            raw_sitemap = content
                            sitemap_source = sm_url
                            break

        if robots_content is None and base_url:
            robots_content = self._fetch(base_url + "/robots.txt")
        sitemap_exists = raw_sitemap is not None
        valid_xml = False
        urls: list[str] = []
        lastmod_count = 0
        is_index = False

        if raw_sitemap:
            try:
                root = ET.fromstring(raw_sitemap)
                valid_xml = True

                if root.tag == f"{_SITEMAP_NS}sitemapindex":
                    is_index = True
                    for sitemap_el in root.findall(f"{_SITEMAP_NS}sitemap"):
                        loc = sitemap_el.find(f"{_SITEMAP_NS}loc")
                        if loc is not None and loc.text:
                            urls.append(loc.text.strip())
                        lm = sitemap_el.find(f"{_SITEMAP_NS}lastmod")
                        if lm is not None and lm.text:
                            lastmod_count += 1
                else:
                    for url_el in root.findall(f"{_SITEMAP_NS}url"):
                        loc = url_el.find(f"{_SITEMAP_NS}loc")
                        if loc is not None and loc.text:
                            urls.append(loc.text.strip())
                        lm = url_el.find(f"{_SITEMAP_NS}lastmod")
                        if lm is not None and lm.text:
                            lastmod_count += 1
            except ET.ParseError:
                valid_xml = False

        has_urls = len(urls) > 0
        unique_urls = set(urls)
        has_duplicates = len(unique_urls) < len(urls)
        duplicate_count = len(urls) - len(unique_urls)

        def _reg(h):  # strip leading www. so apex↔www isn't "another domain"
            h = (h or "").lower()
            return h[4:] if h.startswith("www.") else h

        urls_match_domain = True
        mismatched_urls: list[str] = []
        if domain and urls:
            dreg = _reg(domain)
            for u in urls:
                parsed = urlparse(u)
                if parsed.hostname and _reg(parsed.hostname) != dreg:
                    urls_match_domain = False
                    mismatched_urls.append(u)

        has_lastmod = lastmod_count > 0
        reasonable_size = len(urls) < 50_000

        referenced_in_robots = False
        if robots_content:
            robots_sitemaps = self._sitemaps_from_robots(robots_content)
            referenced_in_robots = len(robots_sitemaps) > 0

        return {
            "domain": domain,
            "sitemap_exists": sitemap_exists,
            "sitemap_source": sitemap_source,
            "valid_xml": valid_xml,
            "is_index": is_index,
            "has_urls": has_urls,
            "url_count": len(urls),
            "unique_url_count": len(unique_urls),
            "urls_match_domain": urls_match_domain,
            "mismatched_urls": mismatched_urls[:10],
            "has_lastmod": has_lastmod,
            "lastmod_count": lastmod_count,
            "has_duplicates": has_duplicates,
            "duplicate_count": duplicate_count,
            "reasonable_size": reasonable_size,
            "referenced_in_robots": referenced_in_robots,
        }

    # ------------------------------------------------------------------
    # scoring
    # ------------------------------------------------------------------

    def score(self, analysis: dict) -> dict:
        sitemap_exists_pts = 25 if analysis.get("sitemap_exists") else 0
        valid_xml_pts = 15 if analysis.get("valid_xml") else 0
        has_urls_pts = 15 if analysis.get("has_urls") else 0
        urls_match_domain_pts = 10 if analysis.get("urls_match_domain") else 0
        has_lastmod_pts = 10 if analysis.get("has_lastmod") else 0
        referenced_in_robots_pts = 10 if analysis.get("referenced_in_robots") else 0
        no_duplicates_pts = 10 if not analysis.get("has_duplicates") else 0
        reasonable_size_pts = 5 if analysis.get("reasonable_size") else 0

        total = (
            sitemap_exists_pts
            + valid_xml_pts
            + has_urls_pts
            + urls_match_domain_pts
            + has_lastmod_pts
            + referenced_in_robots_pts
            + no_duplicates_pts
            + reasonable_size_pts
        )

        if not analysis.get("sitemap_exists"):
            self.add_finding(
                priority="P1",
                title="No sitemap found",
                description="No XML sitemap was found at /sitemap.xml, "
                "/sitemap_index.xml, or any location referenced in robots.txt. "
                "Search engines rely on sitemaps to discover and index pages.",
                fix="Create an XML sitemap and submit it to Google Search Console "
                "and Bing Webmaster Tools.",
                effort="medium",
            )
        else:
            if not analysis.get("valid_xml"):
                self.add_finding(
                    priority="P1",
                    title="Sitemap contains invalid XML",
                    description="The sitemap was found but could not be parsed as "
                    "valid XML. Search engines will ignore a malformed sitemap.",
                    fix="Validate the sitemap XML using an XML validator and fix "
                    "any syntax errors.",
                    effort="low",
                )

            if not analysis.get("has_urls"):
                self.add_finding(
                    priority="P1",
                    title="Sitemap contains no URLs",
                    description="The sitemap was found and is valid XML, but "
                    "contains no <url> entries. An empty sitemap provides "
                    "no value to search engines.",
                    fix="Populate the sitemap with all indexable pages on the site.",
                    effort="medium",
                )

            if not analysis.get("urls_match_domain"):
                count = len(analysis.get("mismatched_urls", []))
                self.add_finding(
                    priority="P2",
                    title="Sitemap contains URLs from other domains",
                    description=f"Found {count} URL(s) pointing to domains other "
                    "than the site's own domain. Search engines may reject "
                    "cross-domain URLs in a sitemap.",
                    fix="Remove or correct URLs that don't belong to this domain.",
                    effort="low",
                )

            if not analysis.get("has_lastmod"):
                self.add_finding(
                    priority="P3",
                    title="Sitemap missing lastmod dates",
                    description="No <lastmod> elements were found in the sitemap. "
                    "Last-modified dates help search engines prioritise "
                    "crawling recently updated pages.",
                    fix="Add <lastmod> dates to sitemap entries, ideally "
                    "auto-generated from actual content change timestamps.",
                    effort="low",
                )

            if analysis.get("has_duplicates"):
                dup_count = analysis.get("duplicate_count", 0)
                self.add_finding(
                    priority="P2",
                    title="Duplicate URLs in sitemap",
                    description=f"Found {dup_count} duplicate URL(s) in the "
                    "sitemap. Duplicates waste crawl budget and may confuse "
                    "search engines.",
                    fix="Remove duplicate entries from the sitemap.",
                    effort="low",
                )

            if not analysis.get("reasonable_size"):
                self.add_finding(
                    priority="P2",
                    title="Sitemap exceeds 50,000 URLs",
                    description=f"The sitemap contains {analysis.get('url_count', 0)} "
                    "URLs, exceeding the 50,000 URL limit per sitemap file "
                    "recommended by the sitemaps protocol.",
                    fix="Split the sitemap into multiple files and use a "
                    "sitemap index file.",
                    effort="medium",
                )

        if not analysis.get("referenced_in_robots"):
            self.add_finding(
                priority="P3",
                title="Sitemap not referenced in robots.txt",
                description="The robots.txt file does not contain a Sitemap: "
                "directive. Adding one helps search engines discover the "
                "sitemap automatically.",
                fix="Add a Sitemap: directive to robots.txt pointing to "
                "the sitemap URL.",
                effort="low",
            )

        return {
            "total": total,
            "sitemap_exists": sitemap_exists_pts,
            "valid_xml": valid_xml_pts,
            "has_urls": has_urls_pts,
            "urls_match_domain": urls_match_domain_pts,
            "has_lastmod": has_lastmod_pts,
            "referenced_in_robots": referenced_in_robots_pts,
            "no_duplicates": no_duplicates_pts,
            "reasonable_size": reasonable_size_pts,
        }

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_domain(url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        return parsed.hostname or ""

    @staticmethod
    def _extract_base_url(url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        if parsed.scheme and parsed.hostname:
            return f"{parsed.scheme}://{parsed.hostname}"
        return ""

    @staticmethod
    def _fetch(url: str, timeout: int = 10) -> str | None:
        """Fetch a URL and return its text content, or None on failure."""
        try:
            req = Request(url, headers={"User-Agent": "SEO-Audit-Bot/1.0"})
            with urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="replace")
        except (URLError, OSError, ValueError):
            pass
        return None

    @staticmethod
    def _sitemaps_from_robots(robots_txt: str) -> list[str]:
        """Extract Sitemap: URLs from robots.txt content."""
        results = []
        for line in robots_txt.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("sitemap:"):
                sm_url = stripped.split(":", 1)[1].strip()
                if sm_url:
                    results.append(sm_url)
        return results
