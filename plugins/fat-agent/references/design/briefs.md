# Writing the brief and pricing the finding

Source: Matthew Blode's Taste Training, "Write your first design brief", "Write a
decision brief", and "Audit and improve your own product" (re-captured Oct 2026). No em
dashes in output.

## The three-part brief

Your output is not code. It is the note you hand a designer, a teammate, or an AI. Three
parts:

1. **Job**: the user's goal in their own words. ("Change my billing plan without reading
   forty lines to find the one control.")
2. **Change**: the specific decision to make, named in the lens's vocabulary and traced
   to its evidence. ("Rank the plan names with weight + a letterspaced caps label instead
   of size alone (typography); they currently sit 20px next to a 24px heading and compete.")
3. **Consequence**: what the interface now communicates / what improves. ("A skimmer sees
   the four plan names in one pass and picks without reading every line.")

Feeling, cause, direction. No expertise needed to send it. A repair that only makes sense
beside its brief has not landed yet.

## Evidence over taste

Every material decision traces to something firmer than preference, in this priority:

1. The user's stated goal and constraints.
2. Verified product behaviour (what the action does to the data).
3. Canonical guidance (design system, platform conventions, team conventions).
4. A verified pattern already shipped in the same area.

Resting on taste is fine, but *say so*. "Collapsed on a hunch" is reviewable; "the right
default" is not. Never treat shipped work as proof: a **fact** is what the product
verifiably does; a **decision** is a choice you make and justify.

For a material product-design change, clear the five-question checklist first (What
problem? Why this interaction? What consequence? Which states? Smallest change?), then
move to layout, component, copy. Behaviour decides the interface.

## Pricing the finding (harm x frequency x reach)

Rank every finding by three questions, then sort into P0..P3:

- **Harm**: blocks the task (high) > causes a wrong action (high) > erodes trust (high)
  > merely looks rough (low).
- **Frequency**: met forty times a day (high) ... once a year (low).
- **Reach**: nearly everyone (high) ... one edge case (low).

Suggested banding:

| Priority | Meaning | Typical profile |
| --- | --- | --- |
| **P0** | Fix before ship | Blocks the task or destroys/loses data; hits everyone. A wiped form on error, a delete with no confirm, an unreachable action by keyboard. |
| **P1** | Fix this pass | Wrong action risk or clear trust erosion; frequent. Ambiguous destructive label, no error recovery, invisible focus. |
| **P2** | Fix soon | Rough but the task still completes. Flat hierarchy, mismatched typeface voice, weak CTA copy. |
| **P3** | Polish | Cosmetic drift. A slightly heavy shadow, an odd gap, a stray widow. |

The predictable mistake is polishing the most visible flaw first. A weak shadow is
obvious and cheap; a wiped form after a validation error is invisible in a screenshot and
expensive. **Cost sets the order, not visibility.**

Motion findings almost never outrank product-design or copy findings. Fix behaviour and
words first; animate a decision only after the first five lenses settle it.
