# Verification and Tokens - methodology reference

Distilled methodology (no code vendored) from four verified 2026 sources. Operationalizes the gates that rules.md asserts but did not previously make executable: CWV measurement (rules.md §1), the WCAG floor (§1, §7), the money-flow E2E lane (§9), and the design-token pipeline (design-to-code.md §3).

Sources, all verified 2026-06-13:
- GoogleChrome/web-vitals (Apache-2.0, 8.5k★) - field + lab CWV measurement.
- dequelabs/axe-core (MPL-2.0, 7.2k★) - automated a11y verification. **MPL is weak copyleft; methodology only, never vendor the source. Self-host note below.**
- microsoft/playwright (Apache-2.0, 90k★) - money-flow E2E.
- style-dictionary/style-dictionary (Apache-2.0, 4.7k★) - token build pipeline.

---

## 1. Core Web Vitals - measure, don't assert (web-vitals)
rules.md §1 demands LCP/INP/CLS numbers at p75 on the primary device. This is how those numbers are actually obtained.

- **Two surfaces, both required.** Lab (Lighthouse/CI, controlled, reproducible - catches regressions pre-merge) and **field/RUM** (real users, the only source of a true p75). A green lab score with a red field p75 means your throttling profile does not match real users - trust the field number.
- **Field collection.** The `web-vitals` library (~2KB) exposes `onLCP`, `onINP`, `onCLS` (and `onTTFB`, `onFCP`). Each takes a callback fired when the metric settles; ship the metric to your analytics endpoint (batch on `visibilitychange`/`pagehide`, not per-event). Its numbers match CrUX / PageSpeed Insights / Search Console by construction - do not hand-roll PerformanceObserver math.
- **Attribution build for diagnosis.** Import from `web-vitals/attribution` to get `metric.attribution`: `attribution.element` (the LCP node), `attribution.interactionTarget` (the slow INP handler's element), `attribution.largestShiftTarget` (the node that shifted). This converts "INP is 400ms" into "this specific button's click handler" - feed it straight into the rules.md §6 perf ladder (a slow INP target is usually a re-render or main-thread-blocking handler; a bad LCP element is usually an unoptimized image or a render-blocking font).
- **The loop:** field RUM finds the regression at p75 → attribution names the element → fix per the §6 tier the element points to → confirm in the next field window. Lab CI prevents re-regression.
- **Gate:** a route with no field measurement plan is not "done" - the §1 numbers must come from somewhere. Lab-only is acceptable only for pre-launch surfaces with no users yet.

## 2. Automated accessibility - make the WCAG floor a gate (axe-core)
rules.md §1 declares a WCAG target (2.2 AA default) and §7 lists the contracts. axe-core verifies them mechanically so the floor is enforced, not hoped for.

- **What it is.** The engine behind Lighthouse's a11y category, `jest-axe`, and `@axe-core/playwright`. It evaluates the live DOM against WCAG rules and returns structured violations (id, impact severity, the failing nodes, the guideline reference).
- **Scope to the declared target.** `withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa'])` runs exactly the rules for the WCAG level §1 committed to - no noise from best-practice-only rules unless you opt in. `withRules`/`disableRules` for targeted runs.
- **Where it runs.** Component level: `jest-axe` / `vitest-axe` on rendered RTL output (catches missing labels, bad contrast, roles before the component ever ships). E2E level: `@axe-core/playwright`'s `AxeBuilder` auto-injects (no manual `injectAxe`) and scans real pages mid-flow.
- **Honest limit.** Automated scanning catches ~30-50% of WCAG issues (the mechanical ones). It does **not** replace the rules.md §7 manual contracts - keyboard-only walk, focus-trap-on-modal, screen-reader announcement of `role="alert"` errors, "meaning not by color alone." axe is the floor; the manual walk is the ceiling.
- **Self-host / license note (MPL-2.0).** axe-core is weak copyleft at file level. We absorb only *how to run and gate it* - we do not vendor or modify its source, so no copyleft obligation triggers. It is consumed as an unmodified dev dependency (npm) or run via Lighthouse; if a client requires a vendored/self-hosted copy, keep it unmodified and isolated so the MPL boundary stays clean.

## 3. Money-flow E2E - the Playwright lane (Playwright)
rules.md §9 reserves E2E for money flows (checkout, auth, publish). This is the actual method, previously only a noun.

- **Locators mirror the a11y rules.** Prefer `getByRole`, `getByLabel`, `getByText` over CSS/test-id selectors - same principle as the RTL byRole rule (§9): if the test can't find an element by its accessible name, neither can a screen reader. Fall back to the documented `data-testid` scheme (§9 handoff) only for elements with no accessible identity.
- **Web-first assertions kill flake.** `expect(locator).toBeVisible()` auto-waits and retries; never `waitForTimeout`. This is why §9 says Playwright, not the brittle alternatives.
- **What to actually cover (money flows only):** the happy path end-to-end (fill → submit → assert the network call fired AND the success UI rendered), plus the one or two failure branches that lose money or lock users out (declined payment, expired session, duplicate submit). Not every page - §9's scope discipline holds.
- **Diagnosis + a11y in the same lane.** Trace viewer (`--trace on`) gives a DOM+network+screenshot timeline for CI failures. Drop `@axe-core/playwright` into the same flow to assert accessibility *during* the money flow, not just on static pages.
- **Cross-engine when it matters.** Projects for Chromium/Firefox/WebKit; enable WebKit when iOS Safari is in the §1 primary-device set.

## 4. Design-token pipeline - Figma values to platform code (Style Dictionary)
design-to-code.md §3 says "lift tokens, never literals" and rules.md §3 consumes them via CVA/`cn()`. Style Dictionary is the build step between those two that was missing.

- **One source, many outputs.** A single token source (W3C/DTCG-format JSON - the emerging standard the Figma token plugins export) is transformed once into every platform target: Tailwind theme extension, CSS custom properties, TS const objects, iOS/Android if the design system spans native.
- **Transforms + formats.** *Transforms* normalize values (hex → rgba, px → rem, name casing). *Formats* serialize the transformed tree into the output file shape (CSS vars block, JS module, Tailwind config fragment). Custom transforms/formats are first-class - the system is built to extend.
- **Closes the design-to-code chain.** Figma node values (design-to-code.md step 1-3) → DTCG token JSON → Style Dictionary build → Tailwind theme / CSS vars → consumed by CVA variants and `cn()` (rules.md §3). A raw `#3B82F6` in component output (the design-to-code.md "bug") now has a named home: the token name resolves through the generated theme.
- **Tiers.** Keep tokens in tiers - primitive (`blue-500`) → semantic (`color-primary`) → component (`button-bg`). Components consume semantic/component tokens only, so a rebrand re-points semantics without touching components.
- **When this is overkill.** Single-platform Tailwind-only projects with a stable palette can stay with `tailwind.config` directly; introduce the pipeline when tokens are multi-platform, exported from Figma, or shared across repos.

---

## Where these plug into existing methodology
- web-vitals → rules.md §1 (CWV numbers), §6 (attribution feeds the perf ladder), Definition of Done.
- axe-core → rules.md §1 (WCAG floor as a gate), §7 (verifies the contracts mechanically), Definition of Done.
- Playwright → rules.md §9 (operationalizes the money-flow E2E line), QA handoff.
- Style Dictionary → design-to-code.md §3 + rules.md §3 (the token build between Figma values and CVA consumption).
