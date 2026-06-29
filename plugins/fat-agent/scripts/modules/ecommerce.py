"""E-commerce audit module.

Checks for Product structured data, cart elements, price displays,
payment trust signals, breadcrumb schema, and SSL badges.
"""

from __future__ import annotations

import json
import re

from modules import register_module
from modules.base import AuditModule

_PAYMENT_PATTERNS = [
    re.compile(r"visa", re.IGNORECASE),
    re.compile(r"mastercard", re.IGNORECASE),
    re.compile(r"paypal", re.IGNORECASE),
    re.compile(r"stripe", re.IGNORECASE),
    re.compile(r"klarna", re.IGNORECASE),
]

_CART_PATTERNS = [
    re.compile(r"add-to-cart", re.IGNORECASE),
    re.compile(r"shopping-cart", re.IGNORECASE),
    re.compile(r"cart-icon", re.IGNORECASE),
    re.compile(r"data-product-id", re.IGNORECASE),
]

_SSL_PATTERNS = [
    re.compile(r"ssl.secur", re.IGNORECASE),
    re.compile(r"ssl.badge", re.IGNORECASE),
    re.compile(r"secure.checkout", re.IGNORECASE),
    re.compile(r"ssl.cert", re.IGNORECASE),
]

_GTIN_RE = re.compile(r'"(?:gtin1[234]?|gtin8|mpn|sku|productID)"\s*:', re.IGNORECASE)
_SHIPPING_RE = re.compile(
    r"shipping (?:policy|info|cost|rate)|delivery (?:policy|info)|free shipping",
    re.IGNORECASE,
)
_RETURN_RE = re.compile(
    r"return(?:s)? policy|refund policy|returns? &|exchange policy|30[- ]day return",
    re.IGNORECASE,
)
_RELATED_RE = re.compile(
    r"related products|you may also like|recommended for you|customers also|similar items|frequently bought",
    re.IGNORECASE,
)
_OOS_RE = re.compile(r"out of stock|sold out|currently unavailable", re.IGNORECASE)


@register_module
class EcommerceModule(AuditModule):
    MODULE_ID = "ecommerce"
    DISPLAY_NAME = "E-commerce"

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------

    @classmethod
    def detect(cls, html: str) -> bool:
        """Return True when Product schema or cart elements are found."""
        if re.search(r'"@type"\s*:\s*"Product"', html, re.IGNORECASE):
            return True
        for pattern in _CART_PATTERNS:
            if pattern.search(html):
                return True
        return False

    # ------------------------------------------------------------------
    # analysis
    # ------------------------------------------------------------------

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        product_schema = bool(
            re.search(r'"@type"\s*:\s*"Product"', html, re.IGNORECASE)
        )
        schema_valid = self._validate_product_schema(html) if product_schema else False

        cart = any(p.search(html) for p in _CART_PATTERNS)
        price = bool(
            re.search(
                r"product.price|price.display|class=[\"'][^\"']*price",
                html,
                re.IGNORECASE,
            )
        )
        payment_badges = any(p.search(html) for p in _PAYMENT_PATTERNS)
        breadcrumb = bool(
            re.search(r'"@type"\s*:\s*"BreadcrumbList"', html, re.IGNORECASE)
        )
        ssl_badge = any(p.search(html) for p in _SSL_PATTERNS)

        oos = bool(_OOS_RE.search(html))
        return {
            "product_schema": product_schema,
            "schema_valid": schema_valid,
            "cart": cart,
            "price": price,
            "payment_badges": payment_badges,
            "breadcrumb": breadcrumb,
            "ssl_badge": ssl_badge,
            "is_pdp": product_schema
            or bool(re.search(r"add[- ]to[- ]cart", html, re.IGNORECASE)),
            "gtin": bool(_GTIN_RE.search(html)),
            "shipping_policy": bool(_SHIPPING_RE.search(html)),
            "return_policy": bool(_RETURN_RE.search(html)),
            "related_items": bool(_RELATED_RE.search(html)),
            "out_of_stock": oos,
            "oos_schema_ok": (not oos)
            or bool(re.search(r"outofstock", html, re.IGNORECASE)),
        }

    # ------------------------------------------------------------------
    # scoring
    # ------------------------------------------------------------------

    def score(self, analysis: dict) -> dict:
        baseline = 10
        product_schema = 25 if analysis.get("product_schema") else 0
        schema_valid = 15 if analysis.get("schema_valid") else 0
        cart = 15 if analysis.get("cart") else 0
        price = 10 if analysis.get("price") else 0
        breadcrumb = 10 if analysis.get("breadcrumb") else 0
        payment_badges = 10 if analysis.get("payment_badges") else 0
        ssl_badge = 5 if analysis.get("ssl_badge") else 0

        total = (
            baseline
            + product_schema
            + schema_valid
            + cart
            + price
            + breadcrumb
            + payment_badges
            + ssl_badge
        )

        # findings for missing signals
        if not analysis.get("product_schema"):
            self.add_finding(
                priority="P1",
                title="Missing Product structured data",
                description="No Product JSON-LD schema was found. Search engines use "
                "this to display rich product results with prices and reviews.",
                fix="Add a JSON-LD script with @type Product including name, offers, "
                "and image properties.",
                effort="medium",
            )

        if analysis.get("product_schema") and not analysis.get("schema_valid"):
            self.add_finding(
                priority="P2",
                title="Product schema is incomplete or missing offers",
                description="The Product schema was found but is missing required "
                "properties (name and offers). Google requires these for "
                "rich results eligibility.",
                fix="Add 'offers' with @type Offer including price and priceCurrency "
                "to your Product schema.",
                effort="low",
            )

        if not analysis.get("cart"):
            self.add_finding(
                priority="P2",
                title="No cart elements detected",
                description="No add-to-cart buttons or shopping cart elements were found. "
                "These are essential for e-commerce conversion.",
                fix="Ensure cart elements use semantic class names like add-to-cart "
                "or shopping-cart for accessibility and SEO.",
                effort="low",
            )

        if not analysis.get("payment_badges"):
            self.add_finding(
                priority="P2",
                title="No payment trust signals found",
                description="No payment provider badges (Visa, Mastercard, PayPal, "
                "Stripe, Klarna) were detected. Trust signals reduce cart "
                "abandonment.",
                fix="Add recognised payment provider logos near your checkout area.",
                effort="low",
            )

        if not analysis.get("breadcrumb"):
            self.add_finding(
                priority="P3",
                title="Missing BreadcrumbList schema",
                description="No BreadcrumbList structured data was found. Breadcrumbs "
                "help search engines understand site hierarchy and improve "
                "product page visibility.",
                fix="Add BreadcrumbList JSON-LD with itemListElement entries matching "
                "your navigation path.",
                effort="low",
            )

        if not analysis.get("ssl_badge"):
            self.add_finding(
                priority="P3",
                title="No SSL trust badge detected",
                description="No SSL or secure checkout badge was found. Displaying "
                "security indicators builds buyer confidence.",
                fix="Add a visible SSL/secure checkout badge near payment forms.",
                effort="low",
            )

        # --- deeper merchant/PDP checks (Hobo-parity) ---
        if analysis.get("is_pdp"):
            if analysis.get("product_schema") and not analysis.get("gtin"):
                self.add_finding(
                    priority="P2",
                    title="Product schema missing GTIN/MPN/SKU identifier",
                    description="No `gtin`/`mpn`/`sku` in the Product markup. Unique product "
                    "identifiers are required/strongly recommended for Merchant listings and help "
                    "Google match your product across the web.",
                    fix="Add `gtin` (or `mpn`) and `sku` to the Product schema.",
                    effort="low",
                )
            if not analysis.get("shipping_policy"):
                self.add_finding(
                    priority="P2",
                    title="No shipping information on the product page",
                    description="No shipping cost/policy detected. Shipping detail reduces cart "
                    "abandonment and is used for Merchant/free-listing eligibility.",
                    fix="Show shipping cost/time on the PDP and add `shippingDetails` to the Offer.",
                    effort="medium",
                )
            if not analysis.get("return_policy"):
                self.add_finding(
                    priority="P2",
                    title="No return/refund policy on the product page",
                    description="No return/refund policy detected. A clear returns policy is a trust "
                    "signal and a Merchant Center requirement.",
                    fix="Link a clear returns/refund policy and add `hasMerchantReturnPolicy` to the Offer.",
                    effort="medium",
                )
            if analysis.get("out_of_stock") and not analysis.get("oos_schema_ok"):
                self.add_finding(
                    priority="P2",
                    title="Out-of-stock product not marked in schema",
                    description="The page reads as out of stock, but the Offer doesn't declare "
                    "`availability: OutOfStock`. Mismatches cause Merchant disapprovals and poor UX.",
                    fix="Set `availability` to `https://schema.org/OutOfStock` (and 404/301 truly "
                    "retired products).",
                    effort="low",
                )
            if not analysis.get("related_items"):
                self.add_finding(
                    priority="P3",
                    title="No related/cross-sell product links",
                    description="No 'related products' / 'you may also like' links found. Related "
                    "links aid internal linking, crawl discovery, and average order value.",
                    fix="Add a related/recommended products block linking to relevant items.",
                    effort="low",
                )

        return {
            "total": total,
            "baseline": baseline,
            "product_schema": product_schema,
            "schema_valid": schema_valid,
            "cart": cart,
            "price": price,
            "breadcrumb": breadcrumb,
            "payment_badges": payment_badges,
            "ssl_badge": ssl_badge,
        }

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_product_schema(html: str) -> bool:
        """Check that Product JSON-LD has both name and offers."""
        for match in re.finditer(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE,
        ):
            try:
                data = json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                if data.get("name") and data.get("offers"):
                    return True
        return False
