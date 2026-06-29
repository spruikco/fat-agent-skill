# Changelog

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
