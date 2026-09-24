# TOP-5 Verified 2026 Sources - CRO + Landing Pages

Research date: 2026-06-13. Star/license/commit via api.github.com (curl, unauthenticated) + vendor docs cross-check. Gate-0 = grep of this employee's current SKILL.md/rules.md/learnings.md/plugin.json for the candidate's distinguishing content.

## Selection criteria
Established + safe; 100+ stars (or 50+ from a notable maintainer); permissive license preferred (GPL/AGPL/NOASSERTION flagged); commit within ~6mo of 2026-06-13.

---

## 1. GrowthBook - Statistics Engine (CUPED, sequential testing, SRM, bandits)
- URL: https://github.com/growthbook/growthbook (docs: https://docs.growthbook.io/statistics/overview)
- Stars: 7,881
- License: NOASSERTION (FLAG) - open-core: core MIT, enterprise/ dirs under a separate commercial license. Public docs methodology is freely readable.
- Last commit: 2026-06-12 (pushed)
- Maintainer: GrowthBook Inc. (180+ contributors; v4.4 May 2026)
- What it adds: the statistical depth the A/B workflow lacks. (a) CUPED variance reduction - up to ~2x faster significance via a pre-experiment lookback, the best answer to the documented low-traffic pain. (b) Sequential testing / always-valid p-values - lets you peek safely, a principled upgrade to the blunt "no peeking" rule. (c) SRM auto-detection - named in rules.md but not operationalized; now given a chi-square test + threshold. (d) Multi-armed bandits (Thompson sampling) - a whole test class absent today.
- Gate-0: ABSENT. CUPED 0, "sequential test" 0, "always-valid" 0, "variance reduction" 0, bandit 0. "GrowthBook" 3x but tool name-drop only. Not a content-duplicate.
- Tag: ABSORB (methodology only; flagged license = methodology + self-host note, no code bundled)

## 2. PostHog
- URL: https://github.com/PostHog/posthog
- Stars: 34,770
- License: NOASSERTION (FLAG) - MIT core + ee/ enterprise dir; experimentation/replay usable self-hosted on the free tier.
- Last commit: 2026-05-30 (pushed)
- Maintainer: PostHog Inc. (very active; 2,790+ forks)
- What it adds: the reference all-in-one self-hosted CRO instrumentation stack - funnels, feature-flag experiments (Bayesian readout), session replay, heatmaps, surveys in one schema. Operationalizes the "instrumentation" + "heatmap/replay from day 1" rules with a concrete free self-hostable backbone. In tags already but never described as the instrumentation reference.
- Gate-0: PARTIAL. "posthog" in tags + tools table as a name; no instrumentation architecture / event taxonomy. Not a content-duplicate.
- Tag: CONNECT (instrumentation reference + methodology; flagged license = self-host note)

## 3. OpenReplay
- URL: https://github.com/openreplay/openreplay
- Stars: 12,098
- License: NOASSERTION (FLAG) - core Apache-2.0 per vendor docs; repo ships an ee/ enterprise dir, hence GitHub reports NOASSERTION. Self-hostable on a small VPS.
- Last commit: 2026-06-12 (pushed)
- Maintainer: OpenReplay (active releases)
- What it adds: behavioral-signal vocabulary the employee lacks - rage clicks, dead clicks/dead zones, click/scroll/interaction maps segmentable by device + source. Turns "watch session replays" into named, prioritizable friction signals feeding the readiness Friction & UX category.
- Gate-0: ABSENT. OpenReplay 0, "rage click" 0, "dead click" 0. Not a content-duplicate.
- Tag: ABSORB (methodology only; flagged license = self-host note)

## 4. Microsoft Clarity
- URL: https://github.com/microsoft/clarity
- Stars: 2,677
- License: MIT (clean - permissive, preferred)
- Last commit: 2026-06-12 (pushed)
- Maintainer: Microsoft (free unlimited tier, no sampling, GDPR/CCPA ready)
- What it adds: the zero-cost zero-sampling heatmap + session-replay default for day-1 instrumentation, plus Clarity friction metrics (rage clicks, dead clicks, excessive scroll, quick-backs). Cleanest license in the set; the safe ship-before-any-test default. Named in rules.md/tags but never positioned as the default or described by its signal set.
- Gate-0: PARTIAL. "Clarity" 5x as a tool name only; no signal taxonomy. Not a content-duplicate.
- Tag: CONNECT (default instrumentation tool + signal taxonomy)

## 5. Unleash
- URL: https://github.com/Unleash/unleash
- Stars: 13,581
- License: AGPL-3.0 (FLAG)
- Last commit: 2026-06-13 (pushed)
- Maintainer: Bricks Software AS / Unleash (mature, enterprise-grade)
- What it adds: feature-flag delivery discipline for safe rollout of test winners - gradual rollouts, kill switches, server-side targeting, flag lifecycle/cleanup. The "winner becomes the new control" step has no rollout-safety method today; Unleash supplies gradual-ramp + instant-rollback. AGPL = methodology only, never bundle code.
- Gate-0: ABSENT. Unleash 0. Flagsmith (BSD-3, 6,408 stars) is the permissive alternative if AGPL is unacceptable. Not a content-duplicate.
- Tag: METHODOLOGY (AGPL: pattern + self-host note only, no code)

---

## Also evaluated (not in top 5)
- Flagsmith - github.com/flagsmith/flagsmith - 6,408 stars - BSD-3-Clause (clean) - pushed 2026-06-12. Permissive alternative to Unleash for rollout flags; held as fallback.
- alirezarezvani/claude-skills sample-size-guide.md - the existing table's cited source; re-verified 2026-06-13. Employee table faithfully matches the upstream "20% lift" column (1%->97k, 3%->31k, 5%->18k, 10%->8.7k, 20%->4k) and the "1% baseline / 5% lift = 1.5M" claim. No correction needed; methodology-basis note added instead.

## License flags summary
| Source | License | Action |
|---|---|---|
| GrowthBook | NOASSERTION (MIT core + commercial enterprise dir) | methodology + self-host note, no code |
| PostHog | NOASSERTION (MIT core + ee dir) | self-host note, no code |
| OpenReplay | NOASSERTION (Apache-2.0 core + ee dir) | self-host note, no code |
| Microsoft Clarity | MIT | clean - safe to cite freely |
| Unleash | AGPL-3.0 | methodology only, never bundle code |
| Flagsmith (alt) | BSD-3-Clause | clean |
