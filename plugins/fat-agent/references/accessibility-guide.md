# Accessibility Quick Reference

WCAG 2.1 essentials for FAT Agent audits. Focused on the checks that can be
performed from HTML analysis and targeted user questions.

## Level A — Must Have

### Perceivable

**1.1.1 Non-text Content**
- All `<img>` have meaningful `alt` text
- Decorative images use `alt=""` (empty alt)
- Icons have `aria-label` or visually hidden text
- `<svg>` elements have `<title>` or `aria-label`

**1.3.1 Info and Relationships**
- Form inputs have `<label>` with matching `for` attribute
- Tables use `<th>` for headers
- Lists use `<ul>`, `<ol>`, `<dl>` — not styled divs
- Headings reflect document structure

**1.4.1 Use of Colour**
- Information isn't conveyed by colour alone
- Links are distinguishable from surrounding text (not just by colour)
- Error states have text indicators, not just red borders

### Operable

**2.1.1 Keyboard**
- All interactive elements are keyboard-accessible
- No keyboard traps (user can always Tab away)
- Custom widgets have appropriate keyboard handlers

**2.4.1 Bypass Blocks**
- Skip navigation link present (`<a href="#main">Skip to content</a>`)
- Main content area has `id="main"` or `<main>` element

**2.4.2 Page Titled**
- Every page has a unique, descriptive `<title>`

**2.4.4 Link Purpose**
- Link text describes the destination
- No "click here" or "read more" without context

### Understandable

**3.1.1 Language of Page**
- `<html lang="en">` (or appropriate language code)

**3.3.2 Labels or Instructions**
- Form fields have visible labels
- Required fields are indicated

### Robust

**4.1.2 Name, Role, Value**
- Custom UI components have ARIA roles
- Dynamic content updates use `aria-live` regions

---

## Level AA — Should Have (Recommended)

### Key additions over Level A

**1.4.3 Contrast (Minimum)**
- Text: 4.5:1 contrast ratio against background
- Large text (18px+ or 14px+ bold): 3:1 ratio
- **Cannot be checked from HTML alone** — ask the user

**1.4.4 Resize Text**
- Page remains usable at 200% zoom
- No horizontal scrolling at 320px viewport width

**2.4.7 Focus Visible**
- Interactive elements have visible focus indicators
- Default browser focus outlines not removed without replacement

**1.4.11 Non-text Contrast**
- UI components and graphical objects: 3:1 ratio against adjacent colours

---

## HTML-Checkable Items

These can be verified by analysing the HTML response:

| Check | How to Detect |
|-------|---------------|
| Image alt text | All `<img>` have non-empty `alt` or `alt=""` for decorative |
| Language attribute | `<html>` has `lang` attribute |
| Page title | `<title>` exists and is non-empty |
| Form labels | `<input>`, `<select>`, `<textarea>` have associated `<label>` or `aria-label` |
| Heading structure | h1-h6 hierarchy, single h1 |
| Skip link | First `<a>` in body points to `#main` or `#content` |
| Landmark roles | `<main>`, `<nav>`, `<header>`, `<footer>` present |
| ARIA on custom widgets | Custom interactive elements have `role`, `aria-*` attributes |
| Table headers | `<table>` elements contain `<th>` |
| Viewport meta | `<meta name="viewport">` doesn't disable zoom |
| Zoom not disabled | No `user-scalable=no` or `maximum-scale=1` in viewport |
| Tabindex | No `tabindex > 0` values (disrupts natural order) |
| Autoplay media | `<video autoplay>` / `<audio autoplay>` has `muted` attribute |
| ARIA roles | All `role` values are valid WAI-ARIA 1.2 roles |
| Table headers | `<table>` elements contain `<th>` header cells |
| SVG accessibility | `<svg>` has `<title>` child or `aria-label` attribute |
| iframe titles | `<iframe>` has `title` attribute |
| Button/link semantics | No `<a role="button">` pattern (use `<button>` instead) |
| Reduced motion | `prefers-reduced-motion` media query present in styles |
| Form error association | Form inputs use `aria-describedby` for error messages |

## Fake Affordances

A "fake affordance" is a non-interactive element (`<div>`, `<span>`) styled to look
clickable — using `cursor: pointer`, hover effects, or CSS classes like `btn`,
`button`, `link`, or `clickable` — but that has no `href`, `onclick`, or interactive
ARIA role (`role="button"` / `role="link"`).

**Why they're harmful:**
- Users click expecting something to happen — nothing does. This erodes trust.
- Screen readers announce no interactive role, so keyboard/AT users can't reach them.
- Mobile users see tap-highlight feedback with no result — a classic UX trap.

**How to detect (automated):**
- Flag `<div>` or `<span>` with classes containing `hover`, `clickable`, `pointer`,
  `btn`, `button`, or `link`, or with inline `cursor: pointer` / `cursor:pointer`.
- Exclude elements that already have `onclick`, `role="button"`, or `role="link"`.

**How to fix:**
- If the element should be clickable, make it a `<button>` or `<a href="...">`.
- If it triggers JavaScript, add `role="button"`, `tabindex="0"`, and a `keydown`
  handler for Enter/Space.
- If the styling is purely decorative (no intended interaction), remove the pointer
  cursor and hover effects to avoid misleading users.

---

## User-Prompted Checks

These require user verification:

| Check | Question to Ask |
|-------|----------------|
| Colour contrast | "Are you using light text on light backgrounds anywhere?" |
| Focus styles | "Have you customised or removed focus outlines on buttons/links?" |
| Keyboard navigation | "Can you Tab through your entire page and reach all interactive elements?" |
| Screen reader testing | "Have you tested with a screen reader (VoiceOver, NVDA)?" |
| Motion/animation | "Do you have animations that can't be paused or disabled?" |
| Reduced motion | "Do you have reduced motion alternatives for animations?" |
| Touch targets | "Are interactive elements at least 44x44px touch targets?" |
| Form errors | "Do you have error messages associated with form fields using aria-describedby?" |
| Auto-playing media | "Is there any auto-playing video or audio on the site?" |

## Scoring

| Category | Points |
|----------|--------|
| Images with alt text | 20 |
| Language attribute | 5 |
| Form accessibility | 15 |
| Heading structure | 10 |
| Skip navigation | 5 |
| Landmark regions | 10 |
| Keyboard accessibility (user-reported) | 15 |
| Focus visibility (user-reported) | 10 |
| Contrast (user-reported) | 10 |
| **Total** | **100** |
