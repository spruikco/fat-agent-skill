#!/usr/bin/env python3
"""Tests for the v2.7.0 performance-calibration fixes.

Locks in: critical-CSS inlining isn't penalised, build-locked image format floors
at 5/20 with an architecture-framed finding, and the score is labelled a heuristic.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.performance import PerformanceModule


def _base(**over):
    a = {
        "html_size_kb": 20,
        "render_blocking_scripts": 0,
        "images_total": 0,
        "images_lazy_loaded": 0,
        "images_with_srcset": 0,
        "images_modern_format": 0,
        "picture_elements": 0,
        "inline_script_kb": 0,
        "inline_style_kb": 0,
        "has_preconnect": True,
        "has_preload": True,
    }
    a.update(over)
    return a


def test_critical_css_inlining_not_penalised():
    # 40KB inline CSS (critical CSS), tiny JS — should keep most inline points
    a = _base(inline_style_kb=40, inline_script_kb=2)
    res = PerformanceModule().score(a)
    assert (
        res["details"]["inline_assets"]["score"] >= 9
    )  # was 4 under the old single-bucket rule


def test_inline_css_does_not_trigger_finding():
    mod = PerformanceModule()
    mod.score(_base(inline_style_kb=50, inline_script_kb=5))
    assert not any("inline" in f["title"].lower() for f in mod.findings)


def test_large_inline_js_still_flagged():
    mod = PerformanceModule()
    mod.score(_base(inline_script_kb=45))
    js = [f for f in mod.findings if "inline javascript" in f["title"].lower()]
    assert len(js) == 1 and js[0]["priority"] == "P2"


def test_build_locked_images_floor_at_five():
    # images present, none modern/responsive -> 5/20 floor (was 3)
    res = PerformanceModule().score(_base(images_total=8))
    assert res["details"]["image_optimisation"]["score"] == 5


def test_image_format_finding_is_architecture_framed():
    mod = PerformanceModule()
    mod.score(_base(images_total=8))
    f = next(f for f in mod.findings if "next-gen" in f["title"].lower())
    assert f["priority"] == "P3"  # not a P1/P2 "quick win"
    assert f["effort"] == "high"  # architecture-level
    assert "build" in f["description"].lower()


def test_optimised_images_no_finding():
    mod = PerformanceModule()
    mod.score(_base(images_total=4, images_modern_format=4, images_with_srcset=4))
    assert not any("next-gen" in f["title"].lower() for f in mod.findings)


def test_score_labelled_as_heuristic():
    res = PerformanceModule().score(_base())
    assert res["measured"] is False
    assert res["method"] == "html-heuristic"
    assert "live" in res["note"].lower()


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
