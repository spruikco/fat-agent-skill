#!/usr/bin/env python3
"""Tests for the deeper merchant/PDP checks added to the ecommerce module."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.ecommerce import EcommerceModule

BARE_PDP = (
    '<script type="application/ld+json">{"@type":"Product","name":"Widget"}</script>'
    '<button class="add-to-cart">Add to cart</button><div class="product-price">$29</div>'
)
RICH_PDP = (
    '<script type="application/ld+json">{"@type":"Product","name":"Widget","sku":"W1",'
    '"gtin13":"0123456789012","offers":{"@type":"Offer","price":"29"}}</script>'
    '<button class="add-to-cart">Add</button>'
    "<a href='/shipping'>Shipping policy</a><a href='/returns'>Returns policy</a>"
    "<section>Related products</section>"
)


def titles(html):
    m = EcommerceModule()
    m.score(m.analyse(html, "https://shop.example/product/widget"))
    return [f["title"] for f in m.findings]


class TestMerchantDepth(unittest.TestCase):
    def test_bare_pdp_flags_gtin_shipping_return_related(self):
        t = titles(BARE_PDP)
        self.assertTrue(any("GTIN" in x for x in t))
        self.assertTrue(any("shipping" in x.lower() for x in t))
        self.assertTrue(any("return" in x.lower() for x in t))
        self.assertTrue(any("related" in x.lower() for x in t))

    def test_rich_pdp_clears_those_findings(self):
        t = titles(RICH_PDP)
        self.assertFalse(any("GTIN" in x for x in t))
        self.assertFalse(any("shipping" in x.lower() for x in t))
        self.assertFalse(any("return" in x.lower() for x in t))

    def test_out_of_stock_without_schema(self):
        html = BARE_PDP + "<p>Currently out of stock</p>"
        self.assertTrue(
            any(
                "out-of-stock" in x.lower() or "out of stock" in x.lower()
                for x in titles(html)
            )
        )

    def test_non_pdp_no_merchant_findings(self):
        # a plain content page should not trigger PDP merchant findings
        t = titles("<article><h1>Blog post</h1><p>hello</p></article>")
        self.assertFalse(any("GTIN" in x for x in t))


# a store's shared chrome: cart icon, prices and add-to-cart buttons on cards
SHOP_CHROME = (
    '<a class="cart-icon" href="/cart">Cart</a>'
    '<div class="card"><span class="price">$65</span>'
    '<button class="add-to-cart">Add to cart</button></div>'
)


def findings_at(html, url):
    m = EcommerceModule()
    analysis = m.analyse(html, url)
    m.score(analysis)
    return analysis, {f["title"]: f for f in m.findings}


class TestProductSchemaOnlyOnProductPages(unittest.TestCase):
    """txsports.com.au: "Missing Product structured data" (P1) was raised on
    the home page, landing pages, blog posts and checkout."""

    def test_not_raised_on_non_product_pages(self):
        for path in (
            "/",
            "/checkout",
            "/cart",
            "/blog/how-to-order",
            "/custom-soccer-uniforms",
        ):
            html = "<h1>Page</h1>" + (
                SHOP_CHROME if path != "/custom-soccer-uniforms" else ""
            )
            analysis, found = findings_at(html, "https://shop.example" + path)
            self.assertFalse(analysis["product_page"], path)
            self.assertNotIn("Missing Product structured data", found, path)

    def test_product_grid_on_landing_page_is_not_a_product_page(self):
        grid = SHOP_CHROME * 4
        analysis, found = findings_at(
            "<h1>Custom jerseys</h1>" + grid, "https://shop.example/custom-jerseys"
        )
        self.assertFalse(analysis["product_page"])
        self.assertNotIn("Missing Product structured data", found)

    def test_raised_on_product_pages(self):
        cases = (
            ("<h1>Jersey</h1>" + SHOP_CHROME, "/products/corio-fc-jersey"),
            ("<h1>Jersey</h1>" + SHOP_CHROME, "/product/corio-fc-jersey"),
            (
                '<meta property="og:type" content="product"><h1>Jersey</h1>',
                "/corio-fc-jersey",
            ),
            ("<h1>Jersey</h1>" + SHOP_CHROME, "/shop/corio-fc-jersey"),
        )
        for html, path in cases:
            analysis, found = findings_at(html, "https://shop.example" + path)
            self.assertTrue(analysis["product_page"], path)
            self.assertEqual(
                found["Missing Product structured data"]["priority"], "P1", path
            )


class TestMerchantListingEnhancements(unittest.TestCase):
    def test_missing_merchant_fields_listed(self):
        analysis, found = findings_at(RICH_PDP, "https://shop.example/product/widget")
        self.assertEqual(
            analysis["merchant_gaps"],
            [
                "image",
                "description",
                "offers.hasMerchantReturnPolicy",
                "offers.shippingDetails",
            ],
        )
        f = found["Merchant listing enhancements missing in Product schema"]
        self.assertEqual(f["priority"], "P2")

    def test_complete_product_has_no_gaps(self):
        html = (
            '<script type="application/ld+json">{"@type":"Product","name":"W",'
            '"image":"https://e.com/w.jpg","description":"A widget","sku":"W1",'
            '"offers":{"@type":"Offer","price":"29","priceCurrency":"AUD",'
            '"hasMerchantReturnPolicy":{"@type":"MerchantReturnPolicy"},'
            '"shippingDetails":{"@type":"OfferShippingDetails"}}}</script>'
        )
        analysis, found = findings_at(html, "https://shop.example/product/w")
        self.assertEqual(analysis["merchant_gaps"], [])
        self.assertNotIn(
            "Merchant listing enhancements missing in Product schema", found
        )

    def test_organisation_level_return_policy_counts(self):
        html = (
            '<script type="application/ld+json">{"@graph":['
            '{"@type":"Organization","name":"Shop","hasMerchantReturnPolicy":'
            '{"@type":"MerchantReturnPolicy"}},'
            '{"@type":"Product","name":"W","image":"x.jpg","description":"d",'
            '"offers":{"@type":"Offer","price":"1",'
            '"shippingDetails":{"@type":"OfferShippingDetails"}}}]}</script>'
        )
        analysis, _ = findings_at(html, "https://shop.example/product/w")
        self.assertEqual(analysis["merchant_gaps"], [])


if __name__ == "__main__":
    unittest.main()
