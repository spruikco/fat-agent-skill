# Remix / React Router v7 -- Framework Fix Reference

Patterns for fixing common audit issues in Remix (v2) and React Router v7
projects. React Router v7 is the successor to Remix -- the APIs are nearly
identical but import paths differ. Examples show both where they diverge.

---

## SEO Meta Tags

Remix uses the `meta` export on route modules. Each route returns an array of
meta descriptor objects.

### Basic meta export

```tsx
// app/routes/about.tsx  (Remix v2)
import type { MetaFunction } from "@remix-run/node";

export const meta: MetaFunction = () => {
  return [
    { title: "About Us -- Acme Co" },
    { name: "description", content: "Learn about Acme Co's mission and team." },
    { property: "og:title", content: "About Us -- Acme Co" },
    { property: "og:description", content: "Learn about Acme Co's mission and team." },
    { property: "og:type", content: "website" },
    { property: "og:image", content: "https://acme.co/og-about.png" },
    { property: "og:url", content: "https://acme.co/about" },
    { name: "twitter:card", content: "summary_large_image" },
  ];
};
```

```tsx
// app/routes/about.tsx  (React Router v7)
import type { MetaFunction } from "react-router";

export const meta: MetaFunction = () => {
  return [
    { title: "About Us -- Acme Co" },
    { name: "description", content: "Learn about Acme Co's mission and team." },
    { property: "og:title", content: "About Us -- Acme Co" },
    { property: "og:description", content: "Learn about Acme Co's mission and team." },
  ];
};
```

### Dynamic meta from loader data

```tsx
import type { MetaFunction, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";

export async function loader({ params }: LoaderFunctionArgs) {
  const product = await getProduct(params.slug);
  if (!product) throw new Response("Not Found", { status: 404 });
  return json({ product });
}

export const meta: MetaFunction<typeof loader> = ({ data }) => {
  if (!data) return [{ title: "Product Not Found" }];
  return [
    { title: `${data.product.name} -- Acme Co` },
    { name: "description", content: data.product.summary },
    { property: "og:title", content: data.product.name },
    { property: "og:image", content: data.product.image },
  ];
};
```

### Route-level meta merging

By default, child route meta **replaces** parent meta entirely -- it does not
merge. If you want to inherit parent meta, you must do it explicitly.

```tsx
// app/routes/products.$slug.tsx
export const meta: MetaFunction<typeof loader> = ({ data, matches }) => {
  // Get parent (root) meta
  const parentMeta = matches.flatMap((match) => match.meta ?? []);

  // Filter out tags we want to override
  const filtered = parentMeta.filter(
    (m) =>
      !("title" in m) &&
      !("name" in m && m.name === "description") &&
      !("property" in m && m.property?.startsWith("og:"))
  );

  return [
    ...filtered,
    { title: `${data?.product.name} -- Acme Co` },
    { name: "description", content: data?.product.summary ?? "" },
    { property: "og:title", content: data?.product.name ?? "" },
  ];
};
```

**Tip:** Create a `mergeMeta` helper to reduce boilerplate:

```tsx
// app/utils/merge-meta.ts
import type { MetaDescriptor, MetaMatch } from "@remix-run/react";

type MetaKey = string;

function getMetaKey(descriptor: MetaDescriptor): MetaKey | null {
  if ("title" in descriptor) return "title";
  if ("name" in descriptor) return `name:${descriptor.name}`;
  if ("property" in descriptor) return `property:${descriptor.property}`;
  if ("httpEquiv" in descriptor) return `httpEquiv:${descriptor.httpEquiv}`;
  return null;
}

export function mergeMeta(
  parentMatches: MetaMatch[],
  childMeta: MetaDescriptor[]
): MetaDescriptor[] {
  const childKeys = new Set(
    childMeta.map(getMetaKey).filter(Boolean)
  );

  const inherited = parentMatches
    .flatMap((m) => m.meta ?? [])
    .filter((m) => {
      const key = getMetaKey(m);
      return key && !childKeys.has(key);
    });

  return [...inherited, ...childMeta];
}
```

---

## Canonical, Alternate, and Hreflang Links

Use the `links` export to add `<link>` elements to the document head.

```tsx
// app/routes/about.tsx
import type { LinksFunction } from "@remix-run/node";

export const links: LinksFunction = () => {
  return [
    { rel: "canonical", href: "https://acme.co/about" },
    { rel: "alternate", hrefLang: "en", href: "https://acme.co/about" },
    { rel: "alternate", hrefLang: "es", href: "https://acme.co/es/about" },
    { rel: "alternate", hrefLang: "x-default", href: "https://acme.co/about" },
  ];
};
```

### Dynamic canonical from loader

```tsx
import type { LinksFunction } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";

// Links cannot access loader data directly, so use useMatches or
// set canonical in <head> via meta for dynamic values:
export const meta: MetaFunction<typeof loader> = ({ data }) => {
  return [
    { tagName: "link", rel: "canonical", href: `https://acme.co/products/${data?.product.slug}` },
  ];
};
```

**Note:** In Remix v2.10+, you can return `{ tagName: "link", ... }` from
`meta` to emit `<link>` elements, which is useful when the URL depends on
loader data.

---

## Structured Data (JSON-LD)

Inject JSON-LD in the root layout or per-route using a `<script>` tag. Remix
does not have a dedicated API for this, so use a component.

### Global structured data in root

```tsx
// app/root.tsx
import { json, type LoaderFunctionArgs } from "@remix-run/node";

export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  return json({
    siteUrl: url.origin,
    siteName: "Acme Co",
  });
}

export default function App() {
  const { siteUrl, siteName } = useLoaderData<typeof loader>();

  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: siteName,
    url: siteUrl,
    logo: `${siteUrl}/logo.png`,
  };

  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema) }}
        />
      </head>
      <body>
        <Outlet />
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}
```

### Per-route structured data

```tsx
// app/routes/products.$slug.tsx
export default function ProductPage() {
  const { product } = useLoaderData<typeof loader>();

  const productSchema = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.summary,
    image: product.image,
    offers: {
      "@type": "Offer",
      price: product.price,
      priceCurrency: "GBP",
      availability: "https://schema.org/InStock",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(productSchema) }}
      />
      <main>
        <h1>{product.name}</h1>
        {/* ... */}
      </main>
    </>
  );
}
```

---

## Error Boundaries

Remix uses React error boundaries per-route. Export an `ErrorBoundary` component
to handle errors gracefully and return proper HTTP status codes.

### Catch-all 404 handling

```tsx
// app/root.tsx
import { isRouteErrorResponse, useRouteError } from "@remix-run/react";

export function ErrorBoundary() {
  const error = useRouteError();

  if (isRouteErrorResponse(error)) {
    return (
      <html lang="en">
        <head>
          <meta charSet="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>{error.status === 404 ? "Page Not Found" : "Error"}</title>
          <Meta />
          <Links />
        </head>
        <body>
          <main>
            <h1>{error.status}</h1>
            <p>{error.status === 404
              ? "The page you requested could not be found."
              : error.statusText}
            </p>
          </main>
          <Scripts />
        </body>
      </html>
    );
  }

  // Unexpected errors (500)
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Server Error</title>
        <Meta />
        <Links />
      </head>
      <body>
        <main>
          <h1>500 -- Server Error</h1>
          <p>Something went wrong. Please try again later.</p>
        </main>
        <Scripts />
      </body>
    </html>
  );
}
```

### Route-level error boundary

```tsx
// app/routes/products.$slug.tsx
export function ErrorBoundary() {
  const error = useRouteError();

  if (isRouteErrorResponse(error) && error.status === 404) {
    return (
      <div className="error-container">
        <h1>Product Not Found</h1>
        <p>We could not find the product you were looking for.</p>
        <a href="/products">Browse all products</a>
      </div>
    );
  }

  return (
    <div className="error-container">
      <h1>Something went wrong</h1>
      <p>We encountered an unexpected error loading this product.</p>
    </div>
  );
}
```

**Important:** Throw `Response` objects with correct status codes in loaders so
the error boundary receives a proper `RouteErrorResponse`:

```tsx
export async function loader({ params }: LoaderFunctionArgs) {
  const product = await getProduct(params.slug);
  if (!product) {
    throw new Response("Not Found", { status: 404 });
  }
  return json({ product });
}
```

---

## Security Headers

Use the `headers` export on route modules. The most common pattern is setting
them in the root route or an entry module.

### Route-level headers export

```tsx
// app/routes/about.tsx
import type { HeadersFunction } from "@remix-run/node";

export const headers: HeadersFunction = () => ({
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
  "Content-Security-Policy":
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com",
  "X-Frame-Options": "DENY",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
});
```

### Root-level headers (apply to all routes)

The `headers` export only applies to the route that defines it. To apply
headers globally, set them in `entry.server.tsx`:

```tsx
// app/entry.server.tsx
import { PassThrough } from "node:stream";
import { createReadableStreamFromReadable } from "@remix-run/node";
import { renderToPipeableStream } from "react-dom/server";
import { RemixServer } from "@remix-run/react";
import type { EntryContext } from "@remix-run/node";

const SECURITY_HEADERS = {
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

export default function handleRequest(
  request: Request,
  responseStatusCode: number,
  responseHeaders: Headers,
  remixContext: EntryContext
) {
  // Apply security headers to every response
  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    responseHeaders.set(key, value);
  }

  return new Promise((resolve, reject) => {
    const { pipe, abort } = renderToPipeableStream(
      <RemixServer context={remixContext} url={request.url} />,
      {
        onShellReady() {
          const body = new PassThrough();
          const stream = createReadableStreamFromReadable(body);

          resolve(
            new Response(stream, {
              headers: responseHeaders,
              status: responseStatusCode,
            })
          );
          pipe(body);
        },
        onShellError(error) {
          reject(error);
        },
        onError(error) {
          responseStatusCode = 500;
          console.error(error);
        },
      }
    );

    setTimeout(abort, 10_000);
  });
}
```

**Note:** If you deploy behind a reverse proxy (Nginx, Caddy), prefer setting
security headers there instead -- it is simpler, covers static assets, and
avoids the `entry.server.tsx` boilerplate.

---

## Streaming SSR and Core Web Vitals

Remix supports streaming SSR via `renderToPipeableStream`. This improves
Time to First Byte (TTFB) and First Contentful Paint (FCP) by flushing the
shell immediately while data loads.

### Using `defer` for streaming (Remix v2)

```tsx
// app/routes/dashboard.tsx
import { defer, type LoaderFunctionArgs } from "@remix-run/node";
import { Await, useLoaderData } from "@remix-run/react";
import { Suspense } from "react";

export async function loader({ request }: LoaderFunctionArgs) {
  // Critical data -- awaited, blocks the shell
  const user = await getUser(request);

  // Non-critical data -- passed as a promise, streamed later
  const recommendations = getRecommendations(user.id);
  const notifications = getNotifications(user.id);

  return defer({
    user,
    recommendations,
    notifications,
  });
}

export default function Dashboard() {
  const { user, recommendations, notifications } = useLoaderData<typeof loader>();

  return (
    <main>
      <h1>Welcome, {user.name}</h1>

      {/* Streams in when ready */}
      <Suspense fallback={<p>Loading recommendations...</p>}>
        <Await resolve={recommendations}>
          {(items) => (
            <ul>
              {items.map((item) => (
                <li key={item.id}>{item.title}</li>
              ))}
            </ul>
          )}
        </Await>
      </Suspense>

      <Suspense fallback={<p>Loading notifications...</p>}>
        <Await resolve={notifications}>
          {(notes) => <NotificationList items={notes} />}
        </Await>
      </Suspense>
    </main>
  );
}
```

### React Router v7 equivalent (no `defer` needed)

React Router v7 loaders can return bare promises -- no `defer` wrapper:

```tsx
// app/routes/dashboard.tsx  (React Router v7)
export async function loader({ request }: LoaderFunctionArgs) {
  const user = await getUser(request);
  return {
    user,
    recommendations: getRecommendations(user.id), // promise
    notifications: getNotifications(user.id),      // promise
  };
}
```

### CWV considerations

- **Await critical data** for the initial shell to avoid layout shift (CLS).
  Only defer truly non-critical, below-the-fold content.
- **Set explicit dimensions** on images and containers inside `<Suspense>`
  fallbacks to prevent layout shift when streamed content replaces them.
- **Avoid long chains** of deferred data -- the browser connection stays open
  until all promises resolve. Set a timeout in `entry.server.tsx` (see above).
- **Preload critical assets** via the `links` export to improve LCP:

```tsx
export const links: LinksFunction = () => [
  { rel: "preload", href: "/fonts/inter.woff2", as: "font", type: "font/woff2", crossOrigin: "anonymous" },
  { rel: "preload", href: "/hero.webp", as: "image" },
];
```

---

## Cache Headers for Static Routes

For routes that rarely change, set cache headers to improve repeat-visit
performance:

```tsx
export const headers: HeadersFunction = () => ({
  "Cache-Control": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800",
});
```

For fully static pages served behind a CDN:

```tsx
export const headers: HeadersFunction = () => ({
  "Cache-Control": "public, max-age=86400, s-maxage=604800",
  "CDN-Cache-Control": "public, max-age=604800",
});
```

---

## Quick Checklist

| Issue | Fix |
|---|---|
| Missing `<title>` | Add `{ title: "..." }` to `meta` export |
| Missing meta description | Add `{ name: "description", content: "..." }` to `meta` |
| No Open Graph tags | Add `property: "og:*"` entries to `meta` |
| No canonical URL | Add `{ rel: "canonical", href: "..." }` to `links` or `meta` |
| No hreflang | Add `{ rel: "alternate", hrefLang: "...", href: "..." }` to `links` |
| No structured data | Add `<script type="application/ld+json">` in component JSX |
| Generic 404 page | Export `ErrorBoundary`, throw `new Response("", { status: 404 })` in loader |
| No 500 handling | Export `ErrorBoundary` in root, handle non-response errors |
| Missing security headers | Set in `entry.server.tsx` or reverse proxy |
| Slow TTFB | Use `defer` / promise returns for non-critical data |
| Layout shift from streaming | Set explicit dimensions on Suspense fallbacks |
| No cache headers | Add `headers` export with appropriate `Cache-Control` |
