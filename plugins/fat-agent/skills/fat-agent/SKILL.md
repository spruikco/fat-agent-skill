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
- All `<img>` tags have `alt` attributes
- Images have explicit `width` and `height` attributes (CLS prevention)
- Form inputs have associated `<label>` elements or `aria-label`
- `<html lang="...">` attribute is set
- Skip links present for keyboard navigation
- ARIA landmarks used (`<main>`, `<nav>`, `<header>`, `<footer>`)
- No empty heading tags (`<h2></h2>`, `<h3>   </h3>`)
- Same-page anchor links (`href="#section"`) point to existing element IDs

Ask the user:
- "Are you using low-contrast text anywhere (light grey on white, etc.)?"
- "Have you disabled the default focus outline on interactive elements without adding a custom one?"

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
Check the HTML for:
- Google Analytics / GA4 (`gtag` or `google-analytics`)
- Google Tag Manager (`googletagmanager`)
- Facebook Pixel (`fbq`)
- Other common tracking scripts
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
- Reference: `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/netlify.md`

**Vercel:**
- Check if response headers indicate Vercel (`x-vercel-id`, `server: Vercel`)
- Ask: "Do you have a `vercel.json` with custom headers configured?"
- Ask: "Are you using Vercel Middleware for redirects or auth?"
- Check for Edge Function headers (`x-middleware-*`)
- Suggest Vercel Analytics / Speed Insights if not detected
- Reference: `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/vercel.md`

**Cloudflare Pages:**
- Check if response headers indicate Cloudflare (`cf-ray`, `server: cloudflare`)
- Ask: "Do you have a `_headers` and `_redirects` file in your build output?"
- Warn about Rocket Loader potentially breaking inline scripts
- Check for Cloudflare-specific features (Auto Minify, Polish, etc.)
- Reference: `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/cloudflare-pages.md`

**WordPress:**
- Check for `/wp-admin/` accessibility (should redirect to login, not expose admin)
- Check for `/xmlrpc.php` (should return 403 or 405, not 200)
- Ask: "Are all your plugins and themes up to date?"
- Check for `wp-json` REST API exposure
- Check for user enumeration via `/?author=1`
- Reference: `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/wordpress.md`

**Apache:**
- Ask: "Do you have a `.htaccess` file with security headers?"
- Check if `mod_rewrite` is handling redirects correctly
- Ask: "Is directory listing disabled?"
- Check for server version exposure in headers (`Server: Apache/x.x.x`)
- Reference: `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/apache.md`

**Nginx:**
- Check if server header exposes version (`Server: nginx/x.x.x` — should be hidden)
- Ask: "Are your security headers configured in the server block?"
- Check for proper `try_files` configuration (SPA routing)
- Reference: `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/nginx.md`

**AWS (S3/CloudFront/Amplify):**
- Check for CloudFront headers (`x-amz-cf-id`, `x-cache`)
- Ask: "Do you have a CloudFront Response Headers Policy configured?"
- Check that S3 bucket is not directly publicly accessible
- Verify custom error pages are configured
- Reference: `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/aws.md`

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
   python ${CLAUDE_PLUGIN_ROOT}/scripts/analyse-html.py page.html | python ${CLAUDE_PLUGIN_ROOT}/scripts/calculate-score.py | python ${CLAUDE_PLUGIN_ROOT}/scripts/generate-badge.py --image --output fat-badge.svg
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
- `${CLAUDE_PLUGIN_ROOT}/references/security-headers.md` — Full security header recommendations
- `${CLAUDE_PLUGIN_ROOT}/references/seo-checklist.md` — Extended SEO audit criteria
- `${CLAUDE_PLUGIN_ROOT}/references/accessibility-guide.md` — WCAG 2.1 quick reference
- `${CLAUDE_PLUGIN_ROOT}/scripts/analyse-html.py` — HTML analysis helper (extracts meta tags, headers, scripts)
- `${CLAUDE_PLUGIN_ROOT}/scripts/calculate-score.py` — Scoring calculator (SEO, Security, Accessibility, FAT Score)
- `${CLAUDE_PLUGIN_ROOT}/scripts/generate-badge.py` — SVG badge generator (character image + score bars)

### Platform-Specific Fix References
Load the relevant file based on the hosting platform from Phase 0:
- `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/netlify.md` — Netlify config (_headers, netlify.toml, Forms)
- `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/vercel.md` — Vercel config (vercel.json, middleware)
- `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/cloudflare-pages.md` — Cloudflare Pages (_headers, Workers)
- `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/apache.md` — Apache config (.htaccess, mod_rewrite)
- `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/nginx.md` — Nginx config (server blocks, add_header)
- `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/wordpress.md` — WordPress config (wp-config.php, plugins)
- `${CLAUDE_PLUGIN_ROOT}/references/platform-fixes/aws.md` — AWS config (CloudFront, S3, Amplify)

### Framework-Specific Fix References
Load the relevant file based on the tech stack from Phase 0:
- `${CLAUDE_PLUGIN_ROOT}/references/framework-fixes/nextjs.md` — Next.js (App Router + Pages Router)
- `${CLAUDE_PLUGIN_ROOT}/references/framework-fixes/astro.md` — Astro (islands, content collections)
- `${CLAUDE_PLUGIN_ROOT}/references/framework-fixes/sveltekit.md` — SvelteKit (load functions, adapters)
- `${CLAUDE_PLUGIN_ROOT}/references/framework-fixes/nuxt.md` — Nuxt 3 (useHead, useSeoMeta)
- `${CLAUDE_PLUGIN_ROOT}/references/framework-fixes/gatsby.md` — Gatsby (Head API, gatsby-plugin-image)
- `${CLAUDE_PLUGIN_ROOT}/references/framework-fixes/wordpress.md` — WordPress themes (functions.php, hooks)
- `${CLAUDE_PLUGIN_ROOT}/references/framework-fixes/static-html.md` — Static HTML/CSS/JS (no framework)
