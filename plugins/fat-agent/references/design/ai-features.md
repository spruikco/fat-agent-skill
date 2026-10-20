# AI: spotting slop, editing output, verifying the last mile, and auditing AI features

Source: Matthew Blode's Taste Training, units "Keep your taste with AI" and "Design AI
people trust" (re-captured Oct 2026). No em dashes in output.

The premise: faster generation makes your judgement matter *more*, not less. The model
supplies code; you supply context. Without context it reaches for the most common answer,
a default nobody checked. Vibe coding (one prompt, whatever comes back) is for exploring;
every shipped screen is a reviewed draft.

---

## 1. Spot visual slop

Slop is a default that arrived without a decision. Any one may fit the product; several
together with no shared reason read as assembled-from-defaults. Four signals cause most:

1. **Default fonts**: a system font nobody chose for its tone.
2. **Purple/indigo-on-white gradients**: flooding the hero for no brand/hierarchy/content
   reason. One earns its place; a wash of them does not.
3. **Predictable layouts**: icon + heading + paragraph, times three, evenly spaced.
   Symmetry works only when options matter equally; it fails when a real priority gets
   flattened.
4. **Excess glow and decoration**: stacked shadows, glowing borders, gradient fills,
   backdrop blur. An effect should show depth, separation, or state, not compete.

## 2. Spot verbal slop (copy tells)

The model writes with the same unowned defaults. Flags:

- Chatbot phrases: "I'd be happy to", "Let's dive in", "As of my last update", "In today's
  fast-paced world", "It's worth noting that".
- Vague attributions: "experts believe", "studies show", "many people say".
- **Em dashes** used as a default connector (more than one per 1,000 words is a signal).
- Adjective stacks and Tell words ("powerful, seamless, robust, intuitive, cutting-edge").

**Fix the meaning, never a mechanical synonym swap.** For each flag: **ask** what the
sentence means and write that, **replace** the abstraction with a fact (number, name,
outcome), or **cut** it.

---

## 3. Edit AI output in three passes (edit, do not regenerate)

Reject a choice for missing the product's standard, not for coming from a model. Subtract
before you add.

**Delete pass (first).** For each element ask what need it supports. No answer, it goes:
placeholder logo strips, generic-praise testimonials, feature grids nobody asked for,
extra buttons diluting the primary action, decorative dividers between every section. Most
first drafts give up three or more.

Then three passes, in order (polish cannot rescue a broken structure):

- **Pass 1: structure.** Name the primary task, make its next action obvious, put
  prerequisites before it.
- **Pass 2: surface (type, spacing, words).** Typeface suits the product; hierarchy
  levels clearly different or identical, never nearly the same; group by relationship
  (plan names near prices, plans apart). Rewrite copy for meaning using ask/replace/cut.
- **Pass 3: details.** The states no prompt asked for: hover, focus, pending, success,
  error, empty. AI ships the happy path; you ship the pending and error states.

**Replace adjectives with references, not moods.** "Make it premium" names no task,
density, or hierarchy, so the model invents a mood. Instead hand it: an approved reference
that shares your task/density/audience/platform, the product's colour/type/spacing tokens,
component constraints, real content, and accessibility requirements. Say what to borrow.
Criteria, not adjectives.

---

## 4. Verify the last mile

"Looks done" is the default; "is done" is the parts no prompt named. Run this yourself.

**Browser identity (four requests):**
- **Tab title:** page before product ("Billing . Northwind", not "Home").
- **Favicon:** not the framework default; add the icon phones use.
- **Share preview:** og image + title + one line; paste the link somewhere private and
  judge the card.
- **Theme colour:** the edge tint on mobile; make it the product's.

**Break it on purpose** (prove it works by trying to make it fail):
1. Read the tab: real title and favicon, not framework defaults.
2. Paste the link privately; judge the preview card.
3. Empty form; connection cut mid-save; no data. A failure keeps the input and names the
   next step; an empty screen invites a first action.

Confirm the states from Pass 3 survived the handoff (hover, focus, pending, error, empty).

---

## 5. Auditing an AI feature (assistant / agent / generative surface)

An AI feature is just another surface to audit; it reaches more states than a screen, not
fewer, and the ones you skip ship anyway. Run these two passes after the six lenses.

### 5a. Audit what it exposes

- **Actions:** for every task the UI offers on an object, try to finish it through the
  agent. Check at the level of create, read, update, delete. Each one you cannot is a
  finding (teams wire create + list, then miss rename + delete, and the wall only shows on
  the request that needs them).
- **States a reply can land in** (each needs a designed frame): **thinking** (show which
  step, not a frozen field), **partial** (what is known vs still coming), **refusal**
  (what it cannot do *and where the user can*, never a bare "I can't"), **empty** (a first
  prompt, not a blank box), **error** (what failed + how to retry, request preserved).
- **Feedback lands where attention is:** results arrive by the request; long jobs show
  step-level progress ("Reading 12 files", "Found 3 conflicts"). It never asks what the
  screen already shows (open folder, selected file, recent actions reach it as context).
- **Show its work:** each move visible and correctable before accept, not one silent
  action you cannot question after.

### 5b. Audit whether it earned the trust to act

Trust is a design property, not a model property. Five checks; the twist is the agent, not
the person, picks the action.

Before the action:
- **Gate proportional to blast radius** (how much it touches, how public, how hard to
  undo): low+easy -> just do it; low+hard -> quick confirm; high+easy -> show a diff then
  apply; high+hard -> explicit approval. An explicit request is its own approval (do not
  re-ask "share with Sam" after they said "share with Sam"). Batch-review 60 items once,
  never 60 separate prompts (that trains blind clicking).
- **Play back the goal before long autonomous work:** "I'll move the 2023 folders under
  Archive and update the links. Go ahead?" The last cheap moment to catch a misread.

During and after:
- **Show confidence:** if the agent is guessing, the interface must say so. One
  confident wrong answer costs more trust than ten honest "I'm not sure". Attach the
  reason/source for sure answers; mark low-confidence ones differently (badge, hedge,
  "why I think this"). A 95% answer and a 40% guess in the same font teach nothing.
- **Never trap someone:** a real stop button during execution (not a spinner that ignores
  clicks) + step progress; undo after for anything reversible; a "talk to a person" path
  for high-stakes work (billing, legal, account-wide). Every flow needs one; consequential
  ones need all.
- **Make memory visible:** anything it stores gets a plain, editable "what I remember
  about you" panel, or opaque memory feels like surveillance.
