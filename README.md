# 🍔 FAT Agent — Fix, Audit, Test

![FAT Score](./fat-badge.svg)

**A Claude plugin that acts as your post-launch QA engineer.**

FAT Agent systematically audits deployed websites for SEO, performance, security, accessibility, and content issues — then walks you through fixing every one.

---

## What It Does

After you deploy a site, say **"run FAT agent"** and it will:

1. **Gather context** — Asks smart questions about your site, stack, and critical user flows
2. **Audit** — Runs 8 automated check categories against your live URL
3. **Report** — Generates a prioritised punch list (P0 Critical → P3 Nice-to-have)
4. **Fix** — Offers to generate code fixes for every issue found
5. **Re-test** — After you redeploy, verifies the fixes are live

### Audit Categories

| Category | Automated? | What It Checks |
|----------|-----------|----------------|
| 🌐 Availability & Response | ✅ | HTTP status, redirects, response headers, caching |
| 🔍 SEO Essentials | ✅ | Title, meta, headings, OG tags, structured data, sitemap, robots.txt |
| ⚡ Performance | ✅ | HTML size, render-blocking scripts, lazy loading, resource hints |
| 🔒 Security Headers | ✅ | HSTS, CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy |
| ♿ Accessibility | Partial | Alt text, labels, landmarks, skip links + targeted user questions |
| 🧪 Functional Checks | 👤 User | Forms, navigation, mobile, 404 page, integrations |
| 📝 Content & Legal | Partial | Placeholder text, privacy policy, copyright year |
| 📊 Analytics & Tracking | ✅ | GA4, GTM, Facebook Pixel, Plausible, Hotjar |

---

## Installation

### Claude Code Plugin (Recommended)

```bash
claude plugins add https://github.com/spruikco/fat-agent-skill
```

This installs the FAT Agent plugin with the `/fat-audit` slash command.

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
You: Post-launch check on https://example.com
You: /fat-audit https://example.com
```

### Claude.ai (Projects)

1. Create a new **Project** in Claude.ai
2. Upload `plugins/fat-agent/skills/fat-agent/SKILL.md` as a project file — this is the core instruction set Claude follows
3. Upload the reference files you want available:
   - `plugins/fat-agent/references/security-headers.md`
   - `plugins/fat-agent/references/seo-checklist.md`
   - `plugins/fat-agent/references/accessibility-guide.md`
   - Any relevant `plugins/fat-agent/references/platform-fixes/*.md` for your hosting platform
   - Any relevant `plugins/fat-agent/references/framework-fixes/*.md` for your tech stack
4. Start a conversation and say "audit my site" or "run FAT agent"

> **Note:** The Python scripts (`analyse-html.py`, `calculate-score.py`) are designed for Claude Code, which can execute them directly. Claude.ai performs the same checks conversationally using `web_fetch`.

### What Happens When You Trigger It

1. **Phase 0 — Context** — FAT Agent asks for your live URL, site type, tech stack, and hosting platform
2. **Phase 1 — Audit** — Fetches your URL, runs 9 check categories (SEO, security, accessibility, performance, analytics, content, functional, platform-specific), asks targeted yes/no questions for things that can't be automated
3. **Phase 2 — Fix** — Generates a prioritised punch list (P0 Critical → P3 Low) with specific code/config fixes tailored to your stack and hosting platform
4. **Phase 3 — Test** — After you redeploy with fixes, re-fetches the URL and verifies each issue is resolved

Fix suggestions are loaded on-demand from the `references/platform-fixes/` and `references/framework-fixes/` directories based on what you told it in Phase 0. A Next.js site on Vercel gets different fix code than a WordPress site on Apache.

### Works With Any Hosting Platform

FAT Agent is **platform-agnostic**. It audits the live URL regardless of where it's hosted:

- Netlify, Vercel, Cloudflare Pages
- AWS (S3, CloudFront, Amplify, EC2)
- DigitalOcean, shared hosting (cPanel, Plesk)
- Self-hosted (Nginx, Apache)
- WordPress hosting (WP Engine, Kinsta, etc.)
- Any platform that serves a URL

---

## Project Structure

```
fat-agent-skill/                          # Marketplace root
├── .claude-plugin/
│   └── marketplace.json                  # Marketplace manifest
├── plugins/
│   └── fat-agent/                        # The plugin
│       ├── .claude-plugin/
│       │   └── plugin.json               # Plugin manifest
│       ├── skills/
│       │   └── fat-agent/
│       │       └── SKILL.md              # Core skill instructions
│       ├── commands/
│       │   └── fat-audit.md              # /fat-audit slash command
│       ├── scripts/
│       │   ├── analyse-html.py           # HTML analysis helper
│       │   ├── calculate-score.py        # Scoring calculator (SEO, Security, A11y, FAT)
│       │   ├── generate-badge.py         # SVG badge generator for READMEs
│       │   └── test_fat_agent.py         # Full test suite (201 tests)
│       ├── references/
│       │   ├── security-headers.md       # Security header reference
│       │   ├── seo-checklist.md          # Extended SEO criteria
│       │   ├── accessibility-guide.md    # WCAG 2.1 quick reference
│       │   ├── platform-fixes/           # Hosting platform config guides
│       │   │   ├── netlify.md
│       │   │   ├── vercel.md
│       │   │   ├── cloudflare-pages.md
│       │   │   ├── apache.md
│       │   │   ├── nginx.md
│       │   │   ├── wordpress.md
│       │   │   └── aws.md
│       │   └── framework-fixes/          # Framework-specific fix patterns
│       │       ├── nextjs.md
│       │       ├── astro.md
│       │       ├── sveltekit.md
│       │       ├── nuxt.md
│       │       ├── gatsby.md
│       │       ├── wordpress.md
│       │       └── static-html.md
│       ├── evals/
│       │   └── evals.json                # Test cases for skill validation
│       ├── assets/
│       │   ├── fat-agent-badge-icon.png
│       │   └── social-preview.png
│       └── README.md                     # Plugin documentation
├── fat-badge.svg                         # Generated FAT score badge
├── README.md                             # This file
├── CLAUDE.md                             # Project conventions for Claude Code
├── LICENSE                               # MIT License
├── .gitignore
└── .github/
    └── LLM-BRIEF.md                     # Project brief for LLM continuation
```

---

## Usage Examples

### Basic Audit
```
User: Run FAT agent on https://mysite.com
Claude: Ready to run a FAT audit! I just need a few details...
```

### Post-Deploy Check
```
User: I just deployed. Is everything working?
Claude: Let me run a FAT audit on your site to check...
```

### Targeted Audit
```
User: Can you check the SEO on my new landing page?
Claude: I'll focus the FAT audit on SEO — fetching your page now...
```

### Slash Command
```
User: /fat-audit https://mysite.com
Claude: Running FAT Agent audit on https://mysite.com...
```

---

## The FAT Report

Issues are prioritised with clear labels:

| Priority | Label | Meaning |
|----------|-------|---------|
| 🔴 P0 | **Critical** | Site is broken, inaccessible, or insecure |
| 🟠 P1 | **High** | Significant SEO, performance, or UX impact |
| 🟡 P2 | **Medium** | Best practice violations, minor issues |
| 🟢 P3 | **Low** | Nice-to-haves, polish items |

Each finding includes:
- **What's wrong** — One-line description
- **Why it matters** — Impact explanation
- **How to fix** — Specific code/config changes
- **Effort** — ⚡ 5 min, 🔧 30 min, or 🏗️ 1+ hour

---

## Scoring

FAT Agent generates scores across four dimensions:

- **SEO Score** (0-100) — Based on meta tags, headings, structured data, sitemap, etc.
- **Security Score** (0-100) — Based on presence and correctness of security headers
- **Accessibility Score** (0-100) — Based on automated checks + user-reported items
- **Performance Score** (0-100) — Based on HTML size, render-blocking scripts, images, fonts, lazy loading
- **Overall FAT Score** — Weighted composite (SEO 30%, Security 25%, A11y 30%, Perf 15%)

### FAT Badge

Generate shields.io-style SVG badges from your audit scores:

```bash
# Overall FAT badge (grade + score)
python plugins/fat-agent/scripts/analyse-html.py page.html | python plugins/fat-agent/scripts/calculate-score.py | python plugins/fat-agent/scripts/generate-badge.py --output badge.svg

# Category badges
python plugins/fat-agent/scripts/generate-badge.py scores.json --category seo --output seo-badge.svg
python plugins/fat-agent/scripts/generate-badge.py scores.json --category security --output security-badge.svg
python plugins/fat-agent/scripts/generate-badge.py scores.json --category accessibility --output a11y-badge.svg
python plugins/fat-agent/scripts/generate-badge.py scores.json --category performance --output perf-badge.svg

# Flat-square style
python plugins/fat-agent/scripts/generate-badge.py scores.json --style flat-square --output badge.svg
```

Then embed in your README:
```markdown
![FAT Score](./badge.svg)
```

---

## Customisation

### Adding Check Categories

Edit `plugins/fat-agent/skills/fat-agent/SKILL.md` to add new audit sections. Follow the existing pattern:
1. Add the check to the appropriate phase
2. Specify whether it's automated or user-prompted
3. Define the priority level for findings
4. Add fix templates

### Extending References

Drop additional `.md` files in `plugins/fat-agent/references/` and reference them from `SKILL.md`.

---

## Contributing

PRs welcome! Areas that could use help:

- [ ] More comprehensive accessibility checks
- [ ] Performance budget configuration
- [ ] CI/CD integration examples
- [ ] Additional analytics provider detection
- [x] FAT Badge generator (SVG score badge for READMEs)
- [ ] Historical audit tracking (compare scores over time)
- [ ] Competitive analysis mode (audit two sites side-by-side)

---

## Credits

Built by [Spruik Co](https://spruik.co) — Digital Marketing & SEO Consultancy.

Designed as a Claude Agent Skill for post-launch quality assurance.

---

## License

MIT — see [LICENSE](LICENSE) for details.
