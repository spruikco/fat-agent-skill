---
name: fat-design
description: Run FAT Design, the six-lens design-taste audit, on a URL, screenshot or frontend code. Finds the weak decisions that make a screen feel generated, ranks them by cost and writes the briefs to fix them.
argument-hint: "[URL or path]"
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - WebFetch
  - AskUserQuestion
---

# /fat-design: the design-taste audit

You have been asked to run FAT Design on a screen.

## Setup

1. Load the skill instructions from `${CLAUDE_PLUGIN_ROOT}/skills/fat-design/SKILL.md`
   and the lens checklists from `${CLAUDE_PLUGIN_ROOT}/references/design/lenses.md`.
2. Work out the target from `$ARGUMENTS`:
   - A URL: the live screen. Render it (browser tools if available, otherwise a headless
     capture if Playwright is installed, otherwise fetch the HTML and say the audit is
     from code alone).
   - A file or directory path: local frontend code. Read the components and styles that
     make up the screen.
   - Nothing: ask for a URL, a screenshot or a path, and which screen matters most.
3. Ask one question only if the primary job of the screen is not obvious: "What is this
   screen for, in one sentence?"

## Workflow

1. **Smell test** (30 seconds): note any slop tells present.
2. **Six sweeps**, one lens at a time, behaviour to finish: product design, copywriting,
   typography, craft, interaction, animation. Record evidence for each finding.
3. **Rank** every finding by harm x frequency x reach into P0 to P3.
4. **Brief** the P0 and P1 findings as Job / Change / Consequence.
5. **Report** using `${CLAUDE_PLUGIN_ROOT}/references/design/report-template.md`.
6. **Offer the repair**: fix the highest-cost finding if the code is at hand, then verify
   on the task that exposed it and run the last-mile check.

If a FAT Agent audit exists for the same site (`.fat-work/` in the project), add the P0
and P1 design findings to its punch list under module `design`.

No em dashes anywhere in the report.
