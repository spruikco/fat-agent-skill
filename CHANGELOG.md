# Changelog

## [3.4.1] - 2026-07-22

### Fixed — hidden-container inputs no longer flagged as unlabelled
Caught dogfooding a client re-audit: the accessibility check counted `<input>`
elements inside hidden containers (bare `hidden` attribute, `aria-hidden`,
`display:none`) as missing labels. Framework detection forms — e.g. the hidden
Netlify form-detection block Next.js sites put in the layout — are invisible to
assistive tech, so their unlabelled inputs are a false positive that inflated
the count and kept a P1 finding open after the visible forms were fixed.

- `analyse-html.py`: streaming parser now tracks hidden-container depth (keyed
  on the tag stack, robust to nesting) and skips form inputs inside them.
- `modules/accessibility.py`: strips hidden form/div blocks before the label
  scan.
- +4 tests = **922 passing**.

## [3.4.0] - 2026-07-20

### Changed — FIX means execute, not just recommend
Phase 2 in SKILL.md now mandates implementation with repo access: work the
punch list directly (technical edits through the repo's own deploy flow),
execute the Content Engine roadmap (titles, internal links, consolidations,
new pages drafted from briefs), and hand DNS/registrar items over as exact
paste-ready records. Loop is fix → deploy → verify; the punch list
auto-resolves on the re-audit.

## [3.3.0] - 2026-07-20

### Changed — deck structure: tight main deck, complete appendix
Driven by live user feedback on a real client deliverable:

- **Deliverables are rendered HTML, never markdown** — new `--briefs` option
  renders every content brief as its own editorial slide (title, demand,
  rationale, numbered outline, link targets). SKILL.md now mandates briefs
  ship as `briefs.json` → deck slides, not .md files.
- **Everything ships, nothing overwhelms**: the main deck stays ~8 slides
  (cover, scorecard, roadmap headline, three hero briefs, P0/P1 findings,
  next steps). An **Appendix** divider then carries the complete detail —
  remaining briefs, every P2/P3 finding, and the full topic inventory as
  dense two-column table slides. No caps, no truncation, no JSON-only data.
- **On-screen section nav** (Score / Roadmap / Findings / Appendix), hidden
  in print.

### Tests
- +2 = **918 passing**.

## [3.2.0] - 2026-07-20

### Added — GA4 behaviour layer
GSC says what ranks; GA4 says whether it works.

- **`scripts/ga4.py`** — ingests a GA4 landing-page report as exported (UI
  CSV with `#` preamble, percentage rates, Grand-total rows — or JSON rows
  from an analytics MCP/API). Two findings rankings can't show:
  **engagement gaps** (≥N sessions, <35% engagement — content/UX problem,
  not a ranking problem) and **money pages converting nothing** (sessions
  but zero key events — broken tracking or broken persuasion). Findings flow
  into the punch list (module `ga4`).
- **SKILL.md**: GA4 section with the same easiest-first data ladder
  (analytics MCP → drop the CSV in unmodified → API on request), and the
  pairing rule with the Content Engine: ranks + traffic − engagement =
  better content, not better SEO.

### Tests
- +5 = **915 passing**.

## [3.1.0] - 2026-07-20

### Changed — Content Engine: zero-reshaping data ingestion
Make it as easy as possible for the end user — never require hand-built JSON.

- **`content_engine.py --gsc` now accepts the Search Console UI export
  as-is**: the downloaded ZIP itself, or a bare `Queries.csv` ("Top queries"
  headers, "1,234" thousands, "3.4%" CTRs, BOM — all handled). JSON from
  MCP/API still works unchanged.
- **Query→page inference**: UI exports lack query→page pairs; when a crawl DB
  is present the engine recovers the mapping by term-matching queries against
  page slugs + titles (matches marked `inferred`).
- **SKILL.md data ladder, easiest first**: (1) a connected Search Console MCP
  → Claude pulls the data itself, the user does nothing; (2) no MCP → the
  user drops the export ZIP in unmodified; (3) API setup only on request.

### Tests
- +5 = **910 passing**.

## [3.0.0] - 2026-07-20

### The Content Engine
Major version: FAT grows from finding what's broken to finding **what's
missing**. Content moves the SEO dial; v3 leads with it.

- **`scripts/content_engine.py`** — clusters real GSC queries into topics
  (greedy Jaccard over stemmed terms, brand terms excluded), maps clusters
  against the site's actual pages + crawl inventory, and classifies every
  cluster: **defend / optimise / rework / consolidate (cannibalisation) /
  create / refresh** (decay via `--previous` period comparison). Every
  create/rework/refresh gets a brief skeleton — working title, target
  queries, suggested H2s from the cluster's own long-tails, money-page link
  target. Findings flow into the punch list (module `content_engine`);
  `--roadmap` writes the full roadmap JSON.
- **Editorial deck**: `editorial_report.py --roadmap` adds a
  **"Content roadmap — where the growth is"** slide rendered BEFORE the
  findings — growth first, defects second.
- **SKILL.md**: the Content Engine workflow + Claude's role spelled out —
  the script supplies evidence (clusters, demand, gaps), Claude writes the
  full briefs and leads the client conversation with the roadmap.

### Tests
- +12 = **905 passing**.

## [2.13.0] - 2026-07-20

### Added — link opportunities + brand-pulled editorial reports
- **`scripts/link_opportunities.py`** — content→money-page internal-link gaps
  from the REAL crawl link graph: content pages (blog/guides/resources) with
  zero internal links to any money page (services/products/pricing/booking).
  With a GSC export, gaps rank by real impressions, show top queries, and get
  a suggested money-page target matched from those queries. Findings flow
  into the punch list (module `link_opportunities`).
- **`scripts/brandkit.py`** — harvests the audited site's own logo, OG/hero
  imagery, colour palette (dominant saturated colour → accent) and typeface
  (Google Fonts link + families) into `brandkit.json` + downloaded images.
- **`scripts/editorial_report.py`** — renders the audit as an A4-landscape,
  photography-led editorial deck in the client's own visual language
  (single-file HTML, print-to-PDF): full-bleed cover, big scorecard, findings
  batched per slide, next-steps close. The default client deliverable;
  Word/PPTX remain for editable documents.
- **SKILL.md**: site-wide Step 4 (link opportunities), editorial-report
  pipeline, and "ship the fix, not just the finding" — paste-ready
  title/meta/heading drafts for every striking-distance and low-CTR keyword.

### Tests
- +11 = **893 passing**.

## [2.12.0] - 2026-07-20

### Added — sitemap hygiene checks (learned in the field)
Shipped straight from a real diagnosis: after fixing every page link on a
production site, a re-crawl still showed ~1,200 × 301 — every one a sitemap
seed (the sitemap generator emitted non-slash URLs on a `trailingSlash` host),
and every remaining 404 was a phantom sitemap entry for pages that never
existed.

- **`sitewide.py` new checks**: `sitemap_redirects` (P1 — sitemap entries
  must be final canonical URLs) and `sitemap_broken` (P1 — sitemap lists
  URLs that 404 or fail to fetch; usually a generator emitting combinations
  that were never built).
- **`internal_redirects` accuracy fix**: now only counts redirects that at
  least one internal link actually points at — sitemap-only redirects were
  previously mislabelled as "internal links resolve through redirects".
- **Systemic-pattern detection**: when most redirects are `URL → URL + '/'`,
  the finding is annotated "SYSTEMIC: fix the generator once", instead of
  presenting N URLs as N individual issues.
- **SKILL.md "Diagnose by origin"**: split sitemap-seed problems from
  page-link problems via the `in_sitemap` column (with ready-to-run SQL), and
  the multiple-generators trap — in Next.js, `app/sitemap.ts` silently
  shadows `public/sitemap.xml`; always verify the LIVE `/sitemap.xml` plus
  every `Sitemap:` line in robots.txt against what each generator emits.

### Tests
- +6 (sitemap redirect/broken checks, internal-vs-sitemap attribution,
  systemic slash-hop annotation) = **882 passing**.

## [2.11.0] - 2026-07-20

### Added — site-wide crawl audit (the layer single pages can't show)
Ported from Froggy (Spruik's internal Screaming-Frog-class crawler), trimmed
to the audit-relevant core. FAT previously audited *pages*; it now audits
*sites*.

- **`scripts/sitecrawl.py`** — concurrent stdlib crawler → SQLite
  (`pages` table + full `links` graph + compact JSON summary to stdout; the
  heavy data never enters conversation context). Seeds from the sitemap as
  well as links (which is what makes orphan detection possible), respects
  robots.txt, strips tracking params during URL normalisation, sniffs
  charsets, records every link with anchor text, retries transient failures,
  backs off adaptively on 403/429 waves, and ships an SSRF guard
  (private/loopback hosts blocked by default; `--allow-private` for
  staging/intranet audits).
- **`scripts/sitewide.py`** — site-level checks over the crawl DB:
  **internal links to broken pages (P0)**, **5xx (P0)**, broken 4xx pages,
  fetch errors, **duplicate titles / meta descriptions / page content across
  URLs**, **orphan pages**, thin content at scale, slow responses (>2s), and
  internal links resolving through redirects. Emits standard FAT findings
  (module `sitewide`) in the scores shape, so they merge straight into the
  punch list and **auto-resolve on a clean re-crawl**. Finding titles are
  stable (counts live in descriptions) so punch-list identity holds across
  crawls. Plus `--query` — SELECT-only, 50-row-capped SQL drill-down for
  token-cheap follow-ups.
- **SKILL.md "Site-Wide Crawl Audit"** — crawl → audit → punch list → SQL
  drill-down workflow; explicit rule: never read page HTML into context
  during a site crawl.

### Tests
- +36 (crawler units, parser, an end-to-end crawl against a local stdlib HTTP
  server incl. orphan/duplicate/broken-link detection, synthetic-DB checks,
  punchlist auto-resolve round-trip) = **876 passing**.

## [2.10.1] - 2026-07-19

### Added — ctx offer-once flow
- **SKILL.md**: when ctx is absent and session continuity would genuinely help
  (resuming a prior-session audit, long engagements), the skill may offer the
  official ctx installer **once, with explicit consent** — a decline is recorded
  in `./.fat-work/.ctx-declined` and the offer is never repeated. Explicitly
  forbidden: silent installation, and bundling/vendoring the ctx binary
  (distribution belongs to the ctx project's installer).
- **README**: "Optional companion — ctx" install note (official one-liners,
  Apache-2.0, local-only).

## [2.10.0] - 2026-07-19

### Added — compaction-safe session continuity
- **`scripts/punchlist.py`** — the punch list now persists to
  `./.fat-work/punchlist.json` instead of living only in conversation memory,
  so audit state survives context compaction, session restarts, and handoffs.
  - `update` merges a scores.json into the list: new findings open, findings
    absent from a **rescanned** module auto-resolve, resolved findings that
    reappear re-open flagged as regressions. Modules not scanned this run are
    left untouched — a quick-profile rescan can't falsely "resolve" a
    full-profile finding (and Security is excluded when not assessed).
  - `status` shows open items grouped by priority (`--json` for machines);
    `resolve` (with `--wontfix`) and `note` record decisions against items —
    the "why we chose this fix" layer that otherwise evaporates with the
    conversation.
- **SKILL.md "Session Continuity & Context Compaction"** — documents the
  design (conversation is disposable, files are not; every check is a
  deterministic script), the resume procedure, and an **optional
  [ctx](https://ctx.rs) integration**: when the ctx CLI is installed, search
  prior agent-session history for the reasoning the punch list can't capture.
  Never required; skipped silently when absent.

### Changed
- **`calculate-score.py` now emits the merged flat `findings` list** in its
  output. `generate-report.py`, `generate-charts.py`, and the HTML dashboard
  already read this key (it previously never existed at the top level), and
  punchlist.py consumes it directly.
- **`ci_gate.py`** treats `overall.blocking` as authoritative when present:
  advisory-module findings in the newly emitted flat list cannot fail the
  build (preserves the 2.9.0 curated-cap semantics). The flat-findings check
  remains as legacy-shape fallback.

### Tests
- +30 (punch list merge/regression/wontfix/CLI round-trip, findings emission,
  ci_gate advisory-vs-blocking) = **840 passing**.

## [2.9.0] - 2026-06-30

### Changed — score-composition redesign (then re-skepticked and fixed)
The headline FAT grade now reflects the whole audit, honestly:
- **Modules feed the grade via a curated P0 cap.** A P0 from a genuinely
  site-critical module (seo, technical_seo, security, crawlability, sitemap) caps
  the grade at D — so a header-level `noindex` can no longer grade A. Advisory
  modules (pwa, cookie_gdpr, eeat, ai_search, content_depth, performance, …) inform
  via findings but do **not** cap the grade (their severities aren't globally
  calibrated to "site broken").
- **Weights rebalanced for an SEO tool:** SEO 40% · Security 25% · Performance 20% ·
  Accessibility 15% (accessibility is no longer weighted equal to SEO).
- **Unassessed categories are imputed at the mean, not excluded** — so skipping
  `--fetch` (no Security headers) no longer *inflates* the grade.
- **Honesty labels in the deliverables:** Word/PPTX scorecards now mark Performance
  "(heuristic)" and Security "(not assessed)" when applicable; dashboard grade bands
  reconciled with the report; `overall` carries `blocking`/`cap_applied`/`modules_scored`.

### Fixed — round-2 skeptic findings
- **Miscalibrated severities** that wrongly capped clean sites: pwa "no manifest"
  P0→P3; cookie_gdpr "no consent banner"/"no privacy policy" P0→P2 and gated on
  tracking actually being present; accessibility missing-alt P0→P1; performance
  render-blocking/large-HTML P1→P2.
- **cookie_gdpr** single-quoted `href` privacy/cookie links now detected;
  **accessibility** form-label check now requires a real `<label for>`/aria, not a
  bare `id=`; **links** stops flagging `rel="noopener"`-only as unsafe; **sitemap**
  no longer flags www↔apex URLs as a foreign domain.
- **ci_gate** reads the nested `overall.score` + `overall.blocking` (it was reading
  dead keys and never blocking on P0).
- **suggest_schema** `_currency` detects glued codes (`EUR12.99`); **gsc** `_parse_ctr`
  treats a bare-number percent (`"5"`) as 5%, not 500%; **content_depth** review
  evidence no longer fires on "Year in Review"/"Code Review"; **ecommerce** finds
  Product nested under `mainEntity`/dict `@graph`; **technical_seo** canonical no
  longer flags `blog.`/`m.`/`amp.` subdomain consolidation; `_title_brand` rejects a
  bare separator. **bulk_audit** now passes the profile's modules (matches the CLI).

## [2.8.0] - 2026-06-30

### Fixed — adversarial self-review ("run a skeptic"): false positives & wrong deliverables
Cry-wolf false positives (always-on modules firing on the wrong pages):
- **YMYL detection** no longer prefix-matches innocent words ("lawn", "taxi",
  "taxonomy", "investigative", "drugstore", "loaner").
- **`is_article`** now needs a per-page signal (own URL path / Article schema /
  on-page `<article>`) — a `/blog/` link in the nav/footer no longer cascades
  editorial findings (incl. a P1) onto plumber homepages and app shells.
- **eeat "trust pages"** downgraded P1→P3 and reworded — it's a page-level
  observation (the footer may not render in this DOM), not a site-wide verdict.
- **AI-crawler block**: blocking *training/opt-out* bots (GPTBot/CCBot/Google-Extended)
  is now P3 informational and doesn't tank the score; only blocking *answer* bots
  (OAI-SearchBot/PerplexityBot) is P1.
- **Canonical host**: http→https and apex↔www are treated as correct consolidation,
  not a P1 "split signals" (and fixed the `lstrip("www.")` footgun that mangled
  hosts like "west.com").
- **"Review" detection** now requires rating/Review-schema evidence, not just the
  word "best"/"compare" in the title.
- **Interstitial / ad-density / JS-only-nav** heuristics tightened to exclude
  fixed headers, cookie/consent banners, hero/announcement banners, and UI
  toggles / `<a name>` anchor targets; interstitial score deduction no longer
  silent.

Wrong client deliverables:
- **suggest_schema currency** no longer guesses USD from a bare "$" (jQuery!) —
  explicit signals only.
- **PDP with a "related products" grid** is classified PDP again (was PLP), so the
  Product JSON-LD is no longer dropped.
- **`x.com` substring** no longer tags netflix.com/dropbox.com as your Twitter;
  hyphenated brands ("Mercedes-Benz") no longer truncated.
- **ecommerce** now parses JSON-LD properly — Product in `@graph`/arrays/list-`@type`
  (Yoast/RankMath/Woo) is detected instead of false "missing offers".
- **schema_validator**: non-string `@type` no longer crashes; `@context` as a
  list/object is recognised; legit-repeatable `@graph` types (ImageObject, etc.)
  and common page types no longer trigger false "duplicate/unknown @type".
- **gsc**: a `"4.2%"` CTR string parses instead of crashing.
- **SEO module** max corrected 61→56 (a perfect page can now reach 100%).

### Known / tracked (not in this release)
- The **headline FAT grade still composes only SEO/Security/A11y/Performance** —
  the 18 newer modules emit findings but don't move the number, and the
  Performance/Security headline scores aren't yet labelled "heuristic/unmeasured"
  in the client report. This is a deliberate scoring-composition redesign for a
  dedicated pass.

## [2.7.0] - 2026-06-30

### Changed — performance scoring honesty & calibration
- **Stopped penalising critical-CSS inlining.** The inline-assets score split into
  inline JS (weighted) vs inline CSS (moderate amounts are fine) — inlining critical
  CSS is a deliberate first-paint/CWV *win*, and the old single-bucket rule wrongly
  docked points and fired a finding for it. The finding is now JS-specific.
- **Softened build-locked image penalty.** Images present but not WebP/srcset now
  floor at 5/20 (was ~3/20), with a clear **architecture-framed P3 finding**
  (effort=high) noting that format is usually a build-pipeline/framework decision
  (a static export can't emit WebP without a step) and matters less when images are
  already sized/dimensioned/lazy-loaded — not a P1 "quick win".
- **Labelled the score as a heuristic.** The `performance` module result now carries
  `measured: false` / `method: "html-heuristic"` and a note: it's a *markup proxy*,
  not measured Core Web Vitals.
- **SKILL.md §1.3 calibration rules:** (1) measure for real with PageSpeed/Lighthouse
  on the live URL and lead with that — you can't PageSpeed a `noindex`/preview;
  (2) **calibrate against the SERP** (if the top-ranking competitors score similar or
  worse, performance isn't the blocker — deprioritise); (3) separate architecture-
  locked items from quick wins. 7 new tests (765 total).

## [2.6.0] - 2026-06-30

### Added
- **GSC health analysis** (`scripts/gsc_health.py`) — beyond the Performance report,
  analyses the **health** reports a URL-only audit can't see: **Manual Actions** (P0),
  **Security Issues** (P0), **Index Coverage / URL Inspection** (indexed vs excluded
  and why — Discovered/Crawled-currently-not-indexed, blocked, soft-404, duplicate-
  canonical, with fix hints), and **Enhancements / rich-result errors** per type.
  Gather the reports via the GSC MCP/API; the script prioritises them for the punch list.
- **Google Discover readiness** (in `content_depth`) — flags articles missing
  `max-image-preview:large`, a large `og:image`, or an RSS/Atom feed.
- **Self-serving review policy** check (in `schema_validator`) — flags
  `aggregateRating`/`review` markup placed on an Organization/LocalBusiness entity
  (ineligible for star results; can trigger a manual action).
- SKILL.md GSC-health collection workflow; 14 new tests (758 total).

## [2.5.0] - 2026-06-29

### Added — "Hobo-parity" depth (cross-referenced against the Hobo Premium SEO Checklist)
- **Crawlability & Indexation module** (`modules/crawlability.py`, always-on) —
  robots.txt blocking CSS/JS (P1), JS-only navigation, faceted/parameter URL sprawl,
  pagination crawlability.
- **Redirect analyser** (`scripts/redirects.py`) — multi-hop chain tracing: redirect
  chains (>1 hop), loops (P0), temporary (302/307) redirects for permanent moves,
  meta-refresh, and **soft 404s** (a "not found" page returning HTTP 200).
- **Content Depth & Quality module** (`modules/content_depth.py`, always-on) —
  YMYL detection, main-content-vs-ad density, information-gain/originality signals,
  freshness (published/updated date), featured-snippet readiness, product-review quality.
- **Video SEO module** (`modules/video.py`, auto-detected) — VideoObject presence +
  required properties (`name`/`description`/`thumbnailUrl`/`uploadDate`), thumbnail,
  key-moments (`Clip`/`SeekToAction`); recommends a video sitemap.
- **E-commerce merchant depth** (extends `modules/ecommerce.py`) — GTIN/MPN/SKU,
  shipping info, return/refund policy, out-of-stock schema alignment, related/cross-sell links.
- SKILL.md §1.20–1.23; 22 modules; 34 new tests (744 total). Schema-policy nuances and
  Google Discover readiness documented as agent-judgement checks.

## [2.4.0] - 2026-06-29

### Added — the modern ranking layer (grounded in Google guidance + the 2024 leak)
- **E-E-A-T & Trust module** (`modules/eeat.py`, always-on, from-afar) — audits
  authorship (visible byline, author page, `author`/`Person` schema), trust pages
  (About/Contact/Privacy/editorial), Organization entity (`logo`/`sameAs`/`contactPoint`),
  reachability (phone/email/address), and transparency (outbound citations, affiliate
  disclosure, "reviewed by"/fact-check for YMYL).
- **AI Search / GEO module** (`modules/ai_search.py`, always-on) — reports the
  AI-crawler posture in robots.txt for GPTBot, OAI-SearchBot, Google-Extended,
  PerplexityBot, ClaudeBot, CCBot, Bytespider, Amazonbot, Applebot-Extended, etc.
  (a blanket `Disallow` is flagged P1 — the #1 cause of AI-search invisibility),
  plus `llms.txt`, extraction-readiness, and entity clarity.
- **Technical SEO depth module** (`modules/technical_seo.py`, always-on) —
  `X-Robots-Tag` header noindex (P0; the meta-only check misses it), canonical
  host/scheme consistency, meta-refresh redirects, intrusive-interstitial heuristics,
  next-gen image formats + explicit width/height (CLS).
- **GSC behavioural analysis** (`scripts/gsc.py`) — turns a Search Console export
  (via the GSC MCP/API/CSV) into the NavBoost-proxy signals a URL-only audit can't
  see: striking-distance keywords, low-CTR-at-good-position (vs a positional CTR
  benchmark), impressions-with-no-clicks, and branded share. Emits report-compatible
  `opportunity_keywords`.
- SKILL.md §1.17–1.19 + a GSC collection workflow; 41 new tests (710 total).

## [2.3.0] - 2026-06-29

### Added
- **From-afar schema advisor** (`scripts/suggest_schema.py`) — classifies any live
  page (home / contact / article / **PDP** / **PLP** / FAQ / local business) from
  its HTML alone and generates **ready-to-paste JSON-LD**, pre-filled with scraped
  signals (business name, phone, address, social `sameAs`, price, currency,
  availability, ratings) and `REPLACE_*` placeholders for the rest. No codebase
  access required.
  - Recommends Organization/LocalBusiness, WebSite (+SearchAction), BreadcrumbList,
    Article/BlogPosting, **Product** (offers/brand/sku/aggregateRating), **ItemList**,
    and **FAQPage** (built from on-page `<details>` Q&A).
  - PDPs get a **`merchant_listing`** readiness checklist (price, currency,
    availability, image, rating, Product schema) for Google Merchant / rich-result
    eligibility.
  - 18 tests; `--format html` emits copy-paste `<script type="application/ld+json">`.
- **Remote / From-Afar Mode** in SKILL.md: URL is now the *only* required input.
  Tech stack and hosting are optional and inferred from response headers / generator
  meta / asset paths; when the stack is unknown, fixes are delivered stack-agnostic
  (the HTML/JSON-LD/header to paste) rather than framework file edits.

### Fixed
- `_meta` extraction now uses a quote backreference so values containing the other
  quote character (e.g. `content="Joe's Plumbing"`) are captured in full.

## [2.2.1] - 2026-06-29

### Fixed
- **Plugin failed to load** under current Claude Code: the `skills` entry in
  `plugin.json` pointed at the `SKILL.md` file, but skills entries must point at
  the **directory** containing `SKILL.md`. Changed `./skills/fat-agent/SKILL.md`
  → `./skills/fat-agent`. The plugin now loads cleanly.

## [2.2.0] - 2026-06-29

### Added
- **Actionable SEMrush report insight** — `generate-report.py` now renders **SEO
  Priority Opportunities**, **Keyword Cannibalisation**, and **Recommended Action
  Plan** sections in the Word/PowerPoint output, driven by `opportunity_keywords`,
  `cannibalization`, and `action_plan` fields (also accepted via an `--actions`
  file or `scores["recommendations"]`). SKILL.md "Turn the data into INSIGHT"
  documents how to compute them.
- PPTX charts are now **aspect-ratio preserved** (fit-to-box, centred) instead of
  stretched. `generate-charts.py` updated to match.

### Changed
- **`spruikco/fat-agent-skill` is now the single canonical home for FAT Agent.**
  The SEMrush enrichment and render-gap work (2.1.0) and the actionable-reports
  work (previously developed in parallel) are unified in this repository.

## [2.1.0] - 2026-06-29

### Added
- **Render-gap crawlability check** for SPAs. `analyse-html.py --served <shell.html>`
  compares the raw server response against the browser-rendered DOM and emits a
  `render_gap` block (content/title/meta-description/canonical/H1/structured-data
  `*_client_only` flags + severity).
- **Crawlability penalty** in `calculate-score.py`: when key SEO signals exist
  only after client-side rendering, the SEO score is penalised so the headline
  number reflects what non-rendering crawlers (Bing, social bots, Google before
  render) actually receive — instead of the best-case JS render.
- **Generic SPA detection**: client-rendered shells with no framework-specific
  marker are now detected via mount nodes (`#root`/`#app`) and ES-module bundles
  (e.g. Vite's `/assets/index-*.js`) combined with a near-empty served `<body>`.
- 15 tests covering generic SPA detection, render-gap computation, and the
  crawlability penalty (including the never-negative-score guard).
- **Optional SEMrush API enrichment** (`scripts/semrush.py`). When a SEMrush API
  key is available, pulls domain authority, organic keywords/traffic, the
  historical trend, and top keyword positions, and emits a `semrush.json` in the
  shape the chart/report scripts already consume. The key is read from the
  `SEMRUSH_API_KEY` environment variable (or `--api-key`) — never hardcoded,
  never written to output, and redacted from all error messages. Falls back to
  SEMrush MCP or browser automation, and skips cleanly when no source is present.
- `references/semrush-integration.md` and `.env.example` documenting the optional
  `SEMRUSH_API_KEY` setup (bring-your-own-key).
- 21 tests for the SEMrush integration (parsing, schema, key redaction, graceful
  degradation) — no network calls, no real key.

### Changed
- SKILL.md §1.2 SPA guidance rewritten to require the render-gap check on every
  SPA and to branch severity on site type (SEO-dependent → P0/P1; app-behind-auth
  → low/ignore).
- SKILL.md "SEMrush Data Collection" rewritten with a key/MCP/browser priority
  order; SEMrush enrichment is explicitly optional and off by default.

## [2.0.0] - 2026-04-14

### Added
- Modular audit system with 7 conditional modules (Local SEO, E-commerce, Email Deliverability, i18n, Link Checker, DNS & Infrastructure, JS Bundle Analysis)
- Module auto-detection from HTML signals
- Audit profiles (quick, full, local, ecommerce, seo, security)
- Multi-page BFS crawler with robots.txt support
- Bulk site auditing from JSON site lists
- Self-contained HTML dashboard report
- Client-facing mode (jargon to plain English)
- CI/CD quality gate script
- Lighthouse CLI integration
- Visual regression screenshot comparison
- Remix and Docker platform references
- 322 tests across 17 test files
- GitHub Actions CI (lint + test on Python 3.10/3.11/3.12)
- pyproject.toml with uv support
- black + ruff formatting

### Changed
- Renamed from fat-agent to fat-agent
- SKILL.md rewritten with Phase 0 module detection and profile selection
- analyse-html.py and calculate-score.py updated with --modules and --profile flags

## [1.2.0] - 2026-03-27

### Added
- Initial fat-agent release
- Core audit: SEO, Security, Accessibility, Performance
- Word and PowerPoint report generation
- SVG badge generator
- Historical audit tracking
- Competitive analysis mode
