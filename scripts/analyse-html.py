#!/usr/bin/env python3
"""
FAT Agent HTML Analyser
Extracts SEO, accessibility, and performance signals from raw HTML.

Usage:
    python analyse-html.py <path-to-html-file>
    python analyse-html.py --url <url>  (requires html content piped in)

Output: JSON report of findings.
"""

import sys
import json
import re
from html.parser import HTMLParser
from collections import defaultdict


class FATHTMLAnalyser(HTMLParser):
    """Parses HTML and extracts audit signals."""

    def __init__(self):
        super().__init__()
        self.findings = {
            "seo": {},
            "accessibility": {},
            "performance": {},
            "security": {},
            "content": {},
        }
        self.current_tag = None
        self.current_attrs = {}
        self.tag_stack = []
        self.text_buffer = ""

        # Counters
        self.h1_count = 0
        self.img_count = 0
        self.img_missing_alt = 0
        self.img_lazy_count = 0
        self.form_inputs = 0
        self.form_inputs_without_label = 0
        self.external_scripts = 0
        self.head_scripts = 0
        self.external_stylesheets = 0
        self.total_html_length = 0
        self.has_skip_link = False
        self.in_head = False
        self.heading_hierarchy = []
        self.meta_tags = {}
        self.og_tags = {}
        self.twitter_tags = {}
        self.link_tags = []
        self.json_ld_blocks = []
        self.has_analytics = False
        self.analytics_providers = []
        self.landmarks = set()
        self.has_viewport = False
        self.has_lang = False
        self.lang_value = None
        self.placeholder_text_found = []
        self.title_text = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.current_tag = tag
        self.current_attrs = attrs_dict
        self.tag_stack.append(tag)

        if tag == "head":
            self.in_head = True

        if tag == "title":
            self.in_title = True
            self.title_text = ""

        if tag == "html":
            if "lang" in attrs_dict:
                self.has_lang = True
                self.lang_value = attrs_dict["lang"]

        # Headings
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self.heading_hierarchy.append(level)
            if tag == "h1":
                self.h1_count += 1

        # Images
        if tag == "img":
            self.img_count += 1
            if "alt" not in attrs_dict:
                self.img_missing_alt += 1
            if attrs_dict.get("loading") == "lazy":
                self.img_lazy_count += 1

        # Meta tags
        if tag == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")

            if name:
                self.meta_tags[name] = content
            if prop.startswith("og:"):
                self.og_tags[prop] = content
            if name.startswith("twitter:") or prop.startswith("twitter:"):
                key = name or prop
                self.twitter_tags[key] = content
            if name == "viewport":
                self.has_viewport = True

        # Link tags
        if tag == "link":
            rel = attrs_dict.get("rel", "")
            href = attrs_dict.get("href", "")
            self.link_tags.append({"rel": rel, "href": href})
            if rel == "stylesheet":
                self.external_stylesheets += 1

        # Scripts
        if tag == "script":
            src = attrs_dict.get("src", "")
            script_type = attrs_dict.get("type", "")

            if script_type == "application/ld+json":
                pass  # Will capture in handle_data

            if src:
                self.external_scripts += 1
                if self.in_head and "async" not in attrs_dict and "defer" not in attrs_dict:
                    self.head_scripts += 1

                # Check for analytics
                if "gtag" in src or "google-analytics" in src or "googletagmanager" in src:
                    self.has_analytics = True
                    self.analytics_providers.append("Google Analytics / GTM")
                if "fbq" in src or "facebook" in src:
                    self.has_analytics = True
                    self.analytics_providers.append("Facebook Pixel")
                if "hotjar" in src:
                    self.has_analytics = True
                    self.analytics_providers.append("Hotjar")
                if "plausible" in src:
                    self.has_analytics = True
                    self.analytics_providers.append("Plausible")

        # Form inputs
        if tag in ("input", "select", "textarea"):
            input_type = attrs_dict.get("type", "text")
            if input_type not in ("hidden", "submit", "button"):
                self.form_inputs += 1
                if "aria-label" not in attrs_dict and "id" not in attrs_dict:
                    self.form_inputs_without_label += 1

        # Skip link detection
        if tag == "a" and len(self.tag_stack) < 5:
            href = attrs_dict.get("href", "")
            if href.startswith("#main") or href.startswith("#content"):
                self.has_skip_link = True

        # Landmarks
        if tag in ("main", "nav", "header", "footer", "aside"):
            self.landmarks.add(tag)
        if attrs_dict.get("role") in ("main", "navigation", "banner", "contentinfo", "complementary"):
            self.landmarks.add(attrs_dict["role"])

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
        if tag == "title":
            self.in_title = False
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

    def handle_data(self, data):
        # Capture <title> text content
        if self.in_title:
            self.title_text += data

        # Check for JSON-LD
        if self.current_tag == "script" and self.current_attrs.get("type") == "application/ld+json":
            try:
                parsed = json.loads(data)
                self.json_ld_blocks.append(parsed)
            except json.JSONDecodeError:
                self.json_ld_blocks.append({"error": "Invalid JSON-LD"})

        # Check for placeholder text
        text = data.strip().lower()
        if text:
            if "lorem ipsum" in text:
                self.placeholder_text_found.append("Lorem ipsum text detected")
            if "placeholder" in text and len(text) < 50:
                self.placeholder_text_found.append(f"Possible placeholder: '{data.strip()[:50]}'")

        # Analytics in inline scripts
        if self.current_tag == "script":
            if "gtag(" in data or "google-analytics" in data:
                self.has_analytics = True
                if "Google Analytics / GTM" not in self.analytics_providers:
                    self.analytics_providers.append("Google Analytics / GTM")
            if "fbq(" in data:
                self.has_analytics = True
                if "Facebook Pixel" not in self.analytics_providers:
                    self.analytics_providers.append("Facebook Pixel")

    def compile_report(self, html_length: int) -> dict:
        """Compile all findings into a structured report."""

        title = self.title_text.strip() or None
        description = self.meta_tags.get("description", None)

        report = {
            "seo": {
                "title_tag": title,
                "title_length": len(title) if title else 0,
                "meta_description": description,
                "meta_description_length": len(description) if description else 0,
                "h1_count": self.h1_count,
                "heading_hierarchy": self.heading_hierarchy,
                "has_canonical": any(
                    "canonical" in link.get("rel", "") for link in self.link_tags
                ),
                "has_robots_meta": "robots" in self.meta_tags,
                "robots_content": self.meta_tags.get("robots", ""),
                "og_tags": self.og_tags,
                "twitter_tags": self.twitter_tags,
                "json_ld_count": len(self.json_ld_blocks),
                "json_ld_types": [
                    block.get("@type", "unknown")
                    for block in self.json_ld_blocks
                    if isinstance(block, dict)
                ],
                "has_favicon": any(
                    "icon" in link.get("rel", "") for link in self.link_tags
                ),
            },
            "accessibility": {
                "has_lang_attribute": self.has_lang,
                "lang_value": self.lang_value,
                "img_total": self.img_count,
                "img_missing_alt": self.img_missing_alt,
                "form_inputs_total": self.form_inputs,
                "form_inputs_without_label": self.form_inputs_without_label,
                "has_skip_link": self.has_skip_link,
                "landmarks_found": list(self.landmarks),
                "has_viewport": self.has_viewport,
            },
            "performance": {
                "html_size_bytes": html_length,
                "html_size_kb": round(html_length / 1024, 1),
                "external_scripts": self.external_scripts,
                "render_blocking_scripts": self.head_scripts,
                "external_stylesheets": self.external_stylesheets,
                "images_total": self.img_count,
                "images_lazy_loaded": self.img_lazy_count,
                "has_preconnect": any(
                    "preconnect" in link.get("rel", "") for link in self.link_tags
                ),
                "has_preload": any(
                    "preload" in link.get("rel", "") for link in self.link_tags
                ),
            },
            "analytics": {
                "has_analytics": self.has_analytics,
                "providers": list(set(self.analytics_providers)),
            },
            "content": {
                "placeholder_text": self.placeholder_text_found,
                "has_placeholder_text": len(self.placeholder_text_found) > 0,
            },
            "summary": {
                "issues_found": 0,
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            },
        }

        # Generate issue summary
        issues = report["summary"]

        # Critical (P0)
        if not report["seo"]["title_tag"]:
            issues["critical"].append("Missing <title> tag")
        if report["seo"]["h1_count"] == 0:
            issues["critical"].append("No <h1> tag found")
        if not report["accessibility"]["has_lang_attribute"]:
            issues["critical"].append("Missing <html lang> attribute")

        # High (P1)
        if not report["seo"]["meta_description"]:
            issues["high"].append("Missing meta description")
        if report["seo"]["h1_count"] > 1:
            issues["high"].append(f"Multiple <h1> tags ({report['seo']['h1_count']})")
        if report["accessibility"]["img_missing_alt"] > 0:
            issues["high"].append(
                f"{report['accessibility']['img_missing_alt']} images missing alt text"
            )
        if not report["seo"]["has_canonical"]:
            issues["high"].append("Missing canonical URL")
        if not report["seo"]["og_tags"]:
            issues["high"].append("No Open Graph tags found")

        # Medium (P2)
        if report["performance"]["render_blocking_scripts"] > 2:
            issues["medium"].append(
                f"{report['performance']['render_blocking_scripts']} render-blocking scripts in <head>"
            )
        if report["performance"]["html_size_kb"] > 100:
            issues["medium"].append(
                f"HTML is {report['performance']['html_size_kb']}KB (recommend < 100KB)"
            )
        if not report["seo"]["has_favicon"]:
            issues["medium"].append("No favicon detected")
        if not report["accessibility"]["has_skip_link"]:
            issues["medium"].append("No skip navigation link")
        if report["content"]["has_placeholder_text"]:
            issues["medium"].append("Placeholder/Lorem Ipsum text detected")

        # Low (P3)
        if not report["seo"]["twitter_tags"]:
            issues["low"].append("No Twitter Card tags")
        if not report["analytics"]["has_analytics"]:
            issues["low"].append("No analytics tracking detected")
        if not report["performance"]["has_preconnect"]:
            issues["low"].append("No preconnect hints found")

        issues["issues_found"] = (
            len(issues["critical"])
            + len(issues["high"])
            + len(issues["medium"])
            + len(issues["low"])
        )

        return report


def analyse_html(html_content: str) -> dict:
    """Analyse HTML content and return a FAT report."""
    analyser = FATHTMLAnalyser()
    analyser.feed(html_content)
    return analyser.compile_report(len(html_content.encode("utf-8")))


def main():
    if len(sys.argv) < 2:
        # Read from stdin
        html_content = sys.stdin.read()
    else:
        filepath = sys.argv[1]
        with open(filepath, "r", encoding="utf-8") as f:
            html_content = f.read()

    report = analyse_html(html_content)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
