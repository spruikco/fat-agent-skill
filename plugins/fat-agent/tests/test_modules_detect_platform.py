"""Shop detection uses platform fingerprints, not the words Shopify/WooCommerce."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules import detect_modules


def test_agency_copy_mentioning_shopify_is_not_a_shop():
    html = "<p>Web development (WordPress &amp; Shopify) and WooCommerce builds.</p>"
    assert "ecommerce" not in detect_modules(html)


def test_real_shopify_store_is_a_shop():
    html = '<link href="//cdn.shopify.com/s/files/1/theme.css"><script>Shopify.theme = {}</script>'
    assert "ecommerce" in detect_modules(html)


def test_real_woocommerce_store_is_a_shop():
    html = '<body class="woocommerce-page"><link href="/wp-content/plugins/woocommerce/assets/css/x.css">'
    assert "ecommerce" in detect_modules(html)
