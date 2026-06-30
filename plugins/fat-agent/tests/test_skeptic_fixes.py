#!/usr/bin/env python3
"""Regression locks for the v2.8.0 skeptic fixes (false positives)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.content_depth import _YMYL_RE, _AD_RE
from modules.eeat import _has_article_context
from modules.ai_search import AISearchModule
from modules.crawlability import js_only_nav


# --- YMYL no longer prefix-matches innocent words ---
def test_ymyl_does_not_match_lawn_taxi_taxonomy():
    for s in [
        "Lawn Care Services",
        "Sydney Taxi Booking",
        "Taxonomy of Plants",
        "Drugstore Cowboy",
    ]:
        assert not _YMYL_RE.search(s), s


def test_ymyl_still_matches_real_ymyl():
    for s in [
        "Mortgage Loan Rates",
        "Health Insurance Guide",
        "Tax Return Help",
        "Lawyer in Sydney",
    ]:
        assert _YMYL_RE.search(s), s


# --- ad density no longer counts hero/cookie/announcement banners ---
def test_ad_regex_ignores_banner_and_sponsor():
    for s in ['class="hero-banner"', 'class="cookie-banner"', 'class="sponsor-logo"']:
        assert not _AD_RE.search(s), s
    assert _AD_RE.search('class="ad-slot"')
    assert _AD_RE.search("adsbygoogle")


# --- is_article needs a per-page signal, not a /blog/ link in the footer ---
def test_is_article_ignores_footer_blog_link():
    home = '<h1>Joe Plumbing</h1><footer><a href="/blog/">Blog</a></footer>'
    assert _has_article_context(home, "https://joe.example/") is False


def test_is_article_true_on_real_article_path():
    assert (
        _has_article_context("<h1>Post</h1>", "https://x.example/blog/my-post") is True
    )


# --- AI training-bot block is not a P1 (answer bots still are) ---
ROBOTS_TRAINING_ONLY = "User-agent: GPTBot\nDisallow: /\nUser-agent: CCBot\nDisallow: /\nUser-agent: *\nAllow: /\n"
ROBOTS_ANSWER_BLOCKED = "User-agent: PerplexityBot\nDisallow: /\n"


def test_blocking_training_bots_is_p3_not_p1():
    m = AISearchModule()
    m.score(
        m.analyse(
            "<html></html>",
            "https://x.example/",
            robots_txt=ROBOTS_TRAINING_ONLY,
            llms_txt="x",
        )
    )
    prios = {
        f["priority"]
        for f in m.findings
        if "training" in f["title"].lower() or "answer" in f["title"].lower()
    }
    assert "P1" not in prios  # training-only block must not be P1
    assert any(
        "training" in f["title"].lower() and f["priority"] == "P3" for f in m.findings
    )


def test_blocking_answer_bots_is_p1():
    m = AISearchModule()
    m.score(
        m.analyse(
            "<html></html>",
            "https://x.example/",
            robots_txt=ROBOTS_ANSWER_BLOCKED,
            llms_txt="x",
        )
    )
    assert any(
        "answer engines blocked" in f["title"].lower() and f["priority"] == "P1"
        for f in m.findings
    )


# --- js_only_nav ignores UI controls and anchor targets ---
def test_js_only_nav_ignores_toggles_and_anchor_targets():
    html = (
        '<a role="button" class="menu-toggle">Menu</a><a name="top"></a><a id="s1"></a>'
    )
    assert js_only_nav(html) == 0


def test_js_only_nav_still_flags_real_hrefless_links():
    html = "<a>Products</a><a>About</a><a>Services</a>"
    assert js_only_nav(html) == 3


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
