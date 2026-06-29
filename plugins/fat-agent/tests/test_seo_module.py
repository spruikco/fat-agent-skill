import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.seo import SEOModule

# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_always_true():
    assert SEOModule.detect("<html></html>") is True


def test_detect_always_true_empty():
    assert SEOModule.detect("") is True


# ---------------------------------------------------------------------------
# analyse()
# ---------------------------------------------------------------------------


def test_analyse_extracts_title():
    html = "<html><head><title>My Page Title</title></head><body></body></html>"
    mod = SEOModule()
    result = mod.analyse(html)
    assert result["title_tag"] == "My Page Title"
    assert result["title_length"] == 13


def test_analyse_missing_title():
    html = "<html><head></head><body></body></html>"
    mod = SEOModule()
    result = mod.analyse(html)
    assert result["title_tag"] == ""
    assert result["title_length"] == 0


def test_analyse_extracts_meta_description():
    html = '<html><head><meta name="description" content="A short description"></head><body></body></html>'
    mod = SEOModule()
    result = mod.analyse(html)
    assert result["meta_description"] == "A short description"
    assert result["meta_description_length"] == 19


def test_analyse_reverse_meta_attr_order():
    html = '<html><head><meta content="Reversed order" name="description"></head><body></body></html>'
    mod = SEOModule()
    result = mod.analyse(html)
    assert result["meta_description"] == "Reversed order"


def test_analyse_h1_count():
    html = "<html><body><h1>First</h1><h1>Second</h1></body></html>"
    mod = SEOModule()
    result = mod.analyse(html)
    assert result["h1_count"] == 2


def test_analyse_canonical():
    html = '<html><head><link rel="canonical" href="https://example.com/"></head><body></body></html>'
    mod = SEOModule()
    result = mod.analyse(html)
    assert result["has_canonical"] is True


def test_analyse_no_canonical():
    html = "<html><head></head><body></body></html>"
    mod = SEOModule()
    result = mod.analyse(html)
    assert result["has_canonical"] is False


def test_analyse_og_tags():
    html = (
        "<html><head>"
        '<meta property="og:title" content="OG Title">'
        '<meta property="og:image" content="https://example.com/img.jpg">'
        "</head><body></body></html>"
    )
    mod = SEOModule()
    result = mod.analyse(html)
    assert result["og_tags"]["og:title"] == "OG Title"
    assert "og:image" in result["og_tags"]


def test_analyse_robots_meta():
    html = '<html><head><meta name="robots" content="noindex, nofollow"></head><body></body></html>'
    mod = SEOModule()
    result = mod.analyse(html)
    assert result["has_robots_meta"] is True
    assert "noindex" in result["robots_content"]


def test_analyse_json_ld():
    html = (
        "<html><head>"
        '<script type="application/ld+json">{"@type": "Organization"}</script>'
        '<script type="application/ld+json">{"@type": "WebPage"}</script>'
        "</head><body></body></html>"
    )
    mod = SEOModule()
    result = mod.analyse(html)
    assert result["json_ld_count"] == 2


# ---------------------------------------------------------------------------
# score()
# ---------------------------------------------------------------------------


def test_score_perfect_seo():
    analysis = {
        "title_tag": "A Good Title That Is Between Fifty And Sixty Chars!",
        "title_length": 52,
        "meta_description": "x" * 155,
        "meta_description_length": 155,
        "h1_count": 1,
        "has_canonical": True,
        "og_tags": {
            "og:title": "t",
            "og:description": "d",
            "og:image": "i",
            "og:url": "u",
        },
        "has_robots_meta": False,
        "robots_content": "",
        "json_ld_count": 2,
    }
    mod = SEOModule()
    result = mod.score(analysis)
    assert result["total"] > 50
    assert len(mod.findings) == 0


def test_score_missing_everything():
    analysis = {
        "title_tag": "",
        "title_length": 0,
        "meta_description": "",
        "meta_description_length": 0,
        "h1_count": 0,
        "has_canonical": False,
        "og_tags": {},
        "has_robots_meta": False,
        "robots_content": "",
        "json_ld_count": 0,
    }
    mod = SEOModule()
    result = mod.score(analysis)
    assert result["total"] < 20
    priorities = [f["priority"] for f in mod.findings]
    assert "P0" in priorities
    assert "P1" in priorities


def test_score_noindex_triggers_p0():
    analysis = {
        "title_tag": "Test",
        "title_length": 4,
        "meta_description": "desc",
        "meta_description_length": 4,
        "h1_count": 1,
        "has_canonical": True,
        "og_tags": {},
        "has_robots_meta": True,
        "robots_content": "noindex",
        "json_ld_count": 0,
    }
    mod = SEOModule()
    mod.score(analysis)
    noindex_findings = [f for f in mod.findings if "noindex" in f["title"].lower()]
    assert len(noindex_findings) == 1
    assert noindex_findings[0]["priority"] == "P0"
