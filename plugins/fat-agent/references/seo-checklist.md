# SEO Checklist Reference

Extended SEO audit criteria for FAT Agent. The SKILL.md covers the essentials;
this file covers the extended checks for deeper audits.

## On-Page SEO

### Title Tag
- ✅ Exists
- ✅ 50-60 characters (Google truncates at ~60)
- ✅ Contains primary keyword
- ✅ Unique per page
- ❌ Starts with "Home" or is just the brand name
- ❌ Contains pipe-separated keyword stuffing

### Meta Description
- ✅ Exists
- ✅ 150-160 characters
- ✅ Contains a call-to-action or compelling hook
- ✅ Unique per page
- ✅ **Present on error/fallback paths** — Dynamic routes (product not found, invalid category) must still include a description in their metadata, not just a title. Search engines crawl stale URLs.
- ❌ Duplicate across pages
- ❌ Auto-generated gibberish

### Headings
- ✅ Exactly one `<h1>` per page
- ✅ `<h1>` contains primary keyword
- ✅ Heading hierarchy is logical (h1 → h2 → h3, no skipping)
- ❌ Multiple `<h1>` tags
- ❌ Empty heading tags
- ❌ Headings used purely for styling

### Images
- ✅ All `<img>` have `alt` attributes
- ✅ Alt text is descriptive (not "image1.jpg")
- ✅ **Dynamic alt fallbacks** — Code-level check: Image components with dynamic data (`alt={product.name}`) include `|| 'fallback'` to prevent undefined/null producing missing alt attributes
- ✅ Images use modern formats (WebP, AVIF) where supported
- ✅ Images are appropriately sized (not 4000px wide for a thumbnail)
- ✅ `loading="lazy"` on below-fold images
- ✅ `width` and `height` attributes set (prevents CLS)

### Links
- ✅ Internal links use descriptive anchor text
- ✅ External links use `rel="noopener"` (or `noreferrer`)
- ✅ Pages have at least one internal link (no orphan pages)
- ✅ No `rel="nofollow"` on internal links (wastes link equity)
- ❌ Broken internal links (404s)
- ❌ "Click here", "read more", "learn more" as anchor text
- ❌ Orphan pages (no internal links pointing to them)

### URL Structure
- ✅ URLs use hyphens (not underscores)
- ✅ URLs are lowercase
- ✅ No double slashes in URL path
- ✅ No query parameters on content pages
- ✅ Consistent trailing slash behaviour

### Image Filenames
- ✅ Descriptive filenames (e.g., `blue-widget-front.webp`)
- ❌ Generic filenames (e.g., `IMG_001.jpg`, `screenshot.png`, `image1.jpg`)

## Technical SEO

### Crawlability
- ✅ `robots.txt` exists and allows crawling of important pages
- ✅ `sitemap.xml` exists and is valid XML
- ✅ Sitemap is referenced in `robots.txt`
- ✅ No important pages blocked by `noindex`
- ✅ Canonical URLs are correct and self-referencing
- ✅ **IndexNow adopted** — API key file at site root (e.g., `/{key}.txt`) for Bing/Yandex fast indexing
- ✅ **Noindex/sitemap consistency** — Pages listed in sitemap are not `noindex`; noindexed pages are not in sitemap
- ❌ Sitemap contains URLs that return `noindex` meta robots

### URL Structure
- ✅ URLs are human-readable (`/about-us` not `/page?id=47`)
- ✅ URLs use hyphens, not underscores
- ✅ No URL parameters for content pages
- ✅ Consistent trailing slash behaviour

### Structured Data
- ✅ JSON-LD present on homepage (Organization or WebSite schema)
- ✅ JSON-LD validates (test at schema.org validator)
- ✅ Relevant schema for page type:
  - Blog posts → Article/BlogPosting
  - Products → Product
  - Local business → LocalBusiness
  - FAQ pages → FAQPage
  - How-to content → HowTo

### International SEO (if applicable)
- ✅ `hreflang` tags for multi-language sites
- ✅ `<html lang="xx">` attribute set correctly
- ✅ Content is actually translated (not just machine-translated)

## Social / Sharing

### Open Graph
- ✅ `og:title` — Page title
- ✅ `og:description` — Page description
- ✅ `og:image` — Share image (1200x630px recommended)
- ✅ `og:url` — Canonical URL
- ✅ `og:type` — Usually "website" or "article"
- ✅ `og:site_name` — Brand name

### Twitter Cards
- ✅ `twitter:card` — "summary_large_image" recommended
- ✅ `twitter:title`
- ✅ `twitter:description`
- ✅ `twitter:image`

## Performance Impact on SEO

### Core Web Vitals
These affect ranking. FAT Agent can fetch CWV data from the PageSpeed Insights API:
- **LCP (Largest Contentful Paint)** — Target ≤ 2.5s. Large hero images without preload are a risk.
- **INP (Interaction to Next Paint)** — Target ≤ 200ms. Heavy JS blocking main thread.
- **CLS (Cumulative Layout Shift)** — Target ≤ 0.1. Images without dimensions, dynamic content injection.
- **FCP (First Contentful Paint)** — Target ≤ 1.8s. Render-blocking resources delay first paint.
- **TTFB (Time to First Byte)** — Target ≤ 800ms. Server response time.

CWV data is fetched from:
```
https://www.googleapis.com/pagespeedonline/v5/runPagespeedTest?url={URL}&strategy=mobile
```
No API key required for basic usage.

### Mobile
- ✅ `<meta name="viewport">` is set correctly
- ✅ Text is readable without zooming
- ✅ Tap targets are at least 48x48px
- ✅ No horizontal scrolling

## Scoring Guide

| Category | Weight | Max Score |
|----------|--------|-----------|
| Title & Meta | 20% | 20 |
| Headings & Content | 15% | 15 |
| Images | 10% | 10 |
| Technical (robots, sitemap, canonical) | 20% | 20 |
| Structured Data | 10% | 10 |
| Social / OG Tags | 10% | 10 |
| Mobile & Performance signals | 15% | 15 |
| **Total** | **100%** | **100** |
