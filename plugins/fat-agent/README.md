# FAT Agent Plugin

**FAT Agent (Fix, Audit, Test)** — a Claude Code plugin that acts as your post-launch QA engineer.

## What It Does

Systematically audits deployed websites for SEO, security, accessibility, performance, and content issues. Generates a prioritised punch list with specific fixes tailored to your tech stack and hosting platform.

## Trigger Phrases

The skill activates when you say things like:
- "Run FAT agent"
- "Audit my site"
- "Post-launch check"
- "Check my deployment"
- "QA my site"
- "Is everything working?"

## Slash Command

```
/fat-audit https://example.com
```

Runs the full audit workflow with the provided URL.

## Audit Categories

| Category | What It Checks |
|----------|----------------|
| Availability & Response | HTTP status, redirects, response headers, caching |
| SEO Essentials | Title, meta, headings, OG tags, structured data, sitemap, robots.txt |
| Performance | HTML size, render-blocking scripts, lazy loading, resource hints |
| Security Headers | HSTS, CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy |
| Accessibility | Alt text, labels, landmarks, skip links |
| Functional Checks | Forms, navigation, mobile, 404 page, integrations |
| Content & Legal | Placeholder text, privacy policy, copyright year |
| Analytics & Tracking | GA4, GTM, Facebook Pixel, and more |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/analyse-html.py` | HTML analysis — extracts meta tags, headers, scripts |
| `scripts/calculate-score.py` | Scoring calculator (SEO, Security, A11y, Performance, FAT) |
| `scripts/generate-badge.py` | SVG badge generator with character image and score bars |
| `scripts/test_fat_agent.py` | Full test suite (201 tests) |

## References

- `references/security-headers.md` — Full security header recommendations
- `references/seo-checklist.md` — Extended SEO audit criteria
- `references/accessibility-guide.md` — WCAG 2.1 quick reference
- `references/platform-fixes/` — Hosting platform config guides (Netlify, Vercel, Cloudflare, Apache, Nginx, WordPress, AWS)
- `references/framework-fixes/` — Framework-specific fix patterns (Next.js, Astro, SvelteKit, Nuxt, Gatsby, WordPress, static HTML)

## Testing

```bash
python scripts/test_fat_agent.py
```

All scripts use Python stdlib only — no pip dependencies required. Python 3.8+.
