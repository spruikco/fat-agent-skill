# Static HTML -- Framework Fix Reference

Fix reference for plain static HTML/CSS/JS sites -- no build step, no framework,
no bundler. Just `.html` files served as-is. This covers the fixes FAT Agent
recommends when auditing a vanilla HTML site.

---

## SEO Meta Tags

Every page needs a complete `<head>` section. Missing or malformed meta tags are
the most common issue on static HTML sites because there is no framework
generating them automatically.

### Essential Head Section

```html
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <!-- Page title: 50-60 characters, primary keyword near the front -->
    <title>Primary Keyword - Secondary Keyword | Brand Name</title>

    <!-- Meta description: 150-160 characters, compelling, unique per page -->
    <meta name="description" content="A concise, compelling description of this page. Include a call-to-action or hook. Keep it under 160 characters for Google.">

    <!-- Canonical URL: prevents duplicate content issues -->
    <link rel="canonical" href="https://example.com/page-url">

    <!-- Robots: control indexing (omit if you want default index/follow) -->
    <meta name="robots" content="index, follow">

    <!-- Open Graph (Facebook, LinkedIn, etc.) -->
    <meta property="og:title" content="Page Title for Social Sharing">
    <meta property="og:description" content="Description shown when shared on social media. Can differ from meta description.">
    <meta property="og:image" content="https://example.com/images/share-image.jpg">
    <meta property="og:url" content="https://example.com/page-url">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Brand Name">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Page Title for Twitter">
    <meta name="twitter:description" content="Description shown on Twitter cards.">
    <meta name="twitter:image" content="https://example.com/images/share-image.jpg">

    <!-- Favicon -->
    <link rel="icon" href="/favicon.ico" sizes="32x32">
    <link rel="icon" href="/icon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
</head>
```

### Title Tag Best Practices

- 50-60 characters maximum (Google truncates at ~60)
- Put the primary keyword near the beginning
- Every page gets a unique title
- Format: `Primary Keyword - Context | Brand`
- Do not stuff keywords with pipe separators
- Do not use just the brand name or "Home"

### Meta Description Best Practices

- 150-160 characters (Google truncates at ~160)
- Include a call-to-action or compelling hook
- Unique per page -- never duplicate across pages
- Include the primary keyword naturally
- Think of it as ad copy for your search result

### Canonical URL

Every page should have a self-referencing canonical tag. This prevents duplicate
content issues when your page is accessible at multiple URLs (with/without
trailing slash, with/without `www`, query parameters, etc.).

```html
<!-- On https://example.com/about -->
<link rel="canonical" href="https://example.com/about">
```

Always use the full absolute URL including the protocol.

### Open Graph Image

- Recommended size: 1200 x 630 pixels
- Minimum size: 600 x 315 pixels
- File size under 8 MB
- Use absolute URLs (not relative paths)
- Test with the Facebook Sharing Debugger: https://developers.facebook.com/tools/debug/

### Robots Meta Tag

```html
<!-- Default behaviour (index and follow links) -- you can omit this -->
<meta name="robots" content="index, follow">

<!-- Prevent indexing (use for staging, thank-you pages, etc.) -->
<meta name="robots" content="noindex, nofollow">

<!-- Index but don't follow links -->
<meta name="robots" content="index, nofollow">

<!-- Prevent caching of the page snippet -->
<meta name="robots" content="noarchive">
```

---

## Structured Data (JSON-LD)

Structured data helps search engines understand your content and can enable rich
results (stars, FAQ accordions, breadcrumbs, etc.). Always use JSON-LD format
inside a `<script type="application/ld+json">` tag in the `<head>` or `<body>`.

Validate at: https://validator.schema.org/ or https://search.google.com/test/rich-results

### Organization (Homepage)

```html
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Company Name",
    "url": "https://example.com",
    "logo": "https://example.com/images/logo.png",
    "description": "Brief description of the company.",
    "sameAs": [
        "https://www.facebook.com/companyname",
        "https://www.linkedin.com/company/companyname",
        "https://twitter.com/companyname"
    ],
    "contactPoint": {
        "@type": "ContactPoint",
        "telephone": "+1-555-555-5555",
        "contactType": "customer service",
        "availableLanguage": "English"
    }
}
</script>
```

### WebSite with Search Action (Homepage)

```html
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "Site Name",
    "url": "https://example.com",
    "potentialAction": {
        "@type": "SearchAction",
        "target": "https://example.com/search?q={search_term_string}",
        "query-input": "required name=search_term_string"
    }
}
</script>
```

### Article (Blog Posts)

```html
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Article Title Here",
    "description": "Brief summary of the article.",
    "image": "https://example.com/images/article-hero.jpg",
    "author": {
        "@type": "Person",
        "name": "Author Name",
        "url": "https://example.com/about/author-name"
    },
    "publisher": {
        "@type": "Organization",
        "name": "Company Name",
        "logo": {
            "@type": "ImageObject",
            "url": "https://example.com/images/logo.png"
        }
    },
    "datePublished": "2025-01-15",
    "dateModified": "2025-02-20",
    "mainEntityOfPage": {
        "@type": "WebPage",
        "@id": "https://example.com/blog/article-slug"
    }
}
</script>
```

### LocalBusiness (Local Sites)

```html
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    "name": "Business Name",
    "description": "Brief description of the business.",
    "image": "https://example.com/images/storefront.jpg",
    "url": "https://example.com",
    "telephone": "+1-555-555-5555",
    "email": "contact@example.com",
    "address": {
        "@type": "PostalAddress",
        "streetAddress": "123 Main Street",
        "addressLocality": "Springfield",
        "addressRegion": "IL",
        "postalCode": "62701",
        "addressCountry": "US"
    },
    "geo": {
        "@type": "GeoCoordinates",
        "latitude": 39.7817,
        "longitude": -89.6501
    },
    "openingHoursSpecification": [
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "opens": "09:00",
            "closes": "17:00"
        },
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": "Saturday",
            "opens": "10:00",
            "closes": "14:00"
        }
    ],
    "priceRange": "$$"
}
</script>
```

### BreadcrumbList (Navigation)

```html
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Home",
            "item": "https://example.com"
        },
        {
            "@type": "ListItem",
            "position": 2,
            "name": "Blog",
            "item": "https://example.com/blog"
        },
        {
            "@type": "ListItem",
            "position": 3,
            "name": "Article Title",
            "item": "https://example.com/blog/article-slug"
        }
    ]
}
</script>
```

### FAQPage

```html
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
        {
            "@type": "Question",
            "name": "What is your return policy?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "We offer a 30-day return policy on all unused items."
            }
        },
        {
            "@type": "Question",
            "name": "Do you offer free shipping?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "Yes, free shipping on all orders over $50."
            }
        }
    ]
}
</script>
```

---

## Image Optimization

Images are the biggest source of performance problems on static sites. Every
image issue compounds -- no dimensions causes layout shift, no lazy loading
wastes bandwidth, no responsive images serves desktop sizes to mobile.

### Width and Height Attributes (CLS Prevention)

Always set `width` and `height` on `<img>` tags. The browser uses these to
reserve space before the image loads, preventing Cumulative Layout Shift (CLS).

```html
<!-- Good: dimensions set, browser reserves space -->
<img src="hero.jpg" alt="Office workspace" width="1200" height="675">

<!-- Bad: no dimensions, page jumps when image loads -->
<img src="hero.jpg" alt="Office workspace">
```

The values should match the image's intrinsic dimensions. CSS can still resize
the image responsively:

```css
img {
    max-width: 100%;
    height: auto;
}
```

### Lazy Loading

Use `loading="lazy"` on images below the fold. Do not lazy-load the hero/LCP
image -- it needs to load immediately.

```html
<!-- Hero image: loads immediately (above the fold) -->
<img src="hero.jpg" alt="Hero banner" width="1200" height="675"
     fetchpriority="high">

<!-- Below-fold images: lazy loaded -->
<img src="team-photo.jpg" alt="Our team" width="800" height="533"
     loading="lazy">

<img src="product-shot.jpg" alt="Product display" width="600" height="400"
     loading="lazy">
```

### fetchpriority for LCP Image

Mark your Largest Contentful Paint image with `fetchpriority="high"` so the
browser prioritises it:

```html
<img src="hero.jpg" alt="Hero banner" width="1200" height="675"
     fetchpriority="high">
```

You can also use it on a preload link in the `<head>`:

```html
<link rel="preload" as="image" href="hero.jpg" fetchpriority="high">
```

### Responsive Images with srcset and sizes

Serve appropriately sized images for different screen widths. This saves
bandwidth on mobile and improves load times.

```html
<img src="product-800.jpg"
     srcset="product-400.jpg 400w,
             product-800.jpg 800w,
             product-1200.jpg 1200w,
             product-1600.jpg 1600w"
     sizes="(max-width: 600px) 100vw,
            (max-width: 1200px) 50vw,
            33vw"
     alt="Product photo"
     width="1600" height="1067"
     loading="lazy">
```

**How `sizes` works:**
- Viewport up to 600px: image takes 100% of viewport width
- Viewport up to 1200px: image takes 50% of viewport width
- Larger: image takes 33% of viewport width

The browser picks the smallest `srcset` image that covers the computed size.

### Picture Element (Format Switching)

Use `<picture>` to serve modern formats (WebP, AVIF) with a fallback for older
browsers:

```html
<picture>
    <source srcset="hero.avif" type="image/avif">
    <source srcset="hero.webp" type="image/webp">
    <img src="hero.jpg" alt="Hero banner" width="1200" height="675">
</picture>
```

Combining format switching with responsive sizes:

```html
<picture>
    <source srcset="hero-400.avif 400w,
                    hero-800.avif 800w,
                    hero-1200.avif 1200w"
            sizes="100vw"
            type="image/avif">
    <source srcset="hero-400.webp 400w,
                    hero-800.webp 800w,
                    hero-1200.webp 1200w"
            sizes="100vw"
            type="image/webp">
    <img src="hero-1200.jpg"
         srcset="hero-400.jpg 400w,
                 hero-800.jpg 800w,
                 hero-1200.jpg 1200w"
         sizes="100vw"
         alt="Hero banner"
         width="1200" height="675">
</picture>
```

### Compression Tools

- **Squoosh** (https://squoosh.app) -- browser-based, supports WebP/AVIF, visual comparison
- **TinyPNG** (https://tinypng.com) -- PNG and JPEG lossy compression
- **ImageOptim** (macOS) -- lossless optimization, strips metadata
- **Sharp** (CLI/Node) -- batch processing: `npx sharp-cli -i input.jpg -o output.webp --webp`

Target file sizes:
- Hero images: under 200 KB
- Content images: under 100 KB
- Thumbnails: under 30 KB

---

## Accessibility Patterns

Static HTML sites have an advantage: no framework abstractions hiding
accessibility issues. Use semantic elements directly and they do most of the
work.

### Semantic HTML Structure

```html
<body>
    <a href="#main" class="skip-link">Skip to content</a>

    <header>
        <nav aria-label="Primary">
            <ul>
                <li><a href="/">Home</a></li>
                <li><a href="/about">About</a></li>
                <li><a href="/services">Services</a></li>
                <li><a href="/contact">Contact</a></li>
            </ul>
        </nav>
    </header>

    <main id="main">
        <article>
            <h1>Page Title</h1>
            <p>Main content goes here.</p>

            <section aria-labelledby="features-heading">
                <h2 id="features-heading">Features</h2>
                <p>Section content.</p>
            </section>
        </article>

        <aside aria-label="Related content">
            <h2>Related Articles</h2>
            <ul>
                <li><a href="/blog/post-1">Related post</a></li>
            </ul>
        </aside>
    </main>

    <footer>
        <nav aria-label="Footer">
            <ul>
                <li><a href="/privacy">Privacy Policy</a></li>
                <li><a href="/terms">Terms of Service</a></li>
            </ul>
        </nav>
        <p>&copy; 2025 Company Name</p>
    </footer>
</body>
```

### Skip to Content Link

The first interactive element in the `<body>` should be a skip link. It is
visually hidden until focused.

```html
<a href="#main" class="skip-link">Skip to content</a>
```

```css
.skip-link {
    position: absolute;
    top: -40px;
    left: 0;
    background: #000;
    color: #fff;
    padding: 8px 16px;
    z-index: 100;
    transition: top 0.2s;
}

.skip-link:focus {
    top: 0;
}
```

### Alt Text on Images

```html
<!-- Informative image: describe what's shown -->
<img src="team.jpg" alt="Five team members standing in front of the office building">

<!-- Decorative image: empty alt (screen readers skip it) -->
<img src="divider.svg" alt="">

<!-- Image that is a link: alt describes the destination -->
<a href="/products/widget">
    <img src="widget.jpg" alt="Blue Widget - view product details">
</a>

<!-- Complex image (chart, infographic): provide full description -->
<img src="chart.png" alt="Bar chart showing quarterly revenue: Q1 $2M, Q2 $2.5M, Q3 $3.1M, Q4 $3.8M">
```

### Form Labels and Fieldsets

Every input needs a label. Use `<fieldset>` and `<legend>` for related groups.

```html
<form action="/contact" method="POST">
    <fieldset>
        <legend>Contact Information</legend>

        <div>
            <label for="name">Full Name <span aria-hidden="true">*</span></label>
            <input type="text" id="name" name="name" required
                   autocomplete="name"
                   aria-required="true">
        </div>

        <div>
            <label for="email">Email Address <span aria-hidden="true">*</span></label>
            <input type="email" id="email" name="email" required
                   autocomplete="email"
                   aria-required="true">
        </div>

        <div>
            <label for="phone">Phone Number</label>
            <input type="tel" id="phone" name="phone"
                   autocomplete="tel">
        </div>
    </fieldset>

    <fieldset>
        <legend>Preferred Contact Method</legend>

        <div>
            <input type="radio" id="contact-email" name="contact-method" value="email">
            <label for="contact-email">Email</label>
        </div>

        <div>
            <input type="radio" id="contact-phone" name="contact-method" value="phone">
            <label for="contact-phone">Phone</label>
        </div>
    </fieldset>

    <div>
        <label for="message">Message <span aria-hidden="true">*</span></label>
        <textarea id="message" name="message" rows="5" required
                  aria-required="true"></textarea>
    </div>

    <button type="submit">Send Message</button>
</form>
```

### ARIA Landmarks and Roles

Semantic HTML elements map to ARIA roles automatically. You rarely need
explicit roles when using the correct elements:

| HTML Element | Implicit ARIA Role | When to Add Explicit Role |
|---|---|---|
| `<header>` | `banner` | Never (when direct child of `<body>`) |
| `<nav>` | `navigation` | Never |
| `<main>` | `main` | Never |
| `<footer>` | `contentinfo` | Never (when direct child of `<body>`) |
| `<aside>` | `complementary` | Never |
| `<section>` | `region` | Only when it has an `aria-labelledby` or `aria-label` |
| `<form>` | `form` | Only when it has an accessible name |

When you need ARIA (custom widgets):

```html
<!-- Mobile menu toggle -->
<button aria-expanded="false" aria-controls="mobile-menu">
    <span class="sr-only">Menu</span>
    <svg aria-hidden="true"><!-- hamburger icon --></svg>
</button>

<nav id="mobile-menu" aria-label="Mobile" hidden>
    <ul>
        <li><a href="/">Home</a></li>
        <li><a href="/about">About</a></li>
    </ul>
</nav>

<!-- Tab interface -->
<div role="tablist" aria-label="Account settings">
    <button role="tab" id="tab-1" aria-selected="true" aria-controls="panel-1">Profile</button>
    <button role="tab" id="tab-2" aria-selected="false" aria-controls="panel-2">Security</button>
</div>
<div role="tabpanel" id="panel-1" aria-labelledby="tab-1">
    <p>Profile settings content.</p>
</div>
<div role="tabpanel" id="panel-2" aria-labelledby="tab-2" hidden>
    <p>Security settings content.</p>
</div>

<!-- Live region for dynamic updates -->
<div aria-live="polite" aria-atomic="true" class="sr-only" id="status">
    <!-- JS updates this text; screen readers announce it -->
</div>
```

### Keyboard Navigation and Focus Styling

```css
/* Never do this without a replacement: */
/* *:focus { outline: none; } */

/* Good: custom focus style that meets contrast requirements */
:focus-visible {
    outline: 3px solid #4A90D9;
    outline-offset: 2px;
}

/* Remove outline only for mouse users, keep for keyboard */
:focus:not(:focus-visible) {
    outline: none;
}
```

### Visually Hidden Text (Screen Reader Only)

```css
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}
```

### Language Attribute

```html
<!-- Set the page language -->
<html lang="en">

<!-- Mark sections in a different language -->
<p>The French word <span lang="fr">bonjour</span> means hello.</p>
```

---

## Performance Optimization

Static HTML sites are fast by default -- no server-side rendering overhead. But
poor asset loading strategy can still tank performance.

### Script Placement and Loading

```html
<!-- BAD: blocks HTML parsing -->
<head>
    <script src="analytics.js"></script>
    <script src="app.js"></script>
</head>

<!-- GOOD: defer -- downloads in parallel, executes after HTML is parsed -->
<head>
    <script src="app.js" defer></script>
</head>

<!-- GOOD: async -- downloads in parallel, executes as soon as downloaded -->
<!-- Use for independent scripts like analytics -->
<head>
    <script src="analytics.js" async></script>
</head>

<!-- ACCEPTABLE: scripts at end of body (legacy approach) -->
<body>
    <!-- ... page content ... -->
    <script src="app.js"></script>
</body>
```

**When to use which:**

| Attribute | Download | Execution | Use For |
|---|---|---|---|
| (none) | Blocks parsing | Blocks parsing | Almost never |
| `defer` | Parallel | After HTML parsed, before DOMContentLoaded | App code, DOM-dependent scripts |
| `async` | Parallel | As soon as downloaded (can interrupt parsing) | Analytics, ads, independent widgets |
| End of `<body>` | After HTML parsed | After HTML parsed | Legacy fallback |

### CSS and Resource Loading

```html
<head>
    <!-- Critical CSS inline (above-the-fold styles) -->
    <style>
        /* Minimal styles for above-the-fold content */
        body { margin: 0; font-family: system-ui, sans-serif; }
        .header { background: #1a1a2e; color: #fff; padding: 1rem; }
        .hero { padding: 4rem 2rem; text-align: center; }
    </style>

    <!-- Full stylesheet (non-blocking with preload + onload swap) -->
    <link rel="preload" href="styles.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
    <noscript><link rel="stylesheet" href="styles.css"></noscript>

    <!-- Or just load it normally (blocks rendering but simpler) -->
    <link rel="stylesheet" href="styles.css">
</head>
```

### Preconnect and Preload Link Hints

```html
<head>
    <!-- Preconnect: establish early connections to important third-party origins -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="preconnect" href="https://www.googletagmanager.com">

    <!-- DNS prefetch: lighter than preconnect, for less critical origins -->
    <link rel="dns-prefetch" href="https://cdn.example.com">
    <link rel="dns-prefetch" href="https://www.google-analytics.com">

    <!-- Preload: fetch critical resources early -->
    <link rel="preload" href="hero.webp" as="image">
    <link rel="preload" href="/fonts/brand-font.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="critical.css" as="style">
</head>
```

**Rules of thumb:**
- `preconnect` -- use for origins you will definitely fetch from (max 2-4)
- `dns-prefetch` -- use for origins you might fetch from
- `preload` -- use for critical resources the browser cannot discover early (fonts, hero images referenced in CSS)

### Font Loading

```html
<head>
    <!-- Preconnect to Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

    <!-- Load the font with display=swap to prevent FOIT (flash of invisible text) -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap"
          rel="stylesheet">
</head>
```

For self-hosted fonts:

```css
@font-face {
    font-family: 'BrandFont';
    src: url('/fonts/brand-font.woff2') format('woff2'),
         url('/fonts/brand-font.woff') format('woff');
    font-weight: 400;
    font-style: normal;
    font-display: swap; /* Show fallback text immediately, swap when font loads */
}

@font-face {
    font-family: 'BrandFont';
    src: url('/fonts/brand-font-bold.woff2') format('woff2'),
         url('/fonts/brand-font-bold.woff') format('woff');
    font-weight: 700;
    font-style: normal;
    font-display: swap;
}
```

**`font-display` values:**

| Value | Behaviour |
|---|---|
| `swap` | Show fallback immediately, swap when loaded. Best for body text. |
| `optional` | Show fallback immediately, swap only if font loads very quickly. Best for non-critical fonts. |
| `fallback` | Brief invisible period (100ms), then fallback, then swap. |
| `block` | Invisible text for up to 3s. Avoid unless font is critical for branding. |
| `auto` | Browser decides. Unpredictable -- avoid. |

### Minification Tools

For static sites without a build step, use online tools or one-off CLI commands:

```bash
# HTML (html-minifier-terser)
npx html-minifier-terser --collapse-whitespace --remove-comments \
    --remove-redundant-attributes --minify-css true --minify-js true \
    -o index.min.html index.html

# CSS (clean-css)
npx clean-css-cli -o styles.min.css styles.css

# JavaScript (terser)
npx terser app.js -o app.min.js --compress --mangle
```

Or use online tools:
- HTML: https://kangax.github.io/html-minifier/
- CSS: https://cssnano.github.io/cssnano/playground/
- JS: https://terser.org/

### Critical CSS Inline Technique

Extract the CSS needed for above-the-fold content and inline it:

```html
<head>
    <!-- Inline critical styles for instant first paint -->
    <style>
        *,*::before,*::after{box-sizing:border-box}
        body{margin:0;font-family:system-ui,-apple-system,sans-serif;line-height:1.6;color:#333}
        .header{background:#1a1a2e;color:#fff;padding:1rem 2rem;display:flex;align-items:center;justify-content:space-between}
        .hero{padding:4rem 2rem;text-align:center;background:#f8f9fa}
        .hero h1{font-size:2.5rem;margin:0 0 1rem}
    </style>

    <!-- Load the full stylesheet without blocking render -->
    <link rel="preload" href="styles.css" as="style"
          onload="this.onload=null;this.rel='stylesheet'">
    <noscript><link rel="stylesheet" href="styles.css"></noscript>
</head>
```

Tool to extract critical CSS automatically:

```bash
npx critical index.html --base . --inline --minify > index-critical.html
```

---

## Analytics Integration

### Google Analytics 4 (gtag.js)

Place this in the `<head>` of every page. Use `async` so it does not block
rendering.

```html
<head>
    <!-- Google Analytics 4 -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', 'G-XXXXXXXXXX');
    </script>
</head>
```

Replace `G-XXXXXXXXXX` with your Measurement ID from Google Analytics.

### Google Tag Manager

If you need more than basic analytics (event tracking, A/B testing, marketing
pixels), use Google Tag Manager instead of raw gtag.js.

```html
<head>
    <!-- Google Tag Manager -->
    <script>
    (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
    new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer','GTM-XXXXXXX');
    </script>
</head>

<body>
    <!-- Google Tag Manager (noscript fallback) -->
    <noscript>
        <iframe src="https://www.googletagmanager.com/ns.html?id=GTM-XXXXXXX"
                height="0" width="0" style="display:none;visibility:hidden"></iframe>
    </noscript>

    <!-- ... rest of page ... -->
</body>
```

Replace `GTM-XXXXXXX` with your GTM Container ID.

### Event Tracking Basics

Track clicks, form submissions, and other user interactions:

```html
<!-- Track a button click -->
<button onclick="gtag('event', 'click', {
    event_category: 'CTA',
    event_label: 'Hero Sign Up Button'
});">Sign Up Free</button>

<!-- Better: add event listeners in a script file -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    // Track CTA clicks
    document.querySelectorAll('[data-track]').forEach(function(el) {
        el.addEventListener('click', function() {
            gtag('event', 'click', {
                event_category: this.dataset.trackCategory || 'general',
                event_label: this.dataset.track
            });
        });
    });

    // Track form submissions
    document.querySelectorAll('form[data-track-form]').forEach(function(form) {
        form.addEventListener('submit', function() {
            gtag('event', 'form_submit', {
                event_category: 'form',
                event_label: this.dataset.trackForm
            });
        });
    });

    // Track outbound link clicks
    document.querySelectorAll('a[href^="http"]').forEach(function(link) {
        if (link.hostname !== window.location.hostname) {
            link.addEventListener('click', function() {
                gtag('event', 'click', {
                    event_category: 'outbound',
                    event_label: this.href,
                    transport_type: 'beacon'
                });
            });
        }
    });
});
</script>
```

Usage in HTML:

```html
<button data-track="Hero CTA" data-track-category="CTA">Get Started</button>
<a href="/pricing" data-track="Pricing Link" data-track-category="navigation">View Pricing</a>
<form data-track-form="Contact Form" action="/submit" method="POST">
    <!-- form fields -->
</form>
```

### Loading Strategy

- Place analytics scripts in the `<head>` with `async`
- GTM script must be in the `<head>` (before other scripts) for it to manage
  tags correctly
- The `async` attribute ensures analytics never blocks page rendering
- Use `transport_type: 'beacon'` on outbound link events so the event fires
  even when navigating away

---

## Common Pitfalls

Issues FAT Agent frequently flags on static HTML sites.

### Missing DOCTYPE Declaration

```html
<!-- BAD: missing DOCTYPE triggers quirks mode -->
<html>
<head>...</head>
<body>...</body>
</html>

<!-- GOOD: HTML5 doctype -->
<!DOCTYPE html>
<html lang="en">
<head>...</head>
<body>...</body>
</html>
```

Without `<!DOCTYPE html>`, browsers render in quirks mode. CSS box model
calculations, default styles, and certain APIs behave differently. Always the
very first line of the file.

### Missing charset Meta Tag

```html
<!-- BAD: no charset -- browser guesses encoding, may display garbled text -->
<head>
    <title>My Page</title>
</head>

<!-- GOOD: charset declared before title (must be within first 1024 bytes) -->
<head>
    <meta charset="utf-8">
    <title>My Page</title>
</head>
```

### Missing Viewport Meta Tag

```html
<!-- BAD: no viewport -- mobile browsers render at desktop width and zoom out -->
<head>
    <meta charset="utf-8">
    <title>My Page</title>
</head>

<!-- GOOD: responsive viewport -->
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>My Page</title>
</head>
```

Do not include `maximum-scale=1` or `user-scalable=no` -- these disable pinch
zoom and are an accessibility violation (WCAG 1.4.4).

### Images Without Dimensions

```html
<!-- BAD: causes CLS -- browser doesn't know the size until image loads -->
<img src="photo.jpg" alt="Photo">

<!-- GOOD: dimensions set, browser reserves space -->
<img src="photo.jpg" alt="Photo" width="800" height="600">
```

Combined with CSS:

```css
img {
    max-width: 100%;
    height: auto;
}
```

### Render-Blocking Scripts in Head

```html
<!-- BAD: blocks HTML parsing -->
<head>
    <script src="jquery.min.js"></script>
    <script src="plugins.js"></script>
    <script src="app.js"></script>
</head>

<!-- GOOD: non-blocking -->
<head>
    <script src="app.js" defer></script>
</head>

<!-- Or move to end of body -->
<body>
    <!-- content -->
    <script src="app.js"></script>
</body>
```

### External Fonts Without font-display

```css
/* BAD: invisible text until font loads (FOIT) */
@font-face {
    font-family: 'CustomFont';
    src: url('font.woff2') format('woff2');
}

/* GOOD: shows fallback text immediately */
@font-face {
    font-family: 'CustomFont';
    src: url('font.woff2') format('woff2');
    font-display: swap;
}
```

When using Google Fonts, append `&display=swap` to the URL:

```html
<!-- BAD -->
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700" rel="stylesheet">

<!-- GOOD -->
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
```

### Mixed Content (HTTP Resources on HTTPS Page)

```html
<!-- BAD: loading HTTP resource on HTTPS page -- browser may block it -->
<img src="http://example.com/image.jpg" alt="Photo">
<script src="http://cdn.example.com/lib.js"></script>
<link rel="stylesheet" href="http://cdn.example.com/styles.css">

<!-- GOOD: use HTTPS or protocol-relative URLs -->
<img src="https://example.com/image.jpg" alt="Photo">
<script src="https://cdn.example.com/lib.js"></script>

<!-- ALSO GOOD: protocol-relative (inherits page protocol) -->
<img src="//example.com/image.jpg" alt="Photo">
```

Browsers block mixed active content (scripts, stylesheets) and may warn on
mixed passive content (images). Always use HTTPS for all external resources.

### Missing Favicon

```html
<!-- Browsers request /favicon.ico by default. Without one you get 404 errors
     in server logs and a missing icon in browser tabs. -->

<head>
    <!-- ICO for legacy support -->
    <link rel="icon" href="/favicon.ico" sizes="32x32">

    <!-- SVG favicon (modern browsers, supports dark mode) -->
    <link rel="icon" href="/icon.svg" type="image/svg+xml">

    <!-- Apple touch icon (iOS home screen) -->
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">

    <!-- Web app manifest (Android, PWA) -->
    <link rel="manifest" href="/site.webmanifest">
</head>
```

Recommended sizes:
- `favicon.ico` -- 32x32 (or multi-size ICO with 16x16, 32x32, 48x48)
- `apple-touch-icon.png` -- 180x180
- SVG -- scalable, single file, supports `prefers-color-scheme`

Generate favicons from a single source image:
https://realfavicongenerator.net/

---

## Complete HTML Boilerplate

A production-ready HTML template with all essentials baked in. Copy this as a
starting point for every page.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <!-- Page title (50-60 characters, keyword-first) -->
    <title>Page Title - Context | Brand Name</title>

    <!-- Meta description (150-160 characters) -->
    <meta name="description" content="Concise, compelling page description with a call-to-action. Unique per page.">

    <!-- Canonical URL -->
    <link rel="canonical" href="https://example.com/page-url">

    <!-- Open Graph -->
    <meta property="og:title" content="Page Title for Social Sharing">
    <meta property="og:description" content="Description shown when shared on social media.">
    <meta property="og:image" content="https://example.com/images/share-image.jpg">
    <meta property="og:url" content="https://example.com/page-url">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Brand Name">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Page Title for Twitter">
    <meta name="twitter:description" content="Description shown on Twitter cards.">
    <meta name="twitter:image" content="https://example.com/images/share-image.jpg">

    <!-- Favicon -->
    <link rel="icon" href="/favicon.ico" sizes="32x32">
    <link rel="icon" href="/icon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <link rel="manifest" href="/site.webmanifest">

    <!-- Preconnect to critical third-party origins -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

    <!-- Fonts (with display=swap) -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap"
          rel="stylesheet">

    <!-- Preload LCP image -->
    <link rel="preload" as="image" href="/images/hero.webp" fetchpriority="high">

    <!-- Critical CSS (inline) -->
    <style>
        *, *::before, *::after { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            line-height: 1.6;
            color: #1a1a1a;
            background: #fff;
        }
        img { max-width: 100%; height: auto; display: block; }
        .skip-link {
            position: absolute;
            top: -40px;
            left: 0;
            background: #1a1a2e;
            color: #fff;
            padding: 8px 16px;
            z-index: 100;
            transition: top 0.2s;
        }
        .skip-link:focus { top: 0; }
        .sr-only {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }
        :focus-visible {
            outline: 3px solid #4A90D9;
            outline-offset: 2px;
        }
        :focus:not(:focus-visible) { outline: none; }
    </style>

    <!-- Full stylesheet (non-render-blocking) -->
    <link rel="preload" href="/css/styles.css" as="style"
          onload="this.onload=null;this.rel='stylesheet'">
    <noscript><link rel="stylesheet" href="/css/styles.css"></noscript>

    <!-- Google Analytics 4 -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', 'G-XXXXXXXXXX');
    </script>

    <!-- Structured Data -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Brand Name",
        "url": "https://example.com",
        "potentialAction": {
            "@type": "SearchAction",
            "target": "https://example.com/search?q={search_term_string}",
            "query-input": "required name=search_term_string"
        }
    }
    </script>
</head>

<body>
    <!-- Skip to content (accessibility) -->
    <a href="#main" class="skip-link">Skip to content</a>

    <!-- Header -->
    <header>
        <nav aria-label="Primary">
            <a href="/" aria-label="Brand Name - Home">
                <img src="/images/logo.svg" alt="Brand Name" width="150" height="40">
            </a>
            <ul>
                <li><a href="/">Home</a></li>
                <li><a href="/about">About</a></li>
                <li><a href="/services">Services</a></li>
                <li><a href="/blog">Blog</a></li>
                <li><a href="/contact">Contact</a></li>
            </ul>
        </nav>
    </header>

    <!-- Main content -->
    <main id="main">
        <!-- Hero section with optimised LCP image -->
        <section aria-labelledby="hero-heading">
            <h1 id="hero-heading">Page Heading Goes Here</h1>
            <p>Supporting text that explains the value proposition.</p>
            <a href="/get-started">Get Started</a>

            <picture>
                <source srcset="/images/hero.avif" type="image/avif">
                <source srcset="/images/hero.webp" type="image/webp">
                <img src="/images/hero.jpg"
                     alt="Descriptive alt text for the hero image"
                     width="1200" height="675"
                     fetchpriority="high">
            </picture>
        </section>

        <!-- Content sections -->
        <section aria-labelledby="features-heading">
            <h2 id="features-heading">Features</h2>

            <article>
                <h3>Feature One</h3>
                <img src="/images/feature-1.webp"
                     alt="Description of feature one illustration"
                     width="600" height="400"
                     loading="lazy">
                <p>Feature description goes here.</p>
            </article>

            <article>
                <h3>Feature Two</h3>
                <img src="/images/feature-2.webp"
                     alt="Description of feature two illustration"
                     width="600" height="400"
                     loading="lazy">
                <p>Feature description goes here.</p>
            </article>
        </section>
    </main>

    <!-- Footer -->
    <footer>
        <nav aria-label="Footer">
            <ul>
                <li><a href="/privacy">Privacy Policy</a></li>
                <li><a href="/terms">Terms of Service</a></li>
                <li><a href="/sitemap.xml">Sitemap</a></li>
            </ul>
        </nav>
        <p>&copy; 2025 Brand Name. All rights reserved.</p>
    </footer>

    <!-- Non-critical JavaScript -->
    <script src="/js/app.js" defer></script>
</body>
</html>
```

### Checklist

Before shipping, verify every page has:

- [ ] `<!DOCTYPE html>`
- [ ] `<html lang="en">` (correct language code)
- [ ] `<meta charset="utf-8">` (first thing in `<head>`)
- [ ] `<meta name="viewport" ...>` (no zoom disabling)
- [ ] Unique `<title>` (50-60 characters)
- [ ] Unique `<meta name="description">` (150-160 characters)
- [ ] `<link rel="canonical">` with absolute URL
- [ ] Open Graph tags (title, description, image, url, type)
- [ ] Twitter Card tags
- [ ] Favicon (ICO + SVG + apple-touch-icon)
- [ ] Structured data (JSON-LD, validated)
- [ ] All images have `alt`, `width`, `height`
- [ ] Below-fold images have `loading="lazy"`
- [ ] LCP image has `fetchpriority="high"`
- [ ] Scripts use `defer` or `async`
- [ ] Fonts use `font-display: swap`
- [ ] Preconnect to critical third-party origins
- [ ] Skip-to-content link
- [ ] Semantic HTML (`header`, `nav`, `main`, `footer`)
- [ ] Form inputs have labels
- [ ] Focus styles not removed
- [ ] No mixed content (all resources over HTTPS)
- [ ] Analytics installed and verified
