#!/usr/bin/env python3
"""
FAT Agent Test Suite
Tests analyse-html.py and calculate-score.py against HTML fixtures
that exercise every detection path.

Usage:
    python test_fat_agent.py
"""

import json
import sys
import os
import unittest

# Import from sibling modules
sys.path.insert(0, os.path.dirname(__file__))
from importlib import import_module

analyse_mod = import_module("analyse-html")
analyse_html = analyse_mod.analyse_html

score_mod = import_module("calculate-score")
calculate_scores = score_mod.calculate_scores
calculate_seo_score = score_mod.calculate_seo_score
calculate_security_score = score_mod.calculate_security_score
calculate_accessibility_score = score_mod.calculate_accessibility_score
calculate_fat_score = score_mod.calculate_fat_score


# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------

PERFECT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Premium Widgets Online — Best Widget Store in Australia</title>
    <meta name="description" content="Shop premium widgets at the best prices in Australia. Free shipping on orders over $50. Discover our hand-picked collection of quality widgets today.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://widgets.example.com/">
    <link rel="icon" href="/favicon.ico">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preload" href="/fonts/main.woff2" as="font" type="font/woff2" crossorigin>
    <meta property="og:title" content="Premium Widgets Online">
    <meta property="og:description" content="Best widget store in Australia">
    <meta property="og:image" content="https://widgets.example.com/og.jpg">
    <meta property="og:url" content="https://widgets.example.com/">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Premium Widgets Online">
    <script type="application/ld+json">{"@type":"WebSite","name":"Premium Widgets","url":"https://widgets.example.com"}</script>
    <script type="application/ld+json">{"@type":"Organization","name":"Widget Co","url":"https://widgets.example.com"}</script>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXX"></script>
</head>
<body>
    <a href="#main">Skip to content</a>
    <header><nav><a href="/">Home</a><a href="/about">About</a></nav></header>
    <main id="main">
        <h1>Premium Widgets Online</h1>
        <h2>Featured Products</h2>
        <img src="widget1.jpg" alt="Deluxe Widget — chrome finish" width="400" height="300">
        <img src="widget2.jpg" alt="Standard Widget — matte black" width="400" height="300" loading="lazy">
        <h3>Customer Reviews</h3>
        <p>Our widgets are the best.</p>
    </main>
    <footer><p>&copy; 2026 Widget Co</p></footer>
</body>
</html>
"""

BROKEN_HTML = """\
<!DOCTYPE html>
<html>
<head>
    <script src="/js/blocking1.js"></script>
    <script src="/js/blocking2.js"></script>
    <script src="/js/blocking3.js"></script>
    <link rel="stylesheet" href="/css/main.css">
    <link rel="stylesheet" href="/css/vendor.css">
</head>
<body>
    <div>
        <h2>Welcome to our site</h2>
        <h4>Skipped h3!</h4>
        <img src="hero.jpg">
        <img src="photo.jpg">
        <img src="banner.png">
        <form>
            <input type="text" name="email">
            <select name="country"></select>
            <textarea name="message"></textarea>
            <input type="hidden" name="csrf" value="abc">
            <input type="submit" value="Send">
        </form>
        <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>
    </div>
</body>
</html>
"""

SEO_EDGE_CASES_HTML = """\
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A</title>
    <meta name="description" content="Short.">
    <meta name="robots" content="noindex, nofollow">
    <link rel="canonical" href="https://example.fr/">
    <link rel="icon" type="image/png" href="/favicon.png">
    <meta property="og:title" content="Test">
    <script type="application/ld+json">{"not valid json: }</script>
</head>
<body>
    <main>
        <h1>First H1</h1>
        <h1>Second H1</h1>
        <h1>Third H1</h1>
    </main>
</body>
</html>
"""

ANALYTICS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Analytics Test</title>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-TEST"></script>
    <script src="https://connect.facebook.net/en_US/fbevents.js"></script>
    <script src="https://static.hotjar.com/c/hotjar-12345.js"></script>
    <script src="https://plausible.io/js/plausible.js" defer></script>
</head>
<body>
    <main>
        <h1>Analytics Page</h1>
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            fbq('init', '123456789');
        </script>
    </main>
</body>
</html>
"""

INLINE_ANALYTICS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><title>Inline Analytics</title></head>
<body>
    <main><h1>Test</h1></main>
    <script>
        (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
        (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
        m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
        })(window,document,'script','https://www.google-analytics.com/analytics.js','ga');
    </script>
</body>
</html>
"""

LANDMARKS_AND_ROLES_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><title>Landmarks Test</title></head>
<body>
    <div role="banner">Site Header</div>
    <div role="navigation">Nav</div>
    <div role="main">Content</div>
    <aside>Sidebar</aside>
    <div role="contentinfo">Footer</div>
</body>
</html>
"""

PERFORMANCE_HEAVY_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Heavy Page</title>
    <script src="/js/a.js"></script>
    <script src="/js/b.js"></script>
    <script src="/js/c.js"></script>
    <script src="/js/d.js"></script>
    <script src="/js/e.js"></script>
    <script async src="/js/async.js"></script>
    <script defer src="/js/defer.js"></script>
    <link rel="stylesheet" href="/css/1.css">
    <link rel="stylesheet" href="/css/2.css">
    <link rel="stylesheet" href="/css/3.css">
</head>
<body>
    <main>
        <h1>Heavy</h1>
        <img src="a.jpg" alt="A">
        <img src="b.jpg" alt="B" loading="lazy">
        <img src="c.jpg" alt="C" loading="lazy">
        <img src="d.jpg" alt="D">
    </main>
</body>
</html>
"""

EMPTY_HTML = """\
<!DOCTYPE html>
<html>
<head></head>
<body></body>
</html>
"""


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------


class TestTitleTagDetection(unittest.TestCase):
    """Verify the title tag bug fix — must capture <title> element text."""

    def test_title_captured_from_element(self):
        r = analyse_html(PERFECT_HTML)
        self.assertEqual(
            r["seo"]["title_tag"],
            "Premium Widgets Online — Best Widget Store in Australia",
        )
        self.assertEqual(r["seo"]["title_length"], 55)

    def test_missing_title_flagged_critical(self):
        r = analyse_html(BROKEN_HTML)
        self.assertIsNone(r["seo"]["title_tag"])
        self.assertEqual(r["seo"]["title_length"], 0)
        self.assertIn("Missing <title> tag", r["summary"]["critical"])

    def test_short_title(self):
        r = analyse_html(SEO_EDGE_CASES_HTML)
        self.assertEqual(r["seo"]["title_tag"], "A")
        self.assertEqual(r["seo"]["title_length"], 1)


class TestMetaDescription(unittest.TestCase):

    def test_description_captured(self):
        r = analyse_html(PERFECT_HTML)
        self.assertIn("Shop premium widgets", r["seo"]["meta_description"])
        self.assertGreater(r["seo"]["meta_description_length"], 100)

    def test_missing_description_flagged_high(self):
        r = analyse_html(BROKEN_HTML)
        self.assertIsNone(r["seo"]["meta_description"])
        self.assertIn("Missing meta description", r["summary"]["high"])

    def test_short_description(self):
        r = analyse_html(SEO_EDGE_CASES_HTML)
        self.assertEqual(r["seo"]["meta_description"], "Short.")
        self.assertEqual(r["seo"]["meta_description_length"], 6)


class TestHeadings(unittest.TestCase):

    def test_single_h1(self):
        r = analyse_html(PERFECT_HTML)
        self.assertEqual(r["seo"]["h1_count"], 1)

    def test_no_h1_flagged_critical(self):
        r = analyse_html(BROKEN_HTML)
        self.assertEqual(r["seo"]["h1_count"], 0)
        self.assertIn("No <h1> tag found", r["summary"]["critical"])

    def test_multiple_h1_flagged_high(self):
        r = analyse_html(SEO_EDGE_CASES_HTML)
        self.assertEqual(r["seo"]["h1_count"], 3)
        self.assertIn("Multiple <h1> tags (3)", r["summary"]["high"])

    def test_heading_hierarchy_logical(self):
        r = analyse_html(PERFECT_HTML)
        self.assertEqual(r["seo"]["heading_hierarchy"], [1, 2, 3])

    def test_heading_hierarchy_skipped(self):
        r = analyse_html(BROKEN_HTML)
        # h2 then h4 — skips h3
        self.assertEqual(r["seo"]["heading_hierarchy"], [2, 4])


class TestStructuredData(unittest.TestCase):

    def test_valid_json_ld_detected(self):
        r = analyse_html(PERFECT_HTML)
        # At least 2 valid JSON-LD blocks with correct types
        self.assertGreaterEqual(r["seo"]["json_ld_count"], 2)
        self.assertIn("WebSite", r["seo"]["json_ld_types"])
        self.assertIn("Organization", r["seo"]["json_ld_types"])

    def test_invalid_json_ld_captured(self):
        r = analyse_html(SEO_EDGE_CASES_HTML)
        # Invalid JSON-LD still gets counted as a block
        self.assertGreaterEqual(r["seo"]["json_ld_count"], 1)

    def test_json_ld_only_html(self):
        """HTML with only JSON-LD and no other scripts."""
        html = '<!DOCTYPE html><html lang="en"><head><title>T</title>'
        html += '<script type="application/ld+json">{"@type":"WebSite","name":"Test"}</script>'
        html += '</head><body><h1>Hi</h1></body></html>'
        r = analyse_html(html)
        self.assertGreaterEqual(r["seo"]["json_ld_count"], 1)
        self.assertIn("WebSite", r["seo"]["json_ld_types"])

    def test_no_json_ld(self):
        r = analyse_html(BROKEN_HTML)
        self.assertEqual(r["seo"]["json_ld_count"], 0)
        self.assertEqual(r["seo"]["json_ld_types"], [])


class TestOpenGraphAndTwitter(unittest.TestCase):

    def test_og_tags_captured(self):
        r = analyse_html(PERFECT_HTML)
        self.assertIn("og:title", r["seo"]["og_tags"])
        self.assertIn("og:description", r["seo"]["og_tags"])
        self.assertIn("og:image", r["seo"]["og_tags"])
        self.assertIn("og:url", r["seo"]["og_tags"])

    def test_twitter_tags_captured(self):
        r = analyse_html(PERFECT_HTML)
        self.assertIn("twitter:card", r["seo"]["twitter_tags"])
        self.assertIn("twitter:title", r["seo"]["twitter_tags"])

    def test_missing_og_flagged_high(self):
        r = analyse_html(BROKEN_HTML)
        self.assertEqual(r["seo"]["og_tags"], {})
        self.assertIn("No Open Graph tags found", r["summary"]["high"])

    def test_missing_twitter_flagged_low(self):
        r = analyse_html(BROKEN_HTML)
        self.assertEqual(r["seo"]["twitter_tags"], {})
        self.assertIn("No Twitter Card tags", r["summary"]["low"])


class TestCanonicalAndRobots(unittest.TestCase):

    def test_canonical_detected(self):
        r = analyse_html(PERFECT_HTML)
        self.assertTrue(r["seo"]["has_canonical"])

    def test_missing_canonical_flagged(self):
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(r["seo"]["has_canonical"])
        self.assertIn("Missing canonical URL", r["summary"]["high"])

    def test_robots_noindex(self):
        r = analyse_html(SEO_EDGE_CASES_HTML)
        self.assertTrue(r["seo"]["has_robots_meta"])
        self.assertIn("noindex", r["seo"]["robots_content"])

    def test_favicon_detected(self):
        r = analyse_html(PERFECT_HTML)
        self.assertTrue(r["seo"]["has_favicon"])

    def test_missing_favicon_flagged(self):
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(r["seo"]["has_favicon"])
        self.assertIn("No favicon detected", r["summary"]["medium"])


class TestAccessibilityImages(unittest.TestCase):

    def test_all_images_have_alt(self):
        r = analyse_html(PERFECT_HTML)
        self.assertEqual(r["accessibility"]["img_total"], 2)
        self.assertEqual(r["accessibility"]["img_missing_alt"], 0)

    def test_images_missing_alt_flagged(self):
        r = analyse_html(BROKEN_HTML)
        self.assertEqual(r["accessibility"]["img_total"], 3)
        self.assertEqual(r["accessibility"]["img_missing_alt"], 3)
        self.assertIn(
            "3 images missing alt text", r["summary"]["high"]
        )


class TestAccessibilityLang(unittest.TestCase):

    def test_lang_present(self):
        r = analyse_html(PERFECT_HTML)
        self.assertTrue(r["accessibility"]["has_lang_attribute"])
        self.assertEqual(r["accessibility"]["lang_value"], "en")

    def test_lang_missing_flagged_critical(self):
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(r["accessibility"]["has_lang_attribute"])
        self.assertIn(
            "Missing <html lang> attribute", r["summary"]["critical"]
        )

    def test_non_english_lang(self):
        r = analyse_html(SEO_EDGE_CASES_HTML)
        self.assertTrue(r["accessibility"]["has_lang_attribute"])
        self.assertEqual(r["accessibility"]["lang_value"], "fr")


class TestAccessibilityForms(unittest.TestCase):

    def test_form_inputs_without_labels(self):
        r = analyse_html(BROKEN_HTML)
        # text input, select, textarea — all missing id and aria-label
        self.assertEqual(r["accessibility"]["form_inputs_total"], 3)
        self.assertEqual(r["accessibility"]["form_inputs_without_label"], 3)

    def test_hidden_and_submit_excluded(self):
        r = analyse_html(BROKEN_HTML)
        # hidden and submit inputs should NOT be counted
        self.assertEqual(r["accessibility"]["form_inputs_total"], 3)

    def test_no_forms(self):
        r = analyse_html(PERFECT_HTML)
        self.assertEqual(r["accessibility"]["form_inputs_total"], 0)


class TestAccessibilityLandmarks(unittest.TestCase):

    def test_semantic_landmarks(self):
        r = analyse_html(PERFECT_HTML)
        landmarks = set(r["accessibility"]["landmarks_found"])
        self.assertIn("header", landmarks)
        self.assertIn("nav", landmarks)
        self.assertIn("main", landmarks)
        self.assertIn("footer", landmarks)

    def test_aria_role_landmarks(self):
        r = analyse_html(LANDMARKS_AND_ROLES_HTML)
        landmarks = set(r["accessibility"]["landmarks_found"])
        self.assertIn("banner", landmarks)
        self.assertIn("navigation", landmarks)
        self.assertIn("main", landmarks)
        self.assertIn("aside", landmarks)
        self.assertIn("contentinfo", landmarks)

    def test_no_landmarks(self):
        r = analyse_html(BROKEN_HTML)
        self.assertEqual(r["accessibility"]["landmarks_found"], [])


class TestPerformance(unittest.TestCase):

    def test_render_blocking_scripts(self):
        r = analyse_html(PERFORMANCE_HEAVY_HTML)
        # 5 sync scripts in head, async and defer don't count
        self.assertEqual(r["performance"]["render_blocking_scripts"], 5)
        self.assertIn(
            "5 render-blocking scripts in <head>", r["summary"]["medium"]
        )

    def test_async_defer_not_counted(self):
        r = analyse_html(PERFORMANCE_HEAVY_HTML)
        # 7 total external scripts (5 sync + 1 async + 1 defer)
        self.assertEqual(r["performance"]["external_scripts"], 7)
        # But only 5 are render-blocking
        self.assertEqual(r["performance"]["render_blocking_scripts"], 5)

    def test_lazy_loading_counted(self):
        r = analyse_html(PERFORMANCE_HEAVY_HTML)
        self.assertEqual(r["performance"]["images_lazy_loaded"], 2)
        self.assertEqual(r["performance"]["images_total"], 4)

    def test_stylesheets_counted(self):
        r = analyse_html(PERFORMANCE_HEAVY_HTML)
        self.assertEqual(r["performance"]["external_stylesheets"], 3)

    def test_preconnect_detected(self):
        r = analyse_html(PERFECT_HTML)
        self.assertTrue(r["performance"]["has_preconnect"])

    def test_preload_detected(self):
        r = analyse_html(PERFECT_HTML)
        self.assertTrue(r["performance"]["has_preload"])

    def test_missing_preconnect_flagged(self):
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(r["performance"]["has_preconnect"])
        self.assertIn("No preconnect hints found", r["summary"]["low"])

    def test_html_size_measured(self):
        r = analyse_html(PERFECT_HTML)
        self.assertGreater(r["performance"]["html_size_bytes"], 0)
        self.assertGreater(r["performance"]["html_size_kb"], 0)


class TestAnalyticsDetection(unittest.TestCase):

    def test_multiple_providers_detected(self):
        r = analyse_html(ANALYTICS_HTML)
        self.assertTrue(r["analytics"]["has_analytics"])
        providers = r["analytics"]["providers"]
        self.assertIn("Google Analytics / GTM", providers)
        self.assertIn("Facebook Pixel", providers)
        self.assertIn("Hotjar", providers)
        self.assertIn("Plausible", providers)

    def test_inline_analytics_detected(self):
        r = analyse_html(INLINE_ANALYTICS_HTML)
        self.assertTrue(r["analytics"]["has_analytics"])
        self.assertIn("Google Analytics / GTM", r["analytics"]["providers"])

    def test_no_analytics_flagged(self):
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(r["analytics"]["has_analytics"])
        self.assertIn(
            "No analytics tracking detected", r["summary"]["low"]
        )


class TestPlaceholderText(unittest.TestCase):

    def test_lorem_ipsum_detected(self):
        r = analyse_html(BROKEN_HTML)
        self.assertTrue(r["content"]["has_placeholder_text"])
        self.assertTrue(
            any("Lorem ipsum" in t for t in r["content"]["placeholder_text"])
        )
        self.assertIn(
            "Placeholder/Lorem Ipsum text detected", r["summary"]["medium"]
        )

    def test_no_placeholder_text(self):
        r = analyse_html(PERFECT_HTML)
        self.assertFalse(r["content"]["has_placeholder_text"])


class TestEmptyHTML(unittest.TestCase):

    def test_empty_page_flags_everything(self):
        r = analyse_html(EMPTY_HTML)
        self.assertIn("Missing <title> tag", r["summary"]["critical"])
        self.assertIn("No <h1> tag found", r["summary"]["critical"])
        self.assertIn("Missing <html lang> attribute", r["summary"]["critical"])
        self.assertIn("Missing meta description", r["summary"]["high"])
        self.assertIn("Missing canonical URL", r["summary"]["high"])
        self.assertIn("No Open Graph tags found", r["summary"]["high"])
        self.assertIn("No favicon detected", r["summary"]["medium"])
        self.assertIn("No Twitter Card tags", r["summary"]["low"])
        self.assertIn("No analytics tracking detected", r["summary"]["low"])
        self.assertGreaterEqual(r["summary"]["issues_found"], 9)


class TestIssueCounts(unittest.TestCase):

    def test_issue_count_matches_lists(self):
        r = analyse_html(BROKEN_HTML)
        s = r["summary"]
        expected = (
            len(s["critical"])
            + len(s["high"])
            + len(s["medium"])
            + len(s["low"])
        )
        self.assertEqual(s["issues_found"], expected)

    def test_perfect_page_minimal_issues(self):
        r = analyse_html(PERFECT_HTML)
        # Perfect page should have very few issues
        self.assertEqual(r["summary"]["critical"], [])
        self.assertEqual(r["summary"]["high"], [])


# ---------------------------------------------------------------------------
# Score Calculator Tests
# ---------------------------------------------------------------------------


class TestSEOScoring(unittest.TestCase):

    def test_perfect_seo_scores_high(self):
        r = analyse_html(PERFECT_HTML)
        scores = calculate_scores(r)
        self.assertGreaterEqual(scores["seo"]["score"], 80)

    def test_broken_seo_scores_low(self):
        r = analyse_html(BROKEN_HTML)
        scores = calculate_scores(r)
        self.assertLessEqual(scores["seo"]["score"], 40)

    def test_title_length_scoring_tiers(self):
        """Verify different title lengths hit different score tiers."""
        # Perfect length (50-60) — full points
        seo_perfect = {"title_tag": "A" * 55, "title_length": 55, "meta_description": None, "meta_description_length": 0}
        s1 = calculate_seo_score(seo_perfect, {})
        # Acceptable length (30-70) — partial
        seo_ok = {"title_tag": "A" * 35, "title_length": 35, "meta_description": None, "meta_description_length": 0}
        s2 = calculate_seo_score(seo_ok, {})
        # Very short — minimal
        seo_short = {"title_tag": "A", "title_length": 1, "meta_description": None, "meta_description_length": 0}
        s3 = calculate_seo_score(seo_short, {})

        self.assertGreater(
            s1["details"]["title_meta"]["score"],
            s2["details"]["title_meta"]["score"],
        )
        self.assertGreater(
            s2["details"]["title_meta"]["score"],
            s3["details"]["title_meta"]["score"],
        )

    def test_heading_hierarchy_scoring(self):
        """Logical hierarchy scores higher than skipped."""
        seo_logical = {"h1_count": 1, "heading_hierarchy": [1, 2, 3]}
        s1 = calculate_seo_score(seo_logical, {})
        seo_skipped = {"h1_count": 1, "heading_hierarchy": [1, 3, 5]}
        s2 = calculate_seo_score(seo_skipped, {})
        self.assertGreater(
            s1["details"]["headings_content"]["score"],
            s2["details"]["headings_content"]["score"],
        )

    def test_structured_data_scoring(self):
        """More JSON-LD blocks = higher score."""
        seo_two = {"json_ld_count": 2}
        s1 = calculate_seo_score(seo_two, {})
        seo_one = {"json_ld_count": 1}
        s2 = calculate_seo_score(seo_one, {})
        seo_none = {"json_ld_count": 0}
        s3 = calculate_seo_score(seo_none, {})
        self.assertGreater(
            s1["details"]["structured_data"]["score"],
            s2["details"]["structured_data"]["score"],
        )
        self.assertGreater(
            s2["details"]["structured_data"]["score"],
            s3["details"]["structured_data"]["score"],
        )

    def test_og_tags_scoring(self):
        """All 4 OG keys + twitter = full social score."""
        seo_full = {
            "og_tags": {"og:title": "T", "og:description": "D", "og:image": "I", "og:url": "U"},
            "twitter_tags": {"twitter:card": "summary"},
        }
        s = calculate_seo_score(seo_full, {})
        self.assertEqual(s["details"]["social"]["score"], 10)


class TestSecurityScoring(unittest.TestCase):

    def test_no_headers_returns_zero(self):
        s = calculate_security_score({})
        self.assertEqual(s["score"], 0)
        self.assertIn("note", s)

    def test_perfect_headers_score_100(self):
        headers = {
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=()",
        }
        s = calculate_security_score(headers)
        self.assertEqual(s["score"], 100)

    def test_partial_hsts_scoring(self):
        """HSTS without includeSubDomains or preload gets partial score."""
        headers_full = {"Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload"}
        headers_partial = {"Strict-Transport-Security": "max-age=31536000"}
        s_full = calculate_security_score(headers_full)
        s_partial = calculate_security_score(headers_partial)
        self.assertEqual(s_full["details"]["hsts"]["score"], 20)
        self.assertEqual(s_partial["details"]["hsts"]["score"], 10)

    def test_csp_report_only_partial(self):
        headers = {"Content-Security-Policy-Report-Only": "default-src 'self'"}
        s = calculate_security_score(headers)
        self.assertEqual(s["details"]["csp"]["score"], 15)

    def test_frame_ancestors_counts_as_xfo(self):
        """CSP frame-ancestors should satisfy X-Frame-Options check."""
        headers = {"Content-Security-Policy": "frame-ancestors 'none'"}
        s = calculate_security_score(headers)
        self.assertEqual(s["details"]["x_frame_options"]["score"], 10)


class TestAccessibilityScoring(unittest.TestCase):

    def test_perfect_a11y_scores_high(self):
        r = analyse_html(PERFECT_HTML)
        scores = calculate_scores(r)
        self.assertGreaterEqual(scores["accessibility"]["score"], 70)

    def test_no_images_gets_full_image_score(self):
        a11y = {"img_total": 0, "img_missing_alt": 0}
        s = calculate_accessibility_score(a11y)
        self.assertEqual(s["details"]["images_alt"]["score"], 20)

    def test_all_images_have_alt_full_score(self):
        a11y = {"img_total": 5, "img_missing_alt": 0}
        s = calculate_accessibility_score(a11y)
        self.assertEqual(s["details"]["images_alt"]["score"], 20)

    def test_half_images_missing_alt(self):
        a11y = {"img_total": 4, "img_missing_alt": 2}
        s = calculate_accessibility_score(a11y)
        self.assertEqual(s["details"]["images_alt"]["score"], 10)

    def test_landmark_scoring(self):
        a11y_full = {"landmarks_found": ["main", "nav", "header", "footer"]}
        s = calculate_accessibility_score(a11y_full)
        # 4 landmarks * 3 = 12, capped at 10
        self.assertEqual(s["details"]["landmarks"]["score"], 10)

    def test_no_landmarks_zero(self):
        a11y = {"landmarks_found": []}
        s = calculate_accessibility_score(a11y)
        self.assertEqual(s["details"]["landmarks"]["score"], 0)

    def test_skip_link_scoring(self):
        a11y_with = {"has_skip_link": True}
        a11y_without = {"has_skip_link": False}
        s1 = calculate_accessibility_score(a11y_with)
        s2 = calculate_accessibility_score(a11y_without)
        self.assertEqual(s1["details"]["skip_navigation"]["score"], 5)
        self.assertEqual(s2["details"]["skip_navigation"]["score"], 0)


class TestOverallFATScore(unittest.TestCase):

    def test_grade_A(self):
        s = calculate_fat_score(95, 95, 95)
        self.assertEqual(s["grade"], "A")
        self.assertGreaterEqual(s["score"], 90)

    def test_grade_B(self):
        s = calculate_fat_score(80, 75, 75)
        self.assertEqual(s["grade"], "B")

    def test_grade_C(self):
        s = calculate_fat_score(65, 60, 60)
        self.assertEqual(s["grade"], "C")

    def test_grade_D(self):
        s = calculate_fat_score(50, 30, 50)
        self.assertEqual(s["grade"], "D")

    def test_grade_F(self):
        s = calculate_fat_score(20, 0, 30)
        self.assertEqual(s["grade"], "F")

    def test_weights_sum_to_1(self):
        s = calculate_fat_score(100, 100, 100)
        weights = s["weights"]
        self.assertAlmostEqual(
            weights["seo"] + weights["security"] + weights["accessibility"],
            1.0,
        )

    def test_perfect_scores_grade_A(self):
        s = calculate_fat_score(100, 100, 100)
        self.assertEqual(s["score"], 100)
        self.assertEqual(s["grade"], "A")


class TestEndToEndPipeline(unittest.TestCase):
    """Test the full analyse -> score pipeline."""

    def test_perfect_html_pipeline(self):
        r = analyse_html(PERFECT_HTML)
        scores = calculate_scores(r)
        self.assertIn("seo", scores)
        self.assertIn("security", scores)
        self.assertIn("accessibility", scores)
        self.assertIn("overall", scores)
        self.assertIn("grade", scores["overall"])

    def test_broken_html_pipeline(self):
        r = analyse_html(BROKEN_HTML)
        scores = calculate_scores(r)
        # Broken page should score poorly
        self.assertLessEqual(scores["overall"]["score"], 50)
        self.assertIn(scores["overall"]["grade"], ("D", "F"))

    def test_pipeline_with_security_headers(self):
        r = analyse_html(PERFECT_HTML)
        headers = {
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=()",
        }
        scores = calculate_scores(r, headers)
        self.assertEqual(scores["security"]["score"], 100)
        self.assertGreaterEqual(scores["overall"]["score"], 85)
        self.assertIn(scores["overall"]["grade"], ("A", "B"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
