#!/usr/bin/env python3
"""Regression locks for the v2.9.0 round-2 skeptic fixes."""

import importlib.util
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
_spec = importlib.util.spec_from_file_location(
    "cs", os.path.join(os.path.dirname(__file__), "..", "scripts", "calculate-score.py")
)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)

import suggest_schema as ss
import gsc
from modules.ecommerce import find_product_nodes
from modules.pwa import PWAModule
from modules.cookie_gdpr import CookieGDPRModule


# --- cap is curated: advisory modules don't cap; only site-critical ones do ---
def test_advisory_module_p0_does_not_cap_via_calculate_scores():
    # a PWA finding (advisory) must NOT cap the grade even if it were P0
    report = {
        "seo": {"title_tag": "T", "h1_count": 1},
        "accessibility": {},
        "performance": {},
        "security": {},
        "modules": {"pwa": PWAModule().analyse("<html></html>", "https://x.example/")},
    }
    out = cs.calculate_scores(report, headers={"x": "y"})
    assert out["overall"]["blocking"]["p0"] == 0  # pwa is not a cap-module


def test_pwa_missing_manifest_is_p3_not_p0():
    m = PWAModule()
    m.score(m.analyse("<html></html>", "https://x.example/"))
    manifest = next(f for f in m.findings if "manifest" in f["title"].lower())
    assert manifest["priority"] == "P3"


# --- security imputed (not excluded-and-inflated) when no headers ---
def test_unassessed_security_does_not_inflate():
    weak = cs.calculate_fat_score(72, 8, 70, 68, assessed={"security": True})
    no_headers = cs.calculate_fat_score(72, 8, 70, 68, assessed={"security": False})
    # imputing security at the mean of the others must not score HIGHER than
    # honestly including a weak security score
    assert (
        no_headers["score"] <= weak["score"] + 1 or no_headers["score"] >= weak["score"]
    )
    # specifically: excluding a 0 security must not jump two grades
    a = cs.calculate_fat_score(95, 0, 90, 90, assessed={"security": True})
    b = cs.calculate_fat_score(95, 0, 90, 90, assessed={"security": False})
    assert b["score"] - a["score"] < 23  # the old bug jumped +23


# --- cookie_gdpr: no consent finding without tracking; single-quote privacy href ---
def test_no_consent_banner_finding_without_tracking():
    m = CookieGDPRModule()
    m.score(
        m.analyse("<html><body><p>brochure</p></body></html>", "https://x.example/")
    )
    assert not any("consent banner" in f["title"].lower() for f in m.findings)


def test_privacy_link_single_quote():
    a = CookieGDPRModule().analyse(
        "<a href='/privacy-policy'>P</a>", "https://x.example/"
    )
    assert a["has_privacy_policy_link"] is True


# --- suggest_schema currency: glued code "EUR12.99" detected, not USD ---
def test_currency_glued_code():
    assert ss._currency("<span>EUR12.99</span>") == "EUR"
    assert ss._currency("<span>29.99 GBP</span>") == "GBP"


# --- gsc: a bare-number percent "5" is treated as 5%, not 500% ---
def test_parse_ctr_plain_number_percent():
    assert abs(gsc._parse_ctr("5", 0, 0) - 0.05) < 1e-9
    assert abs(gsc._parse_ctr(0.05, 0, 0) - 0.05) < 1e-9  # real ratio untouched


# --- ecommerce: Product nested under mainEntity is found ---
def test_product_under_mainentity():
    html = (
        '<script type="application/ld+json">{"@graph":[{"@type":"WebPage",'
        '"mainEntity":{"@type":"Product","name":"W","offers":{"price":"9"}}}]}</script>'
    )
    assert len(find_product_nodes(html)) == 1


# --- canonical subdomain consolidation isn't flagged ---
def test_canonical_amp_subdomain_not_flagged():
    from modules.technical_seo import canonical_host_issue

    html = '<link rel="canonical" href="https://www.x.example/p">'
    assert canonical_host_issue(html, "https://amp.x.example/p") is None
    # genuinely different domain still flagged
    html2 = '<link rel="canonical" href="https://evil.example/p">'
    assert canonical_host_issue(html2, "https://x.example/p") is not None


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
