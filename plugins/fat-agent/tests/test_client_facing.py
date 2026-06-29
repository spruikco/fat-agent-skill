"""Tests for client-facing text transformation utilities."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from client_facing import (
    CLIENT_FACING_MAP,
    transform_text,
    transform_finding,
    strip_code_blocks,
)


class TestTransformText:
    """Test jargon-to-plain-English text replacement."""

    def test_replaces_single_term(self):
        assert (
            transform_text("Missing HSTS header")
            == "Missing Browser security header header"
        )

    def test_replaces_multiple_terms(self):
        text = "Add SPF and DKIM records"
        result = transform_text(text)
        assert "email sender verification" in result
        assert "email signature verification" in result

    def test_leaves_unknown_terms_alone(self):
        text = "Something completely unrelated"
        assert transform_text(text) == text

    def test_replaces_priority_labels(self):
        assert "Urgent" in transform_text("P0 issue found")
        assert "Important" in transform_text("P1 severity")
        assert "Recommended" in transform_text("P2 priority")
        assert "Nice to Have" in transform_text("P3 impact")

    def test_custom_mapping(self):
        custom = {"foo": "bar"}
        assert transform_text("foo baz", mapping=custom) == "bar baz"

    def test_empty_string(self):
        assert transform_text("") == ""

    def test_all_map_entries_are_strings(self):
        for key, value in CLIENT_FACING_MAP.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_case_sensitive(self):
        # "HSTS" should match but "hsts" should not
        assert "Browser security header" in transform_text("HSTS is missing")
        assert transform_text("hsts is missing") == "hsts is missing"


class TestStripCodeBlocks:
    """Test removal of markdown code blocks and inline code."""

    def test_removes_fenced_code_block(self):
        text = "Do this:\n```\nsome code\n```\nDone."
        assert "some code" not in strip_code_blocks(text)
        assert "Do this:" in strip_code_blocks(text)
        assert "Done." in strip_code_blocks(text)

    def test_removes_fenced_code_block_with_language(self):
        text = "Example:\n```python\nprint('hi')\n```\nEnd."
        result = strip_code_blocks(text)
        assert "print" not in result
        assert "End." in result

    def test_removes_inline_code(self):
        text = "Set `max-age=31536000` in the header"
        result = strip_code_blocks(text)
        assert "`" not in result
        assert "max-age=31536000" not in result

    def test_empty_string(self):
        assert strip_code_blocks("") == ""

    def test_no_code_blocks(self):
        text = "Plain text with no code"
        assert strip_code_blocks(text) == text

    def test_multiple_code_blocks(self):
        text = "A\n```\nblock1\n```\nB\n```\nblock2\n```\nC"
        result = strip_code_blocks(text)
        assert "block1" not in result
        assert "block2" not in result
        assert "A" in result
        assert "B" in result
        assert "C" in result


class TestTransformFinding:
    """Test full finding dict transformation."""

    def test_transforms_priority(self):
        finding = {
            "priority": "P0",
            "title": "Missing HSTS header",
            "fix": "Add the header",
        }
        result = transform_finding(finding)
        assert result["priority"] == "Urgent"

    def test_transforms_title_jargon(self):
        finding = {
            "priority": "P2",
            "title": "No meta description found",
            "fix": "Add a meta description tag",
        }
        result = transform_finding(finding)
        assert "search result snippet text" in result["title"]

    def test_strips_code_from_fix(self):
        finding = {
            "priority": "P1",
            "title": "Issue",
            "fix": "Add this:\n```\nHeader set X-Frame-Options DENY\n```\nto your config",
        }
        result = transform_finding(finding)
        assert "```" not in result["fix"]
        assert "Header set" not in result["fix"]

    def test_adds_business_impact_field(self):
        finding = {
            "priority": "P0",
            "title": "Test",
            "fix": "Fix it",
        }
        result = transform_finding(finding)
        assert "business_impact" in result
        assert isinstance(result["business_impact"], str)
        assert len(result["business_impact"]) > 0

    def test_preserves_extra_fields(self):
        finding = {
            "priority": "P3",
            "title": "Minor",
            "fix": "Optional",
            "module": "seo",
        }
        result = transform_finding(finding)
        assert result["module"] == "seo"

    def test_handles_missing_fix_field(self):
        finding = {
            "priority": "P1",
            "title": "Something broken",
        }
        result = transform_finding(finding)
        assert "business_impact" in result

    def test_business_impact_varies_by_priority(self):
        critical = transform_finding({"priority": "P0", "title": "X", "fix": ""})
        low = transform_finding({"priority": "P3", "title": "X", "fix": ""})
        # different priorities should produce different business impact text
        assert critical["business_impact"] != low["business_impact"]
