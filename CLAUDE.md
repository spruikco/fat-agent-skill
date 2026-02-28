# FAT Agent — Project Conventions

## What This Is

FAT Agent is a Claude Skill (not a standalone app). The core file is `SKILL.md` — Claude reads it as instructions when the skill triggers. Everything else supports it.

## File Roles

- `SKILL.md` — The skill definition. Claude reads this on trigger. YAML frontmatter controls activation.
- `scripts/` — Python helpers that Claude executes via bash during audits.
- `references/` — Deep-dive docs Claude loads on-demand when it needs specifics.
- `references/platform-fixes/` — One file per hosting platform (Netlify, Vercel, etc.).
- `references/framework-fixes/` — One file per framework (Next.js, Astro, etc.).
- `evals/` — Test cases for validating skill behaviour.
- `assets/` — Templates and static assets (currently empty).

## Conventions

- British English spelling throughout (analyse, colour, prioritise).
- Markdown for all docs — no HTML in reference files unless demonstrating HTML code.
- Python scripts use stdlib only (no pip dependencies). Must work on Python 3.8+.
- Reference docs follow the pattern: explanation, code example, scoring table.
- Platform/framework docs should include complete, copy-pasteable config examples.
- SKILL.md sections are numbered (1.1, 1.2, ..., 1.9). New audit checks go after 1.9.

## Testing

- `python scripts/analyse-html.py <file.html>` — outputs JSON report.
- `python scripts/analyse-html.py < file.html` — reads from stdin.
- `python scripts/calculate-score.py <report.json>` — scores an analysis report.
- Pipeline: `python scripts/analyse-html.py page.html | python scripts/calculate-score.py`

## Adding Content

When adding a new platform or framework reference:
1. Create the file in the appropriate `references/` subdirectory.
2. Add a reference line to the bottom of `SKILL.md` under Reference Files.
3. If it's a platform, add platform-specific checks to section 1.9 of SKILL.md.
