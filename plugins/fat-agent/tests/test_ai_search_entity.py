"""Tests for the v3.6.0 ai_search additions: entity name extraction, Wikidata
presence, and llms.txt content validation (all findings-only)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules import ai_search as ai
from modules.ai_search import AISearchModule


# ---------------------------------------------------------------------------
# extract_entity_name
# ---------------------------------------------------------------------------


def test_entity_name_from_jsonld():
    html = (
        '<script type="application/ld+json">'
        '{"@type":"Organization","name":"Acme Widgets","url":"https://acme.com"}'
        "</script>"
    )
    assert ai.extract_entity_name(html) == "Acme Widgets"


def test_entity_name_from_og_site_name():
    html = '<meta property="og:site_name" content="Acme Widgets">'
    assert ai.extract_entity_name(html) == "Acme Widgets"


def test_entity_name_from_title_picks_brand_side():
    html = "<title>Best Blue Widgets For Sale | Acme</title>"
    assert ai.extract_entity_name(html) == "Acme"


def test_entity_name_empty_when_absent():
    assert ai.extract_entity_name("<html><body>hi</body></html>") == ""


# ---------------------------------------------------------------------------
# validate_llms_txt
# ---------------------------------------------------------------------------


def test_llms_absent():
    assert ai.validate_llms_txt("")["present"] is False


def test_llms_well_formed():
    content = (
        "# Acme\n\n> Acme makes widgets for makers everywhere.\n\n"
        "## Products\n- [Widgets](https://acme.com/widgets)\n"
        "- [Gadgets](https://acme.com/gadgets)\n- [Docs](https://acme.com/docs)\n"
    )
    v = ai.validate_llms_txt(content)
    assert v["present"] and v["has_title"] and v["well_formed"]
    assert v["link_count"] == 3
    assert v["section_count"] == 1


def test_llms_thin_not_well_formed():
    v = ai.validate_llms_txt("just some text with no heading and no links")
    assert v["present"] is True
    assert v["well_formed"] is False


# ---------------------------------------------------------------------------
# module wiring: llms validation finding
# ---------------------------------------------------------------------------


def _run(html, **kwargs):
    mod = AISearchModule()
    analysis = mod.analyse(html, url="", robots_txt="", **kwargs)
    mod.score(analysis)
    return analysis, mod


def test_thin_llms_produces_finding():
    _, mod = _run("<html></html>", llms_txt="some text only")
    assert any("llms.txt present but thin" in f["title"] for f in mod.findings)


def test_well_formed_llms_no_thin_finding():
    good = "# Acme\n\n## S\n- [a](x)\n- [b](y)\n- [c](z)\n"
    _, mod = _run("<html></html>", llms_txt=good)
    assert not any("thin" in f["title"] for f in mod.findings)


# ---------------------------------------------------------------------------
# module wiring: Wikidata presence finding (injected, no I/O)
# ---------------------------------------------------------------------------


def test_wikidata_missing_produces_finding():
    html = '<meta property="og:site_name" content="Totally Unknown Brand">'
    analysis, mod = _run(html, wikidata_hit=False)
    assert analysis["wikidata_entity"] is False
    assert any("No Wikidata entity" in f["title"] for f in mod.findings)


def test_wikidata_present_no_finding():
    html = '<meta property="og:site_name" content="Google">'
    _, mod = _run(html, wikidata_hit=True)
    assert not any("Wikidata" in f["title"] for f in mod.findings)


def test_wikidata_unknown_no_finding():
    # None == lookup didn't run / errored → never a false negative
    html = '<meta property="og:site_name" content="Acme">'
    analysis, mod = _run(html, wikidata_hit=None)
    assert analysis["wikidata_entity"] is None
    assert not any("Wikidata" in f["title"] for f in mod.findings)


def test_score_structure_unchanged():
    # The new signals must not add score buckets (calculate-score parity).
    _, mod = _run("<html></html>", llms_txt="", wikidata_hit=False)
    result = mod.score(
        mod.analyse("<html></html>", url="", robots_txt="", llms_txt="", wikidata_hit=False)
    )
    assert set(result["details"].keys()) == {
        "ai_crawler_access",
        "llms_txt",
        "extraction_readiness",
        "entity_clarity",
    }
    assert result["max"] == 100
