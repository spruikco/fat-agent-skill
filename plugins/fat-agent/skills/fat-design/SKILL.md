---
name: fat-design
description: >
  FAT Design, the design-taste department of FAT Agent (Fix, Audit, Test). Runs a
  six-lens audit (product design, copywriting, typography, craft, interaction,
  animation) over a screen, URL, screenshot or frontend code to find the last 10%
  that makes an interface feel considered instead of generated. Names each weak
  decision in the lens's vocabulary, ranks findings by cost (harm x frequency x
  reach), writes three-part briefs, and can implement the highest-value repair then
  verify it. Where fat-agent checks SEO, security, speed and accessibility as code,
  fat-design checks whether the thing feels designed. Trigger whenever the user
  wants to audit or improve the visual or interaction quality of a UI, asks "does
  this look AI-generated", "does this look like slop", "fix the last 10%", "make
  this feel designed / considered / premium", "review this design", "is this
  shippable", "why does this feel cheap", or says "FAT design", "design audit",
  "taste audit", "spot the slop". Also run it proactively after a site build or a
  generated screen, before shipping.
---

# FAT Design: the last 10% audit

AI gets an interface about 90% of the way there. FAT Design audits and fixes the last
10%: the small decisions that make a screen feel considered rather than assembled from
defaults. It is the design department of FAT Agent and pairs with the `fat-agent` skill,
which owns SEO, security, performance and accessibility-as-code. Run both on a live site;
run FAT Design alone on a screen, a component or a mockup.

Method informed by Matthew Blode's Taste Training course (blode.co/taste-training). The
per-lens checklists in `references/design/` are the working notes; the course is the
depth behind them.

**House rule: never use em dashes in anything you write for this audit.** The method
flags more than one em dash per 1,000 words as a tell of generated copy, so the audit's
own prose cannot carry them. Use commas, full stops or brackets.

## The core idea

> "The quality of any collaborative creative endeavour tends to approach the level of
> taste of whoever is in charge." When you brief an AI or a builder, you are in charge,
> so your taste is the ceiling.

Quality is a stack of small decisions pointing at one task. None alone is the polish.
Taste is trained, not innate: you build it by comparing versions, naming the difference,
then testing that principle elsewhere. The whole game is one loop:

**Spot -> Name -> Fix -> Verify.** Feel what is off, name it in a lens's vocabulary (so
it becomes something you can hunt on purpose, not a lucky catch), ask for the stronger
version, then prove the repair on the task that exposed it.

## When to run it

- A live URL (screenshot it in the browser, or read the rendered DOM and CSS).
- A screenshot or mockup the user drops in.
- Local frontend code (React, HTML, CSS) in a repo.
- Right after a generator or agent produces a screen, or after a deploy, as a
  ship/no-ship quality gate.

If the target is a whole live site and the user also wants SEO, security or speed, run
the `fat-agent` skill (or `/fat-audit`) for those and FAT Design for design quality.
They are complements, and findings from both belong on the same punch list.

## Gathering evidence

Judge the rendered screen, not the source alone. In order of preference:

1. **Browser tools**, when the session has them: open the URL, take a full-page
   screenshot at desktop width and one at 390px, then zoom into the hero, the primary
   form and the primary action. Try the task by keyboard and read the tab title, favicon
   and share preview.
2. **Headless capture**, when Playwright is installed (the plugin's optional
   `lighthouse` extra): capture the settled page, a 390px mobile shot, and a shot taken
   before any entrance animation settles, which proves whether the hero is blank on
   first paint.
3. **Code and screenshots** supplied by the user, when nothing can be rendered. Say so in
   the report; typography, interaction and motion findings are weaker from code alone.

## The procedure (do this)

1. **Identify the screen's primary job** in one sentence. Everything is judged against
   whether it serves that job. If you cannot name the job, that is finding number one.

2. **Sweep one lens at a time, behaviour to finish, top to bottom.** Hunting for
   everything at once catches almost nothing because the loudest flaw steals attention.
   Pick one lens, sweep the screen, record evidence, then change lenses. Run the six in
   this order (behaviour first, finish last):

   1. **Product design**: what it should do before it is styled
   2. **Copywriting**: every word in the interface
   3. **Typography**: how the text is set
   4. **Craft**: a chosen look, space, colour, edges, polish
   5. **Interaction**: focus, targets, forms, feedback, access
   6. **Animation**: motion that explains change

   The per-lens checklists are in `${CLAUDE_PLUGIN_ROOT}/references/design/lenses.md`.
   Load it before sweeping. Motion comes last because it only describes decisions the
   first five lenses settle: animating a broken state makes the break harder to ignore.

   If the target is an AI feature (assistant, agent, generative surface), add the two AI
   passes in `${CLAUDE_PLUGIN_ROOT}/references/design/ai-features.md` after lens 6:
   audit what it exposes (actions and states) and whether it has earned the trust to act.

3. **Name every finding in the lens's vocabulary and attach evidence.** Not "the header
   feels off" but "the heading is a faux bold: the browser smeared the regular cut, so
   the joints clog (typography)". A named finding is fixable; a vibe is not.

4. **Trace each finding to evidence over taste.** Every call rests on one of: the user's
   stated goal, verified product behaviour, canonical guidance (design system, platform
   conventions), or a pattern already shipped in the same product. Resting on taste is
   allowed, but say so: "collapsed on a hunch" is reviewable, "the right default" is not.

5. **Rank by cost, not by how obvious the flaw was.** For each finding score three
   things, then sort P0 (fix before ship) to P3 (polish):

   - **Harm:** does it block the task, cause a wrong action, erode trust, or merely look
     rough? Blocks, wrong action and trust are high; cosmetic is low.
   - **Frequency:** met once a year, or forty times a day?
   - **Reach:** one edge case, or nearly everyone?

   The predictable mistake is polishing the most visible flaw first. A weak shadow is
   obvious; a wiped form after a validation error is expensive. Cost sets the order.

6. **Write each top finding as a three-part brief** (the note you hand a teammate or an
   AI, see `${CLAUDE_PLUGIN_ROOT}/references/design/briefs.md`):

   - **Job**: the user's goal in their words.
   - **Change**: the specific decision to make, in the lens's vocabulary, traced to its
     evidence.
   - **Consequence**: what the interface must now communicate, or what improves.

7. **Fix the highest-cost finding** (if asked and able). Edit, do not regenerate. For
   generated screens run the subtract-first three-pass edit in `ai-features.md`: delete
   what earns nothing, then structure, then surface (type, spacing, words), then details
   and states.

8. **Verify on the task that exposed it.** Re-run the five-second scan or the actual task
   by keyboard, screen reader and in bad light where relevant. Then run the **last-mile**
   check: tab title, favicon, share preview, theme colour, and the failure paths (empty,
   connection cut mid-save, no data). "Looks done" is the default; "is done" is the parts
   no prompt asked for.

## Fast triage: the slop smell test

Before the full sweep, a 30-second read catches the most common tells. Any one may fit
the product; several together with no shared reason is slop (a default that arrived
without a decision):

- **Default system font** nobody chose for its tone.
- **Purple or indigo gradient hero** doing no job.
- **Three identical evenly spaced cards** flattening a real priority.
- **Stacked decoration:** glow, gradient fill, heavy shadow and backdrop blur competing.
- **Cramped, edge-to-edge layouts** that never chose a content width.
- **Copy tells:** "I'd be happy to", "Let's dive in", "In today's fast-paced world", vague
  attributions ("experts believe"), and em dashes (more than one per 1,000 words).

Full signals and the fix-do-not-swap rule are in `ai-features.md`.

## Output

Produce a **ranked findings report** using
`${CLAUDE_PLUGIN_ROOT}/references/design/report-template.md`: the screen's job, a table
of findings tagged by lens and P0 to P3 with evidence, then three-part briefs for the P0
and P1 items. If you implemented a repair, show the before and after decision and the
verification result. Keep it concrete: every line is a named decision someone can act on.

When a FAT Agent audit is also running, add the P0 and P1 design findings to the same
punch list (`.fat-work/punchlist.json`, module `design`) so they are tracked and
re-tested with everything else.

## The three things to remember

1. One lens at a time, behaviour to finish. Name the weakness, do not just feel it.
2. Rank by cost (harm x frequency x reach), not by visibility. Fix the expensive one.
3. Every fix is one named, evidence-backed sentence you could hand to a person or an AI.

## Reference files

- `references/design/lenses.md`: the six per-lens checklists, behaviour to finish.
- `references/design/briefs.md`: the three-part brief, evidence over taste, pricing a
  finding into P0 to P3.
- `references/design/ai-features.md`: spotting slop, the subtract-first three-pass
  edit, the last-mile check, and the two extra passes for AI features.
- `references/design/report-template.md`: the report shape.
