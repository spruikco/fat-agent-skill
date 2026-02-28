# 🍔 FAT Agent — Fix, Audit, Test

**A Claude skill that acts as your post-launch QA engineer.**

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

### As a Claude Skill (Claude.ai / Claude Code)

1. Download or clone this repository
2. Place the `fat-agent-skill` folder in your skills directory:
   - **Claude Code**: `~/.claude/skills/fat-agent/`
   - **Claude.ai**: Upload as a project skill
3. The skill auto-triggers on phrases like "audit my site", "post-launch check", "run FAT agent"

### Works With Any Hosting Platform

FAT Agent is **platform-agnostic**. It audits the live URL regardless of where it's hosted:

- Netlify
- Vercel
- Cloudflare Pages
- AWS (S3, Amplify, EC2)
- DigitalOcean
- Shared hosting (cPanel, Plesk)
- Self-hosted (Nginx, Apache)
- WordPress hosting (WP Engine, Kinsta, etc.)
- Any platform that serves a URL

Fix suggestions are automatically tailored to your hosting platform and tech stack.

---

## Project Structure

```
fat-agent-skill/
├── SKILL.md                          # Core skill instructions
├── README.md                         # This file
├── LICENSE                           # MIT License
├── CLAUDE.md                         # Project conventions for Claude Code users
├── .gitignore
├── scripts/
│   ├── analyse-html.py              # HTML analysis helper
│   └── calculate-score.py           # Scoring calculator (SEO, Security, A11y, FAT)
├── references/
│   ├── security-headers.md          # Security header reference
│   ├── seo-checklist.md             # Extended SEO criteria
│   ├── accessibility-guide.md       # WCAG 2.1 quick reference
│   ├── platform-fixes/             # Hosting platform config guides
│   │   ├── netlify.md
│   │   ├── vercel.md
│   │   ├── cloudflare-pages.md
│   │   ├── apache.md
│   │   ├── nginx.md
│   │   ├── wordpress.md
│   │   └── aws.md
│   └── framework-fixes/            # Framework-specific fix patterns
│       ├── nextjs.md
│       ├── astro.md
│       ├── sveltekit.md
│       ├── nuxt.md
│       ├── gatsby.md
│       ├── wordpress.md
│       └── static-html.md
├── assets/                          # Templates and static assets
├── evals/
│   └── evals.json                   # Test cases for skill validation
└── .github/
    └── LLM-BRIEF.md                # Project brief for LLM continuation
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
- **Overall FAT Score** — Weighted composite + percentage of issues resolved

---

## Customisation

### Adding Check Categories

Edit `SKILL.md` to add new audit sections. Follow the existing pattern:
1. Add the check to the appropriate phase
2. Specify whether it's automated or user-prompted
3. Define the priority level for findings
4. Add fix templates

### Extending References

Drop additional `.md` files in `references/` and reference them from `SKILL.md`.

---

## Contributing

PRs welcome! Areas that could use help:

- [ ] More comprehensive accessibility checks
- [ ] Performance budget configuration
- [ ] CI/CD integration examples
- [ ] Additional analytics provider detection
- [ ] FAT Badge generator (SVG score badge for READMEs)
- [ ] Historical audit tracking (compare scores over time)
- [ ] Competitive analysis mode (audit two sites side-by-side)

---

## Credits

Built by [Spruik Co](https://spruik.co) — Digital Marketing & SEO Consultancy.

Designed as a Claude Agent Skill for post-launch quality assurance.

---

## License

MIT — see [LICENSE](LICENSE) for details.
