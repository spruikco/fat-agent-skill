import os
import sys

# add the scripts directory to sys.path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from pathlib import Path

from modules import CORE_MODULES, detect_modules

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_registry_returns_core_modules_for_basic_html():
    html = _read("basic.html")
    result = detect_modules(html)
    for mod in CORE_MODULES:
        assert mod in result, f"core module '{mod}' missing from result"
    assert "links" in result


def test_registry_detects_ecommerce():
    html = _read("ecommerce.html")
    result = detect_modules(html)
    assert "ecommerce" in result


def test_registry_detects_i18n():
    html = _read("i18n.html")
    result = detect_modules(html)
    assert "i18n" in result


def test_registry_detects_local_business():
    html = _read("local_business.html")
    result = detect_modules(html)
    assert "local_seo" in result


def test_registry_user_override_adds_module():
    html = _read("basic.html")
    result = detect_modules(html, force_enable=["dns"])
    assert "dns" in result


def test_registry_user_override_removes_module():
    html = _read("basic.html")
    result = detect_modules(html, force_disable=["seo"])
    assert "seo" not in result


def test_registry_site_type_local_enables_local_seo():
    html = _read("basic.html")
    result = detect_modules(html, site_type="local_business")
    assert "local_seo" in result


def test_registry_site_type_ecommerce_enables_ecommerce():
    html = _read("basic.html")
    result = detect_modules(html, site_type="ecommerce")
    assert "ecommerce" in result


def test_get_module_returns_class_for_all_detected():
    from modules import get_module

    html = _read("ecommerce.html")
    result = detect_modules(html)
    for mid in result:
        if mid not in CORE_MODULES:
            mod = get_module(mid)
            assert mod is not None, f"get_module('{mid}') returned None"


def test_get_module_returns_none_for_unknown():
    from modules import get_module

    assert get_module("nonexistent_module") is None
