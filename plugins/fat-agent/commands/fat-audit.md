---
name: fat-audit
description: Run a FAT Agent audit on a deployed website. Checks SEO, security, accessibility, performance, content, and analytics.
argument-hint: "[URL]"
allowed-tools:
  - Bash
  - Read
  - WebFetch
  - AskUserQuestion
---

# /fat-audit — Run a FAT Agent Audit

You have been asked to run a FAT Agent (Fix, Audit, Test) audit.

## Setup

1. Load the FAT Agent skill instructions from `${CLAUDE_PLUGIN_ROOT}/skills/fat-agent/SKILL.md`
2. If a URL argument was provided, use it as the live URL and skip that question in Phase 0

## Workflow

Follow the full FAT Agent workflow:

1. **Phase 0 — Gather Context** — Ask for any missing details (site type, tech stack, hosting platform). If the URL was provided as an argument, skip the URL question.
2. **Phase 1 — Audit** — Run all check categories against the live URL. Use the analysis scripts at `${CLAUDE_PLUGIN_ROOT}/scripts/` and reference files at `${CLAUDE_PLUGIN_ROOT}/references/` as needed.
3. **Phase 2 — Fix** — Generate the prioritised FAT Report and offer to fix issues.
4. **Phase 3 — Test** — After fixes are deployed, re-verify and generate the final scorecard and badge.

## Scripts

- `${CLAUDE_PLUGIN_ROOT}/scripts/analyse-html.py` — HTML analysis helper
- `${CLAUDE_PLUGIN_ROOT}/scripts/calculate-score.py` — Scoring calculator
- `${CLAUDE_PLUGIN_ROOT}/scripts/generate-badge.py` — SVG badge generator
