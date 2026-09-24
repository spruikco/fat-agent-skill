# Shopify -- Platform Fix Reference

Shopify is a fully hosted commerce platform. You never touch the server: there
is no `.htaccess`, no `netlify.toml`, no access to response headers. What you
*can* change lives in four places:

1. **Admin fields** -- per-resource "Search engine listing" fields (title,
   description, URL handle), store-wide preferences, and the URL redirects
   manager.
2. **Theme code** -- Liquid templates (`layout/theme.liquid`, sections,
   snippets) edited via **Online Store > Themes > Edit code** or the Shopify
   CLI (`shopify theme dev` / `shopify theme push`).
3. **Metafields** -- including a small number of reserved SEO metafields that
   Shopify itself respects.
4. **Apps** -- which inject code through app embeds, app blocks, or (on older
   apps) script tags.

This reference covers the most common FAT Agent findings on Shopify stores and
tells you exactly where each one can be fixed, and where it cannot.

**Rule of thumb:** prefer theme code over apps for anything SEO-related. Every
app is another script on every page, and when the app is uninstalled its theme
code often stays behind.

---

## Titles and Meta Descriptions

### Where the fields live

| Page type | Where to edit |
|-----------|---------------|
| Home page | **Online Store > Preferences** (home page title and meta description) |
| Products | Product editor > **Search engine listing** > Edit |
| Collections | Collection editor > **Search engine listing** |
| Pages | Page editor > **Search engine listing** |
| Blog posts | Post editor > **Search engine listing** |
| Blogs (index) | Blog editor > **Search engine listing** |

If the SEO title is left empty, Shopify falls back to the resource title. If
the SEO description is left empty, Shopify falls back to a truncated chunk of
the description body, which is usually poor (it often starts with sizing info
or a promo line). FAT will flag these as weak or duplicated descriptions.

### Bulk editing

For stores with hundreds of products, do not edit one at a time:

- **Product CSV export/import** includes `SEO Title` and `SEO Description`
  columns. Export, fill the gaps in a spreadsheet, re-import with "Overwrite
  existing products" ticked.
- The **bulk editor** can show the SEO title and description columns for
  selected products.
- The values are stored as the reserved metafields `global.title_tag` and
  `global.description_tag`, so any metafield-aware bulk tool can write them.

### Theme output

The theme decides how the fields are rendered. Check `layout/theme.liquid`
contains something equivalent to this (most modern themes, including Dawn,
already do):

```liquid
<title>
  {{ page_title }}
  {%- if current_tags %}{% assign meta_tags = current_tags | join: ', ' %} | {{ 'general.meta.tags' | t: tags: meta_tags }}{% endif -%}
  {%- if current_page != 1 %} | Page {{ current_page }}{% endif -%}
  {%- unless page_title contains shop.name %} | {{ shop.name }}{% endunless -%}
</title>

{%- if page_description -%}
  <meta name="description" content="{{ page_description | escape }}">
{%- endif -%}
```

Why the extra conditions matter:

- **Pagination suffix** stops `/collections/shoes?page=2` having an identical
  title to page one.
- **Tag suffix** stops tag-filtered collection pages duplicating the parent
  collection's title.
- **Shop name guard** stops "Blue Shirt | Acme | Acme" when the merchant has
  already typed the brand into the SEO title.

Older or heavily customised themes sometimes hard-code the shop name into the
`<title>` or omit the meta description entirely. Fix it in `theme.liquid`,
not with an app.

---

## Canonicals and Duplicate / Faceted URLs

Shopify's URL model creates duplicates by design. The same product is
reachable at:

```text
/products/blue-shirt
/collections/shirts/products/blue-shirt
/collections/all/products/blue-shirt
/collections/sale/products/blue-shirt
/products/blue-shirt?variant=43210987654
```

Collections multiply through tags, sorting and storefront filtering:

```text
/collections/shirts/blue
/collections/shirts/blue+cotton
/collections/shirts?sort_by=price-ascending
/collections/shirts?filter.v.option.colour=Blue&filter.v.price.gte=20
```

### What Shopify does for you

The Liquid object `canonical_url` resolves to the canonical version of the
current page. For products reached through a collection path it returns
`/products/handle`; for sorted or filtered collection views it drops the
sort/filter parameters. As long as your theme outputs it, most duplication is
handled:

```liquid
<link rel="canonical" href="{{ canonical_url }}">
```

Check `theme.liquid` has exactly **one** canonical tag. Some SEO apps add a
second one, which gives Google conflicting signals.

### What you should still fix: internal links

Canonical tags are a hint, not a directive. If every internal link points at
the collection-scoped URL, Google crawls thousands of duplicates and may pick
its own canonical. Many themes build product-card links like this:

```liquid
{{ product.url | within: collection }}
```

Change product cards (usually `snippets/card-product.liquid` or
`snippets/product-card.liquid`) to link straight to the canonical URL:

```liquid
<a href="{{ card_product.url }}">
```

This is one of the highest-value Shopify fixes FAT can recommend. It reduces
crawl waste and consolidates link equity onto `/products/handle`.

### Tag pages and filter pages

- **Tag pages** (`/collections/shirts/blue`) canonicalise to themselves and are
  indexable. That is fine if the tags are meaningful ("Blue Shirts"), bad if
  they are internal merchandising tags ("sale-oct", "supplier-x"). Noindex the
  junk ones (see below) or stop linking to them.
- **Multi-tag combinations** (`blue+cotton`) are disallowed in Shopify's
  default `robots.txt`.
- **Storefront filter parameters** (`filter.v.*`, `filter.p.*`) are
  canonicalised back to the collection. If Search Console shows large numbers
  of "Crawled, currently not indexed" or "Duplicate, Google chose different
  canonical" filter URLs, add a disallow rule via `robots.txt.liquid`
  (next section).

### Variant URLs

`?variant=` URLs canonicalise to the base product. This is correct. Do not
fight it unless each variant genuinely needs its own landing page, in which
case split them into separate products.

---

## robots.txt and noindex

### Editing robots.txt

Shopify generates `/robots.txt` automatically. You can customise it by adding
a `robots.txt.liquid` template: **Edit code > Templates > Add a new template >
robots.txt**. Once that file exists, it fully controls the output, so always
start from the default groups and *add* to them rather than replacing them.

Complete, safe template that keeps every Shopify default and adds two extra
rules for the catch-all user agent:

```liquid
{%- comment -%}
  FAT Agent: keep Shopify's default rules, add custom disallows for '*'.
{%- endcomment -%}
{% for group in robots.default_groups %}
  {{- group.user_agent }}

  {%- for rule in group.rules -%}
    {{ rule }}
  {%- endfor -%}

  {%- if group.user_agent.value == '*' -%}
    {{ 'Disallow: /collections/*filter.*' }}
    {{ 'Disallow: /collections/vendors*' }}
  {%- endif -%}

  {%- if group.sitemap != blank -%}
    {{ group.sitemap }}
  {%- endif -%}
{% endfor %}
```

To add a separate group (for example, blocking a specific crawler):

```liquid
{% for group in robots.default_groups %}
  {{- group.user_agent }}
  {%- for rule in group.rules -%}
    {{ rule }}
  {%- endfor -%}
  {%- if group.sitemap != blank -%}
    {{ group.sitemap }}
  {%- endif -%}
{% endfor %}

User-agent: ExampleBot
Disallow: /
```

**Warnings:**

- Do not delete the default groups. They block `/cart`, `/checkout`,
  `/account`, internal search, preview parameters and several Shopify
  internals. Losing them causes real crawl problems.
- `robots.txt` stops crawling, not indexing. A URL that is already indexed and
  then disallowed can linger in results with no snippet. To remove pages from
  the index, noindex them first and only block crawling afterwards.

### Noindex a single resource (no code)

Shopify respects a reserved metafield: namespace `seo`, key `hidden`, type
integer, value `1`. When set on a product, collection, page or article,
Shopify adds `noindex` and removes it from `sitemap.xml`. Set it via a
metafield definition in **Settings > Custom data**, or with any bulk metafield
tool. This is the cleanest way to hide thank-you pages, wholesale-only
products, and internal landing pages.

### Noindex by template (theme code)

For whole classes of pages, add conditions to the `<head>` of
`theme.liquid`:

```liquid
{%- liquid
  assign noindex = false
  if template.name == 'search'
    assign noindex = true
  endif
  if template.name == 'collection' and current_tags
    assign noindex = true
  endif
  if request.path contains '/collections/vendors' or request.path contains '/collections/types'
    assign noindex = true
  endif
-%}
{%- if noindex -%}
  <meta name="robots" content="noindex, follow">
{%- endif -%}
```

Adjust the tag rule if the merchant's tags are genuinely useful landing
pages. Remove the `current_tags` condition in that case.

---

## 301 Redirects

### The URL redirects manager

Found under the online store navigation settings in the admin (**URL
redirects**). Every redirect created here is a permanent 301.

Key behaviours and limits:

| Behaviour | Detail |
|-----------|--------|
| Only fires on 404 | A redirect only triggers if the "from" path does **not** currently exist. You cannot redirect a live product or page; unpublish or delete it first. |
| No wildcards or regex | Every rule is an exact path. `/blog/*` style patterns are not supported. |
| CSV import | Bulk import with two columns: `Redirect from`, `Redirect to`. |
| Handle changes | When you change a product, collection, page or post URL handle, tick **Create a URL redirect** and Shopify adds the 301 for you. |
| Query strings | Treat the "from" path as path-only. Do not rely on query-string matching. |
| Domain redirects | Handled by **Settings > Domains**, not the redirects manager. |

CSV format for bulk migration (for example, moving off WooCommerce):

```csv
Redirect from,Redirect to
/product/blue-shirt/,/products/blue-shirt
/product-category/shirts/,/collections/shirts
/about-us/,/pages/about
/2023/05/summer-sale/,/blogs/news/summer-sale
```

### Migrations: generate the list, do not guess it

1. Crawl the old site (or export all URLs from its sitemap and analytics).
2. Map each URL to its Shopify equivalent in a spreadsheet.
3. Import via CSV.
4. After launch, crawl the old URL list against the new domain and confirm
   each one returns a single 301 to a 200 page (no chains).

```bash
# Check a redirect: expect one 301 then a 200
curl -sIL https://example.com/product/blue-shirt/ | grep -Ei '^(HTTP|location)'
```

### Domain-level redirects

In **Settings > Domains**, set the primary domain. Shopify automatically
301-redirects the `myshopify.com` domain, the other www/apex variant, and any
additional connected domains to the primary. HTTP to HTTPS is automatic.

---

## Sitemaps

Shopify generates `/sitemap.xml` automatically. It is a sitemap index that
links to child sitemaps for products, collections, pages and blogs. With
Shopify Markets using subfolders or separate domains, each market gets its own
sitemap and `hreflang` annotations are added to the pages.

What you can and cannot do:

- **Cannot** edit the XML, reorder it, or add custom URLs.
- **Can** exclude an individual resource with the `seo.hidden` metafield
  (above).
- Unpublished and password-protected content is excluded automatically.
- If the store is password-protected (pre-launch), nothing is crawlable.
  FAT will flag this; remove the password in **Online Store > Preferences**.

Submit `https://example.com/sitemap.xml` in Google Search Console after
verifying the property.

---

## Structured Data

### Product

Most Online Store 2.0 themes emit Product JSON-LD using the built-in
`structured_data` filter, which outputs a complete Product object (name,
images, description, offers per variant, price, currency, availability):

```liquid
<script type="application/ld+json">
  {{ product | structured_data }}
</script>
```

If your theme uses this, leave it alone. If it hand-rolls Product schema in
an older snippet, check with Google's Rich Results Test for missing `offers`,
`priceCurrency` or `availability`, which are common errors.

**Duplicate schema is the most common Shopify structured-data finding.** A
review app, an SEO app and the theme can all output their own Product block.
View source, search for `"@type": "Product"`, and keep exactly one. Disable
schema output in the apps (most have a toggle) rather than deleting theme
code. If a review app provides `aggregateRating`, prefer the app that merges
into the theme's Product object.

### Organization (or LocalBusiness)

Add to `theme.liquid`, inside the `<head>`, and only output it on the home
page:

```liquid
{%- if request.page_type == 'index' -%}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": {{ shop.name | json }},
  "url": {{ shop.url | json }},
  {%- if settings.logo != blank %}
  "logo": {{ settings.logo | image_url: width: 600 | prepend: 'https:' | json }},
  {%- endif %}
  "sameAs": [
    "https://www.instagram.com/example",
    "https://www.facebook.com/example"
  ],
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "customer service",
    "email": {{ shop.email | json }}
  }
}
</script>
{%- endif -%}
```

For a store with a physical shopfront, swap `"@type": "Organization"` for
`"Store"` (a `LocalBusiness` subtype) and add `address`, `telephone`,
`openingHoursSpecification` and `geo`. Use real, consistent NAP details that
match the Google Business Profile.

Note: `settings.logo` depends on the theme's setting name. Check
`config/settings_schema.json` if it renders empty.

### BreadcrumbList

Shopify has no native breadcrumb schema. Add a snippet
`snippets/breadcrumb-schema.liquid` and render it from product and collection
templates:

```liquid
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      "item": {{ shop.url | json }}
    }
    {%- if collection %},
    {
      "@type": "ListItem",
      "position": 2,
      "name": {{ collection.title | json }},
      "item": {{ shop.url | append: collection.url | json }}
    }
    {%- endif %}
    {%- if product %},
    {
      "@type": "ListItem",
      "position": {% if collection %}3{% else %}2{% endif %},
      "name": {{ product.title | json }},
      "item": {{ shop.url | append: product.url | json }}
    }
    {%- endif %}
  ]
}
</script>
```

Render it with `{% render 'breadcrumb-schema' %}` in `sections/main-product.liquid`
and `sections/main-collection-product-grid.liquid` (names vary by theme).

Always use the `json` filter for Liquid values inside JSON-LD. It escapes
quotes and special characters that would otherwise break the whole block.

### FAQ schema

Google retired FAQ rich results on 7 May 2026. Do not add `FAQPage` markup
expecting rich results, and do not install an app for it. Keep FAQ content on
the page as plain, well-structured HTML, which still helps users and AI
answer engines.

---

## Images: Alt Text, Size and Format

### Alt text

- Product images: in the product editor, click a media item > **Add alt
  text**.
- Collection images, blog featured images, and theme section images each
  have their own alt field.
- Bulk: product image alt text is included in the product CSV (`Image Alt
  Text` column).

FAT flags missing alt text per image. On product pages, a good pattern is
product name plus the distinguishing feature of that shot ("Blue linen shirt,
back view").

### Format and size

Shopify's CDN automatically serves WebP or AVIF to browsers that support
them. You do not need to convert uploads. What you *do* need is for the theme
to request sensibly sized images and set `srcset`/`sizes`. Use the
`image_url` and `image_tag` filters:

```liquid
{{
  product.featured_media
  | image_url: width: 1500
  | image_tag:
    widths: '360, 540, 720, 900, 1200, 1500',
    sizes: '(min-width: 990px) 50vw, 100vw',
    loading: 'lazy',
    alt: product.featured_media.alt
}}
```

For the **largest contentful paint image** (the hero or main product image
above the fold), do not lazy load it:

```liquid
{{
  section.settings.image
  | image_url: width: 2000
  | image_tag:
    widths: '750, 1100, 1500, 2000',
    sizes: '100vw',
    loading: 'eager',
    fetchpriority: 'high'
}}
```

`image_tag` also writes `width` and `height` attributes, which prevents layout
shift (CLS).

Uploads: keep source images under roughly 2 to 4 MB and no wider than about
4000px. Shopify resizes on the fly, but enormous originals still slow down
the admin and first-generation transforms.

---

## Security Headers

**You cannot set HTTP response headers on Shopify.** There is no headers
file, no edge function, and no Liquid method to modify them. Shopify sends
its own baseline on storefront responses (check with `curl -I`), typically
including HSTS, `X-Content-Type-Options` and frame-protection directives.
Treat whatever it sends as the ceiling.

```bash
curl -sI https://example.com | grep -Ei 'strict-transport|x-frame|content-security|x-content-type|referrer|permissions'
```

What you can do:

| Header | Status on Shopify | Workaround |
|--------|-------------------|------------|
| `Strict-Transport-Security` | Set by Shopify | None needed |
| `X-Content-Type-Options` | Set by Shopify | None needed |
| `X-Frame-Options` / `frame-ancestors` | Set by Shopify | None available |
| `Content-Security-Policy` | Minimal, platform-controlled | A `<meta http-equiv="Content-Security-Policy">` tag in `theme.liquid` is technically possible but will break apps, the theme editor and checkout-adjacent scripts. Not recommended. |
| `Referrer-Policy` | Often absent | `<meta name="referrer" content="strict-origin-when-cross-origin">` in `theme.liquid` works |
| `Permissions-Policy` | Not configurable | None |

**Cloudflare in front of Shopify is not a workaround.** Shopify already runs
behind its own CDN and does not support merchants proxying their storefront
domain through their own Cloudflare account (orange cloud). It commonly
breaks SSL provisioning and checkout. Keep Shopify DNS records set to DNS-only.

**How FAT should score this:** mark missing headers as "platform-limited"
rather than a merchant failure, and do not deduct for headers the merchant
has no way to set. Referrer-Policy via meta tag is the one fixable item.

---

## Performance

Shopify's servers and CDN are fast. Slow Shopify stores are almost always
slow because of the theme and apps.

### Apps and leftover code

1. List every installed app. For each, ask: is it still used, and does it
   load on every page?
2. Check **Online Store > Themes > Customise > App embeds** and turn off
   embeds for apps that do not need to run storefront-wide.
3. After uninstalling an app, search the theme code for its leftovers:
   snippets it added, `{% render %}` calls, and `<script>` tags in
   `theme.liquid`. Uninstalling does not always clean these up.
4. Prefer apps built on **theme app extensions** (app blocks and embeds)
   over ones that inject via legacy script tags. Extensions are removed
   cleanly when the app is uninstalled.

```bash
# With the Shopify CLI, pull the theme and look for stray app code
shopify theme pull --store your-store.myshopify.com
grep -rn "<script" layout/ snippets/ sections/ | grep -v "{{ 'global.js'"
```

### Theme-level fixes

- **Lazy load below-the-fold images** with `loading: 'lazy'` on `image_tag`
  (see Images). Keep the hero eager.
- **Defer scripts:** theme JavaScript should load with `defer`:

  ```liquid
  <script src="{{ 'global.js' | asset_url }}" defer="defer"></script>
  ```

- **Limit font weights** loaded through the theme settings. Each weight is a
  separate request.
- **Autoplay video sections** in the hero are a common LCP killer. Use a
  poster image and load the video on interaction.
- Run **Shopify Theme Check** (`shopify theme check`) which flags
  parser-blocking scripts, missing `width`/`height`, and oversized assets.

### Measuring

Use the web performance report in Shopify Analytics (real-user Core Web
Vitals) alongside PageSpeed Insights. Test a product page and a collection
page, not only the home page.

---

## Search Console Verification

Three options:

1. **Domain property via DNS (recommended).** Add the `google-site-verification`
   TXT record at your DNS provider. If the domain was bought through Shopify,
   add it in **Settings > Domains > [domain] > DNS settings**. Covers every
   subdomain and protocol.
2. **HTML meta tag.** Paste the tag in `layout/theme.liquid` inside `<head>`:

   ```liquid
   <meta name="google-site-verification" content="YOUR_CODE_HERE">
   ```

3. **Google & YouTube sales channel.** Connecting it can verify the domain as
   part of the Merchant Center setup.

HTML file upload verification is not possible (you cannot place arbitrary
files at the web root).

---

## What You Can't Fix on Shopify

Be upfront with the client about these. FAT should report them as
platform constraints, not as defects the merchant ignored.

| Limitation | Detail |
|------------|--------|
| URL prefixes | `/products/`, `/collections/`, `/pages/`, `/blogs/<blog>/` are fixed. You cannot have `/shirts/blue-shirt`. |
| Response headers | No custom security or caching headers (see above). |
| Sitemap contents | Auto-generated; only per-resource exclusion. |
| Checkout | Hosted by Shopify; its markup, scripts and headers are out of scope. |
| Collection-path duplicates | `/collections/x/products/y` always exists. Mitigate with canonicals and direct internal links. |
| Trailing slashes | Shopify URLs have no trailing slash; you cannot change this. |
| Redirect patterns | No wildcards, no regex, and no redirecting a URL that currently resolves. |
| Web root files | Cannot upload arbitrary files to `/` (for example `/ads.txt` needs an app or Shopify's own support, `/.well-known/` is platform-controlled). |
| Proxying | No supported way to put your own CDN or proxy in front. |
| Server response time | TTFB is Shopify's; you can only reduce Liquid complexity. |

---

## Quick Audit Checklist

| Check | How to Verify | Where to Fix | Priority |
|-------|---------------|--------------|----------|
| Store not password-protected | Visit home page logged out | Online Store > Preferences | P0 |
| One canonical tag per page | View source, search `rel="canonical"` | `theme.liquid`, SEO apps | P1 |
| Product cards link to `/products/handle` | Hover product links on a collection page | Product card snippet | P1 |
| Unique SEO title and description on key templates | FAT crawl, duplicate title report | Search engine listing fields / CSV | P1 |
| Single Product JSON-LD block | View source, count `"@type": "Product"` | Theme or app settings | P1 |
| Migration redirects in place | Crawl old URL list | URL redirects (CSV import) | P0 (after migration) |
| Hero image not lazy loaded | Inspect LCP element | Section Liquid (`loading: 'eager'`) | P1 |
| Product images have alt text | FAT image report | Product media alt / CSV | P2 |
| Organization / LocalBusiness schema on home | Rich Results Test | `theme.liquid` | P2 |
| BreadcrumbList schema | Rich Results Test | Breadcrumb snippet | P3 |
| Junk tag and search pages noindexed | View source on `/search`, tag URLs | `theme.liquid` robots meta | P2 |
| Unused apps removed, embeds trimmed | App list, App embeds panel | Apps / theme code | P2 |
| Referrer-Policy meta tag | View source | `theme.liquid` | P3 |
| Search Console verified, sitemap submitted | GSC property | DNS or `theme.liquid` | P1 |
| Security headers beyond Shopify baseline | `curl -I` | Not fixable (platform-limited) | Info |
