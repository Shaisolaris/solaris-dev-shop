# Frontend Developer - Top-5 Source Candidates (verified 2026-06-13)

Verification: GitHub REST API for stars/license/last-push; methodology cross-checked against official docs. Gate-0 = grep of this employee's actual current content (SKILL.md, rules.md, design-to-code.md, plugin.json).

| # | Source | Stars | License | Last commit | Maintainer | Gate-0 verdict | Tag |
|---|--------|-------|---------|-------------|------------|----------------|-----|
| 1 | GoogleChrome/web-vitals | 8,531 | Apache-2.0 | 2026-06-10 | Google Chrome team | NET-NEW (CWV targets present, field/lab measurement absent) | METHODOLOGY |
| 2 | dequelabs/axe-core | 7,237 | MPL-2.0 (flag) | 2026-06-12 | Deque Systems | NET-NEW (a11y contracts present, automated verification absent) | METHODOLOGY |
| 3 | microsoft/playwright | 90,887 | Apache-2.0 | 2026-06-12 | Microsoft | PARTIAL (named only, zero method) | METHODOLOGY |
| 4 | style-dictionary/style-dictionary | 4,691 | Apache-2.0 | 2026-06-10 | Style Dictionary org (ex-amzn) | PARTIAL ("tokens not literals" present, no token pipeline) | METHODOLOGY |
| 5 | TanStack/query | 49,740 | MIT | 2026-06-12 | Tanner Linsley / TanStack | CONTENT-DUPLICATE (stack default + state ladder rung 7 + perf tier 4) | CONNECT |

---

## 1. GoogleChrome/web-vitals - METHODOLOGY
- URL: https://github.com/GoogleChrome/web-vitals
- Stars 8,531 · Apache-2.0 (permissive) · pushed 2026-06-10 · maintained by the Chrome team.
- What it adds: the employee states LCP/INP/CLS *targets* everywhere but never says **how to measure them on real users**. web-vitals is the canonical ~2KB library whose numbers match CrUX / PageSpeed Insights / Search Console. The `attribution` build (`web-vitals/attribution`) names the actual offending element (`attribution.element` for LCP, `interactionTarget` for INP, `largestShiftTarget` for CLS), turning "INP is bad" into "this button's handler is the regression." Closes the lab-only blind spot: lab Lighthouse vs field RUM at p75.
- Gate-0: grep for `web-vitals`/`RUM`/`real user` = zero hits. Net-new.
- Verdict: ABSORB as methodology (field + lab + attribution loop). Permissive, safe.

## 2. dequelabs/axe-core - METHODOLOGY (license flag: MPL-2.0)
- URL: https://github.com/dequelabs/axe-core
- Stars 7,237 · **MPL-2.0** (weak copyleft - flag) · pushed 2026-06-12 · Deque Systems (the reference a11y vendor).
- What it adds: the employee has strong a11y *contracts* (modal/form/focus) but no way to *verify* them automatically. axe-core is the engine behind Lighthouse a11y, jest-axe, and `@axe-core/playwright`. `withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa'])` scopes a scan to exactly the declared WCAG target (rules.md §1's "WCAG 2.2 AA"), returning structured violations with severity + guideline refs. Makes the WCAG floor a CI gate, not an aspiration.
- License note: MPL-2.0 is file-level copyleft. We absorb **methodology only** (how to run/scope/gate), never vendor the source, so no copyleft obligation triggers. Self-host note added to reference.
- Gate-0: grep for `axe`/`automated a11y` = zero hits. Net-new.
- Verdict: ABSORB methodology only (MPL flagged, methodology-safe).

## 3. microsoft/playwright - METHODOLOGY
- URL: https://github.com/microsoft/playwright
- Stars 90,887 · Apache-2.0 (permissive) · pushed 2026-06-12 · Microsoft.
- What it adds: the employee names "Playwright (money flows)" twice but carries **zero** actual E2E methodology. Adds: `getByRole`/`getByLabel` locators (a11y-tree-first, mirror the RTL byRole rule), web-first auto-waiting assertions (kills flake), trace viewer for CI debugging, `@axe-core/playwright` for a11y-in-E2E, and built-in visual + projection across Chromium/Firefox/WebKit. Operationalizes rules.md §9's "E2E reserved for money flows" line into a real lane.
- Gate-0: `playwright` appears only as a noun, no method. Partial/net-new methodology.
- Verdict: ABSORB methodology. Permissive, safe.

## 4. style-dictionary/style-dictionary - METHODOLOGY
- URL: https://github.com/style-dictionary/style-dictionary
- Stars 4,691 · Apache-2.0 (permissive) · pushed 2026-06-10 · Style Dictionary org (migrated from amzn).
- What it adds: design-to-code.md preaches "lift tokens, never literals" but there's no **token build pipeline**. Style Dictionary is the canonical engine that turns one W3C/DTCG token JSON source into Tailwind theme / CSS vars / TS constants via transforms+formats - the missing link between the Figma node values (design-to-code.md step 3) and the actual `cn()`/CVA consumption in rules.md §3. Completes the Figma → token JSON → platform output chain.
- Gate-0: "design token" appears as a *principle* 5×, but no pipeline/DTCG/transform method. Partial.
- Verdict: ABSORB methodology. Permissive, safe.

## 5. TanStack/query - CONNECT (already absorbed)
- URL: https://github.com/TanStack/query
- Stars 49,740 · MIT (permissive) · pushed 2026-06-12 · TanStack.
- What it adds: nothing net-new - it is already the server-state default (SKILL stack line), state-ladder rung 7, and perf tier 4. Listed here as the verified anchor for the server-state lane so the dependency is on the books with current metadata.
- Gate-0: heavy existing coverage. CONTENT-DUPLICATE.
- Verdict: CONNECT only (no new content); confirms the existing choice is current and MIT-safe.

---

## Considered and rejected (already covered - content-duplicate)
- **testing-library/react-testing-library** (MIT, 19.6k★, 2026-04-02): byRole/byLabelText/userEvent already in rules.md §9. Duplicate.
- **pmndrs/zustand** (MIT, 58k★): already the client-state default. Duplicate.
- **shadcn-ui/ui** (MIT, 116k★) / **radix-ui/primitives** (MIT, 19k★): shadcn is the component default; Radix is its substrate. Duplicate.
- **GoogleChrome/lighthouse** (Apache-2.0, 30k★): the lab side is referenced; web-vitals (#1) adds the missing field side, so Lighthouse is folded into the CWV methodology rather than listed separately.
