#!/usr/bin/env python3
"""Regression locks for v2.8.0 wrong-deliverable bug fixes."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import suggest_schema as ss
import gsc
from modules.ecommerce import find_product_nodes, EcommerceModule
from modules.schema_validator import SchemaValidatorModule


# --- suggest_schema: currency not inferred from a bare "$" ---
def test_currency_not_usd_from_dollar_sign():
    html = "<script>jQuery(function($){})</script><p>£29.99</p>"
    assert ss._currency(html) != "USD"


def test_currency_from_explicit_meta():
    assert (
        ss._currency('<meta property="product:price:currency" content="AUD">') == "AUD"
    )


# --- suggest_schema: a PDP with related-product cards is still a PDP ---
def test_pdp_with_related_cards_still_pdp():
    html = (
        '<meta property="og:type" content="product"><h1>Super Widget</h1>'
        "<button>Add to cart</button>"
        '<div class="product-card">A</div><div class="product-card">B</div>'
    )
    payload = ss.recommend(html, "https://shop.example/product/widget")
    assert "pdp" in payload["page_types"]
    assert any(r["type"] == "Product" for r in payload["recommendations"])


# --- suggest_schema: x.com substring no longer tags unrelated domains ---
def test_xcom_substring_not_tagged_as_twitter():
    sig = ss.gather_signals(
        '<a href="https://www.netflix.com/title/1">n</a>', "https://x.example/"
    )
    assert sig["socials"] == []


def test_real_x_com_is_tagged():
    sig = ss.gather_signals('<a href="https://x.com/acme">x</a>', "https://x.example/")
    assert "https://x.com/acme" in sig["socials"]


# --- suggest_schema: hyphenated brand not truncated ---
def test_hyphenated_brand_intact():
    assert (
        ss._title_brand("Mercedes-Benz of Sydney | Official")
        == "Mercedes-Benz of Sydney"
    )
    assert ss._title_brand("Acme Corp - Best Widgets") == "Acme Corp"


# --- ecommerce: Product in @graph / array / list-@type is detected ---
def test_product_in_graph_detected():
    html = '<script type="application/ld+json">{"@graph":[{"@type":"Product","name":"W","offers":{"price":"9"}}]}</script>'
    nodes = find_product_nodes(html)
    assert len(nodes) == 1
    a = EcommerceModule().analyse(html, "https://shop.example/product/w")
    assert a["product_schema"] and a["schema_valid"]


def test_product_list_type_detected():
    html = '<script type="application/ld+json">[{"@type":["Product","IndividualProduct"],"name":"W"}]</script>'
    assert EcommerceModule.detect(html) is True


# --- schema_validator: non-string @type doesn't crash; @context list ok ---
def test_non_string_type_no_crash():
    html = '<script type="application/ld+json">{"@context":"https://schema.org","@type":123}</script>'
    SchemaValidatorModule().analyse(html, "https://x.example/")  # must not raise


def test_context_as_list_recognised():
    html = '<script type="application/ld+json">{"@context":["https://schema.org",{"x":"y"}],"@type":"Organization","name":"A","url":"u"}</script>'
    a = SchemaValidatorModule().analyse(html, "https://x.example/")
    assert a["has_context"] is True


def test_yoast_graph_no_false_duplicate():
    html = (
        '<script type="application/ld+json">{"@context":"https://schema.org","@graph":['
        '{"@type":["WebPage","CollectionPage"],"name":"P"},'
        '{"@type":"ImageObject","url":"a.jpg"},{"@type":"ImageObject","url":"b.jpg"}]}</script>'
    )
    a = SchemaValidatorModule().analyse(html, "https://x.example/")
    assert a["no_duplicate_types"] is True  # two ImageObjects are legitimate
    assert a["known_types"] is True  # CollectionPage now recognised


# --- gsc: percent CTR string parses instead of crashing ---
def test_gsc_percent_ctr():
    rows = gsc.load_rows(
        [{"query": "x", "clicks": 5, "impressions": 100, "ctr": "4.2%"}]
    )
    assert abs(rows[0]["ctr"] - 0.042) < 1e-9


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
