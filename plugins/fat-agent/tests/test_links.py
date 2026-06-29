import os
import sys

# add the scripts directory to sys.path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.links import LinksModule

# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------


def test_detect_true_for_any_html():
    """Links module is always enabled (ALWAYS_ENABLED=True)."""
    html = "<html><body><h1>Hello</h1></body></html>"
    assert LinksModule.detect(html) is True


def test_detect_true_for_empty_html():
    assert LinksModule.detect("") is True


# ---------------------------------------------------------------------------
# analyse() tests
# ---------------------------------------------------------------------------


def test_analyse_counts_links():
    html = """<html><body>
    <a href="/about">About</a>
    <a href="/contact">Contact</a>
    <a href="https://example.com">Example</a>
    </body></html>"""
    mod = LinksModule()
    result = mod.analyse(html, url="https://mysite.com")
    assert result["total_links"] == 3


def test_analyse_classifies_internal_vs_external():
    html = """<html><body>
    <a href="/about">About</a>
    <a href="https://mysite.com/page">Page</a>
    <a href="https://external.com">External</a>
    </body></html>"""
    mod = LinksModule()
    result = mod.analyse(html, url="https://mysite.com")
    assert result["internal_count"] == 2
    assert result["external_count"] == 1


def test_analyse_detects_empty_href():
    html = """<html><body>
    <a href="">Empty</a>
    <a href="#">hash only</a>
    <a href="/valid">Valid</a>
    </body></html>"""
    mod = LinksModule()
    result = mod.analyse(html, url="https://mysite.com")
    assert result["empty_hrefs"] == 2


def test_analyse_detects_broken_anchor():
    html = """<html><body>
    <a href="#section1">Go to section</a>
    <div id="section2">Section 2</div>
    </body></html>"""
    mod = LinksModule()
    result = mod.analyse(html, url="https://mysite.com")
    assert result["broken_anchors"] == ["#section1"]


def test_analyse_valid_anchor():
    html = """<html><body>
    <a href="#section1">Go to section</a>
    <div id="section1">Section 1</div>
    </body></html>"""
    mod = LinksModule()
    result = mod.analyse(html, url="https://mysite.com")
    assert result["broken_anchors"] == []


def test_analyse_detects_mailto():
    html = """<html><body>
    <a href="mailto:user@example.com">Email</a>
    <a href="mailto:invalid">Bad Email</a>
    </body></html>"""
    mod = LinksModule()
    result = mod.analyse(html, url="https://mysite.com")
    assert result["mailto_count"] == 2
    assert result["valid_mailto"] == ["mailto:user@example.com"]
    assert result["invalid_mailto"] == ["mailto:invalid"]


def test_analyse_detects_tel():
    html = """<html><body>
    <a href="tel:+441234567890">Call</a>
    </body></html>"""
    mod = LinksModule()
    result = mod.analyse(html, url="https://mysite.com")
    assert result["tel_count"] == 1


def test_analyse_checks_noopener_noreferrer():
    html = """<html><body>
    <a href="https://external.com" rel="noopener noreferrer">Safe</a>
    <a href="https://unsafe.com">Unsafe</a>
    <a href="/internal">Internal</a>
    </body></html>"""
    mod = LinksModule()
    result = mod.analyse(html, url="https://mysite.com")
    assert result["external_missing_noopener"] == 1
    assert result["external_count"] == 2


def test_analyse_noopener_only_counts():
    html = """<html><body>
    <a href="https://external.com" rel="noopener">has noopener only</a>
    </body></html>"""
    mod = LinksModule()
    result = mod.analyse(html, url="https://mysite.com")
    # missing noreferrer still counts as missing
    assert result["external_missing_noopener"] == 1


def test_analyse_no_links():
    html = "<html><body><p>No links here.</p></body></html>"
    mod = LinksModule()
    result = mod.analyse(html, url="https://mysite.com")
    assert result["total_links"] == 0
    assert result["internal_count"] == 0
    assert result["external_count"] == 0


def test_analyse_without_url_param():
    """Without url param, all absolute links are external, relative are internal."""
    html = """<html><body>
    <a href="/about">About</a>
    <a href="https://example.com">Example</a>
    </body></html>"""
    mod = LinksModule()
    result = mod.analyse(html)
    assert result["internal_count"] == 1
    assert result["external_count"] == 1


# ---------------------------------------------------------------------------
# score() tests
# ---------------------------------------------------------------------------


def test_score_perfect():
    analysis = {
        "total_links": 10,
        "internal_count": 5,
        "external_count": 5,
        "empty_hrefs": 0,
        "broken_anchors": [],
        "external_missing_noopener": 0,
        "mailto_count": 1,
        "valid_mailto": ["mailto:user@example.com"],
        "invalid_mailto": [],
        "tel_count": 0,
    }
    mod = LinksModule()
    result = mod.score(analysis)
    assert result["total"] == 100


def test_score_empty_hrefs_penalised():
    analysis = {
        "total_links": 5,
        "internal_count": 3,
        "external_count": 2,
        "empty_hrefs": 2,
        "broken_anchors": [],
        "external_missing_noopener": 0,
        "mailto_count": 1,
        "valid_mailto": ["mailto:user@example.com"],
        "invalid_mailto": [],
        "tel_count": 0,
    }
    mod = LinksModule()
    result = mod.score(analysis)
    assert result["no_empty_links"] == 0
    assert result["total"] == 80  # 100 - 20 for empty hrefs


def test_score_broken_anchors_penalised():
    analysis = {
        "total_links": 5,
        "internal_count": 3,
        "external_count": 2,
        "empty_hrefs": 0,
        "broken_anchors": ["#missing"],
        "external_missing_noopener": 0,
        "mailto_count": 1,
        "valid_mailto": ["mailto:user@example.com"],
        "invalid_mailto": [],
        "tel_count": 0,
    }
    mod = LinksModule()
    result = mod.score(analysis)
    assert result["no_broken_anchors"] == 0
    assert result["total"] == 80


def test_score_missing_noopener_penalised():
    analysis = {
        "total_links": 5,
        "internal_count": 3,
        "external_count": 2,
        "empty_hrefs": 0,
        "broken_anchors": [],
        "external_missing_noopener": 1,
        "mailto_count": 1,
        "valid_mailto": ["mailto:user@example.com"],
        "invalid_mailto": [],
        "tel_count": 0,
    }
    mod = LinksModule()
    result = mod.score(analysis)
    assert result["external_links_have_noopener"] == 0
    assert result["total"] == 85


def test_score_no_links_at_all():
    analysis = {
        "total_links": 0,
        "internal_count": 0,
        "external_count": 0,
        "empty_hrefs": 0,
        "broken_anchors": [],
        "external_missing_noopener": 0,
        "mailto_count": 0,
        "valid_mailto": [],
        "invalid_mailto": [],
        "tel_count": 0,
    }
    mod = LinksModule()
    result = mod.score(analysis)
    # no internal links (15), no external links (10), no reasonable count (10), no mailto (10)
    assert result["has_internal_links"] == 0
    assert result["has_external_links"] == 0
    assert result["reasonable_link_count"] == 0


def test_score_too_many_links():
    analysis = {
        "total_links": 250,
        "internal_count": 200,
        "external_count": 50,
        "empty_hrefs": 0,
        "broken_anchors": [],
        "external_missing_noopener": 0,
        "mailto_count": 1,
        "valid_mailto": ["mailto:user@example.com"],
        "invalid_mailto": [],
        "tel_count": 0,
    }
    mod = LinksModule()
    result = mod.score(analysis)
    assert result["reasonable_link_count"] == 0


def test_score_invalid_mailto_penalised():
    analysis = {
        "total_links": 5,
        "internal_count": 3,
        "external_count": 2,
        "empty_hrefs": 0,
        "broken_anchors": [],
        "external_missing_noopener": 0,
        "mailto_count": 1,
        "valid_mailto": [],
        "invalid_mailto": ["mailto:bad"],
        "tel_count": 0,
    }
    mod = LinksModule()
    result = mod.score(analysis)
    assert result["valid_mailto_format"] == 0


def test_score_generates_findings():
    analysis = {
        "total_links": 5,
        "internal_count": 0,
        "external_count": 5,
        "empty_hrefs": 2,
        "broken_anchors": ["#missing"],
        "external_missing_noopener": 3,
        "mailto_count": 1,
        "valid_mailto": [],
        "invalid_mailto": ["mailto:bad"],
        "tel_count": 0,
    }
    mod = LinksModule()
    mod.score(analysis)
    assert len(mod.findings) > 0
    titles = [f["title"] for f in mod.findings]
    assert any("empty" in t.lower() for t in titles)
    assert any("anchor" in t.lower() or "broken" in t.lower() for t in titles)
    assert any("noopener" in t.lower() or "rel" in t.lower() for t in titles)


# ---------------------------------------------------------------------------
# module metadata
# ---------------------------------------------------------------------------


def test_module_id():
    assert LinksModule.MODULE_ID == "links"


def test_display_name():
    assert LinksModule.DISPLAY_NAME == "Link Checker"


def test_always_enabled():
    assert LinksModule.ALWAYS_ENABLED is True
