# E-commerce Audit Checklist

## Product Structured Data (JSON-LD)

Every product page should include a `Product` schema with at minimum:

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Example Widget",
  "image": "https://example.com/widget.jpg",
  "description": "A high-quality widget for everyday use.",
  "sku": "WIDGET-001",
  "brand": {
    "@type": "Brand",
    "name": "WidgetCo"
  },
  "offers": {
    "@type": "Offer",
    "url": "https://example.com/widget",
    "priceCurrency": "GBP",
    "price": "29.99",
    "availability": "https://schema.org/InStock",
    "seller": {
      "@type": "Organization",
      "name": "Example Store"
    }
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.5",
    "reviewCount": "127"
  }
}
```

### Required properties for Google rich results

- `name`
- `offers` (with `price` and `priceCurrency`)
- `image` (at least one)

### Recommended properties

- `brand`
- `sku` or `gtin`
- `aggregateRating`
- `review`
- `description`
- `availability`

## Checkout UX Best Practices

1. **Guest checkout** -- do not force account creation before purchase.
2. **Progress indicator** -- show users where they are in the checkout flow (cart, shipping, payment, confirmation).
3. **Persistent cart summary** -- keep the order total visible throughout checkout.
4. **Input validation** -- validate fields inline as users type rather than on submit.
5. **Auto-fill support** -- use standard `autocomplete` attributes (`cc-name`, `cc-number`, `address-line1`, etc.).
6. **Mobile-first layout** -- stack form fields vertically, use large tap targets (minimum 44x44px).
7. **Error recovery** -- preserve entered data when validation fails; highlight the specific field.

## Payment Trust Signals

Display recognisable payment and security badges to build buyer confidence:

- **Card logos**: Visa, Mastercard, Amex, Discover
- **Payment providers**: PayPal, Stripe, Klarna, Afterpay, Apple Pay, Google Pay
- **Security badges**: SSL certificate seal, PCI DSS compliance, McAfee Secure, Norton Secured
- **Money-back guarantee** badge if applicable
- **Placement**: near the add-to-cart button and again near the payment form

### Implementation tips

- Use SVG logos at consistent sizing for crisp rendering.
- Keep badges above the fold on product and checkout pages.
- Link security badges to verifiable certificate pages where possible.

## Cart Abandonment Reduction

Common reasons for abandonment and mitigations:

| Reason | Mitigation |
|---|---|
| Unexpected shipping costs | Show shipping estimate early (product page or cart) |
| Forced account creation | Offer guest checkout |
| Complex checkout | Reduce to 3-4 steps maximum |
| Payment security concerns | Display trust badges prominently |
| Slow page load | Optimise checkout page performance (target < 2s LCP) |
| No return policy visible | Show return/refund policy link near checkout |

### Exit-intent strategies

- Trigger a modal with a discount code when cursor moves toward the browser chrome.
- Send abandoned cart email within 1 hour (requires email capture earlier in funnel).
- Use persistent cart that survives session expiry (localStorage or server-side).

## BreadcrumbList Schema

Helps search engines understand product category hierarchy:

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      "item": "https://example.com/"
    },
    {
      "@type": "ListItem",
      "position": 2,
      "name": "Widgets",
      "item": "https://example.com/widgets"
    },
    {
      "@type": "ListItem",
      "position": 3,
      "name": "Example Widget"
    }
  ]
}
```

## Price Display Guidelines

- Always show the currency symbol or code.
- Show original price with strikethrough alongside sale price.
- Use `<meta itemprop="price" content="29.99">` inside Product schema markup.
- Display VAT/tax status clearly (e.g. "inc. VAT" or "excl. VAT").
- For variable pricing, show the range ("From GBP 19.99").
