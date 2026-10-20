# Claims, Disclosure & Conversion Checks

Checks that HTML scoring can't see but a human reviewer catches in minutes:
public claims the product can't back, security.txt and sub-processor
disclosures that don't match reality, mobile sign-up paths that hide the
button, analytics that are installed but never send, and site-wide metadata
that a framework layout silently inherits. Each check lists what to test, how,
pass/fail and the fix brief. Run them on every page in the sitemap, not just
the homepage.

Set up once per audit:

```bash
mkdir -p .fat-work/pages .fat-work/text
curl -s https://example.com/sitemap.xml | grep -oE '<loc>[^<]*' | sed 's/<loc>//' | tr -d '\r' > .fat-work/urls.txt
# Save every page, then strip tags/scripts to plain text for grepping.
```

On Windows, Python writes `\r\n` in text mode; strip `\r` before looping URLs
in bash or every request silently fails with status `000`.

---

## 1. Public claims the product can't back

**What:** compliance and security claims ("SOC 2 audit in progress",
"AES-256 at rest", "ISO 27001", "GDPR certified"), infrastructure claims
("infrastructure we own end to end", "direct relationships with inbox
providers"), named SDKs, plugins and apps, testimonials, customer counts and
other stats, and code snippets that show an API.

**How:**
1. Grep the page text for claim patterns:
   `SOC ?2|ISO ?27|HIPAA|PCI|AES|encrypt|99\.[0-9]+%|uptime|SLA|trusted by|[0-9]{2,}\+|customers|in progress|certified|own(ed)? .*infrastructure|SDK|plugin|app store|Zapier|Shopify app`.
2. **Cross-page consistency.** The same fact must read the same everywhere:
   compare the security page, privacy policy, pricing table, about page,
   features page and FAQ. "SOC 2 audit in progress" on one page and "not yet
   audited" on another is a finding even if one of them is true. Same for
   backup frequency, which plan includes a feature (pricing table vs feature
   copy), data residency dates, founder location.
3. **Every named package or integration must exist publicly.** Query the
   registry, not the vendor page (vendor pages 403 bots):

   | Ecosystem | Check (200 = exists) |
   |---|---|
   | npm | `https://registry.npmjs.org/<name>` (read `dist-tags.latest`, `license`) |
   | PyPI | `https://pypi.org/pypi/<name>/json` |
   | RubyGems | `https://rubygems.org/api/v1/gems/<name>.json` |
   | Packagist | `https://packagist.org/search.json?q=<name>` |
   | NuGet | `https://azuresearch-usnc.nuget.org/query?q=<name>` |
   | Go | `https://proxy.golang.org/<module>/@v/list` |
   | crates.io | `https://crates.io/api/v1/crates/<name>` |
   | WordPress.org | `https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&request[slug]=<slug>` |
   | Shopify App Store | `https://apps.shopify.com/<handle>` |
   | Zapier | `https://zapier.com/apps/<app>/integrations` |
   | App Store / Play | search the store for the brand; record the listing URL |

   Also check versions and tool counts the copy quotes ("80+ tools", "v2 SDK")
   against the published package, not the repo.
4. **Code snippets on marketing pages must compile against the published SDK.**
   If the repo or package is available, grep the SDK for every option a snippet
   uses. An invented option (`emails.send({ ai: {...} })`) is copied by
   developers and fails.
5. **Stats and testimonials:** every number needs a source on the page or in
   the product (live dashboards, published reports). Product mockups that show
   numbers are fine when they are obviously illustrative; quotes need a real,
   named person who agreed to them.

**Pass/fail and priority:**
- P1: a compliance/security claim that is false or contradicted on another
  page; an infrastructure claim that changed (e.g. "we run our own delivery
  stack" after moving to a cloud provider); a code snippet using an API that
  doesn't exist.
- P2: a named SDK, plugin or app that isn't published (or is unlisted while the
  copy says "the X app"); the same fact stated differently across pages;
  counts that no longer match ("100+ templates" when the library has 24).
- P3: unsourced but plausible stats; marketing superlatives.

**Fix brief:** state only what is true today, in one place (usually the
security or pricing page), and link to it from everywhere else. Move roadmap
items into a clearly labelled "coming" list with no dates you can't keep.

---

## 2. security.txt (RFC 9116)

**What:** `/.well-known/security.txt` exists, is valid, and agrees with the
site's security / responsible-disclosure page.

**How:**
```bash
curl -s -i https://example.com/.well-known/security.txt
curl -s -o /dev/null -w "%{http_code}\n" https://example.com/security.txt   # legacy location
```
Validate:
- HTTP 200, `Content-Type: text/plain` (a 200 HTML page is a soft-404, a fail).
- `Contact:` present (mailto: or https:), at least one.
- `Expires:` present, ISO 8601, in the future and less than a year away.
- Optional but checked if present: `Encryption:` (URL resolves to a key),
  `Policy:` (resolves, ideally the security page), `Canonical:` (matches the
  served URL), `Preferred-Languages:`. A PGP-signed file must verify.
- **Consistency with the security page:** the contact address is the same; if
  the page promises a PGP key, a bug bounty or a policy URL "in our
  security.txt", the field exists. The disclosure email must be readable in
  the served HTML: Cloudflare Email Obfuscation rewrites addresses to
  `[email protected]` plus a JS decoder, so crawlers, AI answer engines and
  no-JS readers see no address at all.

**Priority:** missing while the site has a security or disclosure page: P2
(P3 otherwise). Expired or soft-404: P2. Page promises something the file
doesn't contain: P2.

**Fix brief:** serve a static file, e.g.
```
Contact: mailto:security@example.com
Expires: 2027-10-01T00:00:00Z
Policy: https://example.com/security
Preferred-Languages: en
Canonical: https://example.com/.well-known/security.txt
```
Put a calendar reminder to bump `Expires`. Turn off email obfuscation for the
disclosure address (Cloudflare: Scrape Shield > Email Address Obfuscation, or a
`<!--email_off-->` block).

---

## 3. Sub-processor and privacy disclosure completeness

**What:** the privacy policy's sub-processor / third-party list covers every
vendor that actually touches personal data, and lists nothing that isn't used.

**How:** build a vendor inventory, then diff it against the policy.
- DNS: `MX`, `TXT` (SPF `include:`s such as `amazonses.com`, `sendgrid.net`,
  `_spf.google.com`; verification tokens such as `google-site-verification`,
  `postal-verification`, `MS=`), DKIM CNAMEs (`*.dkim.amazonses.com`),
  `CNAME`s for app/api/status hosts.
- Response headers: `Server`, `Via`, `cf-ray`, `x-vercel-id`, `x-amz-cf-id`.
- Browser network log: every third-party host the page calls (analytics, tag
  managers, fonts, CDNs, chat, error tracking, RUM beacons such as
  `static.cloudflareinsights.com`).
- Product surfaces: "Sign in with Google/Microsoft", payment provider, SMS/email
  delivery provider, AI providers named in the copy, backup destination.
- If you have the repo, grep env examples and config for vendor SDKs.

**Pass/fail:** each vendor processing personal data appears in the policy with
its role and region. P2 for an undisclosed vendor that receives personal data
(analytics, email delivery, AI, backups, auth). P3 for a stale entry (listed
but not loaded, e.g. the policy names one analytics tool while the site runs
another) or a missing region / transfer note.

**Fix brief:** a table of vendor, purpose, data, region; keep it next to the
code that adds vendors (a checklist item in the PR template).

---

## 4. Vendor naming policy

**What:** some brands must never name certain vendors publicly (white-labelled
infrastructure, competitor names, supplier names under NDA).

**How:** list every third-party brand that appears in marketing copy, `<meta>`,
JSON-LD, `llms.txt`, OG images, alt text and public DNS TXT records, with the
page and a snippet. Check project memory / CLAUDE.md / brand guidelines for a
"never name" list.

**Pass/fail:** a name on the owner's "never name" list: P1. Otherwise report
the inventory without a priority so the owner can judge; note vendor names
that leak through DNS (e.g. a `postal-verification` TXT record) or legal pages,
which a copy review misses.

---

## 5. Mobile conversion (390 x 844)

**What:** a phone visitor can always reach the primary sign-up action.

**How (Playwright, iPhone viewport, `is_mobile=True`, `has_touch=True`):**
1. On load, the primary CTA ("Start free", "Sign up", "Get started") inside the
   header/nav is visible and fully inside the viewport without scrolling.
2. Open the mobile menu (button with `aria-label` / text "menu"), wait for the
   transition, then check the CTA buttons inside it are within the viewport.
   Measure the header: if `header.getBoundingClientRect().height` exceeds
   `innerHeight`, a sticky header + tall menu hides the bottom items; the menu
   panel needs `max-height: calc(100dvh - <bar height>)` and `overflow-y: auto`.
   Screenshot the open menu.
3. Every visible `input`, `select` and `textarea` (marketing forms, login,
   register, newsletter, search) has computed `font-size >= 16px` on mobile, or
   iOS Safari zooms the page on focus.
4. `document.documentElement.scrollWidth <= innerWidth` (no sideways scroll),
   and repeat at desktop width: decorative blurred blobs positioned off-edge in
   a section without `overflow: hidden/clip` cause it.

```js
// evaluate in the page
const vis = e => { const r = e.getBoundingClientRect(); return r.width && r.height && r.top >= 0 && r.bottom <= innerHeight; };
const cta = [...document.querySelectorAll('header a, header button, nav a, nav button')]
  .filter(e => /^(start free|sign up|get started|try)/i.test(e.innerText.trim()));
const small = [...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,textarea')]
  .filter(e => e.offsetParent && parseFloat(getComputedStyle(e).fontSize) < 16);
({ ctaInView: cta.some(vis), smallInputs: small.map(e => e.name || e.id || e.type),
   hOverflow: document.documentElement.scrollWidth > innerWidth });
```

**Priority:** no reachable sign-up CTA on mobile (header and menu): P1. Menu
items cut off below the fold: P2. Inputs under 16px: P2 (forms that convert),
P3 (search boxes). Horizontal overflow: P2.

**Fix brief:** keep the CTA pair at the top of the mobile menu; cap the menu
panel to the remaining viewport and let it scroll; use `text-base sm:text-sm`
(Tailwind) or `font-size: 16px` on mobile inputs; clip decorative overflow on
the section (`overflow-x: clip`).

---

## 6. Analytics actually firing

**What:** a tag in the HTML proves nothing. Confirm hits leave the browser and
custom conversion events arrive.

**How:** in Playwright, record requests and match the collector:

| Tool | Hit to look for |
|---|---|
| GA4 | `google-analytics.com/g/collect` (query `en=page_view`, `tid=G-...`) |
| GTM-only | the container loads, then a GA4/Ads hit follows |
| Plausible | `/api/event` |
| PostHog | `/e/`, `/i/v0/e/`, `/batch/` |
| Umami | `/api/send` |
| Cloudflare Web Analytics | `cloudflareinsights.com/cdn-cgi/rum` |
| Meta Pixel | `facebook.com/tr` |

Then trigger one tracked interaction that doesn't submit anything (a copy
button, an outbound link with navigation aborted) and check the event lands in
`window.dataLayer` and as a hit. GA4 batches events: navigate away (or wait
~10 s) to flush before concluding it didn't fire. Check every host in the
funnel (marketing site and app sign-up page) uses the same measurement ID.

**Priority:** tag present but zero hits (CSP blocks it, wrong ID, consent mode
denied with no banner to grant it): P1. Page views fire but conversion events
never do: P2. Two analytics tools where the privacy policy lists one: see §3.

**Fix brief:** fix the CSP `connect-src`/`script-src`, the ID, or the consent
default; define the conversion events (sign-up started/submitted, CTA click)
and mark them as key events in the analytics property.

---

## 7. Site-wide metadata inheritance (framework layouts)

**What:** layouts in Next.js, Nuxt, SvelteKit and Astro let a root-level
canonical, `og:url`, title or description leak onto every page that doesn't
override it. Per-page "self-referencing canonical" checks miss the pattern;
count it across the sitemap.

**How:** for every sitemap URL record `<title>`, meta description, canonical,
`og:url`, `og:image`, `twitter:title`. Flag:
- canonical equal to the homepage on any URL that isn't the homepage (P1 when
  it affects several pages: those pages are telling search engines they are
  duplicates of the homepage and drop out of the index);
- `og:url` pointing at the homepage (P2);
- pages with the homepage's exact title or description (P2);
- pages with no `og:image` while others have one. In Next.js, `metadata` merges
  shallowly: a page that sets its own `openGraph` loses the root's images,
  site name and locale (P2);
- `twitter:title` still the homepage title on pages that set an OG title (P3).

**Fix brief:** remove canonical/`og:url` from the root layout; give every page
a self-referencing canonical through one helper that returns canonical,
complete `openGraph` (with images) and `twitter` together. Client-component
pages need a sibling `layout.tsx` to export metadata.

---

## 8. Paint cost, motion and third-party main-thread time

**What:** the expensive things markup scoring doesn't weigh.

**How (browser, after load):**
- Count elements with `backdrop-filter` (worse on `position: fixed/sticky`
  elements, repainted every scroll frame), and elements running `infinite` CSS
  animations; check they stop under `prefers-reduced-motion` and when
  offscreen.
- `<video autoplay>`: transfer size, `preload`, `poster`, and whether mobile
  gets a smaller file or a poster only.
- From Lighthouse, read the LCP phase breakdown. A text LCP with a long
  "render delay" (seconds) means the element was in the HTML but painted late:
  render-blocking CSS, a JS-injected render-blocking script (Cloudflare Email
  Obfuscation's `email-decode.min.js`, Rocket Loader), web-font swap, or a
  hydration-time reveal animation.
- `third-party-summary` and `bootup-time`: a tag manager costing more than
  ~250 ms of main thread on mobile should load after interaction / on idle.
- HTML document size: a framework page over ~250 KB is usually serialized
  component data (RSC/`__NEXT_DATA__`) for client components that could be
  server-only.

**Priority:** mobile LCP > 4 s or TBT > 600 ms measured: P1. Autoplaying video
over 2 MB on mobile: P1. More than ~5 infinite animations or backdrop-filter on
sticky chrome: P2. Third-party main-thread > 250 ms: P2.

**Fix brief:** pause animations offscreen (IntersectionObserver) and under
reduced motion; replace sticky `backdrop-filter` with a solid background;
serve poster-only video on mobile; load the tag manager with `lazyOnload` or
on first interaction; turn off Cloudflare Email Obfuscation / Rocket Loader;
move data-heavy components to the server.
