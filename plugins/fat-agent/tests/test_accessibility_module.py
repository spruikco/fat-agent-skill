import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.accessibility import AccessibilityModule

# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_always_true():
    assert AccessibilityModule.detect("<html></html>") is True


def test_detect_always_true_empty():
    assert AccessibilityModule.detect("") is True


# ---------------------------------------------------------------------------
# analyse()
# ---------------------------------------------------------------------------


def test_analyse_img_alt_present():
    html = '<html><body><img src="a.jpg" alt="photo"><img src="b.jpg" alt=""></body></html>'
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert result["img_total"] == 2
    assert result["img_missing_alt"] == 0


def test_analyse_img_alt_missing():
    html = '<html><body><img src="a.jpg"><img src="b.jpg" alt="ok"></body></html>'
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert result["img_total"] == 2
    assert result["img_missing_alt"] == 1


def test_analyse_form_labels():
    html = (
        "<html><body><form>"
        '<input type="text" aria-label="Name">'
        '<input type="text">'
        '<input type="hidden" name="csrf">'
        "</form></body></html>"
    )
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert result["form_inputs_total"] == 2
    assert result["form_inputs_without_label"] == 1


def test_analyse_lang_attribute():
    html = '<html lang="en"><body></body></html>'
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert result["has_lang_attribute"] is True


def test_analyse_no_lang_attribute():
    html = "<html><body></body></html>"
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert result["has_lang_attribute"] is False


def test_analyse_landmarks():
    html = "<html><body><header></header><nav></nav><main></main><footer></footer></body></html>"
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert set(result["landmarks_found"]) == {"header", "nav", "main", "footer"}


def test_analyse_landmarks_via_roles():
    html = '<html><body><div role="banner"></div><div role="main"></div></body></html>'
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert "header" in result["landmarks_found"]
    assert "main" in result["landmarks_found"]


def test_analyse_skip_link():
    html = '<html><body><a href="#main-content">Skip to content</a><main id="main-content"></main></body></html>'
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert result["has_skip_link"] is True


def test_analyse_no_skip_link():
    html = "<html><body><main></main></body></html>"
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert result["has_skip_link"] is False


def test_analyse_heading_hierarchy():
    html = "<html><body><h1>Title</h1><h2>Sub</h2><h3>Detail</h3></body></html>"
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert result["heading_hierarchy"] == [1, 2, 3]


def test_analyse_empty_headings():
    html = "<html><body><h1>Good</h1><h2></h2><h3>  </h3></body></html>"
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert result["empty_headings"] == 2


def test_analyse_aria_roles():
    html = '<html><body><div role="alert">Warning</div><nav role="navigation"></nav></body></html>'
    mod = AccessibilityModule()
    result = mod.analyse(html)
    assert "alert" in result["aria_roles"]
    assert "navigation" in result["aria_roles"]


# ---------------------------------------------------------------------------
# score()
# ---------------------------------------------------------------------------


def test_score_perfect_accessibility():
    analysis = {
        "img_total": 2,
        "img_missing_alt": 0,
        "form_inputs_total": 0,
        "form_inputs_without_label": 0,
        "has_lang_attribute": True,
        "landmarks_found": ["main", "nav", "header", "footer"],
        "has_skip_link": True,
        "heading_hierarchy": [1, 2, 3],
        "empty_headings": 0,
        "aria_roles": [],
    }
    mod = AccessibilityModule()
    result = mod.score(analysis)
    assert result["total"] > 50
    assert len(mod.findings) == 0


def test_score_missing_everything():
    analysis = {
        "img_total": 3,
        "img_missing_alt": 3,
        "form_inputs_total": 2,
        "form_inputs_without_label": 2,
        "has_lang_attribute": False,
        "landmarks_found": [],
        "has_skip_link": False,
        "heading_hierarchy": [],
        "empty_headings": 2,
        "aria_roles": [],
    }
    mod = AccessibilityModule()
    result = mod.score(analysis)
    assert result["total"] < 20
    # missing alt is P1 (matches the core analyser), not a grade-capping P0
    priorities = [f["priority"] for f in mod.findings]
    assert "P1" in priorities
    assert "P2" in priorities
    assert "P0" not in priorities


def test_score_empty_headings_penalty():
    analysis = {
        "img_total": 0,
        "img_missing_alt": 0,
        "form_inputs_total": 0,
        "form_inputs_without_label": 0,
        "has_lang_attribute": True,
        "landmarks_found": ["main"],
        "has_skip_link": True,
        "heading_hierarchy": [1, 2],
        "empty_headings": 4,
        "aria_roles": [],
    }
    mod = AccessibilityModule()
    result = mod.score(analysis)
    assert result["details"]["heading_structure"]["score"] == 0
