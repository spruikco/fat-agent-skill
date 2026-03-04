# Nuxt -- Framework Fix Reference

Nuxt 3 patterns for fixing common QA issues found by FAT Agent. All examples
use the Composition API with `<script setup>` syntax.

---

## SEO Meta Tags

### useHead composable

The primary way to set meta tags per-page. Works in pages, layouts, and
components.

```vue
<!-- pages/about.vue -->
<script setup>
useHead({
  title: 'About Us | Acme Corp',
  meta: [
    { name: 'description', content: 'Learn about Acme Corp and our mission.' },
    { property: 'og:title', content: 'About Us | Acme Corp' },
    { property: 'og:description', content: 'Learn about Acme Corp and our mission.' },
    { property: 'og:image', content: 'https://acme.com/og-about.jpg' },
    { property: 'og:url', content: 'https://acme.com/about' },
    { name: 'twitter:card', content: 'summary_large_image' },
  ],
  link: [
    { rel: 'canonical', href: 'https://acme.com/about' },
  ],
})
</script>
```

`useHead` is reactive. Pass computed values for dynamic titles:

```vue
<script setup>
const { data: post } = await useFetch(`/api/posts/${route.params.slug}`)

useHead({
  title: () => post.value?.title ? `${post.value.title} | Blog` : 'Blog',
  meta: [
    { name: 'description', content: () => post.value?.excerpt ?? '' },
  ],
})
</script>
```

### useSeoMeta composable (type-safe)

Flattened, type-safe alternative. Prevents typos in property names.

```vue
<script setup>
useSeoMeta({
  title: 'About Us | Acme Corp',
  description: 'Learn about Acme Corp and our mission.',
  ogTitle: 'About Us | Acme Corp',
  ogDescription: 'Learn about Acme Corp and our mission.',
  ogImage: 'https://acme.com/og-about.jpg',
  ogUrl: 'https://acme.com/about',
  twitterCard: 'summary_large_image',
  twitterTitle: 'About Us | Acme Corp',
  twitterDescription: 'Learn about Acme Corp and our mission.',
  twitterImage: 'https://acme.com/og-about.jpg',
  robots: 'index, follow',
})
</script>
```

### definePageMeta for route-level meta

`definePageMeta` is a compiler macro for route-level metadata. It runs at build
time, so it cannot reference runtime variables or imported values.

```vue
<script setup>
definePageMeta({
  title: 'Dashboard',
  layout: 'admin',
  middleware: 'auth',
})
</script>
```

Use `definePageMeta` for routing concerns (layout, middleware, page transitions).
Use `useHead` / `useSeoMeta` for HTML `<head>` content.

### App-level defaults in nuxt.config.ts

Set fallback meta tags that apply to every page:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  app: {
    head: {
      htmlAttrs: { lang: 'en' },
      charset: 'utf-8',
      viewport: 'width=device-width, initial-scale=1',
      title: 'Acme Corp',
      meta: [
        { name: 'description', content: 'Default site description for Acme Corp.' },
        { property: 'og:site_name', content: 'Acme Corp' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
      ],
    },
  },
})
```

### Title template

Use `titleTemplate` to avoid repeating the brand suffix on every page:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  app: {
    head: {
      titleTemplate: '%s | Acme Corp',
    },
  },
})
```

Then in a page, just set the page-specific part:

```vue
<script setup>
useHead({ title: 'About Us' })
// Renders: <title>About Us | Acme Corp</title>
</script>
```

To override the template for the homepage:

```vue
<script setup>
useHead({
  title: 'Acme Corp — Build Better Things',
  titleTemplate: '', // disables the template for this page
})
</script>
```

### @nuxtjs/seo module

The `@nuxtjs/seo` module bundles several SEO utilities (sitemap, robots,
og-image, schema-org, link-checker) into one install:

```bash
npx nuxi module add @nuxtjs/seo
```

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ['@nuxtjs/seo'],
  site: {
    url: 'https://acme.com',
    name: 'Acme Corp',
    description: 'Build better things with Acme Corp.',
    defaultLocale: 'en',
  },
})
```

This auto-generates `sitemap.xml`, `robots.txt`, OG images, and schema.org
markup based on your pages.

### Complete per-page example

```vue
<!-- pages/blog/[slug].vue -->
<script setup>
const route = useRoute()
const { data: post } = await useFetch(`/api/posts/${route.params.slug}`)

if (!post.value) {
  throw createError({ statusCode: 404, message: 'Post not found' })
}

useSeoMeta({
  title: post.value.title,
  description: post.value.excerpt,
  ogTitle: post.value.title,
  ogDescription: post.value.excerpt,
  ogImage: post.value.coverImage,
  ogType: 'article',
  ogUrl: `https://acme.com/blog/${route.params.slug}`,
  articlePublishedTime: post.value.publishedAt,
  articleAuthor: post.value.author.name,
  twitterCard: 'summary_large_image',
})

useHead({
  link: [
    { rel: 'canonical', href: `https://acme.com/blog/${route.params.slug}` },
  ],
})
</script>

<template>
  <article>
    <h1>{{ post.title }}</h1>
    <time :datetime="post.publishedAt">{{ post.formattedDate }}</time>
    <div v-html="post.content" />
  </article>
</template>
```

---

## Structured Data (JSON-LD)

### useHead with script for JSON-LD

Inject JSON-LD directly via `useHead`. This works without any extra modules.

```vue
<script setup>
useHead({
  script: [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: 'Acme Corp',
        url: 'https://acme.com',
        logo: 'https://acme.com/logo.png',
        sameAs: [
          'https://twitter.com/acme',
          'https://linkedin.com/company/acme',
        ],
      }),
    },
  ],
})
</script>
```

For a blog post:

```vue
<script setup>
const { data: post } = await useFetch(`/api/posts/${route.params.slug}`)

useHead({
  script: [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        headline: post.value.title,
        description: post.value.excerpt,
        image: post.value.coverImage,
        datePublished: post.value.publishedAt,
        dateModified: post.value.updatedAt,
        author: {
          '@type': 'Person',
          name: post.value.author.name,
        },
        publisher: {
          '@type': 'Organization',
          name: 'Acme Corp',
          logo: {
            '@type': 'ImageObject',
            url: 'https://acme.com/logo.png',
          },
        },
      }),
    },
  ],
})
</script>
```

### nuxt-schema-org module

For a composable-based approach with automatic defaults:

```bash
npx nuxi module add nuxt-schema-org
```

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ['nuxt-schema-org'],
  schemaOrg: {
    identity: {
      type: 'Organization',
      name: 'Acme Corp',
      url: 'https://acme.com',
      logo: 'https://acme.com/logo.png',
    },
  },
})
```

### defineWebSite, defineWebPage composables

These composables from `nuxt-schema-org` add structured data declaratively:

```vue
<!-- app.vue or layouts/default.vue -->
<script setup>
useSchemaOrg([
  defineWebSite({
    name: 'Acme Corp',
    url: 'https://acme.com',
    description: 'Build better things.',
    inLanguage: 'en',
  }),
  defineWebPage(),
])
</script>
```

```vue
<!-- pages/blog/[slug].vue -->
<script setup>
const { data: post } = await useFetch(`/api/posts/${route.params.slug}`)

useSchemaOrg([
  defineArticle({
    headline: post.value.title,
    description: post.value.excerpt,
    image: post.value.coverImage,
    datePublished: post.value.publishedAt,
    dateModified: post.value.updatedAt,
    author: {
      name: post.value.author.name,
    },
  }),
])
</script>
```

For FAQPage:

```vue
<script setup>
useSchemaOrg([
  defineWebPage({ '@type': 'FAQPage' }),
  ...faqs.map(faq =>
    defineQuestion({
      name: faq.question,
      acceptedAnswer: faq.answer,
    })
  ),
])
</script>
```

---

## Image Optimization

### Nuxt Image (@nuxt/image) component

```bash
npx nuxi module add @nuxt/image
```

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ['@nuxt/image'],
  image: {
    quality: 80,
    format: ['webp', 'avif'],
  },
})
```

### NuxtImg and NuxtPicture components

`<NuxtImg>` is a drop-in replacement for `<img>` with automatic optimization.
`<NuxtPicture>` generates `<picture>` with multiple `<source>` elements.

```vue
<template>
  <!-- Basic optimized image -->
  <NuxtImg
    src="/images/hero.jpg"
    alt="Team working on a project"
    width="1200"
    height="630"
    loading="lazy"
    format="webp"
  />

  <!-- Responsive with sizes -->
  <NuxtImg
    src="/images/hero.jpg"
    alt="Team working on a project"
    sizes="100vw sm:50vw md:400px"
    loading="lazy"
  />

  <!-- Picture element with format fallbacks -->
  <NuxtPicture
    src="/images/hero.jpg"
    alt="Team working on a project"
    width="1200"
    height="630"
    format="avif,webp"
    loading="lazy"
  />

  <!-- Preload LCP image (above the fold) -->
  <NuxtImg
    src="/images/hero.jpg"
    alt="Hero banner"
    preload
    width="1200"
    height="630"
  />
</template>
```

**Important:** Always set `width` and `height` to prevent CLS. Use `loading="lazy"`
for below-fold images. Use `preload` for the largest above-fold image (LCP).

### Provider configuration

Configure a remote image provider when images come from a CMS or CDN:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ['@nuxt/image'],
  image: {
    // Default provider for local images
    provider: 'ipx',

    // Cloudinary
    cloudinary: {
      baseURL: 'https://res.cloudinary.com/your-cloud/image/upload/',
    },

    // Imgix
    imgix: {
      baseURL: 'https://your-site.imgix.net/',
    },

    // Allow external domains
    domains: ['cdn.example.com', 'images.unsplash.com'],
  },
})
```

Using a named provider:

```vue
<template>
  <NuxtImg
    provider="cloudinary"
    src="/v1234/blog/hero.jpg"
    alt="Blog hero image"
    width="800"
    height="400"
  />
</template>
```

### Sizes and presets

Define reusable image presets:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  image: {
    presets: {
      blogCover: {
        modifiers: {
          format: 'webp',
          quality: 80,
          width: 800,
          height: 420,
        },
      },
      avatar: {
        modifiers: {
          format: 'webp',
          quality: 75,
          width: 80,
          height: 80,
          fit: 'cover',
        },
      },
      thumbnail: {
        modifiers: {
          format: 'webp',
          quality: 70,
          width: 300,
          height: 200,
          fit: 'cover',
        },
      },
    },

    screens: {
      xs: 320,
      sm: 640,
      md: 768,
      lg: 1024,
      xl: 1280,
      xxl: 1536,
    },
  },
})
```

```vue
<template>
  <NuxtImg preset="blogCover" src="/images/post-cover.jpg" alt="Post cover" />
  <NuxtImg preset="avatar" src="/images/author.jpg" alt="Jane Doe" />
</template>
```

---

## Accessibility Patterns

### Semantic HTML in Vue components

Use native HTML elements. Nuxt auto-imports nothing that changes this rule.

```vue
<template>
  <header>
    <nav aria-label="Main navigation">
      <ul>
        <li><NuxtLink to="/">Home</NuxtLink></li>
        <li><NuxtLink to="/about">About</NuxtLink></li>
        <li><NuxtLink to="/contact">Contact</NuxtLink></li>
      </ul>
    </nav>
  </header>

  <main id="main-content">
    <h1>{{ page.title }}</h1>
    <slot />
  </main>

  <footer>
    <p>&copy; {{ new Date().getFullYear() }} Acme Corp</p>
  </footer>
</template>
```

Skip-to-content link in the layout:

```vue
<!-- layouts/default.vue -->
<template>
  <a href="#main-content" class="skip-link">
    Skip to main content
  </a>
  <AppHeader />
  <main id="main-content" tabindex="-1">
    <slot />
  </main>
  <AppFooter />
</template>

<style scoped>
.skip-link {
  position: absolute;
  top: -100%;
  left: 0;
  z-index: 100;
  padding: 0.5rem 1rem;
  background: #000;
  color: #fff;
}
.skip-link:focus {
  top: 0;
}
</style>
```

### NuxtLink for accessible navigation

`<NuxtLink>` renders a standard `<a>` tag with client-side navigation. It
handles `aria-current="page"` automatically for active routes.

```vue
<template>
  <nav aria-label="Main navigation">
    <NuxtLink to="/" exact-active-class="active">Home</NuxtLink>
    <NuxtLink to="/about" active-class="active">About</NuxtLink>

    <!-- External links automatically get target="_blank" handling -->
    <NuxtLink to="https://docs.example.com" external>
      Documentation
      <span class="sr-only">(opens in new tab)</span>
    </NuxtLink>
  </nav>
</template>

<style>
/* NuxtLink sets aria-current="page" on active links */
a[aria-current="page"] {
  font-weight: bold;
  border-bottom: 2px solid currentColor;
}

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

### Focus management on route changes

By default, Nuxt does not move focus on client-side route changes, which is a
problem for screen reader users. Fix this in a plugin:

```ts
// plugins/focus-management.client.ts
export default defineNuxtPlugin((nuxtApp) => {
  const router = useRouter()

  router.afterEach((to, from) => {
    if (to.path === from.path) return

    nextTick(() => {
      const main = document.getElementById('main-content')
      if (main) {
        main.setAttribute('tabindex', '-1')
        main.focus({ preventScroll: false })
      }
    })
  })
})
```

Alternatively, use the built-in `page:finish` hook:

```ts
// plugins/announce-route.client.ts
export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.hook('page:finish', () => {
    nextTick(() => {
      const h1 = document.querySelector('h1')
      if (h1) {
        h1.setAttribute('tabindex', '-1')
        h1.focus({ preventScroll: true })
      }
    })
  })
})
```

### vue-announcer for screen reader announcements

For dynamic content changes (toasts, loading states, form submissions):

```bash
npm install @vue-a11y/announcer
```

```ts
// plugins/announcer.client.ts
import VueAnnouncer from '@vue-a11y/announcer'

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.use(VueAnnouncer)
})
```

```vue
<script setup>
const { announce } = useAnnouncer()

async function submitForm() {
  await $fetch('/api/contact', { method: 'POST', body: formData })
  announce('Form submitted successfully.', 'assertive')
}
</script>
```

---

## Performance Optimization

### Nuxt rendering modes (SSR, SSG, SPA, hybrid)

Configure the global default in `nuxt.config.ts`:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  // Server-Side Rendering (default) -- best for SEO and dynamic content
  ssr: true,

  // Static Site Generation -- build-time rendering for fully static sites
  // Run with: npx nuxi generate
  ssr: true, // SSG still uses SSR at build time

  // Single-Page Application -- client-only rendering
  ssr: false,
})
```

### Route rules for per-page rendering

The real power is hybrid rendering. Set different strategies per route:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  routeRules: {
    // Static pages -- generated at build time, cached forever
    '/': { prerender: true },
    '/about': { prerender: true },
    '/pricing': { prerender: true },

    // Blog posts -- server-rendered, cached via ISR (regenerate every hour)
    '/blog/**': { isr: 3600 },

    // Dashboard -- client-only SPA (no server rendering)
    '/dashboard/**': { ssr: false },

    // API routes -- cached with stale-while-revalidate
    '/api/**': {
      cache: {
        maxAge: 60,
        staleMaxAge: 300,
      },
    },

    // Redirects
    '/old-page': { redirect: '/new-page' },

    // Custom headers per route
    '/api/**': {
      headers: { 'cache-control': 'no-store' },
    },
  },
})
```

### Component lazy loading (lazy prefix)

Prefix any component with `Lazy` to defer loading until it enters the viewport
or is needed. No import changes required -- it works with auto-imports.

```vue
<template>
  <div>
    <!-- Loaded immediately -->
    <HeroBanner />

    <!-- Lazy loaded when rendered -->
    <LazyTestimonialSlider />
    <LazyFooterNewsletter />

    <!-- Lazy loaded conditionally -->
    <LazyModalDialog v-if="showModal" @close="showModal = false" />
  </div>
</template>
```

For explicit dynamic imports with loading/error states:

```vue
<script setup>
const HeavyChart = defineAsyncComponent({
  loader: () => import('~/components/HeavyChart.vue'),
  loadingComponent: () => h('div', 'Loading chart...'),
  delay: 200,
  timeout: 10000,
})
</script>
```

### Payload extraction

In Nuxt 3.4+, payload extraction splits hydration data into separate files
that can be cached by CDNs:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  experimental: {
    payloadExtraction: true,
  },
})
```

This is particularly useful for static sites. The payload JSON files are
cached independently from the HTML, reducing bandwidth on navigation.

### Nitro server engine

Nitro is Nuxt's server engine. Key performance configurations:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  nitro: {
    // Compress responses
    compressPublicAssets: true,

    // Prerender specific routes at build time
    prerender: {
      routes: ['/', '/about', '/sitemap.xml'],
      crawlLinks: true, // auto-discover pages from links
    },

    // Storage for caching
    storage: {
      cache: {
        driver: 'redis',
        host: 'localhost',
        port: 6379,
      },
    },

    // Minify server output
    minify: true,
  },
})
```

### Auto-imports for smaller bundles

Nuxt auto-imports Vue APIs, composables, and components. This produces
optimally tree-shaken bundles. Do not manually import what Nuxt provides:

```vue
<script setup>
// Do NOT do this -- it may increase bundle size or cause duplicate imports:
// import { ref, computed, watch } from 'vue'
// import { useHead } from '@unhead/vue'
// import { useRoute } from 'vue-router'

// Just use them directly. Nuxt auto-imports these:
const count = ref(0)
const doubled = computed(() => count.value * 2)
const route = useRoute()

useHead({ title: 'My Page' })
</script>
```

To see everything that is auto-imported, check `.nuxt/imports.d.ts` after
running the dev server.

---

## Analytics Integration

### Nuxt plugins for GA4/GTM

Create a client-side plugin for Google Analytics 4:

```ts
// plugins/google-analytics.client.ts
export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig()
  const gtagId = config.public.gtagId

  if (!gtagId) return

  // Load gtag.js
  useHead({
    script: [
      {
        src: `https://www.googletagmanager.com/gtag/js?id=${gtagId}`,
        async: true,
      },
      {
        innerHTML: `
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '${gtagId}');
        `,
      },
    ],
  })

  // Track route changes
  const router = useRouter()
  router.afterEach((to) => {
    if (typeof window.gtag === 'function') {
      window.gtag('event', 'page_view', {
        page_path: to.fullPath,
      })
    }
  })
})
```

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  runtimeConfig: {
    public: {
      gtagId: '', // Set via NUXT_PUBLIC_GTAG_ID env variable
    },
  },
})
```

For Google Tag Manager:

```ts
// plugins/gtm.client.ts
export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig()
  const gtmId = config.public.gtmId

  if (!gtmId) return

  useHead({
    script: [
      {
        innerHTML: `
          (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
          new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
          j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
          'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
          })(window,document,'script','dataLayer','${gtmId}');
        `,
      },
    ],
    noscript: [
      {
        innerHTML: `<iframe src="https://www.googletagmanager.com/ns.html?id=${gtmId}" height="0" width="0" style="display:none;visibility:hidden"></iframe>`,
        tagPosition: 'bodyOpen',
      },
    ],
  })
})
```

### vue-gtag integration

```bash
npm install vue-gtag
```

```ts
// plugins/vue-gtag.client.ts
import VueGtag from 'vue-gtag'

export default defineNuxtPlugin((nuxtApp) => {
  const config = useRuntimeConfig()

  nuxtApp.vueApp.use(VueGtag, {
    config: {
      id: config.public.gtagId,
    },
  }, nuxtApp.$router)
})
```

Then use in components:

```vue
<script setup>
const { event } = useGtag()

function trackClick() {
  event('cta_click', {
    event_category: 'engagement',
    event_label: 'hero_signup',
  })
}
</script>
```

### nuxt-gtag module

The simplest approach. Handles everything automatically:

```bash
npx nuxi module add nuxt-gtag
```

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ['nuxt-gtag'],
  gtag: {
    id: 'G-XXXXXXXXXX',
    config: {
      page_title: true,
      send_page_view: true,
    },
    // Defer loading until user consents (GDPR)
    initialConsent: false,
  },
})
```

Granting consent later:

```vue
<script setup>
const { gtag, initialize } = useGtag()

function acceptCookies() {
  initialize() // loads the gtag script
  gtag('consent', 'update', {
    analytics_storage: 'granted',
  })
}
</script>
```

---

## Common Pitfalls

### Auto-imports masking missing dependencies

Nuxt auto-imports from `vue`, `vue-router`, `nuxt`, and your `composables/`
directory. This means code works locally but can fail if you assume a package
is installed when it is actually provided by a module.

```vue
<script setup>
// This works because Nuxt auto-imports ref from Vue:
const count = ref(0)

// But if you extract this into a standalone utility package,
// it will fail because 'ref' is not imported.
// Always add explicit imports in shared packages or libraries.
</script>
```

**Fix:** When extracting code to a shared package or library outside the Nuxt
project, always add explicit imports:

```ts
// utils/shared-counter.ts (standalone package)
import { ref } from 'vue' // required outside Nuxt auto-import context

export function useCounter() {
  const count = ref(0)
  return { count }
}
```

### Server vs client context (process.server, process.client)

Code in `<script setup>` runs on both server and client during SSR. Browser
APIs are not available on the server.

```vue
<script setup>
// WRONG -- crashes on server:
// const width = window.innerWidth

// CORRECT -- guard with process.client:
const width = ref(0)
if (process.client) {
  width.value = window.innerWidth
}

// CORRECT -- use onMounted (only runs on client):
onMounted(() => {
  width.value = window.innerWidth
})
</script>
```

For components that are entirely client-side, use the `.client.vue` suffix:

```
components/
  VideoPlayer.client.vue   <-- only rendered on client
  SearchBar.vue             <-- renders on both
```

Or wrap with `<ClientOnly>`:

```vue
<template>
  <ClientOnly>
    <VideoPlayer />
    <template #fallback>
      <div class="placeholder">Loading video player...</div>
    </template>
  </ClientOnly>
</template>
```

### useState vs ref (shared state pitfalls)

`ref()` creates a new reactive value per component instance. On the server,
each request gets its own component tree, but `ref()` values declared at module
scope can leak between requests.

`useState()` is SSR-safe and shared across components. It serializes server
state to the client during hydration.

```vue
<script setup>
// WRONG -- leaks state between server requests:
// const user = ref(null) // declared at module scope in a composable

// CORRECT -- SSR-safe shared state:
const user = useState('user', () => null)

// CORRECT -- component-local state (no cross-request leak):
const localCount = ref(0) // fine because it's per-component
</script>
```

The composable pattern:

```ts
// composables/useAuth.ts

// WRONG:
// const user = ref(null) // module-scope ref leaks between requests

// CORRECT:
export function useAuth() {
  const user = useState('auth-user', () => null)
  const isLoggedIn = computed(() => !!user.value)

  async function login(credentials: { email: string; password: string }) {
    user.value = await $fetch('/api/auth/login', {
      method: 'POST',
      body: credentials,
    })
  }

  return { user, isLoggedIn, login }
}
```

### Nitro routes vs pages routes

Nuxt has two routing systems. Confusing them causes 404s and broken APIs.

- `pages/` directory -- Vue components rendered in the browser
- `server/api/` and `server/routes/` -- Nitro server handlers (API endpoints)

```
project/
  pages/
    index.vue           --> https://example.com/
    about.vue           --> https://example.com/about
    blog/[slug].vue     --> https://example.com/blog/my-post
  server/
    api/
      posts.get.ts      --> GET  /api/posts
      posts.post.ts     --> POST /api/posts
      posts/[id].ts     --> /api/posts/123
    routes/
      sitemap.xml.ts    --> /sitemap.xml
    middleware/
      auth.ts           --> runs on every server request
```

Server API route example:

```ts
// server/api/posts.get.ts
export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const posts = await db.posts.findMany({
    take: Number(query.limit) || 10,
  })
  return posts
})
```

```ts
// server/api/posts.post.ts
export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const post = await db.posts.create({ data: body })
  return post
})
```

**Common mistake:** Putting API logic in `pages/api/` (Next.js pattern). In
Nuxt, API routes go in `server/api/`.

### Rendering mode per-route configuration

When using `routeRules`, the rendering mode must match how your page fetches
data. Mismatches cause hydration errors or empty pages.

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  routeRules: {
    // WRONG for a page that uses real-time data:
    // '/dashboard/**': { prerender: true },
    // This bakes in stale data at build time.

    // CORRECT -- client-only rendering for user-specific content:
    '/dashboard/**': { ssr: false },

    // CORRECT -- ISR for content that changes occasionally:
    '/blog/**': { isr: 3600 },

    // CORRECT -- prerender for truly static content:
    '/legal/**': { prerender: true },
  },
})
```

**Gotcha:** `prerender: true` runs the page at build time. If the page calls an
API that requires authentication or returns user-specific data, the build will
either fail or cache the wrong data.

### Environment variables (runtimeConfig vs .env)

Nuxt has strict rules about environment variables. Misusing them exposes
secrets to the client or causes undefined values.

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  runtimeConfig: {
    // Private -- only available on the server (server/ and plugins)
    dbUrl: '',            // Set via NUXT_DB_URL
    apiSecret: '',        // Set via NUXT_API_SECRET

    // Public -- available on both server and client (exposed in the bundle)
    public: {
      apiBase: '',        // Set via NUXT_PUBLIC_API_BASE
      gtagId: '',         // Set via NUXT_PUBLIC_GTAG_ID
    },
  },
})
```

```env
# .env
NUXT_DB_URL=postgres://localhost:5432/mydb
NUXT_API_SECRET=super-secret-key
NUXT_PUBLIC_API_BASE=https://api.example.com
NUXT_PUBLIC_GTAG_ID=G-XXXXXXXXXX
```

Accessing config values:

```ts
// In a server route -- access both private and public:
// server/api/data.ts
export default defineEventHandler(() => {
  const config = useRuntimeConfig()
  console.log(config.dbUrl)          // private -- available
  console.log(config.public.apiBase) // public -- available
  return { ok: true }
})
```

```vue
<!-- In a component -- only public values available -->
<script setup>
const config = useRuntimeConfig()

// CORRECT:
console.log(config.public.apiBase)

// WRONG -- this is undefined on the client:
// console.log(config.dbUrl) // undefined, and should never be exposed
</script>
```

**Common mistakes:**

- Using `process.env.MY_VAR` directly in components. This only works at build
  time, not at runtime. Use `useRuntimeConfig()` instead.
- Putting secrets in `runtimeConfig.public`. Anything under `public` is shipped
  to the client browser. Database URLs, API keys, and tokens go in the top-level
  `runtimeConfig` (private).
- Forgetting the `NUXT_` prefix. Nuxt only reads `.env` variables that start
  with `NUXT_` into `runtimeConfig`. The mapping is automatic:
  `NUXT_DB_URL` maps to `runtimeConfig.dbUrl`,
  `NUXT_PUBLIC_API_BASE` maps to `runtimeConfig.public.apiBase`.
