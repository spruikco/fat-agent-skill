# SvelteKit — Framework Fix Reference

SvelteKit-specific patterns for FAT Agent fix suggestions. When the user's tech
stack is SvelteKit, use these code examples and conventions instead of generic
HTML advice.

SvelteKit uses file-based routing under `src/routes/`, with special files like
`+page.svelte`, `+layout.svelte`, `+page.ts`, and `+page.server.ts` controlling
rendering, data loading, and layout inheritance.

---

## SEO Meta Tags

### Per-Page Meta with `svelte:head`

Every `+page.svelte` can inject elements into `<head>` using the built-in
`svelte:head` component. This is the primary mechanism for per-page SEO.

```svelte
<!-- src/routes/about/+page.svelte -->
<svelte:head>
  <title>About Us | Acme Corp</title>
  <meta name="description" content="Learn about Acme Corp's mission, team, and values." />
  <link rel="canonical" href="https://acme.com/about" />
</svelte:head>

<h1>About Us</h1>
<p>Welcome to Acme Corp...</p>
```

### Shared Head Elements in `+layout.svelte`

For site-wide defaults (favicon, charset, viewport, default OG tags), use the
root layout. Elements in `svelte:head` from pages override or append to those in
layouts.

```svelte
<!-- src/routes/+layout.svelte -->
<script>
  let { children } = $props();
</script>

<svelte:head>
  <meta property="og:site_name" content="Acme Corp" />
  <meta name="twitter:card" content="summary_large_image" />
  <link rel="icon" href="/favicon.svg" />
</svelte:head>

{@render children()}
```

### Dynamic Meta from Load Functions

For pages where SEO data comes from a CMS, database, or API, use `+page.ts` or
`+page.server.ts` to load the data, then bind it in the page component.

```typescript
// src/routes/blog/[slug]/+page.server.ts
import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ params }) => {
  const post = await getPost(params.slug);

  if (!post) {
    error(404, 'Post not found');
  }

  return {
    title: post.title,
    description: post.excerpt,
    ogImage: post.coverImage,
    publishedAt: post.publishedAt,
    content: post.content
  };
};
```

```svelte
<!-- src/routes/blog/[slug]/+page.svelte -->
<script>
  let { data } = $props();
</script>

<svelte:head>
  <title>{data.title} | Acme Blog</title>
  <meta name="description" content={data.description} />
  <meta property="og:title" content={data.title} />
  <meta property="og:description" content={data.description} />
  <meta property="og:image" content={data.ogImage} />
  <meta property="og:type" content="article" />
  <meta property="article:published_time" content={data.publishedAt} />
</svelte:head>

<article>
  <h1>{data.title}</h1>
  {@html data.content}
</article>
```

### Reusable SEO Component

For consistency across many pages, extract a reusable component:

```svelte
<!-- src/lib/components/Seo.svelte -->
<script>
  let {
    title,
    description,
    ogImage = 'https://acme.com/og-default.jpg',
    ogType = 'website',
    canonicalUrl = '',
    noindex = false
  } = $props();

  const siteName = 'Acme Corp';
  const fullTitle = title ? `${title} | ${siteName}` : siteName;
</script>

<svelte:head>
  <title>{fullTitle}</title>
  <meta name="description" content={description} />

  {#if noindex}
    <meta name="robots" content="noindex, nofollow" />
  {/if}

  {#if canonicalUrl}
    <link rel="canonical" href={canonicalUrl} />
  {/if}

  <!-- Open Graph -->
  <meta property="og:title" content={fullTitle} />
  <meta property="og:description" content={description} />
  <meta property="og:image" content={ogImage} />
  <meta property="og:type" content={ogType} />
  <meta property="og:site_name" content={siteName} />
  {#if canonicalUrl}
    <meta property="og:url" content={canonicalUrl} />
  {/if}

  <!-- Twitter -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={fullTitle} />
  <meta name="twitter:description" content={description} />
  <meta name="twitter:image" content={ogImage} />
</svelte:head>
```

Usage in any page:

```svelte
<script>
  import Seo from '$lib/components/Seo.svelte';
  let { data } = $props();
</script>

<Seo
  title={data.title}
  description={data.description}
  canonicalUrl="https://acme.com/about"
/>
```

---

## Structured Data (JSON-LD)

### Static JSON-LD

Use `{@html ...}` inside `svelte:head` to inject a JSON-LD script tag. The
`{@html}` directive is required because Svelte escapes content by default.

```svelte
<svelte:head>
  {@html `<script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Acme Corp",
      "url": "https://acme.com",
      "logo": "https://acme.com/logo.png",
      "sameAs": [
        "https://twitter.com/acme",
        "https://linkedin.com/company/acme"
      ]
    }
  </script>`}
</svelte:head>
```

### Dynamic JSON-LD from Load Data

For pages where schema data comes from a database or CMS:

```svelte
<!-- src/routes/blog/[slug]/+page.svelte -->
<script>
  let { data } = $props();

  const jsonLd = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: data.title,
    description: data.description,
    image: data.ogImage,
    datePublished: data.publishedAt,
    dateModified: data.updatedAt,
    author: {
      '@type': 'Person',
      name: data.author.name
    },
    publisher: {
      '@type': 'Organization',
      name: 'Acme Corp',
      logo: {
        '@type': 'ImageObject',
        url: 'https://acme.com/logo.png'
      }
    }
  });
</script>

<svelte:head>
  {@html `<script type="application/ld+json">${jsonLd}</script>`}
</svelte:head>
```

**Important:** Always use `JSON.stringify()` for dynamic data to prevent XSS
through malicious content containing `</script>`. `JSON.stringify` escapes
special characters safely.

### Reusable JSON-LD Component

```svelte
<!-- src/lib/components/JsonLd.svelte -->
<script>
  let { schema } = $props();
</script>

<svelte:head>
  {@html `<script type="application/ld+json">${JSON.stringify(schema)}</script>`}
</svelte:head>
```

Usage:

```svelte
<JsonLd schema={{
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: data.faqs.map(faq => ({
    '@type': 'Question',
    name: faq.question,
    acceptedAnswer: {
      '@type': 'Answer',
      text: faq.answer
    }
  }))
}} />
```

---

## Image Optimization

### @sveltejs/enhanced-img

The official SvelteKit image optimization package. Processes images at build
time, generates multiple sizes and formats (AVIF, WebP), and outputs responsive
`<img>` tags with correct `width` and `height` to prevent CLS.

Install:

```bash
npm install --save-dev @sveltejs/enhanced-img
```

Configure in `vite.config.ts`:

```typescript
import { sveltekit } from '@sveltejs/kit/vite';
import { enhancedImages } from '@sveltejs/enhanced-img';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [
    enhancedImages(),
    sveltekit()
  ]
});
```

Usage in components (note the `enhanced:img` element):

```svelte
<!-- Static import — processed at build time -->
<enhanced:img
  src="$lib/assets/hero.jpg"
  alt="Acme Corp headquarters at sunset"
  sizes="(min-width: 768px) 50vw, 100vw"
/>

<!-- Lazy loading for below-fold images -->
<enhanced:img
  src="$lib/assets/team-photo.jpg"
  alt="The Acme Corp team"
  loading="lazy"
  sizes="(min-width: 768px) 50vw, 100vw"
/>
```

`enhanced:img` automatically:
- Generates AVIF and WebP variants
- Sets `width` and `height` to prevent layout shift
- Outputs a `<picture>` element with `<source>` elements for each format
- Supports `sizes` for responsive behaviour

**Limitations:** Only works with static imports (paths known at build time).
For dynamic/CMS images, use manual `<img>` tags or `vite-imagetools`.

### vite-imagetools for Build-Time Transforms

For more control over image processing:

```bash
npm install --save-dev vite-imagetools
```

```typescript
// vite.config.ts
import { sveltekit } from '@sveltejs/kit/vite';
import { imagetools } from 'vite-imagetools';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [
    imagetools(),
    sveltekit()
  ]
});
```

```svelte
<script>
  // Query parameters control the transform
  import heroAvif from '$lib/assets/hero.jpg?w=800;1200;1600&format=avif&as=srcset';
  import heroWebp from '$lib/assets/hero.jpg?w=800;1200;1600&format=webp&as=srcset';
  import heroFallback from '$lib/assets/hero.jpg?w=1200';
</script>

<picture>
  <source srcset={heroAvif} type="image/avif" />
  <source srcset={heroWebp} type="image/webp" />
  <img
    src={heroFallback}
    alt="Acme Corp hero image"
    width="1200"
    height="800"
    loading="eager"
  />
</picture>
```

### Responsive Images with Manual srcset

For dynamic images (CMS, user uploads) where build-time processing is not
possible, use standard HTML with a CDN that supports on-the-fly transforms
(Cloudinary, Imgix, Vercel Image Optimization):

```svelte
<script>
  let { image } = $props();

  function getSrcset(url: string, widths: number[]) {
    return widths
      .map(w => `${url}?w=${w}&auto=format ${w}w`)
      .join(', ');
  }
</script>

<img
  src="{image.url}?w=800&auto=format"
  srcset={getSrcset(image.url, [400, 800, 1200, 1600])}
  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 800px"
  alt={image.alt}
  width={image.width}
  height={image.height}
  loading="lazy"
  decoding="async"
/>
```

### Lazy Loading Patterns

```svelte
<!-- Hero image: load eagerly, preload in head -->
<svelte:head>
  <link rel="preload" as="image" href="/images/hero.webp" />
</svelte:head>

<img
  src="/images/hero.webp"
  alt="Hero banner"
  width="1600"
  height="900"
  loading="eager"
  fetchpriority="high"
/>

<!-- Below-fold images: lazy load -->
<img
  src="/images/feature.webp"
  alt="Feature screenshot"
  width="800"
  height="600"
  loading="lazy"
  decoding="async"
/>
```

---

## Accessibility Patterns

### SvelteKit's Built-in A11y Warnings

Svelte is unique among frameworks in providing **compile-time accessibility
warnings**. The compiler checks for common a11y issues and emits warnings during
`npm run dev` and `npm run build`. These are enabled by default.

Checked patterns include:
- `<img>` without `alt` attribute
- `<a>` without content or `aria-label`
- Non-interactive elements with event handlers but no `role`
- Missing `for` attribute on `<label>`
- Positive `tabindex` values (anti-pattern)
- `autofocus` usage
- Missing `<figcaption>` in `<figure>`
- Redundant ARIA roles (e.g., `role="button"` on `<button>`)
- Click handlers on non-interactive elements without a keyboard handler

These warnings appear in the terminal during development. They can be configured
(but should not be disabled) in `svelte.config.js`:

```javascript
// svelte.config.js — only if you need to suppress specific false positives
/** @type {import('@sveltejs/kit').Config} */
const config = {
  onwarn: (warning, handler) => {
    // Only suppress specific known false positives
    if (warning.code === 'a11y_click_events_have_key_events') return;
    handler(warning);
  },
  // ...
};
```

**FAT Agent note:** If the user's site is built with SvelteKit and has a11y
issues, ask whether they are seeing compiler warnings they have been ignoring.
The compiler catches many issues before deployment.

### Focus Management with afterNavigate

SvelteKit uses client-side navigation for internal links. After navigation, the
browser does not perform a full page load, so focus is not automatically reset.
This is a common accessibility gap in SPAs.

SvelteKit handles this automatically since v1.0 by resetting focus to the body
after navigation and announcing the new page to screen readers. However, custom
focus management may be needed for specific UX patterns:

```svelte
<!-- src/routes/+layout.svelte -->
<script>
  import { afterNavigate } from '$app/navigation';

  afterNavigate(() => {
    // Focus the main content heading after navigation.
    // Useful when the default body focus reset is not specific enough.
    const heading = document.querySelector('h1');
    if (heading) {
      heading.setAttribute('tabindex', '-1');
      heading.focus();
    }
  });
</script>
```

### Announcing Page Changes for Screen Readers

SvelteKit automatically creates a live region that announces page titles after
navigation. This is built-in and requires no configuration. However, if page
titles are missing, screen readers will have nothing to announce.

**FAT Agent note:** If the user's SvelteKit site lacks `<title>` tags on some
pages, flag this as both an SEO and accessibility issue. SvelteKit's built-in
route announcer depends on the page title.

For custom announcements beyond page title changes:

```svelte
<!-- src/lib/components/Announcer.svelte -->
<script>
  let message = $state('');

  export function announce(text: string) {
    message = '';
    // Brief delay ensures screen readers detect the change
    setTimeout(() => { message = text; }, 100);
  }
</script>

<div
  aria-live="polite"
  aria-atomic="true"
  class="sr-only"
>
  {message}
</div>

<style>
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
</style>
```

### ARIA Patterns in Svelte Components

Svelte makes dynamic ARIA attributes straightforward with reactive bindings:

```svelte
<!-- Accessible disclosure/accordion -->
<script>
  let isOpen = $state(false);
  const panelId = 'faq-panel-1';
</script>

<button
  aria-expanded={isOpen}
  aria-controls={panelId}
  onclick={() => isOpen = !isOpen}
>
  Frequently Asked Questions
</button>

{#if isOpen}
  <div id={panelId} role="region" aria-label="FAQ answers">
    <slot />
  </div>
{/if}
```

```svelte
<!-- Accessible modal dialog -->
<script>
  let { open = false, title, onclose } = $props();
  let dialogEl;

  $effect(() => {
    if (open && dialogEl) {
      dialogEl.showModal();
    }
  });
</script>

{#if open}
  <dialog
    bind:this={dialogEl}
    aria-labelledby="dialog-title"
    onclose={onclose}
  >
    <h2 id="dialog-title">{title}</h2>
    <slot />
    <button onclick={onclose}>Close</button>
  </dialog>
{/if}
```

```svelte
<!-- Skip link — should be the first focusable element in +layout.svelte -->
<a href="#main-content" class="skip-link">
  Skip to main content
</a>

<nav aria-label="Main navigation">
  <!-- navigation items -->
</nav>

<main id="main-content">
  {@render children()}
</main>

<style>
  .skip-link {
    position: absolute;
    top: -40px;
    left: 0;
    padding: 8px;
    background: #000;
    color: #fff;
    z-index: 100;
  }
  .skip-link:focus {
    top: 0;
  }
</style>
```

---

## Performance Optimization

### SSR + Client Hydration

SvelteKit server-side renders pages by default. The HTML is generated on the
server, sent to the browser, then Svelte "hydrates" the page to make it
interactive. This gives fast initial paint and full SEO crawlability.

No configuration needed — SSR is the default. To verify SSR is working, check
the raw HTML response (view source, not DevTools Elements panel). If the page
content is in the HTML, SSR is working.

### Prerendering Static Pages

For pages that are the same for every user (marketing pages, blog posts, docs),
prerendering generates static HTML at build time. This is faster than SSR
because there is no server-side computation on each request.

```typescript
// src/routes/about/+page.ts
export const prerender = true;
```

To prerender the entire site (for static hosting):

```typescript
// src/routes/+layout.ts
export const prerender = true;
```

For a hybrid approach, set it per-route:

```typescript
// src/routes/blog/[slug]/+page.ts
export const prerender = true;  // Blog posts are static

// src/routes/dashboard/+page.ts
export const prerender = false; // Dashboard needs SSR (user-specific)
```

To generate a list of prerenderable dynamic routes:

```typescript
// src/routes/blog/[slug]/+page.ts
import type { EntryGenerator } from './$types';

export const entries: EntryGenerator = async () => {
  const posts = await getAllPostSlugs();
  return posts.map(slug => ({ slug }));
};

export const prerender = true;
```

### Code Splitting (Automatic Per-Route)

SvelteKit automatically code-splits per route. Each `+page.svelte` and its
dependencies are bundled into a separate chunk. No configuration needed.

To verify code splitting is working, check the build output:

```bash
npm run build
```

The output lists each chunk and its size. If a single chunk is very large, look
for heavy libraries imported at the top level that could be dynamically imported.

### Streaming with +page.server.ts

For pages that need multiple slow data sources, use streaming to send the HTML
shell immediately while data loads:

```typescript
// src/routes/dashboard/+page.server.ts
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
  // Fast data — included in the initial HTML
  const user = await getUser();

  // Slow data — streamed after initial HTML is sent
  const analytics = getAnalytics();       // NOT awaited
  const notifications = getNotifications(); // NOT awaited

  return {
    user,                          // Available immediately
    streamed: {
      analytics,                   // Promise — resolves after initial render
      notifications                // Promise — resolves after initial render
    }
  };
};
```

```svelte
<!-- src/routes/dashboard/+page.svelte -->
<script>
  let { data } = $props();
</script>

<h1>Welcome, {data.user.name}</h1>

{#await data.streamed.analytics}
  <p>Loading analytics...</p>
{:then analytics}
  <AnalyticsWidget {analytics} />
{:catch error}
  <p>Failed to load analytics.</p>
{/await}
```

**Note:** In SvelteKit 2+, top-level promises returned from `load` functions are
automatically streamed without needing a `streamed` wrapper. Simply return an
un-awaited promise directly:

```typescript
// SvelteKit 2+ simplified streaming
export const load: PageServerLoad = async () => {
  return {
    user: await getUser(),       // Awaited — in initial HTML
    analytics: getAnalytics()    // Not awaited — streamed automatically
  };
};
```

### Preloading (data-sveltekit-preload-data)

SvelteKit can preload page data when the user hovers over or focuses a link,
making navigation feel instant.

```svelte
<!-- Preload on hover (default behaviour for internal links) -->
<a href="/about">About</a>

<!-- Preload on hover — explicitly set -->
<a href="/about" data-sveltekit-preload-data="hover">About</a>

<!-- Preload immediately when the link enters the viewport -->
<a href="/pricing" data-sveltekit-preload-data="eager">Pricing</a>

<!-- Preload only the code, not the data (for dynamic pages) -->
<a href="/dashboard" data-sveltekit-preload-code>Dashboard</a>

<!-- Disable preloading for a specific link -->
<a href="/external-heavy-page" data-sveltekit-preload-data="off">Heavy Page</a>
```

Set the default for all links in the root layout's `<body>`:

```html
<!-- src/app.html -->
<body data-sveltekit-preload-data="hover">
  %sveltekit.body%
</body>
```

### Service Workers

SvelteKit has first-class service worker support. Create a
`src/service-worker.ts` file and SvelteKit provides access to the build
manifest:

```typescript
/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

import { build, files, version } from '$service-worker';

const CACHE = `cache-${version}`;
const ASSETS = [...build, ...files];

// Install: cache all built assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS))
  );
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(async (keys) => {
      for (const key of keys) {
        if (key !== CACHE) await caches.delete(key);
      }
    })
  );
});

// Fetch: serve from cache, fall back to network
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request);
    })
  );
});
```

`$service-worker` exports:
- `build` — Array of URLs for JS/CSS chunks generated by Vite
- `files` — Array of URLs for files in `static/`
- `version` — Unique string from the current build (use as cache key)

---

## Analytics Integration

### Script Tag in app.html

For global analytics scripts that need to load on every page (GA4, GTM), add
them directly to `src/app.html`:

```html
<!-- src/app.html -->
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  %sveltekit.head%

  <!-- Google Tag Manager -->
  <script>
    (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
    new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer','GTM-XXXXXXX');
  </script>
</head>
<body data-sveltekit-preload-data="hover">
  %sveltekit.body%
</body>
</html>
```

### SPA Page View Tracking with afterNavigate

Since SvelteKit uses client-side navigation for internal links, analytics tools
that only track full page loads will miss route changes. Use `afterNavigate` in
the root layout to fire page view events on every navigation:

```svelte
<!-- src/routes/+layout.svelte -->
<script>
  import { afterNavigate } from '$app/navigation';
  import { page } from '$app/stores';

  afterNavigate(() => {
    // Google Analytics 4
    if (typeof gtag === 'function') {
      gtag('event', 'page_view', {
        page_title: document.title,
        page_location: $page.url.href,
        page_path: $page.url.pathname
      });
    }
  });

  let { children } = $props();
</script>

{@render children()}
```

For Google Tag Manager (dataLayer push):

```svelte
<script>
  import { afterNavigate } from '$app/navigation';
  import { page } from '$app/stores';

  afterNavigate(() => {
    if (typeof window !== 'undefined' && window.dataLayer) {
      window.dataLayer.push({
        event: 'virtualPageview',
        pagePath: $page.url.pathname,
        pageTitle: document.title
      });
    }
  });
</script>
```

### Client-Only Scripts with onMount

Some scripts (chat widgets, heatmaps, etc.) should only run in the browser, not
during SSR. Use `onMount` to ensure they execute only on the client:

```svelte
<script>
  import { onMount } from 'svelte';

  onMount(() => {
    // This only runs in the browser, not during SSR
    const script = document.createElement('script');
    script.src = 'https://widget.example.com/chat.js';
    script.async = true;
    document.head.appendChild(script);
  });
</script>
```

For scripts that should only load on specific pages, place the `onMount` in that
page's `+page.svelte` rather than the layout.

### Using $app/environment for Conditional Loading

```svelte
<script>
  import { browser } from '$app/environment';

  if (browser) {
    // Safe to access window, document, localStorage, etc.
  }
</script>
```

---

## Common Pitfalls

### Not Returning Data from Load Functions

Load functions **must** return an object. If the function runs but returns
nothing, the page component receives an empty `data` prop and nothing renders.
This is a silent failure — no error, just a blank page.

```typescript
// WRONG — returns nothing
export const load: PageServerLoad = async () => {
  const posts = await getPosts();
  // Missing return!
};

// CORRECT
export const load: PageServerLoad = async () => {
  const posts = await getPosts();
  return { posts };
};
```

**FAT Agent note:** If a SvelteKit site has pages that render with no content
(blank or only the layout shell), ask the user to check their `+page.ts` or
`+page.server.ts` load function for a missing `return`.

### Missing +layout.svelte Inheritance

Layouts in SvelteKit cascade. Every route directory inherits the `+layout.svelte`
from its parent. A common mistake is creating a `+layout.svelte` in a nested
route and forgetting to render children, which causes child pages to disappear.

```svelte
<!-- WRONG — child pages will not render -->
<!-- src/routes/blog/+layout.svelte -->
<h2>Blog</h2>
<!-- Missing {@render children()} -->

<!-- CORRECT -->
<!-- src/routes/blog/+layout.svelte -->
<script>
  let { children } = $props();
</script>

<h2>Blog</h2>
{@render children()}
```

Another common issue: creating a new `+layout.svelte` that unintentionally
replaces the root layout's structure (navigation, footer, etc.). To add a
section-specific layout while keeping the root layout, use layout groups:

```
src/routes/
  +layout.svelte           ← root layout (nav, footer)
  (marketing)/
    +layout.svelte          ← marketing-specific wrapper
    about/+page.svelte
    pricing/+page.svelte
  (app)/
    +layout.svelte          ← app-specific wrapper (sidebar)
    dashboard/+page.svelte
```

### Form Actions vs API Routes Confusion

SvelteKit has two mechanisms for handling form submissions and mutations:

**Form actions** (`+page.server.ts`) — the preferred approach for form handling.
Works without JavaScript, progressively enhanced:

```typescript
// src/routes/contact/+page.server.ts
import type { Actions } from './$types';
import { fail } from '@sveltejs/kit';

export const actions: Actions = {
  default: async ({ request }) => {
    const formData = await request.formData();
    const email = formData.get('email')?.toString();

    if (!email || !email.includes('@')) {
      return fail(400, { email, error: 'Invalid email address' });
    }

    await saveContact(email);
    return { success: true };
  }
};
```

```svelte
<!-- src/routes/contact/+page.svelte -->
<script>
  import { enhance } from '$app/forms';
  let { form } = $props();
</script>

<form method="POST" use:enhance>
  <label>
    Email
    <input name="email" type="email" value={form?.email ?? ''} />
  </label>
  {#if form?.error}
    <p class="error">{form.error}</p>
  {/if}
  {#if form?.success}
    <p class="success">Thanks! We'll be in touch.</p>
  {/if}
  <button type="submit">Submit</button>
</form>
```

**API routes** (`+server.ts`) — for JSON APIs, webhooks, or endpoints consumed
by external services:

```typescript
// src/routes/api/subscribe/+server.ts
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ request }) => {
  const { email } = await request.json();
  await addSubscriber(email);
  return json({ success: true });
};
```

**When to use which:**
- User-facing forms: form actions (works without JS, better UX)
- AJAX/fetch calls from components: API routes
- External webhooks: API routes
- Third-party API proxying: API routes

### Hydration Mismatches

Hydration mismatches happen when the server-rendered HTML differs from what the
client tries to render. Svelte will log a warning in the console. Common causes:

```svelte
<!-- WRONG — different value on server vs client -->
<script>
  // Date differs between server and client render
  const now = new Date().toLocaleTimeString();
</script>
<p>Current time: {now}</p>

<!-- CORRECT — render time-sensitive content only on the client -->
<script>
  import { browser } from '$app/environment';
  import { onMount } from 'svelte';

  let now = $state('');

  onMount(() => {
    now = new Date().toLocaleTimeString();
  });
</script>
<p>Current time: {now || 'Loading...'}</p>
```

```svelte
<!-- WRONG — accessing browser-only APIs during SSR -->
<script>
  const width = window.innerWidth; // Crashes during SSR!
</script>

<!-- CORRECT -->
<script>
  import { browser } from '$app/environment';
  let width = $state(0);

  $effect(() => {
    if (browser) {
      width = window.innerWidth;
    }
  });
</script>
```

Other hydration mismatch causes:
- Browser extensions injecting elements into the DOM
- Using `Math.random()` or `crypto.randomUUID()` for keys
- Conditional rendering based on `typeof window !== 'undefined'` (use
  `$app/environment`'s `browser` instead)

### Environment Variables

SvelteKit has a strict, intentional system for environment variables that
prevents accidentally leaking secrets to the client.

| Module | Accessible Where | Prefix Required | Use Case |
|--------|-----------------|-----------------|----------|
| `$env/static/private` | Server only | None / `PRIVATE_` | API keys, DB creds |
| `$env/static/public` | Server + Client | `PUBLIC_` | Site URL, feature flags |
| `$env/dynamic/private` | Server only | None / `PRIVATE_` | Runtime-resolved secrets |
| `$env/dynamic/public` | Server + Client | `PUBLIC_` | Runtime-resolved config |

```typescript
// Server-only — used in +page.server.ts, +server.ts, hooks.server.ts
import { DATABASE_URL, API_SECRET } from '$env/static/private';

// Available everywhere — requires PUBLIC_ prefix
import { PUBLIC_SITE_URL } from '$env/static/public';
```

```
# .env
DATABASE_URL=postgres://localhost:5432/mydb    # Server only
API_SECRET=sk_live_abc123                       # Server only
PUBLIC_SITE_URL=https://acme.com                # Available on client
PUBLIC_GA_ID=G-XXXXXXXXXX                       # Available on client
```

**Common mistake:** Using `process.env.MY_VAR` — this does not work in
SvelteKit. Always use the `$env` modules.

**FAT Agent note:** If a SvelteKit site is exposing sensitive data in the
client bundle, check for variables that should use `$env/static/private` but are
instead imported from `$env/static/public` or hard-coded in client-side code.

### Adapter Selection

SvelteKit uses adapters to deploy to different platforms. The adapter determines
how the output is built. Using the wrong adapter can cause the site to fail or
miss features.

```bash
# Install the adapter for your platform
npm install --save-dev @sveltejs/adapter-auto     # Auto-detects platform
npm install --save-dev @sveltejs/adapter-node      # Node.js server
npm install --save-dev @sveltejs/adapter-static    # Static site (no SSR)
npm install --save-dev @sveltejs/adapter-vercel    # Vercel
npm install --save-dev @sveltejs/adapter-netlify   # Netlify
npm install --save-dev @sveltejs/adapter-cloudflare # Cloudflare Pages
```

```javascript
// svelte.config.js
import adapter from '@sveltejs/adapter-auto'; // Change for your platform

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter()
  }
};

export default config;
```

| Adapter | Best For | SSR | Prerender | Serverless |
|---------|----------|-----|-----------|------------|
| `adapter-auto` | Auto-detect platform (good default) | Yes | Yes | Depends |
| `adapter-node` | Self-hosted Node servers, Docker | Yes | Yes | No |
| `adapter-static` | GitHub Pages, S3, any static host | No | All pages | No |
| `adapter-vercel` | Vercel deployments | Yes | Yes | Yes |
| `adapter-netlify` | Netlify deployments | Yes | Yes | Yes |
| `adapter-cloudflare` | Cloudflare Pages/Workers | Yes | Yes | Yes |

**Common mistakes:**
- Using `adapter-static` but having routes that need SSR (form actions, dynamic
  server load functions) — the build will fail or those routes will not work
- Using `adapter-auto` in production when the platform is not auto-detectable
  (e.g., Docker, custom servers) — use `adapter-node` explicitly
- Forgetting to set `prerender = true` on all routes when using `adapter-static`

**FAT Agent note:** If a SvelteKit site returns 404 or 500 errors on specific
routes after deployment, check whether the adapter matches the hosting platform
and whether pages requiring SSR are deployed to a static-only host.

---

## Security Headers in SvelteKit

SvelteKit can set security headers via `hooks.server.ts`:

```typescript
// src/hooks.server.ts
import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
  const response = await resolve(event);

  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  response.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  response.headers.set(
    'Strict-Transport-Security',
    'max-age=31536000; includeSubDomains; preload'
  );

  return response;
};
```

This approach works for SSR routes. For prerendered/static pages, headers must
be set at the hosting platform level (Netlify `_headers`, Vercel `vercel.json`,
etc.). See `references/security-headers.md` for platform-specific examples.

---

## Quick Fix Reference Table

Summary table for FAT Agent to reference when generating fix suggestions for
SvelteKit sites.

| Issue Found | Fix Location | Quick Fix |
|-------------|--------------|-----------|
| Missing `<title>` | `+page.svelte` | Add `<svelte:head><title>...</title></svelte:head>` |
| Missing meta description | `+page.svelte` | Add `<meta name="description">` inside `svelte:head` |
| Missing OG tags | `+page.svelte` or `Seo.svelte` component | Add OG meta tags inside `svelte:head` |
| No JSON-LD | `+page.svelte` | Add `{@html}` script in `svelte:head` |
| Images without `alt` | Component file | Add `alt` attribute (compiler warns about this) |
| Images without dimensions | Component file | Add `width`/`height` or use `enhanced:img` |
| No `lang` attribute | `src/app.html` | Set `<html lang="en">` |
| Missing skip link | `+layout.svelte` | Add skip link as first child of body |
| No analytics tracking on SPA navigation | `+layout.svelte` | Add `afterNavigate` page view event |
| Missing security headers | `hooks.server.ts` | Add `handle` hook with headers |
| Client bundle exposing secrets | `+page.server.ts` | Move to `$env/static/private` |
| Blank page (no content) | `+page.server.ts` | Check load function returns data |
| 404 on deployed routes | `svelte.config.js` | Verify adapter matches hosting platform |
| No prerendering on static content | `+page.ts` | Add `export const prerender = true` |
| Hydration mismatch warnings | Component file | Guard browser APIs with `browser` or `onMount` |
