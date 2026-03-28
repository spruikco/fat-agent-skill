# Next.js — Framework Fix Reference

Patterns for fixing common audit issues in Next.js projects. Covers both the
**App Router** (Next.js 13+, `app/` directory) and the **Pages Router**
(`pages/` directory). Code examples use TypeScript for App Router and JavaScript
for Pages Router unless noted otherwise.

---

## SEO Meta Tags

### App Router (Metadata API)

Next.js 13+ provides a built-in Metadata API. No `<head>` manipulation needed.

**Static metadata export**

```tsx
// app/about/page.tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About Us — Acme Co",
  description: "Learn about Acme Co's mission, team, and values.",
};

export default function AboutPage() {
  return <main><h1>About Us</h1></main>;
}
```

**Title template (set once in root layout)**

```tsx
// app/layout.tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: {
    default: "Acme Co",          // fallback when a page doesn't set title
    template: "%s — Acme Co",    // child pages inject into %s
  },
  description: "Widgets and gadgets for the modern era.",
  metadataBase: new URL("https://acme.co"),
  openGraph: {
    siteName: "Acme Co",
    locale: "en_US",
    type: "website",
  },
};
```

Then a child page only needs:

```tsx
// app/pricing/page.tsx
export const metadata: Metadata = {
  title: "Pricing",  // renders as "Pricing — Acme Co"
};
```

**Dynamic metadata (data-dependent pages)**

```tsx
// app/blog/[slug]/page.tsx
import type { Metadata } from "next";
import { getPost } from "@/lib/posts";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPost(slug);

  return {
    title: post.title,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      description: post.excerpt,
      type: "article",
      publishedTime: post.date,
      images: [{ url: post.coverImage, width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.excerpt,
      images: [post.coverImage],
    },
  };
}

export default async function BlogPost({ params }: Props) {
  const { slug } = await params;
  const post = await getPost(slug);
  return <article><h1>{post.title}</h1></article>;
}
```

### Pages Router

**next/head for per-page meta**

```jsx
// pages/about.js
import Head from "next/head";

export default function About() {
  return (
    <>
      <Head>
        <title>About Us — Acme Co</title>
        <meta name="description" content="Learn about Acme Co." />
        <meta property="og:title" content="About Us — Acme Co" />
        <meta property="og:description" content="Learn about Acme Co." />
        <meta property="og:image" content="https://acme.co/og-about.jpg" />
        <meta name="twitter:card" content="summary_large_image" />
      </Head>
      <main><h1>About Us</h1></main>
    </>
  );
}
```

**_document.js for global head elements**

```jsx
// pages/_document.js
import { Html, Head, Main, NextScript } from "next/document";

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        {/* global — appears on every page */}
        <link rel="icon" href="/favicon.ico" />
        <meta name="theme-color" content="#0a0a0a" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
```

**next-seo package (Pages Router convenience)**

```bash
npm install next-seo
```

```jsx
// pages/_app.js
import { DefaultSeo } from "next-seo";

export default function App({ Component, pageProps }) {
  return (
    <>
      <DefaultSeo
        titleTemplate="%s — Acme Co"
        defaultTitle="Acme Co"
        description="Widgets and gadgets for the modern era."
        openGraph={{
          type: "website",
          siteName: "Acme Co",
          images: [{ url: "https://acme.co/og-default.jpg", width: 1200, height: 630 }],
        }}
        twitter={{ cardType: "summary_large_image" }}
      />
      <Component {...pageProps} />
    </>
  );
}
```

Then override per page:

```jsx
// pages/pricing.js
import { NextSeo } from "next-seo";

export default function Pricing() {
  return (
    <>
      <NextSeo title="Pricing" description="Plans starting at $9/mo." />
      <main><h1>Pricing</h1></main>
    </>
  );
}
```

---

## Structured Data (JSON-LD)

### App Router

Inline a `<script type="application/ld+json">` in the page or layout. Next.js
will hoist it to `<head>` automatically.

```tsx
// app/page.tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Acme Co — Widgets & Gadgets",
  description: "Leading provider of widgets and gadgets since 2005.",
};

export default function HomePage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Acme Co",
    url: "https://acme.co",
    logo: "https://acme.co/logo.png",
    sameAs: [
      "https://twitter.com/acmeco",
      "https://linkedin.com/company/acmeco",
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <main><h1>Welcome to Acme Co</h1></main>
    </>
  );
}
```

**Blog post with Article schema + generateMetadata**

```tsx
// app/blog/[slug]/page.tsx
import type { Metadata } from "next";
import { getPost } from "@/lib/posts";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPost(slug);
  return {
    title: post.title,
    description: post.excerpt,
    openGraph: { type: "article", publishedTime: post.date },
  };
}

export default async function BlogPost({ params }: Props) {
  const { slug } = await params;
  const post = await getPost(slug);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.excerpt,
    datePublished: post.date,
    dateModified: post.updatedAt,
    author: {
      "@type": "Person",
      name: post.author.name,
    },
    image: post.coverImage,
    publisher: {
      "@type": "Organization",
      name: "Acme Co",
      logo: { "@type": "ImageObject", url: "https://acme.co/logo.png" },
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <article>
        <h1>{post.title}</h1>
        <p>{post.body}</p>
      </article>
    </>
  );
}
```

### Pages Router (next-seo)

```jsx
import { ArticleJsonLd } from "next-seo";

export default function BlogPost({ post }) {
  return (
    <>
      <ArticleJsonLd
        type="Article"
        url={`https://acme.co/blog/${post.slug}`}
        title={post.title}
        images={[post.coverImage]}
        datePublished={post.date}
        dateModified={post.updatedAt}
        authorName={post.author.name}
        publisherName="Acme Co"
        publisherLogo="https://acme.co/logo.png"
        description={post.excerpt}
      />
      <article><h1>{post.title}</h1></article>
    </>
  );
}
```

### Common Schema Types

| Schema | When to Use |
|--------|-------------|
| `Organization` | Homepage — company info, logo, social links |
| `WebSite` | Homepage — enables sitelinks search box |
| `Article` / `BlogPosting` | Blog posts, news articles |
| `Product` | E-commerce product pages |
| `FAQPage` | FAQ sections |
| `BreadcrumbList` | Breadcrumb navigation |
| `LocalBusiness` | Physical business location pages |

---

## Image Optimization

### next/image Component

```tsx
import Image from "next/image";

// Static import — width/height inferred automatically
import heroImg from "@/public/hero.jpg";

export default function Hero() {
  return (
    <Image
      src={heroImg}
      alt="Team collaborating around a whiteboard"
      priority                    // preloads — use for LCP image
      placeholder="blur"          // shows blurred preview while loading
      sizes="100vw"
    />
  );
}
```

**Remote images with explicit dimensions**

```tsx
<Image
  src="https://cdn.acme.co/products/widget-pro.jpg"
  alt="Widget Pro — titanium finish"
  width={800}
  height={600}
  sizes="(max-width: 768px) 100vw, 50vw"
/>
```

### Key Props

| Prop | Purpose |
|------|---------|
| `width` + `height` | Prevents CLS — sets the aspect ratio |
| `priority` | Preloads the image. Use on LCP image (usually hero). Only use on above-fold images. |
| `sizes` | Tells the browser which size to fetch. Without it, Next.js sends the full-size image. |
| `placeholder="blur"` | Shows a blurred version while loading. Works automatically with static imports. For remote images, supply `blurDataURL`. |
| `fill` | Makes the image fill its parent container (parent must have `position: relative`). Use instead of `width`/`height` when the aspect ratio is unknown. |
| `loading="lazy"` | Default behaviour. Do not combine with `priority`. |

### Remote Image Configuration

```js
// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.acme.co",
        pathname: "/products/**",
      },
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
    ],
  },
};

module.exports = nextConfig;
```

### Responsive Image Pattern

```tsx
// Full-width hero that scales down on mobile
<Image
  src={heroImg}
  alt="Descriptive alt text for this hero image"
  priority
  sizes="100vw"
  style={{ width: "100%", height: "auto" }}
/>

// Two-column layout image
<Image
  src="/product-shot.jpg"
  alt="Widget Pro product shot"
  width={600}
  height={400}
  sizes="(max-width: 768px) 100vw, 50vw"
/>
```

---

## Accessibility Patterns

### Semantic HTML in Layouts

```tsx
// app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="skip-link">Skip to content</a>
        <header role="banner">
          <nav aria-label="Main navigation">{/* nav links */}</nav>
        </header>
        <main id="main">{children}</main>
        <footer role="contentinfo">{/* footer content */}</footer>
      </body>
    </html>
  );
}
```

### Skip Link CSS

```css
.skip-link {
  position: absolute;
  left: -9999px;
  top: auto;
  width: 1px;
  height: 1px;
  overflow: hidden;
  z-index: 100;
}

.skip-link:focus {
  position: fixed;
  top: 10px;
  left: 10px;
  width: auto;
  height: auto;
  padding: 0.75rem 1.5rem;
  background: #000;
  color: #fff;
  font-size: 1rem;
  text-decoration: none;
  z-index: 9999;
}
```

### next/link with Descriptive Text

```tsx
// Bad — no context for screen readers
<Link href="/pricing">Click here</Link>

// Good — descriptive
<Link href="/pricing">View pricing plans</Link>

// Good — icon link with accessible label
<Link href="/cart" aria-label="Shopping cart (3 items)">
  <ShoppingCartIcon aria-hidden="true" />
</Link>
```

### Focus Management on Route Changes

The App Router does not automatically move focus on navigation. Use a layout
component to manage this:

```tsx
"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

export function FocusManager({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const mainRef = useRef<HTMLElement>(null);
  const isFirstRender = useRef(true);

  useEffect(() => {
    // Don't steal focus on initial page load
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    mainRef.current?.focus({ preventScroll: false });
  }, [pathname]);

  return (
    <main ref={mainRef} id="main" tabIndex={-1} style={{ outline: "none" }}>
      {children}
    </main>
  );
}
```

### aria-live for Dynamic Content

```tsx
"use client";

import { useState } from "react";

export function SearchResults() {
  const [results, setResults] = useState<string[]>([]);

  return (
    <>
      <input
        type="search"
        aria-label="Search products"
        onChange={(e) => {
          // search logic here
        }}
      />
      <div aria-live="polite" aria-atomic="true">
        {results.length} results found
      </div>
      <ul>
        {results.map((r) => <li key={r}>{r}</li>)}
      </ul>
    </>
  );
}
```

### ESLint Integration

Next.js includes `eslint-plugin-jsx-a11y` rules by default when you use
`next lint`. Ensure your `.eslintrc.json` extends the Next.js config:

```json
{
  "extends": ["next/core-web-vitals", "next/typescript"]
}
```

Run the lint check:

```bash
npx next lint
```

---

## Performance Optimization

### Server Components (App Router)

Every component in the `app/` directory is a Server Component by default.
Server Components send zero JavaScript to the browser. Only add `"use client"`
when the component needs browser APIs (state, effects, event handlers).

```tsx
// Server Component (default) — no JS shipped to client
// app/blog/page.tsx
import { getPosts } from "@/lib/posts";

export default async function BlogIndex() {
  const posts = await getPosts();   // runs on the server, not bundled
  return (
    <ul>
      {posts.map((p) => (
        <li key={p.slug}><a href={`/blog/${p.slug}`}>{p.title}</a></li>
      ))}
    </ul>
  );
}
```

```tsx
// Client Component — only use when needed
// components/like-button.tsx
"use client";

import { useState } from "react";

export function LikeButton() {
  const [liked, setLiked] = useState(false);
  return (
    <button onClick={() => setLiked(!liked)}>
      {liked ? "Liked" : "Like"}
    </button>
  );
}
```

**Rule of thumb:** Keep `"use client"` on the smallest possible component.
Import a client component into a server component, not the other way around.

### Dynamic Imports (Code Splitting)

```tsx
import dynamic from "next/dynamic";

// Heavy component loaded only when rendered
const HeavyChart = dynamic(() => import("@/components/heavy-chart"), {
  loading: () => <p>Loading chart...</p>,
  ssr: false,  // skip server rendering if it uses browser-only APIs
});

export default function Dashboard() {
  return (
    <section>
      <h2>Analytics</h2>
      <HeavyChart />
    </section>
  );
}
```

### Third-Party Scripts (next/script)

```tsx
import Script from "next/script";

// In layout.tsx or page.tsx
<Script
  src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"
  strategy="afterInteractive"  // loads after page becomes interactive
/>
```

| Strategy | When to Use |
|----------|-------------|
| `beforeInteractive` | Critical scripts that must load before hydration (rare) |
| `afterInteractive` | Analytics, tag managers — loads after page is interactive (default) |
| `lazyOnload` | Low-priority scripts — chat widgets, social embeds |
| `worker` | Offloads to a web worker via Partytown (experimental) |

### Font Optimization (next/font)

Eliminates layout shift from font loading. Self-hosts fonts to avoid external
network requests.

```tsx
// app/layout.tsx
import { Inter, Playfair_Display } from "next/font/google";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-playfair",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${playfair.variable}`}>
      <body className={inter.className}>{children}</body>
    </html>
  );
}
```

Then reference in CSS:

```css
h1, h2, h3 {
  font-family: var(--font-playfair), serif;
}

body {
  font-family: var(--font-inter), sans-serif;
}
```

### Local Fonts

```tsx
import localFont from "next/font/local";

const brandFont = localFont({
  src: [
    { path: "../public/fonts/Brand-Regular.woff2", weight: "400" },
    { path: "../public/fonts/Brand-Bold.woff2", weight: "700" },
  ],
  display: "swap",
  variable: "--font-brand",
});
```

### Prefetching

- `<Link>` components prefetch linked pages when they enter the viewport
  (production only).
- Set `prefetch={false}` on links to low-priority pages to save bandwidth.

```tsx
import Link from "next/link";

// Prefetched by default
<Link href="/pricing">Pricing</Link>

// Disable prefetch for rarely visited pages
<Link href="/terms" prefetch={false}>Terms of Service</Link>
```

### Bundle Analysis

```bash
npm install @next/bundle-analyzer
```

```js
// next.config.js
const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true",
});

module.exports = withBundleAnalyzer({
  // your existing config
});
```

```bash
ANALYZE=true npm run build
```

This opens an interactive treemap showing exactly what is in your client bundles.

---

## Analytics Integration

### Google Analytics 4 (gtag.js)

```tsx
// app/layout.tsx
import Script from "next/script";

const GA_ID = process.env.NEXT_PUBLIC_GA_ID;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        {GA_ID && (
          <>
            <Script
              src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
              strategy="afterInteractive"
            />
            <Script id="ga-init" strategy="afterInteractive">
              {`
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('config', '${GA_ID}');
              `}
            </Script>
          </>
        )}
      </body>
    </html>
  );
}
```

### Google Tag Manager

```tsx
// app/layout.tsx
import Script from "next/script";

const GTM_ID = process.env.NEXT_PUBLIC_GTM_ID;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {GTM_ID && (
          <>
            <noscript>
              <iframe
                src={`https://www.googletagmanager.com/ns.html?id=${GTM_ID}`}
                height="0"
                width="0"
                style={{ display: "none", visibility: "hidden" }}
              />
            </noscript>
            <Script id="gtm-init" strategy="afterInteractive">
              {`
                (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
                new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
                j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
                'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
                })(window,document,'script','dataLayer','${GTM_ID}');
              `}
            </Script>
          </>
        )}
        {children}
      </body>
    </html>
  );
}
```

### Vercel Analytics

```bash
npm install @vercel/analytics
```

```tsx
// app/layout.tsx
import { Analytics } from "@vercel/analytics/react";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
```

### Custom Event Tracking

```tsx
"use client";

// With gtag
export function trackEvent(action: string, category: string, label: string) {
  if (typeof window !== "undefined" && typeof window.gtag === "function") {
    window.gtag("event", action, {
      event_category: category,
      event_label: label,
    });
  }
}

// Usage
<button onClick={() => trackEvent("click", "CTA", "hero_signup")}>
  Get Started
</button>
```

```tsx
// With Vercel Analytics
import { track } from "@vercel/analytics";

<button onClick={() => track("signup_click", { location: "hero" })}>
  Get Started
</button>
```

---

## Common Pitfalls

### 1. Client Components Bloating the Bundle

**Problem:** Placing `"use client"` at the top of a large component tree pulls
everything underneath into the client bundle.

```tsx
// BAD — entire page becomes a client component
"use client";

import { HeavyDataGrid } from "./data-grid";
import { StaticSidebar } from "./sidebar";
import { Footer } from "./footer";

export default function Dashboard() {
  const [filter, setFilter] = useState("");
  return (
    <>
      <StaticSidebar />
      <HeavyDataGrid filter={filter} />
      <Footer />
    </>
  );
}
```

**Fix:** Extract the interactive part into the smallest possible client
component and keep the rest as Server Components.

```tsx
// app/dashboard/page.tsx  (Server Component)
import { StaticSidebar } from "./sidebar";
import { Footer } from "./footer";
import { FilterableGrid } from "./filterable-grid"; // only this is "use client"

export default function Dashboard() {
  return (
    <>
      <StaticSidebar />
      <FilterableGrid />
      <Footer />
    </>
  );
}
```

```tsx
// app/dashboard/filterable-grid.tsx
"use client";
import { useState } from "react";
import { HeavyDataGrid } from "./data-grid";

export function FilterableGrid() {
  const [filter, setFilter] = useState("");
  return <HeavyDataGrid filter={filter} onFilterChange={setFilter} />;
}
```

### 2. Missing loading.tsx Causing Layout Shift

**Problem:** When navigating to a route that fetches data, the user sees nothing
until the data resolves. Content pops in all at once, causing CLS.

**Fix:** Add `loading.tsx` files to route segments that fetch data.

```tsx
// app/blog/loading.tsx
export default function BlogLoading() {
  return (
    <div role="status" aria-label="Loading blog posts">
      <div className="skeleton" style={{ height: "2rem", width: "60%" }} />
      <div className="skeleton" style={{ height: "1rem", width: "80%", marginTop: "1rem" }} />
      <div className="skeleton" style={{ height: "1rem", width: "70%", marginTop: "0.5rem" }} />
    </div>
  );
}
```

This file is automatically wrapped in a `<Suspense>` boundary by Next.js.

### 3. Images Without Width/Height Causing CLS

**Problem:** Using a plain `<img>` tag or `next/image` without dimensions.

```tsx
// BAD — causes layout shift
<img src="/hero.jpg" alt="Hero" />

// BAD — next/image with fill but parent has no dimensions
<div>
  <Image src="/hero.jpg" alt="Hero" fill />
</div>
```

**Fix:**

```tsx
// GOOD — explicit dimensions
<Image src="/hero.jpg" alt="Hero" width={1200} height={600} />

// GOOD — fill with sized parent
<div style={{ position: "relative", width: "100%", aspectRatio: "2/1" }}>
  <Image src="/hero.jpg" alt="Hero" fill style={{ objectFit: "cover" }} />
</div>
```

### 4. Forgetting Metadata in Nested Routes

**Problem:** Root layout defines metadata, but nested routes inherit the root
values instead of defining their own. Every page shows the same title and
description.

**Fix:** Export `metadata` or `generateMetadata` in every `page.tsx` that needs
unique meta tags.

```
app/
  layout.tsx        ← title template: "%s — Acme Co"
  page.tsx          ← title: "Home"
  about/
    page.tsx        ← title: "About Us"     (renders "About Us — Acme Co")
  blog/
    page.tsx        ← title: "Blog"
    [slug]/
      page.tsx      ← generateMetadata()    (dynamic per post)
  pricing/
    page.tsx        ← MISSING metadata!     (falls back to "Acme Co")
```

### 5. API Routes Returning HTML Instead of JSON

**Problem:** A route handler accidentally returns a rendered component or plain
string instead of JSON, causing consumers to receive HTML.

```tsx
// BAD — app/api/products/route.ts
export async function GET() {
  const products = await getProducts();
  return new Response(products);  // sends "[object Object]"
}
```

**Fix:**

```tsx
// GOOD — app/api/products/route.ts
import { NextResponse } from "next/server";

export async function GET() {
  const products = await getProducts();
  return NextResponse.json(products);
}
```

For Pages Router:

```js
// GOOD — pages/api/products.js
export default async function handler(req, res) {
  const products = await getProducts();
  res.status(200).json(products);
}
```

### 6. Middleware Running on Static Assets

**Problem:** Middleware runs on every request including images, fonts, and static
files, adding latency and potentially breaking assets.

```tsx
// BAD — middleware.ts (no matcher)
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  // This runs on EVERY request — including _next/static/*, images, etc.
  return NextResponse.next();
}
```

**Fix:** Always add a `matcher` config to exclude static assets.

```tsx
// GOOD — middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  // your middleware logic
  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt
     * - public folder assets
     */
    "/((?!_next/static|_next/image|favicon\\.ico|sitemap\\.xml|robots\\.txt|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
```

### 7. not-found.tsx vs 404.tsx

**App Router** uses `not-found.tsx`:

```tsx
// app/not-found.tsx
import Link from "next/link";

export default function NotFound() {
  return (
    <main>
      <h1>Page Not Found</h1>
      <p>The page you are looking for does not exist.</p>
      <Link href="/">Return to homepage</Link>
    </main>
  );
}
```

Trigger it programmatically with `notFound()`:

```tsx
import { notFound } from "next/navigation";

export default async function BlogPost({ params }: Props) {
  const { slug } = await params;
  const post = await getPost(slug);
  if (!post) notFound();

  return <article><h1>{post.title}</h1></article>;
}
```

**Pages Router** uses `pages/404.js`:

```jsx
// pages/404.js
import Link from "next/link";

export default function Custom404() {
  return (
    <main>
      <h1>404 — Page Not Found</h1>
      <Link href="/">Go back home</Link>
    </main>
  );
}
```

Do not mix these up. Using `pages/404.js` in an App Router project will be
ignored. Using `app/not-found.tsx` in a Pages Router project will not work.

---

### 8. framer-motion LCP Animation Fix

**Problem:** Using `initial={{ opacity: 0 }}` on hero images (or any LCP element)
delays Largest Contentful Paint. The browser renders the element at zero opacity
first, then animates it in, adding hundreds of milliseconds to LCP.

**Fix:** Use `initial={false}` on the first/hero image so framer-motion skips the
entry animation and renders the element in its final state immediately.

```tsx
"use client";

import { motion } from "framer-motion";
import Image from "next/image";

// For a single hero image — skip the initial animation entirely
export function Hero() {
  return (
    <motion.div
      initial={false}       // renders immediately at final state — no LCP delay
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <Image src="/hero.jpg" alt="Hero banner" width={1200} height={600} priority />
    </motion.div>
  );
}

// For carousels — only skip initial animation on the first slide
export function Carousel({ slides }: { slides: { src: string; alt: string }[] }) {
  return (
    <>
      {slides.map((slide, index) => (
        <motion.div
          key={slide.src}
          initial={index === 0 ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
        >
          <Image
            src={slide.src}
            alt={slide.alt}
            width={1200}
            height={600}
            priority={index === 0}
            loading={index === 0 ? "eager" : "lazy"}
          />
        </motion.div>
      ))}
    </>
  );
}
```

---

### 9. GTM / Meta Pixel Deferral Pattern

**Problem:** Google Tag Manager (~263KB) and Meta Pixel (~138KB) loaded
synchronously in `<head>` block rendering and delay First Contentful Paint.
Inline scripts that call `document.createElement` to inject these resources are
just as blocking as external `<script>` tags when placed in `<head>`.

**Fix:** Wrap the loader in `setTimeout` with a 1500-3500ms delay, or use the
Next.js `<Script>` component with `strategy="afterInteractive"`.

```tsx
// app/layout.tsx
import Script from "next/script";

const GTM_ID = process.env.NEXT_PUBLIC_GTM_ID;
const FB_PIXEL_ID = process.env.NEXT_PUBLIC_FB_PIXEL_ID;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}

        {/* GTM — deferred via afterInteractive (loads after hydration) */}
        {GTM_ID && (
          <Script id="gtm-deferred" strategy="afterInteractive">
            {`
              setTimeout(function(){
                (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
                new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
                j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
                'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
                })(window,document,'script','dataLayer','${GTM_ID}');
              }, 2000);
            `}
          </Script>
        )}

        {/* Meta Pixel — deferred with setTimeout */}
        {FB_PIXEL_ID && (
          <Script id="fb-pixel-deferred" strategy="afterInteractive">
            {`
              setTimeout(function(){
                !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){
                n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};
                if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
                n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];
                s.parentNode.insertBefore(t,s)}(window,document,'script',
                'https://connect.facebook.net/en_US/fbevents.js');
                fbq('init','${FB_PIXEL_ID}');fbq('track','PageView');
              }, 3000);
            `}
          </Script>
        )}
      </body>
    </html>
  );
}
```

---

### 10. Image Quality Config in Next.js 14+

**Problem:** The `images.quality` property in `next.config.js` was removed in
Next.js 14. Setting it there has no effect and may produce a build warning.

**Fix:** Set `quality` per-component using the `quality` prop on `next/image`, or
create a reusable wrapper component with a default quality.

```tsx
// components/optimized-image.tsx
import Image, { ImageProps } from "next/image";

const DEFAULT_QUALITY = 80;

export function OptimizedImage({ quality, ...props }: ImageProps) {
  return <Image quality={quality ?? DEFAULT_QUALITY} {...props} />;
}
```

```tsx
// Usage — per-component quality override
import { OptimizedImage } from "@/components/optimized-image";

// Uses default quality (80)
<OptimizedImage src="/product.jpg" alt="Widget Pro" width={600} height={400} />

// Override for hero image — higher quality
<OptimizedImage src="/hero.jpg" alt="Hero banner" width={1200} height={600} quality={90} priority />

// Override for thumbnails — lower quality is fine
<OptimizedImage src="/thumb.jpg" alt="Thumbnail" width={150} height={150} quality={60} />
```

---

### 11. Consistent Hero DOM for CLS Prevention

**Problem:** Conditional rendering of hero content (e.g., based on data loading
state or feature flags) causes Cumulative Layout Shift. When the hero
placeholder is absent from the initial render and then injected, every element
below it shifts down.

**Fix:** Always render the hero container in the DOM with fixed dimensions. Use
CSS `visibility: hidden` or `opacity: 0` instead of conditional JS rendering to
hide content that is not yet ready.

```tsx
// BAD — conditional rendering causes CLS
export function Hero({ loaded, data }: { loaded: boolean; data?: HeroData }) {
  if (!loaded) return null;  // nothing in DOM — elements below shift when this appears
  return (
    <section style={{ height: 600 }}>
      <h1>{data?.title}</h1>
    </section>
  );
}

// GOOD — container is always in the DOM, content becomes visible when ready
export function Hero({ loaded, data }: { loaded: boolean; data?: HeroData }) {
  return (
    <section
      style={{
        height: 600,
        visibility: loaded ? "visible" : "hidden",
      }}
    >
      <h1>{data?.title ?? "\u00A0"}</h1>
    </section>
  );
}
```

For Next.js App Router with Suspense:

```tsx
// app/page.tsx — server component with streaming
import { Suspense } from "react";
import { HeroContent } from "./hero-content";

function HeroSkeleton() {
  return (
    <section style={{ height: 600 }} aria-hidden="true">
      <div className="skeleton" style={{ width: "60%", height: "2rem" }} />
    </section>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<HeroSkeleton />}>
      <HeroContent />
    </Suspense>
  );
}
```

The skeleton has the same dimensions as the real hero, so no layout shift occurs
when the content streams in.
