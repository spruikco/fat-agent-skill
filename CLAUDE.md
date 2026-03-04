# FAT Agent — Project Conventions

## What This Is

FAT Agent is a Claude Plugin distributed via a marketplace. The repo root is the marketplace; the plugin lives under `plugins/fat-agent/`.

## File Roles

- `plugins/fat-agent/skills/fat-agent/SKILL.md` — The skill definition. Claude reads this on trigger. YAML frontmatter controls activation.
- `plugins/fat-agent/scripts/` — Python helpers that Claude executes via bash during audits.
- `plugins/fat-agent/references/` — Deep-dive docs Claude loads on-demand when it needs specifics.
- `plugins/fat-agent/references/platform-fixes/` — One file per hosting platform (Netlify, Vercel, etc.).
- `plugins/fat-agent/references/framework-fixes/` — One file per framework (Next.js, Astro, etc.).
- `plugins/fat-agent/evals/` — Test cases for validating skill behaviour.
- `plugins/fat-agent/assets/` — Templates and static assets.
- `plugins/fat-agent/commands/fat-audit.md` — The `/fat-audit` slash command.
- `.claude-plugin/marketplace.json` — Marketplace manifest.
- `plugins/fat-agent/.claude-plugin/plugin.json` — Plugin manifest.

## Conventions

- British English spelling throughout (analyse, colour, prioritise).
- Markdown for all docs — no HTML in reference files unless demonstrating HTML code.
- Python scripts use stdlib only (no pip dependencies). Must work on Python 3.8+.
- Reference docs follow the pattern: explanation, code example, scoring table.
- Platform/framework docs should include complete, copy-pasteable config examples.
- SKILL.md sections are numbered (1.1, 1.2, ..., 1.9). New audit checks go after 1.9.

## Testing

- `python plugins/fat-agent/scripts/analyse-html.py <file.html>` — outputs JSON report.
- `python plugins/fat-agent/scripts/analyse-html.py --url https://example.com <file.html>` — enables mixed content detection.
- `python plugins/fat-agent/scripts/analyse-html.py < file.html` — reads from stdin.
- `python plugins/fat-agent/scripts/calculate-score.py <report.json>` — scores an analysis report.
- Pipeline: `python plugins/fat-agent/scripts/analyse-html.py page.html | python plugins/fat-agent/scripts/calculate-score.py`
- `python plugins/fat-agent/scripts/generate-badge.py <scores.json>` — generates an SVG score badge.
- `python plugins/fat-agent/scripts/generate-badge.py scores.json --category seo` — badge for a specific category.
- `python plugins/fat-agent/scripts/generate-badge.py scores.json --output badge.svg` — write to file.
- Full pipeline: `python plugins/fat-agent/scripts/analyse-html.py page.html | python plugins/fat-agent/scripts/calculate-score.py | python plugins/fat-agent/scripts/generate-badge.py --output badge.svg`
- `python plugins/fat-agent/scripts/test_fat_agent.py` — runs the full test suite (201 tests).

## Adding Content

When adding a new platform or framework reference:
1. Create the file in the appropriate `plugins/fat-agent/references/` subdirectory.
2. Add a reference line to the bottom of `plugins/fat-agent/skills/fat-agent/SKILL.md` under Reference Files.
3. If it's a platform, add platform-specific checks to section 1.9 of SKILL.md.
