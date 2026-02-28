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
- ✅ Images use modern formats (WebP, AVIF) where supported
- ✅ Images are appropriately sized (not 4000px wide for a thumbnail)
- ✅ `loading="lazy"` on below-fold images
- ✅ `width` and `height` attributes set (prevents CLS)

### Links
- ✅ Internal links use descriptive anchor text
- ✅ External links use `rel="noopener"` (or `noreferrer`)
- ❌ Broken internal links (404s)
- ❌ "Click here" as anchor text
- ❌ Orphan pages (no internal links pointing to them)

## Technical SEO

### Crawlability
- ✅ `robots.txt` exists and allows crawling of important pages
- ✅ `sitemap.xml` exists and is valid XML
- ✅ Sitemap is referenced in `robots.txt`
- ✅ No important pages blocked by `noindex`
- ✅ Canonical URLs are correct and self-referencing

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
These affect ranking. FAT Agent can't measure them directly but flags risks:
- **LCP (Largest Contentful Paint)** — Large hero images without preload
- **FID/INP (Interaction to Next Paint)** — Heavy JS blocking main thread
- **CLS (Cumulative Layout Shift)** — Images without dimensions, dynamic content injection

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
