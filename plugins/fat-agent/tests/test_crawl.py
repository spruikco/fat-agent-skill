"""Tests for the multi-page crawler helper functions."""

import sys
import os
import unittest

# add scripts directory to path
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
    ),
)

from crawl import (
    normalize_url,
    extract_links,
    is_same_domain,
    build_crawl_plan,
    is_allowed_by_robots,
)


class TestNormalizeUrl(unittest.TestCase):
    """Test URL normalization and deduplication."""

    def test_strips_fragment(self):
        self.assertEqual(
            normalize_url("https://example.com/page#section"),
            "https://example.com/page",
        )

    def test_strips_trailing_slash(self):
        self.assertEqual(
            normalize_url("https://example.com/page/"),
            "https://example.com/page",
        )

    def test_preserves_root_path(self):
        # root url should keep its slash or normalise consistently
        result = normalize_url("https://example.com/")
        self.assertIn(result, ["https://example.com", "https://example.com/"])

    def test_strips_fragment_and_trailing_slash(self):
        self.assertEqual(
            normalize_url("https://example.com/page/#top"),
            "https://example.com/page",
        )

    def test_lowercases_scheme_and_host(self):
        self.assertEqual(
            normalize_url("HTTPS://EXAMPLE.COM/Page"),
            "https://example.com/Page",
        )

    def test_identical_urls_after_normalization(self):
        a = normalize_url("https://example.com/about/")
        b = normalize_url("https://example.com/about#contact")
        self.assertEqual(a, b)

    def test_different_paths_stay_different(self):
        a = normalize_url("https://example.com/about")
        b = normalize_url("https://example.com/contact")
        self.assertNotEqual(a, b)

    def test_query_params_preserved(self):
        self.assertEqual(
            normalize_url("https://example.com/search?q=hello"),
            "https://example.com/search?q=hello",
        )


class TestExtractLinks(unittest.TestCase):
    """Test link extraction from HTML."""

    def test_extracts_absolute_links(self):
        html = """
        <html><body>
            <a href="https://example.com/about">About</a>
            <a href="https://example.com/contact">Contact</a>
        </body></html>
        """
        links = extract_links(html, "https://example.com")
        self.assertIn("https://example.com/about", links)
        self.assertIn("https://example.com/contact", links)

    def test_resolves_relative_links(self):
        html = '<a href="/about">About</a>'
        links = extract_links(html, "https://example.com/page")
        self.assertIn("https://example.com/about", links)

    def test_resolves_relative_path_links(self):
        html = '<a href="subpage">Sub</a>'
        links = extract_links(html, "https://example.com/dir/")
        self.assertIn("https://example.com/dir/subpage", links)

    def test_ignores_mailto_and_tel(self):
        html = """
        <a href="mailto:test@example.com">Email</a>
        <a href="tel:+1234567890">Phone</a>
        <a href="javascript:void(0)">JS</a>
        """
        links = extract_links(html, "https://example.com")
        self.assertEqual(len(links), 0)

    def test_ignores_empty_href(self):
        html = '<a href="">Empty</a><a>No href</a>'
        links = extract_links(html, "https://example.com")
        self.assertEqual(len(links), 0)

    def test_deduplicates_links(self):
        html = """
        <a href="/about">About</a>
        <a href="/about/">About Again</a>
        <a href="/about#top">about top</a>
        """
        links = extract_links(html, "https://example.com")
        # all three should normalise to the same url
        self.assertEqual(len(links), 1)

    def test_extracts_only_http_links(self):
        html = """
        <a href="https://example.com/page">HTTPS</a>
        <a href="http://example.com/other">HTTP</a>
        <a href="ftp://example.com/file">FTP</a>
        """
        links = extract_links(html, "https://example.com")
        self.assertEqual(len(links), 2)


class TestIsSameDomain(unittest.TestCase):
    """Test same-domain filtering."""

    def test_same_domain(self):
        self.assertTrue(
            is_same_domain("https://example.com/about", "https://example.com")
        )

    def test_different_domain(self):
        self.assertFalse(
            is_same_domain("https://other.com/page", "https://example.com")
        )

    def test_subdomain_is_different(self):
        self.assertFalse(
            is_same_domain("https://blog.example.com/post", "https://example.com")
        )

    def test_different_scheme_same_domain(self):
        self.assertTrue(
            is_same_domain("http://example.com/page", "https://example.com")
        )

    def test_www_vs_non_www(self):
        # www.example.com and example.com are different hostnames
        self.assertFalse(
            is_same_domain("https://www.example.com/page", "https://example.com")
        )

    def test_case_insensitive(self):
        self.assertTrue(
            is_same_domain("https://Example.COM/page", "https://example.com")
        )


class TestBuildCrawlPlan(unittest.TestCase):
    """Test crawl plan generation (which URLs would be crawled)."""

    def _make_link_map(self, mapping):
        """mapping is {url: [list of links found on that page]}."""
        return mapping

    def test_single_page_no_links(self):
        link_map = {"https://example.com": []}
        plan = build_crawl_plan(
            "https://example.com", link_map, max_depth=2, max_pages=10
        )
        self.assertEqual(plan, ["https://example.com"])

    def test_respects_max_depth(self):
        link_map = {
            "https://example.com": ["https://example.com/a"],
            "https://example.com/a": ["https://example.com/a/b"],
            "https://example.com/a/b": ["https://example.com/a/b/c"],
            "https://example.com/a/b/c": [],
        }
        plan = build_crawl_plan(
            "https://example.com", link_map, max_depth=1, max_pages=100
        )
        self.assertIn("https://example.com", plan)
        self.assertIn("https://example.com/a", plan)
        # depth=1 means start + 1 level deep, should not include /a/b
        self.assertNotIn("https://example.com/a/b", plan)

    def test_respects_max_pages(self):
        link_map = {
            "https://example.com": [
                "https://example.com/a",
                "https://example.com/b",
                "https://example.com/c",
            ],
            "https://example.com/a": [],
            "https://example.com/b": [],
            "https://example.com/c": [],
        }
        plan = build_crawl_plan(
            "https://example.com", link_map, max_depth=5, max_pages=2
        )
        self.assertEqual(len(plan), 2)
        # start url should always be first
        self.assertEqual(plan[0], "https://example.com")

    def test_deduplicates_urls(self):
        link_map = {
            "https://example.com": [
                "https://example.com/a",
                "https://example.com/b",
            ],
            "https://example.com/a": ["https://example.com/b"],
            "https://example.com/b": ["https://example.com/a"],
        }
        plan = build_crawl_plan(
            "https://example.com", link_map, max_depth=3, max_pages=100
        )
        self.assertEqual(len(plan), 3)
        self.assertEqual(len(set(plan)), 3)  # no duplicates

    def test_breadth_first_order(self):
        link_map = {
            "https://example.com": [
                "https://example.com/a",
                "https://example.com/b",
            ],
            "https://example.com/a": ["https://example.com/a/deep"],
            "https://example.com/b": [],
            "https://example.com/a/deep": [],
        }
        plan = build_crawl_plan(
            "https://example.com", link_map, max_depth=5, max_pages=100
        )
        # bfs: root -> a, b -> a/deep
        idx_a = plan.index("https://example.com/a")
        idx_b = plan.index("https://example.com/b")
        idx_deep = plan.index("https://example.com/a/deep")
        self.assertLess(idx_a, idx_deep)
        self.assertLess(idx_b, idx_deep)

    def test_filters_cross_domain_links(self):
        link_map = {
            "https://example.com": [
                "https://example.com/a",
                "https://other.com/external",
            ],
            "https://example.com/a": [],
        }
        plan = build_crawl_plan(
            "https://example.com", link_map, max_depth=2, max_pages=100
        )
        self.assertNotIn("https://other.com/external", plan)


class TestIsAllowedByRobots(unittest.TestCase):
    """Test basic robots.txt checking."""

    def test_allows_when_no_disallow(self):
        robots_txt = "User-agent: *\nDisallow:"
        self.assertTrue(is_allowed_by_robots("/about", robots_txt))

    def test_disallows_matching_path(self):
        robots_txt = "User-agent: *\nDisallow: /admin"
        self.assertFalse(is_allowed_by_robots("/admin", robots_txt))
        self.assertFalse(is_allowed_by_robots("/admin/settings", robots_txt))

    def test_allows_non_matching_path(self):
        robots_txt = "User-agent: *\nDisallow: /admin"
        self.assertTrue(is_allowed_by_robots("/about", robots_txt))

    def test_disallow_root_blocks_all(self):
        robots_txt = "User-agent: *\nDisallow: /"
        self.assertFalse(is_allowed_by_robots("/anything", robots_txt))

    def test_empty_robots_allows_all(self):
        self.assertTrue(is_allowed_by_robots("/anything", ""))

    def test_multiple_disallow_rules(self):
        robots_txt = "User-agent: *\nDisallow: /admin\nDisallow: /private"
        self.assertFalse(is_allowed_by_robots("/admin", robots_txt))
        self.assertFalse(is_allowed_by_robots("/private/data", robots_txt))
        self.assertTrue(is_allowed_by_robots("/public", robots_txt))


if __name__ == "__main__":
    unittest.main()
