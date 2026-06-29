# 🍔 FAT Agent with Superpowers — Fix, Audit, Test

![FAT Score](./fat-badge.svg)
[![CI](https://github.com/spruikco/fat-agent-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/spruikco/fat-agent-skill/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-630%2B%20passing-brightgreen)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**A modular Claude plugin that acts as your post-launch QA engineer.**

FAT Agent systematically audits deployed websites across SEO, security, accessibility, performance, local SEO, e-commerce, email deliverability, internationalisation, DNS infrastructure, and more — then walks you through fixing every issue found.

---

## What It Does

After you deploy a site, say **"run FAT agent"** and it will:

1. **Gather context** — Asks about your site, stack, and critical user flows
2. **Auto-detect modules** — Analyses your HTML for e-commerce, local business, i18n, and email signals
3. **Audit** — Runs core + detected modules against your live URL
4. **Report** — Generates a prioritised punch list, HTML dashboard, and shareable reports
5. **Fix** — Offers to generate code fixes for every issue found
6. **Re-test** — After you redeploy, verifies the fixes are live

### Core Modules (always enabled)

| Module | What It Checks |
|--------|----------------|
| 🔍 SEO | Title, meta, headings, OG tags, structured data, sitemap, robots.txt, CWV |
| 🔒 Security | HSTS, CSP, X-Frame-Options, Referrer-Policy, mixed content |
| ♿ Accessibility | Alt text, labels, landmarks, ARIA, skip links, focus, motion, zoom |
| ⚡ Performance | HTML size, render-blocking scripts, lazy loading, resource hints, fonts |

### Conditional Modules (auto-detected or user-selected)

| Module | Trigger Signal | What It Checks |
|--------|---------------|----------------|
| 📍 Local SEO | LocalBusiness schema, Google Maps, tel: links | NAP, GBP, service area, trust signals, CTAs |
| 🛒 E-commerce | Product schema, cart elements | Product schema validation, payment badges, breadcrumbs |
| 📧 Email Deliverability | Contact forms with email inputs | SPF, DKIM, DMARC records |
| 🌐 i18n | hreflang tags, language switcher | Hreflang validation, x-default, RTL support, lang attribute |
| 🔗 Link Checker | Always available | Internal/external links, broken anchors, noopener, mailto validation |
| 🛰️ DNS & Infrastructure | Opt-in | DNSSEC, CAA, SSL expiry, CDN detection, HTTP/2 |
| 📦 JS Bundle Analysis | Script tags detected | Heavy libraries, async/defer, module scripts, bundle patterns |

Plus Content Quality, GDPR/Cookie consent, Schema validation, and Sitemap modules.

### Audit Profiles

| Profile | Modules |
|---------|---------|
| `quick` | SEO, Security |
| `full` | All modules |
| `local` | SEO, Security, A11y, Perf, Local SEO, Email, Links |
| `ecommerce` | SEO, Security, A11y, Perf, E-commerce, Links |
| `seo` | SEO only |
| `security` | Security only |

---

## Installation

### Claude Code Plugin (Recommended)

```
/plugin marketplace add spruikco/fat-agent-skill
/plugin install fat-agent@fat-agent-marketplace
```

This installs the FAT Agent plugin with the `/fat-audit` slash command. Already installed an
earlier version? Run `/plugin update` to pull the latest superpowers.

### Claude Code (Manual)

```bash
git clone https://github.com/spruikco/fat-agent-skill ~/.claude/skills/fat-agent
```

Claude Code reads `SKILL.md` automatically and activates the skill when it detects trigger phrases.

Then in any conversation:
```
You: Run FAT agent on https://mysite.com
You: Audit my site
You: I just deployed — is everything working?
You: Audit my site with the local business profile
You: /fat-audit https://example.com
```

### Claude.ai (Projects)

1. Create a new **Project** in Claude.ai
2. Upload `plugins/fat-agent/skills/fat-agent/SKILL.md` as a project file — this is the core instruction set Claude follows
3. Upload the reference files you want available (security headers, SEO checklist, accessibility guide, and any relevant `platform-fixes/` or `framework-fixes/` for your stack)
4. Start a conversation and say "audit my site" or "run FAT agent"

> **Note:** The Python scripts are designed for Claude Code, which executes them directly. Claude.ai performs the same checks conversationally using `web_fetch`.

### Works With Any Hosting Platform

FAT Agent is **platform-agnostic** — it audits the live URL regardless of where it's hosted: Netlify, Vercel, Cloudflare Pages, AWS, DigitalOcean, shared hosting, self-hosted Nginx/Apache, WordPress hosting, or anything that serves a URL.

---

## Superpowers

### Multi-Page Crawling

```bash
python plugins/fat-agent/scripts/crawl.py --url https://example.com --depth 2 --max-pages 10 --output-dir /tmp/crawl
```

Breadth-first crawler with robots.txt support, same-domain filtering, and optional link checking.

### Bulk Site Auditing

```bash
python plugins/fat-agent/scripts/bulk_audit.py --sites sites.json --output-dir /tmp/bulk --profile quick
```

Audit multiple sites from a JSON list with a comparison table output.

### HTML Dashboard

```bash
python plugins/fat-agent/scripts/generate_html_dashboard.py --scores scores.json --url example.com --output-dir ./reports
```

Self-contained HTML report with colour-coded grades, progress bars, and a findings table. Supports `--client-facing` mode for non-technical stakeholders.

### Lighthouse Integration

```bash
python plugins/fat-agent/scripts/lighthouse.py --url https://example.com --output /tmp/lighthouse.json
```

Wraps the Lighthouse CLI for accurate Core Web Vitals. Falls back gracefully when not installed.

### Visual Regression

```bash
python plugins/fat-agent/scripts/visual_regression.py --url https://example.com --output-dir .fat-screenshots
```

Screenshot comparison across viewports using Playwright (with fallback).

### CI/CD Gate

```bash
python plugins/fat-agent/scripts/ci_gate.py --scores scores.json --threshold 70 --fail-on P0
```

Exit codes: `0` = pass, `1` = score below threshold, `2` = priority findings found.

### Client-Facing Mode

Transforms technical jargon into plain English for non-technical stakeholders — e.g. "HSTS" becomes "browser security header", "P0 Critical" becomes "Urgent", and code blocks are stripped from fix suggestions.

### Competitive Analysis

Say "compare my site with [competitor URL]" for a side-by-side score comparison with actionable improvement suggestions.

### SEMrush Enrichment (optional)

If you have a SEMrush API key, FAT Agent layers in real domain authority, organic keyword/traffic figures, historical trends, and top keyword positions:

```bash
python plugins/fat-agent/scripts/semrush.py --domain example.com --database au --output /tmp/semrush.json
```

**Bring your own key** — the script reads it from the `SEMRUSH_API_KEY` environment variable (never hardcoded, never written to output, redacted from all errors). No key, no problem: the audit runs fully without it. A connected SEMrush MCP server or browser automation also work as sources. See [`references/semrush-integration.md`](plugins/fat-agent/references/semrush-integration.md).

### The modern ranking layer (E-E-A-T, AI search, behavioural)

Beyond the classic technical audit, FAT Agent checks what 2026 Google ranking actually weights — grounded in Google's guidance and the 2024 Content Warehouse leak:

- **E-E-A-T & Trust** — author bylines/bio + `Person` schema, trust pages (About/Contact/Privacy/editorial), Organization entity + `sameAs`, outbound citations, disclosures. *Anonymity is a ranking liability.*
- **AI Search / GEO** — flags your **AI-crawler posture** in `robots.txt` (GPTBot, OAI-SearchBot, Google-Extended, PerplexityBot, ClaudeBot, CCBot…) so a blanket `Disallow` isn't silently keeping you out of AI Overviews/ChatGPT/Perplexity; checks `llms.txt`, extraction-readiness, entity clarity.
- **Technical depth** — `X-Robots-Tag` header noindex, canonical host/scheme consistency, intrusive interstitials, next-gen images + CLS dimensions.
- **GSC behavioural (NavBoost proxy)** — feed a Search Console export to `scripts/gsc.py` for striking-distance keywords, low-CTR-at-good-position, and branded share — the click signals a URL-only audit can't see.
- **Crawl & content depth** — robots-blocks-CSS/JS, JS-only nav, faceted-URL sprawl, redirect chains/loops + soft-404 (`scripts/redirects.py`), YMYL/ad-density/originality/freshness, plus Video SEO and deeper e-commerce merchant checks (GTIN, shipping/returns, out-of-stock schema).

### Schema Suggestions — from afar, no codebase needed

FAT Agent can audit **any live URL** (yours, a client's, a prospect's) with zero repo access. It classifies each page — home, article, **product (PDP)**, **listing (PLP)**, FAQ, local business — and generates **ready-to-paste JSON-LD**, pre-filled from the live page:

```bash
python plugins/fat-agent/scripts/suggest_schema.py --fetch --url https://example.com --format html
```

Recommends Organization/LocalBusiness (with NAP + `sameAs`), Product (offers, brand, `aggregateRating` — the fields Google needs for **rich results and free Merchant listings**), ItemList, Article, FAQPage, and BreadcrumbList — with a per-PDP **Merchant-listing readiness checklist**. Stack and hosting are optional and auto-inferred; when unknown, fixes are delivered as stack-agnostic snippets.

---

## The FAT Report

Issues are prioritised with clear labels:

| Priority | Label | Meaning |
|----------|-------|---------|
| 🔴 P0 | **Critical** | Site is broken, inaccessible, or insecure |
| 🟠 P1 | **High** | Significant SEO, performance, or UX impact |
| 🟡 P2 | **Medium** | Best practice violations, minor issues |
| 🟢 P3 | **Low** | Nice-to-haves, polish items |

Each finding includes what's wrong, why it matters, how to fix it, and an effort estimate (⚡ 5 min, 🔧 30 min, 🏗️ 1+ hour).

---

## Scoring

| Category | Weight |
|----------|--------|
| SEO | 30% |
| Security | 25% |
| Accessibility | 30% |
| Performance | 15% |

Module scores (Local SEO, E-commerce, etc.) are reported separately as supplementary scores.
Grades: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, F < 60.

### FAT Badge

Generate shields.io-style SVG badges from your audit scores:

```bash
python plugins/fat-agent/scripts/analyse-html.py page.html \
  | python plugins/fat-agent/scripts/calculate-score.py \
  | python plugins/fat-agent/scripts/generate-badge.py --output badge.svg
```

Then embed in your README:
```markdown
![FAT Score](./badge.svg)
```

---

## Project Structure

The repo root is the marketplace; the plugin lives under `plugins/fat-agent/`:

- **skills/fat-agent/SKILL.md** — Core skill instructions (the orchestration guide)
- **commands/fat-audit.md** — `/fat-audit` slash command definition
- **scripts/** — Python analysis pipeline (`analyse-html.py`, `calculate-score.py`, `crawl.py`, `bulk_audit.py`, `lighthouse.py`, `pagespeed.py`, `visual_regression.py`, `ci_gate.py`, `client_facing.py`, `profiles.py`, badge/chart/report/dashboard generators)
  - **scripts/modules/** — Audit modules (local_seo, ecommerce, email_deliverability, i18n, links, dns_infra, js_bundle, content_quality, cookie_gdpr, pwa, schema_validator, sitemap, plus core SEO/security/accessibility/performance) with a base class and registry
- **templates/** — HTML dashboard template and CSS
- **references/** — Security headers, SEO checklist, accessibility guide, performance budgets, CI/CD integration, local SEO & e-commerce checklists
  - **platform-fixes/** — Netlify, Vercel, Cloudflare Pages, Apache, Nginx, WordPress, AWS, Docker
  - **framework-fixes/** — Next.js, Astro, SvelteKit, Nuxt, Gatsby, Remix, WordPress, Static HTML
- **tests/** — 630 tests across 17 test files with fixtures
- **evals/** — Skill evaluation test cases
- **assets/** — Brand images

---

## Testing

```bash
cd plugins/fat-agent
python3 -m pytest tests/ -v
```

630 tests covering all modules, the registry, crawler, bulk audit, Lighthouse, visual regression, dashboard, CI gate, client-facing transforms, and profiles.

---

## Credits

Built by [Spruik Co](https://spruik.co) — Digital Marketing & SEO Consultancy.
Designed as a Claude Agent Skill for post-launch quality assurance.

---

## License

MIT — see [LICENSE](LICENSE) for details.
