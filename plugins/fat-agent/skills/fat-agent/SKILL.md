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

That's the *only* thing FAT Agent needs. Everything below is helpful but optional —
if the user doesn't know or doesn't have the codebase, **infer what you can from
the live response and proceed** (see *Remote / From-Afar Mode* below).

#### Helpful (optional — auto-detected when not provided)
2. **Site type** — marketing site, SaaS app, e-commerce, blog, portfolio, landing page, web app, local business. *Infer from the page: product schema/cart → e-commerce; LocalBusiness/NAP → local business; `<article>`/blog paths → blog.*
3. **Tech stack** — Framework/CMS. *Infer from response headers (`Server`, `X-Powered-By`, `X-Generator`), `<meta name="generator">`, cookies (e.g. `wordpress_*`), and asset paths (`/_next/`, `/_nuxt/`, Vite `/assets/index-*.js`, `/wp-content/`).*
4. **Hosting platform** — *Infer from headers (`Server`, `Via`, `X-Vercel-*`, `CF-Ray`/`Server: cloudflare`, `X-Served-By` Fastly/Netlify, `X-Amz-*`).* Used only to tailor config-format fixes; when unknown, give **stack-agnostic** fixes (the HTML/JSON-LD/header to add).

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

### Remote / From-Afar Mode

FAT Agent can audit **any live URL with zero codebase access** — your own site, a
client's, or a prospect's you're pitching. When you don't have (or don't need) the
repo:

- **Don't block on stack/hosting.** Fetch the page and infer them from response
  headers and markup (see the inference hints under *Helpful*, above).
- **Deliver stack-agnostic fixes.** Instead of "edit `next.config.js`", hand the
  user the exact **HTML/JSON-LD/header** to add. They can paste it into any CMS,
  tag manager, or template. Only switch to framework-specific fixes once the stack
  is confirmed.
- **Lead with schema + local SEO suggestions** — these are fully derivable from the
  live page and are the highest-leverage from-afar wins (see *Schema Suggestions*).

This makes FAT Agent equally useful for self-audits and for outside-in audits of
sites you can only reach over HTTP.

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
- Inline **JavaScript** size (flag large blocking inline JS). **Inline critical CSS is a
  first-paint optimisation — don't flag moderate amounts**; only flag genuinely excessive inline CSS.
- Check for `<link rel="preconnect">` or `<link rel="preload">` hints
- Font loading: `font-display: swap` in inline styles, Google Fonts preconnect, font preloads

> **⚠️ This is a markup *proxy*, not measured performance.** The `performance`
> module reads HTML; it does **not** measure Core Web Vitals. Three rules so the
> score doesn't mislead:
>
> 1. **Measure for real, lead with that.** Always run PageSpeed/Lighthouse against
>    the **live, public URL** (`scripts/pagespeed.py` / `scripts/lighthouse.py`) and
>    present measured LCP/CLS/INP as the authority; treat the HTML score as a
>    fallback **labelled "heuristic (unmeasured)"**. You **cannot** PageSpeed a
>    `noindex`/preview/staging URL that isn't publicly reachable — audit the live
>    URL or a public preview, or say the score is unmeasured.
> 2. **Calibrate against the SERP, not an absolute ideal.** Before calling
>    performance a problem, run the same check (ideally PageSpeed) on the **top 1–3
>    ranking competitors** for the target query. If they score similar or worse, the
>    performance level provably isn't the ranking blocker — **deprioritise it and
>    say so.** A low absolute number that beats the #1 result is not a finding.
> 3. **Separate architecture-locked from quick wins.** WebP/AVIF + `srcset` on a
>    **static export**, or critical-CSS inlining done by the framework, are
>    build/framework-level — mark them effort=high / post-cutover, not P1 quick
>    wins. **Inlined critical CSS is a first-paint *win* — never flag it.** The real
>    levers on a locked stack are usually fonts (self-host + subset + preload),
>    image *sizing/dimensions* (CLS), and lazy-loading — not format.

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

### 1.16 — Schema Suggestions (paste-ready JSON-LD, from-afar)

Always run for SEO-relevant audits — it needs nothing but the live HTML, so it
works fully remotely. Where `schema_validator` *validates* existing markup, this
*recommends what's missing and writes it for you*.

```bash
python scripts/suggest_schema.py --url https://example.com page.html --format html
# or fetch it directly:
python scripts/suggest_schema.py --fetch --url https://example.com --format json
```

`suggest_schema.py` classifies the page (home / contact / article / **PDP** /
**PLP** / FAQ / local business), scrapes the live signals, and emits **ready-to-paste
JSON-LD** pre-filled with what it found (`REPLACE_*` marks what the user must
supply). It recommends, per page:

- **Organization / LocalBusiness** — brand entity; for local pages, NAP +
  `openingHoursSpecification` + `geo` + `sameAs` (Knowledge Panel + local pack).
- **WebSite** (+ `SearchAction` sitelinks box), **BreadcrumbList** on deep pages.
- **Article / BlogPosting** on content pages (headline, author, dates, publisher).
- **Product** on PDPs — `offers` (price, `priceCurrency`, `availability`,
  `itemCondition`), `brand`, `sku`, and `aggregateRating`/`review` — i.e. the
  fields Google needs for **product rich results and free Merchant listings**.
- **ItemList** on PLPs (product-grid carousels).
- **FAQPage** built from on-page `<details>`/Q&A content.

For PDPs it also returns a **`merchant_listing`** readiness checklist (price,
currency, availability, image, rating, Product schema) so you can tell the user
exactly what's blocking Merchant/rich-result eligibility.

**Presenting results:** group the suggestions by page, show each as a copy-paste
`<script type="application/ld+json">` block, and note which `REPLACE_*` values the
user needs to fill. Prioritise LocalBusiness/Product (P0–P1) over WebSite/Breadcrumb.

### 1.17 — E-E-A-T & Trust (module: `eeat`, always-on)

Modern Google ranking — and the leaked authorship/entity signals — reward
identifiable expertise and trust. In 2026, anonymity is a ranking liability. Uses
`scripts/modules/eeat.py` (from-afar). Checks:
- **Authorship** — visible author byline, link to an author bio/page, and `author`
  in Article schema referencing a `Person` (with `sameAs`).
- **Trust pages** — About, Contact, Privacy (and ideally an editorial/review policy)
  linked from the global nav/footer. Required for YMYL.
- **Entity** — `Organization`/`LocalBusiness` schema with `logo`, `sameAs`, `contactPoint`.
- **Reachability** — phone, email, postal address present.
- **Transparency** — outbound citations to authoritative sources; affiliate/sponsored
  disclosure; "reviewed by"/fact-check for YMYL.

### 1.18 — AI Search / GEO (module: `ai_search`, always-on)

AI Overviews appear on ~30–40% of queries; ChatGPT/Perplexity/Gemini/Claude cite
sources. Uses `scripts/modules/ai_search.py`. Checks:
- **AI-crawler posture** in `robots.txt` — reports allowed/blocked/partial for GPTBot,
  OAI-SearchBot, Google-Extended, PerplexityBot, ClaudeBot, CCBot, Bytespider,
  Amazonbot, Applebot-Extended, etc. **A blanket `Disallow` is the #1 cause of
  AI-search invisibility** — flag blocked answer bots as P1 and make the posture a
  deliberate choice.
- **`llms.txt`** manifest presence.
- **Extraction-readiness** — concise lead answer/summary, Q&A, lists, tables, clear headings.
- **Entity clarity** — Organization/Person + `sameAs` to Wikipedia/Wikidata.

### 1.19 — Technical SEO depth (module: `technical_seo`, always-on)

Header- and DOM-level technical checks beneath the core SEO module. Uses
`scripts/modules/technical_seo.py`. Checks:
- **`X-Robots-Tag` header** noindex/nofollow (a header-level block the meta check misses) — P0.
- **Canonical host/scheme consistency** (www vs non-www, http vs https, foreign host).
- **Meta-refresh redirects** (use a 301 instead).
- **Intrusive interstitial / pop-up** heuristics (a page-experience demotion).
- **Next-gen images** (WebP/AVIF) and **explicit width/height** (CLS).

### 1.20 — Crawlability & Indexation (module: `crawlability`, always-on)

Crawl-management depth. Uses `scripts/modules/crawlability.py`. Checks:
- **robots.txt blocking CSS/JS** — blocked render resources stop Google rendering the
  page (P1).
- **JS-only navigation** — `<a>` without a crawlable `href`.
- **Faceted / parameter URLs** — sort/filter/session/tracking links that explode crawl
  space and create duplicates.
- **Pagination** — crawlable `?page=`/`rel=next` links vs JS-only pagination.

**Redirect chains, loops & soft-404s** (multi-request) — run `scripts/redirects.py`:

```bash
python scripts/redirects.py --url https://example.com/old-page
```

Flags chains > 1 hop, loops (P0), temporary (302/307) redirects used for permanent
moves, meta-refresh, and **soft 404s** (a "not found" page returning HTTP 200). Run it
on key URLs and on any URL that should 404. For **orphan pages / click-depth**, crawl
with `scripts/crawl.py` (or the seo-crawler skill) and flag pages > 3 clicks deep or
unreachable from internal links.

### 1.21 — Content Depth & Quality (module: `content_depth`, always-on)

Quality-Rater-aligned content signals. Uses `scripts/modules/content_depth.py`. Checks:
- **YMYL detection** — flags Your-Money-or-Your-Life topics needing the highest E-E-A-T bar.
- **Main-content vs ad density** — too many ad slots relative to content.
- **Information gain / originality** — original media, data tables, statistics, citations.
- **Freshness** — a real published/updated date.
- **Featured-snippet readiness** — a concise lead answer near the top.
- **Product-review quality** — first-hand testing, pros/cons, comparisons on review pages.

### 1.22 — E-commerce / Merchant depth (module: `ecommerce`)

Beyond Product schema/cart/price, the `ecommerce` module now checks PDPs for:
**GTIN/MPN/SKU**, **shipping** info, **return/refund policy**, **out-of-stock** schema
alignment (`availability: OutOfStock`, or 404/301 retired products), and **related/cross-sell
links** — the fields that drive Merchant/free-listing eligibility and crawl discovery.

### 1.23 — Video SEO (module: `video`, auto-detected)

Enabled when a `<video>`/YouTube/Vimeo embed is present. Uses `scripts/modules/video.py`.
Checks for **VideoObject** structured data with its required properties (`name`,
`description`, `thumbnailUrl`, `uploadDate`), a thumbnail, and **key-moments** markup
(`Clip`/`SeekToAction`); recommend submitting a **video sitemap**.

> **Also handle by judgement (not auto-checked):** schema policy (mark up only
> user-visible content; first-party reviews only — no externally-aggregated
> `aggregateRating`; use the most specific type) and **Google Discover** readiness
> (`max-image-preview:large`, images ≥1200px wide, an RSS/Atom feed).

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

### Persist the Punch List

After presenting the report, ALWAYS persist it to disk — the punch list must
survive context compaction, session restarts, and handoffs:

```bash
python scripts/punchlist.py update --scores ./.fat-work/scores.json --url https://example.com
python scripts/punchlist.py status
```

This merges the scored findings into `./.fat-work/punchlist.json`: new findings
open, findings absent from a rescanned module auto-resolve, and resolved
findings that reappear are re-opened as regressions. Findings from modules that
were *not* scanned this run are left untouched, so a quick-profile rescan never
falsely "resolves" a full-profile finding.

When the user makes a decision about a finding (defer it, choose fix A over
fix B, accept the risk), record it against the item so the reasoning survives
the conversation:

```bash
python scripts/punchlist.py note <id> --text "Client chose SSR over prerender — Vercel move planned Q3"
python scripts/punchlist.py resolve <id> --wontfix --note "Brand team owns this page; out of scope"
```

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

**Editorial report (brand-pulled, print-ready):** For client deliverables that
should look like an agency proposal rather than a tool export, generate the
editorial deck — it renders the audit in the CLIENT'S own visual language,
using imagery, logo, accent colour and typeface harvested from their live
site:

```bash
python scripts/brandkit.py --url https://client.com --out ./.fat-work/brand
python scripts/editorial_report.py \
    --scores ./.fat-work/scores.json \
    --sitewide ./.fat-work/sitewide.json \
    --brandkit ./.fat-work/brand/brandkit.json \
    --out ./.fat-work/audit-report.html
```

Output is a single-file, A4-landscape HTML deck (photography-led cover, big
editorial scorecard, one batch of findings per slide, next-steps close) that
prints to PDF from any browser. Sanity-check the harvested brand kit before
presenting: if the accent colour or hero images look wrong (some sites
lazy-load imagery), override by editing `brandkit.json` and re-running.
Offer this as the default client deliverable; the Word/PPTX pipeline below
remains for users who need editable documents.

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
3. **Update the punch list** — Re-run the scoring pipeline, then:
   ```bash
   python scripts/punchlist.py update --scores ./.fat-work/scores.json
   python scripts/punchlist.py status
   ```
   Verified-absent findings auto-resolve; reappearing ones are flagged as
   regressions. Never track fixed/still-present in conversation memory alone.
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
- **Overall FAT score** — a weighted composite of the measured categories
  (**SEO 40% · Security 25% · Performance 20% · Accessibility 15%**), then **capped
  by finding severity**: any open **P0 caps the grade at D**, any open **P1 caps it
  at B** (an A means no high-priority issues open). Module findings (technical SEO,
  crawlability, E-E-A-T, AI, content) feed this cap, so the headline number reflects
  the whole audit — not just on-page tags.
- **Honesty in the scorecard:** label **Performance** as *heuristic (markup proxy,
  not measured CWV)* unless real Lighthouse/PageSpeed was wired in, and **Security**
  as *not assessed* when no response headers were fetched (it's excluded from the
  grade, not scored as a failure). Don't present either as a measured letter grade
  when it isn't one.

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

## Site-Wide Crawl Audit

Page-level audits can't see cross-page problems. `sitecrawl.py` +
`sitewide.py` add the site-level layer: a concurrent stdlib crawl into a
SQLite database (a `pages` table plus a full `links` graph), then site-level
checks over it. Use this whenever the user says "audit the whole site",
"crawl the site", or the site has more than a handful of pages.

### Step 1 — Crawl

```bash
python scripts/sitecrawl.py https://example.com --max-urls 300 --out ./.fat-work/crawl
```

Prints only a compact JSON summary; the full data lands in
`./.fat-work/crawl/site.db`. **Never read page HTML into context during a
site crawl — everything needed is in the database.** Flags: `--max-urls`
(default 300), `--concurrency` (8), `--subdomains`, `--delay`,
`--ignore-robots`, `--no-sitemap`, `--allow-private` (staging/intranet hosts —
the SSRF guard blocks private addresses by default), `--insecure`.

The crawler seeds from the sitemap as well as links — that's what makes
orphan-page detection possible (an orphan, by definition, can't be reached by
following links). It respects robots.txt, strips tracking parameters, records
every internal/external link with anchor text, and backs off automatically if
the site starts returning 403/429.

### Step 2 — Site-level audit

```bash
python scripts/sitewide.py --db ./.fat-work/crawl/site.db            # human summary
python scripts/sitewide.py --db ./.fat-work/crawl/site.db --json > ./.fat-work/sitewide.json
python scripts/punchlist.py update --scores ./.fat-work/sitewide.json
```

Checks that only exist at site level: **internal links to broken pages (P0)**,
**5xx errors (P0)**, broken 4xx pages, fetch errors, **duplicate titles /
meta descriptions / page content across URLs**, **orphan pages**, thin
content at scale, slow responses, internal links resolving through redirects,
and **sitemap hygiene** — sitemap entries that redirect or 404. Findings are
standard FAT findings (module `sitewide`) — they merge into the punch list,
auto-resolve on a clean re-crawl, and belong at the top of the report
alongside the page-level results.

**Diagnose by origin — sitemap seeds vs page links.** A URL can enter the
crawl two ways (a link on a page, or the sitemap), and the fix is completely
different depending on which. The `in_sitemap` column separates them:

```sql
-- are the 301s/404s the PAGES' fault or the SITEMAP's fault?
SELECT in_sitemap, status, COUNT(*) FROM pages
WHERE status >= 300 GROUP BY in_sitemap, status;
-- redirects that no internal link points at = sitemap-only problem
SELECT COUNT(*) FROM pages p WHERE p.status BETWEEN 300 AND 399
AND NOT EXISTS (SELECT 1 FROM links l WHERE l.type='internal' AND l.target=p.url);
```

Real-world case: after fixing every page link on a site, a re-crawl still
showed ~1,200 × 301 — **all** of them sitemap seeds. The sitemap generator
emitted every URL without the trailing slash the host 301s to. Two rules
from that incident:

1. **Sitemaps must list final canonical URLs** — a redirecting or 404 sitemap
   entry wastes a fetch per URL per crawl and mis-hints canonicals. On
   `trailingSlash` sites, verify the sitemap's `<loc>` values end with `/`.
2. **Find every sitemap generator before concluding.** Sites accumulate
   several (a static `public/sitemap.xml`, a build script, and a framework
   route). In Next.js, an `app/sitemap.ts` metadata route **silently
   shadows** `public/sitemap.xml` — fixing the script that writes the public
   file changes nothing. Fetch the LIVE `/sitemap.xml` (and every `Sitemap:`
   URL in robots.txt) and compare against what each generator emits.

The `sitewide.py` redirect findings flag the systemic case automatically:
when most redirects are `URL → URL + '/'`, the finding says to fix the
generator once rather than treating N URLs as N issues.

### Step 3 — Drill down (token-cheap)

Answer follow-up questions with capped SQL against the DB, not by re-fetching
pages:

```bash
python scripts/sitewide.py --db ./.fat-work/crawl/site.db \
    --query "SELECT url,title_len FROM pages WHERE title_len>60 ORDER BY title_len DESC"
```

SELECT-only, 50-row cap. Useful columns on `pages`: status, redirect_to,
depth, response_ms, size_bytes, title/title_len, meta_desc/meta_desc_len,
h1/h1_count, canonical/canonical_self, word_count, content_hash,
images/images_no_alt, internal_links/external_links, indexable/index_reason,
in_sitemap, error. `links` has source/target/anchor/rel/type.

For JavaScript-rendered sites, the crawl sees server HTML only (which is what
non-rendering crawlers see — that's a feature for SEO truth). Use
`render_js.py` / the render-gap check on key pages to cover the rendered view.

### Step 4 — Internal-link opportunities (content → money pages)

The crawl's link graph enables a finding most tools fake: content pages that
earn attention but never pass it on. Run it on every site with a blog or
guide section:

```bash
python scripts/link_opportunities.py --db ./.fat-work/crawl/site.db \
    [--gsc ./.fat-work/gsc.json] --json > ./.fat-work/links.json
python scripts/punchlist.py update --scores ./.fat-work/links.json
```

Graph mode alone finds content pages with **zero internal links to any money
page** (services/products/pricing/booking, override with `--money-pattern` /
`--content-pattern`). With a GSC export, gaps are ranked by real impressions,
top queries are shown, and each page gets a **suggested money-page target**
matched from its actual queries. Frame these to the user as revenue routing:
"this guide earns N impressions and sends none of that authority to a page
that sells".

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
- Keep track of previously found issues — don't re-report things already flagged.
  The source of truth is `./.fat-work/punchlist.json`, not conversation memory
- If the user asks "what's left?", run `python scripts/punchlist.py status` and
  show the result — don't answer from memory
- Be encouraging but honest — don't gloss over real issues

---

## Session Continuity & Context Compaction

FAT is designed so context compaction doesn't matter: **the conversation is
disposable, the files are not.** All audit state lives on disk (`scores.json`,
`punchlist.json`, `.fat-history.json`, crawl/report artifacts) and every check
is a deterministic script — anything compacted away is either persisted or
re-computable in one command.

**When resuming an audit** (a new session, or after compaction in a long one):

1. Read `./.fat-work/punchlist.json` — open items, decisions, and notes
2. Read `.fat-history.json` (if present) — score trend across audits
3. Run `python scripts/punchlist.py status` and confirm with the user where
   the audit is up to before doing anything else

**Optional — recover prior-session reasoning with ctx:** if the [ctx](https://ctx.rs)
CLI is installed (check with `ctx --version`; it is a separate open-source tool,
never required), search the local agent-session history for the earlier audit
conversations the punch list can't capture — why a fix was chosen, what was
already attempted, what the client pushed back on:

```bash
ctx search "<domain> audit"
ctx show session <id>
```

Cite the ctx session/event id when retrieved history changes your answer. If
ctx is not installed, skip this silently — the punch list and history files
carry the essential state on their own.

**Offering to install ctx (once, with consent — never automatically):** when
ctx is absent AND session continuity would genuinely help (resuming an audit
from a previous session, or a long multi-session engagement), you may offer it
one time:

1. First check for the decline marker — if `./.fat-work/.ctx-declined` exists,
   the user has already said no. **Do not offer again; never mention it.**
2. Otherwise offer once, plainly: it is optional, open-source (Apache-2.0),
   fully local (SQLite on their machine, no cloud, no telemetry), and FAT works
   fine without it. Official installers:
   ```bash
   curl -fsSL https://ctx.rs/install | sh        # macOS / Linux
   ```
   ```powershell
   irm https://ctx.rs/install.ps1 | iex          # Windows
   ```
3. If they decline (or don't clearly accept), record it and move on:
   ```bash
   mkdir -p ./.fat-work && touch ./.fat-work/.ctx-declined
   ```

**Never** install ctx (or anything else) without the user's explicit yes in the
current conversation, and never bundle or vendor its binary — distribution
belongs to the ctx project's own installer.

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
- `scripts/punchlist.py` — Persistent punch list (read/write `./.fat-work/punchlist.json`; update/status/resolve/note — survives context compaction)
- `scripts/crawl.py` — Multi-page BFS crawler with robots.txt support
- `scripts/sitecrawl.py` — Site-wide concurrent crawler → SQLite (`pages` + `links` graph, sitemap seeding, SSRF guard, adaptive throttling)
- `scripts/sitewide.py` — Site-level audit over the crawl DB (broken internal links, duplicate titles/content, orphans, sitemap hygiene) + capped SQL drill-down
- `scripts/link_opportunities.py` — Content→money-page internal-link gaps from the real link graph (+ GSC ranking & target suggestions)
- `scripts/brandkit.py` — Harvest the client site's logo, imagery, palette & fonts → `brandkit.json`
- `scripts/editorial_report.py` — Brand-pulled A4 editorial audit deck (single-file HTML, print-to-PDF; `--roadmap` adds the content-roadmap slide)
- `scripts/content_engine.py` — The Content Engine: GSC queries → topic clusters → defend/optimise/rework/consolidate/create/refresh roadmap with brief skeletons
- `scripts/bulk_audit.py` — Portfolio-wide bulk site auditor
- `scripts/ci_gate.py` — CI/CD quality gate (threshold + priority checks)
- `scripts/lighthouse.py` — Lighthouse CLI integration wrapper
- `scripts/pagespeed.py` — PageSpeed Insights API wrapper (Core Web Vitals)
- `scripts/semrush.py` — Optional SEMrush API enrichment → `semrush.json` (key from `SEMRUSH_API_KEY`)
- `scripts/suggest_schema.py` — From-afar schema advisor → paste-ready JSON-LD (Organization/LocalBusiness, Product/PDP, ItemList/PLP, Article, FAQPage, Breadcrumb) + Merchant-listing readiness
- `scripts/gsc.py` — Google Search Console behavioural analysis (NavBoost proxy) → striking-distance, low-CTR, branded share, `opportunity_keywords`
- `scripts/redirects.py` — Redirect-chain / loop / 302-vs-301 / soft-404 analyser (multi-hop)
- `scripts/gsc_health.py` — GSC *health* analysis (Index Coverage, Manual Actions, Security Issues, Enhancements)
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
  - `eeat.py` — E-E-A-T & Trust (authorship, trust pages, entity, transparency) — always-on
  - `ai_search.py` — AI Search / GEO (AI-crawler posture, llms.txt, extraction, entity) — always-on
  - `technical_seo.py` — Technical depth (X-Robots-Tag, canonical host, interstitials, images) — always-on
  - `content_depth.py` — Content quality (YMYL, ad density, originality, freshness, review quality) — always-on
  - `crawlability.py` — Crawl/indexation (robots-blocks-CSS/JS, JS-only nav, faceted URLs, pagination) — always-on
  - `video.py` — Video SEO (VideoObject + required props, thumbnail, key moments) — auto-detected

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

### GSC Behavioural Data Collection (NavBoost proxy)

The 2024 leak confirmed click signals (NavBoost) are among Google's strongest
ranking inputs — invisible to a URL-only audit, but visible in Search Console.
When the user grants access, fold GSC in:

1. **Collect** the last 3 months of query+page performance rows. Prefer a connected
   **GSC MCP** (e.g. `mcp__gsc__*` tools); otherwise the Search Console API, or a
   manual export. Save as `gsc.json` (rows of query/page/clicks/impressions/ctr/position;
   the GSC API `{"keys":[...]}` shape is accepted as-is).
2. **Analyse** with `scripts/gsc.py`:

```bash
python scripts/gsc.py --data gsc.json --brand "acme" --output /tmp/gsc.json
```

3. **Present** the behavioural wins, which most audits never surface:
   - **Striking-distance** (positions ~5–20 with impressions) — fastest ranking wins.
   - **Low-CTR at good position** — a title/meta/intent fix, not a ranking one
     (compare `ctr` vs `benchmark_ctr`).
   - **Impressions, ~no clicks** — snippet/intent mismatch.
   - **Branded share** — brand-strength proxy.

4. **Ship the fix, not just the finding.** For each striking-distance and
   low-CTR keyword, DRAFT the paste-ready change yourself — don't stop at
   reporting the keyword:
   - A rewritten `<title>` (≤60 chars, keyword near the front, on brand)
   - A rewritten meta description (≤155 chars, matches the query's intent)
   - Where relevant, an H1/H2 suggestion or a short content-gap paragraph brief
   Fetch the target page first so the drafts fit the page's actual voice and
   subject. Present as a copy-paste block per keyword, current vs proposed.

### The Content Engine (lead the content discussion)

The audit layers find what's broken; the Content Engine finds **what's
missing** — content is what moves the SEO dial.

**Getting the data — easiest path first, never make the user reshape
anything:**

1. **A Search Console MCP is connected** (check the available tools for
   search-analytics/GSC tools): pull query+page performance data YOURSELF
   (last 3–6 months, query+page dimensions) and write it as `gsc.json` rows
   of `{query, page, clicks, impressions, position}`. The user does nothing.
2. **No MCP**: ask the user to download the export from Search Console
   (Performance → Export → Download CSV) and **drop the ZIP in as-is** —
   `content_engine.py --gsc export.zip` reads the zip directly, or a bare
   `Queries.csv`. UI exports lack query→page pairs; the engine infers them
   from the crawl DB automatically (matches are marked `inferred`).
3. **API** setup only if the user asks for automation.

Then run:

```bash
python scripts/content_engine.py --gsc ./.fat-work/gsc.json \
    --db ./.fat-work/crawl/site.db --brand "<brand>" \
    --roadmap ./.fat-work/roadmap.json --json > ./.fat-work/content.json
python scripts/punchlist.py update --scores ./.fat-work/content.json
```

It clusters real queries into topics (hub-and-spoke, brand terms excluded),
maps each cluster against the site's actual pages, and classifies every
cluster: **defend** (top-10 — protect), **optimise** (striking distance),
**rework** (covered but ranking nowhere), **consolidate** (cannibalised —
multiple pages splitting one topic), **create** (real demand, no page — new
content brief), **refresh** (pass `--previous` with an earlier GSC export to
catch decayed clusters). Every create/rework/refresh gets a brief skeleton:
working title, target queries, suggested H2s from the cluster's own
long-tails, and a money-page link target.

**Your job after the script runs:** turn the top brief skeletons into full
content briefs — audience, angle, outline with the suggested H2s, internal
links in AND out (use the crawl link graph), and what would make this page
the best answer on the internet for its head query. The script supplies
evidence; you supply the editorial thinking. Lead the client conversation
with the roadmap, not the defect list.

Pass `--roadmap` output to `editorial_report.py --roadmap` and the deck gains
a **"Content roadmap — where the growth is"** slide placed BEFORE the
findings: growth first, defects second.

`gsc.py` also emits `opportunity_keywords` in the report schema, so GSC wins feed
straight into the deck's *SEO Priority Opportunities* slide. If no GSC access is
available, skip — the rest of the audit is unaffected.

#### GSC health reports (the damaging stuff a URL audit can't see)

Beyond Performance, pull the **health** reports and run `scripts/gsc_health.py` —
these surface penalties and indexation problems invisible from the page:

1. Via the GSC MCP / Search Console API, gather: **Manual Actions**, **Security
   Issues**, **URL Inspection / Index Coverage** (per-URL `coverageState`), and
   **Enhancements** (rich-result errors per type). Assemble into one JSON:

```json
{ "manual_actions": [...], "security_issues": [...],
  "url_inspections": [{"url": "...", "coverageState": "Crawled - currently not indexed"}],
  "enhancements": {"Products": {"errors": 3}} }
```

2. Analyse:

```bash
python scripts/gsc_health.py --data gsc_health.json
```

It returns prioritised findings — **Manual Actions and Security Issues are P0** —
plus index-coverage reasons (Discovered/Crawled-not-indexed, blocked, soft-404,
duplicate-canonical) grouped with fix hints, and rich-result error counts. Fold
these into the FAT report at the top of the punch list.

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

#### Turn the data into INSIGHT, not just numbers

A report full of metrics is not actionable. Whenever SEMrush organic data is
collected, **compute and add these fields to the SEMrush JSON** so the docx and
pptx render the insight automatically (see the `generate-report.py` schema):

- **`opportunity_keywords`** — non-branded, winnable (position ~4–30), high-value
  keywords, ranked by `volume × CPC × position-proximity`. Each item:
  `{"keyword","volume","cpc","position","url","priority"}`. This is the
  front-foot "what to work on" board. Flag the user's stated priority pages.
- **`cannibalization`** — keywords ranking on more than one URL (the pages
  compete and split signals). Each item: `{"keyword","volume","urls":[...]}`.
- **`action_plan`** — a phased, prioritised list of next steps. Either a list of
  strings, or a list of `{"phase","items":[...]}` objects. Tie each action to a
  finding (e.g. "commercial term X ranks via a blog post → strengthen the money
  page and internal-link to it"). Also accepted via `scores["recommendations"]`
  or a separate `--actions actions.json` file.

Also surface the **branded vs non-branded** traffic split and the **position
distribution** (top3 / 4-10 / 11-20 / 21-50 / 51-100) — a heavily branded
profile with money terms stuck on page 2-3 is the most common local-SEO finding.

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
- One slide per available chart (auto-generated, **aspect-ratio preserved** —
  charts are fit-to-box and centred, never stretched)
- **SEO Priority Opportunities** slide (table) — when `opportunity_keywords` is provided
- **Keyword Cannibalisation** slide (table) — when `cannibalization` is provided
- **Recommended Action Plan** slide(s) — when an action plan / `recommendations`
  is provided (auto-overflows across multiple slides)
- Key findings with priority-coloured bullets
- Closing slide with branding

> The SEMrush insight slides and the action plan are what make the deck
> actionable. Always populate `opportunity_keywords`, `cannibalization` and
> `action_plan` (see *SEMrush Data Collection → Turn the data into INSIGHT*)
> when SEMrush data is available — otherwise the deck is "just numbers".

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
