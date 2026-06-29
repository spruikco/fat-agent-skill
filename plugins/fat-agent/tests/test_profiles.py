"""Tests for audit profiles system."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from profiles import PROFILES, resolve_profile


class TestProfiles:
    """Test profile definitions and resolution."""

    def test_quick_has_seo_and_security(self):
        modules = resolve_profile("quick")
        assert "seo" in modules
        assert "security" in modules

    def test_quick_has_links(self):
        modules = resolve_profile("quick")
        assert "links" in modules

    def test_quick_does_not_have_ecommerce(self):
        modules = resolve_profile("quick")
        assert "ecommerce" not in modules

    def test_full_has_at_least_16_modules(self):
        modules = resolve_profile("full")
        assert len(modules) >= 16

    def test_full_has_new_modules(self):
        modules = resolve_profile("full")
        for mod in [
            "content_quality",
            "cookie_gdpr",
            "pwa",
            "schema_validator",
            "sitemap",
        ]:
            assert mod in modules, f"full profile missing {mod}"

    def test_local_has_local_seo(self):
        modules = resolve_profile("local")
        assert "local_seo" in modules

    def test_local_has_content_quality_and_schema_validator(self):
        modules = resolve_profile("local")
        assert "content_quality" in modules
        assert "schema_validator" in modules

    def test_seo_has_content_quality_and_sitemap(self):
        modules = resolve_profile("seo")
        assert "content_quality" in modules
        assert "sitemap" in modules
        assert "schema_validator" in modules

    def test_unknown_name_falls_back_to_full(self):
        modules = resolve_profile("nonexistent_profile")
        assert modules == PROFILES["full"]

    def test_security_has_dns_infra_and_cookie_gdpr(self):
        modules = resolve_profile("security")
        assert "security" in modules
        assert "dns_infra" in modules
        assert "cookie_gdpr" in modules

    def test_ecommerce_profile_has_expected_modules(self):
        modules = resolve_profile("ecommerce")
        assert "seo" in modules
        assert "ecommerce" in modules
        assert "links" in modules
        assert "schema_validator" in modules

    def test_accessibility_profile(self):
        modules = resolve_profile("accessibility")
        assert "accessibility" in modules
        assert "performance" in modules
        assert len(modules) == 2

    def test_content_profile(self):
        modules = resolve_profile("content")
        assert "seo" in modules
        assert "content_quality" in modules
        assert "links" in modules
        assert "sitemap" in modules

    def test_all_profiles_are_lists(self):
        for name, modules in PROFILES.items():
            assert isinstance(modules, list), f"Profile '{name}' is not a list"

    def test_all_profile_modules_are_strings(self):
        for name, modules in PROFILES.items():
            for mod in modules:
                assert isinstance(mod, str), f"Module in '{name}' is not a string"

    def test_expected_profile_names_exist(self):
        expected = [
            "quick",
            "full",
            "seo",
            "security",
            "local",
            "ecommerce",
            "accessibility",
            "content",
        ]
        for name in expected:
            assert name in PROFILES, f"Profile '{name}' missing"
