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
calculate_performance_score = score_mod.calculate_performance_score
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
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <meta name="theme-color" content="#4285f4">
    <meta property="og:title" content="Premium Widgets Online">
    <meta property="og:description" content="Best widget store in Australia">
    <meta property="og:image" content="https://widgets.example.com/og.jpg">
    <meta property="og:url" content="https://widgets.example.com/">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Premium Widgets Online">
    <link rel="alternate" hreflang="en" href="https://widgets.example.com/">
    <link rel="alternate" hreflang="fr" href="https://widgets.example.com/fr/">
    <script type="application/ld+json">{"@type":"WebSite","name":"Premium Widgets","url":"https://widgets.example.com"}</script>
    <script type="application/ld+json">{"@type":"Organization","name":"Widget Co","url":"https://widgets.example.com"}</script>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXX"></script>
    <style>
        @font-face { font-family: 'Main'; src: url('/fonts/main.woff2'); font-display: swap; }
    </style>
</head>
<body>
    <a href="#main">Skip to content</a>
    <header><nav><a href="/">Home</a><a href="/about">About</a></nav></header>
    <main id="main">
        <h1>Premium Widgets Online</h1>
        <h2>Featured Products</h2>
        <img src="widget1.webp" alt="Deluxe Widget — chrome finish" width="400" height="300">
        <img src="widget2.webp" alt="Standard Widget — matte black" width="400" height="300" loading="lazy">
        <picture>
            <source srcset="hero.avif" type="image/avif">
            <source srcset="hero.webp" type="image/webp">
            <img src="hero.jpg" alt="Hero banner" width="1200" height="600" loading="lazy">
        </picture>
        <h3>Customer Reviews</h3>
        <p>Our widgets are the best.</p>
        <a href="https://example.com/partner" target="_blank" rel="noopener noreferrer">Partner</a>
        <a href="#reviews">See reviews</a>
    </main>
    <section id="reviews"><h2>Reviews</h2></section>
    <footer><p>&copy; 2026 Widget Co</p></footer>
    <script>
        if ('serviceWorker' in navigator) { navigator.serviceWorker.register('/sw.js'); }
    </script>
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

# --- NEW FIXTURES ---

MIXED_CONTENT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Mixed Content Test</title>
    <link rel="stylesheet" href="http://cdn.example.com/style.css">
    <script src="http://cdn.example.com/app.js"></script>
</head>
<body>
    <main>
        <h1>Mixed Content Page</h1>
        <img src="http://cdn.example.com/logo.png" alt="Logo">
        <img src="https://cdn.example.com/safe.png" alt="Safe">
        <img src="/relative/image.png" alt="Relative">
        <a href="http://external.example.com">HTTP link</a>
    </main>
</body>
</html>
"""

DUPLICATE_META_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <title>First Title</title>
    <title>Second Title</title>
    <meta name="description" content="First description.">
    <meta name="description" content="Second description that is different.">
    <link rel="canonical" href="https://example.com/page1">
    <link rel="canonical" href="https://example.com/page2">
</head>
<body>
    <main><h1>Duplicate Meta</h1></main>
</body>
</html>
"""

VIEWPORT_EDGE_CASES_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Viewport Test</title>
    <meta name="viewport" content="initial-scale=1.0">
</head>
<body>
    <main><h1>Missing width=device-width</h1></main>
</body>
</html>
"""

PWA_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PWA Test Page With Good Title Length Here</title>
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/icon-192.png">
    <meta name="theme-color" content="#ff5722">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main>
        <h1>PWA Ready</h1>
    </main>
    <script>
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js');
        }
    </script>
</body>
</html>
"""

IMAGE_OPTIMISATION_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Image Optimisation Test Page Title Here</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main>
        <h1>Image Tests</h1>
        <img src="photo.webp" alt="WebP photo" width="800" height="600" srcset="photo-400.webp 400w, photo-800.webp 800w">
        <img src="hero.avif" alt="AVIF hero" width="1200" height="600">
        <picture>
            <source srcset="banner.avif" type="image/avif">
            <source srcset="banner.webp" type="image/webp">
            <img src="banner.jpg" alt="Banner" width="1000" height="400" loading="lazy">
        </picture>
        <img src="old.jpg" alt="Old JPEG" loading="lazy">
    </main>
</body>
</html>
"""

FONT_LOADING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Font Loading Test Page Title Here Now</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="preload" href="/fonts/body.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/fonts/heading.woff2" as="font" type="font/woff2" crossorigin>
    <style>
        @font-face {
            font-family: 'Body';
            src: url('/fonts/body.woff2') format('woff2');
            font-display: swap;
        }
    </style>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main><h1>Font Loading</h1></main>
</body>
</html>
"""

COOKIE_BANNER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Cookie Banner Detection Test Page</title>
    <script src="https://consent.cookiebot.com/uc.js" data-cbid="abc123"></script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main><h1>Cookies</h1></main>
</body>
</html>
"""

COOKIE_ONETRUST_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>OneTrust Cookie Test Page Title Here</title>
    <script src="https://cdn.cookielaw.org/scripttemplates/otSDKStub.js"></script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main><h1>OneTrust</h1></main>
</body>
</html>
"""

HREFLANG_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Hreflang Test Page Title Here For Testing</title>
    <link rel="alternate" hreflang="en" href="https://example.com/">
    <link rel="alternate" hreflang="es" href="https://example.com/es/">
    <link rel="alternate" hreflang="de" href="https://example.com/de/">
    <link rel="alternate" hreflang="x-default" href="https://example.com/">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main><h1>Multi-language</h1></main>
</body>
</html>
"""

EMPTY_HEADINGS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Empty Headings Test Page Title Here Now</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main>
        <h1>Good Heading</h1>
        <h2></h2>
        <h3>   </h3>
        <h2>Also Good</h2>
    </main>
</body>
</html>
"""

INLINE_SIZE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Inline Size Test</title>
    <style>""" + "body { margin: 0; } " * 500 + """</style>
</head>
<body>
    <main>
        <h1>Inline Size</h1>
        <script>""" + "var x = 1; " * 500 + """</script>
    </main>
</body>
</html>
"""

NOOPENER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Noopener Test Page Title For Testing Here</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main>
        <h1>External Links</h1>
        <a href="https://safe.example.com" target="_blank" rel="noopener noreferrer">Safe link</a>
        <a href="https://unsafe1.example.com" target="_blank">Unsafe link 1</a>
        <a href="https://unsafe2.example.com" target="_blank" rel="nofollow">Unsafe link 2</a>
        <a href="/internal" target="_blank">Internal blank (not external)</a>
        <a href="https://safe2.example.com" target="_blank" rel="noopener">Safe link 2</a>
    </main>
</body>
</html>
"""

ANCHOR_VALIDATION_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Anchor Validation Test Page Title Here</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main>
        <h1>Anchor Tests</h1>
        <a href="#section1">Go to section 1</a>
        <a href="#section2">Go to section 2</a>
        <a href="#nonexistent">Go to missing section</a>
        <a href="#also-missing">Also missing</a>
    </main>
    <section id="section1"><h2>Section 1</h2></section>
    <section id="section2"><h2>Section 2</h2></section>
</body>
</html>
"""

CHARSET_VARIANTS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
    <title>Charset HTTP Equiv Test Page Title Here</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main><h1>Charset Test</h1></main>
</body>
</html>
"""

# --- SPA / Client-Side Rendering Fixtures ---

SPA_NEXTJS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>My Next.js App — Home Page Title Here Now</title>
    <meta name="description" content="A Next.js application with client-side rendering for dynamic content delivery and great user experience across all devices.">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="canonical" href="https://example.com/">
    <link rel="icon" href="/favicon.ico">
    <script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>
</head>
<body>
    <div id="__next">
        <nav>Navigation</nav>
        <main>
            <div class="hero-section">
                <p>Welcome to our site</p>
            </div>
        </main>
    </div>
    <script src="/_next/static/chunks/main.js"></script>
</body>
</html>
"""

SPA_REACT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>React App With Good Title Length Here Now</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <div id="root" data-reactroot>
        <main><p>Loading...</p></main>
    </div>
</body>
</html>
"""

SPA_ANGULAR_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Angular App With Proper Title Length Now</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <app-root ng-version="17.0.0">
        <main><p>Loading...</p></main>
    </app-root>
</body>
</html>
"""

SPA_NUXT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nuxt App With Good Enough Title Length</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <div id="__nuxt">
        <main><p>Loading...</p></main>
    </div>
    <script src="/_nuxt/entry.js"></script>
    <script>window.__NUXT__={}</script>
</body>
</html>
"""

SPA_WITH_H1_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Next.js App With H1 Present In SSR Output</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>
</head>
<body>
    <div id="__next">
        <main><h1>Server-Rendered H1</h1></main>
    </div>
</body>
</html>
"""

TITLE_LENGTH_EDGE_CASES_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>This title is way too long and exceeds the recommended sixty character limit for search engine optimisation best practices</title>
    <meta name="description" content="OK.">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main><h1>Title Length</h1></main>
</body>
</html>
"""

META_DESC_LONG_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Meta Description Length Test Page Title Here</title>
    <meta name="description" content="This meta description is intentionally written to be extremely long so that it exceeds the recommended maximum of one hundred and sixty characters which is the generally accepted best practice for search engine optimisation.">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <main><h1>Description Length</h1></main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Test Classes — Original
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
        # h1, h2, h3, h2 (reviews section)
        self.assertEqual(r["seo"]["heading_hierarchy"][:3], [1, 2, 3])

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

    def test_og_image_url_captured(self):
        r = analyse_html(PERFECT_HTML)
        self.assertEqual(r["seo"]["og_image_url"], "https://widgets.example.com/og.jpg")

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
# NEW Test Classes — Mixed Content
# ---------------------------------------------------------------------------


class TestMixedContent(unittest.TestCase):

    def test_mixed_content_detected_on_https(self):
        r = analyse_html(MIXED_CONTENT_HTML, page_url="https://example.com")
        self.assertTrue(r["security"]["has_mixed_content"])
        urls = r["security"]["mixed_content_urls"]
        self.assertIn("http://cdn.example.com/style.css", urls)
        self.assertIn("http://cdn.example.com/app.js", urls)
        self.assertIn("http://cdn.example.com/logo.png", urls)

    def test_no_mixed_content_without_https_url(self):
        """Without page_url, mixed content detection is disabled."""
        r = analyse_html(MIXED_CONTENT_HTML)
        self.assertFalse(r["security"]["has_mixed_content"])

    def test_relative_urls_not_flagged(self):
        r = analyse_html(MIXED_CONTENT_HTML, page_url="https://example.com")
        urls = r["security"]["mixed_content_urls"]
        # /relative/image.png should NOT appear
        self.assertFalse(any("/relative/" in u for u in urls))

    def test_https_resources_not_flagged(self):
        r = analyse_html(MIXED_CONTENT_HTML, page_url="https://example.com")
        urls = r["security"]["mixed_content_urls"]
        self.assertFalse(any("https://cdn.example.com/safe.png" in u for u in urls))

    def test_mixed_content_flagged_critical(self):
        r = analyse_html(MIXED_CONTENT_HTML, page_url="https://example.com")
        self.assertTrue(
            any("Mixed content" in i for i in r["summary"]["critical"])
        )


# ---------------------------------------------------------------------------
# NEW Test Classes — Duplicate Meta
# ---------------------------------------------------------------------------


class TestDuplicateMeta(unittest.TestCase):

    def test_duplicate_titles_detected(self):
        r = analyse_html(DUPLICATE_META_HTML)
        self.assertEqual(r["seo"]["duplicate_title_tags"], 2)

    def test_duplicate_descriptions_detected(self):
        r = analyse_html(DUPLICATE_META_HTML)
        self.assertEqual(r["seo"]["duplicate_meta_descriptions"], 2)

    def test_duplicate_canonicals_detected(self):
        r = analyse_html(DUPLICATE_META_HTML)
        self.assertEqual(r["seo"]["duplicate_canonicals"], 2)

    def test_duplicate_titles_flagged_high(self):
        r = analyse_html(DUPLICATE_META_HTML)
        self.assertTrue(
            any("Duplicate <title>" in i for i in r["summary"]["high"])
        )

    def test_duplicate_descriptions_flagged_high(self):
        r = analyse_html(DUPLICATE_META_HTML)
        self.assertTrue(
            any("Duplicate meta descriptions" in i for i in r["summary"]["high"])
        )

    def test_duplicate_canonicals_flagged_high(self):
        r = analyse_html(DUPLICATE_META_HTML)
        self.assertTrue(
            any("Duplicate canonical" in i for i in r["summary"]["high"])
        )

    def test_no_duplicates_on_clean_page(self):
        r = analyse_html(PERFECT_HTML)
        self.assertEqual(r["seo"]["duplicate_title_tags"], 1)
        self.assertEqual(r["seo"]["duplicate_meta_descriptions"], 1)
        self.assertEqual(r["seo"]["duplicate_canonicals"], 1)


# ---------------------------------------------------------------------------
# NEW Test Classes — Viewport Validation
# ---------------------------------------------------------------------------


class TestViewportValidation(unittest.TestCase):

    def test_valid_viewport(self):
        r = analyse_html(PERFECT_HTML)
        self.assertTrue(r["seo"]["viewport_valid"])

    def test_missing_device_width_flagged(self):
        r = analyse_html(VIEWPORT_EDGE_CASES_HTML)
        self.assertFalse(r["seo"]["viewport_valid"])
        self.assertTrue(
            any("width=device-width" in i for i in r["summary"]["high"])
        )

    def test_viewport_content_captured(self):
        r = analyse_html(VIEWPORT_EDGE_CASES_HTML)
        self.assertEqual(r["seo"]["viewport_content"], "initial-scale=1.0")

    def test_no_viewport(self):
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(r["accessibility"]["has_viewport"])
        self.assertFalse(r["seo"]["viewport_valid"])


# ---------------------------------------------------------------------------
# NEW Test Classes — PWA / Web App Manifest
# ---------------------------------------------------------------------------


class TestPWADetection(unittest.TestCase):

    def test_manifest_detected(self):
        r = analyse_html(PWA_HTML)
        self.assertTrue(r["pwa"]["has_manifest"])

    def test_apple_touch_icon_detected(self):
        r = analyse_html(PWA_HTML)
        self.assertTrue(r["pwa"]["has_apple_touch_icon"])

    def test_theme_color_detected(self):
        r = analyse_html(PWA_HTML)
        self.assertTrue(r["pwa"]["has_theme_color"])
        self.assertEqual(r["pwa"]["theme_color_value"], "#ff5722")

    def test_service_worker_detected(self):
        r = analyse_html(PWA_HTML)
        self.assertTrue(r["pwa"]["has_service_worker"])

    def test_perfect_html_has_pwa(self):
        r = analyse_html(PERFECT_HTML)
        self.assertTrue(r["pwa"]["has_manifest"])
        self.assertTrue(r["pwa"]["has_apple_touch_icon"])
        self.assertTrue(r["pwa"]["has_theme_color"])
        self.assertTrue(r["pwa"]["has_service_worker"])

    def test_no_pwa_on_broken(self):
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(r["pwa"]["has_manifest"])
        self.assertFalse(r["pwa"]["has_apple_touch_icon"])
        self.assertFalse(r["pwa"]["has_theme_color"])
        self.assertFalse(r["pwa"]["has_service_worker"])


# ---------------------------------------------------------------------------
# NEW Test Classes — Image Optimisation
# ---------------------------------------------------------------------------


class TestImageOptimisation(unittest.TestCase):

    def test_webp_detected(self):
        r = analyse_html(IMAGE_OPTIMISATION_HTML)
        self.assertGreater(r["performance"]["images_modern_format"], 0)

    def test_srcset_detected(self):
        r = analyse_html(IMAGE_OPTIMISATION_HTML)
        self.assertEqual(r["performance"]["images_with_srcset"], 1)

    def test_picture_elements_detected(self):
        r = analyse_html(IMAGE_OPTIMISATION_HTML)
        self.assertEqual(r["performance"]["picture_elements"], 1)

    def test_image_dimensions_tracked(self):
        r = analyse_html(IMAGE_OPTIMISATION_HTML)
        # 3 images have width+height, 1 doesn't
        self.assertEqual(r["accessibility"]["img_with_dimensions"], 3)

    def test_no_dimensions_flagged(self):
        r = analyse_html(BROKEN_HTML)
        self.assertEqual(r["accessibility"]["img_with_dimensions"], 0)
        self.assertTrue(
            any("width/height" in i for i in r["summary"]["low"])
        )

    def test_no_responsive_images_flagged(self):
        """Pages with >3 images and no srcset/picture get a low-priority flag."""
        r = analyse_html(PERFORMANCE_HEAVY_HTML)
        self.assertTrue(
            any("responsive images" in i.lower() for i in r["summary"]["low"])
        )


# ---------------------------------------------------------------------------
# NEW Test Classes — Font Loading
# ---------------------------------------------------------------------------


class TestFontLoading(unittest.TestCase):

    def test_font_display_swap_detected(self):
        r = analyse_html(FONT_LOADING_HTML)
        self.assertTrue(r["performance"]["has_font_display_swap"])

    def test_google_fonts_preconnect_detected(self):
        r = analyse_html(FONT_LOADING_HTML)
        self.assertTrue(r["performance"]["has_google_fonts_preconnect"])

    def test_font_preloads_counted(self):
        r = analyse_html(FONT_LOADING_HTML)
        self.assertEqual(r["performance"]["font_preloads"], 2)

    def test_perfect_html_has_font_loading(self):
        r = analyse_html(PERFECT_HTML)
        self.assertTrue(r["performance"]["has_font_display_swap"])
        self.assertTrue(r["performance"]["has_google_fonts_preconnect"])
        self.assertGreaterEqual(r["performance"]["font_preloads"], 1)


# ---------------------------------------------------------------------------
# NEW Test Classes — Cookie/Privacy Banner
# ---------------------------------------------------------------------------


class TestCookieBannerDetection(unittest.TestCase):

    def test_cookiebot_detected(self):
        r = analyse_html(COOKIE_BANNER_HTML)
        self.assertTrue(r["privacy"]["has_consent_banner"])
        self.assertIn("Cookiebot", r["privacy"]["consent_providers"])

    def test_onetrust_detected(self):
        r = analyse_html(COOKIE_ONETRUST_HTML)
        self.assertTrue(r["privacy"]["has_consent_banner"])
        self.assertIn("OneTrust", r["privacy"]["consent_providers"])

    def test_no_consent_banner(self):
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(r["privacy"]["has_consent_banner"])
        self.assertEqual(r["privacy"]["consent_providers"], [])


# ---------------------------------------------------------------------------
# NEW Test Classes — Hreflang / i18n
# ---------------------------------------------------------------------------


class TestHreflangDetection(unittest.TestCase):

    def test_hreflang_tags_detected(self):
        r = analyse_html(HREFLANG_HTML)
        tags = r["seo"]["hreflang_tags"]
        self.assertEqual(len(tags), 4)
        langs = [t["hreflang"] for t in tags]
        self.assertIn("en", langs)
        self.assertIn("es", langs)
        self.assertIn("de", langs)
        self.assertIn("x-default", langs)

    def test_perfect_html_hreflang(self):
        r = analyse_html(PERFECT_HTML)
        tags = r["seo"]["hreflang_tags"]
        self.assertEqual(len(tags), 2)

    def test_no_hreflang(self):
        r = analyse_html(BROKEN_HTML)
        self.assertEqual(r["seo"]["hreflang_tags"], [])


# ---------------------------------------------------------------------------
# NEW Test Classes — Empty Headings
# ---------------------------------------------------------------------------


class TestEmptyHeadings(unittest.TestCase):

    def test_empty_headings_detected(self):
        r = analyse_html(EMPTY_HEADINGS_HTML)
        self.assertEqual(r["accessibility"]["empty_headings"], 2)

    def test_empty_headings_flagged_medium(self):
        r = analyse_html(EMPTY_HEADINGS_HTML)
        self.assertTrue(
            any("empty heading" in i for i in r["summary"]["medium"])
        )

    def test_no_empty_headings(self):
        r = analyse_html(PERFECT_HTML)
        self.assertEqual(r["accessibility"]["empty_headings"], 0)


# ---------------------------------------------------------------------------
# NEW Test Classes — Inline Script/Style Size
# ---------------------------------------------------------------------------


class TestInlineSize(unittest.TestCase):

    def test_inline_script_size_measured(self):
        r = analyse_html(INLINE_SIZE_HTML)
        self.assertGreater(r["performance"]["inline_script_bytes"], 0)
        self.assertGreater(r["performance"]["inline_script_kb"], 0)

    def test_inline_style_size_measured(self):
        r = analyse_html(INLINE_SIZE_HTML)
        self.assertGreater(r["performance"]["inline_style_bytes"], 0)
        self.assertGreater(r["performance"]["inline_style_kb"], 0)

    def test_external_scripts_not_counted_as_inline(self):
        r = analyse_html(PERFORMANCE_HEAVY_HTML)
        # All scripts are external, so inline should be 0
        self.assertEqual(r["performance"]["inline_script_bytes"], 0)


# ---------------------------------------------------------------------------
# NEW Test Classes — Meta Charset
# ---------------------------------------------------------------------------


class TestMetaCharset(unittest.TestCase):

    def test_charset_attribute_detected(self):
        r = analyse_html(PERFECT_HTML)
        self.assertTrue(r["seo"]["has_charset"])
        self.assertEqual(r["seo"]["charset_value"], "utf-8")

    def test_http_equiv_charset_detected(self):
        r = analyse_html(CHARSET_VARIANTS_HTML)
        self.assertTrue(r["seo"]["has_charset"])
        self.assertEqual(r["seo"]["charset_value"], "iso-8859-1")

    def test_missing_charset_flagged(self):
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(r["seo"]["has_charset"])
        self.assertIn("Missing <meta charset> declaration", r["summary"]["medium"])


# ---------------------------------------------------------------------------
# NEW Test Classes — Noopener / Noreferrer
# ---------------------------------------------------------------------------


class TestNoopener(unittest.TestCase):

    def test_unsafe_external_links_counted(self):
        r = analyse_html(NOOPENER_HTML)
        # 4 external target=_blank links, 2 without noopener
        self.assertEqual(r["security"]["external_links_total"], 4)
        self.assertEqual(r["security"]["external_links_without_noopener"], 2)

    def test_safe_links_not_flagged(self):
        r = analyse_html(PERFECT_HTML)
        self.assertEqual(r["security"]["external_links_without_noopener"], 0)

    def test_unsafe_links_flagged_low(self):
        r = analyse_html(NOOPENER_HTML)
        self.assertTrue(
            any("noopener" in i for i in r["summary"]["low"])
        )

    def test_internal_blank_not_counted(self):
        """target=_blank on internal /paths should not count as external."""
        r = analyse_html(NOOPENER_HTML)
        # /internal doesn't start with http, so not counted
        self.assertEqual(r["security"]["external_links_total"], 4)


# ---------------------------------------------------------------------------
# NEW Test Classes — Anchor Validation
# ---------------------------------------------------------------------------


class TestAnchorValidation(unittest.TestCase):

    def test_valid_anchors_not_flagged(self):
        r = analyse_html(ANCHOR_VALIDATION_HTML)
        broken = r["accessibility"]["broken_anchors"]
        self.assertNotIn("#section1", broken)
        self.assertNotIn("#section2", broken)

    def test_broken_anchors_detected(self):
        r = analyse_html(ANCHOR_VALIDATION_HTML)
        broken = r["accessibility"]["broken_anchors"]
        self.assertIn("#nonexistent", broken)
        self.assertIn("#also-missing", broken)

    def test_broken_anchors_flagged_medium(self):
        r = analyse_html(ANCHOR_VALIDATION_HTML)
        self.assertTrue(
            any("Broken same-page anchors" in i for i in r["summary"]["medium"])
        )

    def test_no_broken_anchors_on_perfect(self):
        r = analyse_html(PERFECT_HTML)
        self.assertEqual(r["accessibility"]["broken_anchors"], [])


# ---------------------------------------------------------------------------
# Score Calculator Tests — Original (updated for new structure)
# ---------------------------------------------------------------------------


class TestSEOScoring(unittest.TestCase):

    def test_perfect_seo_scores_high(self):
        r = analyse_html(PERFECT_HTML)
        scores = calculate_scores(r)
        self.assertGreaterEqual(scores["seo"]["score"], 75)

    def test_broken_seo_scores_low(self):
        r = analyse_html(BROKEN_HTML)
        scores = calculate_scores(r)
        self.assertLessEqual(scores["seo"]["score"], 40)

    def test_title_length_scoring_tiers(self):
        """Verify different title lengths hit different score tiers."""
        seo_perfect = {"title_tag": "A" * 55, "title_length": 55, "meta_description": None, "meta_description_length": 0}
        s1 = calculate_seo_score(seo_perfect, {})
        seo_ok = {"title_tag": "A" * 35, "title_length": 35, "meta_description": None, "meta_description_length": 0}
        s2 = calculate_seo_score(seo_ok, {})
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

    def test_duplicate_meta_penalty(self):
        """Duplicate titles/descriptions should reduce score."""
        seo_clean = {"title_tag": "A" * 55, "title_length": 55, "duplicate_title_tags": 1}
        seo_dup = {"title_tag": "A" * 55, "title_length": 55, "duplicate_title_tags": 2}
        s1 = calculate_seo_score(seo_clean, {})
        s2 = calculate_seo_score(seo_dup, {})
        self.assertGreater(
            s1["details"]["title_meta"]["score"],
            s2["details"]["title_meta"]["score"],
        )

    def test_charset_scoring(self):
        """Charset present = higher i18n score."""
        seo_charset = {"has_charset": True}
        seo_no_charset = {"has_charset": False}
        s1 = calculate_seo_score(seo_charset, {})
        s2 = calculate_seo_score(seo_no_charset, {})
        self.assertGreater(
            s1["details"]["i18n_charset"]["score"],
            s2["details"]["i18n_charset"]["score"],
        )

    def test_viewport_valid_scoring(self):
        """Valid viewport adds to mobile_performance score."""
        seo_valid = {"viewport_valid": True}
        seo_invalid = {"viewport_valid": False}
        s1 = calculate_seo_score(seo_valid, {})
        s2 = calculate_seo_score(seo_invalid, {})
        self.assertGreater(
            s1["details"]["mobile_performance"]["score"],
            s2["details"]["mobile_performance"]["score"],
        )


class TestSecurityScoring(unittest.TestCase):

    def test_no_headers_gives_html_scores(self):
        """Even without headers, mixed content + link safety are scored."""
        html_sec = {"has_mixed_content": False, "external_links_total": 0, "external_links_without_noopener": 0}
        s = calculate_security_score({}, html_sec)
        self.assertEqual(s["details"]["mixed_content"]["score"], 10)
        self.assertEqual(s["details"]["link_safety"]["score"], 5)
        self.assertEqual(s["score"], 15)

    def test_mixed_content_penalty(self):
        html_sec = {"has_mixed_content": True}
        s = calculate_security_score({}, html_sec)
        self.assertEqual(s["details"]["mixed_content"]["score"], 0)

    def test_noopener_penalty(self):
        html_sec = {"external_links_total": 4, "external_links_without_noopener": 4}
        s = calculate_security_score({}, html_sec)
        self.assertEqual(s["details"]["link_safety"]["score"], 0)

    def test_perfect_headers_score_high(self):
        headers = {
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=()",
        }
        html_sec = {"has_mixed_content": False, "external_links_total": 0, "external_links_without_noopener": 0}
        s = calculate_security_score(headers, html_sec)
        self.assertEqual(s["score"], 100)

    def test_partial_hsts_scoring(self):
        """HSTS without includeSubDomains or preload gets partial score."""
        headers_full = {"Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload"}
        headers_partial = {"Strict-Transport-Security": "max-age=31536000"}
        s_full = calculate_security_score(headers_full)
        s_partial = calculate_security_score(headers_partial)
        self.assertEqual(s_full["details"]["hsts"]["score"], 18)
        self.assertEqual(s_partial["details"]["hsts"]["score"], 8)

    def test_csp_report_only_partial(self):
        headers = {"Content-Security-Policy-Report-Only": "default-src 'self'"}
        s = calculate_security_score(headers)
        self.assertEqual(s["details"]["csp"]["score"], 13)

    def test_frame_ancestors_counts_as_xfo(self):
        """CSP frame-ancestors should satisfy X-Frame-Options check."""
        headers = {"Content-Security-Policy": "frame-ancestors 'none'"}
        s = calculate_security_score(headers)
        self.assertEqual(s["details"]["x_frame_options"]["score"], 8)


class TestAccessibilityScoring(unittest.TestCase):

    def test_perfect_a11y_scores_high(self):
        r = analyse_html(PERFECT_HTML)
        scores = calculate_scores(r)
        self.assertGreaterEqual(scores["accessibility"]["score"], 70)

    def test_no_images_gets_full_image_score(self):
        a11y = {"img_total": 0, "img_missing_alt": 0}
        s = calculate_accessibility_score(a11y)
        self.assertEqual(s["details"]["images_alt"]["score"], 18)

    def test_all_images_have_alt_full_score(self):
        a11y = {"img_total": 5, "img_missing_alt": 0}
        s = calculate_accessibility_score(a11y)
        self.assertEqual(s["details"]["images_alt"]["score"], 18)

    def test_half_images_missing_alt(self):
        a11y = {"img_total": 4, "img_missing_alt": 2}
        s = calculate_accessibility_score(a11y)
        self.assertEqual(s["details"]["images_alt"]["score"], 9)

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

    def test_empty_headings_reduce_score(self):
        a11y_clean = {"empty_headings": 0}
        a11y_empty = {"empty_headings": 3}
        s1 = calculate_accessibility_score(a11y_clean)
        s2 = calculate_accessibility_score(a11y_empty)
        self.assertGreater(
            s1["details"]["heading_structure"]["score"] + s1["details"]["empty_headings"]["score"],
            s2["details"]["heading_structure"]["score"] + s2["details"]["empty_headings"]["score"],
        )

    def test_image_dimensions_scoring(self):
        a11y_dims = {"img_total": 4, "img_with_dimensions": 4}
        a11y_no_dims = {"img_total": 4, "img_with_dimensions": 0}
        s1 = calculate_accessibility_score(a11y_dims)
        s2 = calculate_accessibility_score(a11y_no_dims)
        self.assertEqual(s1["details"]["image_dimensions"]["score"], 4)
        self.assertEqual(s2["details"]["image_dimensions"]["score"], 0)


# ---------------------------------------------------------------------------
# NEW Test Classes — Performance Scoring
# ---------------------------------------------------------------------------


class TestPerformanceScoring(unittest.TestCase):

    def test_perfect_performance_scores_high(self):
        r = analyse_html(PERFECT_HTML)
        scores = calculate_scores(r)
        self.assertGreaterEqual(scores["performance"]["score"], 60)

    def test_heavy_page_scores_low(self):
        r = analyse_html(PERFORMANCE_HEAVY_HTML)
        scores = calculate_scores(r)
        self.assertLessEqual(scores["performance"]["score"], 60)

    def test_image_optimisation_scoring(self):
        perf = {
            "images_total": 4,
            "images_with_srcset": 4,
            "picture_elements": 0,
            "images_modern_format": 4,
        }
        s = calculate_performance_score(perf)
        self.assertEqual(s["details"]["image_optimisation"]["score"], 20)

    def test_no_images_full_score(self):
        perf = {"images_total": 0}
        s = calculate_performance_score(perf)
        self.assertEqual(s["details"]["image_optimisation"]["score"], 20)

    def test_font_loading_scoring(self):
        perf = {
            "has_font_display_swap": True,
            "has_google_fonts_preconnect": True,
            "font_preloads": 1,
        }
        s = calculate_performance_score(perf)
        self.assertEqual(s["details"]["font_loading"]["score"], 15)

    def test_no_font_signals_partial(self):
        perf = {
            "has_font_display_swap": False,
            "has_google_fonts_preconnect": False,
            "font_preloads": 0,
        }
        s = calculate_performance_score(perf)
        self.assertEqual(s["details"]["font_loading"]["score"], 5)

    def test_inline_size_scoring(self):
        perf_small = {"inline_script_kb": 2, "inline_style_kb": 3}
        perf_large = {"inline_script_kb": 40, "inline_style_kb": 20}
        s1 = calculate_performance_score(perf_small)
        s2 = calculate_performance_score(perf_large)
        self.assertGreater(
            s1["details"]["inline_assets"]["score"],
            s2["details"]["inline_assets"]["score"],
        )

    def test_render_blocking_scoring(self):
        perf_clean = {"render_blocking_scripts": 0}
        perf_heavy = {"render_blocking_scripts": 5}
        s1 = calculate_performance_score(perf_clean)
        s2 = calculate_performance_score(perf_heavy)
        self.assertEqual(s1["details"]["render_blocking"]["score"], 15)
        self.assertEqual(s2["details"]["render_blocking"]["score"], 0)


class TestOverallFATScore(unittest.TestCase):

    def test_grade_A(self):
        s = calculate_fat_score(95, 95, 95, 95)
        self.assertEqual(s["grade"], "A")
        self.assertGreaterEqual(s["score"], 90)

    def test_grade_B(self):
        s = calculate_fat_score(80, 75, 75, 75)
        self.assertEqual(s["grade"], "B")

    def test_grade_C(self):
        s = calculate_fat_score(65, 60, 60, 60)
        self.assertEqual(s["grade"], "C")

    def test_grade_D(self):
        s = calculate_fat_score(50, 30, 50, 40)
        self.assertEqual(s["grade"], "D")

    def test_grade_F(self):
        s = calculate_fat_score(20, 0, 30, 10)
        self.assertEqual(s["grade"], "F")

    def test_weights_sum_to_1(self):
        s = calculate_fat_score(100, 100, 100, 100)
        weights = s["weights"]
        self.assertAlmostEqual(sum(weights.values()), 1.0)

    def test_perfect_scores_grade_A(self):
        s = calculate_fat_score(100, 100, 100, 100)
        self.assertEqual(s["score"], 100)
        self.assertEqual(s["grade"], "A")

    def test_three_category_fallback(self):
        """When no performance score, uses 3-category weighting."""
        s = calculate_fat_score(100, 100, 100)
        self.assertEqual(s["score"], 100)
        weights = s["weights"]
        self.assertNotIn("performance", weights)
        self.assertAlmostEqual(sum(weights.values()), 1.0)


class TestEndToEndPipeline(unittest.TestCase):
    """Test the full analyse -> score pipeline."""

    def test_perfect_html_pipeline(self):
        r = analyse_html(PERFECT_HTML)
        scores = calculate_scores(r)
        self.assertIn("seo", scores)
        self.assertIn("security", scores)
        self.assertIn("accessibility", scores)
        self.assertIn("performance", scores)
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
        self.assertGreaterEqual(scores["overall"]["score"], 80)
        self.assertIn(scores["overall"]["grade"], ("A", "B"))

    def test_new_sections_present(self):
        """Verify new report sections (security, pwa, privacy) exist."""
        r = analyse_html(PERFECT_HTML)
        self.assertIn("security", r)
        self.assertIn("pwa", r)
        self.assertIn("privacy", r)
        self.assertIn("mixed_content_urls", r["security"])
        self.assertIn("has_manifest", r["pwa"])
        self.assertIn("has_consent_banner", r["privacy"])


# ---------------------------------------------------------------------------
# NEW Test Classes — SPA / Client-Side Rendering Detection
# ---------------------------------------------------------------------------


class TestSPADetection(unittest.TestCase):

    def test_nextjs_detected_by_div_id(self):
        r = analyse_html(SPA_NEXTJS_HTML)
        self.assertTrue(r["seo"]["spa_detected"])
        self.assertIn("Next.js", r["seo"]["spa_indicators"])

    def test_nextjs_detected_by_next_data(self):
        r = analyse_html(SPA_WITH_H1_HTML)
        self.assertTrue(r["seo"]["spa_detected"])
        self.assertIn("Next.js", r["seo"]["spa_indicators"])

    def test_react_detected(self):
        r = analyse_html(SPA_REACT_HTML)
        self.assertTrue(r["seo"]["spa_detected"])
        self.assertIn("React", r["seo"]["spa_indicators"])

    def test_angular_detected(self):
        r = analyse_html(SPA_ANGULAR_HTML)
        self.assertTrue(r["seo"]["spa_detected"])
        self.assertIn("Angular", r["seo"]["spa_indicators"])

    def test_nuxt_detected_by_div_id(self):
        r = analyse_html(SPA_NUXT_HTML)
        self.assertTrue(r["seo"]["spa_detected"])
        self.assertIn("Nuxt", r["seo"]["spa_indicators"])

    def test_no_spa_on_static_html(self):
        r = analyse_html(PERFECT_HTML)
        self.assertFalse(r["seo"]["spa_detected"])
        self.assertEqual(r["seo"]["spa_indicators"], [])

    def test_no_spa_on_broken_html(self):
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(r["seo"]["spa_detected"])


class TestSPAH1Softening(unittest.TestCase):
    """H1 missing on SPA should be P1 High, not P0 Critical."""

    def test_spa_missing_h1_is_high_not_critical(self):
        r = analyse_html(SPA_NEXTJS_HTML)
        self.assertEqual(r["seo"]["h1_count"], 0)
        # Should NOT be in critical
        self.assertFalse(
            any("h1" in i.lower() for i in r["summary"]["critical"])
        )
        # Should be in high
        self.assertTrue(
            any("No <h1>" in i for i in r["summary"]["high"])
        )

    def test_spa_h1_message_includes_framework(self):
        r = analyse_html(SPA_NEXTJS_HTML)
        h1_issues = [i for i in r["summary"]["high"] if "No <h1>" in i]
        self.assertEqual(len(h1_issues), 1)
        self.assertIn("Next.js", h1_issues[0])
        self.assertIn("verify in browser", h1_issues[0])

    def test_spa_with_h1_no_issue(self):
        r = analyse_html(SPA_WITH_H1_HTML)
        self.assertEqual(r["seo"]["h1_count"], 1)
        # No H1 issue in any priority level
        all_issues = (
            r["summary"]["critical"]
            + r["summary"]["high"]
            + r["summary"]["medium"]
            + r["summary"]["low"]
        )
        self.assertFalse(any("h1" in i.lower() for i in all_issues))

    def test_non_spa_missing_h1_still_critical(self):
        r = analyse_html(BROKEN_HTML)
        self.assertEqual(r["seo"]["h1_count"], 0)
        self.assertIn("No <h1> tag found", r["summary"]["critical"])

    def test_react_missing_h1_is_high(self):
        r = analyse_html(SPA_REACT_HTML)
        self.assertEqual(r["seo"]["h1_count"], 0)
        self.assertTrue(
            any("No <h1>" in i and "React" in i for i in r["summary"]["high"])
        )


# ---------------------------------------------------------------------------
# NEW Test Classes — Heading Hierarchy Skip Detection
# ---------------------------------------------------------------------------


class TestHeadingHierarchySkip(unittest.TestCase):

    def test_skip_detected_as_medium(self):
        r = analyse_html(BROKEN_HTML)
        self.assertTrue(
            any("Heading hierarchy skips" in i for i in r["summary"]["medium"])
        )

    def test_skip_message_shows_levels(self):
        r = analyse_html(BROKEN_HTML)
        skip_issues = [i for i in r["summary"]["medium"] if "Heading hierarchy skips" in i]
        self.assertEqual(len(skip_issues), 1)
        self.assertIn("h2", skip_issues[0])
        self.assertIn("h4", skip_issues[0])

    def test_no_skip_on_logical_hierarchy(self):
        r = analyse_html(PERFECT_HTML)
        self.assertFalse(
            any("Heading hierarchy skips" in i for i in r["summary"]["medium"])
        )

    def test_no_skip_on_empty_page(self):
        r = analyse_html(EMPTY_HTML)
        self.assertFalse(
            any("Heading hierarchy skips" in i for i in r["summary"]["medium"])
        )


# ---------------------------------------------------------------------------
# NEW Test Classes — Title & Description Length Warnings
# ---------------------------------------------------------------------------


class TestTitleLengthWarnings(unittest.TestCase):

    def test_short_title_flagged(self):
        r = analyse_html(SEO_EDGE_CASES_HTML)
        self.assertTrue(
            any("Title tag is only" in i for i in r["summary"]["medium"])
        )

    def test_long_title_flagged(self):
        r = analyse_html(TITLE_LENGTH_EDGE_CASES_HTML)
        tlen = r["seo"]["title_length"]
        self.assertGreater(tlen, 60)
        self.assertTrue(
            any("Title tag is" in i and "characters" in i for i in r["summary"]["medium"])
        )

    def test_ideal_title_not_flagged(self):
        r = analyse_html(PERFECT_HTML)
        self.assertFalse(
            any("Title tag is" in i for i in r["summary"]["medium"])
        )

    def test_no_title_not_length_flagged(self):
        """Missing title triggers critical, not a length warning."""
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(
            any("Title tag is" in i for i in r["summary"]["medium"])
        )


class TestDescriptionLengthWarnings(unittest.TestCase):

    def test_short_description_flagged(self):
        r = analyse_html(SEO_EDGE_CASES_HTML)
        self.assertTrue(
            any("Meta description is only" in i for i in r["summary"]["medium"])
        )

    def test_long_description_flagged(self):
        r = analyse_html(META_DESC_LONG_HTML)
        dlen = r["seo"]["meta_description_length"]
        self.assertGreater(dlen, 160)
        self.assertTrue(
            any("Meta description is" in i and "characters" in i for i in r["summary"]["medium"])
        )

    def test_ideal_description_not_flagged(self):
        r = analyse_html(PERFECT_HTML)
        self.assertFalse(
            any("Meta description is" in i for i in r["summary"]["medium"])
        )

    def test_no_description_not_length_flagged(self):
        """Missing description triggers high, not a length warning."""
        r = analyse_html(BROKEN_HTML)
        self.assertFalse(
            any("Meta description is" in i for i in r["summary"]["medium"])
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
