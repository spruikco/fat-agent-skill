# Wix -- Platform Fix Reference

Wix is a fully hosted website builder. There is no server access, no file
system, no theme code in the traditional sense, and no control over HTTP
response headers. Fixes happen in four places:

1. **Page SEO settings** -- per page (and per dynamic page / page type) title,
   description, URL slug, indexing toggle, and an "Advanced SEO" area for
   custom meta tags and structured data.
2. **Site-wide SEO settings** -- in the dashboard's Marketing & SEO area:
   default title patterns per page type, the robots.txt editor, the URL
   redirect manager, and site verification.
3. **Custom code** -- the dashboard's Custom Code settings, which inject HTML
   into the head or body of all or selected pages (requires a premium plan
   with a connected domain).
4. **Velo** -- Wix's JavaScript development platform, which includes an SEO
   API for setting titles, meta tags, links and structured data at runtime.

This reference covers the most common FAT Agent findings on Wix sites and
explains exactly what Wix allows. Menu names in Wix move around frequently;
where exact labels are uncertain, the area of the dashboard is described.

---

## Titles and Meta Descriptions

### Static pages

In the Editor, open the **Pages** panel, choose the page's settings, and go
to the **SEO basics** tab:

- **Title tag** -- what appears in search results and the browser tab.
- **Meta description**.
- **URL slug** -- changing it on a live page offers to create a 301 redirect.
  Always accept.

### Page-type patterns (stores, blog, bookings, dynamic pages)

Wix lets you define a **default SEO pattern** for each page type (product
pages, blog posts, category pages, dynamic pages and so on) in the site-wide
SEO settings. Patterns use variables, for example:

```text
Title:        {Product Name} | {Site Name}
Description:  {Product Description}
```

Set a strong pattern once, then override individual pages that matter. FAT's
duplicate-title findings on Wix stores are usually caused by a weak pattern
(often just `{Site Name}`) applied to every product.

### Dynamic pages with Velo

For dynamic pages driven by a CMS collection, Velo gives full control. Put
this in the dynamic page's code panel:

```javascript
import wixSeoFrontend from 'wix-seo-frontend';

$w.onReady(async function () {
  const item = $w('#dynamicDataset').getCurrentItem();
  if (!item) return;

  const title = `${item.title} | Acme Plumbing Melbourne`;
  const description = (item.summary || '').slice(0, 155);

  await wixSeoFrontend.setTitle(title);
  await wixSeoFrontend.setMetaTags([
    { name: 'description', content: description },
    { property: 'og:title', content: title },
    { property: 'og:description', content: description }
  ]);
});
```

**Caution:** the `set*` functions *replace* what the SEO panel generated for
that page. If you set meta tags from Velo, include every tag you want to keep.
Prefer the SEO panel patterns where they are sufficient, and use Velo only
where you need logic the patterns cannot express.

---

## Canonicals and Duplicate URLs

Wix outputs a self-referencing canonical tag on every page automatically.
This is correct in the vast majority of cases.

- **Custom canonical:** the page's Advanced SEO settings allow you to add
  custom tags. Where a page genuinely duplicates another (for example, a
  landing-page copy for a campaign), set the canonical to the original there.
  Do not add a second canonical via Custom Code; you will end up with two.
- **Dynamic pages:** Velo can set the canonical link:

  ```javascript
  import wixSeoFrontend from 'wix-seo-frontend';

  $w.onReady(async function () {
    await wixSeoFrontend.setLinks([
      { rel: 'canonical', href: 'https://www.example.com.au/services/blocked-drains' }
    ]);
  });
  ```

- **Store category and filter URLs:** Wix Stores filtering and sorting use
  query parameters. Wix canonicalises these back to the base category page.
  If Search Console shows large numbers of parameter URLs being crawled,
  consider a robots.txt disallow for the specific parameter (next section).
- **Multilingual sites:** Wix Multilingual adds `hreflang` automatically. Make
  sure every language version has translated SEO fields, otherwise FAT will
  flag duplicate titles across languages.

---

## robots.txt and noindex

### noindex a page

In the page's **SEO basics** tab, turn off the setting that lets search
engines index the page. Wix adds a `noindex` robots meta tag and removes the
page from the sitemap. Use this for thank-you pages, members-only pages, test
pages, and thin legal boilerplate you do not want ranking.

For a whole page type (for example, all blog tag pages), use the page-type
SEO settings, which include the same indexing toggle.

### robots.txt editor

Wix provides a **robots.txt editor** in the site-wide SEO settings. You can
add rules, and you can reset to the Wix default. Limits:

- The editor only controls the text of `/robots.txt`. It does not change how
  Wix serves pages.
- Keep the Wix defaults. They block internal and system paths that should
  never be crawled.
- Add rules below the defaults rather than rewriting the file.

Example additions for a Wix store where parameter URLs are wasting crawl:

```text
User-agent: *
Disallow: /*?sort=
Disallow: /*&sort=
```

Check the exact parameter names on the live site first (open a filtered
category and copy the URL). Wix changes these over time.

**Remember:** `Disallow` stops crawling, not indexing. To remove a page from
Google, noindex it and leave it crawlable until it drops out.

---

## 301 Redirects

Wix has a **URL Redirect Manager** in the site-wide SEO settings.

| Behaviour | Detail |
|-----------|--------|
| Redirect type | 301 permanent |
| Single redirects | Old URL path to a page on the site or an external URL |
| Bulk import | CSV upload for migrations |
| Automatic redirects | Offered when you change a page's URL slug |
| Pattern support | Limited; plan on one row per URL for migrations |
| Domain redirects | www / non-www and HTTP to HTTPS are handled automatically by Wix once the domain is connected |

Typical CSV for migrating from WordPress (check the column headers against
the sample file the Redirect Manager offers, as Wix has changed them before):

```csv
Old URL,New URL
/about-us/,/about
/services/hot-water/,/hot-water-repairs
/blog/2024/06/blocked-drains-guide/,/post/blocked-drains-guide
/contact-us/,/contact
```

After importing, crawl the old URL list and confirm each returns one 301 to a
page returning 200:

```bash
curl -sIL https://www.example.com.au/about-us/ | grep -Ei '^(HTTP|location)'
```

---

## Sitemaps

Wix generates `/sitemap.xml` automatically. It is a sitemap index linking to
child sitemaps per content type (pages, store products, blog posts, dynamic
pages and so on).

- **Cannot** edit the XML directly.
- Pages set to noindex are excluded automatically.
- Hidden-from-menu pages are still included if they are indexable. Hide them
  from search too if they should not rank.
- Submit `https://www.example.com.au/sitemap.xml` in Search Console. Wix's
  built-in Google connection (below) can submit it for you.

---

## Structured Data

### What Wix generates automatically

Wix outputs structured data for several of its own apps, including store
products (Product with offers), blog posts, events and bookings services,
plus site-level markup based on your business information. Check the output
with Google's Rich Results Test before adding anything, so you do not create
duplicates.

### Custom JSON-LD per page

In a page's **Advanced SEO** tab, there is a **structured data markup** area.
Paste JSON-LD there. For page types, the page-type SEO settings accept JSON-LD
with variables.

Organization (paste on the home page):

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Acme Plumbing",
  "url": "https://www.example.com.au/",
  "logo": "https://static.wixstatic.com/media/your-logo-id.png",
  "sameAs": [
    "https://www.facebook.com/acmeplumbing",
    "https://www.instagram.com/acmeplumbing"
  ]
}
```

LocalBusiness (for businesses with a physical address or service area):

```json
{
  "@context": "https://schema.org",
  "@type": "Plumber",
  "name": "Acme Plumbing",
  "url": "https://www.example.com.au/",
  "telephone": "+61 3 9000 0000",
  "image": "https://static.wixstatic.com/media/your-shopfront.jpg",
  "priceRange": "$$",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "12 Example Street",
    "addressLocality": "Richmond",
    "addressRegion": "VIC",
    "postalCode": "3121",
    "addressCountry": "AU"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": -37.8183,
    "longitude": 144.9983
  },
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "opens": "07:00",
      "closes": "17:00"
    }
  ],
  "areaServed": ["Richmond", "Hawthorn", "Kew"]
}
```

Use the most specific `LocalBusiness` subtype available (`Plumber`,
`Dentist`, `Restaurant` and so on). Keep name, address and phone identical to
the Google Business Profile.

BreadcrumbList for a service page:

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.example.com.au/" },
    { "@type": "ListItem", "position": 2, "name": "Services", "item": "https://www.example.com.au/services" },
    { "@type": "ListItem", "position": 3, "name": "Blocked Drains", "item": "https://www.example.com.au/services/blocked-drains" }
  ]
}
```

### Structured data from Velo (dynamic pages)

```javascript
import wixSeoFrontend from 'wix-seo-frontend';

$w.onReady(async function () {
  const item = $w('#dynamicDataset').getCurrentItem();
  if (!item) return;

  await wixSeoFrontend.setStructuredData([
    {
      '@context': 'https://schema.org',
      '@type': 'Service',
      name: item.title,
      description: item.summary,
      provider: { '@type': 'Organization', name: 'Acme Plumbing' },
      areaServed: item.suburb
    }
  ]);
});
```

As with titles, `setStructuredData` replaces the page's existing structured
data. Include everything the page needs in the array.

### FAQ schema

Google retired FAQ rich results on 7 May 2026. Do not add `FAQPage` markup
for rich results. Wix's FAQ app content can stay on the page as visible
questions and answers, which still help users and AI answer engines.

---

## Images: Alt Text, Size and Format

### Alt text

Select an image in the Editor, open its settings, and fill in the alt text
field (Wix phrases it as describing what is in the image). Gallery items,
store product images and blog images each have their own alt fields. Mark
purely decorative images as decorative where the option exists.

### Format, size and lazy loading

Wix's media platform handles most of this automatically:

- Images are served in modern formats (WebP) to supporting browsers.
- Wix serves resized versions to fit the rendered size.
- Below-the-fold images are lazy loaded by the platform.

What you control:

- **Upload size.** Do not upload 6000px, 10 MB camera originals. Resize to
  roughly 2500px on the long edge and compress first.
- **Hero choices.** Full-screen video backgrounds, slideshows and large
  animated strips in the first viewport are the most common Wix LCP problem.
  Use a single, well-compressed still image for the hero.
- **Image count.** Galleries with dozens of images on one page still cost
  bytes even when lazy loaded.

---

## Security Headers

**You cannot set HTTP response headers on Wix.** There is no headers file,
no server config, and Velo cannot modify page response headers. Wix handles
SSL automatically and serves the site over HTTPS; check what else it sends
with:

```bash
curl -sI https://www.example.com.au | grep -Ei 'strict-transport|x-frame|content-security|x-content-type|referrer|permissions'
```

| Header | Status on Wix | Workaround |
|--------|---------------|------------|
| `Strict-Transport-Security` | Platform-controlled | None |
| `X-Content-Type-Options` | Platform-controlled | None |
| `X-Frame-Options` / `frame-ancestors` | Platform-controlled | None |
| `Content-Security-Policy` | Not configurable | None practical. A meta CSP via Custom Code would break the Wix runtime. |
| `Referrer-Policy` | Not configurable as a header | A `<meta name="referrer" content="strict-origin-when-cross-origin">` via Custom Code in the head |
| `Permissions-Policy` | Not configurable | None |

**Cloudflare in front of Wix is not a supported workaround.** Wix manages
SSL and routing for connected domains, and proxying the domain through your
own Cloudflare account (orange cloud) is not supported and can break
certificate issuance. Keep DNS records DNS-only.

**How FAT should score this:** mark missing headers as "platform-limited".
The only honest recommendation for a client who needs full header control
(for example, for a security questionnaire) is a platform change.

---

## Performance

Wix sites ship a large JavaScript runtime you cannot remove. Focus on what
you add on top of it.

### Checklist

1. **Apps.** Every installed Wix app and third-party widget adds scripts.
   Remove apps that are not in use, and check they are not loaded on pages
   that do not need them.
2. **Custom Code.** In the Custom Code settings, review every snippet. Scope
   each one to the pages that need it rather than "all pages", and choose
   body-end placement for anything not required in the head.
3. **Hero section.** Replace video backgrounds and slideshows above the fold
   with a single static image.
4. **Animations.** Entrance animations on many elements delay visual
   completeness. Use them sparingly.
5. **Fonts.** Limit to two families and a few weights.
6. **Velo code.** Keep `$w.onReady` light. Heavy data queries on page load
   delay interactivity; load secondary data after the page renders.
7. **Page length.** Very long single-page designs with hundreds of elements
   are slow on mobile. Split them.

Wix provides a site speed dashboard with real-user Core Web Vitals. Use it
alongside PageSpeed Insights, and test the mobile version.

---

## Search Console Verification

Options, in order of preference:

1. **Wix's built-in Google Search Console connection**, reached through the
   SEO setup checklist or SEO tools. It verifies the site and submits the
   sitemap in one step.
2. **Domain property via DNS TXT record.** If the domain uses Wix
   nameservers, add the TXT record in the domain's DNS settings in Wix;
   otherwise add it at your DNS provider.
3. **Meta tag.** The site verification area of the SEO settings accepts a
   verification meta tag, or add it via Custom Code in the head:

   ```html
   <meta name="google-site-verification" content="YOUR_CODE_HERE">
   ```

HTML file upload verification is not possible.

---

## What You Can't Fix on Wix

| Limitation | Detail |
|------------|--------|
| Response headers | No custom security, caching or CORS headers. |
| Proxying / CDN | Cannot put your own CDN or proxy in front. |
| JavaScript runtime | The Wix framework bundle is always loaded; you cannot remove it. |
| URL prefixes | Some app page types use fixed or semi-fixed prefixes (for example `/product-page/`, `/post/`). Wix has added some prefix customisation, but not full control. |
| Sitemap contents | Auto-generated; exclusion only via noindex. |
| HTML output | Generated markup is heavy and not editable; heading levels are set per text element only. |
| Web root files | You cannot upload arbitrary files to `/` or `/.well-known/`. |
| Server response time | Platform-controlled. |
| Code on free plans | Custom Code and a custom domain need a premium plan. |

---

## Quick Audit Checklist

| Check | How to Verify | Where to Fix | Priority |
|-------|---------------|--------------|----------|
| Site on custom domain, not `wixsite.com` | Visit site | Domain settings (premium plan) | P0 |
| Key pages indexable | View source for `noindex` | Page SEO basics | P0 |
| Unique titles and descriptions | FAT crawl | Page SEO basics / page-type patterns | P1 |
| Page-type patterns not just `{Site Name}` | Check product and post titles | Site-wide SEO settings | P1 |
| Migration redirects in place | Crawl old URL list | URL Redirect Manager (CSV) | P0 (after migration) |
| Organization / LocalBusiness schema | Rich Results Test | Home page Advanced SEO | P2 |
| No duplicate schema blocks | View source | Advanced SEO / Velo | P2 |
| Images have alt text | FAT image report | Image settings | P2 |
| Hero is a still image, not video/slideshow | Inspect LCP element | Editor | P1 |
| Unused apps and Custom Code removed | App list, Custom Code list | Dashboard | P2 |
| Thank-you and test pages noindexed | View source | Page SEO basics | P3 |
| Search Console verified, sitemap submitted | GSC property | SEO tools / DNS | P1 |
| Referrer-Policy meta tag | View source | Custom Code | P3 |
| Security headers | `curl -I` | Not fixable (platform-limited) | Info |
