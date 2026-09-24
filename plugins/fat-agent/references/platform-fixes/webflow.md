# Webflow -- Platform Fix Reference

Webflow is a visual site builder with its own hosting and CMS. Compared with
Wix and Squarespace it gives you considerably more SEO control: an editable
`robots.txt`, a proper 301 redirect manager with pattern support, per-page
and CMS-template SEO fields bound to CMS data, and custom code in the head of
every page. What it does not give you on standard hosting is control over
HTTP response headers.

Fixes happen in four places:

1. **Page settings** -- title, meta description, Open Graph, slug, sitemap
   indexing, and page-level custom code (head and before `</body>`).
2. **CMS Collection template pages** -- the same fields, but bound to CMS
   fields so every item gets unique values.
3. **Site settings** -- the SEO tab (robots.txt, sitemap, global canonical,
   site verification), the publishing / hosting tab (301 redirects, advanced
   publishing options), and site-wide custom code.
4. **The Designer** -- image alt text, lazy loading, heading structure, and
   the embeds you add.

Custom code (site-wide and page-level) requires a paid site plan. Check the
plan before recommending any code-based fix.

This reference covers the most common FAT Agent findings on Webflow sites.
Webflow reorganises its settings screens periodically; where exact labels are
uncertain, the settings area is described.

---

## Titles and Meta Descriptions

### Static pages

Open the **Pages** panel, click the gear icon on a page, and fill in:

- **Title tag**
- **Meta description**
- **Open Graph** title, description and image (can inherit from SEO fields)

If the title tag is empty, Webflow falls back to the page name, which is
often something like "Home" or "About". FAT will flag these.

### CMS template pages

Every CMS Collection has a template page. Its SEO settings accept CMS fields
as variables, inserted with the field picker. A good pattern:

```text
Title tag:         {Name} | Acme Consulting
Meta description:  {Summary}
```

Better still, add dedicated **SEO Title** and **Meta Description** plain-text
fields to the collection and bind those, falling back to Name/Summary only
where empty. That lets editors write proper titles for important items
without changing the item's heading.

Recommended collection fields for SEO:

| Field | Type | Purpose |
|-------|------|---------|
| SEO Title | Plain text (max 60) | Bound to title tag |
| Meta Description | Plain text (max 160) | Bound to meta description |
| Robots | Plain text | Set to `noindex, follow` on items to hide; output in a robots meta tag (below) |
| Canonical URL | Link | Optional override for syndicated items |
| Main Image Alt | Plain text | Alt text for the main image |

---

## Canonicals and Duplicate URLs

### Global canonical

In the site settings **SEO** tab, set the **global canonical tag URL** to the
preferred origin (for example `https://www.example.com.au`). Webflow then
outputs a self-referencing canonical on every page using that origin. Without
it, some Webflow sites output no canonical at all, and FAT will flag every
page.

Also set a **default domain** in the publishing settings so the other
www/apex variant and the `webflow.io` staging domain redirect to it.

### Per-page and per-item canonical

Webflow pages have a canonical field in their SEO settings on current
versions. For CMS items that need a canonical pointing elsewhere (syndicated
articles, for example), use a Link field and output it in the template's
head custom code:

```html
<link rel="canonical" href="{{Canonical URL}}">
```

Here `{{Canonical URL}}` stands for the CMS field inserted with the field
picker (it appears as a purple token in the editor). **Only do this if the
global canonical is not also emitting one for the template**, otherwise the
page will carry two canonical tags. If both would appear, leave the global
canonical in charge and do not override.

### Duplicate sources on Webflow

| Source | Example | Fix |
|--------|---------|-----|
| Staging domain | `acme.webflow.io` indexed | Disable indexing of the Webflow subdomain in the SEO settings |
| Collection list pagination | `/blog?a1b2c3d4_page=2` | Canonical handles it; keep the first page strong. Consider "Load more" instead of numbered pagination for small lists |
| Utility pages | `/search`, password pages | Exclude from sitemap and noindex |
| Unused CMS templates | A collection used only for data, whose template pages are still live | Exclude from sitemap and noindex the template, or turn off the template pages if the collection supports it |
| Category collections with thin pages | `/category/news` with one post | Noindex or merge |

---

## robots.txt and noindex

### robots.txt

Webflow gives you a fully editable `robots.txt` field in the site settings
**SEO** tab. Whatever you type is served at `/robots.txt`.

A complete, sensible default for a typical Webflow marketing site:

```text
User-agent: *
Disallow: /search
Disallow: /*?*_page=
Disallow: /401
Disallow: /404

Sitemap: https://www.example.com.au/sitemap.xml
```

Notes:

- Leave the field empty and Webflow serves a permissive default.
- `robots.txt` only stops crawling, not indexing. Noindex pages you want out
  of the index, and let them be crawled until they drop out.
- The `webflow.io` staging subdomain has its own indexing toggle. Make sure it
  is set to not be indexed.

### noindex a static page

Add a robots meta tag in the page's custom code **head** section:

```html
<meta name="robots" content="noindex, follow">
```

Then turn off **sitemap indexing** for that page in its settings so it is also
removed from the sitemap.

### Conditional noindex on CMS items

Add a **Plain text** field called `Robots` to the collection. Set it to
`noindex, follow` on items you want hidden and leave it empty on the rest. In
the template page's head custom code:

```html
<meta name="robots" content="{{Robots}}">
```

An empty `content` attribute is ignored by search engines, so indexable items
are unaffected. Head custom code cannot use conditional visibility, which is
why the value is stored as text rather than driven by a switch field.

---

## 301 Redirects

Found in the site settings **publishing / hosting** area under **301
redirects**.

Single redirect:

```text
Old path:        /about-us
Redirect to:     /about
```

Pattern redirect using a capture group, which Webflow supports:

```text
Old path:        /blog/(.*)
Redirect to:     /insights/%1
```

`(.*)` captures the remainder of the path and `%1` inserts it. Multiple groups
map to `%1`, `%2` and so on.

Migration examples from WordPress:

```text
/(\d{4})/(\d{2})/(.*)        ->  /insights/%3
/category/(.*)               ->  /insights/category/%1
/services/(.*)/              ->  /services/%1
```

Rules and limits:

| Behaviour | Detail |
|-----------|--------|
| Status | 301 permanent |
| Applies when | Redirects take effect after publishing |
| Patterns | Regex-style capture groups with `%1` substitution |
| Trailing slashes | Webflow URLs have no trailing slash; old WordPress URLs usually do, so test both forms |
| Bulk import | Available on current versions via CSV; otherwise add rules one by one |
| Order | Specific rules before broad pattern rules |
| Domain redirects | Set the default domain; Webflow redirects other connected domains and HTTP to HTTPS automatically |

**Gotcha:** a live page at the old path takes precedence in practice. Delete
or move the old page before relying on a redirect from its path.

```bash
curl -sIL https://www.example.com.au/2023/05/old-post/ | grep -Ei '^(HTTP|location)'
```

---

## Sitemaps

In the site settings **SEO** tab:

- **Auto-generate sitemap** is on by default and produces `/sitemap.xml`
  covering static pages and CMS items.
- Per page: turn off **sitemap indexing** to exclude it.
- Per CMS collection: exclude the whole collection's template pages from the
  sitemap in the template's settings.
- **Custom sitemap:** turn off auto-generation and paste your own XML into
  the field. Only do this if you will maintain it; a stale hand-written
  sitemap is worse than the automatic one.

Submit `https://www.example.com.au/sitemap.xml` in Search Console.

---

## Structured Data

Webflow emits no structured data by default. Everything is added via custom
code, which is actually an advantage: you control exactly what is output and
there is no platform schema to duplicate.

### Organization (site-wide head custom code)

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Acme Consulting",
  "url": "https://www.example.com.au/",
  "logo": "https://cdn.prod.website-files.com/your-site-id/your-logo.png",
  "sameAs": [
    "https://www.linkedin.com/company/acme-consulting"
  ]
}
</script>
```

For a business with a physical location, put a `LocalBusiness` (or a more
specific subtype) on the home or contact page's head custom code instead, with
`address`, `telephone`, `geo` and `openingHoursSpecification`, matching the
Google Business Profile exactly.

### Article on a CMS template (template page head custom code)

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{{Name}}",
  "description": "{{Meta Description}}",
  "image": "{{Main Image}}",
  "datePublished": "{{Published On}}",
  "dateModified": "{{Updated On}}",
  "author": {
    "@type": "Person",
    "name": "{{Author:Name}}"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Acme Consulting"
  },
  "mainEntityOfPage": "https://www.example.com.au/insights/{{Slug}}"
}
</script>
```

Each `{{...}}` is a CMS field inserted with the field picker. **Watch for
quotes:** Webflow inserts field values as-is. A title containing a straight
double quote will break the JSON. Keep double quotes out of fields used in
JSON-LD, or use curly quotes in content. Validate a few items with the Rich
Results Test after publishing. Date fields may need their display format set
to an ISO-style format.

### Product (Webflow Ecommerce template)

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "{{Name}}",
  "description": "{{Meta Description}}",
  "image": "{{Main Image}}",
  "sku": "{{SKU}}",
  "brand": { "@type": "Brand", "name": "Acme" },
  "offers": {
    "@type": "Offer",
    "url": "https://www.example.com.au/product/{{Slug}}",
    "priceCurrency": "AUD",
    "price": "{{Price}}",
    "availability": "https://schema.org/InStock"
  }
}
</script>
```

Check how the price field renders; if it includes a currency symbol, create a
plain-number field for schema use.

### BreadcrumbList (CMS template)

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.example.com.au/" },
    { "@type": "ListItem", "position": 2, "name": "Insights", "item": "https://www.example.com.au/insights" },
    { "@type": "ListItem", "position": 3, "name": "{{Name}}", "item": "https://www.example.com.au/insights/{{Slug}}" }
  ]
}
</script>
```

### FAQ schema

Google retired FAQ rich results on 7 May 2026. Do not add `FAQPage` markup for
rich results. Keep FAQ content as visible on-page text.

---

## Images: Alt Text, Size and Format

### Alt text

- **Asset-level alt text:** in the **Assets** panel, open an image's settings
  and add alt text. Images placed in the Designer can then use the asset's alt
  text.
- **Per-instance override:** select the image, open its settings, and choose
  a custom alt text or mark it **decorative** (outputs an empty `alt=""`).
- **CMS images:** bind the image element's alt text to a CMS text field (for
  example `Main Image Alt`). Without that, CMS images often ship with no alt.

### Format and size

- Webflow generates responsive variants and a `srcset` for image elements
  automatically. **Background images do not get this**, so avoid large CSS
  background images for hero content; use an image element with object-fit
  instead.
- The **Assets** panel can convert uploads to WebP or AVIF in bulk. Do this
  for existing large JPEGs and PNGs.
- Upload at sensible dimensions (around 2x the largest rendered width) and
  compress first.

### Lazy loading

Each image element has a **Load** setting (lazy, eager, or automatic). Set
the hero / LCP image to **eager** and leave below-the-fold images lazy.
A lazy-loaded hero is one of the most common Webflow LCP findings.

---

## Security Headers

On standard Webflow hosting **you cannot set arbitrary HTTP response
headers**. HTTPS is automatic. The advanced publishing options in the site
settings expose a small number of toggles (such as secure frame headers and
SSL-related options); use them, but nothing beyond them is configurable on
standard plans.

```bash
curl -sI https://www.example.com.au | grep -Ei 'strict-transport|x-frame|content-security|x-content-type|referrer|permissions'
```

| Header | Status on Webflow | Workaround |
|--------|-------------------|------------|
| `Strict-Transport-Security` | Platform / advanced publishing options | Check current options; otherwise platform-limited |
| `X-Frame-Options` | Toggle in advanced publishing options | Turn on secure frame headers |
| `X-Content-Type-Options` | Platform-controlled | None on standard hosting |
| `Content-Security-Policy` | Not configurable on standard hosting | Meta CSP in site head code is possible but fragile with interactions and embeds |
| `Referrer-Policy` | Not configurable as a header | `<meta name="referrer" content="strict-origin-when-cross-origin">` in site-wide head code |
| `Permissions-Policy` | Not configurable | None on standard hosting |

### Workarounds that genuinely exist

1. **Enterprise hosting / reverse proxy.** Webflow Enterprise supports
   documented reverse-proxy setups, which let you add headers at the proxy.
   Standard plans should not proxy the domain through their own Cloudflare
   (orange cloud); check Webflow's current guidance before trying, as it can
   break SSL issuance and publishing.
2. **Code export.** Paid workspace plans can export static HTML/CSS/JS and
   host it on Netlify, Vercel or Cloudflare Pages, where headers are fully
   configurable. **CMS content, forms and Ecommerce do not survive export**,
   so this only suits brochure sites without CMS.

**How FAT should score this:** credit the toggles the client has enabled,
mark the remaining headers "platform-limited", and recommend the
Referrer-Policy meta tag.

---

## Performance

1. **Interactions and animations.** Heavy page-load interactions, scroll
   animations and Lottie files delay rendering. Keep first-viewport
   interactions minimal.
2. **Third-party code.** Review site-wide and page-level custom code.
   Remove stale tags and move non-critical scripts to the before-`</body>`
   area, with `defer`:

   ```html
   <script src="https://example-widget.com/widget.js" defer></script>
   ```

3. **Minification.** In the advanced publishing options, enable minification
   of HTML, CSS and JS.
4. **Fonts.** Upload only the weights you use, and prefer WOFF2. Each Google
   Font weight added in the Designer is another request.
5. **Unused styles.** Use the Style Manager's clean-up to remove unused
   classes, which shrinks the site CSS.
6. **Collection lists.** Large collection lists (with images) on one page
   are heavy; paginate or limit items.
7. **Video backgrounds.** Swap for a still image on mobile, or compress
   aggressively.
8. **LCP image eager** (see Images).

Measure with PageSpeed Insights on mobile across the home page, a key static
page and a CMS template page.

---

## Search Console Verification

1. **Google site verification field** in the site settings **SEO** tab. Paste
   only the verification code (content value), publish, then verify.
2. **Domain property via DNS TXT record** at your DNS provider. Best option,
   as it covers every subdomain.
3. **Meta tag in site-wide head custom code** (paid plans):

   ```html
   <meta name="google-site-verification" content="YOUR_CODE_HERE">
   ```

HTML file upload verification is not possible.

---

## What You Can't Fix on Webflow

| Limitation | Detail |
|------------|--------|
| Response headers | Only the advanced publishing toggles; no custom headers on standard hosting. |
| CMS URL depth | CMS items live at `/collection-slug/item-slug`. No nested paths such as `/services/melbourne/plumbing`. |
| Trailing slashes | Webflow URLs have no trailing slash; not configurable. |
| Pagination parameters | Collection list pagination uses a generated `?xxxx_page=` parameter. |
| Custom code limits | Character limits apply to custom code fields; large scripts must be hosted elsewhere and referenced. |
| Custom code on free plans | Requires a paid site plan. |
| Conditional logic in head | Custom code cannot use conditional visibility; use CMS text fields as values. |
| Web root files | Cannot upload arbitrary files to `/` or `/.well-known/`. |
| Proxying | Only supported on Enterprise. |
| Export | Exported code loses CMS, forms and Ecommerce. |

---

## Quick Audit Checklist

| Check | How to Verify | Where to Fix | Priority |
|-------|---------------|--------------|----------|
| `webflow.io` subdomain not indexed | `site:` search, view source on staging | SEO settings (subdomain indexing) | P0 |
| Default domain set, other variants redirect | `curl -I` on www / apex | Publishing settings | P0 |
| Global canonical URL set | View source for `rel="canonical"` | SEO settings | P1 |
| Unique titles and descriptions | FAT crawl | Page settings / CMS template bindings | P1 |
| Migration redirects in place | Crawl old URL list | 301 redirects | P0 (after migration) |
| robots.txt sensible, includes sitemap | Visit `/robots.txt` | SEO settings | P2 |
| LCP image set to eager | Inspect hero image | Image settings | P1 |
| Images converted to WebP / AVIF | Network panel | Assets panel | P2 |
| CMS images have bound alt text | FAT image report | Image element settings | P2 |
| Organization / LocalBusiness schema | Rich Results Test | Site or page head code | P2 |
| Article / Product schema on templates | Rich Results Test | Template head code | P2 |
| Utility and data-only pages noindexed | View source | Page head code, sitemap toggle | P3 |
| Minification on | View source | Advanced publishing options | P3 |
| Secure frame headers on | `curl -I` | Advanced publishing options | P2 |
| Search Console verified, sitemap submitted | GSC property | SEO settings / DNS | P1 |
| Referrer-Policy meta tag | View source | Site head code | P3 |
| Other security headers | `curl -I` | Not fixable on standard hosting | Info |
