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

    def __init__(self, page_url=None):
        super().__init__()
        self.page_url = page_url or ""
        self.is_https = self.page_url.startswith("https://")
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

        # Counters — original
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

        # New counters — mixed content
        self.mixed_content_urls = []

        # New counters — duplicate meta
        self.title_count = 0
        self.meta_description_count = 0
        self.canonical_count = 0

        # New counters — viewport validation
        self.viewport_content = None

        # New counters — PWA / web app manifest
        self.has_manifest = False
        self.has_theme_color = False
        self.theme_color_value = None
        self.has_apple_touch_icon = False
        self.has_service_worker_registration = False

        # New counters — image optimisation
        self.img_with_dimensions = 0  # has both width and height
        self.img_with_srcset = 0
        self.picture_elements = 0
        self.img_modern_format = 0  # src ends with .webp, .avif

        # New counters — font loading
        self.has_font_display_swap = False
        self.has_google_fonts_preconnect = False
        self.font_preloads = 0

        # New counters — cookie/privacy banner
        self.consent_scripts = []

        # New counters — hreflang
        self.hreflang_tags = []

        # New counters — empty headings
        self.empty_headings = 0
        self.in_heading = False
        self.heading_text = ""

        # New counters — inline script/style size
        self.inline_script_bytes = 0
        self.inline_style_bytes = 0
        self.in_script = False
        self.in_style = False
        self.script_has_src = False

        # New counters — meta charset
        self.has_charset = False
        self.charset_value = None

        # New counters — noopener / noreferrer
        self.external_links_total = 0
        self.external_links_without_noopener = 0

        # New counters — anchor validation
        self.anchor_hrefs = []  # internal #fragment links
        self.element_ids = []   # all id= attributes found

        # SPA / client-side rendering framework detection
        self.spa_indicators = []

    def _check_mixed_content(self, url):
        """Flag http:// URLs when page is served over HTTPS."""
        if self.is_https and url.startswith("http://"):
            self.mixed_content_urls.append(url)

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.current_tag = tag
        self.current_attrs = attrs_dict
        self.tag_stack.append(tag)

        # Track element IDs for anchor validation
        if "id" in attrs_dict:
            self.element_ids.append(attrs_dict["id"])

        # SPA / client-side rendering framework detection
        element_id = attrs_dict.get("id", "")
        if element_id == "__next":
            if "Next.js" not in self.spa_indicators:
                self.spa_indicators.append("Next.js")
        if element_id == "__nuxt":
            if "Nuxt" not in self.spa_indicators:
                self.spa_indicators.append("Nuxt")
        if "data-reactroot" in attrs_dict:
            if "React" not in self.spa_indicators:
                self.spa_indicators.append("React")
        if "ng-version" in attrs_dict:
            if "Angular" not in self.spa_indicators:
                self.spa_indicators.append("Angular")
        if any(k.startswith("data-svelte") for k in attrs_dict):
            if "Svelte" not in self.spa_indicators:
                self.spa_indicators.append("Svelte")
        if any(k.startswith("data-astro") for k in attrs_dict):
            if "Astro" not in self.spa_indicators:
                self.spa_indicators.append("Astro")

        if tag == "head":
            self.in_head = True

        if tag == "title":
            self.in_title = True
            self.title_text = ""
            self.title_count += 1

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
            self.in_heading = True
            self.heading_text = ""

        # Images
        if tag == "img":
            self.img_count += 1
            if "alt" not in attrs_dict:
                self.img_missing_alt += 1
            if attrs_dict.get("loading") == "lazy":
                self.img_lazy_count += 1
            # Image dimensions (CLS prevention)
            if "width" in attrs_dict and "height" in attrs_dict:
                self.img_with_dimensions += 1
            # Srcset for responsive images
            if "srcset" in attrs_dict:
                self.img_with_srcset += 1
            # Modern image formats
            src = attrs_dict.get("src", "")
            if src:
                src_lower = src.lower().split("?")[0]  # strip query params
                if src_lower.endswith(".webp") or src_lower.endswith(".avif"):
                    self.img_modern_format += 1
                self._check_mixed_content(src)

        # Picture element
        if tag == "picture":
            self.picture_elements += 1

        # Source element inside picture (for modern format detection)
        if tag == "source":
            srcset = attrs_dict.get("srcset", "")
            stype = attrs_dict.get("type", "")
            if "webp" in stype or "avif" in stype:
                self.img_modern_format += 1
            if srcset:
                self._check_mixed_content(srcset.split(",")[0].strip().split(" ")[0])

        # Meta tags
        if tag == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")
            charset = attrs_dict.get("charset", "")
            http_equiv = attrs_dict.get("http-equiv", "").lower()

            if name:
                self.meta_tags[name] = content
            if prop.startswith("og:"):
                self.og_tags[prop] = content
            if name.startswith("twitter:") or prop.startswith("twitter:"):
                key = name or prop
                self.twitter_tags[key] = content
            if name == "viewport":
                self.has_viewport = True
                self.viewport_content = content
            if name == "description":
                self.meta_description_count += 1
            # Theme color
            if name == "theme-color":
                self.has_theme_color = True
                self.theme_color_value = content
            # Charset
            if charset:
                self.has_charset = True
                self.charset_value = charset.lower()
            if http_equiv == "content-type" and "charset" in content.lower():
                self.has_charset = True
                # Extract charset from content="text/html; charset=utf-8"
                for part in content.split(";"):
                    if "charset" in part.lower():
                        self.charset_value = part.split("=")[-1].strip().lower()

        # Link tags
        if tag == "link":
            rel = attrs_dict.get("rel", "")
            href = attrs_dict.get("href", "")
            hreflang = attrs_dict.get("hreflang", "")
            as_attr = attrs_dict.get("as", "")
            link_type = attrs_dict.get("type", "")
            self.link_tags.append({"rel": rel, "href": href})
            if rel == "stylesheet":
                self.external_stylesheets += 1
                self._check_mixed_content(href)
            # Canonical count
            if "canonical" in rel:
                self.canonical_count += 1
            # PWA manifest
            if "manifest" in rel:
                self.has_manifest = True
            # Apple touch icon
            if "apple-touch-icon" in rel:
                self.has_apple_touch_icon = True
            # Hreflang
            if "alternate" in rel and hreflang:
                self.hreflang_tags.append({"hreflang": hreflang, "href": href})
            # Font preload
            if "preload" in rel and as_attr == "font":
                self.font_preloads += 1
            # Google Fonts preconnect
            if "preconnect" in rel and "fonts.googleapis.com" in href:
                self.has_google_fonts_preconnect = True
            # Mixed content on link href
            if href:
                self._check_mixed_content(href)

        # Scripts
        if tag == "script":
            src = attrs_dict.get("src", "")
            script_type = attrs_dict.get("type", "")

            if script_type == "application/ld+json":
                pass  # Will capture in handle_data

            self.in_script = True
            self.script_has_src = bool(src)

            # SPA detection from script attributes
            script_id = attrs_dict.get("id", "")
            if script_id == "__NEXT_DATA__":
                if "Next.js" not in self.spa_indicators:
                    self.spa_indicators.append("Next.js")

            if src:
                self.external_scripts += 1
                self._check_mixed_content(src)
                if self.in_head and "async" not in attrs_dict and "defer" not in attrs_dict:
                    self.head_scripts += 1

                src_lower = src.lower()

                # SPA detection from script src
                if "/_next/" in src_lower:
                    if "Next.js" not in self.spa_indicators:
                        self.spa_indicators.append("Next.js")
                if "/_nuxt/" in src_lower:
                    if "Nuxt" not in self.spa_indicators:
                        self.spa_indicators.append("Nuxt")

                # Check for analytics
                if "gtag" in src_lower or "google-analytics" in src_lower or "googletagmanager" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Google Analytics / GTM")
                if "fbq" in src_lower or "facebook" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Facebook Pixel")
                if "hotjar" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Hotjar")
                if "plausible" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Plausible")

                # Cookie/consent management scripts
                if "cookiebot" in src_lower or "consent.cookiebot" in src_lower:
                    self.consent_scripts.append("Cookiebot")
                if "onetrust" in src_lower or "optanon" in src_lower or "cookielaw" in src_lower:
                    self.consent_scripts.append("OneTrust")
                if "cookieyes" in src_lower or "cookie-yes" in src_lower:
                    self.consent_scripts.append("CookieYes")
                if "termly" in src_lower:
                    self.consent_scripts.append("Termly")
                if "cookieconsent" in src_lower:
                    self.consent_scripts.append("CookieConsent")
                if "quantcast" in src_lower and "choice" in src_lower:
                    self.consent_scripts.append("Quantcast Choice")
                if "iubenda" in src_lower:
                    self.consent_scripts.append("iubenda")
                if "trustarc" in src_lower or "truste" in src_lower:
                    self.consent_scripts.append("TrustArc")

        # Style tag
        if tag == "style":
            self.in_style = True

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

        # Anchor tag processing
        if tag == "a":
            href = attrs_dict.get("href", "")
            target = attrs_dict.get("target", "")
            rel = attrs_dict.get("rel", "")

            # Same-page anchor tracking
            if href.startswith("#") and len(href) > 1:
                self.anchor_hrefs.append(href[1:])

            # External link noopener check
            if target == "_blank" and href.startswith("http"):
                self.external_links_total += 1
                if "noopener" not in rel:
                    self.external_links_without_noopener += 1

            # Mixed content on links
            if href:
                self._check_mixed_content(href)

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
        if tag == "script":
            self.in_script = False
            self.script_has_src = False
        if tag == "style":
            self.in_style = False
        # Empty heading detection
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if self.in_heading and not self.heading_text.strip():
                self.empty_headings += 1
            self.in_heading = False
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

    def handle_data(self, data):
        # Capture <title> text content
        if self.in_title:
            self.title_text += data

        # Capture heading text for empty heading detection
        if self.in_heading:
            self.heading_text += data

        # Inline script/style size measurement
        if self.in_script and not self.script_has_src:
            self.inline_script_bytes += len(data.encode("utf-8"))
        if self.in_style:
            self.inline_style_bytes += len(data.encode("utf-8"))
            # Font-display: swap detection in inline styles
            if "font-display" in data and "swap" in data:
                self.has_font_display_swap = True

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

            # SPA detection from inline script content
            if "__NUXT__" in data:
                if "Nuxt" not in self.spa_indicators:
                    self.spa_indicators.append("Nuxt")

            # Service worker registration detection
            if "serviceWorker" in data and "register" in data:
                self.has_service_worker_registration = True

            # Font-display: swap in inline script (e.g. WebFontLoader)
            if "font-display" in data and "swap" in data:
                self.has_font_display_swap = True

    def compile_report(self, html_length: int) -> dict:
        """Compile all findings into a structured report."""

        title = self.title_text.strip() or None
        description = self.meta_tags.get("description", None)

        # Validate viewport content
        viewport_valid = False
        if self.viewport_content:
            vc = self.viewport_content.lower().replace(" ", "")
            viewport_valid = "width=device-width" in vc

        # Anchor validation — find broken same-page anchors
        broken_anchors = [
            f"#{frag}" for frag in self.anchor_hrefs if frag not in self.element_ids
        ]

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
                "og_image_url": self.og_tags.get("og:image", None),
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
                "has_charset": self.has_charset,
                "charset_value": self.charset_value,
                "hreflang_tags": self.hreflang_tags,
                "duplicate_title_tags": self.title_count,
                "duplicate_meta_descriptions": self.meta_description_count,
                "duplicate_canonicals": self.canonical_count,
                "viewport_valid": viewport_valid,
                "viewport_content": self.viewport_content,
                "spa_detected": len(self.spa_indicators) > 0,
                "spa_indicators": list(set(self.spa_indicators)),
            },
            "accessibility": {
                "has_lang_attribute": self.has_lang,
                "lang_value": self.lang_value,
                "img_total": self.img_count,
                "img_missing_alt": self.img_missing_alt,
                "img_with_dimensions": self.img_with_dimensions,
                "form_inputs_total": self.form_inputs,
                "form_inputs_without_label": self.form_inputs_without_label,
                "has_skip_link": self.has_skip_link,
                "landmarks_found": list(self.landmarks),
                "has_viewport": self.has_viewport,
                "empty_headings": self.empty_headings,
                "broken_anchors": broken_anchors,
            },
            "performance": {
                "html_size_bytes": html_length,
                "html_size_kb": round(html_length / 1024, 1),
                "external_scripts": self.external_scripts,
                "render_blocking_scripts": self.head_scripts,
                "external_stylesheets": self.external_stylesheets,
                "images_total": self.img_count,
                "images_lazy_loaded": self.img_lazy_count,
                "images_with_srcset": self.img_with_srcset,
                "picture_elements": self.picture_elements,
                "images_modern_format": self.img_modern_format,
                "has_preconnect": any(
                    "preconnect" in link.get("rel", "") for link in self.link_tags
                ),
                "has_preload": any(
                    "preload" in link.get("rel", "") for link in self.link_tags
                ),
                "inline_script_bytes": self.inline_script_bytes,
                "inline_style_bytes": self.inline_style_bytes,
                "inline_script_kb": round(self.inline_script_bytes / 1024, 1),
                "inline_style_kb": round(self.inline_style_bytes / 1024, 1),
                "font_preloads": self.font_preloads,
                "has_font_display_swap": self.has_font_display_swap,
                "has_google_fonts_preconnect": self.has_google_fonts_preconnect,
            },
            "security": {
                "mixed_content_urls": self.mixed_content_urls,
                "has_mixed_content": len(self.mixed_content_urls) > 0,
                "external_links_total": self.external_links_total,
                "external_links_without_noopener": self.external_links_without_noopener,
            },
            "pwa": {
                "has_manifest": self.has_manifest,
                "has_theme_color": self.has_theme_color,
                "theme_color_value": self.theme_color_value,
                "has_apple_touch_icon": self.has_apple_touch_icon,
                "has_service_worker": self.has_service_worker_registration,
            },
            "privacy": {
                "has_consent_banner": len(self.consent_scripts) > 0,
                "consent_providers": list(set(self.consent_scripts)),
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
            if report["seo"]["spa_detected"]:
                frameworks = ", ".join(report["seo"]["spa_indicators"])
                issues["high"].append(
                    f"No <h1> tag in server-rendered HTML ({frameworks} detected"
                    " — may render client-side; verify in browser)"
                )
            else:
                issues["critical"].append("No <h1> tag found")
        if not report["accessibility"]["has_lang_attribute"]:
            issues["critical"].append("Missing <html lang> attribute")
        if report["security"]["has_mixed_content"]:
            count = len(report["security"]["mixed_content_urls"])
            issues["critical"].append(f"Mixed content: {count} HTTP resource(s) on HTTPS page")

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
        if report["seo"]["duplicate_title_tags"] > 1:
            issues["high"].append(f"Duplicate <title> tags ({report['seo']['duplicate_title_tags']})")
        if report["seo"]["duplicate_meta_descriptions"] > 1:
            issues["high"].append(f"Duplicate meta descriptions ({report['seo']['duplicate_meta_descriptions']})")
        if report["seo"]["duplicate_canonicals"] > 1:
            issues["high"].append(f"Duplicate canonical tags ({report['seo']['duplicate_canonicals']})")
        if report["accessibility"]["has_viewport"] and not report["seo"]["viewport_valid"]:
            issues["high"].append("Viewport meta tag present but missing width=device-width")

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
        if not report["seo"]["has_charset"]:
            issues["medium"].append("Missing <meta charset> declaration")
        if report["accessibility"]["empty_headings"] > 0:
            issues["medium"].append(f"{report['accessibility']['empty_headings']} empty heading tag(s)")
        if report["accessibility"]["broken_anchors"]:
            issues["medium"].append(
                f"Broken same-page anchors: {', '.join(report['accessibility']['broken_anchors'][:5])}"
            )
        if report["performance"]["inline_script_kb"] > 50:
            issues["medium"].append(
                f"Large inline scripts: {report['performance']['inline_script_kb']}KB"
            )
        # Heading hierarchy skip detection
        hierarchy = report["seo"]["heading_hierarchy"]
        if len(hierarchy) > 1:
            for i in range(1, len(hierarchy)):
                if hierarchy[i] > hierarchy[i - 1] + 1:
                    skipped_from = f"h{hierarchy[i - 1]}"
                    skipped_to = f"h{hierarchy[i]}"
                    issues["medium"].append(
                        f"Heading hierarchy skips levels ({skipped_from} \u2192 {skipped_to})"
                    )
                    break
        # Title length warnings
        if report["seo"]["title_tag"]:
            tlen = report["seo"]["title_length"]
            if tlen > 60:
                issues["medium"].append(
                    f"Title tag is {tlen} characters (recommended: 50\u201360)"
                )
            elif tlen < 30:
                issues["medium"].append(
                    f"Title tag is only {tlen} character{'s' if tlen != 1 else ''} (recommended: 50\u201360)"
                )
        # Meta description length warnings
        if report["seo"]["meta_description"]:
            dlen = report["seo"]["meta_description_length"]
            if dlen > 160:
                issues["medium"].append(
                    f"Meta description is {dlen} characters (recommended: 150\u2013160)"
                )
            elif dlen < 70:
                issues["medium"].append(
                    f"Meta description is only {dlen} characters (recommended: 150\u2013160)"
                )

        # Low (P3)
        if not report["seo"]["twitter_tags"]:
            issues["low"].append("No Twitter Card tags")
        if not report["analytics"]["has_analytics"]:
            issues["low"].append("No analytics tracking detected")
        if not report["performance"]["has_preconnect"]:
            issues["low"].append("No preconnect hints found")
        if report["security"]["external_links_without_noopener"] > 0:
            issues["low"].append(
                f"{report['security']['external_links_without_noopener']} external link(s) with target=\"_blank\" missing rel=\"noopener\""
            )
        img_total = report["performance"]["images_total"]
        if img_total > 0 and report["accessibility"]["img_with_dimensions"] == 0:
            issues["low"].append("No images have explicit width/height attributes (CLS risk)")
        if img_total > 3 and report["performance"]["images_with_srcset"] == 0 and report["performance"]["picture_elements"] == 0:
            issues["low"].append("No responsive images (srcset or <picture>) detected")

        issues["issues_found"] = (
            len(issues["critical"])
            + len(issues["high"])
            + len(issues["medium"])
            + len(issues["low"])
        )

        return report


def analyse_html(html_content: str, page_url: str = "") -> dict:
    """Analyse HTML content and return a FAT report."""
    analyser = FATHTMLAnalyser(page_url=page_url)
    analyser.feed(html_content)
    return analyser.compile_report(len(html_content.encode("utf-8")))


def main():
    page_url = ""
    filepath = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--url" and i + 1 < len(args):
            page_url = args[i + 1]
            i += 2
        else:
            filepath = args[i]
            i += 1

    if filepath:
        with open(filepath, "r", encoding="utf-8") as f:
            html_content = f.read()
    else:
        html_content = sys.stdin.read()

    report = analyse_html(html_content, page_url=page_url)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
