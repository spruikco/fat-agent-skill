# The six lenses: audit checklists

Sweep one lens at a time, top to bottom, behaviour first and finish last. Record
evidence for each hit before changing lenses: hunt for everything at once and the loudest
flaw takes the whole pass. Source: Matthew Blode's Taste Training, units 1-7 and 9,
re-captured Oct 2026 (48 lessons). (No em dashes anywhere in output.)

---

## Lens 1: Product design (what it does before it is styled)

Catches the *wrong* interface, not a rough version of the right one. Styling cannot
rescue a control that makes the wrong promise.

- **Task:** can you name the screen's primary job in one sentence?
- **Control matches the choice:** the shape of the choice picks the control, not habit.
  - 2-3 fixed, mutually exclusive -> radio / segmented, not a select that hides them.
  - Many or changing options -> select / combobox, not a long radio list.
  - Binary applied immediately -> switch. Binary saved with a form -> checkbox. (A
    switch says "done" the instant it flips; a checkbox stages until Save.)
  - One action -> button, not a one-item menu (a menu holding one item is a button in
    disguise). Going somewhere -> link, not a button.
  - A toggle defers the decision. If you already know the right answer, ship it as the
    default instead of asking.
- **Scope and consequence named before the click:** object (the exact noun, "the Q3
  Designs folder", not "this item"), scope (how many, whose; shared raises the stakes),
  consequence (reversible or permanent). Verb + noun on the button ("Delete project",
  never "Confirm/OK/Yes"). One verb, one meaning (Delete vs Remove vs Archive; Cancel vs
  Discard). If the user cannot tell what changes, how much, and whether it reverses, it
  does not ship.
- **Friction proportional to impact:** reversible+routine -> none or an undo toast;
  reversible -> plain confirm; irreversible -> distance from the safe controls, a quieter
  button, and a typed or second confirmation. A confirm dialog on a reversible action just
  trains people to dismiss dialogs.
- **Every reachable state is designed**, not just the happy path. List the landings the
  data and permissions allow: loading (skeleton, not a bare spinner), per-action loading
  (spinner *in* the pressed control, label held still), empty (name the object + first
  action; never-had-any is a different screen from filtered-to-zero; a hero always earns
  one action, every other empty screen earns what its reason for being empty deserves),
  sparse, populated, partial/stale,
  error (what happened, why, recovery; never clear the input), permission-denied (what
  they lack + how to request), disabled (why, never a silent grey), optimistic (rollback
  designed), destructive-in-progress (pending + honest undo window + failure path).
- **Smallest intervention:** could a better default or a behaviour change remove UI
  instead of adding it? The ladder, cheapest first: (1) a better default, (2) a
  behaviour change the system does reliably, (3) reuse an existing pattern, (4) new UI
  only if nothing above works. Every control costs attention forever.

**Material vs mechanical:** a change is *material* if it alters what the user does or
their data (needs a brief); otherwise *mechanical*. In doubt, treat as material. Five
questions before a material change ships: What problem (user's words)? Why this
interaction (not habit)? What consequence (scope, reversibility, who)? Which states
(all reachable, completable without a mouse)? Smallest change that works? If you cannot
fill in the job, the desired outcome and the consequence, stop and ask: guessing produces
confident, wrong work.

---

## Lens 2: Copywriting (every word)

The one domain you can improve today without any tooling.

- **Reader and task:** does the opening name *why this matters now*, in the reader's
  world, not the product's category? Headline leads with the reader's Why; body leads
  with the outcome (their changed day), not the feature. "You shouldn't have to babysit
  a shared folder" (theirs) beats "We built X after years of..." (yours). The page runs
  promise, proof, ask; a page that asks before it earns loses the stranger. Name the part
  you are judging (hero, subhead, proof, objection, final ask): "the subhead repeats the
  headline" is a ticket, "the hero is weak" is a mood.
- **Claims are checkable:** every adjective is replaced by evidence (a number, a name,
  or a scenario) or cut. "Powerful/seamless/robust/intuitive" are Tells; a figure with
  its scope and source is a Show. Watch vague numbers that look like proof ("up to 10x",
  "many teams", "trusted by thousands"). Keep factual categories ("open-source",
  "native iOS").
- **Buttons name outcomes:** marketing CTA = verb + result + qualifier you can back
  ("Start syncing free"), not "Get started / Learn more / Submit". Cover the page and
  read only the button: if it fits any site unchanged, it names a mechanic, not an
  outcome. One primary action per section; it must keep the headline's promise.
- **Microcopy (labels, errors, empty states):** verb + exact object ("Send invitation",
  not "Submit"); never expose internals; name the object on destructive buttons ("Delete
  3 files"). An error names what happened, why (when known), and the recovery, never a
  raw exception or bare "Something went wrong". An empty state prompts the first action,
  not the void. Ellipsis signals more-is-coming (Rename..., Saving...), not immediate
  actions. An empty slot is an answer, not an omission: show "None" or "Not set", never
  a blank cell.
- **Editing (cut what the sentence lives without):** three kinds of padding are filler
  ("very", "just", "in order to"), qualifiers ("we believe that", "designed to"), and
  repetition. Removal test: does the sentence vanish without losing a claim? Edit one
  lens at a time; flag first, fix after the last pass. The sweep order is load-bearing:
  clarity first, then specificity, zero-risk cuts last.

---

## Lens 3: Typography (how text is set)

- **Voice fits the message:** a typeface speaks before a word is read (sort any face by
  serifs? stress? contrast?). A playful bubble face on a legal-security page makes the
  voice argue with the words, and readers believe the voice. One face, one casing, one
  job per weight, everywhere. One distinctive typographic move, applied everywhere and
  protected across redesigns, beats six half-committed ones.
- **Font quality:** no faux bold (browser-thickened; joints clog, counters shrink) and
  no faked italic (a slant, not a redrawn cursive; check a, f, g). Real families ship
  separate weights. Characters are distinguishable: test `Il1O0` and `rn` vs `m`. Even
  spacing: set `AWAY` large and look for holes (missing kerning).
- **Pairing:** each face has one clear job (display vs text), with genre contrast so the
  change reads as intentional, and matched *stress* so they share one world. Stop at two.
- **Comfortable body text:** measure 45-75 characters (best ~66), size 18-24px desktop
  (15-19 phone), line height 1.4-1.5. Paragraph gap about the size of the text (one
  signal: gap or indent, never both). Subhead sits closer to what it introduces (gap
  above ~3x the gap below).
- **Hierarchy:** any two sizes are identical or clearly different, never nearly the same.
  Size is one lever of four: weight, letterspaced caps, and colour also rank text without
  growing it. Keep ranks few (2-3 cover most screens). Lead with values when the label
  is redundant (the number first, its label quieter), and keep dense link lists calm
  instead of painting every word as a link.
- **Finish / details:** clean rag (avoid justified on web and centred past a line or two);
  no stranded widow in a headline; curly quotes and apostrophes in prose; the right dash
  per job (hyphen joins, en dash ranges 2020-2024, em dash for asides but keep one style);
  ligatures on; real small caps; **tabular figures** for columns/counters (one shared
  width) and proportional in prose. Keep a value with its unit ("10 MB" together).
- **Display type tightens:** as type grows, pull letter-spacing and leading in (leading
  toward ~1.1) so a headline reads as one object. Capitals are the exception that wants
  more air. Body text wants no adjustment at all.

---

## Lens 4: Craft (space, colour, edges, polish)

- **Look chosen under constraints (first):** a look is not a mood board, it is the
  agreement between type, colour, corner radius, and the words on the buttons. Friendly
  and round, or sharp and quiet; casual verbs or formal ones; one accent, not five. Four
  prompts in one afternoon give you four personalities fighting on one surface. Pick the
  look on purpose before polishing, then limit the menu: a handful of type sizes (not
  nineteen-pixel one-offs), a few weights, one radius family, one small colour ramp. If
  you cannot name which step on the short list a value came from, it is a guess: replace
  the guess with a pick. Constraint is not austerity, it is how decision fatigue stops
  showing up as drift.
- **Space by relationship:** close = related, far = separate. Two gap sizes do the work
  (small 4-8 inside a unit, bigger 24-32 between). Never two gaps that nearly match. The
  classic failure is a form label floating equidistant between two fields; pull it tight
  to its own field.
- **Alignment / edges:** hang elements from as few shared left lines as possible (squint
  and count verticals: two is calm, five is noise). Optical over mathematical centring:
  centre by mass (a play triangle in a round button nudges toward its point).
- **Corners agree:** a nested (inner) radius = outer radius minus the padding between
  them. Equal inner and outer radii pinch; if space > outer radius, the inner goes square.
- **Colour system is small and strict:** one family of quiet shades that share lightness
  steps (siblings), one accent with one job. Five accent colours read as none. Pull the
  endpoints in (near-black on near-white, not pure black on pure white) but keep body
  text above 4.5:1 contrast. Tint neutrals toward the page: never park a cool grey on a
  saturated fill, it turns muddy. Prefer OKLCH for even ramps.
- **Room to breathe:** cramped is the default of AI output and of tired humans filling
  a frame, so the fix runs backwards from instinct: add air until groups read, then
  tighten until it feels intentional. Related items stay close; separate sections get a
  gap you could name; when unsure, double the gap (ambiguous gaps look like mistakes,
  generous ones look like calm you can edit down). You do not have to fill the screen: a
  short form stretched edge to edge makes every field a marathon. Keep forms and reading
  columns content-sized and leave the leftover canvas empty. Test: shrink it to a phone
  column in your head; if it still works, it never needed the desktop stretch.
- **Layout survives stress:** judge by what breaks it, not by flattering content. Demo
  data is never the hard case: test the worst realistic content, the longest real name (truncate/wrap, lesser columns step aside, the action stays
  reachable), the narrowest screen, 200% zoom, and the on-screen keyboard (the active
  field + its button stay visible).
- **Polish / sanding (last):** one slow pass catching values that drifted from their
  systems. Five sweeps: **edges** (a hairline where a near-white block meets a near-white
  page), **shadows** (two layers: a contact line + a wide wash, not one grey smudge),
  **corners** (nested radii share a centre), **gaps** (sibling gaps match to the pixel),
  **colour** (every colour traces to one palette step). Prefer space, background or
  shadow over border soup; use accent borders and overlap sparingly, for rank and depth.
  Every line, shadow, corner, gap and colour should name its purpose and its system;
  anything that cannot is drift. No single mistake, ten small ones, is what reads a grade
  cheaper.

---

## Lens 5: Interaction (what it does under your hands)

- **Invisible states made visible:** a pressed state answers the press itself (dip/darken)
  or people press twice and double-fire. Focus is always visible (focus ring), stays
  inside an open dialog, and returns to the trigger on close. Cursor honesty: a pointing
  hand only over things that click; if a whole row lights up, the whole row presses.
- **Page holds its shape while loading:** reserve space for content that arrives late
  (no layout shift), use a skeleton over a bare spinner across a region, and show text in
  a matched font stand-in so a heading never blanks.
- **Targets:** a control's real size is the area that responds. Visible mark can be ~16px
  but the touch area a forgiving ~44px (a fingertip covers ~1cm). Kill dead zones between
  tappable rows (grow targets until they meet). Where two targets overlap, decide which
  one owns each pixel. During a gesture follow the finger; on release respect distance
  and speed.
- **Forms that respect you:** labels stay visible while typing (placeholders only show
  the shape of an answer). A failed submit keeps every value, marks the exact field, and
  says how to fix it right beside the problem. Enter submits a short form, paste always
  works, the submit button stays pressable so it points at what is missing. Right keyboard
  per field; body/input text >=16px so iOS does not zoom. Never fix a zoom problem by
  disabling zoom.
- **Feedback where attention is:** acknowledge every press at once, lock the control
  while the work runs (or the silence buys you a second press), show a spinner only past
  ~200ms. A spinner claims "this is taking a while"; shown for a 40ms request it lies, and
  people tally small lies. Put the confirmation on the thing acted on (the button that
  copied says "Copied"); float a message only for events with no button to answer from.
  Feedback lasts as long as the work: a two-minute job needs a place (a progress row, a
  status), not a flash.
- **Access (finish the task three ways):** by keyboard (ring visible), by screen reader
  (every icon-only control has an accessible name in the words you would print on a text
  button), and in bad light (body text >=4.5:1, large >=3:1; colour never signals alone,
  pair it with an icon/word/underline). Anything revealed on hover is revealed on
  focus, and anything shown is also announced. A green automated audit checks parts; only
  finishing the task proves the flow works.

---

## Lens 6: Animation (motion that explains change)

Runs last. Motion is a cost paid every time it plays; spend it only where it does a
nameable job. Make everything else instant.

- **Purpose test, four jobs:** feedback (an action landed), orientation (where something
  lives), continuity (keep your place), delight (rare personality on purpose). No job ->
  instant. "It looks nice" is not a job.
- **Frequency test:** the more often it plays, the less it may move. Keyboard/shortcut
  actions get none (a shortcut has already decided what happens, so movement can only
  delay it); hovers/selection barely; drawers/dialogs/toasts enough to explain;
  onboarding/milestones is where delight lives. Scroll effects usually fail both tests.
- **Shape of one movement:** easing is *how* it spends time, duration is *how long*.
  Anything answering an action starts fast and settles gently; exits run quicker than
  entrances (the person already decided). Rough anchors: button ack <100ms; tooltips/menus
  150-200ms; drawers/dialogs 250-300ms. Under ~200ms reads as immediate. Constant speed
  reads mechanical unless it reports real progress (an upload bar).
- **Choreography:** anchored things grow from their trigger (menu from the button's
  corner), only full-screen elements earn a centre entrance, nothing starts from zero
  size (start ~90%). Direction carries meaning (forward from ahead, back from behind).
  Stagger under ~50ms per item and judge the total until the last item is usable; long
  lists stagger the first handful then land the rest together.
- **Comfort / stand-down:** motion never blocks input (interruptible, bends mid-flight).
  Honour reduced-motion (swap the swoop for a fade, keep every state change legible).
  Daily actions earn no flourish. Loops move only while they say something true and pause
  off-screen.

---

## Prioritise, then brief

After the six sweeps you will have more findings than can be fixed at once. Rank each by
**harm x frequency x reach** (see `report-template.md`), fix by cost not visibility, and
turn the top ones into three-part briefs (see `briefs.md`). Motion findings almost never
outrank a product-design or copy finding: fix behaviour and words first.
