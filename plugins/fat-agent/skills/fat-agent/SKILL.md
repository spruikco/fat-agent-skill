---
name: fat-agent
description: >
  FAT Agent (Fix, Audit, Test) — a post-launch quality assurance agent that
  systematically audits deployed websites and web applications. Triggers whenever
  a user mentions "FAT agent", "post-launch audit", "site audit", "audit my site",
  "check my deployment", "post-deploy check", "QA my site", "launch checklist",
  or any request to review a live or recently deployed website for issues.
  Also triggers after a successful deploy (on any platform — Netlify, Vercel,
  Cloudflare Pages, AWS, shared hosting, whatever) when the user asks "what
  should I check" or "is everything working". Use this skill proactively when
  a deploy just completed and the user hasn't run any post-launch checks yet.
---

# FAT Agent — Fix, Audit, Test

A post-launch quality assurance agent that performs a comprehensive, systematic
audit of deployed websites and guides users through fixing every issue found.

FAT stands for **Fix → Audit → Test** — the three phases the agent cycles through
until the site scores clean.

## Philosophy

Most post-launch issues fall into predictable categories. Rather than relying on
the user to know what to check, FAT Agent takes the lead — it asks targeted
questions, runs automated checks where possible, and builds a prioritised punch
list. Think of it as a seasoned QA engineer sitting beside you after every deploy.

---

## When to Trigger

Activate FAT Agent when:
- A user says "run FAT agent", "audit my site", "post-launch check", etc.
- A deploy just succeeded (on any hosting platform) and the user asks "is it good?" or similar
- The user pastes a URL and asks Claude to "check it" or "review it"
- After any deploy, if the user hasn't mentioned running QA

---

## Phase 0 — Gather Context

Before auditing anything, FAT Agent needs to understand the project. Ask the user
for the following (skip anything already known from conversation context or memory):

### Required
1. **Live URL** — The production URL to audit (e.g., `https://example.com`)
2. **Site type** — What kind of site is this? (marketing site, SaaS app, e-commerce, blog, portfolio, landing page, web app)
3. **Tech stack** — Framework/CMS (e.g., Next.js, WordPress, static HTML, Astro, etc.)
4. **Hosting platform** — Where is this deployed? (Netlify, Vercel, Cloudflare Pages, AWS, shared hosting, self-hosted, etc.) — this helps tailor fix suggestions to the right config format

### Situational (ask only if relevant)
4. **Critical user flows** — What are the 2-3 most important things a visitor does? (e.g., "fill out contact form", "add to cart and checkout", "sign up")
5. **Target audience** — Who visits this site? (helps calibrate accessibility and performance expectations)
6. **Known issues** — Anything the user already knows is broken or unfinished?
7. **Previous audit results** — Has a FAT audit been run before? (check conversation history)

Present these as a friendly, concise intake form — not an interrogation. Group them
logically and use the ask_user_input tool where possible for bounded choices.

**Example opener:**
> Ready to run a FAT audit! I just need a few details to get started. What's the
> live URL, and what kind of site are we looking at?

---

## Phase 1 — AUDIT

Run checks in this exact order. For each category, use `web_fetch` on the live URL
and analyse the response. Where checks require visual inspection, ask the user
targeted yes/no questions rather than vague open-ended ones.

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
- Heading hierarchy is logical (no skipped levels, e.g. `h1` → `h3` missing `h2`)
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
Modern frameworks (Next.js, Nuxt, React, Angular, Svelte, Astro) often render
headings and other semantic elements client-side after hydration. The
`analyse-html.py` script detects common SPA indicators (`id="__next"`,
`__NEXT_DATA__`, `data-reactroot`, etc.) and downgrades a missing `<h1>` from
P0 Critical to P1 High when a framework is detected. Component libraries like
Framer Motion (`<motion.h1>`) and styled-components also wrap native elements
in ways the HTML parser cannot see. When an SPA is detected, recommend the user
verify headings in DevTools or using the browser automation tools rather than
treating a missing `<h1>` as a hard failure.

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
render-blocking scripts ≤ 2, external scripts ≤ 15). See `references/performance-budgets.md`
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

---

## Phase 2 — FIX

After completing all audit checks, compile a **FAT Report** — a prioritised list
of findings.

### Priority Levels
| Priority | Label | Meaning |
|----------|-------|---------|
| 🔴 P0 | **Critical** | Site is broken, inaccessible, or insecure |
| 🟠 P1 | **High** | Significant SEO, performance, or UX impact |
| 🟡 P2 | **Medium** | Best practice violations, minor issues |
| 🟢 P3 | **Low** | Nice-to-haves, polish items |

### Report Format
Present findings grouped by priority, with each item containing:
1. **What's wrong** — One-line description
2. **Why it matters** — Impact explanation (keep it brief)
3. **How to fix** — Specific, actionable fix (with code snippets where possible)
4. **Effort** — Quick estimate (⚡ 5 min, 🔧 30 min, 🏗️ 1+ hour)

**Example finding:**
> 🟠 **P1 — Missing meta description**
> Your homepage has no `<meta name="description">` tag. Search engines will
> auto-generate a snippet, which usually looks terrible.
>
> **Fix:** Add to your `<head>`:
> ```html
> <meta name="description" content="Your compelling 155-character description here">
> ```
> **Effort:** ⚡ 5 min

After presenting the report, ask: "Want me to help fix any of these now? I can
generate the code changes for the quick wins."

---

## Phase 3 — TEST

After fixes are applied and redeployed:

1. **Re-fetch the URL** and verify the specific issues that were fixed
2. **Report results** — "✅ Fixed" or "❌ Still present" for each item
3. **Update the punch list** — Remove resolved items, flag persistent ones
4. **Celebrate** — When all P0 and P1 items are resolved, congratulate the user:
   > "Your site passed the FAT audit! All critical and high-priority items are
   > resolved. Here's your final scorecard."

### Final Scorecard
Present a summary showing:
- Total issues found → Total resolved
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
- `scripts/analyse-html.py` — HTML analysis helper (extracts meta tags, headers, scripts)
- `scripts/calculate-score.py` — Scoring calculator (SEO, Security, Accessibility, FAT Score)
- `scripts/generate-badge.py` — SVG badge generator (character image + score bars)
- `scripts/track-history.py` — Historical audit tracker (read/write `.fat-history.json`)
- `references/performance-budgets.md` — Performance budget configuration guide
- `references/ci-cd-integration.md` — CI/CD integration examples (GitHub Actions, Netlify, Vercel, etc.)

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
