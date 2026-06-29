import os
import sys

# add the scripts directory to sys.path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.ecommerce import EcommerceModule

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURE_DIR, name)) as f:
        return f.read()


# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------


def test_detect_true_for_product_schema():
    html = '<html><head><script type="application/ld+json">{"@type": "Product", "name": "Widget"}</script></head><body></body></html>'
    assert EcommerceModule.detect(html) is True


def test_detect_true_for_cart_element():
    html = '<html><body><div class="shopping-cart">Cart</div></body></html>'
    assert EcommerceModule.detect(html) is True


def test_detect_true_for_add_to_cart():
    html = '<html><body><button class="add-to-cart">Add</button></body></html>'
    assert EcommerceModule.detect(html) is True


def test_detect_false_for_plain_page():
    html = "<html><body><h1>About Us</h1><p>Welcome.</p></body></html>"
    assert EcommerceModule.detect(html) is False


def test_detect_true_for_fixture():
    html = _load_fixture("ecommerce.html")
    assert EcommerceModule.detect(html) is True


# ---------------------------------------------------------------------------
# analyse() tests using fixture
# ---------------------------------------------------------------------------


def test_analyse_detects_product_schema():
    html = _load_fixture("ecommerce.html")
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["product_schema"] is True


def test_analyse_flags_invalid_schema_missing_offers():
    """Fixture has Product schema without 'offers', so schema_valid should be False."""
    html = _load_fixture("ecommerce.html")
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["schema_valid"] is False


def test_analyse_valid_schema_with_offers():
    html = """<html><head><script type="application/ld+json">
    {"@type": "Product", "name": "Widget", "offers": {"@type": "Offer", "price": "29.99"}}
    </script></head><body></body></html>"""
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["product_schema"] is True
    assert result["schema_valid"] is True


def test_analyse_detects_cart():
    html = _load_fixture("ecommerce.html")
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["cart"] is True


def test_analyse_detects_price():
    html = _load_fixture("ecommerce.html")
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["price"] is True


def test_analyse_no_payment_badges_in_fixture():
    html = _load_fixture("ecommerce.html")
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["payment_badges"] is False


def test_analyse_detects_payment_badges():
    html = '<html><body><img alt="Pay with Visa"><img alt="Mastercard accepted"></body></html>'
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["payment_badges"] is True


def test_analyse_detects_stripe_badge():
    html = '<html><body><div class="stripe-badge">Powered by Stripe</div></body></html>'
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["payment_badges"] is True


def test_analyse_detects_klarna():
    html = '<html><body><img src="klarna-logo.png" alt="Klarna"></body></html>'
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["payment_badges"] is True


def test_analyse_no_breadcrumb_in_fixture():
    html = _load_fixture("ecommerce.html")
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["breadcrumb"] is False


def test_analyse_detects_breadcrumb_schema():
    html = '<html><head><script type="application/ld+json">{"@type": "BreadcrumbList"}</script></head><body></body></html>'
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["breadcrumb"] is True


def test_analyse_no_ssl_badge_in_fixture():
    html = _load_fixture("ecommerce.html")
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["ssl_badge"] is False


def test_analyse_detects_ssl_badge():
    html = '<html><body><img alt="SSL Secured" src="ssl-badge.png"></body></html>'
    mod = EcommerceModule()
    result = mod.analyse(html)
    assert result["ssl_badge"] is True


# ---------------------------------------------------------------------------
# score() tests
# ---------------------------------------------------------------------------


def test_score_perfect():
    analysis = {
        "product_schema": True,
        "schema_valid": True,
        "cart": True,
        "price": True,
        "breadcrumb": True,
        "payment_badges": True,
        "ssl_badge": True,
    }
    mod = EcommerceModule()
    result = mod.score(analysis)
    assert result["total"] == 100
    assert result["baseline"] == 10
    assert result["product_schema"] == 25
    assert result["schema_valid"] == 15
    assert result["cart"] == 15
    assert result["price"] == 10
    assert result["breadcrumb"] == 10
    assert result["payment_badges"] == 10
    assert result["ssl_badge"] == 5


def test_score_baseline_only():
    analysis = {
        "product_schema": False,
        "schema_valid": False,
        "cart": False,
        "price": False,
        "breadcrumb": False,
        "payment_badges": False,
        "ssl_badge": False,
    }
    mod = EcommerceModule()
    result = mod.score(analysis)
    assert result["total"] == 10
    assert result["baseline"] == 10


def test_score_fixture_html():
    """Fixture has product_schema (invalid), cart, price. No payment/breadcrumb/ssl."""
    analysis = {
        "product_schema": True,
        "schema_valid": False,
        "cart": True,
        "price": True,
        "breadcrumb": False,
        "payment_badges": False,
        "ssl_badge": False,
    }
    mod = EcommerceModule()
    result = mod.score(analysis)
    expected = 10 + 25 + 0 + 15 + 10 + 0 + 0 + 0
    assert result["total"] == expected


def test_score_generates_findings_for_missing_signals():
    analysis = {
        "product_schema": False,
        "schema_valid": False,
        "cart": False,
        "price": False,
        "breadcrumb": False,
        "payment_badges": False,
        "ssl_badge": False,
    }
    mod = EcommerceModule()
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert len(titles) > 0
    assert any("schema" in t.lower() or "product" in t.lower() for t in titles)
    assert any("cart" in t.lower() for t in titles)
    assert any("payment" in t.lower() or "trust" in t.lower() for t in titles)


def test_score_generates_finding_for_invalid_schema():
    analysis = {
        "product_schema": True,
        "schema_valid": False,
        "cart": True,
        "price": True,
        "breadcrumb": True,
        "payment_badges": True,
        "ssl_badge": True,
    }
    mod = EcommerceModule()
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any(
        "schema" in t.lower()
        and (
            "valid" in t.lower() or "incomplete" in t.lower() or "missing" in t.lower()
        )
        for t in titles
    )


# ---------------------------------------------------------------------------
# module metadata
# ---------------------------------------------------------------------------


def test_module_id():
    assert EcommerceModule.MODULE_ID == "ecommerce"


def test_display_name():
    assert EcommerceModule.DISPLAY_NAME == "E-commerce"
