# FAT Design report template

Fill this in as the audit output. Keep every line a named, evidence-backed decision. No
em dashes. Adapt length to the target (a single component needs less than a full page).

---

```
# FAT Design audit: <screen / URL / component>
Date: <date>   Target: <what was audited>   Source: <live URL / screenshot / repo path>

## Primary job
<One sentence: what this screen is for. If it cannot be named, that is finding T0.>

## Slop smell test (30-second read)
<Which of the AI-slop tells are present, if any: default font / purple gradient /
symmetric cards / stacked decoration / copy tells. Note: one may be fine; several
together with no shared reason is the problem.>

## Findings
| ID | Lens | Finding (named, with evidence) | Harm | Freq | Reach | Priority |
|----|------|--------------------------------|------|------|-------|----------|
| T1 | Product | <e.g. Delete uses the same pill as Save, no confirm, irreversible> | High | Low | All | P0 |
| T2 | Copy | <e.g. CTA "Get started" names a mechanic, not the outcome> | Med | High | All | P1 |
| T3 | Type | <e.g. faux bold heading, clogged joints> | Low | High | All | P2 |
| .. | ..   | ..                             | ..   | ..   | ..    | .. |

Lenses: Product / Copy / Type / Craft / Interaction / Motion (+ AI-expose / AI-trust).

## Briefs for P0 / P1
### <T1 title>  [Lens, Priority]
- Job: <user goal in their words>
- Change: <the decision, in the lens vocabulary, traced to evidence>
- Consequence: <what improves / what the interface now communicates>

### <T2 title>  [Lens, Priority]
- Job: ...
- Change: ...
- Consequence: ...

## Repair applied (if any)
- Finding: <which one>
- Before -> after: <the decision changed, not just the diff>
- Verification: <re-ran the task by keyboard / screen reader / bad light / last-mile;
  result>

## The read
<Two or three sentences: the highest-cost pattern, and the single change that would move
quality most.>
```

---

## Scoring shorthand

- Harm: High = blocks task / wrong action / data loss / trust; Med = friction or
  confusion; Low = cosmetic.
- Freq: High = many times a day; Med = daily-ish; Low = rare.
- Reach: All = nearly everyone; Some = a segment; Edge = one case.
- Priority rolls up per `briefs.md`: P0 fix before ship, P1 this pass, P2 soon, P3 polish.

Fix by cost, not by visibility. Behaviour and words before motion.
