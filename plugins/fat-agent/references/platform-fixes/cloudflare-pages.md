# Cloudflare Pages -- Platform Fix Reference

Configuration reference for sites deployed on Cloudflare Pages. Covers headers,
redirects, SSL, caching, and Cloudflare-specific features that affect QA audits.

---

## Security Headers

Cloudflare Pages uses a `_headers` file placed in the build output directory
(same syntax as Netlify). Each rule starts with a URL pattern, followed by
indented header key-value pairs.

### Complete Recommended Headers

```
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
  X-DNS-Prefetch-Control: on
  Cross-Origin-Opener-Policy: same-origin
  Cross-Origin-Resource-Policy: same-origin
  Cross-Origin-Embedder-Policy: require-corp
```

**Note:** `Content-Security-Policy` is highly site-specific. The above is a
strict starting point. You will need to add domains for any third-party scripts,
fonts, analytics, CDNs, etc.

### Path-Specific Headers

```
/api/*
  Access-Control-Allow-Origin: https://example.com
  Access-Control-Allow-Methods: GET, POST, OPTIONS
  Access-Control-Allow-Headers: Content-Type, Authorization

/assets/*
  Cache-Control: public, max-age=31536000, immutable

/*.html
  Cache-Control: public, max-age=0, must-revalidate
```

### Attaching and Detaching Headers

Prefix a header name with `!` to remove a header that Cloudflare sets by default:

```
/public/*
  ! X-Frame-Options
```

This removes `X-Frame-Options` for paths under `/public/`, useful if you need
specific pages to be embeddable in iframes.

---

## Redirects & Rewrites

### _redirects File

Place a `_redirects` file in the build output directory. Format:

```
# Basic redirect (301 by default)
/old-page  /new-page

# Explicit status codes
/old-page  /new-page  301
/moved-temp  /new-location  302

# Redirect to external URL
/blog  https://blog.example.com  301
```

### Status Codes

| Code | Meaning | Use Case |
|------|---------|----------|
| 301 | Permanent redirect | Page moved forever, transfer SEO |
| 302 | Temporary redirect | Page temporarily elsewhere |
| 303 | See Other | Redirect after form POST |
| 307 | Temporary (preserves method) | API redirects |
| 308 | Permanent (preserves method) | API redirects |
| 200 | Rewrite (proxy) | Serve different content at same URL |

### Splat Redirects

Use `:splat` to capture everything after a wildcard `*`:

```
# Redirect entire directory
/old-blog/*  /blog/:splat  301

# Move to subdomain
/docs/*  https://docs.example.com/:splat  301

# Rewrite (proxy) -- serves content from /index.html for SPA routing
/*  /index.html  200
```

**Important:** The SPA fallback (`/* /index.html 200`) must be the **last rule**
in the file. Cloudflare Pages processes rules top-to-bottom and stops at the
first match.

### Placeholder Redirects

Use `:placeholder` for named segments:

```
/blog/:year/:month/:slug  /posts/:slug  301
/users/:id/profile  /profile/:id  301
```

### Custom 404 Page

Place a `404.html` file in the build output root. Cloudflare Pages automatically
serves it with a 404 status code when no matching file or redirect is found.

No `_redirects` entry is needed for this -- it is automatic.

### Bulk Redirects via Cloudflare Dashboard

For sites with more than 2000 redirects (the `_redirects` file limit), use
Cloudflare Bulk Redirects:

1. Go to **Cloudflare Dashboard > Account > Bulk Redirects**
2. Create a Bulk Redirect List (CSV upload or manual entry)
3. Create a Bulk Redirect Rule referencing that list
4. Bulk Redirects support up to **millions** of entries per list

Bulk Redirects are evaluated **before** `_redirects` file rules.

**CSV format for bulk upload:**

```csv
source_url,target_url,status_code
https://example.com/old-1,https://example.com/new-1,301
https://example.com/old-2,https://example.com/new-2,301
```

---

## SSL/HTTPS Configuration

### Automatic SSL Modes

Cloudflare provides free SSL for all Pages deployments on `*.pages.dev` domains.
For custom domains, the SSL mode is configured at the zone level:

| Mode | Browser-to-Cloudflare | Cloudflare-to-Origin | Certificate Required at Origin |
|------|----------------------|---------------------|-------------------------------|
| **Off** | HTTP | HTTP | No |
| **Flexible** | HTTPS | HTTP | No |
| **Full** | HTTPS | HTTPS | Self-signed OK |
| **Full (Strict)** | HTTPS | HTTPS | Valid CA-signed cert required |

**Recommendation:** Use **Full (Strict)** whenever possible. Flexible mode is
a common source of redirect loops because the origin sees HTTP requests and
tries to redirect to HTTPS, which Cloudflare then proxies back as HTTP, creating
an infinite loop.

### Always Use HTTPS

**Dashboard:** SSL/TLS > Edge Certificates > Always Use HTTPS

This adds a 301 redirect from `http://` to `https://` at the Cloudflare edge.
For Pages deployments on `*.pages.dev`, HTTPS is enforced automatically.

**Warning:** If your origin is configured to also redirect HTTP to HTTPS and
you are using Flexible SSL mode, this creates a redirect loop. Either:
- Switch to Full (Strict) SSL mode, or
- Remove the HTTP-to-HTTPS redirect from your origin

### Custom Domains

1. Go to **Workers & Pages > your project > Custom domains**
2. Add domain (must be on a Cloudflare-managed DNS zone)
3. Cloudflare auto-provisions a certificate (usually within minutes)
4. Set SSL mode to Full (Strict) at the zone level

For domains not on Cloudflare DNS, you must first add the domain to Cloudflare
and update nameservers.

### HSTS via Dashboard

In addition to the `_headers` file, HSTS can be enabled at the zone level:

**Dashboard:** SSL/TLS > Edge Certificates > HTTP Strict Transport Security (HSTS)

This sets HSTS globally for the zone. If you also set it in `_headers`, the
`_headers` value takes precedence for Pages routes.

---

## Caching Headers

### _headers File Caching Rules

```
# HTML pages -- never cache (always revalidate)
/
  Cache-Control: public, max-age=0, must-revalidate

/*.html
  Cache-Control: public, max-age=0, must-revalidate

# Hashed static assets (JS, CSS with content hash in filename)
/assets/*
  Cache-Control: public, max-age=31536000, immutable

# Images
/images/*
  Cache-Control: public, max-age=604800

# Fonts
/fonts/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

# Service worker -- never cache
/sw.js
  Cache-Control: public, max-age=0, must-revalidate

# Manifest
/manifest.json
  Cache-Control: public, max-age=604800
```

### Cloudflare CDN Cache Tiers

Cloudflare has two separate cache layers:

**Browser Cache TTL** -- How long the visitor's browser caches the asset.
Controlled by `Cache-Control` headers from your `_headers` file or origin.

**Edge Cache TTL** -- How long Cloudflare's CDN edge nodes cache the asset.
Configured via:
- Dashboard: Caching > Configuration > Browser Cache TTL (zone-wide default)
- Cache Rules (path-specific, more granular)
- `Cloudflare-CDN-Cache-Control` header (programmatic, per-response)
- `CDN-Cache-Control` header (standard, per-response)

```
/api/*
  Cache-Control: no-store
  CDN-Cache-Control: no-store

/assets/*
  Cache-Control: public, max-age=31536000, immutable
  CDN-Cache-Control: max-age=2592000
```

**`CDN-Cache-Control`** is stripped before reaching the browser. It controls
Cloudflare edge cache independently of browser cache.

### Cache Rules via Dashboard

**Dashboard:** Caching > Cache Rules

Cache Rules let you override caching behavior per-path without touching code:

| Setting | Effect |
|---------|--------|
| Eligible for cache | Lets Cloudflare cache the response |
| Edge TTL | How long Cloudflare caches at the edge |
| Browser TTL | Overrides Cache-Control for the browser |
| Cache Key | Customize what makes a cached response unique |
| Bypass cache | Skip caching entirely |

Example rule: Cache everything under `/api/public/` for 1 hour at the edge
but 5 minutes in the browser.

### Purging Cache

**Full purge:**
- Dashboard: Caching > Configuration > Purge Everything
- API: `POST /zones/{zone_id}/purge_cache` with `{"purge_everything": true}`

**Selective purge:**
- By URL: Dashboard or API with `{"files": ["https://example.com/style.css"]}`
- By tag: Requires Enterprise (uses `Cache-Tag` header)
- By prefix: `{"prefixes": ["https://example.com/assets/"]}`

```bash
# Purge specific URLs via API
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache" \
  -H "Authorization: Bearer {api_token}" \
  -H "Content-Type: application/json" \
  --data '{"files":["https://example.com/assets/style.css","https://example.com/assets/app.js"]}'
```

After a Pages deployment, Cloudflare **automatically** purges the cache for the
project. Manual purging is typically only needed when changing Cache Rules or
debugging stale content.

---

## Cloudflare-Specific Features

### Pages Functions (File-Based Routing)

Place JavaScript/TypeScript files in a `functions/` directory at the project
root. The file path maps to the URL route:

```
functions/
  api/
    hello.js          -> /api/hello
    users/
      [id].js         -> /api/users/:id
      index.js        -> /api/users
    posts/
      [[path]].js     -> /api/posts/* (catch-all)
  _middleware.js       -> runs on every request
```

**Example function (`functions/api/hello.js`):**

```js
export async function onRequestGet(context) {
  return new Response(JSON.stringify({ message: "Hello from Pages Functions" }), {
    headers: { "Content-Type": "application/json" },
  });
}

export async function onRequestPost(context) {
  const body = await context.request.json();
  return new Response(JSON.stringify({ received: body }), {
    headers: { "Content-Type": "application/json" },
  });
}
```

**Middleware (`functions/_middleware.js`):**

```js
export async function onRequest(context) {
  // Add headers to every response
  const response = await context.next();
  response.headers.set("X-Custom-Header", "my-value");
  return response;
}
```

### Workers (Advanced)

For logic beyond file-based routing, use a `_worker.js` file in the build
output directory. This replaces Pages Functions entirely for that project:

```js
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // API routes handled by the worker
    if (url.pathname.startsWith("/api/")) {
      return new Response(JSON.stringify({ status: "ok" }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // Everything else falls through to static assets
    return env.ASSETS.fetch(request);
  },
};
```

**Note:** `_worker.js` and `functions/` are mutually exclusive. If both exist,
`_worker.js` takes precedence.

### KV Storage

Bind a KV namespace in your Pages project settings:

**Dashboard:** Workers & Pages > your project > Settings > Bindings > KV

```js
// functions/api/data.js
export async function onRequestGet(context) {
  const value = await context.env.MY_KV.get("my-key");
  return new Response(value || "not found");
}

export async function onRequestPut(context) {
  const body = await context.request.text();
  await context.env.MY_KV.put("my-key", body);
  return new Response("saved");
}
```

### Environment Variables

Set environment variables in the dashboard:

**Dashboard:** Workers & Pages > your project > Settings > Environment variables

Variables are available in Pages Functions via `context.env`:

```js
export async function onRequestGet(context) {
  const apiKey = context.env.API_KEY;
  // Use apiKey...
}
```

**Separate production and preview variables.** The dashboard lets you set
different values for Production vs Preview environments.

Environment variables are **not** available at build time by default. To use
them during the build, they must be set in the Build configuration section.

### Build Configuration

**Dashboard:** Workers & Pages > your project > Settings > Builds & deployments

Key settings:

| Setting | Example |
|---------|---------|
| Build command | `npm run build` |
| Build output directory | `dist`, `build`, `out`, `.next` |
| Root directory | `/` or `/packages/web` (monorepos) |
| Node.js version | Set via `NODE_VERSION` env var (e.g., `18`) |

```
# Environment variables for build
NODE_VERSION=18
NPM_FLAGS=--prefer-offline
```

### Preview Deployments

Every push to a non-production branch generates a preview deployment at:

```
https://<commit-hash>.<project-name>.pages.dev
```

Preview URLs are shareable but not indexed by search engines (Cloudflare sets
`X-Robots-Tag: noindex` on preview deployments automatically).

**Branch-specific previews:**

```
https://<branch-name>.<project-name>.pages.dev
```

Configure branch control in the dashboard to limit which branches trigger
preview deployments.

---

## Common Gotchas

### _headers File: 100-Rule Limit

The `_headers` file supports a maximum of **100 header rules** (a rule is one
URL pattern block). Each block can have multiple headers, but the block itself
counts as one rule.

```
# This is 1 rule with 5 headers (fine)
/*
  Header-One: value
  Header-Two: value
  Header-Three: value
  Header-Four: value
  Header-Five: value

# This is a 2nd rule
/api/*
  Access-Control-Allow-Origin: *
```

If you exceed 100 rules, additional rules are silently ignored. Use Pages
Functions middleware for complex header logic instead.

### _redirects File: 2000-Rule Limit

The `_redirects` file supports a maximum of **2000 redirect rules**. The first
2000 rules are processed; the rest are silently dropped.

For large-scale redirects (site migrations), use **Bulk Redirects** via the
Cloudflare dashboard instead.

### Rocket Loader Can Break Scripts

**Dashboard:** Speed > Optimization > Content Optimization > Rocket Loader

Rocket Loader defers loading of all JavaScript to improve paint times. It works
by rewriting `<script>` tags at the Cloudflare edge. This can break:

- Inline scripts that must execute synchronously
- Scripts that depend on DOM-ready ordering
- Third-party widgets (chat, analytics, embeds)
- Scripts using `document.write`

**Fix:** Disable Rocket Loader for the zone, or add `data-cfasync="false"` to
critical script tags:

```html
<script data-cfasync="false" src="/critical-script.js"></script>
```

### Always Use HTTPS Redirect Loops

If both of these are true, you get an infinite redirect loop:
1. **Always Use HTTPS** is enabled
2. SSL mode is set to **Flexible**

The loop: Browser requests HTTP -> Cloudflare redirects to HTTPS -> Cloudflare
connects to origin via HTTP (Flexible) -> Origin redirects HTTP to HTTPS ->
Cloudflare follows redirect -> Origin redirects again -> loop.

**Fix:** Set SSL mode to **Full** or **Full (Strict)**.

### Auto Minification

**Dashboard:** Speed > Optimization > Content Optimization > Auto Minify

Cloudflare can auto-minify HTML, CSS, and JavaScript at the edge. This can
cause issues:

- Breaks inline JavaScript that relies on whitespace or comments
- Can mangle certain CSS constructs
- Adds processing time at the edge
- Makes debugging harder (source doesn't match served content)

**Recommendation:** Handle minification in your build process and disable
Cloudflare Auto Minify. Build-time minification gives you source maps and
predictable output.

**Note:** Cloudflare deprecated Auto Minify in 2024 and is replacing it with
content compression (Brotli/gzip). New zones may not have this setting.

### Browser Integrity Check Blocking Bots

**Dashboard:** Security > Settings > Browser Integrity Check

This feature checks HTTP headers for common patterns used by abusive bots. It
can inadvertently block:

- Monitoring services (Pingdom, UptimeRobot)
- Search engine crawlers with non-standard user agents
- API clients
- CI/CD health checks

**Fix:** Either disable Browser Integrity Check, or create a WAF rule to
skip the check for known-good IPs or user agents:

**Dashboard:** Security > WAF > Custom Rules

```
# Example: Skip security checks for monitoring service
(http.user_agent contains "UptimeRobot") -> Skip: Browser Integrity Check
```

### Email Address Obfuscation

**Dashboard:** Scrape Shield > Email Address Obfuscation

Cloudflare replaces email addresses in HTML with JavaScript-decoded versions
to prevent scraping. This can break:

- `mailto:` links in JavaScript frameworks (React, Vue)
- Email addresses rendered dynamically
- Structured data / JSON-LD containing email addresses

**Fix:** Disable if your framework handles email rendering, or wrap emails in
`data-cfasync="false"` elements.

### SPA Routing Conflicts

For single-page apps, you need a catch-all rewrite, but it must be the **last**
rule in `_redirects`:

```
# Specific redirects first
/old-page  /new-page  301
/legacy/*  /modern/:splat  301

# SPA catch-all MUST be last
/*  /index.html  200
```

If the catch-all is not last, it intercepts all requests and no other redirects
execute.

---

## Complete Config Example

### Production _headers File

```
# ============================================
# Security Headers (all pages)
# ============================================
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
  Content-Security-Policy: default-src 'self'; script-src 'self' https://www.googletagmanager.com https://www.google-analytics.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com; connect-src 'self' https://www.google-analytics.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests
  Cross-Origin-Opener-Policy: same-origin
  Cross-Origin-Resource-Policy: same-origin

# ============================================
# Cache: HTML (never cache, always revalidate)
# ============================================
/
  Cache-Control: public, max-age=0, must-revalidate

/*.html
  Cache-Control: public, max-age=0, must-revalidate

# ============================================
# Cache: Hashed assets (cache forever)
# ============================================
/assets/*
  Cache-Control: public, max-age=31536000, immutable

# ============================================
# Cache: Images (1 week)
# ============================================
/images/*
  Cache-Control: public, max-age=604800

# ============================================
# Cache: Fonts (cache forever, allow cross-origin)
# ============================================
/fonts/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

# ============================================
# Service worker (never cache)
# ============================================
/sw.js
  Cache-Control: public, max-age=0, must-revalidate

# ============================================
# API routes (CORS + no cache)
# ============================================
/api/*
  Cache-Control: no-store
  Access-Control-Allow-Origin: https://example.com
  Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
  Access-Control-Allow-Headers: Content-Type, Authorization
```

### Production _redirects File

```
# ============================================
# Domain-level redirects
# ============================================
# www to non-www (handle in Cloudflare DNS/Page Rules instead for better perf)

# ============================================
# Page redirects (301 permanent)
# ============================================
/old-about        /about           301
/old-contact      /contact         301
/blog/old-post    /blog/new-post   301

# ============================================
# Section migrations
# ============================================
/old-blog/*       /blog/:splat     301
/docs/v1/*        /docs/v2/:splat  301
/help/*           /support/:splat  301

# ============================================
# Vanity URLs (302 so they can change)
# ============================================
/go/signup        /register        302
/go/demo          /schedule-demo   302

# ============================================
# External redirects
# ============================================
/twitter          https://twitter.com/example    301
/github           https://github.com/example     301

# ============================================
# SPA catch-all (MUST be last)
# ============================================
/*                /index.html                    200
```

### Dashboard Checklist

After deploying, verify these Cloudflare dashboard settings:

| Setting | Location | Recommended Value |
|---------|----------|-------------------|
| SSL mode | SSL/TLS > Overview | Full (Strict) |
| Always Use HTTPS | SSL/TLS > Edge Certificates | On |
| HSTS | SSL/TLS > Edge Certificates | Enabled (or via _headers) |
| Minimum TLS Version | SSL/TLS > Edge Certificates | TLS 1.2 |
| Auto Minify | Speed > Optimization | Off (use build-time minification) |
| Rocket Loader | Speed > Optimization | Off (unless tested thoroughly) |
| Browser Integrity Check | Security > Settings | On (monitor for false positives) |
| Email Obfuscation | Scrape Shield | Off (if using JS framework) |
| Browser Cache TTL | Caching > Configuration | Respect Existing Headers |
| Brotli | Speed > Optimization | On |
