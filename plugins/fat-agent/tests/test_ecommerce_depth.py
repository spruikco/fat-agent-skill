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


if __name__ == "__main__":
    unittest.main()
