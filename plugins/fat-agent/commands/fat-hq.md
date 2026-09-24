---
name: fat-hq
description: Connect FAT Agent to FAT HQ (optional hosted dashboard) or send the latest audit there.
argument-hint: "[login <key> | upload [URL] | status]"
allowed-tools:
  - Bash
  - Read
---

# /fat-hq: FAT HQ dashboard

FAT HQ keeps your audits, charts scores over time, re-checks sites on a
schedule and emails you when something breaks. It is optional; the plugin
works fully without it. Accounts and plugin keys: https://fathq.prodimus.com.au

Arguments: `$ARGUMENTS`

- `login <key>`: run `python ${CLAUDE_PLUGIN_ROOT}/scripts/fat_hq.py login <key>` and report the result.
- `upload [URL]`: run `python ${CLAUDE_PLUGIN_ROOT}/scripts/fat_hq.py upload` (add `--url URL` if given)
  from the project directory that holds `.fat-work/`. If there is no `.fat-work/scores.json`,
  say so and offer to run `/fat-audit` first.
- `status` or nothing: run `python ${CLAUDE_PLUGIN_ROOT}/scripts/fat_hq.py status`. If no key is
  saved, explain how to make one at https://fathq.prodimus.com.au/app/keys.

Never print or repeat a full key back to the user after saving it.
