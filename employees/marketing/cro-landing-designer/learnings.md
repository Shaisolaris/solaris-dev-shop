# CRO + Landing Designer - Learnings (Pending)

## Pending observations
- **2026-04-25 - Clean rebuild from alirezarezvani sales_playbook + wshobson interaction-design**: 8-stage funnel discipline (Lead → Close with entry/exit criteria + owner + benchmark per stage) is the most under-applied CRO framework.
- **2026-04-25 - Hypothesis-before-test + MDE-pre-calc** are the two test discipline rules that determine whether you ship learnings or noise.

- **2026-06-09 - v0.4.0 rebuild from sickn33/alirezarezvani CRO suite + VoltAgent ab-test-analysis**: the readiness gate (Page Conversion Readiness Index <70 = refuse to A/B test) is the single biggest upgrade - it converts "fix our 1% page" requests from test-roulette into ordered diagnosis. Second: SRM check before reading any result.
- **2026-06-09 - Sample-size reality**: detecting a 5% relative lift on a 1% baseline costs ~1.5M visitors/variant. Low-traffic pages must test big swings (offer, hero, layout) or not test at all.

- **2026-06-13 - v0.5.0 depth pass**: operationalized the three statistics rules that were named but not actionable. SRM now has a concrete chi-square test + p<0.001 flag threshold (was "detect SRM" with no method). "No peeking" now has its principled escape hatch (sequential / always-valid p-values declared at design time). CUPED registered as the low-traffic lever - the real answer to "this page is untestable," when a correlated pre-period covariate exists.
- **2026-06-13 - Behavioral signals got a vocabulary**: rage click / dead click / dead zone / quick-back / scroll cliff now map to specific readiness categories, so "watch session replays" becomes prioritizable diagnosis. Always segment maps by device + source first.
- **2026-06-13 - Phantom-ref cleanup**: frameworks.md never existed; the two referenced scripts (conversion_audit.py, sample_size_calculator.py) are upstream-only and were being presented as runnable. Reframed as external tools + added an inline pooled sample-size formula so the employee can size a test with no script present.
- **2026-06-13 - Sample-size table provenance**: the anchor table is faithful to its cited source (alirezarezvani sample-size-guide.md) but those figures run ~2x a textbook pooled calc. Documented as conservative go/no-go anchors, not the committed number.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| 2026-06-13 | SRM chi-square + p<0.001 gate | rules.md A/B section + depth §3 |
| 2026-06-13 | Small-task/prototype lane | rules.md (skips full gate for no-traffic/one-off work) |
| 2026-06-13 | CUPED low-traffic lever | rules.md A/B section + depth §1 |
## Sources

- Upstream: growthbook/growthbook (NOASSERTION (FLAG) - open-core: core MIT, enterprise/ dirs under a separate commercial); PostHog (NOASSERTION (FLAG) - MIT core + ee/ enterprise dir; experimentation/replay usable); OpenReplay (NOASSERTION (FLAG) - core Apache-2.0 per vendor docs; repo ships an ee/ enterprise dir); Microsoft Clarity (MIT (clean - permissive, preferred)); Unleash (AGPL-3.0 (FLAG))
- What was used: noted: growthbook/growthbook, PostHog, OpenReplay, Microsoft Clarity, Unleash
- License notes: growthbook/growthbook: NOASSERTION (FLAG) - open-core: core MIT, enterprise/ dirs under a separate commercial; PostHog: NOASSERTION (FLAG) - MIT core + ee/ enterprise dir; experimentation/replay usable; OpenReplay: NOASSERTION (FLAG) - core Apache-2.0 per vendor docs; repo ships an ee/ enterprise dir; Unleash: AGPL-3.0 (FLAG)
