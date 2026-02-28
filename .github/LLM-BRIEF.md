# FAT Agent — Project Brief for LLM Continuation

## What This Project Is

FAT Agent (Fix, Audit, Test) is a **Claude Skill** — a reusable instruction set that Claude reads when triggered, giving it a structured workflow to follow. Think of it as a specialist personality/playbook that activates when a user says things like "audit my site" or "run FAT agent".

The skill turns Claude into a **post-launch QA engineer**. After someone deploys a website, FAT Agent systematically checks everything that matters (SEO, security, accessibility, performance, content, analytics) and builds a prioritised punch list of issues with specific fixes. It then guides the user through resolving each issue and re-verifies after redeployment.

## How Claude Skills Work

A skill is a folder with this structure:

```
skill-name/
├── SKILL.md          ← The core file. Claude reads this when the skill triggers.
│                       Has YAML frontmatter (name + description for triggering)
│                       and markdown body (the actual instructions).
├── scripts/          ← Helper scripts Claude can execute
├── references/       ← Deep-dive docs Claude reads when needed
├── assets/           ← Templates, icons, etc.
└── evals/            ← Test cases to validate the skill works
```

The `description` field in SKILL.md frontmatter is critical — it's what Claude uses to decide whether to activate the skill. It needs to be comprehensive and slightly "pushy" to avoid under-triggering.

## What's Been Built So Far

### ✅ Done

1. **SKILL.md** — Complete core skill with:
   - Phase 0: Context gathering (asks user for URL, site type, stack, critical flows)
   - Phase 1: AUDIT — 8 check categories (availability, SEO, performance, security, accessibility, functional, content/legal, analytics)
   - Phase 2: FIX — Prioritised report generation (P0 Critical → P3 Low) with fix code and effort estimates
   - Phase 3: TEST — Re-verification after fixes are deployed, final scorecard

2. **references/security-headers.md** — Full security header reference with Netlify-specific implementation examples

3. **references/seo-checklist.md** — Extended SEO audit criteria covering on-page, technical, social, and performance-impact-on-SEO checks with scoring guide

4. **references/accessibility-guide.md** — WCAG 2.1 quick reference split into HTML-checkable items vs user-prompted checks

5. **scripts/analyse-html.py** — Python HTML parser that extracts SEO, accessibility, performance, security, and content signals from raw HTML. Outputs a structured JSON report with auto-generated issue summaries by priority.

6. **evals/evals.json** — 5 test cases covering basic audit, contextual trigger, focused audit, punch list status, and re-verification

7. **README.md** — GitHub-ready documentation with usage examples, project structure, scoring explanation, and contribution guide

8. **LICENSE** — MIT

## What Needs to Be Finished / Improved

### High Priority

1. **The skill needs real-world testing.** Run it against 3-5 actual URLs and see where it falls short. The audit categories are comprehensive in theory but may need tuning for edge cases (SPAs that return minimal HTML, sites behind Cloudflare challenges, sites with heavy client-side rendering).

2. **Framework-specific fix templates.** Currently the fixes are generic HTML. Add targeted fix snippets for:
   - Next.js (App Router + Pages Router)
   - Astro
   - WordPress
   - Gatsby
   - SvelteKit
   - Nuxt
   - Plain HTML / Netlify static sites
   
   These should go in `references/framework-fixes/` with one file per framework, and SKILL.md should reference them based on the tech stack gathered in Phase 0.

3. **The analyse-html.py script doesn't capture `<title>` tag content properly.** It looks for a `<meta name="title">` which is non-standard. It needs to capture the text content inside `<title>...</title>` tags. The HTMLParser's `handle_data` method needs a branch for when `current_tag == "title"`.

4. **Platform-specific fix templates.** The skill asks for hosting platform in Phase 0. Fix suggestions need to be tailored per platform. The security-headers reference already covers Netlify, Vercel, Cloudflare Pages, Apache, Nginx, Next.js, and WordPress. Extend this pattern to other audit categories. Create `references/platform-fixes/` with one file per platform:
   - `netlify.md` — _headers, netlify.toml, Netlify Forms, Edge Functions
   - `vercel.md` — vercel.json, middleware, edge config
   - `cloudflare-pages.md` — _headers, _redirects, Workers
   - `apache.md` — .htaccess directives
   - `nginx.md` — server block config
   - `wordpress.md` — functions.php, plugin recommendations, wp-config.php
   - `aws.md` — CloudFront headers, S3 config, Amplify settings
   
   SKILL.md should reference these based on the hosting platform gathered in Phase 0.

5. **Platform-specific hosting checks.** Add a conditional audit section (1.9) that runs platform-aware checks based on what the user told us in Phase 0. Examples:
   - **Netlify**: `_headers` file, `_redirects`, Netlify Forms setup, deploy preview vs production
   - **Vercel**: `vercel.json` config, middleware, edge config
   - **Cloudflare Pages**: `_headers`, `_redirects`, Workers bindings
   - **WordPress**: wp-admin exposure, xmlrpc.php disabled, plugin update status
   - **Apache/Nginx**: .htaccess / server config best practices
   - **Generic**: SSL cert validity, www vs non-www consistency, custom domain config
   
   This section should be modular — only run the checks relevant to the declared platform.

### Medium Priority

6. **The scoring system is described but not implemented as a unified calculator.** Create a `scripts/calculate-score.py` that takes the JSON output from `analyse-html.py` and produces the four dimension scores (SEO, Security, Accessibility, Overall FAT Score) with the weightings defined in the reference docs.

7. **Add a config file generator per platform.** When security headers are missing, FAT Agent should offer to generate the complete config file for the user's specific platform (e.g., `_headers` for Netlify/Cloudflare, `vercel.json` for Vercel, `.htaccess` for Apache, etc.), not just show snippets.

8. **Add a "FAT Badge" generator.** After a site passes the audit, generate an SVG badge (like those shields.io badges) showing the FAT score that the user can add to their README or site footer. Fun gamification element.

9. **Internationalisation checks.** The accessibility guide mentions `hreflang` but the main audit flow doesn't check for it. Add i18n as a conditional check when the site serves multiple languages.

10. **Cookie/GDPR compliance checks.** Currently this is just a user-prompted "does your cookie banner appear?" — could be enhanced by checking for common consent management platforms (CookieBot, OneTrust, etc.) in the HTML.

### Low Priority / Nice-to-Have

11. **Historical tracking.** If FAT Agent is run multiple times on the same site, it would be great to show improvement over time. This would require persistent storage (maybe a JSON file the skill reads/writes).

12. **Competitive analysis mode.** "Run FAT agent on my site AND my competitor's site and compare." Would need to run the audit twice and present a side-by-side comparison.

13. **CI/CD integration guide.** A reference doc explaining how to run FAT Agent checks as part of a deploy pipeline (Netlify build plugins, GitHub Actions, etc.).

14. **A `.skill` package file.** The skill-creator tooling can package skills into installable `.skill` files. This would make distribution easier.

## Design Principles to Follow

- **Platform-agnostic first.** Every audit check should work on any hosted URL. Platform-specific advice is layered on top based on what the user tells us in Phase 0 — never assume a platform
- **Don't overwhelm the user.** Present findings in batches of 3-5, not a wall of 30 issues
- **Be specific.** "Your title is 84 characters" not "Your title might be too long"
- **Always offer to fix.** Don't just report — generate the actual code/config changes
- **Tailor fixes to BOTH the tech stack AND the hosting platform.** A Next.js-on-Vercel fix looks different from a Next.js-on-Netlify fix which looks different from a WordPress-on-Apache fix
- **Use ask_user_input tool** for bounded choices instead of open-ended questions
- **Quick wins first.** Sort by effort as well as priority — a 5-minute P2 fix is worth doing before a 2-hour P1 fix in many cases
- **Respect the user's time.** If they say "I only care about SEO", focus there
- **Celebrate progress.** When issues get resolved, acknowledge it. The final scorecard should feel rewarding.

## Technical Context

- This is a Claude Skill, NOT a standalone application
- Claude reads SKILL.md as instructions and follows them conversationally
- The skill uses Claude's built-in tools: `web_fetch` (to grab live URLs), `web_search` (to find PageSpeed results etc.), `ask_user_input` (for structured questions), and `bash_tool` (to run the Python scripts)
- The Python scripts are helpers that Claude executes, not user-facing CLI tools
- All reference docs are loaded by Claude on-demand when it needs deeper info on a specific category
- The skill is designed for Anthropic's Claude.ai / Claude Code environments

## Repository

```
fat-agent-skill/
├── SKILL.md                              # Core skill (complete)
├── README.md                             # GitHub docs (complete)  
├── LICENSE                               # MIT (complete)
├── LLM-BRIEF.md                          # This file — handoff doc for continuation
├── scripts/
│   ├── analyse-html.py                   # HTML analyser (needs title tag fix)
│   └── calculate-score.py                # Score calculator (TO BUILD)
├── references/
│   ├── security-headers.md               # Security reference (complete, multi-platform)
│   ├── seo-checklist.md                  # SEO reference (complete)
│   ├── accessibility-guide.md            # A11y reference (complete)
│   ├── platform-fixes/                   # Platform-specific fix templates (TO BUILD)
│   │   ├── netlify.md
│   │   ├── vercel.md
│   │   ├── cloudflare-pages.md
│   │   ├── apache.md
│   │   ├── nginx.md
│   │   ├── wordpress.md
│   │   └── aws.md
│   └── framework-fixes/                  # Framework-specific fixes (TO BUILD)
│       ├── nextjs.md
│       ├── astro.md
│       ├── wordpress.md
│       └── ...
├── assets/                               # (empty, for future badge generator etc.)
└── evals/
    └── evals.json                        # Test cases (complete, could expand)
```

**Important distinction:**
- `platform-fixes/` = hosting platform config (Netlify _headers, Vercel vercel.json, Apache .htaccess)
- `framework-fixes/` = application framework code (Next.js Head component, Astro layouts, WordPress functions.php)

## Who Made This

Built by Rye at Spruik Co (Adelaide, Australia) — a digital marketing and SEO consultancy. The skill leverages deep SEO and web development expertise to automate the post-launch QA process that agencies typically do manually.

---

**To the LLM reading this:** Pick up from the "What Needs to Be Finished" section. Start with the high-priority items. Read the existing files first to understand the patterns and conventions, then build the missing pieces to match. The voice should be practical and direct — this is a tool for professionals, not a tutorial.
