#!/usr/bin/env python3
"""
FAT Agent HTML Analyser
Extracts SEO, accessibility, and performance signals from raw HTML.

Usage:
    python analyse-html.py <path-to-html-file>
    python analyse-html.py --url <url>  (requires html content piped in)
    python analyse-html.py --budget .fat-budget.json page.html
    python analyse-html.py --fetch --url <url> page.html  (fetches HTTP headers + analyses HTML)

Output: JSON report of findings.
"""

import sys
import json
import re
import os
import urllib.request
import urllib.error
from html.parser import HTMLParser
from collections import defaultdict


# Valid WAI-ARIA 1.2 roles (used for role validation)
VALID_ARIA_ROLES = frozenset({
    "alert", "alertdialog", "application", "article", "banner", "button",
    "cell", "checkbox", "columnheader", "combobox", "complementary",
    "contentinfo", "definition", "dialog", "document", "feed", "figure",
    "form", "grid", "gridcell", "group", "heading", "img", "link", "list",
    "listbox", "listitem", "log", "main", "marquee", "math", "menu",
    "menubar", "menuitem", "menuitemcheckbox", "menuitemradio", "meter",
    "navigation", "none", "note", "option", "presentation", "progressbar",
    "radio", "radiogroup", "region", "row", "rowgroup", "rowheader",
    "scrollbar", "search", "searchbox", "separator", "slider", "spinbutton",
    "status", "switch", "tab", "table", "tablist", "tabpanel", "term",
    "textbox", "timer", "toolbar", "tooltip", "tree", "treegrid", "treeitem",
})
DEPRECATED_ARIA_ROLES = frozenset({"directory"})

# Generic image filename patterns (case-insensitive)
GENERIC_IMG_PATTERNS = re.compile(
    r"(^|/)(img[_-]?\d+|image\d*|screenshot\d*|photo\d*|picture\d*|"
    r"untitled|DSC[_\d]+|IMG[_\d]+|Screen\s?Shot)[^/]*\.\w+$",
    re.IGNORECASE,
)

# Poor anchor text patterns
POOR_ANCHOR_TEXTS = frozenset({
    "click here", "here", "read more", "learn more", "more", "link",
    "this", "this link", "go", "see more", "details", "info",
})

# Default performance budgets
DEFAULT_BUDGETS = {
    "html_kb": 100,
    "inline_total_kb": 50,
    "render_blocking_scripts": 2,
    "images_without_lazy": 3,
    "external_scripts": 15,
    "external_stylesheets": 5,
}


class FATHTMLAnalyser(HTMLParser):
    """Parses HTML and extracts audit signals."""

    def __init__(self, page_url=None, budget=None):
        super().__init__()
        self.page_url = page_url or ""
        self.is_https = self.page_url.startswith("https://")
        self.budget = budget or DEFAULT_BUDGETS
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

        # Counters — mixed content
        self.mixed_content_urls = []

        # Counters — duplicate meta
        self.title_count = 0
        self.meta_description_count = 0
        self.canonical_count = 0

        # Counters — viewport validation
        self.viewport_content = None

        # Counters — PWA / web app manifest
        self.has_manifest = False
        self.has_theme_color = False
        self.theme_color_value = None
        self.has_apple_touch_icon = False
        self.has_service_worker_registration = False

        # Counters — image optimisation
        self.img_with_dimensions = 0
        self.img_with_srcset = 0
        self.picture_elements = 0
        self.img_modern_format = 0

        # Counters — font loading
        self.has_font_display_swap = False
        self.has_google_fonts_preconnect = False
        self.font_preloads = 0

        # Counters — preconnect tracking
        self.preconnect_count = 0
        self.preconnect_urls = []

        # Counters — LCP animation / hidden inline style on images
        self.images_with_hidden_inline_style = 0

        # Counters — font preloads with crossorigin
        self.font_preloads_with_crossorigin = 0

        # Counters — cookie/privacy banner
        self.consent_scripts = []

        # Counters — hreflang
        self.hreflang_tags = []

        # Counters — empty headings
        self.empty_headings = 0
        self.in_heading = False
        self.heading_text = ""

        # Counters — inline script/style size
        self.inline_script_bytes = 0
        self.inline_style_bytes = 0
        self.in_script = False
        self.in_style = False
        self.script_has_src = False

        # Counters — meta charset
        self.has_charset = False
        self.charset_value = None

        # Counters — noopener / noreferrer
        self.external_links_total = 0
        self.external_links_without_noopener = 0

        # Counters — anchor validation
        self.anchor_hrefs = []
        self.element_ids = []

        # SPA / client-side rendering framework detection
        self.spa_indicators = []

        # --- NEW: Thin content detection ---
        self.body_text_words = 0
        self.in_body = False
        self.excluded_region_depth = 0  # >0 when inside nav/footer/header

        # --- NEW: Keyword overlap title/h1 ---
        self.h1_texts = []

        # --- NEW: Internal vs external link audit ---
        self.internal_link_count = 0
        self.all_external_link_count = 0

        # --- NEW: Image filename SEO ---
        self.img_generic_filenames = 0

        # --- NEW: Duplicate OG detection ---
        self.og_tag_counts = defaultdict(int)

        # --- NEW: Canonical URL tracking ---
        self.canonical_url = None

        # --- NEW: Orphan/poor anchor text ---
        self.poor_anchor_text_count = 0
        self.in_anchor = False
        self.anchor_text_buffer = ""

        # --- NEW: rel=nofollow audit ---
        self.nofollow_internal_count = 0
        self.nofollow_total_count = 0

        # --- NEW: Accessibility — tabindex > 0 ---
        self.positive_tabindex_count = 0

        # --- NEW: Accessibility — autoplay media ---
        self.autoplay_without_muted_count = 0

        # --- NEW: Accessibility — zoom disabled ---
        self.zoom_disabled = False

        # --- NEW: Accessibility — ARIA role validation ---
        self.invalid_aria_roles = []
        self.deprecated_aria_roles = []

        # --- NEW: Accessibility — button/link semantics ---
        self.link_as_button_count = 0

        # --- NEW: Accessibility — table accessibility ---
        self.tables_total = 0
        self.table_has_th = False
        self.in_table = False
        self.table_nesting = 0

        # --- NEW: Accessibility — SVG accessibility ---
        self.svg_total = 0
        self.svg_without_accessible_name = 0
        self.in_svg = False
        self.svg_depth = 0
        self.svg_has_title = False
        self.svg_has_aria = False

        # --- NEW: Accessibility — iframe titles ---
        self.iframes_total = 0
        self.iframes_without_title = 0

        # --- NEW: Accessibility — prefers-reduced-motion ---
        self.has_prefers_reduced_motion = False

        # --- NEW: Accessibility — fake affordances (non-interactive elements styled as interactive) ---
        self.fake_affordance_count = 0

        # --- NEW: Accessibility — form error association ---
        self.form_inputs_with_describedby = 0

        # --- NEW: Inline dynamic script loaders in <head> ---
        self.inline_dynamic_script_loaders = []

        # --- NEW: Image URL collection (Wave 3) ---
        self.image_urls = []

        # HTTP response headers (populated when --fetch is used)
        self.response_headers = {}

    def _check_mixed_content(self, url):
        """Flag http:// URLs when page is served over HTTPS."""
        if self.is_https and url.startswith("http://"):
            self.mixed_content_urls.append(url)

    def _is_internal_link(self, href):
        """Check if a link is internal (relative or same domain)."""
        if not href or href.startswith("#") or href.startswith("javascript:"):
            return False
        if href.startswith("/") or href.startswith("./") or href.startswith("../"):
            return True
        if self.page_url:
            from urllib.parse import urlparse
            try:
                page_domain = urlparse(self.page_url).netloc
                link_domain = urlparse(href).netloc
                if link_domain and link_domain == page_domain:
                    return True
                if not link_domain:
                    return True
            except Exception:
                pass
        if not href.startswith("http://") and not href.startswith("https://") and not href.startswith("//"):
            return True
        return False

    def _is_external_link(self, href):
        """Check if a link is external (different domain)."""
        if not href or href.startswith("#") or href.startswith("javascript:"):
            return False
        if href.startswith("http://") or href.startswith("https://") or href.startswith("//"):
            if self.page_url:
                from urllib.parse import urlparse
                try:
                    page_domain = urlparse(self.page_url).netloc
                    link_domain = urlparse(href).netloc
                    if link_domain and link_domain != page_domain:
                        return True
                except Exception:
                    pass
                return False
            # No page_url — treat all absolute URLs as external
            return True
        return False

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

        # --- NEW: tabindex > 0 detection ---
        tabindex = attrs_dict.get("tabindex", None)
        if tabindex is not None:
            try:
                if int(tabindex) > 0:
                    self.positive_tabindex_count += 1
            except (ValueError, TypeError):
                pass

        # --- NEW: ARIA role validation ---
        role = attrs_dict.get("role", "")
        if role:
            role_lower = role.lower().strip()
            if role_lower in DEPRECATED_ARIA_ROLES:
                if role_lower not in self.deprecated_aria_roles:
                    self.deprecated_aria_roles.append(role_lower)
            elif role_lower and role_lower not in VALID_ARIA_ROLES:
                if role_lower not in self.invalid_aria_roles:
                    self.invalid_aria_roles.append(role_lower)

        # --- NEW: Button/link semantics ---
        if tag == "a" and attrs_dict.get("role", "").lower() == "button":
            self.link_as_button_count += 1

        # --- NEW: Fake affordance detection ---
        # Non-interactive elements styled to look clickable (div/span with hover/pointer/btn classes
        # or cursor:pointer style) but lacking href, onclick, or appropriate ARIA roles.
        # Skip elements that are children of interactive elements (a, button, label, [role=button]).
        if tag in ("div", "span"):
            has_onclick = "onclick" in attrs_dict
            has_role_interactive = role.lower().strip() in ("button", "link") if role else False
            # Check if any ancestor is an interactive element
            interactive_ancestors = {"a", "button", "label", "summary", "details"}
            has_interactive_ancestor = any(t in interactive_ancestors for t in self.tag_stack)
            if not has_onclick and not has_role_interactive and not has_interactive_ancestor:
                classes = attrs_dict.get("class", "").lower()
                style = attrs_dict.get("style", "").lower()
                interactive_class_keywords = ("clickable", "cursor-pointer", "btn", "button")
                has_interactive_class = any(kw in classes for kw in interactive_class_keywords)
                # Exclude pointer-events-none — it prevents interaction, not a fake affordance
                if "pointer-events-none" in classes or "pointer-events: none" in style:
                    has_interactive_class = False
                has_pointer_style = "cursor:pointer" in style.replace(" ", "") or "cursor: pointer" in style
                if has_interactive_class or has_pointer_style:
                    self.fake_affordance_count += 1

        if tag == "head":
            self.in_head = True

        if tag == "body":
            self.in_body = True

        if tag == "title":
            self.in_title = True
            self.title_text = ""
            self.title_count += 1

        if tag == "html":
            if "lang" in attrs_dict:
                self.has_lang = True
                self.lang_value = attrs_dict["lang"]

        # --- NEW: Thin content — track excluded regions ---
        if tag in ("nav", "footer") and self.in_body:
            self.excluded_region_depth += 1

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
            # --- NEW: Collect image URLs (Wave 3) ---
            img_src = attrs_dict.get("src", "")
            if img_src:
                self.image_urls.append(img_src)
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
            # --- NEW: LCP animation detection — hidden inline styles ---
            style = attrs_dict.get("style", "")
            if style:
                style_norm = style.lower().replace(" ", "")
                if ("opacity:0" in style_norm or "visibility:hidden" in style_norm
                        or "display:none" in style_norm):
                    self.images_with_hidden_inline_style += 1
            # Modern image formats
            src = attrs_dict.get("src", "")
            if src:
                src_lower = src.lower().split("?")[0]  # strip query params
                if src_lower.endswith(".webp") or src_lower.endswith(".avif"):
                    self.img_modern_format += 1
                # Next.js /_next/image serves AVIF/WebP via content negotiation
                elif "/_next/image" in src.lower():
                    self.img_modern_format += 1
                self._check_mixed_content(src)
                # --- NEW: Generic image filename detection ---
                filename = src.split("/")[-1].split("?")[0] if "/" in src else src.split("?")[0]
                if GENERIC_IMG_PATTERNS.search(filename):
                    self.img_generic_filenames += 1

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

        # --- NEW: Autoplay media detection ---
        if tag in ("video", "audio"):
            has_autoplay = "autoplay" in attrs_dict
            has_muted = "muted" in attrs_dict
            if has_autoplay and not has_muted:
                self.autoplay_without_muted_count += 1

        # --- NEW: Table accessibility ---
        if tag == "table":
            self.tables_total += 1
            self.in_table = True
            self.table_nesting += 1
            self.table_has_th = False
        if tag == "th" and self.in_table:
            self.table_has_th = True

        # --- NEW: SVG accessibility ---
        if tag == "svg":
            self.svg_total += 1
            self.in_svg = True
            self.svg_depth = len(self.tag_stack)
            self.svg_has_title = False
            self.svg_has_aria = "aria-label" in attrs_dict or "aria-labelledby" in attrs_dict
            if attrs_dict.get("role") == "img" and self.svg_has_aria:
                pass  # Will check for title child too
        if tag == "title" and self.in_svg:
            self.svg_has_title = True

        # --- NEW: iframe titles ---
        if tag == "iframe":
            self.iframes_total += 1
            if "title" not in attrs_dict or not attrs_dict.get("title", "").strip():
                self.iframes_without_title += 1

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
                # --- NEW: Duplicate OG tracking ---
                self.og_tag_counts[prop] += 1
            if name.startswith("twitter:") or prop.startswith("twitter:"):
                key = name or prop
                self.twitter_tags[key] = content
            if name == "viewport":
                self.has_viewport = True
                self.viewport_content = content
                # --- NEW: Zoom disabled detection ---
                vc = content.lower().replace(" ", "")
                if "user-scalable=no" in vc or "user-scalable=0" in vc:
                    self.zoom_disabled = True
                if "maximum-scale=1" in vc or "maximum-scale=1.0" in vc:
                    self.zoom_disabled = True
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
            # Canonical count + URL tracking
            if "canonical" in rel:
                self.canonical_count += 1
                self.canonical_url = href
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
                if "crossorigin" in attrs_dict:
                    self.font_preloads_with_crossorigin += 1
            # Google Fonts preconnect
            if "preconnect" in rel and "fonts.googleapis.com" in href:
                self.has_google_fonts_preconnect = True
            # --- NEW: Preconnect count tracking ---
            if "preconnect" in rel and href:
                self.preconnect_count += 1
                self.preconnect_urls.append(href)
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

                # Check for analytics — ORIGINAL providers
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

                # --- NEW: Additional analytics providers ---
                if "usefathom.com" in src_lower or "cdn.usefathom.com" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Fathom Analytics")
                if "umami.is" in src_lower or "analytics.umami" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Umami")
                if "mixpanel.com" in src_lower or "mxpnl.com" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Mixpanel")
                if "heap-analytics" in src_lower or "heap.load" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Heap")
                if "segment.com/analytics.js" in src_lower or "cdn.segment.com" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Segment")
                if "amplitude.com" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Amplitude")
                if "posthog" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("PostHog")
                if "clarity.ms" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Microsoft Clarity")
                if "matomo" in src_lower or "piwik" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Matomo")
                if "vercel-analytics" in src_lower or "va.vercel-scripts" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Vercel Analytics")
                if "cloudflareinsights" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Cloudflare Web Analytics")
                if "omniture" in src_lower or "s_code" in src_lower or "appmeasurement" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Adobe Analytics")
                if "snaptr" in src_lower or "sc-static.net" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Snapchat Pixel")
                if ("tiktok" in src_lower and "analytics" in src_lower) or "analytics.tiktok.com" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("TikTok Pixel")
                if "linkedin.com/px" in src_lower or "snap.licdn.com" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("LinkedIn Insight Tag")
                if "pintrk" in src_lower or "s.pinimg.com" in src_lower:
                    self.has_analytics = True
                    self.analytics_providers.append("Pinterest Tag")

                # Cookie/consent management scripts — ORIGINAL
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

                # --- NEW: Additional consent providers ---
                if "osano.com" in src_lower:
                    self.consent_scripts.append("Osano")
                if "cookiefirst.com" in src_lower:
                    self.consent_scripts.append("CookieFirst")
                if "complianz" in src_lower:
                    self.consent_scripts.append("Complianz")

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
                # --- NEW: Form error association ---
                if "aria-describedby" in attrs_dict or "aria-errormessage" in attrs_dict:
                    self.form_inputs_with_describedby += 1

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

            # --- NEW: Anchor text tracking ---
            self.in_anchor = True
            self.anchor_text_buffer = ""

            # Same-page anchor tracking
            if href.startswith("#") and len(href) > 1:
                self.anchor_hrefs.append(href[1:])

            # External link noopener check
            if target == "_blank" and href.startswith("http"):
                self.external_links_total += 1
                if "noopener" not in rel:
                    self.external_links_without_noopener += 1

            # --- NEW: Internal vs external link count ---
            if self._is_internal_link(href):
                self.internal_link_count += 1
            elif self._is_external_link(href):
                self.all_external_link_count += 1

            # --- NEW: rel=nofollow audit ---
            if "nofollow" in rel:
                self.nofollow_total_count += 1
                if self._is_internal_link(href):
                    self.nofollow_internal_count += 1

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
        if tag == "body":
            self.in_body = False
        if tag == "title":
            self.in_title = False
        if tag == "script":
            self.in_script = False
            self.script_has_src = False
        if tag == "style":
            self.in_style = False

        # --- NEW: Thin content — leave excluded regions ---
        if tag in ("nav", "footer") and self.excluded_region_depth > 0:
            self.excluded_region_depth -= 1

        # Empty heading detection
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if self.in_heading and not self.heading_text.strip():
                self.empty_headings += 1
            # --- NEW: Capture h1 text for keyword overlap ---
            if tag == "h1" and self.in_heading and self.heading_text.strip():
                self.h1_texts.append(self.heading_text.strip())
            self.in_heading = False

        # --- NEW: Anchor text — check for poor anchor text on close ---
        if tag == "a" and self.in_anchor:
            text = self.anchor_text_buffer.strip().lower()
            if text and text in POOR_ANCHOR_TEXTS:
                self.poor_anchor_text_count += 1
            self.in_anchor = False

        # --- NEW: Table — track if table had th ---
        if tag == "table":
            if self.in_table and not self.table_has_th and self.tables_total > 0:
                pass  # Will count in compile_report from tables_without_th
            self.table_nesting -= 1
            if self.table_nesting <= 0:
                self.in_table = False
                self.table_nesting = 0

        # --- NEW: SVG — check accessibility on close ---
        if tag == "svg" and self.in_svg:
            if not self.svg_has_title and not self.svg_has_aria:
                self.svg_without_accessible_name += 1
            self.in_svg = False

        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

    def handle_data(self, data):
        # Capture <title> text content
        if self.in_title:
            self.title_text += data

        # Capture heading text for empty heading detection
        if self.in_heading:
            self.heading_text += data

        # --- NEW: Capture anchor text ---
        if self.in_anchor:
            self.anchor_text_buffer += data

        # --- NEW: Thin content — count words in body text outside nav/footer ---
        if self.in_body and not self.in_head and self.excluded_region_depth == 0:
            if not self.in_script and not self.in_style:
                words = data.split()
                self.body_text_words += len(words)

        # Inline script/style size measurement
        if self.in_script and not self.script_has_src:
            self.inline_script_bytes += len(data.encode("utf-8"))
        if self.in_style:
            self.inline_style_bytes += len(data.encode("utf-8"))
            # Font-display: swap detection in inline styles
            if "font-display" in data and "swap" in data:
                self.has_font_display_swap = True
            # --- NEW: prefers-reduced-motion detection ---
            if "prefers-reduced-motion" in data:
                self.has_prefers_reduced_motion = True

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

        # --- NEW: Inline dynamic script loader detection in <head> ---
        if self.current_tag == "script" and self.in_head and not self.script_has_src:
            if "googletagmanager.com/gtm.js" in data and "createElement" in data:
                if "GTM" not in self.inline_dynamic_script_loaders:
                    self.inline_dynamic_script_loaders.append("GTM")
            if "connect.facebook.net" in data and "fbevents.js" in data:
                if "Meta Pixel" not in self.inline_dynamic_script_loaders:
                    self.inline_dynamic_script_loaders.append("Meta Pixel")
            if "static.hotjar.com" in data:
                if "Hotjar" not in self.inline_dynamic_script_loaders:
                    self.inline_dynamic_script_loaders.append("Hotjar")

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

            # --- NEW: Inline analytics detection for new providers ---
            if "mixpanel.init" in data:
                self.has_analytics = True
                if "Mixpanel" not in self.analytics_providers:
                    self.analytics_providers.append("Mixpanel")
            if "heap.load" in data:
                self.has_analytics = True
                if "Heap" not in self.analytics_providers:
                    self.analytics_providers.append("Heap")
            if "analytics.load" in data and "segment" in data.lower():
                self.has_analytics = True
                if "Segment" not in self.analytics_providers:
                    self.analytics_providers.append("Segment")
            if "amplitude.init" in data:
                self.has_analytics = True
                if "Amplitude" not in self.analytics_providers:
                    self.analytics_providers.append("Amplitude")
            if "posthog.init" in data:
                self.has_analytics = True
                if "PostHog" not in self.analytics_providers:
                    self.analytics_providers.append("PostHog")
            if "_linkedin_partner_id" in data:
                self.has_analytics = True
                if "LinkedIn Insight Tag" not in self.analytics_providers:
                    self.analytics_providers.append("LinkedIn Insight Tag")
            if "pintrk" in data:
                self.has_analytics = True
                if "Pinterest Tag" not in self.analytics_providers:
                    self.analytics_providers.append("Pinterest Tag")
            if "rdt('init'" in data or "rdt( 'init'" in data:
                self.has_analytics = True
                if "Reddit Pixel" not in self.analytics_providers:
                    self.analytics_providers.append("Reddit Pixel")
            if "ttq" in data and "tiktok" in data.lower():
                self.has_analytics = True
                if "TikTok Pixel" not in self.analytics_providers:
                    self.analytics_providers.append("TikTok Pixel")
            if "snaptr" in data:
                self.has_analytics = True
                if "Snapchat Pixel" not in self.analytics_providers:
                    self.analytics_providers.append("Snapchat Pixel")

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

            # --- NEW: prefers-reduced-motion in inline scripts ---
            if "prefers-reduced-motion" in data:
                self.has_prefers_reduced_motion = True

    @staticmethod
    def check_image_sizes(image_urls, page_url, threshold_bytes=1048576):
        """HEAD-request each image URL and flag those exceeding threshold.

        Returns (sizes_dict, oversized_list) where:
            sizes_dict: {url: content_length_bytes or None}
            oversized_list: [{url, size}] for images > threshold
        """
        from urllib.parse import urljoin

        sizes = {}
        oversized = []
        for img_url in image_urls:
            resolved = urljoin(page_url, img_url) if page_url else img_url
            try:
                req = urllib.request.Request(resolved, method="HEAD")
                req.add_header("User-Agent", "FAT-Agent/1.0")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    cl = resp.getheader("Content-Length")
                    if cl:
                        size = int(cl)
                        sizes[img_url] = size
                        if size > threshold_bytes:
                            oversized.append({"url": img_url, "size": size})
                    else:
                        sizes[img_url] = None
            except Exception:
                sizes[img_url] = None
        return sizes, oversized

    def compile_report(self, html_length: int) -> dict:
        """Compile all findings into a structured report."""

        title = self.title_text.strip() or None
        description = self.meta_tags.get("description", None)

        # --- NEW: Duplicate title suffix detection ---
        title_duplicate_suffix = None
        if title:
            # Split on common separators: |, -, —, –, :
            segments = re.split(r'\s*[|:\u2014\u2013]\s*|\s+-\s+', title)
            segments = [s.strip() for s in segments if s.strip()]
            if len(segments) >= 2:
                seen = set()
                duplicates = []
                for seg in segments:
                    seg_lower = seg.lower()
                    if seg_lower in seen:
                        duplicates.append(seg)
                    else:
                        seen.add(seg_lower)
                if duplicates:
                    title_duplicate_suffix = duplicates

        # --- NEW: Next.js font-display inference ---
        font_display_swap_source = None
        if self.has_font_display_swap:
            font_display_swap_source = "inline_css"
        elif self.font_preloads > 0 and "Next.js" in self.spa_indicators:
            # Next.js with font preloads infers font-display: swap via
            # next/font optimisation — check for crossorigin font preloads
            if self.font_preloads_with_crossorigin > 0:
                self.has_font_display_swap = True
                font_display_swap_source = "nextjs_font_preload"

        # Validate viewport content
        viewport_valid = False
        if self.viewport_content:
            vc = self.viewport_content.lower().replace(" ", "")
            viewport_valid = "width=device-width" in vc

        # Anchor validation — find broken same-page anchors
        broken_anchors = [
            f"#{frag}" for frag in self.anchor_hrefs if frag not in self.element_ids
        ]

        # --- NEW: Keyword overlap detection ---
        title_h1_keyword_overlap = False
        if title and self.h1_texts:
            title_words = set(w.lower() for w in title.split() if len(w) > 3)
            for h1 in self.h1_texts:
                h1_words = set(w.lower() for w in h1.split() if len(w) > 3)
                if title_words & h1_words:
                    title_h1_keyword_overlap = True
                    break

        # --- NEW: URL structure checks ---
        url_issues = []
        if self.page_url:
            from urllib.parse import urlparse
            try:
                parsed = urlparse(self.page_url)
                path = parsed.path
                if "_" in path:
                    url_issues.append("underscores_in_url")
                if path != path.lower():
                    url_issues.append("uppercase_in_url")
                if "//" in path:
                    url_issues.append("double_slashes_in_url")
                if parsed.query and not any(
                    x in path for x in ["/api/", "/search", "/filter", "/callback"]
                ):
                    url_issues.append("query_params_on_content_page")
            except Exception:
                pass

        # --- NEW: Canonical validation ---
        canonical_self_referencing = None
        canonical_trailing_slash_mismatch = False
        if self.canonical_url and self.page_url:
            canonical_self_referencing = (
                self.canonical_url.rstrip("/") == self.page_url.rstrip("/")
            )
            # Trailing slash consistency — only flag if the canonical differs
            # from the page URL beyond just a trailing slash on the root path.
            # Don't flag when --url was typed without slash but canonical has one
            # (e.g., https://example.com vs https://example.com/) as these are
            # semantically identical.
            canon_norm = self.canonical_url.rstrip("/")
            page_norm = self.page_url.rstrip("/")
            if canon_norm == page_norm:
                # Same URL, just trailing slash difference — not a real issue
                canonical_trailing_slash_mismatch = False
            else:
                canon_has_slash = self.canonical_url.endswith("/")
                page_has_slash = self.page_url.endswith("/")
                if canon_has_slash != page_has_slash:
                    canonical_trailing_slash_mismatch = True

        # --- NEW: Duplicate OG tags ---
        duplicate_og_tags = {k: v for k, v in self.og_tag_counts.items() if v > 1}

        # --- NEW: Tables without th ---
        tables_without_th = 0
        # We track this simply: tables_total - tables_with_th would require per-table tracking
        # Simplified: track in handle_endtag pattern — already done via table_has_th flag
        # For accurate counting, we use a simpler heuristic:
        # tables_without_th is approximated by checking if any th was found at all
        # This is a simplification — for production, per-table tracking would be needed

        # --- NEW: Budget violations ---
        budget_violations = []
        budget = self.budget
        if html_length / 1024 > budget.get("html_kb", 100):
            budget_violations.append(
                f"HTML size ({round(html_length/1024, 1)}KB) exceeds budget ({budget['html_kb']}KB)"
            )
        total_inline_kb = (self.inline_script_bytes + self.inline_style_bytes) / 1024
        if total_inline_kb > budget.get("inline_total_kb", 50):
            budget_violations.append(
                f"Inline assets ({round(total_inline_kb, 1)}KB) exceed budget ({budget['inline_total_kb']}KB)"
            )
        if self.head_scripts > budget.get("render_blocking_scripts", 2):
            budget_violations.append(
                f"Render-blocking scripts ({self.head_scripts}) exceed budget ({budget['render_blocking_scripts']})"
            )
        images_without_lazy = self.img_count - self.img_lazy_count
        if images_without_lazy > budget.get("images_without_lazy", 3):
            budget_violations.append(
                f"Non-lazy images ({images_without_lazy}) exceed budget ({budget['images_without_lazy']})"
            )
        if self.external_scripts > budget.get("external_scripts", 15):
            budget_violations.append(
                f"External scripts ({self.external_scripts}) exceed budget ({budget['external_scripts']})"
            )
        if self.external_stylesheets > budget.get("external_stylesheets", 5):
            budget_violations.append(
                f"External stylesheets ({self.external_stylesheets}) exceed budget ({budget['external_stylesheets']})"
            )

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
                "canonical_url": self.canonical_url,
                "canonical_self_referencing": canonical_self_referencing,
                "canonical_trailing_slash_mismatch": canonical_trailing_slash_mismatch,
                "has_robots_meta": "robots" in self.meta_tags,
                "robots_content": self.meta_tags.get("robots", ""),
                "og_tags": self.og_tags,
                "og_image_url": self.og_tags.get("og:image", None),
                "duplicate_og_tags": duplicate_og_tags,
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
                # --- NEW SEO fields ---
                "body_word_count": self.body_text_words,
                "thin_content": self.body_text_words < 300 and self.body_text_words > 0,
                "title_h1_keyword_overlap": title_h1_keyword_overlap,
                "internal_link_count": self.internal_link_count,
                "external_link_count": self.all_external_link_count,
                "img_generic_filenames": self.img_generic_filenames,
                "url_issues": url_issues,
                "poor_anchor_text_count": self.poor_anchor_text_count,
                "nofollow_total_count": self.nofollow_total_count,
                "nofollow_internal_count": self.nofollow_internal_count,
                "title_duplicate_suffix": title_duplicate_suffix,
            },
            "accessibility": {
                "has_lang_attribute": self.has_lang,
                "lang_value": self.lang_value,
                "img_total": self.img_count,
                "img_missing_alt": self.img_missing_alt,
                "img_with_dimensions": self.img_with_dimensions,
                "form_inputs_total": self.form_inputs,
                "form_inputs_without_label": self.form_inputs_without_label,
                "form_inputs_with_describedby": self.form_inputs_with_describedby,
                "has_skip_link": self.has_skip_link,
                "landmarks_found": list(self.landmarks),
                "has_viewport": self.has_viewport,
                "empty_headings": self.empty_headings,
                "broken_anchors": broken_anchors,
                # --- NEW accessibility fields ---
                "positive_tabindex_count": self.positive_tabindex_count,
                "autoplay_without_muted": self.autoplay_without_muted_count,
                "zoom_disabled": self.zoom_disabled,
                "invalid_aria_roles": self.invalid_aria_roles,
                "deprecated_aria_roles": self.deprecated_aria_roles,
                "link_as_button_count": self.link_as_button_count,
                "tables_total": self.tables_total,
                "tables_without_th": self.tables_total - (1 if self.table_has_th and self.tables_total > 0 else 0),
                "svg_total": self.svg_total,
                "svg_without_accessible_name": self.svg_without_accessible_name,
                "iframes_total": self.iframes_total,
                "iframes_without_title": self.iframes_without_title,
                "has_prefers_reduced_motion": self.has_prefers_reduced_motion,
                "fake_affordance_count": self.fake_affordance_count,
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
                "font_display_swap_source": font_display_swap_source,
                "preconnect_count": self.preconnect_count,
                "preconnect_urls": self.preconnect_urls,
                "images_with_hidden_inline_style": self.images_with_hidden_inline_style,
                "budget_violations": budget_violations,
                "inline_dynamic_script_loaders": list(self.inline_dynamic_script_loaders),
                "_image_urls": list(self.image_urls),
            },
            "security": {
                "mixed_content_urls": self.mixed_content_urls,
                "has_mixed_content": len(self.mixed_content_urls) > 0,
                "external_links_total": self.external_links_total,
                "external_links_without_noopener": self.external_links_without_noopener,
                "response_headers_available": len(self.response_headers) > 0,
                "has_hsts": "strict-transport-security" in self.response_headers,
                "has_csp": "content-security-policy" in self.response_headers,
                "has_x_content_type_options": "x-content-type-options" in self.response_headers,
                "has_x_frame_options": "x-frame-options" in self.response_headers,
                "has_referrer_policy": "referrer-policy" in self.response_headers,
                "has_permissions_policy": "permissions-policy" in self.response_headers,
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
        # Security headers (only when response headers are available)
        if report["security"]["response_headers_available"]:
            missing_headers = []
            if not report["security"]["has_hsts"]:
                missing_headers.append("Strict-Transport-Security")
            if not report["security"]["has_csp"]:
                missing_headers.append("Content-Security-Policy")
            if not report["security"]["has_x_content_type_options"]:
                missing_headers.append("X-Content-Type-Options")
            if not report["security"]["has_x_frame_options"]:
                missing_headers.append("X-Frame-Options")
            if not report["security"]["has_referrer_policy"]:
                missing_headers.append("Referrer-Policy")
            if not report["security"]["has_permissions_policy"]:
                missing_headers.append("Permissions-Policy")
            if missing_headers:
                for h in missing_headers:
                    issues["high"].append(f"Missing security header: {h}")
        else:
            issues["low"].append("Response headers not available — run with --fetch --url <url> to check security headers")
        # --- NEW: Zoom disabled is P0 Critical ---
        if report["accessibility"]["zoom_disabled"]:
            issues["critical"].append("Viewport disables user zoom (user-scalable=no or maximum-scale=1)")

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
        # --- NEW: Autoplay without muted is P1 ---
        if report["accessibility"]["autoplay_without_muted"] > 0:
            issues["high"].append(
                f"{report['accessibility']['autoplay_without_muted']} media element(s) autoplay without muted attribute"
            )
        # --- NEW: LCP animation — hidden inline style on images ---
        if report["performance"]["images_with_hidden_inline_style"] > 0:
            issues["high"].append(
                f"{report['performance']['images_with_hidden_inline_style']} image(s) with hidden inline style (opacity:0, visibility:hidden, display:none) — may delay LCP"
            )
        # --- NEW: Inline dynamic script loaders in <head> ---
        loaders = report["performance"]["inline_dynamic_script_loaders"]
        if loaders:
            loader_names = ", ".join(loaders)
            issues["high"].append(
                f"Inline scripts in <head> dynamically load heavy third-party resources: {loader_names} — defer with setTimeout"
            )

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
            if report["seo"]["spa_detected"]:
                frameworks = ", ".join(report["seo"]["spa_indicators"])
                issues["low"].append(
                    f"No skip navigation link in server-rendered HTML ({frameworks} detected"
                    " — may render client-side; verify in browser)"
                )
            else:
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
        # --- NEW: Thin content detection ---
        if report["seo"]["thin_content"]:
            issues["medium"].append(
                f"Thin content: only {report['seo']['body_word_count']} words (recommend 300+)"
            )
        # --- NEW: Generic image filenames ---
        if report["seo"]["img_generic_filenames"] > 0:
            issues["medium"].append(
                f"{report['seo']['img_generic_filenames']} image(s) with generic filenames (e.g., IMG_001)"
            )
        # --- NEW: Duplicate OG tags ---
        if report["seo"]["duplicate_og_tags"]:
            dup_keys = ", ".join(report["seo"]["duplicate_og_tags"].keys())
            issues["medium"].append(f"Duplicate Open Graph tags: {dup_keys}")
        # --- NEW: Title duplicate suffix ---
        if report["seo"]["title_duplicate_suffix"]:
            dups = ", ".join(report["seo"]["title_duplicate_suffix"])
            issues["medium"].append(f"Title contains repeated segment(s): {dups}")
        # --- NEW: Excess preconnects ---
        if report["performance"]["preconnect_count"] > 4:
            issues["medium"].append(
                f"{report['performance']['preconnect_count']} preconnect hints found (recommend \u2264 4)"
            )
        # --- NEW: Canonical trailing slash mismatch ---
        if report["seo"]["canonical_trailing_slash_mismatch"]:
            issues["medium"].append("Canonical URL trailing slash doesn't match page URL")
        # --- NEW: Positive tabindex ---
        if report["accessibility"]["positive_tabindex_count"] > 0:
            issues["medium"].append(
                f"{report['accessibility']['positive_tabindex_count']} element(s) with tabindex > 0 (disrupts natural tab order)"
            )
        # --- NEW: Table accessibility ---
        tables_no_th = report["accessibility"]["tables_without_th"]
        if tables_no_th > 0:
            issues["medium"].append(
                f"{tables_no_th} table(s) without header cells (<th>)"
            )
        # --- NEW: SVG accessibility ---
        if report["accessibility"]["svg_without_accessible_name"] > 0:
            if report["seo"]["spa_detected"]:
                frameworks = ", ".join(report["seo"]["spa_indicators"])
                issues["low"].append(
                    f"{report['accessibility']['svg_without_accessible_name']} SVG(s) without accessible name in server HTML ({frameworks} detected"
                    " — aria-hidden may render client-side; verify in browser)"
                )
            else:
                issues["medium"].append(
                    f"{report['accessibility']['svg_without_accessible_name']} SVG(s) without accessible name (<title> or aria-label)"
                )
        # --- NEW: iframe titles ---
        if report["accessibility"]["iframes_without_title"] > 0:
            issues["medium"].append(
                f"{report['accessibility']['iframes_without_title']} iframe(s) missing title attribute"
            )
        # --- NEW: Fake affordances ---
        if report["accessibility"]["fake_affordance_count"] > 0:
            issues["medium"].append(
                f"{report['accessibility']['fake_affordance_count']} non-interactive element(s) styled to look clickable (fake affordances)"
            )
        # --- NEW: Budget violations ---
        for violation in budget_violations:
            issues["medium"].append(f"Budget exceeded: {violation}")

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
        # --- NEW: Poor anchor text ---
        if report["seo"]["poor_anchor_text_count"] > 0:
            if report["seo"]["spa_detected"]:
                frameworks = ", ".join(report["seo"]["spa_indicators"])
                issues["low"].append(
                    f"{report['seo']['poor_anchor_text_count']} link(s) with poor anchor text in server HTML ({frameworks} detected"
                    " — may differ after hydration; verify in browser)"
                )
            else:
                issues["low"].append(
                    f"{report['seo']['poor_anchor_text_count']} link(s) with poor anchor text (e.g., 'click here', 'read more')"
                )
        # --- NEW: Zero internal links ---
        if report["seo"]["internal_link_count"] == 0 and self.body_text_words > 0:
            issues["low"].append("No internal links found on this page")
        # --- NEW: Nofollow on internal links ---
        if report["seo"]["nofollow_internal_count"] > 0:
            issues["low"].append(
                f"{report['seo']['nofollow_internal_count']} internal link(s) have rel=\"nofollow\""
            )
        # --- NEW: URL structure issues ---
        for url_issue in url_issues:
            if url_issue == "underscores_in_url":
                issues["low"].append("URL contains underscores (prefer hyphens)")
            elif url_issue == "uppercase_in_url":
                issues["low"].append("URL contains uppercase characters")
            elif url_issue == "double_slashes_in_url":
                issues["low"].append("URL contains double slashes in path")
            elif url_issue == "query_params_on_content_page":
                issues["low"].append("Content page URL contains query parameters")
        # --- NEW: Invalid ARIA roles ---
        if report["accessibility"]["invalid_aria_roles"]:
            issues["low"].append(
                f"Invalid ARIA role(s): {', '.join(report['accessibility']['invalid_aria_roles'][:5])}"
            )
        if report["accessibility"]["deprecated_aria_roles"]:
            issues["low"].append(
                f"Deprecated ARIA role(s): {', '.join(report['accessibility']['deprecated_aria_roles'])}"
            )
        # --- NEW: Link as button ---
        if report["accessibility"]["link_as_button_count"] > 0:
            issues["low"].append(
                f"{report['accessibility']['link_as_button_count']} <a> element(s) with role=\"button\" (review semantics)"
            )

        issues["issues_found"] = (
            len(issues["critical"])
            + len(issues["high"])
            + len(issues["medium"])
            + len(issues["low"])
        )

        return report


def analyse_html(html_content: str, page_url: str = "", budget: dict = None, response_headers: dict = None) -> dict:
    """Analyse HTML content and return a FAT report."""
    analyser = FATHTMLAnalyser(page_url=page_url, budget=budget)
    analyser.response_headers = response_headers or {}
    analyser.feed(html_content)
    return analyser.compile_report(len(html_content.encode("utf-8")))


def analyse_batch(urls, budget=None, timeout=10):
    """Fetch and analyse multiple URLs in sequence.

    Returns a list of report dicts, each augmented with _url and _status.
    Sleeps 0.5s between requests (polite crawling).
    """
    import time

    results = []
    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(0.5)
        report = {"_url": url, "_status": None}
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "FAT-Agent/1.0")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                report["_status"] = resp.status
                analysis = analyse_html(html, page_url=url, budget=budget)
                report.update(analysis)
        except urllib.error.HTTPError as e:
            report["_status"] = e.code
        except Exception as e:
            report["_status"] = str(e)
        results.append(report)
    return results


def check_url_status(urls, timeout=10):
    """HEAD-request each URL and return status information.

    Returns list of {url, status, final_url, redirected}.
    """
    results = []
    for url in urls:
        entry = {"url": url, "status": None, "final_url": url, "redirected": False}
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "FAT-Agent/1.0")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                entry["status"] = resp.status
                entry["final_url"] = resp.url
                entry["redirected"] = resp.url != url
        except urllib.error.HTTPError as e:
            entry["status"] = e.code
        except Exception as e:
            entry["status"] = str(e)
        results.append(entry)
    return results


def main():
    page_url = ""
    filepath = None
    budget = None
    fetch_headers = False
    check_images = False
    batch_file = None
    check_urls_file = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--url" and i + 1 < len(args):
            page_url = args[i + 1]
            i += 2
        elif args[i] == "--budget" and i + 1 < len(args):
            budget_path = args[i + 1]
            try:
                with open(budget_path, "r", encoding="utf-8") as f:
                    budget = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Warning: Could not load budget file '{budget_path}': {e}", file=sys.stderr)
            i += 2
        elif args[i] == "--fetch":
            fetch_headers = True
            i += 1
        elif args[i] == "--check-images":
            check_images = True
            i += 1
        elif args[i] == "--batch" and i + 1 < len(args):
            batch_file = args[i + 1]
            i += 2
        elif args[i] == "--check-urls" and i + 1 < len(args):
            check_urls_file = args[i + 1]
            i += 2
        else:
            filepath = args[i]
            i += 1

    # --- Batch mode ---
    if batch_file:
        with open(batch_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
        # Try JSON array first, then line-delimited
        try:
            urls = json.loads(content)
        except json.JSONDecodeError:
            urls = [line.strip() for line in content.splitlines() if line.strip()]
        results = analyse_batch(urls, budget=budget)
        pages_ok = sum(1 for r in results if isinstance(r.get("_status"), int) and 200 <= r["_status"] < 400)
        pages_failed = len(results) - pages_ok
        output = {
            "pages_tested": len(results),
            "pages_ok": pages_ok,
            "pages_failed": pages_failed,
            "results": results,
        }
        print(json.dumps(output, indent=2))
        return

    # --- URL status check mode ---
    if check_urls_file:
        with open(check_urls_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
        try:
            urls = json.loads(content)
        except json.JSONDecodeError:
            urls = [line.strip() for line in content.splitlines() if line.strip()]
        results = check_url_status(urls)
        print(json.dumps(results, indent=2))
        return

    # Auto-detect .fat-budget.json if no --budget flag
    if budget is None:
        auto_budget_path = ".fat-budget.json"
        if os.path.exists(auto_budget_path):
            try:
                with open(auto_budget_path, "r", encoding="utf-8") as f:
                    budget = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

    if filepath:
        with open(filepath, "r", encoding="utf-8") as f:
            html_content = f.read()
    else:
        html_content = sys.stdin.read()

    response_headers = {}
    if fetch_headers and page_url:
        try:
            req = urllib.request.Request(page_url, method='HEAD')
            req.add_header('User-Agent', 'FAT-Agent/1.0')
            with urllib.request.urlopen(req, timeout=10) as resp:
                response_headers = {k.lower(): v for k, v in resp.getheaders()}
        except Exception as e:
            print(f"Warning: Could not fetch headers from '{page_url}': {e}", file=sys.stderr)

    report = analyse_html(html_content, page_url=page_url, budget=budget, response_headers=response_headers)

    # --- Image size check ---
    if check_images and page_url and report.get("performance", {}).get("_image_urls"):
        image_urls = report["performance"]["_image_urls"]
        sizes, oversized = FATHTMLAnalyser.check_image_sizes(image_urls, page_url)
        if oversized:
            for item in oversized:
                size_mb = round(item["size"] / (1024 * 1024), 2)
                report["summary"]["high"].append(
                    f"Oversized image ({size_mb}MB): {item['url']}"
                )
            report["summary"]["issues_found"] = (
                len(report["summary"]["critical"])
                + len(report["summary"]["high"])
                + len(report["summary"]["medium"])
                + len(report["summary"]["low"])
            )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
