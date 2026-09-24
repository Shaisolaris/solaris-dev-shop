# Web Interface Compliance and Quality Checklist - methodology reference

Net-new depth pass 2026-06-15 (methodology only, no code vendored). Absorbed from vercel-labs/agent-skills, the `web-design-guidelines` skill and its canonical source `vercel-labs/web-interface-guidelines/command.md` (the Web Interface Guidelines). Source: vercel-labs/agent-skills (MIT, official Vercel, ~27.6k stars, 233 commits, active, verified 2026-06-15).

This is the granular, line-level **interaction-quality and accessibility compliance checklist** the designer can run as a pre-delivery acceptance gate and hand to frontend-developer as the implementation spec. It is the designer-facing companion to the same guidelines frontend-developer references for code review.

## Gate-0 - why this is net-new (not a duplicate)
The employee already carries two design-quality layers:
- **design-intelligence DB priority checklist 1-to-10** (rules.md) - a PRIORITIZED, category-level checklist (accessibility / touch / performance / style / layout / typography / animation / forms / navigation / charts) used to triage a build. It is a triage ladder, not a line-level spec.
- **design-taste-heuristics.md** (Leonxlnx/taste-skill) - anti-slop / taste / high-agency JUDGMENT heuristics (the Design Read, the three dials, layout anti-slop, copy self-audit). It is about whether the direction is RIGHT and off the LLM-default rails.

Neither carries the granular, mechanical, item-by-item interaction-quality acceptance list below - the specific things like `touch-action: manipulation`, `overscroll-behavior: contain` in modals, never-block-paste, `min-w-0` for flex truncation, `translate="no"` on brand names, `color-scheme` on the root, `inputmode` per field, spellcheck-off on emails/codes, placeholders ending in an ellipsis with an example pattern, `text-wrap: balance` on headings, tabular figures for number columns, focus-the-first-error-on-submit. These are the deliverable-level details a designer must SPEC and then VERIFY, and the design QA + handoff section did not enumerate them. So: net-new, complements both existing layers.

How the three fit together: the DB checklist triages WHAT to prioritize; taste-heuristics decides if the direction is right; THIS list is the mechanical acceptance gate that says the chosen, well-directed design is actually correct and accessible at the detail level. Run all three; this one is last, before sign-off.

---

## How to use this
- **As a spec layer:** when writing the design QA + handoff spec sheet, attach the relevant items below per component/screen so frontend implements them on the first pass instead of being caught in review.
- **As an acceptance gate:** before sign-off, walk the checklist for the delivered UI. Accessibility and the destructive-action items are ship-blockers (consistent with the DB checklist marking accessibility + touch CRITICAL).
- Output findings in the terse `file:line - finding` format frontend-developer already uses, so the two employees speak the same review language.

---

## Accessibility (ship-blockers)
- Icon-only buttons need an accessible label (`aria-label`); decorative icons get `aria-hidden="true"`.
- Every form control has a real `<label>` (or `aria-label`); a placeholder is never a label.
- Interactive elements have keyboard handlers, not pointer-only behavior.
- `<button>` for actions, `<a>`/link for navigation - never a `<div>`/`<span>` with a click handler.
- Images have `alt` (or `alt=""` if purely decorative).
- Async updates (toasts, inline validation, live results) announce via `aria-live="polite"`.
- Semantic HTML first (`<button>`, `<a>`, `<label>`, `<table>`, `<nav>`, `<main>`), ARIA only to fill gaps.
- Headings are hierarchical `<h1>`-`<h6>`; provide a skip-to-content link; heading anchors get `scroll-margin-top`.

## Focus states (ship-blockers)
- Every interactive element has a VISIBLE focus indicator; `outline: none` without a replacement is a violation.
- Prefer `:focus-visible` over `:focus` so the ring shows on keyboard, not on mouse click.
- Compound controls group focus with `:focus-within`.

## Forms (interaction quality)
- Inputs set `autocomplete` and a meaningful `name`; use the correct `type` (`email`, `tel`, `url`, `number`) and `inputmode`.
- Never block paste (`onPaste` + `preventDefault` is banned - it breaks password managers and long inputs).
- Labels are clickable (wrap the control or use `htmlFor`); checkbox/radio + label share one hit target with no dead zones.
- Turn spellcheck OFF on emails, codes, usernames (`spellcheck={false}`).
- Submit button stays enabled until the request starts, then shows a spinner; do not pre-disable.
- Errors render inline next to the field; focus the FIRST error on submit; the message states the fix, not just the problem.
- Placeholders end with an ellipsis and show an example pattern (not a restatement of the label).
- Warn before navigating away from unsaved changes.

## Animation (interaction quality)
- Honor `prefers-reduced-motion` (provide a reduced variant or disable).
- Animate `transform`/`opacity` only (compositor-friendly); never `transition: all` - list properties explicitly.
- Set the correct `transform-origin`; for SVG animate a `<g>` wrapper with `transform-box: fill-box`.
- Animations are interruptible - they respond to user input mid-flight rather than locking the UI.

## Typography (polish)
- Use the ellipsis character, not three dots; curly quotes, not straight quotes.
- Non-breaking spaces in `10 MB`, shortcut hints, and brand names so they do not wrap awkwardly.
- Loading states end with an ellipsis ("Loading...", "Saving...").
- `font-variant-numeric: tabular-nums` for number columns and any compared figures.
- `text-wrap: balance` / `text-pretty` on headings to prevent widows.

## Content handling (robustness)
- Text containers handle long content: truncate, `line-clamp`, or `break-words` as appropriate.
- Flex children that should truncate need `min-w-0` (the single most-missed truncation bug).
- Design and SPEC the empty state - do not let empty strings/arrays render broken UI.
- User-generated content is specced for short, average, AND very long inputs.

## Images and performance (CLS and load)
- `<img>` carries explicit `width` and `height` to reserve space (prevents layout shift).
- Below-fold images lazy-load; the above-fold critical image is prioritized.
- Lists over ~50 items virtualize (this is where the ui-ux-designer headless-table / virtualization knowledge meets the spec).
- No layout reads in render paths; add `preconnect` for CDN/asset domains; preload critical fonts with `font-display: swap`.

## Navigation and state (deep-linkability)
- URL reflects state - filters, tabs, pagination, expanded panels live in query params so a view is shareable and back-button works.
- Stateful UI is deep-linkable; links are real `<a>`/link elements so Cmd/Ctrl-click and middle-click work.
- Destructive actions require a confirmation or an undo window - never fire immediately and irreversibly.

## Touch and interaction (mobile quality)
- `touch-action: manipulation` to kill the double-tap-zoom delay; set `-webkit-tap-highlight-color` intentionally.
- `overscroll-behavior: contain` inside modals/drawers/sheets so the page behind does not scroll.
- During drag, disable text selection and mark dragged elements `inert`.
- Use `autofocus` sparingly - desktop only, single primary input; avoid on mobile (it forces the keyboard up).
- Touch targets meet the existing 44x44pt iOS / 48x48dp Android minimum (reinforces the DB checklist).

## Safe areas and layout (device fit)
- Full-bleed layouts use `env(safe-area-inset-*)` for notches / home indicator / Dynamic Island (reinforces the iOS section in SKILL.md).
- Prevent unwanted horizontal scrollbars; prefer flex/grid over JS measurement for layout.

## Dark mode and theming (correctness)
- Set `color-scheme` on the root for dark themes so native scrollbars and form controls match.
- `<meta name="theme-color">` matches the page background.
- Native `<select>` gets explicit `background-color` and `color` (Windows dark mode renders it wrong otherwise).
- (Pairs with the existing rule: dark mode is a re-toned contrast story via tokens, never a hue inversion.)

## Locale and i18n (correctness)
- Dates/times via `Intl.DateTimeFormat`, numbers/currency via `Intl.NumberFormat` - never hardcoded formats.
- Detect language from `Accept-Language` / `navigator.languages`, not from IP.
- Wrap brand names, code tokens, and identifiers with `translate="no"` so auto-translation does not garble them.

## Hover and interactive states (feedback)
- Buttons/links have a `hover:` state; hover/active/focus increase contrast over the resting state (the feedback must be visible, not subtle).
- Implement FULL state cycles, not just the static success state: skeleton (shaped like the final layout), empty, error, and a tactile `:active` (reinforces the taste-heuristics state-cycle rule).

## Content and copy (clarity)
- Active voice; specific button labels ("Save API Key", not "Continue"); numerals for counts.
- Error messages include the fix / next step. Second person, avoid first person.

## Anti-patterns to flag and reject
- `user-scalable=no` / `maximum-scale=1` (disables zoom - an accessibility failure).
- `onPaste` + `preventDefault`; `transition: all`; `outline: none` with no focus replacement.
- Click handlers on `<div>`/`<span>`; inline `onClick` navigation without a real link.
- Images without dimensions; large lists mapped without virtualization.
- Inputs without labels; icon buttons without `aria-label`; hardcoded date/number formats; unjustified `autofocus`.

---

## Relationship to the existing layers (one line each)
- design-intelligence DB priority checklist (rules.md): triages WHAT matters most - run first.
- design-taste-heuristics.md: judges whether the direction is RIGHT and off the LLM-default rails - run during design.
- THIS checklist: the mechanical, line-level accessibility + interaction-quality acceptance gate - run last, before sign-off, and attach to the handoff spec.
- frontend-developer references the same Web Interface Guidelines for code review (rules.md §7), so a UI specced against this list reviews clean on their side too.

## Source (verified 2026-06-15, methodology only, no code vendored)
- vercel-labs/agent-skills - MIT (official Vercel) - ~27.6k stars - 233 commits, active - the `web-design-guidelines` skill + its canonical `vercel-labs/web-interface-guidelines/command.md` (Web Interface Guidelines, 100+ rules across accessibility, focus, forms, animation, typography, content, images, performance, navigation, touch, safe-areas, theming, i18n, hydration, hover, copy, anti-patterns). Distilled here as a designer-facing acceptance checklist; not copied verbatim, no code bundled.
