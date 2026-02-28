# Vercel -- Platform Fix Reference

Vercel-specific configuration for fixing issues flagged by FAT Agent. Covers
`vercel.json` for all frameworks and `next.config.js` for Next.js projects.

---

## Security Headers

### vercel.json (any framework)

```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Strict-Transport-Security",
          "value": "max-age=31536000; includeSubDomains; preload"
        },
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "Referrer-Policy",
          "value": "strict-origin-when-cross-origin"
        },
        {
          "key": "Permissions-Policy",
          "value": "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        },
        {
          "key": "X-DNS-Prefetch-Control",
          "value": "on"
        },
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        }
      ]
    }
  ]
}
```

### next.config.js (Next.js projects)

The `headers()` function in `next.config.js` is the preferred approach for
Next.js on Vercel because it works in both local development and production.

```js
// next.config.js  (or next.config.mjs / next.config.ts)
const securityHeaders = [
  {
    key: 'Strict-Transport-Security',
    value: 'max-age=31536000; includeSubDomains; preload',
  },
  {
    key: 'X-Content-Type-Options',
    value: 'nosniff',
  },
  {
    key: 'X-Frame-Options',
    value: 'DENY',
  },
  {
    key: 'Referrer-Policy',
    value: 'strict-origin-when-cross-origin',
  },
  {
    key: 'Permissions-Policy',
    value: 'camera=(), microphone=(), geolocation=()',
  },
  {
    key: 'Content-Security-Policy',
    value: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
  },
];

const nextConfig = {
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: securityHeaders,
      },
    ];
  },
};

module.exports = nextConfig;
```

**CSP note:** The Content-Security-Policy value above is deliberately strict.
Most real sites need to loosen it for analytics, CDNs, or inline scripts.
Adjust `script-src`, `style-src`, and `connect-src` to match your actual
dependencies. For Next.js with inline scripts, you will likely need
`'unsafe-inline'` in `script-src` or use nonce-based CSP via middleware.

### Nonce-based CSP with Next.js middleware

For stricter CSP without `'unsafe-inline'` for scripts:

```ts
// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString('base64');
  const cspHeader = `
    default-src 'self';
    script-src 'self' 'nonce-${nonce}' 'strict-dynamic';
    style-src 'self' 'unsafe-inline';
    img-src 'self' data: https:;
    font-src 'self';
    connect-src 'self';
    frame-ancestors 'none';
    base-uri 'self';
    form-action 'self';
  `;

  const contentSecurityPolicyHeaderValue = cspHeader
    .replace(/\s{2,}/g, ' ')
    .trim();

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-nonce', nonce);
  requestHeaders.set(
    'Content-Security-Policy',
    contentSecurityPolicyHeaderValue
  );

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });

  response.headers.set(
    'Content-Security-Policy',
    contentSecurityPolicyHeaderValue
  );

  return response;
}
```

---

## Redirects & Rewrites

### vercel.json redirects

```json
{
  "redirects": [
    {
      "source": "/old-page",
      "destination": "/new-page",
      "permanent": true
    },
    {
      "source": "/blog/:slug",
      "destination": "/posts/:slug",
      "permanent": true
    },
    {
      "source": "/docs/:path*",
      "destination": "https://docs.example.com/:path*",
      "permanent": false
    }
  ]
}
```

- `"permanent": true` sends a 308 (permanent redirect).
- `"permanent": false` sends a 307 (temporary redirect).
- Use `:param` for named segments and `:path*` for wildcard catch-all.

**Limit:** `vercel.json` supports a maximum of 1,024 redirects. For larger
redirect maps, use Next.js middleware or `next.config.js` redirects.

### vercel.json rewrites

Rewrites serve content from a different path without changing the URL in the
browser.

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://api.example.com/:path*"
    },
    {
      "source": "/app/:path*",
      "destination": "/app/index.html"
    }
  ]
}
```

### next.config.js redirects

```js
const nextConfig = {
  async redirects() {
    return [
      {
        source: '/old-page',
        destination: '/new-page',
        permanent: true,
      },
      {
        source: '/blog/:slug',
        destination: '/posts/:slug',
        permanent: true,
      },
      // Regex support
      {
        source: '/post/:slug(\\d{1,})',
        destination: '/blog/:slug',
        permanent: false,
      },
    ];
  },
};
```

### next.config.js rewrites

```js
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'https://api.example.com/:path*',
      },
    ];
    // Or use beforeFiles / afterFiles / fallback for ordering:
    // return {
    //   beforeFiles: [],   // checked before pages/public files
    //   afterFiles: [],    // checked after pages but before fallback
    //   fallback: [],      // checked after everything else
    // };
  },
};
```

### Trailing slash handling

```json
// vercel.json
{
  "trailingSlash": false
}
```

```js
// next.config.js
const nextConfig = {
  trailingSlash: false, // or true -- pick one and be consistent
};
```

Setting `trailingSlash: false` redirects `/about/` to `/about`.
Setting `trailingSlash: true` redirects `/about` to `/about/`.
Being inconsistent causes duplicate content issues flagged by search engines.

### www to non-www (or vice versa)

Vercel handles this at the domain level. In your Vercel dashboard:

1. Add both `example.com` and `www.example.com` as domains.
2. Set one as primary; the other redirects automatically with a 308.

If you need to force it in `vercel.json`:

```json
{
  "redirects": [
    {
      "source": "/:path(.*)",
      "has": [{ "type": "host", "value": "www.example.com" }],
      "destination": "https://example.com/:path",
      "permanent": true
    }
  ]
}
```

### Custom 404 page

For non-Next.js projects, create a `404.html` in your output directory. Vercel
serves it automatically for any path that does not match a file or route.

For Next.js, create `pages/404.js` (Pages Router) or `app/not-found.tsx`
(App Router):

```tsx
// app/not-found.tsx  (App Router)
export default function NotFound() {
  return (
    <main>
      <h1>404 - Page Not Found</h1>
      <p>The page you are looking for does not exist.</p>
    </main>
  );
}
```

```js
// pages/404.js  (Pages Router)
export default function Custom404() {
  return <h1>404 - Page Not Found</h1>;
}
```

---

## SSL/HTTPS Configuration

### Automatic SSL

Vercel provisions and renews TLS certificates automatically for all domains
(custom and `.vercel.app`). No configuration needed.

- Uses Let's Encrypt certificates.
- Supports TLS 1.2 and 1.3.
- Certificates auto-renew before expiry.

### Custom domains

Add domains via the Vercel dashboard or CLI:

```bash
# Add a custom domain
vercel domains add example.com

# List current domains
vercel domains ls
```

DNS setup options:
- **A record:** Point `@` to `76.76.21.21`
- **CNAME:** Point `www` to `cname.vercel-dns.com`
- **Nameservers:** Use Vercel DNS for automatic configuration.

### Force HTTPS

Vercel redirects HTTP to HTTPS by default on all deployments. No configuration
is needed. If you additionally want HSTS to prevent future HTTP requests at the
browser level, add the `Strict-Transport-Security` header (see Security Headers
section above).

---

## Caching Headers

### Vercel's automatic caching

Vercel automatically applies caching behaviour based on content type:

| Content | Default Cache Behaviour |
|---------|------------------------|
| Static assets in `/public` or build output | Immutable, long-lived cache on Vercel Edge |
| Pages (SSR/SSG) | Varies by rendering strategy |
| API routes / serverless functions | No cache (`Cache-Control: private, no-cache`) |
| ISR pages | `s-maxage` with `stale-while-revalidate` |

### Cache-Control for API routes

In Next.js API routes, set `Cache-Control` explicitly:

```ts
// app/api/data/route.ts  (App Router)
export async function GET() {
  const data = await fetchData();

  return Response.json(data, {
    headers: {
      'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
    },
  });
}
```

```ts
// pages/api/data.ts  (Pages Router)
import type { NextApiRequest, NextApiResponse } from 'next';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  res.setHeader(
    'Cache-Control',
    'public, s-maxage=60, stale-while-revalidate=300'
  );
  res.json({ data: 'cached for 60s on edge, stale for 5min' });
}
```

**Key directives for Vercel:**
- `s-maxage=N` -- Cache on Vercel's edge CDN for N seconds.
- `stale-while-revalidate=N` -- Serve stale content while revalidating in the
  background for N seconds after `s-maxage` expires.
- `public` -- Allow edge caching (required for `s-maxage` to take effect).
- `private, no-cache` -- Never cache (default for serverless functions).
- `max-age=0, must-revalidate` -- Do not cache in the browser at all.

### ISR / SSG caching behaviour

**Static Site Generation (SSG):**
Pages built at `next build` time are served from the edge cache with immutable
headers. No revalidation occurs unless you redeploy.

**Incremental Static Regeneration (ISR):**

```tsx
// app/posts/[slug]/page.tsx  (App Router)
export const revalidate = 60; // revalidate every 60 seconds

export default async function PostPage({ params }: { params: { slug: string } }) {
  const post = await getPost(params.slug);
  return <article>{post.content}</article>;
}
```

```tsx
// pages/posts/[slug].tsx  (Pages Router)
export async function getStaticProps({ params }) {
  const post = await getPost(params.slug);
  return {
    props: { post },
    revalidate: 60, // regenerate at most every 60 seconds
  };
}
```

Vercel sets `Cache-Control: s-maxage=60, stale-while-revalidate` on ISR pages.
The first request after the revalidation window triggers a background rebuild.

**On-Demand Revalidation:**

```ts
// app/api/revalidate/route.ts
import { revalidatePath } from 'next/cache';
import { NextRequest } from 'next/server';

export async function POST(request: NextRequest) {
  const { path, secret } = await request.json();

  if (secret !== process.env.REVALIDATION_SECRET) {
    return Response.json({ error: 'Invalid secret' }, { status: 401 });
  }

  revalidatePath(path);
  return Response.json({ revalidated: true });
}
```

### Edge caching

Vercel caches responses at edge locations worldwide. Control edge caching with
the `CDN-Cache-Control` header for edge-only caching that does not affect
browser caching:

```ts
// Set edge cache independently of browser cache
return new Response(body, {
  headers: {
    'Cache-Control': 'max-age=0, must-revalidate',        // browser: no cache
    'CDN-Cache-Control': 'public, s-maxage=3600',          // edge: cache 1 hour
    'Vercel-CDN-Cache-Control': 'public, s-maxage=86400',  // vercel edge: cache 1 day
  },
});
```

Header precedence on Vercel:
1. `Vercel-CDN-Cache-Control` (Vercel edge only, stripped before reaching client)
2. `CDN-Cache-Control` (any CDN, stripped before reaching client)
3. `Cache-Control` (both CDN and browser)

### vercel.json with cache headers

```json
{
  "headers": [
    {
      "source": "/assets/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    },
    {
      "source": "/api/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, s-maxage=60, stale-while-revalidate=300"
        }
      ]
    },
    {
      "source": "/(.*).html",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=0, must-revalidate"
        }
      ]
    }
  ]
}
```

---

## Vercel-Specific Features

### Middleware for dynamic headers and redirects

Middleware runs at the edge before a request is completed. Use it for
conditional redirects, A/B testing, geolocation-based routing, or dynamic
header injection.

```ts
// middleware.ts (at project root, alongside app/ or pages/)
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const response = NextResponse.next();

  // Add dynamic headers
  response.headers.set('X-Robots-Tag', 'noindex');

  // Geo-based redirect
  const country = request.geo?.country || 'US';
  if (country === 'AU' && !request.nextUrl.pathname.startsWith('/au')) {
    return NextResponse.redirect(new URL('/au' + request.nextUrl.pathname, request.url));
  }

  // Bot detection header
  const ua = request.headers.get('user-agent') || '';
  if (/bot|crawl|spider/i.test(ua)) {
    response.headers.set('X-Is-Bot', 'true');
  }

  return response;
}

// Only run on specific paths (recommended for performance)
export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
```

### Edge Config

Edge Config provides ultra-low-latency reads for configuration data like
feature flags or redirects at the edge.

```ts
import { get } from '@vercel/edge-config';

export async function middleware(request: NextRequest) {
  const maintenance = await get('maintenance');
  if (maintenance) {
    return NextResponse.redirect(new URL('/maintenance', request.url));
  }

  const redirects = await get<Record<string, string>>('redirects');
  const target = redirects?.[request.nextUrl.pathname];
  if (target) {
    return NextResponse.redirect(new URL(target, request.url));
  }

  return NextResponse.next();
}
```

### Environment variables

```bash
# Set via CLI
vercel env add NEXT_PUBLIC_API_URL production
vercel env add DATABASE_URL production preview

# Pull to local .env file
vercel env pull .env.local
```

In `vercel.json` (for non-sensitive, non-secret values):

```json
{
  "env": {
    "NEXT_PUBLIC_SITE_URL": "https://example.com"
  }
}
```

**Rules:**
- `NEXT_PUBLIC_` prefix exposes the variable to the browser (Next.js only).
- Secrets should be set via the dashboard or CLI, never in `vercel.json`.
- Environment variables can be scoped to `production`, `preview`, or
  `development`.

### Analytics and Speed Insights

```bash
# Install the packages
npm install @vercel/analytics @vercel/speed-insights
```

```tsx
// app/layout.tsx
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/next';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
```

For non-Next.js projects:

```ts
// main.ts or index.ts
import { inject } from '@vercel/analytics';
import { injectSpeedInsights } from '@vercel/speed-insights';

inject();
injectSpeedInsights();
```

### Cron jobs

Define scheduled serverless functions in `vercel.json`:

```json
{
  "crons": [
    {
      "path": "/api/cron/daily-cleanup",
      "schedule": "0 0 * * *"
    },
    {
      "path": "/api/cron/hourly-sync",
      "schedule": "0 * * * *"
    }
  ]
}
```

The endpoint must return a 200 status to indicate success:

```ts
// app/api/cron/daily-cleanup/route.ts
import { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  // Verify the request is from Vercel Cron
  const authHeader = request.headers.get('authorization');
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Do the work
  await performCleanup();

  return Response.json({ success: true });
}
```

**Note:** Cron jobs are only available on Pro and Enterprise plans.

### Serverless function configuration

```json
// vercel.json
{
  "functions": {
    "app/api/heavy-task/route.ts": {
      "maxDuration": 60,
      "memory": 1024
    },
    "app/api/**/*.ts": {
      "maxDuration": 30
    }
  }
}
```

```ts
// Or per-route in Next.js App Router:
// app/api/heavy-task/route.ts
export const maxDuration = 60; // seconds
export const dynamic = 'force-dynamic';
```

Default limits by plan:

| Plan | Max Duration | Memory |
|------|-------------|--------|
| Hobby | 10s | 1024 MB |
| Pro | 60s (300s with streaming) | 1024 MB (3008 MB max) |
| Enterprise | 900s | 3008 MB |

---

## Common Gotchas

### vercel.json headers do not override framework headers

If your framework (e.g. Next.js) sets a header in `next.config.js` or in an API
route, and you also set the same header in `vercel.json`, the **framework header
takes precedence**. The `vercel.json` header is only applied if the framework
does not set that header.

**Fix:** Pick one source of truth. For Next.js projects, prefer
`next.config.js` headers or middleware. Use `vercel.json` for non-framework
routes (static files, etc.).

### Middleware vs vercel.json precedence

The execution order on Vercel is:

1. `vercel.json` redirects
2. Filesystem (public files, static assets)
3. `vercel.json` rewrites (beforeFiles equivalent)
4. Middleware
5. `next.config.js` redirects / rewrites
6. Filesystem (pages, app routes)
7. `vercel.json` rewrites (afterFiles / fallback equivalent)

Headers set in middleware can override headers set in `vercel.json` or
`next.config.js`.

### Cold starts on serverless functions

Serverless functions that have not been invoked recently experience a cold
start. This adds latency (typically 250ms-2s depending on bundle size).

**Mitigations:**
- Keep function bundles small. Use `@vercel/nft` (automatic) but avoid
  importing heavy libraries.
- Use edge functions (`export const runtime = 'edge'`) for latency-sensitive
  routes. Edge functions have near-zero cold starts but limited Node.js API
  access.
- On Pro/Enterprise, use `crons` to periodically invoke critical functions.
- Split large API routes into smaller functions.

```ts
// Convert a serverless function to edge for faster cold starts
// app/api/fast-endpoint/route.ts
export const runtime = 'edge';

export async function GET() {
  return Response.json({ fast: true });
}
```

### Redirect limit in vercel.json

`vercel.json` supports up to 1,024 redirects. For larger redirect maps (e.g.
migrating a legacy site with thousands of URLs), use Next.js middleware with a
JSON or database lookup:

```ts
// middleware.ts
import redirects from './redirects.json'; // { "/old": "/new", ... }

export function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;
  const target = (redirects as Record<string, string>)[path];

  if (target) {
    return NextResponse.redirect(new URL(target, request.url), 308);
  }

  return NextResponse.next();
}
```

For very large redirect sets (10,000+), use Edge Config for faster lookups:

```ts
import { get } from '@vercel/edge-config';

export async function middleware(request: NextRequest) {
  const target = await get<string>(request.nextUrl.pathname);
  if (target) {
    return NextResponse.redirect(new URL(target, request.url), 308);
  }
  return NextResponse.next();
}
```

### Edge middleware vs Node.js middleware

Next.js middleware on Vercel always runs at the edge. This means:

- **No Node.js APIs:** `fs`, `child_process`, `net`, etc. are not available.
- **No native modules:** Libraries that use compiled binaries will not work.
- **Limited `crypto`:** Only Web Crypto API is available (no `node:crypto`).
- **Size limit:** Middleware bundle must be under 1 MB (edge) / 250 MB (serverless).
- **Execution limit:** 30s on Hobby, 30s on Pro (edge functions).

If you need full Node.js access, use API routes with `runtime: 'nodejs'`
(the default) instead of middleware.

### Build output file size limits

- Individual serverless functions: 250 MB (compressed).
- Edge functions: 1 MB (after compression).
- Total deployment size: 100 GB.

If your function exceeds the limit, check for accidentally bundled
`node_modules`, large data files, or unused dependencies.

### Preview deployments inherit production headers

Headers configured in `vercel.json` apply to all deployments including preview
URLs. If you have HSTS enabled, preview deployments will also enforce HTTPS.
This is usually fine, but be aware when sharing preview links.

---

## Complete Config Example

A production-ready `vercel.json` covering security headers, caching, redirects,
and function configuration:

```json
{
  "framework": null,
  "trailingSlash": false,

  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Strict-Transport-Security",
          "value": "max-age=31536000; includeSubDomains; preload"
        },
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "Referrer-Policy",
          "value": "strict-origin-when-cross-origin"
        },
        {
          "key": "Permissions-Policy",
          "value": "camera=(), microphone=(), geolocation=()"
        },
        {
          "key": "X-DNS-Prefetch-Control",
          "value": "on"
        }
      ]
    },
    {
      "source": "/assets/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    },
    {
      "source": "/fonts/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        },
        {
          "key": "Access-Control-Allow-Origin",
          "value": "*"
        }
      ]
    },
    {
      "source": "/api/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, s-maxage=0, must-revalidate"
        }
      ]
    }
  ],

  "redirects": [
    {
      "source": "/:path(.*)",
      "has": [{ "type": "host", "value": "www.example.com" }],
      "destination": "https://example.com/:path",
      "permanent": true
    },
    {
      "source": "/old-blog/:slug",
      "destination": "/blog/:slug",
      "permanent": true
    },
    {
      "source": "/feed",
      "destination": "/rss.xml",
      "permanent": true
    }
  ],

  "rewrites": [
    {
      "source": "/sitemap.xml",
      "destination": "/api/sitemap"
    }
  ],

  "functions": {
    "api/heavy-task.ts": {
      "maxDuration": 60,
      "memory": 1024
    }
  },

  "crons": [
    {
      "path": "/api/cron/daily-cleanup",
      "schedule": "0 0 * * *"
    }
  ]
}
```

### Equivalent Next.js next.config.js

For Next.js projects, this is the recommended approach (replace or complement
the `vercel.json` config above):

```js
// next.config.js
const securityHeaders = [
  { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains; preload' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  { key: 'X-DNS-Prefetch-Control', value: 'on' },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  trailingSlash: false,
  poweredByHeader: false, // removes X-Powered-By: Next.js

  async headers() {
    return [
      {
        source: '/(.*)',
        headers: securityHeaders,
      },
      {
        source: '/assets/:path*',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=31536000, immutable' },
        ],
      },
      {
        source: '/fonts/:path*',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=31536000, immutable' },
          { key: 'Access-Control-Allow-Origin', value: '*' },
        ],
      },
    ];
  },

  async redirects() {
    return [
      {
        source: '/old-blog/:slug',
        destination: '/blog/:slug',
        permanent: true,
      },
      {
        source: '/feed',
        destination: '/rss.xml',
        permanent: true,
      },
    ];
  },

  async rewrites() {
    return [
      {
        source: '/sitemap.xml',
        destination: '/api/sitemap',
      },
    ];
  },
};

module.exports = nextConfig;
```

---

## Quick Lookup Table

| Issue Flagged by FAT Agent | Fix Location | Section |
|---------------------------|-------------|---------|
| Missing HSTS | `vercel.json` headers or `next.config.js` | Security Headers |
| Missing X-Content-Type-Options | `vercel.json` headers or `next.config.js` | Security Headers |
| Missing X-Frame-Options | `vercel.json` headers or `next.config.js` | Security Headers |
| Missing Referrer-Policy | `vercel.json` headers or `next.config.js` | Security Headers |
| Missing Permissions-Policy | `vercel.json` headers or `next.config.js` | Security Headers |
| Missing Content-Security-Policy | `next.config.js` or middleware | Security Headers |
| No HTTPS redirect | Automatic on Vercel | SSL/HTTPS |
| Broken redirects / 404s | `vercel.json` redirects or `next.config.js` | Redirects & Rewrites |
| Trailing slash inconsistency | `vercel.json` or `next.config.js` trailingSlash | Redirects & Rewrites |
| No custom 404 page | `pages/404.js` or `app/not-found.tsx` | Redirects & Rewrites |
| No cache headers on static assets | `vercel.json` headers or `next.config.js` | Caching Headers |
| Slow API responses | Add `s-maxage` / `stale-while-revalidate` | Caching Headers |
| Slow cold starts | Use edge runtime or reduce bundle size | Common Gotchas |
