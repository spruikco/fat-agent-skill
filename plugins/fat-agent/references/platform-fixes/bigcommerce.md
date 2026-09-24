# BigCommerce -- Platform Fix Reference

BigCommerce is a hosted commerce platform. As with Shopify you have no server
access, but you get more control than most hosted platforms: an editable
`robots.txt`, a redirects manager that can target products and categories
dynamically, configurable URL structures, a handful of security-header
settings, and full access to the **Stencil** theme (Handlebars templates,
SCSS and JavaScript).

Fixes happen in five places:

1. **Catalogue and content SEO fields** -- per product, category, brand and
   web page: page title, meta description, URL.
2. **Store settings** -- URL structure, `robots.txt`, redirects, security and
   privacy settings.
3. **Stencil theme** -- templates in `templates/` edited with the Stencil CLI
   (recommended) or the control panel's theme file editor.
4. **Script Manager** -- injects scripts into the header or footer of all
   pages or selected page types, without editing the theme.
5. **Apps** -- from the BigCommerce App Marketplace, which load their own
   scripts on the storefront.

This reference covers the most common FAT Agent findings on BigCommerce
stores using the default Cornerstone theme or a Stencil theme derived from
it. Control-panel menu names change periodically; where exact labels are
uncertain, the settings area is described.

---

## Titles and Meta Descriptions

### Where the fields live

| Page type | Where to edit |
|-----------|---------------|
| Home page | Store settings, website / SEO area (home page title and meta description) |
| Products | Product editor > **SEO** section (page title, meta description, product URL) |
| Categories | Category editor > SEO section |
| Brands | Brand editor > SEO section |
| Web pages | Page editor > SEO section |
| Blog posts | Post editor > SEO section |

If the page title is empty, BigCommerce uses the product or category name,
and templates may append the store name. If the meta description is empty,
the output depends on the theme, and it is often blank. FAT will flag both.

### Bulk editing

- The **product export / import** (CSV) includes page title and meta
  description columns. Export, fill gaps, re-import.
- The Catalog and Management APIs expose `page_title` and `meta_description`
  on products and categories for scripted bulk updates.

### Theme output

In Cornerstone, `templates/layout/base.html` outputs the title and meta tags:

```handlebars
<title>{{ head.title }}</title>
{{{ head.meta_tags }}}
{{{ head.config }}}
```

`head.meta_tags` contains the meta description and other platform-generated
tags. If a custom theme has replaced these with hard-coded values, restore
the platform variables.

---

## Canonicals, Duplicate URLs and Faceted Search

### Canonical tags

BigCommerce emits a canonical tag for storefront pages as part of its head
output. Check with view-source that each page has exactly **one** canonical
tag and that it uses the primary domain over HTTPS. A custom theme or SEO app
that adds its own canonical will create duplicates; remove the extra.

### Where duplicates come from

| Source | Example | Default handling |
|--------|---------|------------------|
| Faceted search (Product Filtering) | `/shirts/?Colour=Blue&_bc_fsnf=1` | Canonical to the category; parameter patterns typically disallowed in default robots.txt |
| Sorting | `/shirts/?sort=priceasc` | Canonical to the category |
| Pagination | `/shirts/?page=2` | Self-canonical per page |
| Product in multiple categories | Product URLs are category-independent by default | No duplication unless URL structure uses category paths |
| Search results | `/search.php?search_query=shirt` | Should be noindexed (below) |
| Compare, cart, account | `/compare/`, `/cart.php`, `/account.php` | Disallowed in default robots.txt |

### URL structure setting

BigCommerce lets you choose URL formats for products, categories, brands and
web pages in the store's **URL structure** settings: short, SEO-optimised
(including the category path), or a custom pattern. Changing the format on
a live store changes every URL, so:

1. Decide once, before launch if possible.
2. If you must change it, make sure the option to create 301 redirects for
   the old URLs is enabled when saving.
3. Crawl a sample of old URLs afterwards.

A short, category-independent product URL (`/blue-linen-shirt/`) avoids
duplicates when a product sits in several categories and survives category
reorganisations.

### Faceted search

Product Filtering (faceted search) creates a combinatorial number of
parameter URLs. The platform canonicalises them to the category, and the
default `robots.txt` blocks the filter marker parameter. If Search Console
still shows filter URLs being crawled heavily:

1. Confirm the default disallow rules are still in `robots.txt` (they may
   have been deleted during a custom edit).
2. Make sure filter links are not in the main navigation or sitemap.
3. If a specific filter combination deserves to rank ("Blue Linen Shirts"),
   create a real category for it with its own content instead of relying on a
   filter URL.

---

## robots.txt and noindex

### robots.txt

BigCommerce has an editable **robots.txt** in the store's website / SEO
settings. Edit it carefully: start from the default and add rules below it.

Example additions to the default file:

```text
User-agent: *
Disallow: /search.php
Disallow: /*?*sort=
Disallow: /*&sort=
Disallow: /*_bc_fsnf=1
Disallow: /compare
Disallow: /wishlist.php

Sitemap: https://www.example.com.au/xmlsitemap.php
```

Open the live `/robots.txt` first and check which of these are already
present; the default already covers several. Do not duplicate rules, and do
not remove defaults for `/cart.php`, `/checkout`, `/account.php` and
similar.

**Remember:** `Disallow` stops crawling, not indexing. To remove indexed
pages, noindex them first.

### noindex by page type (Stencil)

Stencil exposes a `page_type` variable in templates. Add this to the `<head>`
of `templates/layout/base.html`:

```handlebars
{{#if page_type '===' 'search'}}
    <meta name="robots" content="noindex, follow">
{{/if}}
{{#if page_type '===' 'compare'}}
    <meta name="robots" content="noindex, follow">
{{/if}}
{{#if page_type '===' 'account_orderstatus'}}
    <meta name="robots" content="noindex, nofollow">
{{/if}}
```

Check the `page_type` values in your theme (log `{{page_type}}` in a
development build with `stencil start`) as they are specific strings.

### noindex a single product or page

- **Products:** setting a product to not visible on the storefront removes it
  from the storefront and sitemap. For a product that should be reachable but
  not indexed, use a custom template (below).
- **Web pages:** hidden pages are not linked in navigation but may still be
  reachable. Use a custom template or delete them.

Custom template approach: copy `templates/pages/page.html` to
`templates/pages/custom/page/noindex-page.html`, add the robots meta tag in
its head block, then assign that template to the page in its settings.
Products and categories support custom templates the same way under
`templates/pages/custom/product/` and `templates/pages/custom/category/`.

---

## 301 Redirects

Found in the store's **301 Redirects** settings.

| Behaviour | Detail |
|-----------|--------|
| Status | 301 permanent |
| Target type | A manual URL, **or** a dynamic target (a specific product, category, brand or web page). Dynamic targets keep working if the destination's URL later changes. Prefer them. |
| Bulk | CSV import / export |
| Automatic | Changing a product or category URL can create a redirect automatically (check the setting when saving) |
| Patterns | No wildcard or regex rules; one row per path |
| Only fires on missing URLs | A redirect does not override a URL that currently resolves to a live item |
| Domain redirects | Primary domain, www / apex and HTTP to HTTPS are handled by the domain and SSL settings |

CSV import for a migration (check the column headers against an export from
your own store first, as the format has changed across versions):

```csv
Domain,Old Path,Manual URL/Path,Dynamic Target Type,Dynamic Target ID
www.example.com.au,/product/blue-linen-shirt/,,product,1234
www.example.com.au,/product-category/shirts/,,category,56
www.example.com.au,/about-us/,/about/,,
```

Verify after import:

```bash
curl -sIL https://www.example.com.au/product/blue-linen-shirt/ | grep -Ei '^(HTTP|location)'
```

---

## Sitemaps

BigCommerce generates an XML sitemap automatically at `/xmlsitemap.php`
(a sitemap index with child sitemaps for products, categories, brands and
pages).

- **Cannot** edit it directly.
- Products and categories set to not visible are excluded.
- Submit `https://www.example.com.au/xmlsitemap.php` in Search Console and
  reference it in `robots.txt`.
- Check that `/sitemap.xml` also resolves (some setups redirect it; if not,
  submit the `xmlsitemap.php` URL).

---

## Structured Data

### Product

Cornerstone includes Product structured data on product pages. Check with
Google's Rich Results Test for:

- A single Product entity (review apps and SEO apps often add a second one).
- `offers` with `price`, `priceCurrency` and `availability`.
- `gtin`, `mpn` or `sku` where you have them (fill in the product identifier
  fields in the catalogue).
- `aggregateRating` only if reviews are genuinely shown on the page.

If you need to write or replace Product JSON-LD in a custom theme, use the
Stencil `json` helper, which outputs a correctly quoted and escaped JSON
value:

```handlebars
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": {{{json product.title}}},
  "sku": {{{json product.sku}}},
  "url": {{{json product.url}}},
  {{#if product.main_image}}
  "image": "{{getImage product.main_image 'zoom_size'}}",
  {{/if}}
  "brand": {
    "@type": "Brand",
    "name": {{{json product.brand.name}}}
  },
  "offers": {
    "@type": "Offer",
    "url": {{{json product.url}}},
    "priceCurrency": {{{json currency_selector.active_currency_code}}},
    "price": {{{json product.price.without_tax.value}}},
    "availability": "https://schema.org/{{#if product.can_purchase}}InStock{{else}}OutOfStock{{/if}}"
  }
}
</script>
```

Front-matter in the template may need product fields enabled for all of these
values to be available. Test with `stencil start` and view the rendered
output before pushing. If the store sells products with tax-inclusive
display pricing (typical in Australia), use the price object that matches
what the customer sees.

### Organization

Add to `templates/layout/base.html`, output only on the home page:

```handlebars
{{#if page_type '===' 'default'}}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": {{{json settings.store_name}}},
  "url": {{{json urls.home}}},
  "logo": "https://www.example.com.au/content/logo.png",
  "sameAs": [
    "https://www.facebook.com/example",
    "https://www.instagram.com/example"
  ]
}
</script>
{{/if}}
```

For a retailer with a physical shop, use `Store` (a `LocalBusiness` subtype)
and add `address`, `telephone`, `openingHoursSpecification` and `geo`.

If you cannot or do not want to edit the theme, the same JSON-LD (with
hard-coded values) can be added through **Script Manager**, scoped to the
home page.

### BreadcrumbList

Cornerstone's breadcrumb component outputs BreadcrumbList markup. Confirm it
is present on product and category pages with the Rich Results Test. If a
custom theme removed it, the `breadcrumbs` array is available in templates:

```handlebars
{{#if breadcrumbs}}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{#each breadcrumbs}}
    {
      "@type": "ListItem",
      "position": {{add @index 1}},
      "name": {{{json name}}},
      "item": {{{json url}}}
    }{{#unless @last}},{{/unless}}
    {{/each}}
  ]
}
</script>
{{/if}}
```

### FAQ schema

Google retired FAQ rich results on 7 May 2026. Do not add `FAQPage` markup for
rich results. Keep product and category FAQ content as visible on-page text.

---

## Images: Alt Text, Size and Format

### Alt text

- **Product images:** each image in the product editor has a description
  field, which the theme outputs as alt text.
- **Category images** and **web page images** have their own alt or
  description fields.
- **Bulk:** product image descriptions are included in the product CSV.

Check the theme actually outputs the description as `alt`. In Cornerstone
product card and gallery templates, the image description is passed as the
alt value.

### Format, size and lazy loading

- BigCommerce's image CDN serves resized variants on request and supports
  modern formats. Use the `getImageSrcset` helper so templates request
  appropriate sizes:

  ```handlebars
  <img src="{{getImageSrcset image 1x=theme_settings.productgallery_size}}"
       srcset="{{getImageSrcset image use_default_sizes=true}}"
       sizes="(min-width: 800px) 50vw, 100vw"
       alt="{{image.alt}}"
       loading="lazy"
       width="500" height="500">
  ```

- Cornerstone uses the `lazysizes` library (`class="lazyload"` with
  `data-src` / `data-srcset`). Native `loading="lazy"` is a lighter option in
  custom themes.
- **Do not lazy load the main product image or the home page hero.** Remove
  the lazy class or use `loading="eager"` with `fetchpriority="high"` on the
  LCP image.
- Upload product images at around 1280 to 2048px on the long edge and
  compress first.

---

## Security Headers

BigCommerce controls most response headers, but the store's **security and
privacy** settings expose several header-related options:

- **HSTS** -- enable it and choose a max-age.
- **Frame options** -- control whether the storefront can be framed
  (`X-Frame-Options`).
- **Content Security Policy** -- current versions provide CSP controls
  (for example, an allowlist of script sources or a report-only mode). Start
  in report-only if available; apps and Script Manager scripts all need to
  be allowed.

Check the result:

```bash
curl -sI https://www.example.com.au | grep -Ei 'strict-transport|x-frame|content-security|x-content-type|referrer|permissions'
```

| Header | Status on BigCommerce | Workaround |
|--------|-----------------------|------------|
| `Strict-Transport-Security` | Setting in security settings | Enable it |
| `X-Frame-Options` | Setting in security settings | Set to same origin or deny |
| `Content-Security-Policy` | Settings on current versions | Configure carefully, report-only first |
| `X-Content-Type-Options` | Platform-controlled | None |
| `Referrer-Policy` | Not configurable as a header | `<meta name="referrer" content="strict-origin-when-cross-origin">` in `base.html` or Script Manager |
| `Permissions-Policy` | Not configurable | None |

**Cloudflare in front of BigCommerce:** BigCommerce already runs behind its
own CDN. Proxying the storefront domain through your own Cloudflare account
is not a supported standard setup and can break SSL and checkout. Keep DNS
records DNS-only unless BigCommerce support has confirmed a specific
configuration for the plan.

**How FAT should score this:** credit headers the merchant has enabled in
settings, flag disabled HSTS and frame options as fixable, and mark the
rest "platform-limited".

---

## Performance

1. **Apps.** Each storefront app adds scripts. Remove unused apps, and check
   Script Manager for scripts left behind after uninstalling.
2. **Script Manager scope.** Scope each script to the pages it needs
   (for example, a reviews widget only on product pages) and prefer footer
   placement with `defer`.
3. **Theme JavaScript.** Cornerstone bundles are split by page type; custom
   themes sometimes load everything everywhere. Build with
   `stencil bundle` and check bundle sizes.
4. **Faceted search.** Large numbers of facets with counts slow category
   pages. Show only the facets customers use.
5. **Product listing size.** Reduce products per page on category pages if
   they load heavy card images and swatches.
6. **Fonts.** Limit families and weights in the theme settings.
7. **Hero carousel.** The Cornerstone home page carousel is a common LCP
   issue. Use a single static hero, eager loaded.

Measure with PageSpeed Insights on mobile across the home page, a category
page and a product page.

---

## Search Console Verification

1. **Domain property via DNS TXT record** at your DNS provider (best: covers
   all subdomains and protocols).
2. **Meta tag** through Script Manager (header, all pages), or in
   `templates/layout/base.html`:

   ```html
   <meta name="google-site-verification" content="YOUR_CODE_HERE">
   ```

3. **Google-related channels and apps** can verify the domain as part of
   their setup.

HTML file upload verification to the web root is generally not possible;
use DNS or the meta tag.

---

## What You Can't Fix on BigCommerce

| Limitation | Detail |
|------------|--------|
| Checkout | Hosted and largely fixed (Optimized One-Page Checkout); limited template control. |
| Most response headers | Only the HSTS, frame and CSP settings. |
| Sitemap contents | Auto-generated at `/xmlsitemap.php`; exclusion only by visibility. |
| Redirect patterns | No wildcards or regex. |
| Faceted search parameters | Parameter names and structure are platform-defined. |
| Legacy PHP paths | `/cart.php`, `/login.php`, `/search.php` and similar are fixed. |
| Server response time | Platform-controlled. |
| Proxying | No supported standard way to put your own CDN in front. |
| Web root files | Limited; use WebDAV `content` folder for static files (served under `/content/`). |

---

## Quick Audit Checklist

| Check | How to Verify | Where to Fix | Priority |
|-------|---------------|--------------|----------|
| Store not in maintenance mode | Visit logged out | Store settings | P0 |
| One canonical per page, HTTPS primary domain | View source | Theme / SEO apps | P1 |
| Unique titles and descriptions | FAT crawl | Catalogue SEO fields / CSV | P1 |
| URL structure final, old URLs redirected | Crawl old URL list | URL structure + 301 Redirects | P0 (after change) |
| Redirects use dynamic targets | Review redirect list | 301 Redirects | P2 |
| robots.txt keeps defaults, blocks facets and search | Visit `/robots.txt` | robots.txt settings | P1 |
| Search results noindexed | View source on `/search.php` | `base.html` | P2 |
| Single Product JSON-LD block | View source | Theme / app settings | P1 |
| Organization / Store schema on home | Rich Results Test | `base.html` or Script Manager | P2 |
| BreadcrumbList present | Rich Results Test | Breadcrumb component | P3 |
| Product image descriptions filled | FAT image report | Product images / CSV | P2 |
| LCP image not lazy loaded | Inspect hero / main product image | Theme templates | P1 |
| Unused apps and Script Manager scripts removed | App list, Script Manager | Control panel | P2 |
| HSTS and frame options enabled | `curl -I` | Security settings | P1 |
| CSP configured (report-only first) | `curl -I` | Security settings | P3 |
| Search Console verified, sitemap submitted | GSC property | DNS / Script Manager | P1 |
| Referrer-Policy meta tag | View source | `base.html` / Script Manager | P3 |
