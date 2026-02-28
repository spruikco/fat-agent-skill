# Gatsby -- Framework Fix Reference

Gatsby-specific patterns for fixing issues found during post-launch QA audits.
Covers SEO, structured data, images, accessibility, performance, analytics, and
common pitfalls unique to Gatsby's architecture.

---

## SEO Meta Tags

Gatsby provides two approaches for managing `<head>` content: the modern Head API
(Gatsby 4.19+) and the legacy `gatsby-plugin-react-helmet`. New projects should
always use the Head API.

### Gatsby Head API (Gatsby 4.19+)

Export a named `Head` function from any page or template. Gatsby server-renders
this into the static HTML automatically.

```jsx
// src/pages/about.js
import * as React from "react"

export function Head() {
  return (
    <>
      <title>About Us | Example Co</title>
      <meta name="description" content="Learn about our team and mission." />
      <link rel="canonical" href="https://example.com/about" />
    </>
  )
}

export default function AboutPage() {
  return <main><h1>About Us</h1></main>
}
```

The `Head` export receives the same props as the page component (`data`,
`pageContext`, `location`, `params`), so you can build dynamic meta from
GraphQL query results.

```jsx
// src/templates/blog-post.js
import * as React from "react"
import { graphql } from "gatsby"

export function Head({ data }) {
  const post = data.markdownRemark.frontmatter
  return (
    <>
      <title>{post.title} | My Blog</title>
      <meta name="description" content={post.excerpt} />
      <meta property="og:title" content={post.title} />
      <meta property="og:description" content={post.excerpt} />
      <meta property="og:type" content="article" />
    </>
  )
}

export const query = graphql`
  query ($id: String!) {
    markdownRemark(id: { eq: $id }) {
      frontmatter {
        title
        excerpt
      }
    }
  }
`

export default function BlogPost({ data }) {
  return (
    <article
      dangerouslySetInnerHTML={{ __html: data.markdownRemark.html }}
    />
  )
}
```

### Legacy: gatsby-plugin-react-helmet

Still used in older Gatsby 3.x and early 4.x projects. Requires both
`react-helmet` and `gatsby-plugin-react-helmet`.

```bash
npm install react-helmet gatsby-plugin-react-helmet
```

```js
// gatsby-config.js
module.exports = {
  plugins: [`gatsby-plugin-react-helmet`],
}
```

```jsx
import * as React from "react"
import { Helmet } from "react-helmet"

export default function AboutPage() {
  return (
    <>
      <Helmet>
        <title>About Us | Example Co</title>
        <meta name="description" content="Learn about our team and mission." />
        <link rel="canonical" href="https://example.com/about" />
      </Helmet>
      <main><h1>About Us</h1></main>
    </>
  )
}
```

**Migration note:** If upgrading to the Head API, remove `react-helmet` and
`gatsby-plugin-react-helmet` entirely. The two approaches should not be mixed
on the same page -- the Head API takes precedence, and leftover Helmet calls
will be silently ignored.

### Reusable SEO Component

The recommended pattern is a shared `SEO` component used inside every page's
`Head` export.

```jsx
// src/components/seo.js
import * as React from "react"
import { useStaticQuery, graphql } from "gatsby"

export function SEO({ title, description, pathname, image, children }) {
  const { site } = useStaticQuery(graphql`
    query {
      site {
        siteMetadata {
          title
          description
          siteUrl
          image
          twitterUsername
        }
      }
    }
  `)

  const meta = site.siteMetadata
  const seo = {
    title: title ? `${title} | ${meta.title}` : meta.title,
    description: description || meta.description,
    url: `${meta.siteUrl}${pathname || ""}`,
    image: `${meta.siteUrl}${image || meta.image}`,
    twitterUsername: meta.twitterUsername,
  }

  return (
    <>
      <title>{seo.title}</title>
      <meta name="description" content={seo.description} />

      {/* Open Graph */}
      <meta property="og:title" content={seo.title} />
      <meta property="og:description" content={seo.description} />
      <meta property="og:url" content={seo.url} />
      <meta property="og:type" content="website" />
      <meta property="og:image" content={seo.image} />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />

      {/* Twitter Card */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={seo.title} />
      <meta name="twitter:description" content={seo.description} />
      <meta name="twitter:image" content={seo.image} />
      {seo.twitterUsername && (
        <meta name="twitter:creator" content={seo.twitterUsername} />
      )}

      {/* Canonical */}
      <link rel="canonical" href={seo.url} />

      {children}
    </>
  )
}
```

**Usage in a page:**

```jsx
// src/pages/pricing.js
import * as React from "react"
import { SEO } from "../components/seo"

export function Head() {
  return (
    <SEO
      title="Pricing"
      description="Simple, transparent pricing for teams of any size."
      pathname="/pricing"
    />
  )
}

export default function PricingPage() {
  return <main><h1>Pricing</h1></main>
}
```

### Complete Head Export with All Tags

For pages that need full coverage (homepage, key landing pages):

```jsx
export function Head() {
  return (
    <>
      {/* Primary */}
      <html lang="en" />
      <title>Example Co -- Build Better Products</title>
      <meta name="description" content="Example Co helps teams ship faster." />
      <link rel="canonical" href="https://example.com/" />

      {/* Open Graph */}
      <meta property="og:title" content="Example Co -- Build Better Products" />
      <meta property="og:description" content="Example Co helps teams ship faster." />
      <meta property="og:url" content="https://example.com/" />
      <meta property="og:type" content="website" />
      <meta property="og:site_name" content="Example Co" />
      <meta property="og:image" content="https://example.com/og-image.jpg" />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:image:alt" content="Example Co hero banner" />
      <meta property="og:locale" content="en_US" />

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content="@exampleco" />
      <meta name="twitter:creator" content="@exampleco" />
      <meta name="twitter:title" content="Example Co -- Build Better Products" />
      <meta name="twitter:description" content="Example Co helps teams ship faster." />
      <meta name="twitter:image" content="https://example.com/og-image.jpg" />

      {/* Technical */}
      <meta name="robots" content="index, follow" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <meta name="theme-color" content="#1a1a2e" />
      <link rel="icon" href="/favicon.ico" />
      <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
    </>
  )
}
```

---

## Structured Data (JSON-LD)

### Using the Head API

Place `<script type="application/ld+json">` tags inside the `Head` export.
Build the schema object in JavaScript and serialize it with `JSON.stringify`.

```jsx
// src/templates/blog-post.js
export function Head({ data }) {
  const post = data.markdownRemark.frontmatter
  const siteUrl = data.site.siteMetadata.siteUrl

  const schema = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.excerpt,
    datePublished: post.date,
    dateModified: post.dateModified || post.date,
    image: post.featuredImage
      ? `${siteUrl}${post.featuredImage.publicURL}`
      : undefined,
    author: {
      "@type": "Person",
      name: post.author,
      url: `${siteUrl}/about`,
    },
    publisher: {
      "@type": "Organization",
      name: "Example Co",
      logo: {
        "@type": "ImageObject",
        url: `${siteUrl}/logo.png`,
      },
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `${siteUrl}${post.slug}`,
    },
  }

  return (
    <>
      <title>{post.title} | Example Co Blog</title>
      <meta name="description" content={post.excerpt} />
      <script type="application/ld+json">
        {JSON.stringify(schema)}
      </script>
    </>
  )
}
```

### Organization Schema (Homepage)

```jsx
// src/pages/index.js
export function Head() {
  const orgSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Example Co",
    url: "https://example.com",
    logo: "https://example.com/logo.png",
    sameAs: [
      "https://twitter.com/exampleco",
      "https://linkedin.com/company/exampleco",
      "https://github.com/exampleco",
    ],
    contactPoint: {
      "@type": "ContactPoint",
      telephone: "+1-555-123-4567",
      contactType: "customer service",
    },
  }

  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Example Co",
    url: "https://example.com",
    potentialAction: {
      "@type": "SearchAction",
      target: "https://example.com/search?q={search_term_string}",
      "query-input": "required name=search_term_string",
    },
  }

  return (
    <>
      <title>Example Co -- Build Better Products</title>
      <script type="application/ld+json">
        {JSON.stringify(orgSchema)}
      </script>
      <script type="application/ld+json">
        {JSON.stringify(websiteSchema)}
      </script>
    </>
  )
}
```

### FAQ Schema

```jsx
export function Head({ data }) {
  const faqs = data.allFaqJson.nodes

  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  }

  return (
    <>
      <title>FAQ | Example Co</title>
      <script type="application/ld+json">
        {JSON.stringify(faqSchema)}
      </script>
    </>
  )
}
```

### Dynamic Schema from GraphQL

Pull structured data fields directly from the CMS via Gatsby's data layer:

```jsx
export const query = graphql`
  query ProductPage($id: String!) {
    product(id: { eq: $id }) {
      name
      description
      price
      currency
      sku
      image {
        publicURL
      }
      rating
      reviewCount
    }
    site {
      siteMetadata {
        siteUrl
      }
    }
  }
`

export function Head({ data }) {
  const p = data.product
  const siteUrl = data.site.siteMetadata.siteUrl

  const productSchema = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: p.name,
    description: p.description,
    image: `${siteUrl}${p.image.publicURL}`,
    sku: p.sku,
    offers: {
      "@type": "Offer",
      price: p.price,
      priceCurrency: p.currency,
      availability: "https://schema.org/InStock",
    },
    aggregateRating: p.reviewCount > 0
      ? {
          "@type": "AggregateRating",
          ratingValue: p.rating,
          reviewCount: p.reviewCount,
        }
      : undefined,
  }

  return (
    <script type="application/ld+json">
      {JSON.stringify(productSchema)}
    </script>
  )
}
```

---

## Image Optimization

Gatsby's image pipeline processes images at build time, generating responsive
sizes, modern formats (WebP, AVIF), and blur-up placeholders.

### Installation

```bash
npm install gatsby-plugin-image gatsby-plugin-sharp gatsby-transformer-sharp
```

```js
// gatsby-config.js
module.exports = {
  plugins: [
    `gatsby-plugin-image`,
    `gatsby-plugin-sharp`,
    `gatsby-transformer-sharp`,
  ],
}
```

### StaticImage (Fixed Source at Build Time)

Use `StaticImage` when the image source is known at build time and does not
change based on props. The `src` prop must be a static string -- it cannot be
a variable or expression.

```jsx
import { StaticImage } from "gatsby-plugin-image"

export default function Header() {
  return (
    <header>
      <StaticImage
        src="../images/hero.jpg"
        alt="Mountain landscape at sunrise"
        layout="fullWidth"
        placeholder="blurred"
        formats={["auto", "webp", "avif"]}
        quality={90}
      />
    </header>
  )
}
```

**StaticImage restrictions:**

- `src` must be a static string literal (no variables, no template literals)
- Cannot receive `src` as a prop from a parent component
- Cannot use `src` from component state or context
- Gatsby statically analyzes the code at build time to find the image

```jsx
// THIS WILL NOT WORK -- src is dynamic
function Card({ imagePath }) {
  return <StaticImage src={imagePath} alt="card" />  // Build error
}

// THIS WORKS -- src is a static string
function Card() {
  return <StaticImage src="../images/card.jpg" alt="card" />
}
```

### GatsbyImage (Dynamic Source from GraphQL)

Use `GatsbyImage` when the image comes from GraphQL queries (CMS content,
markdown frontmatter, filesystem nodes, etc).

```jsx
import { GatsbyImage, getImage } from "gatsby-plugin-image"
import { graphql } from "gatsby"

export default function BlogPost({ data }) {
  const post = data.markdownRemark
  const image = getImage(post.frontmatter.featuredImage)

  return (
    <article>
      {image && (
        <GatsbyImage
          image={image}
          alt={post.frontmatter.featuredImageAlt}
        />
      )}
      <h1>{post.frontmatter.title}</h1>
    </article>
  )
}

export const query = graphql`
  query ($id: String!) {
    markdownRemark(id: { eq: $id }) {
      frontmatter {
        title
        featuredImageAlt
        featuredImage {
          childImageSharp {
            gatsbyImageData(
              width: 800
              layout: CONSTRAINED
              placeholder: BLURRED
              formats: [AUTO, WEBP, AVIF]
            )
          }
        }
      }
      html
    }
  }
`
```

### getImage Helper

The `getImage` helper safely extracts `gatsbyImageData` from nested GraphQL
objects. It handles null checks and various nesting depths:

```jsx
import { getImage } from "gatsby-plugin-image"

// All of these work -- getImage navigates the nesting for you
const image = getImage(data.file)
const image = getImage(data.file.childImageSharp)
const image = getImage(data.file.childImageSharp.gatsbyImageData)

// Returns undefined if the image is missing (no crash)
const image = getImage(null) // => undefined
```

### Layout Types

| Layout | Behavior | When to Use |
|--------|----------|-------------|
| `constrained` | Scales down to fit container, never exceeds `width`/`height`. Generates `srcset` with multiple sizes. | Most content images. Default layout. |
| `fixed` | Renders at exact `width` and `height`. Generates 1x and 2x versions for retina. | Logos, icons, avatars, thumbnails. |
| `fullWidth` | Stretches to fill the container width. Always spans the full width of its parent. | Hero images, banners, full-bleed backgrounds. |

```jsx
// Constrained (default) -- max 800px wide, scales down in smaller containers
<StaticImage src="../images/photo.jpg" alt="" layout="constrained" width={800} />

// Fixed -- always 100x100px (200x200 on retina)
<StaticImage src="../images/avatar.jpg" alt="" layout="fixed" width={100} height={100} />

// Full width -- spans container, generates sizes up to viewport width
<StaticImage src="../images/hero.jpg" alt="" layout="fullWidth" />
```

### Placeholder Options

Placeholders display while the full image loads (lazy loading). Each adds a
small amount to the HTML payload.

| Placeholder | What It Shows | Payload Impact | Best For |
|-------------|---------------|----------------|----------|
| `blurred` | Tiny blurred version of the image inlined as base64 | ~1-2KB per image | Photos, detailed images |
| `dominantColor` | Solid color matching the image's dominant color | ~20 bytes | Logos, simple graphics |
| `tracedSVG` | Simplified SVG outline of the image | ~1-5KB per image | Artistic effect, illustrations |
| `none` | No placeholder (empty space until loaded) | 0KB | Above-fold images with preload |

```jsx
<StaticImage
  src="../images/photo.jpg"
  alt="Sunset over the ocean"
  placeholder="blurred"
/>

<StaticImage
  src="../images/logo.png"
  alt="Company logo"
  placeholder="dominantColor"
/>
```

### Image CDN for Remote Images (Gatsby 5+)

Gatsby 5 introduced Image CDN support, which processes remote images on-the-fly
instead of downloading and processing them at build time. This dramatically
reduces build times for sites with many CMS-hosted images.

```js
// gatsby-config.js (with a CMS source plugin that supports Image CDN)
module.exports = {
  plugins: [
    {
      resolve: `gatsby-source-contentful`,
      options: {
        spaceId: process.env.CONTENTFUL_SPACE_ID,
        accessToken: process.env.CONTENTFUL_ACCESS_TOKEN,
      },
    },
  ],
}
```

```jsx
// In a template -- remote images work like local ones
export const query = graphql`
  query ($id: String!) {
    contentfulBlogPost(id: { eq: $id }) {
      title
      heroImage {
        gatsbyImageData(
          layout: FULL_WIDTH
          placeholder: DOMINANT_COLOR
          width: 1200
        )
      }
    }
  }
`
```

Image CDN is supported by Contentful, DatoCMS, and WordPress source plugins
(among others). Check your source plugin documentation for support status.

---

## Accessibility Patterns

### Built-In Focus Management (@reach/router)

Gatsby uses `@reach/router` internally. On client-side navigation, Gatsby:

1. Moves focus to a wrapper `<div>` around the page content
2. Announces the new page title via an ARIA live region (`aria-live="assertive"`)

This is automatic -- no configuration is needed. However, the focus wrapper
element receives `tabindex="-1"` and `role="group"`, so the focused element is
not a landmark and screen reader users may need to navigate into the content.

### Skip Link Pattern

A skip link allows keyboard users to jump directly to the main content,
bypassing repeated navigation. Gatsby provides an example using
`@reach/skip-nav`:

```bash
npm install @reach/skip-nav
```

```jsx
// src/components/layout.js
import * as React from "react"
import { SkipNavLink, SkipNavContent } from "@reach/skip-nav"
import "@reach/skip-nav/styles.css"

export default function Layout({ children }) {
  return (
    <>
      <SkipNavLink>Skip to main content</SkipNavLink>
      <header>
        <nav>{/* Navigation links */}</nav>
      </header>
      <SkipNavContent>
        <main>{children}</main>
      </SkipNavContent>
      <footer>{/* Footer content */}</footer>
    </>
  )
}
```

If you prefer not to use `@reach/skip-nav`, implement it manually:

```jsx
// src/components/layout.js
import * as React from "react"
import "./layout.css"

export default function Layout({ children }) {
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <header>
        <nav aria-label="Main navigation">{/* links */}</nav>
      </header>
      <main id="main-content" tabIndex={-1}>
        {children}
      </main>
      <footer>{/* footer */}</footer>
    </>
  )
}
```

```css
/* src/components/layout.css */
.skip-link {
  position: absolute;
  left: -9999px;
  top: auto;
  width: 1px;
  height: 1px;
  overflow: hidden;
  z-index: 9999;
}

.skip-link:focus {
  position: fixed;
  top: 10px;
  left: 10px;
  width: auto;
  height: auto;
  padding: 12px 24px;
  background: #000;
  color: #fff;
  font-size: 1rem;
  text-decoration: none;
  border-radius: 4px;
}
```

### ARIA in Gatsby Components

Gatsby components are standard React components, so all ARIA attributes use
the camelCase JSX syntax:

```jsx
function SearchForm() {
  const [query, setQuery] = React.useState("")
  const [results, setResults] = React.useState([])

  return (
    <div role="search" aria-label="Site search">
      <label htmlFor="search-input">Search</label>
      <input
        id="search-input"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-describedby="search-help"
        aria-controls="search-results"
      />
      <p id="search-help">Enter keywords to search articles and pages.</p>
      <ul id="search-results" role="listbox" aria-label="Search results">
        {results.map((r) => (
          <li key={r.id} role="option">
            <a href={r.slug}>{r.title}</a>
          </li>
        ))}
      </ul>
      {results.length === 0 && query && (
        <p role="status" aria-live="polite">
          No results found for "{query}".
        </p>
      )}
    </div>
  )
}
```

### gatsby-plugin-a11y (Development Warnings)

Surfaces accessibility warnings during development using `react-axe`:

```bash
npm install gatsby-plugin-a11y
```

```js
// gatsby-config.js
module.exports = {
  plugins: [
    {
      resolve: `gatsby-plugin-a11y`,
      options: {
        // Show errors only (not warnings) in console
        showInDevelopment: true,
        axeOptions: {
          runOnly: {
            type: "tag",
            values: ["wcag2a", "wcag2aa"],
          },
        },
      },
    },
  ],
}
```

This plugin only runs in development (`gatsby develop`). It does not affect
production builds.

### Accessible Gatsby Link

Gatsby's `<Link>` component handles client-side routing and focus management.
Add descriptive text and ARIA attributes like any anchor element:

```jsx
import { Link } from "gatsby"

// Good -- descriptive link text
<Link to="/pricing">View pricing plans</Link>

// Good -- aria-label for icon-only links
<Link to="/" aria-label="Go to homepage">
  <LogoIcon />
</Link>

// Good -- aria-current is set automatically by Gatsby for the active page
<Link to="/about" activeClassName="active">About</Link>
```

---

## Performance Optimization

### Static Site Generation (Default)

Every page in Gatsby is statically generated at build time by default. The
HTML is pre-rendered, so the first paint is fast and content is immediately
available for search engine crawlers. After the initial HTML load, Gatsby
hydrates the page into a full React application for client-side interactivity.

No configuration is needed -- this is the default behavior.

### Deferred Static Generation (DSG)

DSG (Gatsby 4+) defers the generation of specific pages until their first
request. The page is built once on the first visit, then cached for subsequent
requests. This is useful for large sites where thousands of pages slow down
builds but most traffic concentrates on recent content.

**Using `createPage` in gatsby-node.js:**

```js
// gatsby-node.js
exports.createPages = async ({ graphql, actions }) => {
  const { createPage } = actions
  const result = await graphql(`
    query {
      allMarkdownRemark {
        nodes {
          id
          frontmatter {
            slug
            date
          }
        }
      }
    }
  `)

  const sixMonthsAgo = new Date()
  sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6)

  result.data.allMarkdownRemark.nodes.forEach((node) => {
    const postDate = new Date(node.frontmatter.date)

    createPage({
      path: `/blog/${node.frontmatter.slug}`,
      component: require.resolve(`./src/templates/blog-post.js`),
      context: { id: node.id },
      // Defer older posts -- they are built on first request
      defer: postDate < sixMonthsAgo,
    })
  })
}
```

**Using File System Route API:**

```jsx
// src/pages/blog/{MarkdownRemark.frontmatter__slug}.js
import * as React from "react"
import { graphql } from "gatsby"

export async function config() {
  const result = await graphql(`
    query {
      allMarkdownRemark {
        nodes {
          frontmatter {
            slug
            date
          }
        }
      }
    }
  `)

  const sixMonthsAgo = new Date()
  sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6)

  return ({ params }) => {
    const node = result.data.allMarkdownRemark.nodes.find(
      (n) => n.frontmatter.slug === params.frontmatter__slug
    )
    return {
      defer: node && new Date(node.frontmatter.date) < sixMonthsAgo,
    }
  }
}

export default function BlogPost({ data }) {
  return <article>{/* ... */}</article>
}
```

**Requirement:** DSG requires a Node.js server at runtime (`gatsby serve` or a
compatible hosting platform like Gatsby Cloud or Netlify). It does not work with
purely static hosting like S3 or basic Cloudflare Pages.

### Code Splitting (Automatic)

Gatsby automatically code-splits per page. Each page gets its own JavaScript
bundle, and shared code is extracted into common chunks. No manual
configuration is needed.

To further optimize, lazy-load heavy components:

```jsx
import * as React from "react"

// Lazy-load a heavy component (chart library, map, etc.)
const HeavyChart = React.lazy(() => import("../components/heavy-chart"))

export default function AnalyticsPage() {
  const [isClient, setIsClient] = React.useState(false)

  React.useEffect(() => {
    setIsClient(true)
  }, [])

  return (
    <main>
      <h1>Analytics Dashboard</h1>
      {isClient && (
        <React.Suspense fallback={<div>Loading chart...</div>}>
          <HeavyChart />
        </React.Suspense>
      )}
    </main>
  )
}
```

### gatsby-plugin-preload-fonts

Preloads fonts per route to reduce time-to-first-meaningful-paint. The plugin
uses Puppeteer to crawl your site and discover which font files each route needs.

```bash
npm install gatsby-plugin-preload-fonts
```

```js
// gatsby-config.js
module.exports = {
  plugins: [`gatsby-plugin-preload-fonts`],
}
```

After installing, run the font crawl:

```bash
npx gatsby-preload-fonts
```

This generates a `font-preload-cache.json` file at the project root. Commit
this file to version control. On each build, Gatsby injects `<link rel="preload">`
tags for the fonts needed by each route.

**Rerun `gatsby-preload-fonts` whenever you add new fonts or routes.** Stale
cache data means new routes will not have font preloads.

### gatsby-plugin-offline (PWA)

Creates a service worker for offline support using Workbox:

```bash
npm install gatsby-plugin-offline
```

```js
// gatsby-config.js
module.exports = {
  plugins: [
    {
      resolve: `gatsby-plugin-offline`,
      options: {
        precachePages: [`/about/`, `/blog/*`],
        workboxConfig: {
          runtimeCaching: [
            {
              urlPattern: /^https:\/\/fonts\.googleapis\.com/,
              handler: `StaleWhileRevalidate`,
            },
            {
              urlPattern: /^https:\/\/fonts\.gstatic\.com/,
              handler: `CacheFirst`,
              options: {
                cacheName: `google-fonts-webfonts`,
                expiration: {
                  maxEntries: 30,
                  maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
                },
              },
            },
          ],
        },
      },
    },
  ],
}
```

**Important:** `gatsby-plugin-offline` must come **after** `gatsby-plugin-manifest`
in the plugins array. The manifest is needed for the PWA install prompt.

**Warning:** Service workers can cause stale content issues. During QA, you
may see old content persisting after deploys. Test with DevTools > Application >
Service Workers > "Update on reload" enabled, and consider using
`gatsby-plugin-remove-serviceworker` if offline support is not needed.

### Bundle Analysis

Use `gatsby-plugin-webpack-bundle-analyser-v2` to visualize bundle contents:

```bash
npm install gatsby-plugin-webpack-bundle-analyser-v2
```

```js
// gatsby-config.js
module.exports = {
  plugins: [
    {
      resolve: `gatsby-plugin-webpack-bundle-analyser-v2`,
      options: {
        analyzerMode: `static`,
        reportFilename: `_bundle-report.html`,
        openAnalyzer: false,
        defaultSizes: `gzip`,
      },
    },
  ],
}
```

After `gatsby build`, open `_bundle-report.html` to see an interactive treemap
of all bundles. Look for:

- Unexpectedly large dependencies (moment.js, lodash full imports)
- Duplicate copies of the same library
- Large components that should be lazy-loaded
- CSS-in-JS runtime cost

---

## Analytics Integration

### gatsby-plugin-google-gtag (Recommended)

The recommended plugin for Google Analytics 4 (GA4) and other Google tags
(Ads, etc). It replaces the deprecated `gatsby-plugin-google-analytics`.

```bash
npm install gatsby-plugin-google-gtag
```

```js
// gatsby-config.js
module.exports = {
  plugins: [
    {
      resolve: `gatsby-plugin-google-gtag`,
      options: {
        trackingIds: [
          "G-XXXXXXXXXX",       // GA4 Measurement ID
          "AW-XXXXXXXXXX",      // Google Ads (optional)
        ],
        gtagConfig: {
          anonymize_ip: true,
          cookie_expires: 0,
        },
        pluginConfig: {
          // Puts gtag script in <head> instead of <body>
          head: true,
          // Respect Do Not Track
          respectDNT: true,
          // Exclude paths from tracking
          exclude: ["/preview/**", "/admin/**"],
          // Delay processing pageview events on route change (ms)
          delayOnRouteUpdate: 0,
        },
      },
    },
  ],
}
```

**Important:** This plugin only loads in production (`gatsby build && gatsby serve`).
It does **not** fire during `gatsby develop`.

### gatsby-plugin-google-tagmanager

For sites using Google Tag Manager as a container for all tags:

```bash
npm install gatsby-plugin-google-tagmanager
```

```js
// gatsby-config.js
module.exports = {
  plugins: [
    {
      resolve: `gatsby-plugin-google-tagmanager`,
      options: {
        id: "GTM-XXXXXXX",
        includeInDevelopment: false,
        defaultDataLayer: {
          platform: "gatsby",
        },
        // Place script in <head>
        enableWebVitalsTracking: true,
      },
    },
  ],
}
```

### gatsby-plugin-facebook-pixel

```bash
npm install gatsby-plugin-facebook-pixel
```

```js
// gatsby-config.js
module.exports = {
  plugins: [
    {
      resolve: `gatsby-plugin-facebook-pixel`,
      options: {
        pixelId: "YOUR_PIXEL_ID",
      },
    },
  ],
}
```

### Custom SPA Tracking with onRouteUpdate

Gatsby is a single-page application after initial load. Standard analytics
scripts only fire on the initial page load, missing subsequent client-side
navigations. The `onRouteUpdate` API in `gatsby-browser.js` fires on every
route change:

```js
// gatsby-browser.js

// Generic pattern for any analytics provider
export const onRouteUpdate = ({ location, prevLocation }) => {
  // Don't track the initial page load (the analytics script handles it)
  if (!prevLocation) return

  // Example: custom analytics call
  if (typeof window.analytics !== "undefined") {
    window.analytics.page({
      path: location.pathname,
      referrer: prevLocation ? prevLocation.pathname : "",
      title: document.title,
      url: location.href,
    })
  }
}
```

```js
// gatsby-browser.js -- manual GA4 event (if not using gatsby-plugin-google-gtag)
export const onRouteUpdate = ({ location }) => {
  if (typeof window.gtag === "undefined") return

  // Wait for page title to update
  setTimeout(() => {
    window.gtag("event", "page_view", {
      page_title: document.title,
      page_location: location.href,
      page_path: location.pathname,
    })
  }, 100)
}
```

**Note on delayOnRouteUpdate:** If you use page transitions (e.g.,
`gatsby-plugin-transition-link`), the page title and content may not be
updated when `onRouteUpdate` fires. Use `delayOnRouteUpdate` in the gtag plugin
options or add a manual `setTimeout` to wait for transitions to complete.

---

## Common Pitfalls

### Node vs Browser APIs (typeof window)

Gatsby renders pages in Node.js during `gatsby build`. Code that references
browser globals (`window`, `document`, `navigator`, `localStorage`) crashes
the build.

**The problem:**

```jsx
// BREAKS during gatsby build -- window does not exist in Node.js
const width = window.innerWidth

export default function MyComponent() {
  return <div>Width: {width}</div>
}
```

**Fix 1: Guard with typeof check (for side effects only, not rendering):**

```jsx
export default function MyComponent() {
  if (typeof window !== "undefined") {
    // Safe to use window here for side effects
    window.scrollTo(0, 0)
  }
  return <div>Content</div>
}
```

**Fix 2: useEffect (preferred for rendering differences):**

```jsx
import * as React from "react"

export default function MyComponent() {
  const [windowWidth, setWindowWidth] = React.useState(0)

  React.useEffect(() => {
    // useEffect only runs in the browser, never during SSR
    setWindowWidth(window.innerWidth)
    const handleResize = () => setWindowWidth(window.innerWidth)
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  return <div>Width: {windowWidth || "Loading..."}</div>
}
```

**Fix 3: Null loader for browser-only packages in gatsby-node.js:**

Some npm packages reference `window` at the module level. They crash the build
even if you never call them during SSR.

```js
// gatsby-node.js
exports.onCreateWebpackConfig = ({ stage, loaders, actions }) => {
  if (stage === "build-html" || stage === "develop-html") {
    actions.setWebpackConfig({
      module: {
        rules: [
          {
            test: /leaflet/,    // Replace with the offending package
            use: loaders.null(),
          },
        ],
      },
    })
  }
}
```

### GraphQL Data Layer Complexity

Gatsby's GraphQL layer auto-generates types from source data. Schema inference
can produce unexpected types when data is inconsistent.

**Problem:** A field that is a string in one node and null in another gets
inferred as `String` -- but if the first node Gatsby encounters has a number,
the whole field becomes `Int` and string values crash the build.

**Fix: Explicit schema definitions in gatsby-node.js:**

```js
// gatsby-node.js
exports.createSchemaCustomization = ({ actions }) => {
  const { createTypes } = actions
  createTypes(`
    type MarkdownRemarkFrontmatter {
      title: String!
      date: Date! @dateformat
      tags: [String]
      featuredImage: File @fileByRelativePath
      # Force price to always be Float, even if some entries look like integers
      price: Float
    }
  `)
}
```

### Build Time Growing with Content Volume

Gatsby processes every page and image at build time. As content grows, builds
slow down.

**Mitigation strategies:**

| Strategy | Impact | Implementation |
|----------|--------|----------------|
| Deferred Static Generation | Defer infrequently-visited pages | `defer: true` in `createPage` |
| Parallel image processing | Speed up Sharp image transforms | `GATSBY_CPU_COUNT` env variable |
| Incremental builds | Only rebuild changed pages | Gatsby Cloud (proprietary feature) |
| Reduce image sizes | Fewer pixels to process | Set `maxWidth` in GraphQL queries |
| Cache `.cache` and `public` | Skip re-processing unchanged assets | Persist between CI builds |

```bash
# Speed up image processing with more CPU cores
GATSBY_CPU_COUNT=4 gatsby build

# Or use logical cores (often faster)
GATSBY_CPU_COUNT=logical_cores gatsby build
```

### gatsby-node.js vs gatsby-browser.js vs gatsby-ssr.js

These three files have distinct roles. Putting code in the wrong file is a
common source of bugs.

| File | Runs Where | Runs When | Purpose |
|------|-----------|-----------|---------|
| `gatsby-node.js` | Node.js only | Build time | Create pages, customize GraphQL schema, modify webpack config |
| `gatsby-browser.js` | Browser only | Runtime (client) | Wrap root element, respond to route changes, inject client-side code |
| `gatsby-ssr.js` | Node.js only | Build time (HTML generation) | Wrap root element for SSR, inject scripts/styles into server-rendered HTML |

**Common mistake:** Adding a context provider in `gatsby-browser.js` but
forgetting to add the same provider in `gatsby-ssr.js`. The provider exists in
the client but not in the server-rendered HTML, causing a hydration mismatch.

```js
// gatsby-browser.js
import * as React from "react"
import { ThemeProvider } from "./src/context/theme"

export const wrapRootElement = ({ element }) => (
  <ThemeProvider>{element}</ThemeProvider>
)
```

```js
// gatsby-ssr.js -- MUST mirror gatsby-browser.js
import * as React from "react"
import { ThemeProvider } from "./src/context/theme"

export const wrapRootElement = ({ element }) => (
  <ThemeProvider>{element}</ThemeProvider>
)
```

**Tip:** Extract the shared wrapper into a single file and import it from both:

```js
// src/wrap-root-element.js
import * as React from "react"
import { ThemeProvider } from "./context/theme"

export function wrapRootElement({ element }) {
  return <ThemeProvider>{element}</ThemeProvider>
}
```

```js
// gatsby-browser.js
export { wrapRootElement } from "./src/wrap-root-element"
```

```js
// gatsby-ssr.js
export { wrapRootElement } from "./src/wrap-root-element"
```

### Hydration Mismatches with Client-Only Content

When the server-rendered HTML differs from the initial client render, React
logs a hydration warning and may discard the server-rendered DOM entirely,
causing a flash of content.

**Common causes:**

1. Rendering based on `typeof window !== "undefined"` in the component body
2. Using `Date.now()` or `Math.random()` during render
3. Reading `localStorage` or `sessionStorage` during render
4. Different timezone between build server and client

**Incorrect (causes hydration mismatch):**

```jsx
export default function Greeting() {
  // Server renders "Hello, Guest" but client renders "Hello, John"
  const name = typeof window !== "undefined"
    ? localStorage.getItem("name") || "Guest"
    : "Guest"

  return <h1>Hello, {name}</h1>
}
```

**Correct (two-pass rendering):**

```jsx
import * as React from "react"

export default function Greeting() {
  const [name, setName] = React.useState("Guest")

  React.useEffect(() => {
    const stored = localStorage.getItem("name")
    if (stored) setName(stored)
  }, [])

  return <h1>Hello, {name}</h1>
}
```

**For components that cannot render during SSR at all, use a client-only guard:**

```jsx
import * as React from "react"

function ClientOnly({ children, fallback = null }) {
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  return mounted ? children : fallback
}

// Usage
export default function Dashboard() {
  return (
    <main>
      <h1>Dashboard</h1>
      <ClientOnly fallback={<p>Loading map...</p>}>
        <InteractiveMap />
      </ClientOnly>
    </main>
  )
}
```

**Enable DEV_SSR to catch mismatches early:**

```js
// gatsby-config.js
module.exports = {
  flags: {
    DEV_SSR: true,
  },
}
```

This makes `gatsby develop` perform server-side rendering, surfacing hydration
errors during development instead of only during `gatsby build`.

### Plugin Version Compatibility

Gatsby's plugin ecosystem can be fragile across major versions. A Gatsby 5
project may not work with plugins built for Gatsby 3.

**Check compatibility before installing:**

```bash
# Check a plugin's peer dependencies
npm info gatsby-plugin-image peerDependencies

# Check which version of Gatsby a plugin requires
npm info gatsby-plugin-mdx peerDependencies
```

**Common compatibility issues:**

| Scenario | Symptom | Fix |
|----------|---------|-----|
| Plugin requires Gatsby 4, project uses Gatsby 5 | Build error or runtime crash | Check plugin README for v5-compatible version |
| Plugin uses old `gatsby-image` API | Import errors | Migrate to `gatsby-plugin-image` |
| Plugin not updated for React 18 | Hydration warnings, `act()` errors | Pin to last working version or find alternative |
| Multiple plugins modify the same webpack config | Build failures | Check plugin order in `gatsby-config.js` |

**Rule of thumb:** After upgrading Gatsby's major version, update all
`gatsby-*` plugins to their latest versions in the same commit. Run
`npm outdated | grep gatsby` to find stale plugins.

### Image Processing Slowing Builds

Gatsby's Sharp-based image pipeline is the single largest contributor to build
time on content-heavy sites.

**Diagnosis:**

```bash
# Enable Gatsby's build profiling
GATSBY_TIMING=1 gatsby build
```

This prints a timing breakdown showing how long each build phase takes.
`processImages` and `writeImageFiles` are typically the slowest stages.

**Fixes:**

```js
// Reduce generated image sizes -- don't generate larger than you need
export const query = graphql`
  query {
    file(relativePath: { eq: "hero.jpg" }) {
      childImageSharp {
        gatsbyImageData(
          width: 1200          # Cap at 1200px instead of default 2560px
          quality: 80          # 80 is a good balance (default is 50)
          formats: [AUTO, WEBP] # Skip AVIF if build time matters more than file size
          breakpoints: [375, 768, 1024, 1200]  # Fewer breakpoints = fewer images
        )
      }
    }
  }
`
```

```js
// gatsby-config.js -- configure Sharp defaults globally
module.exports = {
  plugins: [
    {
      resolve: `gatsby-plugin-sharp`,
      options: {
        defaults: {
          formats: [`auto`, `webp`],
          quality: 80,
          breakpoints: [375, 768, 1024, 1200],
          placeholder: `dominantColor`, // Cheaper than blurred
        },
      },
    },
  ],
}
```

**CI caching:** Persist the `.cache` and `public` directories between CI builds.
Gatsby skips re-processing images that are already in the cache.

```yaml
# Example: GitHub Actions cache
- name: Cache Gatsby build
  uses: actions/cache@v4
  with:
    path: |
      .cache
      public
    key: gatsby-build-${{ hashFiles('**/gatsby-config.js') }}-${{ github.sha }}
    restore-keys: |
      gatsby-build-${{ hashFiles('**/gatsby-config.js') }}-
      gatsby-build-
```
