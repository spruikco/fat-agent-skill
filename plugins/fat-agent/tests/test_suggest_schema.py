#!/usr/bin/env python3
"""Tests for scripts/suggest_schema.py — from-afar schema advisor."""

import io
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import suggest_schema as ss

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


LOCAL_HTML = """
<html><head>
<title>Joe's Plumbing | Sydney</title>
<meta property="og:site_name" content="Joe's Plumbing">
<meta name="description" content="24/7 emergency plumber in Sydney.">
</head><body>
<h1>Joe's Plumbing</h1>
<a href="tel:+61299990000">Call</a>
<a href="mailto:hi@joes.example">Email</a>
<a href="https://www.facebook.com/joesplumbing">fb</a>
<a href="https://instagram.com/joesplumbing">ig</a>
<iframe src="https://www.google.com/maps/embed?pb=x"></iframe>
</body></html>
"""

PDP_HTML = """
<html><head>
<title>Acme Widget</title>
<meta property="og:type" content="product">
<meta property="og:title" content="Acme Widget Pro">
<meta property="og:image" content="https://shop.example/w.jpg">
<meta property="product:price:amount" content="29.99">
<meta property="product:price:currency" content="AUD">
</head><body>
<h1>Acme Widget Pro</h1>
<button class="add-to-cart">Add to cart</button>
<span>In stock</span>
<div class="rating">4.6 stars from 212 reviews</div>
</body></html>
"""

PLP_HTML = """
<html><head><title>Shop</title></head><body>
<h1>All Products</h1>
<div class="product-card"><button class="add-to-cart">Add</button></div>
<div class="product-card"><button class="add-to-cart">Add</button></div>
<div class="product-card"><button class="add-to-cart">Add</button></div>
</body></html>
"""

FAQ_HTML = """
<html><head><title>Help</title></head><body>
<h2>Frequently Asked Questions</h2>
<details><summary>Do you ship overseas?</summary><p>Yes, worldwide.</p></details>
<details><summary>What is the return window?</summary><p>30 days.</p></details>
</body></html>
"""


class TestSignals(unittest.TestCase):
    def test_local_signals(self):
        sig = ss.gather_signals(LOCAL_HTML, "https://joes.example/contact")
        self.assertEqual(sig["name"], "Joe's Plumbing")
        self.assertEqual(sig["phone"], "+61299990000")
        self.assertEqual(sig["email"], "hi@joes.example")
        self.assertIn("https://www.facebook.com/joesplumbing", sig["socials"])
        self.assertIn("https://instagram.com/joesplumbing", sig["socials"])

    def test_product_signals(self):
        sig = ss.gather_signals(PDP_HTML, "https://shop.example/product/widget")
        self.assertEqual(sig["price"], "29.99")
        self.assertEqual(sig["currency"], "AUD")
        self.assertEqual(sig["availability"], "https://schema.org/InStock")
        self.assertIsNotNone(sig["rating"])
        self.assertEqual(sig["rating"][1], "212")  # review count


class TestClassify(unittest.TestCase):
    def test_local_contact(self):
        self.assertIn("local", ss.classify(LOCAL_HTML, "https://joes.example/contact"))
        self.assertIn(
            "contact", ss.classify(LOCAL_HTML, "https://joes.example/contact")
        )

    def test_pdp(self):
        self.assertIn(
            "pdp", ss.classify(PDP_HTML, "https://shop.example/product/widget")
        )

    def test_plp(self):
        self.assertIn("plp", ss.classify(PLP_HTML, "https://shop.example/shop"))

    def test_faq(self):
        self.assertIn("faq", ss.classify(FAQ_HTML, "https://x.example/help"))

    def test_home(self):
        self.assertIn(
            "home", ss.classify("<html><body>hi</body></html>", "https://x.example/")
        )


class TestRecommendLocal(unittest.TestCase):
    def setUp(self):
        self.payload = ss.recommend(LOCAL_HTML, "https://joes.example/contact")

    def test_recommends_localbusiness(self):
        types = [r["type"] for r in self.payload["recommendations"]]
        self.assertIn("LocalBusiness", types)

    def test_localbusiness_populated_from_scrape(self):
        lb = next(
            r for r in self.payload["recommendations"] if r["type"] == "LocalBusiness"
        )
        jl = lb["jsonld"]
        self.assertEqual(jl["name"], "Joe's Plumbing")
        self.assertEqual(jl["telephone"], "+61299990000")
        self.assertIn("https://www.facebook.com/joesplumbing", jl["sameAs"])
        # address street is unknown -> placeholder flagged in needs_input
        self.assertTrue(
            any(
                "street" in p.lower() or p.startswith("REPLACE")
                for p in [jl["address"]["streetAddress"]]
            )
        )

    def test_jsonld_is_valid_json(self):
        for rec in self.payload["recommendations"]:
            json.dumps(rec["jsonld"])  # must serialise


class TestRecommendEcommerce(unittest.TestCase):
    def test_pdp_product_with_offers(self):
        payload = ss.recommend(PDP_HTML, "https://shop.example/product/widget")
        prod = next(r for r in payload["recommendations"] if r["type"] == "Product")
        jl = prod["jsonld"]
        self.assertEqual(jl["offers"]["price"], "29.99")
        self.assertEqual(jl["offers"]["priceCurrency"], "AUD")
        self.assertEqual(jl["offers"]["availability"], "https://schema.org/InStock")
        self.assertIn("aggregateRating", jl)

    def test_merchant_listing_checklist(self):
        payload = ss.recommend(PDP_HTML, "https://shop.example/product/widget")
        ml = payload["merchant_listing"]
        self.assertTrue(ml["checks"]["price"])
        self.assertTrue(ml["checks"]["availability"])
        # product schema absent in fixture -> flagged missing
        self.assertIn("product_schema", ml["missing"])

    def test_existing_fixture_ecommerce(self):
        payload = ss.recommend(
            fixture("ecommerce.html"), "https://shop.example/product/widget"
        )
        self.assertIn("pdp", payload["page_types"])


class TestRecommendFaq(unittest.TestCase):
    def test_faqpage_built_from_details(self):
        payload = ss.recommend(FAQ_HTML, "https://x.example/help")
        faq = next(r for r in payload["recommendations"] if r["type"] == "FAQPage")
        questions = [q["name"] for q in faq["jsonld"]["mainEntity"]]
        self.assertIn("Do you ship overseas?", questions)
        self.assertEqual(
            faq["jsonld"]["mainEntity"][0]["acceptedAnswer"]["text"], "Yes, worldwide."
        )


class TestIncompleteExistingSchema(unittest.TestCase):
    def test_local_fixture_flags_incomplete(self):
        # fixture has LocalBusiness already -> status should be 'incomplete', still advised
        payload = ss.recommend(
            fixture("local_business.html"), "https://smiths.example/contact"
        )
        lb = next(r for r in payload["recommendations"] if r["type"] == "LocalBusiness")
        self.assertEqual(lb["status"], "incomplete")


class TestRendering(unittest.TestCase):
    def test_html_snippets(self):
        payload = ss.recommend(LOCAL_HTML, "https://joes.example/contact")
        html = ss.to_html_snippets(payload)
        self.assertIn('<script type="application/ld+json">', html)
        self.assertIn("LocalBusiness", html)


class TestCLI(unittest.TestCase):
    def test_stdin_json(self):
        buf = io.StringIO()
        with patch("sys.stdin", io.StringIO(LOCAL_HTML)), patch("sys.stdout", buf):
            ss.main(["--url", "https://joes.example/contact"])
        data = json.loads(buf.getvalue())
        self.assertIn("local", data["page_types"])

    def test_html_format(self):
        buf = io.StringIO()
        with patch("sys.stdin", io.StringIO(PDP_HTML)), patch("sys.stdout", buf):
            ss.main(["--url", "https://shop.example/product/x", "--format", "html"])
        self.assertIn("application/ld+json", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
