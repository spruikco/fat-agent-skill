"""Tests for render_js module (without Playwright installed)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from render_js import check_available, render_page


class TestCheckAvailable:
    """Test the check_available function."""

    def test_returns_bool(self):
        result = check_available()
        assert isinstance(result, bool)


class TestRenderPage:
    """Test render_page returns correct structure when playwright is missing."""

    def test_returns_dict(self):
        result = render_page("https://example.com")
        assert isinstance(result, dict)

    def test_has_rendered_key(self):
        result = render_page("https://example.com")
        assert "rendered" in result

    def test_has_html_key(self):
        result = render_page("https://example.com")
        assert "html" in result

    def test_rendered_false_when_playwright_missing(self):
        # if playwright is not installed, rendered should be false
        if not check_available():
            result = render_page("https://example.com")
            assert result["rendered"] is False
            assert result["html"] is None
            assert "error" in result

    def test_error_message_when_playwright_missing(self):
        if not check_available():
            result = render_page("https://example.com")
            assert result["error"] == "playwright not installed"


class TestCLIArgParsing:
    """Test CLI argument parsing without actually running the CLI."""

    def test_render_js_is_importable(self):
        import render_js

        assert hasattr(render_js, "main")
        assert hasattr(render_js, "render_page")
        assert hasattr(render_js, "check_available")

    def test_main_function_exists(self):
        from render_js import main

        assert callable(main)
