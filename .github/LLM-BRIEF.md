# FAT Agent — Project Brief for LLM Continuation

## What This Project Is

FAT Agent (Fix, Audit, Test) is a **Claude Plugin** distributed as a marketplace — a reusable instruction set that Claude reads when triggered, giving it a structured workflow to follow. Think of it as a specialist personality/playbook that activates when a user says things like "audit my site" or "run FAT agent".

The skill turns Claude into a **post-launch QA engineer**. After someone deploys a website, FAT Agent systematically checks everything that matters (SEO, security, accessibility, performance, content, analytics) and builds a prioritised punch list of issues with specific fixes. It then guides the user through resolving each issue and re-verifies after redeployment.

## How Claude Plugins Work

The repo is structured as a marketplace containing one plugin:

```
fat-agent-skill/                          # Marketplace root
├── .claude-plugin/
│   └── marketplace.json                  # Points to plugins
└── plugins/
    └── fat-agent/                        # The plugin
        ├── .claude-plugin/
        │   └── plugin.json              # Plugin manifest
        ├── skills/
        │   └── fat-agent/
        │       └── SKILL.md             # Core skill instructions (YAML frontmatter + markdown)
        ├── commands/
        │   └── fat-audit.md             # /fat-audit slash command
        ├── scripts/                     # Python helpers Claude executes
        ├── references/                  # Deep-dive docs loaded on-demand
        ├── assets/                      # Icons, images
        └── evals/                       # Test cases
```

The `description` field in SKILL.md frontmatter is critical — it's what Claude uses to decide whether to activate the skill. It needs to be comprehensive and slightly "pushy" to avoid under-triggering.

SKILL.md uses `${CLAUDE_PLUGIN_ROOT}` prefix for all script and reference file paths, which resolves to `plugins/fat-agent/` at runtime.

## What's Been Built So Far

### Done

1. **SKILL.md** — Complete core skill with:
   - Phase 0: Context gathering (asks user for URL, site type, stack, critical flows)
   - Phase 1: AUDIT — 8 check categories (availability, SEO, performance, security, accessibility, functional, content/legal, analytics)
   - Phase 2: FIX — Prioritised report generation (P0 Critical → P3 Low) with fix code and effort estimates
   - Phase 3: TEST — Re-verification after fixes are deployed, final scorecard

2. **references/security-headers.md** — Full security header reference with Netlify-specific implementation examples

3. **references/seo-checklist.md** — Extended SEO audit criteria covering on-page, technical, social, and performance-impact-on-SEO checks with scoring guide

4. **references/accessibility-guide.md** — WCAG 2.1 quick reference split into HTML-checkable items vs user-prompted checks

5. **scripts/analyse-html.py** — Python HTML parser that extracts SEO, accessibility, performance, security, and content signals from raw HTML. Outputs a structured JSON report with auto-generated issue summaries by priority.

6. **scripts/calculate-score.py** — Scoring calculator producing SEO, Security, Accessibility, Performance, and overall FAT scores.

7. **scripts/generate-badge.py** — SVG badge generator with character image and colour-coded category breakdown.

8. **evals/evals.json** — 5 test cases covering basic audit, contextual trigger, focused audit, punch list status, and re-verification

9. **README.md** — GitHub-ready documentation with usage examples, project structure, scoring explanation, and contribution guide

10. **Plugin structure** — Marketplace manifest, plugin manifest, `/fat-audit` slash command

11. **Platform and framework references** — Complete fix templates for 7 hosting platforms and 7 frameworks

12. **LICENSE** — MIT

## What Needs to Be Finished / Improved

### High Priority

1. **The skill needs real-world testing.** Run it against 3-5 actual URLs and see where it falls short. The audit categories are comprehensive in theory but may need tuning for edge cases (SPAs that return minimal HTML, sites behind Cloudflare challenges, sites with heavy client-side rendering).

### Medium Priority

2. **Add a config file generator per platform.** When security headers are missing, FAT Agent should offer to generate the complete config file for the user's specific platform (e.g., `_headers` for Netlify/Cloudflare, `vercel.json` for Vercel, `.htaccess` for Apache, etc.), not just show snippets.

3. **Internationalisation checks.** The accessibility guide mentions `hreflang` but the main audit flow doesn't check for it. Add i18n as a conditional check when the site serves multiple languages.

### Low Priority / Nice-to-Have

4. **Historical tracking.** If FAT Agent is run multiple times on the same site, it would be great to show improvement over time. This would require persistent storage (maybe a JSON file the skill reads/writes).

5. **Competitive analysis mode.** "Run FAT agent on my site AND my competitor's site and compare." Would need to run the audit twice and present a side-by-side comparison.

6. **CI/CD integration guide.** A reference doc explaining how to run FAT Agent checks as part of a deploy pipeline (Netlify build plugins, GitHub Actions, etc.).

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

- This is a Claude Plugin distributed as a marketplace
- Claude reads SKILL.md as instructions and follows them conversationally
- The skill uses Claude's built-in tools: `web_fetch` (to grab live URLs), `web_search` (to find PageSpeed results etc.), `ask_user_input` (for structured questions), and `bash_tool` (to run the Python scripts)
- The Python scripts are helpers that Claude executes, not user-facing CLI tools
- All reference docs are loaded by Claude on-demand when it needs deeper info on a specific category
- The skill is designed for Anthropic's Claude.ai / Claude Code environments
- The `/fat-audit` slash command provides direct invocation with an optional URL argument

## Repository

```
fat-agent-skill/
├── .claude-plugin/
│   └── marketplace.json                  # Marketplace manifest
├── plugins/fat-agent/
│   ├── .claude-plugin/
│   │   └── plugin.json                  # Plugin manifest
│   ├── skills/fat-agent/
│   │   └── SKILL.md                     # Core skill (complete)
│   ├── commands/
│   │   └── fat-audit.md                 # /fat-audit slash command
│   ├── scripts/
│   │   ├── analyse-html.py              # HTML analyser
│   │   ├── calculate-score.py           # Score calculator
│   │   ├── generate-badge.py            # Badge generator
│   │   └── test_fat_agent.py            # Test suite (201 tests)
│   ├── references/
│   │   ├── security-headers.md          # Security reference (complete, multi-platform)
│   │   ├── seo-checklist.md             # SEO reference (complete)
│   │   ├── accessibility-guide.md       # A11y reference (complete)
│   │   ├── platform-fixes/             # Platform-specific fix templates
│   │   │   ├── netlify.md
│   │   │   ├── vercel.md
│   │   │   ├── cloudflare-pages.md
│   │   │   ├── apache.md
│   │   │   ├── nginx.md
│   │   │   ├── wordpress.md
│   │   │   └── aws.md
│   │   └── framework-fixes/            # Framework-specific fixes
│   │       ├── nextjs.md
│   │       ├── astro.md
│   │       ├── sveltekit.md
│   │       ├── nuxt.md
│   │       ├── gatsby.md
│   │       ├── wordpress.md
│   │       └── static-html.md
│   ├── evals/
│   │   └── evals.json                  # Test cases (complete)
│   └── assets/
│       ├── fat-agent-badge-icon.png
│       └── social-preview.png
├── fat-badge.svg                        # Generated badge
├── README.md                            # GitHub docs
├── CLAUDE.md                            # Project conventions
├── LICENSE                              # MIT
├── .gitignore
└── .github/
    └── LLM-BRIEF.md                    # This file
```

**Important distinction:**
- `platform-fixes/` = hosting platform config (Netlify _headers, Vercel vercel.json, Apache .htaccess)
- `framework-fixes/` = application framework code (Next.js Head component, Astro layouts, WordPress functions.php)

## Who Made This

Built by Rye at Spruik Co (Adelaide, Australia) — a digital marketing and SEO consultancy. The skill leverages deep SEO and web development expertise to automate the post-launch QA process that agencies typically do manually.

---

**To the LLM reading this:** Pick up from the "What Needs to Be Finished" section. Start with the high-priority items. Read the existing files first to understand the patterns and conventions, then build the missing pieces to match. The voice should be practical and direct — this is a tool for professionals, not a tutorial.
