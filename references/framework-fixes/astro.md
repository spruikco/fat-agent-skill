# Astro -- Framework Fix Reference

Astro-specific patterns and fixes for FAT Agent audits. Astro ships zero
JavaScript by default and uses an island architecture, which changes the shape
of most common fixes compared to SPA frameworks.

Applies to: Astro 4.x+ (Content Collections v2, astro:assets, View Transitions).

---

## SEO Meta Tags

Astro layouts own the `<head>`, so all meta tag work happens in `.astro`
components -- usually a shared `BaseHead.astro` or directly in a layout file.

### Receiving props in layouts

Layout components receive page-specific data via `Astro.props`:

```astro
---
// src/layouts/BaseLayout.astro
interface Props {
  title: string;
  description: string;
  image?: string;
  canonicalURL?: string;
}

const {
  title,
  description,
  image = '/og-default.png',
  canonicalURL = new URL(Astro.url.pathname, Astro.site).href,
} = Astro.props;
---
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <meta name="description" content={description} />
    <link rel="canonical" href={canonicalURL} />

    <!-- Open Graph -->
    <meta property="og:type" content="website" />
    <meta property="og:title" content={title} />
    <meta property="og:description" content={description} />
    <meta property="og:image" content={new URL(image, Astro.site)} />
    <meta property="og:url" content={canonicalURL} />

    <!-- Twitter -->
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content={title} />
    <meta name="twitter:description" content={description} />
    <meta name="twitter:image" content={new URL(image, Astro.site)} />

    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="sitemap" href="/sitemap-index.xml" />
    <slot name="head" />
  </head>
  <body>
    <slot />
  </body>
</html>
```

**Why `Astro.site`?** Without it, OG image URLs will be relative paths, which
social platforms cannot resolve. Set `site` in `astro.config.mjs`:

```js
// astro.config.mjs
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://example.com',
});
```

### @astrojs/sitemap integration

```bash
npx astro add sitemap
```

This auto-generates a sitemap at build time. Requires `site` in the config.
To filter pages:

```js
// astro.config.mjs
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://example.com',
  integrations: [
    sitemap({
      filter: (page) => !page.includes('/admin/'),
    }),
  ],
});
```

**Common audit finding:** Sitemap exists at `/sitemap-index.xml` (not
`/sitemap.xml`). Both are valid, but `robots.txt` must reference the correct
path. Add it manually:

```
# public/robots.txt
User-agent: *
Allow: /

Sitemap: https://example.com/sitemap-index.xml
```

### astro-seo package

For teams that prefer a component-based approach over manual meta tags:

```bash
npm install astro-seo
```

```astro
---
// src/layouts/BaseLayout.astro
import { SEO } from 'astro-seo';
---
<html lang="en">
  <head>
    <SEO
      title="Page Title"
      description="Page description."
      openGraph={{
        basic: {
          title: "Page Title",
          type: "website",
          image: "https://example.com/og.png",
        },
      }}
      twitter={{
        creator: "@handle",
      }}
      extend={{
        meta: [
          { name: "twitter:card", content: "summary_large_image" },
        ],
      }}
    />
  </head>
  <body><slot /></body>
</html>
```

### ViewTransitions and meta tags

When using Astro's `<ViewTransitions />`, meta tags update automatically on
client-side navigations. However, third-party scripts that read meta tags on
load (analytics, social embeds) may not re-fire. Handle this with the
`astro:after-swap` event:

```astro
---
import { ViewTransitions } from 'astro:transitions';
---
<head>
  <ViewTransitions />
  <script is:inline>
    document.addEventListener('astro:after-swap', () => {
      // Re-initialise anything that reads meta tags on page load
      // e.g., analytics page view tracking
    });
  </script>
</head>
```

### Complete BaseHead component example

A production-ready head component combining all of the above:

```astro
---
// src/components/BaseHead.astro
interface Props {
  title: string;
  description: string;
  image?: string;
  article?: boolean;
}

import { ViewTransitions } from 'astro:transitions';

const {
  title,
  description,
  image = '/og-default.png',
  article = false,
} = Astro.props;

const canonicalURL = new URL(Astro.url.pathname, Astro.site).href;
const ogImageURL = new URL(image, Astro.site).href;
---

<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="generator" content={Astro.generator} />

<!-- Primary -->
<title>{title}</title>
<meta name="description" content={description} />
<link rel="canonical" href={canonicalURL} />

<!-- Open Graph -->
<meta property="og:type" content={article ? 'article' : 'website'} />
<meta property="og:url" content={canonicalURL} />
<meta property="og:title" content={title} />
<meta property="og:description" content={description} />
<meta property="og:image" content={ogImageURL} />
<meta property="og:site_name" content="Your Site Name" />

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content={title} />
<meta name="twitter:description" content={description} />
<meta name="twitter:image" content={ogImageURL} />

<!-- Favicon -->
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />

<!-- Sitemap -->
<link rel="sitemap" href="/sitemap-index.xml" />

<!-- View Transitions -->
<ViewTransitions />
```

Used in a layout:

```astro
---
// src/layouts/BaseLayout.astro
import BaseHead from '../components/BaseHead.astro';

const { title, description, image } = Astro.props;
---
<html lang="en">
  <head>
    <BaseHead title={title} description={description} image={image} />
  </head>
  <body>
    <slot />
  </body>
</html>
```

---

## Structured Data (JSON-LD)

### Inline script in head

Astro requires `is:inline` on scripts that should not be bundled. JSON-LD must
be rendered as-is (not processed by Astro's script bundler):

```astro
---
// src/layouts/BaseLayout.astro
const schema = {
  '@context': 'https://schema.org',
  '@type': 'WebSite',
  name: 'My Website',
  url: Astro.site,
};
---
<head>
  <script
    type="application/ld+json"
    set:html={JSON.stringify(schema)}
  />
</head>
```

**Why `set:html`?** Without it, Astro will HTML-encode the JSON content,
turning `"` into `&quot;` and breaking the schema. The `set:html` directive
injects raw HTML.

**Note:** When using `set:html`, you do not need `is:inline`. The `set:html`
directive already prevents bundling for `type="application/ld+json"` scripts.

### Dynamic schema generation

Create a utility function for reusable schema generation:

```typescript
// src/utils/schema.ts
export function createArticleSchema(article: {
  title: string;
  description: string;
  publishDate: Date;
  modifiedDate?: Date;
  author: string;
  image: string;
  url: string;
}) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: article.title,
    description: article.description,
    datePublished: article.publishDate.toISOString(),
    dateModified: (article.modifiedDate ?? article.publishDate).toISOString(),
    author: {
      '@type': 'Person',
      name: article.author,
    },
    image: article.image,
    url: article.url,
  };
}

export function createBreadcrumbSchema(
  items: { name: string; url: string }[]
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  };
}

export function createOrganizationSchema(org: {
  name: string;
  url: string;
  logo: string;
  sameAs?: string[];
}) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: org.name,
    url: org.url,
    logo: org.logo,
    sameAs: org.sameAs ?? [],
  };
}
```

### Per-page schema types

Use the schema utilities in individual pages or layouts:

```astro
---
// src/pages/blog/[slug].astro
import BaseLayout from '../../layouts/BaseLayout.astro';
import { createArticleSchema, createBreadcrumbSchema } from '../../utils/schema';
import { getCollection } from 'astro:content';

export async function getStaticPaths() {
  const posts = await getCollection('blog');
  return posts.map((post) => ({
    params: { slug: post.slug },
    props: { post },
  }));
}

const { post } = Astro.props;
const { Content } = await post.render();

const articleSchema = createArticleSchema({
  title: post.data.title,
  description: post.data.description,
  publishDate: post.data.publishDate,
  author: post.data.author,
  image: new URL(post.data.image, Astro.site).href,
  url: new URL(Astro.url.pathname, Astro.site).href,
});

const breadcrumbSchema = createBreadcrumbSchema([
  { name: 'Home', url: new URL('/', Astro.site).href },
  { name: 'Blog', url: new URL('/blog/', Astro.site).href },
  { name: post.data.title, url: new URL(Astro.url.pathname, Astro.site).href },
]);
---
<BaseLayout title={post.data.title} description={post.data.description}>
  <script
    slot="head"
    type="application/ld+json"
    set:html={JSON.stringify(articleSchema)}
  />
  <script
    slot="head"
    type="application/ld+json"
    set:html={JSON.stringify(breadcrumbSchema)}
  />
  <article>
    <h1>{post.data.title}</h1>
    <Content />
  </article>
</BaseLayout>
```

---

## Image Optimization

Astro has built-in image optimization via `astro:assets`. This is the
recommended approach -- no third-party packages required.

### astro:assets Image component

```astro
---
// src/pages/about.astro
import { Image } from 'astro:assets';
import teamPhoto from '../assets/team.jpg';
---

<!-- Local image: width/height inferred automatically -->
<Image src={teamPhoto} alt="Our team gathered around a whiteboard" />

<!-- Override format and quality -->
<Image
  src={teamPhoto}
  alt="Our team gathered around a whiteboard"
  format="webp"
  quality={80}
  widths={[400, 800, 1200]}
  sizes="(max-width: 600px) 400px, (max-width: 1000px) 800px, 1200px"
/>
```

**Audit note:** The `Image` component automatically adds `width` and `height`
attributes, preventing CLS. If an audit finds `<img>` tags without dimensions,
suggest migrating to the `Image` component.

### getImage() for background images

The `Image` component only works in markup. For CSS background images or
other programmatic uses:

```astro
---
import { getImage } from 'astro:assets';
import heroSrc from '../assets/hero.jpg';

const hero = await getImage({
  src: heroSrc,
  format: 'webp',
  width: 1920,
  quality: 80,
});
---

<div
  class="hero"
  style={`background-image: url('${hero.src}');`}
>
  <h1>Welcome</h1>
</div>
```

### Width/height and format props

| Prop | Purpose | Default |
|------|---------|---------|
| `width` | Output width in pixels | Original width |
| `height` | Output height in pixels | Maintains aspect ratio |
| `format` | Output format (`webp`, `avif`, `png`, `jpg`) | Original format |
| `quality` | Compression quality (1-100) | Framework default |
| `widths` | Array of widths for `srcset` generation | None |
| `sizes` | Sizes attribute for responsive images | None |
| `loading` | `"lazy"` or `"eager"` | `"lazy"` |

**Common fix:** If FAT Agent detects images served in legacy formats (JPEG/PNG)
where WebP would save bytes:

```astro
<!-- Before: raw img tag with no optimization -->
<img src="/photos/hero.jpg" alt="Hero image" />

<!-- After: optimized with astro:assets -->
---
import { Image } from 'astro:assets';
import heroImg from '../assets/photos/hero.jpg';
---
<Image src={heroImg} alt="Hero image" format="webp" quality={80} />
```

### Remote images configuration

Astro can optimize remote images, but requires an allow-list in the config:

```js
// astro.config.mjs
export default defineConfig({
  image: {
    domains: ['cdn.example.com', 'images.unsplash.com'],
    // Or allow any remote image (less secure):
    // remotePatterns: [{ protocol: 'https' }],
  },
});
```

Then use with the Image component:

```astro
---
import { Image } from 'astro:assets';
---
<Image
  src="https://cdn.example.com/photo.jpg"
  alt="Remote photo"
  width={800}
  height={600}
  format="webp"
/>
```

**Note:** Remote images require explicit `width` and `height` because Astro
cannot infer dimensions at build time.

### Picture component for art direction

Use `<Picture>` when you need different crops or aspect ratios at different
breakpoints:

```astro
---
import { Picture } from 'astro:assets';
import hero from '../assets/hero.jpg';
---
<Picture
  src={hero}
  formats={['avif', 'webp']}
  alt="Hero banner"
  widths={[400, 800, 1600]}
  sizes="(max-width: 600px) 400px, (max-width: 1200px) 800px, 1600px"
/>
```

This generates a `<picture>` element with `<source>` tags for each format,
with automatic fallback to the original format.

---

## Accessibility Patterns

### Semantic HTML

Astro has no virtual DOM or component abstraction that discourages standard
HTML. Use semantic elements directly:

```astro
---
// src/layouts/BaseLayout.astro
---
<html lang="en">
  <head><slot name="head" /></head>
  <body>
    <a href="#main-content" class="skip-link">Skip to content</a>
    <header>
      <nav aria-label="Primary">
        <slot name="nav" />
      </nav>
    </header>
    <main id="main-content">
      <slot />
    </main>
    <footer>
      <nav aria-label="Footer">
        <slot name="footer-nav" />
      </nav>
    </footer>
  </body>
</html>
```

### Skip links in Layout component

Skip links must be the first focusable element in the body. Style them to be
visually hidden until focused:

```astro
<!-- In layout -->
<a href="#main-content" class="skip-link">Skip to content</a>

<style>
  .skip-link {
    position: absolute;
    top: -100%;
    left: 0;
    padding: 0.5rem 1rem;
    background: #000;
    color: #fff;
    z-index: 9999;
    text-decoration: none;
  }
  .skip-link:focus {
    top: 0;
  }
</style>
```

### ARIA in Astro components

Astro components pass through all HTML attributes, including ARIA attributes,
without any special handling:

```astro
---
// src/components/Alert.astro
interface Props {
  type?: 'info' | 'warning' | 'error';
}

const { type = 'info' } = Astro.props;

const roleMap = {
  info: 'status',
  warning: 'alert',
  error: 'alert',
};
---
<div role={roleMap[type]} aria-live={type === 'info' ? 'polite' : 'assertive'}>
  <slot />
</div>
```

### Focus management with client-side JS

For dynamic content (modals, drawers), use a framework island or `is:inline`
scripts to manage focus:

```astro
---
// src/components/Modal.astro
---
<dialog id="modal" aria-labelledby="modal-title">
  <h2 id="modal-title"><slot name="title" /></h2>
  <div><slot /></div>
  <button data-close-modal>Close</button>
</dialog>

<script>
  // This script is bundled by Astro (no is:inline needed)
  function setupModal() {
    const modal = document.getElementById('modal') as HTMLDialogElement;
    const closeBtn = modal?.querySelector('[data-close-modal]');

    closeBtn?.addEventListener('click', () => {
      modal.close();
    });

    modal?.addEventListener('close', () => {
      // Return focus to the element that opened the modal
      const opener = document.querySelector('[data-opens-modal]');
      (opener as HTMLElement)?.focus();
    });
  }

  // Handle both initial load and View Transitions navigation
  setupModal();
  document.addEventListener('astro:after-swap', setupModal);
</script>
```

### Accessible navigation patterns

Mobile navigation with proper ARIA and keyboard support:

```astro
---
// src/components/MobileNav.astro
const navItems = [
  { href: '/', label: 'Home' },
  { href: '/about', label: 'About' },
  { href: '/blog', label: 'Blog' },
  { href: '/contact', label: 'Contact' },
];
---
<nav aria-label="Primary">
  <button
    id="menu-toggle"
    aria-expanded="false"
    aria-controls="mobile-menu"
    aria-label="Open navigation menu"
  >
    <span class="hamburger" aria-hidden="true"></span>
  </button>

  <ul id="mobile-menu" role="list" hidden>
    {navItems.map((item) => (
      <li>
        <a
          href={item.href}
          aria-current={Astro.url.pathname === item.href ? 'page' : undefined}
        >
          {item.label}
        </a>
      </li>
    ))}
  </ul>
</nav>

<script>
  function setupNav() {
    const toggle = document.getElementById('menu-toggle');
    const menu = document.getElementById('mobile-menu');
    if (!toggle || !menu) return;

    toggle.addEventListener('click', () => {
      const expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!expanded));
      toggle.setAttribute('aria-label',
        expanded ? 'Open navigation menu' : 'Close navigation menu'
      );
      menu.hidden = expanded;

      if (!expanded) {
        // Focus the first link when opening
        const firstLink = menu.querySelector('a');
        firstLink?.focus();
      }
    });

    // Close on Escape
    menu.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-label', 'Open navigation menu');
        menu.hidden = true;
        toggle.focus();
      }
    });
  }

  setupNav();
  document.addEventListener('astro:after-swap', setupNav);
</script>
```

---

## Performance Optimization

### Zero JS by default

Astro's defining feature: `.astro` components ship zero client-side JavaScript.
All component logic runs at build time and only HTML/CSS is sent to the browser.

**Audit implication:** If a FAT audit finds excessive JS bundle size on an Astro
site, the issue is almost certainly in framework component islands (React, Vue,
Svelte, etc.) that are over-hydrated.

### Client directives

When a component needs interactivity, Astro requires an explicit hydration
directive. Choosing the right one has a direct performance impact:

| Directive | When it hydrates | Use for |
|-----------|-----------------|---------|
| `client:load` | Immediately on page load | Critical interactive elements (cart, auth) |
| `client:idle` | After page finishes loading (requestIdleCallback) | Non-critical interactive elements |
| `client:visible` | When element enters the viewport | Below-fold components, comments section |
| `client:media="(query)"` | When a media query matches | Mobile-only menus, responsive widgets |
| `client:only="react"` | Client-only, no SSR | Components that depend on browser APIs |

```astro
---
import SearchWidget from '../components/SearchWidget.jsx';
import NewsletterForm from '../components/NewsletterForm.svelte';
import CommentSection from '../components/CommentSection.tsx';
import MobileDrawer from '../components/MobileDrawer.vue';
---

<!-- Critical: needs to be interactive immediately -->
<SearchWidget client:load />

<!-- Non-critical: can wait for idle -->
<NewsletterForm client:idle />

<!-- Below the fold: hydrate when scrolled to -->
<CommentSection client:visible />

<!-- Only needs JS on mobile -->
<MobileDrawer client:media="(max-width: 768px)" />
```

**Common fix:** Audit finds slow TTI. Check for `client:load` directives that
could be replaced with `client:idle` or `client:visible`.

### Content Collections for structured content

Content Collections enforce schema validation and provide type safety. This
matters for QA because it catches missing frontmatter (titles, descriptions,
dates) at build time rather than producing broken pages:

```typescript
// src/content.config.ts
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: z.object({
    title: z.string().max(60),
    description: z.string().max(160),
    publishDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    author: z.string(),
    image: z.string(),
    imageAlt: z.string(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
  }),
});

export const collections = { blog };
```

**Audit note:** If blog posts have inconsistent or missing meta descriptions,
recommend adding Content Collections schema validation to catch these issues
at build time.

### Prefetch integration

Astro has built-in link prefetching. Enable it in the config:

```js
// astro.config.mjs
export default defineConfig({
  prefetch: {
    prefetchAll: false, // true = prefetch all links on the page
    defaultStrategy: 'viewport', // 'hover' | 'viewport' | 'load'
  },
});
```

Or per-link:

```html
<a href="/about" data-astro-prefetch>About</a>
<a href="/blog" data-astro-prefetch="hover">Blog</a>
<a href="/contact" data-astro-prefetch="viewport">Contact</a>
```

### View Transitions API

Astro's View Transitions provide SPA-like navigation with MPA architecture:

```astro
---
// src/layouts/BaseLayout.astro
import { ViewTransitions } from 'astro:transitions';
---
<html lang="en">
  <head>
    <ViewTransitions />
  </head>
  <body>
    <header transition:persist>
      <!-- Header stays mounted across navigations -->
    </header>
    <main transition:animate="slide">
      <slot />
    </main>
  </body>
</html>
```

**Performance impact:** View Transitions avoid full page reloads, keeping the
perceived performance high. However, scripts that rely on `DOMContentLoaded`
will not re-fire. Use `astro:after-swap` and `astro:page-load` events instead:

```astro
<script>
  // Runs on every navigation, including the initial page load
  document.addEventListener('astro:page-load', () => {
    // Reinitialise components, analytics page views, etc.
  });
</script>
```

### Island architecture benefits

When auditing an Astro site, keep in mind:

- **Static HTML is free.** Only hydrated islands contribute to JS bundle size.
- **Each island hydrates independently.** A slow React component does not block
  an adjacent Svelte component.
- **Framework mixing is supported.** React, Vue, Svelte, Solid, and Preact
  components can coexist on the same page, each hydrating with the correct
  runtime.

**What to look for in audits:**
1. Pages that import framework components but forget `client:*` directives --
   these render as static HTML (the component's initial state) but are not
   interactive.
2. Pages with many `client:load` islands that could be `client:visible`.
3. Large framework runtimes loaded for trivially simple interactions that
   could be plain `<script>` tags instead.

---

## Analytics Integration

### Partytown for off-main-thread analytics

Partytown moves third-party scripts (Google Analytics, Tag Manager, etc.) into
a web worker so they do not block the main thread:

```bash
npx astro add partytown
```

```js
// astro.config.mjs
import partytown from '@astrojs/partytown';

export default defineConfig({
  integrations: [
    partytown({
      config: {
        forward: ['dataLayer.push'],
      },
    }),
  ],
});
```

Then add the analytics script with `type="text/partytown"`:

```astro
---
// src/layouts/BaseLayout.astro
---
<head>
  <!-- Google Analytics via Partytown -->
  <script type="text/partytown" src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
  <script type="text/partytown">
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('set', 'page_path', window.location.pathname);
    gtag('config', 'G-XXXXXXXXXX');
  </script>
</head>
```

**Important:** The `forward` config option is required for any function calls
the analytics script needs. Without `forward: ['dataLayer.push']`, GTM events
will silently fail.

### Script placement with is:inline

For analytics that must run exactly as written (no bundling, no module wrapping):

```astro
<script is:inline>
  // This runs in the global scope, unbundled
  (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
  new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
  j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
  'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
  })(window,document,'script','dataLayer','GTM-XXXXXXX');
</script>
```

**When to use `is:inline`:**
- The script uses `document.write` (some legacy analytics)
- The script must execute in global scope (not wrapped in a module)
- The script is a third-party snippet that should not be modified

**When NOT to use `is:inline`:**
- Your own application scripts -- let Astro bundle and optimise them
- Scripts that import modules -- `is:inline` prevents import resolution

### View Transitions and analytics

When View Transitions are enabled, page views must be tracked on each
navigation, not just initial load:

```astro
<script>
  document.addEventListener('astro:page-load', () => {
    // Fire on every navigation (including initial page load)
    if (typeof gtag === 'function') {
      gtag('set', 'page_path', window.location.pathname);
      gtag('event', 'page_view');
    }
  });
</script>
```

---

## Common Pitfalls

### Forgetting client: directives on interactive components

**Symptom:** A React/Vue/Svelte component renders but buttons do not work,
inputs do not accept text, state does not change.

**Cause:** The component was imported without a `client:*` directive. Astro
renders it as static HTML at build time and ships no JavaScript for it.

```astro
<!-- BROKEN: renders as static HTML, not interactive -->
---
import Counter from '../components/Counter.jsx';
---
<Counter />

<!-- FIXED: hydrates on the client -->
<Counter client:load />
```

**Audit detection:** Look for framework component imports (`.jsx`, `.tsx`,
`.svelte`, `.vue`) in `.astro` files that lack a `client:*` directive. If the
component contains any interactivity (event handlers, state), it needs one.

### Over-hydrating with client:load

**Symptom:** Poor TTI (Time to Interactive) or large JS bundle on initial load.

**Cause:** Using `client:load` on every component when most do not need
immediate interactivity.

```astro
<!-- BEFORE: everything loads immediately -->
<Header client:load />
<HeroSlider client:load />
<TestimonialCarousel client:load />
<ContactForm client:load />
<Footer client:load />

<!-- AFTER: only critical components load immediately -->
<Header client:load />
<HeroSlider client:load />
<TestimonialCarousel client:visible />
<ContactForm client:visible />
<!-- Footer has no interactivity -- no directive needed -->
<Footer />
```

### Not setting lang attribute on html element

**Symptom:** Accessibility audit flags missing language declaration.

**Cause:** The `lang` attribute is in the layout's `<html>` tag. Easy to forget
because Astro does not add it by default.

```astro
<!-- WRONG -->
<html>

<!-- CORRECT -->
<html lang="en">
```

**For multilingual sites**, pass the language as a prop:

```astro
---
const { lang = 'en' } = Astro.props;
---
<html lang={lang}>
```

### Missing viewBox on inline SVGs

**Symptom:** SVGs render at wrong size or do not scale responsively.

**Cause:** When inlining SVGs in Astro components, the viewBox attribute can
get dropped or the SVG may have hardcoded width/height:

```astro
<!-- WRONG: hardcoded dimensions, no viewBox -->
<svg width="24" height="24">
  <path d="..." />
</svg>

<!-- CORRECT: viewBox allows responsive scaling -->
<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
  <path d="..." />
</svg>
```

**For icon components:**

```astro
---
// src/components/Icon.astro
interface Props {
  name: string;
  size?: number;
  label?: string;
}

const { name, size = 24, label } = Astro.props;
---
<svg
  viewBox="0 0 24 24"
  width={size}
  height={size}
  aria-hidden={label ? undefined : 'true'}
  aria-label={label}
  role={label ? 'img' : undefined}
>
  <use href={`/icons/sprite.svg#${name}`} />
</svg>
```

### Content Collections schema validation gotchas

**Symptom:** Build fails with cryptic Zod validation errors.

**Common causes and fixes:**

1. **Date parsing:** Frontmatter dates without quotes are parsed as YAML dates.
   Use `z.coerce.date()` instead of `z.date()`:

   ```typescript
   // WRONG: fails on YAML date objects
   publishDate: z.date(),

   // CORRECT: coerces strings and YAML dates
   publishDate: z.coerce.date(),
   ```

2. **Optional fields without defaults:** If a field is optional in some posts,
   mark it properly:

   ```typescript
   // WRONG: every post must have tags
   tags: z.array(z.string()),

   // CORRECT: defaults to empty array if missing
   tags: z.array(z.string()).default([]),
   ```

3. **Image validation in schema:** Use the built-in `image()` helper for
   type-safe image references:

   ```typescript
   import { defineCollection, z } from 'astro:content';

   const blog = defineCollection({
     schema: ({ image }) => z.object({
       title: z.string(),
       cover: image(),
       coverAlt: z.string(),
     }),
   });
   ```

### Trailing slash inconsistency between dev and production

**Symptom:** Links work in dev but produce 404s in production (or vice versa).

**Cause:** Astro's dev server handles both `/about` and `/about/`, but static
hosting platforms (Netlify, Cloudflare Pages) may not. The behaviour depends on
the `trailingSlash` config and the host's settings.

```js
// astro.config.mjs
export default defineConfig({
  // Pick one and be consistent:
  trailingSlash: 'always',  // /about/ (recommended for static hosting)
  // trailingSlash: 'never', // /about
  // trailingSlash: 'ignore', // both work (default, but risky)
});
```

**Fix checklist:**
1. Set `trailingSlash` explicitly in `astro.config.mjs`
2. Ensure all internal `<a href>` values match the chosen convention
3. If using `'always'`, verify the hosting platform serves `index.html` from
   directories (most do by default)
4. If using Netlify, check `netlify.toml` for conflicting `[[redirects]]` rules
5. Update sitemap URLs to match -- `@astrojs/sitemap` respects the
   `trailingSlash` config automatically

**Quick diagnostic:** Fetch the problematic URL with and without a trailing
slash. If one returns a 301/308 redirect and the other returns 200, the config
and hosting are misaligned.
