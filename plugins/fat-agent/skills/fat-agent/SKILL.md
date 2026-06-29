---
name: fat-agent
description: >
  FAT Agent with Superpowers (Fix, Audit, Test) — a post-launch quality
  assurance agent that systematically audits deployed websites and web
  applications using modular, auto-detected check categories. Triggers whenever
  a user mentions "FAT agent", "post-launch audit", "site audit", "audit my site",
  "check my deployment", "post-deploy check", "QA my site", "launch checklist",
  or any request to review a live or recently deployed website for issues.
  Also triggers after a successful deploy (on any platform — Netlify, Vercel,
  Cloudflare Pages, AWS, shared hosting, whatever) when the user asks "what
  should I check" or "is everything working". Use this skill proactively when
  a deploy just completed and the user hasn't run any post-launch checks yet.
---

# FAT Agent with Superpowers — Fix, Audit, Test

A post-launch quality assurance agent that performs a comprehensive, modular
audit of deployed websites and guides users through fixing every issue found.

FAT stands for **Fix -> Audit -> Test** — the three phases the agent cycles
through until the site scores clean.

## Philosophy

Most post-launch issues fall into predictable categories. Rather than relying on
the user to know what to check, FAT Agent with Superpowers takes the lead — it
asks targeted questions, auto-detects which modules are relevant, runs automated
checks where possible, and builds a prioritised punch list. Think of it as a
seasoned QA engineer sitting beside you after every deploy.

---

## When to Trigger

Activate FAT Agent with Superpowers when:
- A user says "run FAT agent", "audit my site", "post-launch check", etc.
- A deploy just succeeded (on any hosting platform) and the user asks "is it good?" or similar
- The user pastes a URL and asks Claude to "check it" or "review it"
- After any deploy, if the user hasn't mentioned running QA

---

## Phase 0 — Gather Context & Module Detection

Before auditing anything, FAT Agent with Superpowers needs to understand the
project and determine which audit modules to run.

### Step 1: Collect Project Details

Ask the user for the following (skip anything already known from conversation
context or memory):

#### Required
1. **Live URL** — The production URL to audit (e.g., `https://example.com`)
2. **Site type** — What kind of site is this? (marketing site, SaaS app, e-commerce, blog, portfolio, landing page, web app, local business)
3. **Tech stack** — Framework/CMS (e.g., Next.js, WordPress, static HTML, Astro, etc.)
4. **Hosting platform** — Where is this deployed? (Netlify, Vercel, Cloudflare Pages, AWS, shared hosting, self-hosted, etc.) — this helps tailor fix suggestions to the right config format

#### Situational (ask only if relevant)
5. **Critical user flows** — What are the 2-3 most important things a visitor does? (e.g., "fill out contact form", "add to cart and checkout", "sign up")
6. **Target audience** — Who visits this site? (helps calibrate accessibility and performance expectations)
7. **Known issues** — Anything the user already knows is broken or unfinished?
8. **Previous audit results** — Has a FAT audit been run before? (check conversation history)

Present these as a friendly, concise intake form — not an interrogation. Group them
logically and use the ask_user_input tool where possible for bounded choices.

**Example opener:**
> Ready to run a FAT audit! I just need a few details to get started. What's the
> live URL, and what kind of site are we looking at?

### Step 2: Select Audit Profile

After gathering context, ask the user to select an audit profile:

> Which audit profile would you like to use?
> - **Quick scan** — SEO + Security only (fast, ~2 minutes)
> - **Full audit** — All modules enabled (thorough, ~10 minutes)
> - **Local business** — Core + Local SEO + Email + Links
> - **E-commerce** — Core + E-commerce + Links
> - **Custom** — Pick individual modules to enable/disable

Profiles are defined in `scripts/profiles.py`:

| Profile | Modules |
|---------|---------|
| `quick` | seo, security |
| `full` | seo, security, accessibility, performance, links, ecommerce, email_deliverability, i18n, local_seo, dns_infra, js_bundle |
| `local` | seo, security, accessibility, performance, local_seo, email_deliverability, links |
| `ecommerce` | seo, security, accessibility, performance, ecommerce, links |
| `custom` | User selects from all available modules |

If the user doesn't express a preference, default to **Full audit**.

### Step 3: Auto-Detection & Module Confirmation

After fetching the homepage HTML, run the auto-detection system
(`scripts/modules/__init__.py: detect_modules()`) to determine which conditional
modules are relevant. Detection uses HTML signal patterns:

- **E-commerce**: add-to-cart elements, Product JSON-LD, Shopify/WooCommerce markers
- **i18n**: hreflang tags, language switcher elements
- **Local SEO**: LocalBusiness JSON-LD, Google Maps embeds, tel: links
- **Email deliverability**: Contact forms, email input fields
- **Links**: Always enabled (universally useful)

Core modules (SEO, Security, Accessibility, Performance) always run regardless
of detection.

Show the user the detected module list and offer to toggle:

> Based on your site, I'll run these modules:
> - [core] SEO, Security, Accessibility, Performance
> - [detected] E-commerce, Links, Email Deliverability
> - [disabled] Local SEO, i18n, DNS & Infrastructure, JS Bundle Analysis
>
> Want to enable or disable any of these before I start?

Apply `force_enable` / `force_disable` overrides as requested, then proceed to
Phase 1.

---

## Phase 1 — AUDIT

Run checks in this order. Core modules (1.1-1.9) always run. Conditional
modules (1.10-1.15) run based on detection results from Phase 0. For each
category, use `web_fetch` on the live URL and analyse the response. Where
checks require visual inspection, ask the user targeted yes/no questions
rather than vague open-ended ones.

### Core Modules (always run)

### 1.1 — Availability & Response
- Fetch the homepage — does it return 200?
- Check response headers for caching, security headers, content-type
- Check for redirect chains (www vs non-www, http vs https)
- Measure approximate response time from fetch

### 1.2 — SEO Essentials
Fetch the HTML and check:
- `<title>` tag exists and is 50-60 characters (flag if < 30 or > 60)
- No duplicate `<title>` tags (common CMS/framework bug)
- `<meta name="description">` exists and is 150-160 characters (flag if < 70 or > 160)
- No duplicate meta descriptions
- Only one `<h1>` per page, no empty heading tags
- Heading hierarchy is logical (no skipped levels, e.g. `h1` -> `h3` missing `h2`)
- `<meta name="robots">` is not set to `noindex` (unless intentional)
- `<link rel="canonical">` is present and correct, no duplicate canonicals
- `<meta charset="UTF-8">` is present
- `<meta name="viewport">` has `width=device-width` (not just present — validated)
- Open Graph tags (`og:title`, `og:description`, `og:image`, `og:url`) are present
- `og:image` URL is captured for validation
- Twitter Card tags are present
- Structured data / JSON-LD is present (check for `<script type="application/ld+json">`)
- `<link rel="alternate" hreflang="...">` tags for multi-language sites
- `sitemap.xml` exists (fetch `/sitemap.xml`)
- `robots.txt` exists and is sensible (fetch `/robots.txt`)
- Favicon exists (`<link rel="icon">`)
- **IndexNow adoption**: Check if an IndexNow API key file exists at the site root (fetch `/{key}.txt` or look for IndexNow references in `robots.txt`). IndexNow notifies Bing/Yandex of content changes for faster indexing. If missing, flag as P2 and suggest adding a key file + robots.txt reference.
- **Meta descriptions on error paths**: If the site uses dynamic routes (Next.js, Nuxt, etc.), check that fallback/error metadata (e.g., "Product Not Found" pages) still includes a `description` — not just a `title`. Bing crawls stale URLs and flags pages without descriptions even on 404-like responses.
- **Noindex audit**: For any pages with `<meta name="robots" content="noindex">`, verify these are intentional (checkout, thank-you, admin pages = correct; SEO landing pages = wrong). Cross-reference against the sitemap — pages in the sitemap should never be noindex.
- **Thin content detection** — Flag pages with < 300 words of body text (excluding nav/footer). Thin pages are less likely to rank and may be flagged by search engines as low-quality.
- **Keyword in title/h1** — Track whether the `<title>` and `<h1>` share key terms. If they don't overlap at all, flag as P3 Low.
- **Internal link audit** — Count internal vs external links. Flag pages with zero internal links as P3.
- **URL structure** — Detect underscores (should be hyphens), uppercase characters, double slashes, and query parameters on content pages.
- **Image filename SEO** — Flag images with generic filenames (IMG_001, screenshot, image1). Descriptive filenames help image search.
- **Duplicate Open Graph detection** — Extend duplicate meta checks to `og:` properties. Duplicate `og:image` or `og:title` tags confuse social sharing crawlers.
- **robots.txt / sitemap cross-reference** — Check if `robots.txt` references the sitemap URL. If not, flag as P2.
- **Trailing slash consistency** — Detect if the canonical URL trailing slash pattern differs from the current page URL.
- **Self-referencing canonical validation** — Check if the canonical URL matches the page URL (it should be self-referencing unless intentionally different).
- **Orphan anchor text** — Flag links using "click here", "read more", "learn more" as poor anchor text (bad for SEO and accessibility).
- **rel=nofollow audit** — Count links with `nofollow`. Flag internal links with `nofollow` as a mistake (it wastes link equity).
- **Core Web Vitals via PageSpeed Insights API** — Fetch `https://www.googleapis.com/pagespeedonline/v5/runPagespeedTest?url={URL}&strategy=mobile` (no API key needed for basic usage). Extract LCP, CLS, INP/FID, FCP, TTFB, Speed Index. Flag any metric in "poor" range as P1, "needs improvement" as P2. Fetch `strategy=desktop` for comparison. Display as a CWV summary table.

Ask the user:
- "Does your mobile content match your desktop content? (Mobile-first indexing)"
- "Is Google Search Console configured for this domain?"

**SPA / Client-Side Rendering Caveat:**
Modern frameworks (Next.js, Nuxt, React, Angular, Svelte, Astro, Vite builds)
often render content client-side after hydration. `analyse-html.py` detects both
framework-specific markers (`__next`, `__nuxt`, `data-reactroot`, `/_next/`,
etc.) **and** generic client-rendered shells — a mount node (`#root`/`#app`) or
an ES-module bundle (e.g. Vite's `/assets/index-*.js`) combined with a near-empty
served `<body>`. The detected stack appears in `seo.spa_indicators` and
`seo.spa_detected`.

When an SPA is detected, several checks are downgraded:
- **Missing `<h1>`**: Downgraded from P0 Critical to P1 High
- **Skip navigation**: Downgraded from P2 Medium to P3 Low
- **SVG accessibility**: Downgraded from P2 Medium to P3 Low
- **Poor anchor text**: Annotated as possibly client-rendered

Additionally, the script cannot see HTTP response headers from static HTML files.
Use `--fetch --url <url>` to make a live HTTP request and score security headers
(HSTS, CSP, X-Content-Type-Options, etc.). Without `--fetch`, security header
checks are skipped and a note is added to the report.

**The render-gap check (do this for every SPA):**
The single most important thing to verify on an SPA is whether the *server
response* — what non-rendering crawlers actually receive — contains the SEO
signals, or whether they only appear after JavaScript runs. Bing, social/
link-preview bots, and Google-before-render see the server HTML. A page that
looks perfect in the browser can be an empty `<div id="root">` to a crawler.

Capture **both** versions and compare them:

1. Save the **raw server response** (the shell): `curl -sL <url> -o served.html`
2. Save the **browser-rendered DOM** (after JS runs) via browser automation:
   `document.documentElement.outerHTML` → `rendered.html`
3. Analyse the **rendered** DOM as the primary file (so accessibility, images,
   and performance reflect what users get) and pass the shell with `--served`:

   ```bash
   python scripts/analyse-html.py rendered.html \
       --served served.html --fetch --url https://example.com \
       | python scripts/calculate-score.py > ./.fat-work/scores.json
   ```

`analyse-html.py` adds a `render_gap` block (`content_client_only`,
`title_client_only`, `meta_description_client_only`, `canonical_client_only`,
`h1_client_only`, `structured_data_client_only`, plus a `severity`).
`calculate-score.py` then applies a **crawlability penalty** to the SEO score,
so the headline number reflects the crawler-facing reality — not the best-case
JS render. **Do not paper over this gap with a prose caveat; let the score and
the `render_gap` finding carry it.**

**Branch on site type — the same gap means different things:**
- **SEO-dependent sites** (marketing, blog, e-commerce, directory, local
  business, landing pages): a render gap is a **P0/P1 finding**. The fix is real
  server-side rendering or pre-rendering (SSG / SSR / prerender step) so each
  route ships its own `<head>` and content. Flag it as the top issue.
- **Apps behind auth** (dashboards, internal tools, SaaS app shells that aren't
  meant to rank): the gap is expected and **low/ignore**. Note it and move on —
  don't tank the score over it. State which branch you applied and why.

When an SPA is detected, also recommend the user verify in DevTools or using
browser automation tools rather than treating server-HTML-only findings as hard
failures *for content the page never intended crawlers to see*.

### 1.3 — Performance Indicators
From the HTML response, check:
- Total HTML size (flag if > 100KB)
- Number of render-blocking scripts in `<head>`
- Whether images use `loading="lazy"` where appropriate
- Image optimisation: `srcset` attributes, `<picture>` elements, modern formats (WebP/AVIF)
- Image dimensions: `width` and `height` attributes present (prevents CLS)
- Whether CSS is inlined or external (and count external stylesheets)
- Inline script/style size (flag if combined > 50KB — bypasses caching)
- Check for `<link rel="preconnect">` or `<link rel="preload">` hints
- Font loading: `font-display: swap` in inline styles, Google Fonts preconnect, font preloads

**Performance Budgets:**
If a `.fat-budget.json` file exists in the project root, use it to check custom
thresholds. Otherwise, apply sensible defaults (HTML < 100KB, inline < 50KB,
render-blocking scripts <= 2, external scripts <= 15). See `references/performance-budgets.md`
for configuration details.

Ask: "Would you like to configure custom performance budgets for this project?"

**Then suggest**: "For a deeper performance audit, I recommend running your URL
through Google PageSpeed Insights — would you like me to search for your latest
scores?"

### 1.4 — Security Headers & Mixed Content
Check response headers for:
- `Strict-Transport-Security` (HSTS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options` or `Content-Security-Policy` frame-ancestors
- `Referrer-Policy`
- `Permissions-Policy`

From the HTML, check:
- Mixed content: `http://` resources (images, scripts, stylesheets) loaded on an HTTPS page
- External links with `target="_blank"` have `rel="noopener"` (security + performance)

### 1.5 — Accessibility Quick Scan
From the HTML, check:
- All `<img>` tags have `alt` attributes (not just present — non-empty and meaningful)
- **Dynamic alt text fallbacks**: If the codebase is available, check that Image components using dynamic data (e.g., `alt={product.name}`) include fallbacks like `alt={product.name || 'Product image'}`. Without fallbacks, undefined/null values produce images with no alt attribute at all. This is a common source of bulk alt-text failures (Bing reported 439 missing alt errors on one site from this pattern alone).
- Images have explicit `width` and `height` attributes (CLS prevention)
- Form inputs have associated `<label>` elements or `aria-label`
- `<html lang="...">` attribute is set
- Skip links present for keyboard navigation
- ARIA landmarks used (`<main>`, `<nav>`, `<header>`, `<footer>`)
- No empty heading tags (`<h2></h2>`, `<h3>   </h3>`)
- Same-page anchor links (`href="#section"`) point to existing element IDs

**Extended automated checks:**
- **ARIA role validation** — Detect invalid or deprecated ARIA roles (e.g., `role="directory"` is deprecated)
- **tabindex > 0 detection** — Flag positive tabindex values (disrupts natural tab order — bad practice)
- **Autoplay media** — Detect `<video autoplay>` and `<audio autoplay>` without `muted` (P1 High)
- **Zoom disabled** — Detect `user-scalable=no` or `maximum-scale=1` in viewport meta (P0 Critical — blocks assistive technology)
- **Button vs link semantics** — Detect `<a>` with `role="button"` (flag for review)
- **Table accessibility** — Detect `<table>` without `<th>` header cells
- **SVG accessibility** — Detect `<svg>` without `<title>` or `aria-label`
- **iframe titles** — Detect `<iframe>` without `title` attribute
- **Form error association** — Check for `aria-describedby` / `aria-errormessage` usage
- **Motion preference** — Detect `prefers-reduced-motion` in inline styles/media queries
- **Fake affordance detection** — Detect non-interactive elements (`<div>`, `<span>`) with interactive styling (hover effects, cursor:pointer, button/link CSS classes) that lack `href`, `onclick`, or appropriate ARIA roles. These elements look clickable but do nothing — a UX trap that frustrates users and harms accessibility. Flag as P1 High.

Ask the user:
- "Are you using low-contrast text anywhere (light grey on white, etc.)?"
- "Have you disabled the default focus outline on interactive elements without adding a custom one?"
- "Do you have reduced motion alternatives for animations?"
- "Have you tested with a screen reader?"
- "Are interactive elements at least 44x44px touch targets?"
- "Do you have error messages associated with form fields using aria-describedby?"

### 1.6 — Functional Checks (User-Guided)
These can't be automated — ask the user to verify:
- [ ] All navigation links work
- [ ] Contact forms submit successfully (and confirmation appears)
- [ ] Email notifications are received (from forms, signups, etc.)
- [ ] Mobile responsiveness looks correct on phone and tablet
- [ ] Social sharing links work
- [ ] Any third-party integrations are functioning (analytics, chat widgets, etc.)
- [ ] 404 page is set up and styled
- [ ] Cookies/GDPR banner appears if required for their region
- [ ] All elements that look clickable are actually clickable (no fake affordances)

Present these as a checklist with the ask_user_input tool, grouped into batches
of 3-4 so it's not overwhelming.

### 1.7 — Content, Legal & Privacy
- Check for placeholder/lorem ipsum text in the HTML
- Detect cookie/consent management scripts (Cookiebot, OneTrust, CookieYes, Termly, iubenda, TrustArc, Quantcast Choice)
- If no consent banner detected and site targets EU/UK/CA, ask: "Do you need a cookie consent banner for GDPR/CCPA compliance?"
- Ask: "Is your privacy policy linked in the footer?"
- Ask: "Is your copyright year current?"
- Ask: "Are all team photos, logos, and images final (no placeholders)?"

### 1.8a — PWA / Web App Readiness
Check the HTML for:
- `<link rel="manifest">` (web app manifest)
- `<meta name="theme-color">` for browser chrome theming
- `<link rel="apple-touch-icon">` for iOS home screen
- Service worker registration (`navigator.serviceWorker.register`)
- If none found and the site is a web app, suggest adding these for "Add to Home Screen" support

### 1.8b — Analytics & Tracking
Check the HTML for known analytics providers (detected automatically):
- **Tier 1:** Google Analytics/GA4/GTM, Facebook Pixel, Hotjar, Plausible
- **Privacy-focused:** Fathom Analytics, Umami, Matomo
- **Product analytics:** Mixpanel, Heap, Segment, Amplitude, PostHog
- **Platform-specific:** Vercel Analytics, Cloudflare Web Analytics, Adobe Analytics
- **Ad pixels:** Snapchat Pixel, TikTok Pixel, LinkedIn Insight Tag, Pinterest Tag, Reddit Pixel
- **Consent management:** Cookiebot, OneTrust, CookieYes, Termly, iubenda, TrustArc, Osano, CookieFirst, Complianz, Quantcast Choice, Microsoft Clarity
- If none found, ask: "I don't see any analytics installed — is that intentional?"

### 1.9 — Platform-Specific Checks

Run these checks **conditionally** based on the hosting platform identified in Phase 0.
Only execute the section matching the user's declared platform. If the platform is unknown
or not listed, run the Generic checks.

**Netlify:**
- Check for `_headers` file in the deploy (ask user or inspect response headers)
- Check for `_redirects` file or `[[redirects]]` in `netlify.toml`
- Ask: "Are you using Netlify Forms? If so, is the `data-netlify="true"` attribute on your form tag?"
- Ask: "Have you checked your deploy preview vs production — are they consistent?"
- Suggest enabling Netlify's asset optimization (CSS/JS minification, image compression)
- Reference: `references/platform-fixes/netlify.md`

**Vercel:**
- Check if response headers indicate Vercel (`x-vercel-id`, `server: Vercel`)
- Ask: "Do you have a `vercel.json` with custom headers configured?"
- Ask: "Are you using Vercel Middleware for redirects or auth?"
- Check for Edge Function headers (`x-middleware-*`)
- Suggest Vercel Analytics / Speed Insights if not detected
- Reference: `references/platform-fixes/vercel.md`

**Cloudflare Pages:**
- Check if response headers indicate Cloudflare (`cf-ray`, `server: cloudflare`)
- Ask: "Do you have a `_headers` and `_redirects` file in your build output?"
- Warn about Rocket Loader potentially breaking inline scripts
- Check for Cloudflare-specific features (Auto Minify, Polish, etc.)
- Reference: `references/platform-fixes/cloudflare-pages.md`

**WordPress:**
- Check for `/wp-admin/` accessibility (should redirect to login, not expose admin)
- Check for `/xmlrpc.php` (should return 403 or 405, not 200)
- Ask: "Are all your plugins and themes up to date?"
- Check for `wp-json` REST API exposure
- Check for user enumeration via `/?author=1`
- Reference: `references/platform-fixes/wordpress.md`

**Apache:**
- Ask: "Do you have a `.htaccess` file with security headers?"
- Check if `mod_rewrite` is handling redirects correctly
- Ask: "Is directory listing disabled?"
- Check for server version exposure in headers (`Server: Apache/x.x.x`)
- Reference: `references/platform-fixes/apache.md`

**Nginx:**
- Check if server header exposes version (`Server: nginx/x.x.x` — should be hidden)
- Ask: "Are your security headers configured in the server block?"
- Check for proper `try_files` configuration (SPA routing)
- Reference: `references/platform-fixes/nginx.md`

**AWS (S3/CloudFront/Amplify):**
- Check for CloudFront headers (`x-amz-cf-id`, `x-cache`)
- Ask: "Do you have a CloudFront Response Headers Policy configured?"
- Check that S3 bucket is not directly publicly accessible
- Verify custom error pages are configured
- Reference: `references/platform-fixes/aws.md`

**Generic (any platform):**
- Verify SSL certificate is valid and not expiring soon
- Check www vs non-www consistency (both should resolve, one should redirect)
- Check custom domain is properly configured (no CNAME/A record issues)
- Check that HTTP redirects to HTTPS

### Conditional Modules (run when detected/enabled)

### 1.10 — Local SEO Checks (module: `local_seo`)

Enabled when: LocalBusiness JSON-LD detected, Google Maps embed found, `tel:` links
present, site type is "local business" or "landing page", or user manually enables.

Uses `scripts/modules/local_seo.py`. Checks:
- LocalBusiness JSON-LD schema present with correct `@type` subtype
- NAP (Name, Address, Phone) consistency in schema
- Google Maps embed present and functional
- Click-to-call `tel:` links present and valid
- WhatsApp link present (if applicable)
- Google Business Profile (GBP) link present
- Service area defined in schema
- Opening hours (`openingHoursSpecification`) in schema
- Review/aggregate rating schema present
- Trust signals (testimonials, certifications, badges)
- Prominent CTAs (call, directions, book)
- Directions link to Google Maps
- Reference: `references/local-seo-checklist.md`

### 1.11 — E-commerce Checks (module: `ecommerce`)

Enabled when: Product JSON-LD detected, add-to-cart elements found,
Shopify/WooCommerce markers present, site type is "e-commerce", or user
manually enables.

Uses `scripts/modules/ecommerce.py`. Checks:
- Product structured data (JSON-LD with `@type: Product`)
- Price display elements detected
- Cart/add-to-cart functionality elements present
- Payment trust signals (Visa, Mastercard, PayPal, Stripe, Klarna badges)
- Breadcrumb schema for product navigation
- SSL trust badges
- Reference: `references/ecommerce-checklist.md`

### 1.12 — Email Deliverability (module: `email_deliverability`)

Enabled when: Contact forms detected, email input fields found, or user
manually enables.

Uses `scripts/modules/email_deliverability.py`. Checks:
- **SPF record** — DNS TXT lookup for `v=spf1` on the domain
- **DKIM record** — DNS TXT lookup for common selectors (google, default, selector1, mail, k1)
- **DMARC record** — DNS TXT lookup for `_dmarc.{domain}`, policy evaluation (reject > quarantine > none)
- Flags missing records as P1 High (emails likely going to spam)

### 1.13 — i18n Checks (module: `i18n`)

Enabled when: `hreflang` tags detected, language switcher elements found,
or user manually enables.

Uses `scripts/modules/i18n.py`. Checks:
- `hreflang` tags present and valid (ISO 639-1 codes)
- `x-default` hreflang present (required for multi-language)
- Self-referencing hreflang on each language version
- `<html lang="...">` attribute matches content language
- `Content-Language` response header present
- Locale routing patterns (e.g., `/en/`, `/fr/`)
- RTL support detection (for Arabic, Hebrew, etc.)
- No orphaned language versions (hreflang pointing to non-existent pages)

### 1.14 — DNS & Infrastructure (module: `dns_infra`)

Enabled when: User selects "Full audit" profile or manually enables. Not
auto-detected from HTML — this is an opt-in deep check.

Uses `scripts/modules/dns_infra.py`. Checks:
- **DNSSEC** — Verify DNSSEC is configured for the domain
- **CAA records** — Check Certificate Authority Authorization records exist
- **SSL certificate expiry** — Flag if certificate expires within 30 days (P1), 14 days (P0)
- **CDN detection** — Identify CDN provider from response headers
- **HTTP/2 support** — Verify the server supports HTTP/2

### 1.15 — JS Bundle Analysis (module: `js_bundle`)

Enabled when: User selects "Full audit" profile or manually enables. Runs
HTML-level JavaScript analysis without requiring source maps.

Uses `scripts/modules/js_bundle.py`. Checks:
- Total external script count (flag if > 15)
- Heavy library detection (moment.js, full lodash, etc. — suggest lighter alternatives)
- Inline script total size (flag if > 50KB)
- Bundler pattern detection (webpack, Vite, Rollup, Parcel signatures)
- `async` / `defer` attribute usage on script tags
- ES module (`type="module"`) adoption
- Render-blocking script identification

---

## Phase 2 — FIX

After completing all audit checks, compile a **FAT Report** — a prioritised list
of findings.

### Priority Levels
| Priority | Label | Meaning |
|----------|-------|---------|
| P0 | **Critical** | Site is broken, inaccessible, or insecure |
| P1 | **High** | Significant SEO, performance, or UX impact |
| P2 | **Medium** | Best practice violations, minor issues |
| P3 | **Low** | Nice-to-haves, polish items |

### Report Format
Present findings grouped by priority, with each item containing:
1. **What's wrong** — One-line description
2. **Why it matters** — Impact explanation (keep it brief)
3. **How to fix** — Specific, actionable fix (with code snippets where possible)
4. **Effort** — Quick estimate (5 min, 30 min, 1+ hour)

**Example finding:**
> **P1 — Missing meta description**
> Your homepage has no `<meta name="description">` tag. Search engines will
> auto-generate a snippet, which usually looks terrible.
>
> **Fix:** Add to your `<head>`:
> ```html
> <meta name="description" content="Your compelling 155-character description here">
> ```
> **Effort:** 5 min

### Report Generation

After presenting the report in the chat, ALWAYS generate reports using the
Report & Chart Generation pipeline (see below). Generate all of:

1. **Word (.docx)** — Full technical report with findings matrix
2. **PowerPoint (.pptx)** — Executive summary with score cards and charts
3. **HTML dashboard** — Self-contained single-file HTML report with interactive
   score visualisation, sortable findings table, and expandable fix details.
   Generate using:
   ```bash
   python scripts/generate-report.py \
       --scores /tmp/scores.json \
       --url example.com \
       --charts-dir /tmp/charts \
       --brand assets/fat-agent-brand.png \
       --output-dir ./reports \
       --format html
   ```

**Client-facing mode (`--client-facing`):** When the user specifies
`--client-facing` or says "this is for a client", generate reports with:
- Professional language (no developer jargon)
- Priority labels shown as "Critical / High / Medium / Low" (no P0-P3 codes)
- Fix suggestions framed as recommendations, not direct code snippets
- Executive summary on the first page/slide
- Branding prominence increased (FAT Agent logo + client's URL)
- No references to internal scripts or tooling

Pass `--client-facing` to `generate-report.py` for all three formats.

Then ask: "Want me to help fix any of these now? I can generate the code changes
for the quick wins."

---

## Phase 3 — TEST

After fixes are applied and redeployed:

1. **Re-fetch the URL** and verify the specific issues that were fixed
2. **Report results** — "Fixed" or "Still present" for each item
3. **Update the punch list** — Remove resolved items, flag persistent ones
4. **Visual regression comparison** — If a previous audit's HTML/screenshots are
   available, compare key elements (header, hero, footer) for unintended visual
   changes introduced during fixes. Flag any significant layout shifts.
5. **Link checking results** — If the `links` module was enabled, report broken
   link status: total links checked, internal broken, external broken, redirect
   chains found. Show a summary table of any links returning 4xx/5xx status.
6. **Celebrate** — When all P0 and P1 items are resolved, congratulate the user:
   > "Your site passed the FAT audit! All critical and high-priority items are
   > resolved. Here's your final scorecard."

### Final Scorecard
After presenting the final scorecard, regenerate the Word, PowerPoint, and HTML
reports with updated scores (re-run the Report & Chart Generation pipeline).
Present a summary showing:
- Total issues found -> Total resolved
- Breakdown by priority
- Remaining items (if any) with a note about when to address them
- Overall FAT score: percentage of issues resolved weighted by priority

### FAT Badge
After presenting the final scorecard, generate a FAT badge and offer to add it
to the project:

1. **Generate the badge** — pipe the scores through the badge generator:
   ```bash
   python scripts/analyse-html.py page.html | python scripts/calculate-score.py | python scripts/generate-badge.py --image --output fat-badge.svg
   ```
   Save `fat-badge.svg` to the project root directory.

2. **Offer to update the README** — ask the user:
   > "Want me to add your FAT score badge to the README?"

   If yes, insert the badge image reference near the top of the project's README
   (after the title/heading, before the description). Use the format:
   ```markdown
   ![FAT Score](./fat-badge.svg)
   ```
   If the README already has a FAT badge reference, replace it (the score may
   have changed). Don't duplicate it.

3. **Offer to commit** — ask the user:
   > "Want me to commit the badge and README update?"

   If yes, stage `fat-badge.svg` and `README.md`, and commit with a message like:
   `Add FAT audit badge — <grade> <score>/100`

The badge includes the FAT Agent character with the overall grade bar and a
colour-coded category breakdown (SEO, Security, A11y, Perf). It uses a compact
128px icon (~23KB) so the SVG stays under ~35KB — safe for version control.

If the user declines the badge, skip it and move on. Don't push it.

### Historical Audit Tracking

After presenting the final scorecard, save the results to the audit history:

1. **Save to history** — Run:
   ```bash
   python scripts/track-history.py --save scores.json --url <URL>
   ```
   This appends the current scores to `.fat-history.json` in the project root.

2. **Show comparison** — On subsequent audits, load history and show improvement:
   ```bash
   python scripts/track-history.py --diff
   ```
   Example: "Your SEO score improved from 72 to 91 (+19) since the last audit on 14 March"

3. **Show trend** — Display score trajectory:
   ```bash
   python scripts/track-history.py --trend
   ```

4. **Offer to commit** — Ask if the user wants to commit `.fat-history.json` so the
   team can see audit history tracked in version control.

### CI/CD Integration

At the end of Phase 3, offer: "Would you like to set up automated FAT checks in
your CI/CD pipeline?" If yes, load `references/ci-cd-integration.md` for complete
examples for GitHub Actions, Netlify, Vercel, GitLab CI, and generic shell scripts.

---

## Multi-Page Crawling

FAT Agent with Superpowers supports crawling multiple pages on the same domain.
Use `scripts/crawl.py` for breadth-first discovery with robots.txt respect.

### Usage

When the user says "audit the whole site", "check all pages", or provides
`--depth` or `--max-pages` flags:

```bash
python scripts/crawl.py --url https://example.com --depth 2 --max-pages 20 --output /tmp/crawl.json
```

**Flags:**
- `--depth N` — Maximum link-following depth from the start URL (default: 2)
- `--max-pages N` — Maximum total pages to crawl (default: 10)
- `--output PATH` — Write the discovered URL list as JSON

The crawler:
1. Fetches the start URL and extracts all same-domain links
2. BFS traversal up to `--depth` levels, respecting `--max-pages` cap
3. Checks `robots.txt` and skips disallowed paths
4. Normalises URLs (lowercases, strips fragments, deduplicates)
5. Outputs a JSON array of discovered page URLs

After crawling, run the Phase 1 audit pipeline on each discovered page. Aggregate
findings across all pages and present a per-page breakdown alongside the
site-wide summary:

```
| Page              | SEO | Security | A11y | Perf | Score |
|-------------------|-----|----------|------|------|-------|
| /                 | 92  | 85       | 88   | 76   | 85    |
| /about            | 78  | 85       | 90   | 80   | 83    |
| /contact          | 65  | 85       | 72   | 82   | 76    |
| Site-wide average | 78  | 85       | 83   | 79   | 81    |
```

Flag pages that score significantly below the site average.

---

## Bulk Site Auditing (Portfolio Mode)

For agencies or developers managing multiple sites, FAT Agent with Superpowers
supports portfolio-wide auditing via `scripts/bulk_audit.py`.

### Usage

When the user says "audit all my sites", "portfolio audit", or provides
`--sites`:

```bash
python scripts/bulk_audit.py --sites sites.json --output-dir ./results --profile full
```

**Input format** (`sites.json`):
```json
[
  {"url": "https://example.com", "name": "Example Site"},
  {"url": "https://another.com", "name": "Another Site"}
]
```

**Flags:**
- `--sites PATH` — Path to the JSON file listing sites to audit
- `--output-dir PATH` — Directory for per-site result JSON files
- `--profile NAME` — Audit profile to apply to all sites (default: `full`)

**Output:**
- Per-site JSON score files in `--output-dir`
- `portfolio_summary.json` — Aggregated scores for all sites
- Console comparison table showing all sites ranked by overall score

Present results as a portfolio dashboard:
```
| Site          | SEO | Security | A11y | Perf | Overall | Grade |
|---------------|-----|----------|------|------|---------|-------|
| Example Site  | 92  | 100      | 88   | 76   | 89      | A     |
| Another Site  | 65  | 85       | 72   | 80   | 76      | C     |
```

Highlight the weakest site and the weakest category across the portfolio.

---

## CI/CD Gate

For automated quality enforcement, FAT Agent with Superpowers includes
`scripts/ci_gate.py` — a standalone script that checks FAT scores against
thresholds and exits non-zero if the site fails.

### Usage in CI pipelines

```bash
# Run the audit pipeline
python scripts/analyse-html.py --url "$SITE_URL" page.html | \
    python scripts/calculate-score.py > scores.json

# Gate: fail if overall score < 70 or any P0 findings exist
python scripts/ci_gate.py --scores scores.json --threshold 70 --fail-on P0
```

**Flags:**
- `--scores PATH` — Path to the scored JSON from `calculate-score.py`
- `--threshold N` — Minimum overall score to pass (default: 60)
- `--fail-on P0` — Fail the build if any P0 Critical findings exist
- `--fail-on P1` — Fail the build if any P1 High findings exist

**Exit codes:**
- `0` — Passed all checks
- `1` — Score below threshold or priority findings detected

See `references/ci-cd-integration.md` for full GitHub Actions, GitLab CI, and
generic shell integration examples.

---

## Lighthouse Integration

When the Lighthouse CLI is available on the system, FAT Agent with Superpowers
can run a full Lighthouse audit to complement its HTML-level analysis.

### Usage

```bash
python scripts/lighthouse.py --url https://example.com --output /tmp/lighthouse_report.json
```

**What it provides:**
- Performance, Accessibility, Best Practices, and SEO scores (0-100)
- Core Web Vitals: LCP, CLS, INP, FCP, TTFB
- Results merged into the FAT report alongside HTML-level findings

**Integration with the audit pipeline:**
1. During Phase 1, check if `lighthouse` CLI is on PATH (`scripts/lighthouse.py: check_lighthouse_available()`)
2. If available, run Lighthouse against the URL
3. Merge Lighthouse scores into the scored JSON — use Lighthouse data for Performance
   and CWV metrics, which are more accurate than HTML-only analysis
4. If not available, fall back to PageSpeed Insights API and HTML-level checks (default behaviour)

Lighthouse results appear in the report as a dedicated "Lighthouse Scores" section
with the familiar red/orange/green score cards.

---

## Competitive Analysis Mode

**Trigger:** User says "compare my site with [competitor URL]" or "competitive analysis"

When triggered:

1. **Run Phase 1 audit on both URLs** — Fetch both pages and run `analyse-html.py` + `calculate-score.py` on each
2. **Generate side-by-side comparison**:
   ```
   | Category      | Your Site | Competitor | Delta |
   |---------------|-----------|------------|-------|
   | SEO           | 85        | 92         | -7    |
   | Security      | 100       | 65         | +35   |
   | Accessibility | 90        | 78         | +12   |
   | Performance   | 72        | 88         | -16   |
   | Overall       | 87        | 81         | +6    |
   ```
3. **Highlight areas where the user is behind** — Focus on categories with negative deltas
4. **Suggest specific improvements** — For each area the competitor scores higher, suggest actionable fixes
5. **Offer to generate fixes** — "Want me to help close the gap on SEO and Performance?"

Note: The competitive comparison uses the same automated HTML analysis. It cannot
see JavaScript-rendered content, so recommend both sites be checked with browser
tools for a complete picture.

---

## Ongoing Behaviour

- If the user deploys again in the same conversation, offer to re-run the audit
- Keep track of previously found issues — don't re-report things already flagged
- If the user asks "what's left?", show the current punch list status
- Be encouraging but honest — don't gloss over real issues

---

## Important Notes

- **Don't overwhelm**: Present findings in digestible batches if there are many
- **Be specific**: "Your title tag is 84 characters" not "Your title tag might be too long"
- **Offer to help fix**: Don't just report — offer to generate fixes
- **Respect the user's time**: Quick wins first, deep dives only if requested
- **Use conversation context**: If you know the tech stack, tailor your fix suggestions (e.g., Next.js Head component vs raw HTML)

---

## Reference Files

For extended check details, see:
- `references/security-headers.md` — Full security header recommendations
- `references/seo-checklist.md` — Extended SEO audit criteria
- `references/accessibility-guide.md` — WCAG 2.1 quick reference
- `references/local-seo-checklist.md` — Local SEO audit criteria
- `references/ecommerce-checklist.md` — E-commerce audit criteria
- `references/performance-budgets.md` — Performance budget configuration guide
- `references/ci-cd-integration.md` — CI/CD integration examples (GitHub Actions, Netlify, Vercel, etc.)
- `references/semrush-integration.md` — Optional SEMrush enrichment (API key setup + field reference)

### Scripts
- `scripts/analyse-html.py` — HTML analysis helper (extracts meta tags, headers, scripts)
- `scripts/calculate-score.py` — Scoring calculator (SEO, Security, Accessibility, FAT Score)
- `scripts/generate-badge.py` — SVG badge generator (character image + score bars)
- `scripts/generate-charts.py` — Chart image generator (traffic, keywords, scores, PageSpeed)
- `scripts/generate-report.py` — Word + PowerPoint + HTML report generator (branded, with charts)
- `scripts/track-history.py` — Historical audit tracker (read/write `.fat-history.json`)
- `scripts/crawl.py` — Multi-page BFS crawler with robots.txt support
- `scripts/bulk_audit.py` — Portfolio-wide bulk site auditor
- `scripts/ci_gate.py` — CI/CD quality gate (threshold + priority checks)
- `scripts/lighthouse.py` — Lighthouse CLI integration wrapper
- `scripts/pagespeed.py` — PageSpeed Insights API wrapper (Core Web Vitals)
- `scripts/semrush.py` — Optional SEMrush API enrichment → `semrush.json` (key from `SEMRUSH_API_KEY`)
- `scripts/profiles.py` — Audit profile definitions (quick, full, local, ecommerce, custom)
- `scripts/modules/` — Modular audit system:
  - `base.py` — `AuditModule` abstract base class
  - `__init__.py` — Module registry, detection engine, core/conditional module lists
  - `local_seo.py` — Local SEO checks
  - `ecommerce.py` — E-commerce checks
  - `email_deliverability.py` — SPF/DKIM/DMARC checks
  - `i18n.py` — Internationalisation checks
  - `dns_infra.py` — DNS & infrastructure checks
  - `js_bundle.py` — JavaScript bundle analysis
  - `links.py` — Link quality and broken link detection

### Platform-Specific Fix References
Load the relevant file based on the hosting platform from Phase 0:
- `references/platform-fixes/netlify.md` — Netlify config (_headers, netlify.toml, Forms)
- `references/platform-fixes/vercel.md` — Vercel config (vercel.json, middleware)
- `references/platform-fixes/cloudflare-pages.md` — Cloudflare Pages (_headers, Workers)
- `references/platform-fixes/apache.md` — Apache config (.htaccess, mod_rewrite)
- `references/platform-fixes/nginx.md` — Nginx config (server blocks, add_header)
- `references/platform-fixes/wordpress.md` — WordPress config (wp-config.php, plugins)
- `references/platform-fixes/aws.md` — AWS config (CloudFront, S3, Amplify)

### Framework-Specific Fix References
Load the relevant file based on the tech stack from Phase 0:
- `references/framework-fixes/nextjs.md` — Next.js (App Router + Pages Router)
- `references/framework-fixes/astro.md` — Astro (islands, content collections)
- `references/framework-fixes/sveltekit.md` — SvelteKit (load functions, adapters)
- `references/framework-fixes/nuxt.md` — Nuxt 3 (useHead, useSeoMeta)
- `references/framework-fixes/gatsby.md` — Gatsby (Head API, gatsby-plugin-image)
- `references/framework-fixes/wordpress.md` — WordPress themes (functions.php, hooks)
- `references/framework-fixes/static-html.md` — Static HTML/CSS/JS (no framework)

---

## Report & Chart Generation

**IMPORTANT:** After completing Phase 2 (FIX report), ALWAYS generate Word,
PowerPoint, and HTML reports. Do NOT just present findings in the chat — produce
downloadable, branded documents. This is a core deliverable of every FAT audit.

### Branding

The FAT Agent brand image is bundled at `assets/fat-agent-brand.png`. **Always**
use this image as the `--brand` argument when generating reports and charts. It
appears on:
- Word report cover page (large, centred)
- Word report footer (small)
- PowerPoint title slide (large, centred)
- PowerPoint header bar on every slide (small, left-aligned)
- PowerPoint closing slide (large, centred)
- HTML dashboard header

Resolve the path relative to the plugin directory. For example:
```python
import os
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND_IMAGE = os.path.join(PLUGIN_DIR, 'assets', 'fat-agent-brand.png')
```

### Workflow

After Phase 2 findings are compiled:

1. **Install dependencies** (if not already available):
   ```bash
   pip install matplotlib python-docx python-pptx Pillow
   ```

2. **Save the scored JSON** to a temp file:
   ```bash
   python scripts/analyse-html.py --headers headers.json page.html | \
       python scripts/calculate-score.py > /tmp/scores.json
   ```

3. **Generate charts** from the scored data (and optional SEMrush data):
   ```bash
   python scripts/generate-charts.py \
       --scores /tmp/scores.json \
       --semrush /tmp/semrush.json \
       --output-dir /tmp/charts \
       --font "Plus Jakarta Sans"
   ```

4. **Generate reports** with branding and embedded charts:
   ```bash
   python scripts/generate-report.py \
       --scores /tmp/scores.json \
       --semrush /tmp/semrush.json \
       --url example.com \
       --charts-dir /tmp/charts \
       --brand assets/fat-agent-brand.png \
       --output-dir ./reports \
       --font "Plus Jakarta Sans"
   ```

   For client-facing reports, add `--client-facing`:
   ```bash
   python scripts/generate-report.py \
       --scores /tmp/scores.json \
       --url example.com \
       --charts-dir /tmp/charts \
       --brand assets/fat-agent-brand.png \
       --output-dir ./reports \
       --client-facing
   ```

5. **Tell the user** where the reports are saved and offer to open them.

### Available Charts

| Chart | File | Data Source |
|---|---|---|
| FAT score bars + issues donut | `chart_fat_scores.png` | Scored JSON (always available) |
| PageSpeed mobile vs desktop | `chart_pagespeed.png` | Scored JSON + PageSpeed data |
| Organic traffic over time | `chart_traffic_trend.png` | SEMrush data (if provided) |
| Keywords trend + SERP distribution | `chart_keywords_trend.png` | SEMrush data (if provided) |
| Top keywords by volume | `chart_top_keywords.png` | SEMrush data (if provided) |
| Domain metrics dashboard | `chart_overview.png` | SEMrush data (if provided) |

Charts that require SEMrush data are automatically skipped if no `--semrush`
file is provided. The `chart_fat_scores.png` chart is **always** generated.

### SEMrush Data Collection

SEMrush enrichment is **optional** and **off by default**. When real SEMrush data
is available, fold it into the SEO findings and generate the domain-intelligence
charts. Try these sources in order and use the first that works:

**1. SEMrush API key (preferred — no browser needed).**
If the user has a SEMrush API key configured in their environment, the
`semrush.py` script pulls authority, organic keywords/traffic, the historical
trend, and top keyword positions, and writes a `semrush.json` in the exact shape
the chart/report scripts consume:

```bash
python scripts/semrush.py --domain example.com --database au --output /tmp/semrush.json
```

The key is read from the `SEMRUSH_API_KEY` environment variable (or `--api-key`).
**Never ask the user to paste their key into the chat and never hardcode it** —
it must come from their own environment. If `SEMRUSH_API_KEY` is not set, the
script emits `{"available": false}` and exits cleanly; just skip SEMrush charts.
Database codes: `au`, `us`, `uk`, etc. — match the site's primary market.

**2. SEMrush MCP server.**
If a SEMrush MCP server is connected (its tools appear as available), use those
tools to gather the same fields, then write them to `semrush.json` in the format
documented in the `generate-charts.py` docstring.

**3. Browser automation (fallback).**
If browser tools are available but no key/MCP is, collect data by navigating to
`semrush.com/analytics/overview/?q={domain}&searchType=domain`, switching to the
target country, and reading authority score, organic traffic, keywords, referring
domains, backlinks, and the organic positions table. Save as `semrush.json`.

**4. None available.** Skip SEMrush charts — the report still includes the FAT
score chart and all audit findings tables.

See `references/semrush-integration.md` for the full setup and field reference.

### Report Contents

**Word report (.docx) includes:**
- Branded cover page with FAT Agent logo
- Scoring summary table (all categories with grades)
- Complete findings matrix (prioritised P0-P3 with fix suggestions)
- SEO score breakdown (8 sub-categories from calculate-score.py)
- SEMrush domain intelligence section (if data provided)
- All available chart images embedded with captions
- Recommended action plan (phased)
- Branded footer

**PowerPoint (.pptx) includes:**
- Title slide with FAT Agent branding
- Executive summary with colour-coded score cards
- One slide per available chart (auto-generated)
- Key findings with priority-coloured bullets
- Closing slide with branding

**HTML dashboard (.html) includes:**
- Self-contained single HTML file (no external dependencies)
- Interactive score visualisation with colour-coded gauges
- Sortable and filterable findings table
- Expandable fix details for each finding
- Responsive layout for viewing on any device

### Font

Use **Plus Jakarta Sans** as the default font. Pass `--font "Plus Jakarta Sans"`
to both `generate-charts.py` and `generate-report.py`. If the font is not
installed on the system, the scripts fall back to Calibri, then system sans-serif.

### Full Pipeline Example

```bash
# 1. Fetch the page and save headers
curl -sI https://example.com > /tmp/headers.txt
curl -sL https://example.com -o /tmp/page.html

# 2. Analyse and score
python scripts/analyse-html.py --headers /tmp/headers.json /tmp/page.html | \
    python scripts/calculate-score.py > /tmp/scores.json

# 3. (Optional) Run Lighthouse for deeper performance data
python scripts/lighthouse.py --url https://example.com --output /tmp/lighthouse_report.json

# 4. Generate charts (with optional SEMrush data)
python scripts/generate-charts.py \
    --scores /tmp/scores.json \
    --semrush /tmp/semrush.json \
    --output-dir /tmp/charts

# 5. Generate branded reports (all formats)
python scripts/generate-report.py \
    --scores /tmp/scores.json \
    --semrush /tmp/semrush.json \
    --url example.com \
    --charts-dir /tmp/charts \
    --brand assets/fat-agent-brand.png \
    --output-dir ./reports

# 6. Generate badge (for README)
cat /tmp/scores.json | python scripts/generate-badge.py --image --output fat-badge.svg

# 7. (Optional) Multi-page crawl
python scripts/crawl.py --url https://example.com --depth 2 --max-pages 20 --output /tmp/crawl.json

# 8. (Optional) CI gate check
python scripts/ci_gate.py --scores /tmp/scores.json --threshold 70 --fail-on P0
```
