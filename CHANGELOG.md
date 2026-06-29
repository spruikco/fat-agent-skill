# Changelog

## [Unreleased]

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

### Changed
- SKILL.md §1.2 SPA guidance rewritten to require the render-gap check on every
  SPA and to branch severity on site type (SEO-dependent → P0/P1; app-behind-auth
  → low/ignore).

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
