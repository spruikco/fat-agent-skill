# Netlify -- Platform Fix Reference

Netlify is a cloud platform for static sites and serverless functions. Sites are
deployed from a Git repository, built on Netlify's infrastructure, and served
from a global CDN. Configuration lives in two places: a `netlify.toml` file in
the project root (version-controlled, structured TOML) and flat files like
`_headers` and `_redirects` placed in the **publish directory** (the folder
Netlify actually deploys, often `dist/`, `build/`, or `public/`).

This reference covers the most common fixes for issues that FAT Agent surfaces
in post-launch audits of Netlify-hosted sites.

---

## Security Headers

### Approach 1: `_headers` file

Create a plain-text file named `_headers` and place it in your **publish
directory**. Each path is followed by indented header declarations.

```text
# ---- Security headers applied to every page and asset ----
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
```

### Approach 2: `netlify.toml`

Add a `[[headers]]` block to `netlify.toml` in your project root. This approach
supports deploy-context overrides and is version-controlled alongside your build
settings.

```toml
[[headers]]
  for = "/*"
  [headers.values]
    Strict-Transport-Security = "max-age=31536000; includeSubDomains; preload"
    X-Content-Type-Options = "nosniff"
    X-Frame-Options = "DENY"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Permissions-Policy = "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    Content-Security-Policy = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
```

### Header-by-header notes

| Header | Recommended Value | Notes |
|--------|-------------------|-------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Only add `preload` if you have submitted your domain to hstspreload.org. Once preloaded, removal is slow. |
| `X-Content-Type-Options` | `nosniff` | No configuration needed -- always set this. |
| `X-Frame-Options` | `DENY` (or `SAMEORIGIN` if you embed your own pages) | Being superseded by CSP `frame-ancestors`, but still recommended for older browser coverage. |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Balanced default. Use `no-referrer` for maximum privacy. |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disable every API you do not use. Add `interest-cohort=()` to opt out of FLoC/Topics. |
| `Content-Security-Policy` | Site-specific | Start strict and loosen as needed. FAT Agent flags absence but cannot auto-generate a policy. |

---

## Redirects & Rewrites

Netlify supports two syntaxes: a flat `_redirects` file and structured
`[[redirects]]` blocks in `netlify.toml`. Rules from `_redirects` are processed
**first**, followed by rules in `netlify.toml`. Both are **first-match-wins** --
put specific rules before general catch-alls.

### `_redirects` file syntax

```text
# Syntax: from  to  [status]  [conditions]

# 301 permanent redirect (default status if omitted)
/old-page   /new-page   301

# 302 temporary redirect
/sale       /promo      302

# 200 rewrite (proxy -- URL stays the same in the browser)
/api/*      https://api.example.com/:splat   200

# Custom 404
/*          /404.html   404
```

Place this file in your **publish directory**.

### `netlify.toml` syntax

```toml
[[redirects]]
  from = "/old-page"
  to = "/new-page"
  status = 301

[[redirects]]
  from = "/api/*"
  to = "https://api.example.com/:splat"
  status = 200
  force = true          # proxy even if a local file exists at that path

[[redirects]]
  from = "/*"
  to = "/404.html"
  status = 404
```

### HTTP to HTTPS redirect

Netlify handles this **automatically** when "Force HTTPS" is enabled in
**Domain management > HTTPS > Force HTTPS**. You do **not** need a redirect
rule for this. Netlify issues a 301 redirect from `http://` to `https://`
at the CDN edge before your redirect rules are evaluated.

### www to non-www (or reverse)

Netlify handles this through **domain aliases**. Set your preferred domain as
the primary custom domain in **Domain management > Domains**. Netlify will
automatically 301-redirect the other variant.

For example, if `example.com` is the primary domain and `www.example.com` is a
domain alias, Netlify redirects `www.example.com/*` to `example.com/*` with a
301 automatically.

If you need manual control, you can add a rule:

```text
# In _redirects -- force www to apex
https://www.example.com/*   https://example.com/:splat   301!
```

The `!` (force) flag ensures the redirect fires even if a file exists at that
path on the www subdomain.

### Trailing slash consistency

Netlify's **Pretty URLs** feature (enabled by default) controls trailing-slash
behavior:

- **Pretty URLs ON (default):** `/about` serves `/about/index.html` and
  redirects `/about.html` to `/about/`.
- **Pretty URLs OFF:** URLs are served as-is.

You **cannot** use redirect rules to add or remove trailing slashes -- Netlify's
URL normalization runs before redirect processing. To change trailing-slash
behavior, toggle Pretty URLs in **Site configuration > Build & deploy > Post
processing > Asset optimization**.

### Custom 404 pages

Create a `404.html` file in your publish directory. Netlify will automatically
serve it for any path that does not match a file, with a 404 status code.

Alternatively, add an explicit catch-all:

```text
# _redirects
/*   /404.html   404
```

Or in `netlify.toml`:

```toml
[[redirects]]
  from = "/*"
  to = "/404.html"
  status = 404
```

**Important:** Place this rule **last** so it only matches after all other rules
have been checked.

### SPA fallback redirects

For single-page applications (React Router, Vue Router, etc.), rewrite all
paths to `index.html` with a 200 status so the client-side router handles
routing:

```text
# _redirects
/*   /index.html   200
```

```toml
# netlify.toml
[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

This rule should be the **last** redirect rule. It will only fire if no static
file exists at the requested path (because `force` defaults to `false`).

---

## SSL / HTTPS Configuration

### Automatic SSL via Let's Encrypt

Netlify automatically provisions a free TLS certificate from Let's Encrypt for
every site, including custom domains. Certificates are renewed automatically
before expiry. No manual setup is required.

- If your domain uses **Netlify DNS**, Netlify provisions a **wildcard
  certificate** covering all subdomains.
- If your domain uses **external DNS**, Netlify provisions a certificate for
  the specific domains configured (requires DNS records pointing to Netlify).

### Custom domains and DNS configuration

**Option A -- Netlify DNS (recommended):**

1. Add your domain in **Domain management > Domains > Add custom domain**.
2. When prompted, choose "Set up Netlify DNS".
3. Update your domain registrar's nameservers to the Netlify nameservers shown.
4. Netlify provisions the certificate automatically once DNS propagates.

**Option B -- External DNS:**

1. Add your domain in **Domain management > Domains > Add custom domain**.
2. At your DNS provider, create:
   - An `A` record pointing to Netlify's load balancer IP: `75.2.60.5`
   - A `CNAME` record for `www` pointing to `[your-site].netlify.app`
3. Wait for DNS propagation and certificate provisioning (can take up to 24h).
4. Optionally add a `CAA` record allowing `letsencrypt.org` to issue
   certificates for your domain.

### Force HTTPS setting

Navigate to **Domain management > HTTPS > Force HTTPS** and enable it. This
makes Netlify issue a 301 redirect for all HTTP requests to HTTPS at the CDN
edge.

### HSTS preload considerations

Before adding `preload` to your HSTS header:

1. Confirm HTTPS works correctly on your site and all subdomains.
2. Confirm the HSTS header is served on the apex domain over HTTPS.
3. Submit your domain at [hstspreload.org](https://hstspreload.org).
4. Understand that **removal from the preload list takes months**. Only add
   `preload` once you are certain the site will remain HTTPS-only permanently.

A safe ramp-up strategy:

```text
# Week 1: short max-age, no preload
Strict-Transport-Security: max-age=300; includeSubDomains

# Week 2: increase max-age
Strict-Transport-Security: max-age=86400; includeSubDomains

# Week 3+: full year, add preload once confident
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

---

## Caching Headers

Netlify's CDN applies its own caching layer. By default, Netlify treats static
asset responses as fresh for up to one year and uses **instant cache
invalidation** on deploy -- when you deploy, Netlify purges stale assets from
the CDN automatically. Browser caching, however, is fully under your control via
the `Cache-Control` header.

### Strategy

| Content type | Cache-Control | Rationale |
|--------------|---------------|-----------|
| HTML pages | `public, max-age=0, must-revalidate` | Always fetch the latest version. Netlify's CDN handles edge caching. |
| Hashed assets (JS, CSS with hash in filename) | `public, max-age=31536000, immutable` | The filename changes when content changes, so the browser can cache forever. |
| Unhashed static assets (JS, CSS without hash) | `public, max-age=3600` | Short cache to balance freshness and performance. |
| Fonts | `public, max-age=31536000, immutable` | Fonts rarely change and are often hashed by bundlers. |
| Images | `public, max-age=86400` | One day; adjust based on how often images change. |
| Favicons & web manifest | `public, max-age=3600` | Short cache; these are small and change occasionally. |

### Complete `_headers` file with caching rules

```text
# =============================================
#  Security Headers (all paths)
# =============================================
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()

# =============================================
#  HTML -- no browser cache, always revalidate
# =============================================
/*.html
  Cache-Control: public, max-age=0, must-revalidate

/
  Cache-Control: public, max-age=0, must-revalidate

# =============================================
#  Hashed JS & CSS -- cache forever
# =============================================
/assets/*
  Cache-Control: public, max-age=31536000, immutable

/_next/static/*
  Cache-Control: public, max-age=31536000, immutable

/static/js/*
  Cache-Control: public, max-age=31536000, immutable

/static/css/*
  Cache-Control: public, max-age=31536000, immutable

# =============================================
#  Fonts -- long cache
# =============================================
/*.woff2
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

/*.woff
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

/fonts/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

# =============================================
#  Images -- 1 day cache
# =============================================
/images/*
  Cache-Control: public, max-age=86400

/*.svg
  Cache-Control: public, max-age=86400

/*.png
  Cache-Control: public, max-age=86400

/*.jpg
  Cache-Control: public, max-age=86400

/*.webp
  Cache-Control: public, max-age=86400

/*.avif
  Cache-Control: public, max-age=86400

# =============================================
#  Favicons & manifest
# =============================================
/favicon.ico
  Cache-Control: public, max-age=3600

/site.webmanifest
  Cache-Control: public, max-age=3600

/browserconfig.xml
  Cache-Control: public, max-age=3600
```

### Equivalent `netlify.toml` approach (selected rules)

```toml
# HTML pages
[[headers]]
  for = "/*.html"
  [headers.values]
    Cache-Control = "public, max-age=0, must-revalidate"

# Hashed assets
[[headers]]
  for = "/assets/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

# Fonts
[[headers]]
  for = "/*.woff2"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
    Access-Control-Allow-Origin = "*"

# Images
[[headers]]
  for = "/images/*"
  [headers.values]
    Cache-Control = "public, max-age=86400"
```

---

## Netlify-Specific Features

### Netlify Forms

Netlify can process form submissions from static HTML without a backend.

**Basic setup:**

```html
<form name="contact" method="POST" data-netlify="true">
  <input type="text" name="name" required />
  <input type="email" name="email" required />
  <textarea name="message" required></textarea>
  <button type="submit">Send</button>
</form>
```

The `data-netlify="true"` attribute (or a bare `netlify` attribute) tells
Netlify's build bot to detect the form during deploy. Netlify strips the
attribute and injects a hidden `form-name` input automatically.

**Honeypot spam filtering:**

```html
<form name="contact" method="POST" data-netlify="true" data-netlify-honeypot="bot-field">
  <!-- Hidden from real users via CSS -->
  <p class="hidden">
    <label>Don't fill this out: <input name="bot-field" /></label>
  </p>
  <input type="text" name="name" required />
  <input type="email" name="email" required />
  <textarea name="message" required></textarea>
  <button type="submit">Send</button>
</form>
```

```css
.hidden {
  position: absolute;
  left: -9999px;
  height: 0;
  overflow: hidden;
}
```

**reCAPTCHA:**

```html
<form name="contact" method="POST" data-netlify="true" data-netlify-recaptcha="true">
  <input type="text" name="name" required />
  <input type="email" name="email" required />
  <textarea name="message" required></textarea>
  <div data-netlify-recaptcha="true"></div>
  <button type="submit">Send</button>
</form>
```

**AJAX submission (for SPAs or custom UX):**

```js
async function handleSubmit(event) {
  event.preventDefault();
  const form = event.target;
  const formData = new FormData(form);

  try {
    const response = await fetch("/", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(formData).toString(),
    });

    if (response.ok) {
      // Show success message
    } else {
      // Handle error
    }
  } catch (error) {
    // Handle network error
  }
}
```

**Important:** Netlify Forms does **not** support `Content-Type: application/json`.
The body must be URL-encoded. The `form-name` field must be included in the
POST body (it is included automatically if you use `FormData` from the form
element).

For JavaScript-rendered forms (React, Vue, etc.), you must also include a hidden
HTML form in your static markup so Netlify's build bot can detect it:

```html
<!-- Hidden form for Netlify's build bot (placed in index.html or a static template) -->
<form name="contact" netlify hidden>
  <input type="text" name="name" />
  <input type="email" name="email" />
  <textarea name="message"></textarea>
</form>
```

### Deploy previews vs production

Every pull request automatically gets a **deploy preview** at a unique URL like
`deploy-preview-42--your-site.netlify.app`. Use this for QA before merging.

Key differences from production:

- Deploy previews use a Netlify subdomain (no custom domain).
- Search engines should not index them (Netlify sets `X-Robots-Tag: noindex`).
- Environment variables may differ if you set context-specific values.

Configure preview behavior in `netlify.toml`:

```toml
# Production-specific settings
[context.production]
  command = "npm run build"
  environment = { NODE_ENV = "production" }

# Deploy preview settings
[context.deploy-preview]
  command = "npm run build"
  environment = { NODE_ENV = "preview", SHOW_DRAFT_CONTENT = "true" }
```

### Branch deploys

Enable branch deploys in **Site configuration > Build & deploy > Branches and
deploy contexts** to get a subdomain for each branch:

- `main` branch deploys to production.
- `staging` branch deploys to `staging--your-site.netlify.app`.

```toml
[context.branch-deploy]
  command = "npm run build"

# Named branch context
[context.staging]
  command = "npm run build"
  environment = { API_URL = "https://staging-api.example.com" }
```

### Edge Functions for dynamic headers

When you need headers that depend on request data (geolocation, cookies, A/B
testing), use Edge Functions. Custom headers defined in `_headers` or
`netlify.toml` only apply to static files served from Netlify's backing store --
they do not apply to responses from Edge Functions or serverless functions.

Create an edge function at `netlify/edge-functions/security-headers.ts`:

```typescript
import type { Context } from "@netlify/edge-functions";

export default async (request: Request, context: Context) => {
  const response = await context.next();

  // Add security headers to every response
  response.headers.set(
    "Strict-Transport-Security",
    "max-age=31536000; includeSubDomains; preload"
  );
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set(
    "Referrer-Policy",
    "strict-origin-when-cross-origin"
  );
  response.headers.set(
    "Permissions-Policy",
    "camera=(), microphone=(), geolocation=()"
  );

  return response;
};

export const config = { path: "/*" };
```

Register it in `netlify.toml`:

```toml
[[edge_functions]]
  function = "security-headers"
  path = "/*"
```

### Environment variables

Set environment variables in **Site configuration > Environment variables** or
in `netlify.toml` (for non-secret values only -- secrets should never be
committed to version control):

```toml
[build.environment]
  NODE_VERSION = "20"
  NPM_FLAGS = "--prefer-offline"

[context.production.environment]
  API_URL = "https://api.example.com"

[context.deploy-preview.environment]
  API_URL = "https://staging-api.example.com"
```

### Build plugins

Install plugins via the Netlify UI or declare them in `netlify.toml`.

**Lighthouse plugin** (runs Lighthouse after every deploy):

```toml
[[plugins]]
  package = "@netlify/plugin-lighthouse"

  [plugins.inputs]
    # Audit these paths (default is just "/")
    audits = [
      { path = "/", thresholds = { performance = 0.9, accessibility = 0.9, best-practices = 0.9, seo = 0.9 } },
      { path = "/about" },
      { path = "/contact" }
    ]
```

**Sitemap plugin:**

```toml
[[plugins]]
  package = "@netlify/plugin-sitemap"

  [plugins.inputs]
    buildDir = "dist"
    prettyURLs = true
    # Exclude paths from the sitemap
    exclude = ["/admin", "/thank-you"]
```

**Other useful plugins:**

- `netlify-plugin-submit-sitemap` -- Pings search engines on deploy.
- `netlify-plugin-checklinks` -- Validates internal links at build time.
- `@netlify/plugin-csp-nonce` -- Injects CSP nonces into inline scripts.

---

## Common Gotchas

### 1. `_headers` file must be in the publish directory

The `_headers` and `_redirects` files must be in the directory that Netlify
deploys (e.g., `dist/`, `build/`, `public/`), **not** the project root.

If your build tool does not copy them automatically, add a step:

```toml
[build]
  command = "npm run build && cp _headers _redirects dist/"
  publish = "dist"
```

Or use `netlify.toml` for headers and redirects instead -- it is always read
from the project root.

### 2. `_redirects` rules are first-match-wins

The first rule that matches wins. Place specific rules before general catch-alls.

```text
# CORRECT order:
/blog/old-post   /blog/new-post   301
/blog/*          /blog/index.html  200

# WRONG order -- the catch-all matches first and the specific rule never fires:
/blog/*          /blog/index.html  200
/blog/old-post   /blog/new-post   301
```

Also note: rules in `_redirects` are processed **before** rules in
`netlify.toml`. If both files have rules, `_redirects` takes priority.

### 3. `netlify.toml` headers vs `_headers` file precedence

When both files define headers for the same path, the values are **merged**.
If they define the **same header name** for the same path, the `_headers` file
value takes precedence over `netlify.toml`.

Recommendation: pick one approach and use it consistently. `netlify.toml` is
generally preferred because it supports deploy-context scoping and keeps all
configuration in a single file.

### 4. Asset optimization settings

Netlify offers optional post-processing for CSS, JS, and images (**Site
configuration > Build & deploy > Post processing > Asset optimization**). These
are **off by default** and can sometimes cause issues:

- CSS/JS minification can break already-minified bundles.
- Image compression may re-compress already-optimized images.
- Pretty URLs affects trailing-slash behavior (see Redirects section).

If your build tool already handles minification and optimization, leave these
off.

### 5. Mixed content issues when migrating from HTTP

After enabling HTTPS, audit your site for mixed content -- resources loaded over
`http://` on an `https://` page. Common culprits:

- Hardcoded `http://` URLs in CMS content or templates.
- Third-party scripts, fonts, or images referenced via HTTP.
- Inline CSS `url()` values pointing to HTTP resources.

Fix by using protocol-relative URLs (`//cdn.example.com/...`) or, better,
explicit `https://` URLs. Adding the CSP header `upgrade-insecure-requests`
tells browsers to automatically upgrade HTTP subresource requests:

```text
/*
  Content-Security-Policy: upgrade-insecure-requests
```

### 6. Netlify Forms detection requirements

Netlify's build bot must detect your form in the **static HTML** at build time.
This means:

- The `<form>` tag must have either `data-netlify="true"` or a bare `netlify`
  attribute.
- For JavaScript-rendered forms (React, Vue, Svelte), you must include a
  hidden HTML form with matching `name` and field `name` attributes in your
  static HTML (e.g., in `public/index.html`).
- The form `name` attribute must be unique across your site.
- If the form is not detected at build time, submissions will return a 404.

### 7. Custom headers do not apply to proxied content

Headers defined in `_headers` or `netlify.toml` only apply to files served
directly from Netlify's CDN. They do **not** apply to:

- Proxied responses (status 200 rewrites to external URLs).
- Responses from Netlify Functions or Edge Functions.
- Content served by Netlify's built-in auth or form handlers.

For these cases, set headers in your function code or use Edge Functions to
add headers to proxied responses.

---

## Complete Config Example

### `netlify.toml`

```toml
# =============================================================================
#  Build settings
# =============================================================================
[build]
  command = "npm run build"
  publish = "dist"
  # Copy flat config files into the publish directory if needed
  # command = "npm run build && cp _headers _redirects dist/"

[build.environment]
  NODE_VERSION = "20"

# =============================================================================
#  Deploy context overrides
# =============================================================================
[context.production]
  command = "npm run build"
  environment = { NODE_ENV = "production" }

[context.deploy-preview]
  command = "npm run build"
  environment = { NODE_ENV = "preview" }

# =============================================================================
#  Redirects (processed AFTER _redirects file rules)
# =============================================================================

# Specific page redirects
[[redirects]]
  from = "/old-page"
  to = "/new-page"
  status = 301

# API proxy
[[redirects]]
  from = "/api/*"
  to = "https://api.example.com/:splat"
  status = 200
  force = true
  [redirects.headers]
    X-Custom-Header = "my-value"

# SPA fallback -- must be LAST
[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

# =============================================================================
#  Security headers (all paths)
# =============================================================================
[[headers]]
  for = "/*"
  [headers.values]
    Strict-Transport-Security = "max-age=31536000; includeSubDomains; preload"
    X-Content-Type-Options = "nosniff"
    X-Frame-Options = "DENY"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Permissions-Policy = "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    # Adjust CSP to your site's needs
    Content-Security-Policy = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"

# =============================================================================
#  Caching headers
# =============================================================================

# HTML -- no browser cache
[[headers]]
  for = "/*.html"
  [headers.values]
    Cache-Control = "public, max-age=0, must-revalidate"

# Hashed JS/CSS assets -- cache forever
[[headers]]
  for = "/assets/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

# Fonts -- cache forever, allow cross-origin
[[headers]]
  for = "/*.woff2"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
    Access-Control-Allow-Origin = "*"

[[headers]]
  for = "/*.woff"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
    Access-Control-Allow-Origin = "*"

# Images -- 1 day
[[headers]]
  for = "/images/*"
  [headers.values]
    Cache-Control = "public, max-age=86400"

# Favicon -- 1 hour
[[headers]]
  for = "/favicon.ico"
  [headers.values]
    Cache-Control = "public, max-age=3600"

# =============================================================================
#  Plugins
# =============================================================================
[[plugins]]
  package = "@netlify/plugin-lighthouse"

  [plugins.inputs]
    audits = [
      { path = "/", thresholds = { performance = 0.9, accessibility = 0.9, best-practices = 0.9, seo = 0.9 } }
    ]

[[plugins]]
  package = "@netlify/plugin-sitemap"

  [plugins.inputs]
    buildDir = "dist"
    prettyURLs = true
```

### `_headers` (place in publish directory)

```text
# =============================================================================
#  Security headers
# =============================================================================
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'

# =============================================================================
#  HTML -- always revalidate
# =============================================================================
/*.html
  Cache-Control: public, max-age=0, must-revalidate

/
  Cache-Control: public, max-age=0, must-revalidate

# =============================================================================
#  Hashed assets -- cache forever
# =============================================================================
/assets/*
  Cache-Control: public, max-age=31536000, immutable

/_next/static/*
  Cache-Control: public, max-age=31536000, immutable

/static/js/*
  Cache-Control: public, max-age=31536000, immutable

/static/css/*
  Cache-Control: public, max-age=31536000, immutable

# =============================================================================
#  Fonts
# =============================================================================
/*.woff2
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

/*.woff
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

/fonts/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

# =============================================================================
#  Images
# =============================================================================
/images/*
  Cache-Control: public, max-age=86400

/*.svg
  Cache-Control: public, max-age=86400

/*.png
  Cache-Control: public, max-age=86400

/*.jpg
  Cache-Control: public, max-age=86400

/*.webp
  Cache-Control: public, max-age=86400

/*.avif
  Cache-Control: public, max-age=86400

# =============================================================================
#  Favicons & manifest
# =============================================================================
/favicon.ico
  Cache-Control: public, max-age=3600

/site.webmanifest
  Cache-Control: public, max-age=3600
```

### `_redirects` (place in publish directory)

```text
# Specific redirects (first-match-wins -- specific before general)
/old-page       /new-page       301
/legacy/*       /modern/:splat  301

# API proxy
/api/*          https://api.example.com/:splat  200

# SPA fallback (must be last)
/*              /index.html     200
```

---

## Verification & Testing

After deploying your configuration, verify headers and redirects:

```bash
# Check security headers
curl -I https://example.com

# Check a specific redirect
curl -I https://example.com/old-page

# Check caching headers on a static asset
curl -I https://example.com/assets/main.abc123.js

# Comprehensive security header audit
# Visit https://securityheaders.com and enter your URL

# SSL/TLS quality check
# Visit https://www.ssllabs.com/ssltest/ and enter your domain
```

For automated checks, use the Netlify CLI locally:

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Serve your site locally with Netlify's processing
netlify dev

# Deploy a preview to test configuration
netlify deploy

# Deploy to production
netlify deploy --prod
```

---

## Sources

- [Custom Headers -- Netlify Docs](https://docs.netlify.com/manage/routing/headers/)
- [Redirects and Rewrites -- Netlify Docs](https://docs.netlify.com/manage/routing/redirects/overview/)
- [Redirect Options -- Netlify Docs](https://docs.netlify.com/manage/routing/redirects/redirect-options/)
- [File-based Configuration -- Netlify Docs](https://docs.netlify.com/build/configure-builds/file-based-configuration/)
- [HTTPS (SSL) -- Netlify Docs](https://docs.netlify.com/manage/domains/secure-domains-with-https/https-ssl/)
- [Get Started with Domains -- Netlify Docs](https://docs.netlify.com/manage/domains/get-started-with-domains/)
- [Caching Overview -- Netlify Docs](https://docs.netlify.com/build/caching/caching-overview/)
- [Forms Setup -- Netlify Docs](https://docs.netlify.com/manage/forms/setup/)
- [Spam Filters -- Netlify Docs](https://docs.netlify.com/manage/forms/spam-filters/)
- [Edge Functions API -- Netlify Docs](https://docs.netlify.com/build/edge-functions/api/)
- [Netlify Plugin Lighthouse -- GitHub](https://github.com/netlify/netlify-plugin-lighthouse)
- [Caching Static Assets on Netlify -- Artem Sapegin](https://sapegin.me/blog/caching-static-assets-on-netlify/)
