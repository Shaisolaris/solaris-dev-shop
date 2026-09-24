# CRO + Experimentation Depth (2026)

Methodology reference for the cro-landing-designer. Deepens the A/B testing and instrumentation layers with statistical methods and behavioral-signal vocabulary absorbed 2026-06-13. Methodology only - no third-party code is bundled. Sources with non-permissive or NOASSERTION licenses (GrowthBook, PostHog, OpenReplay, Unleash) are described as self-hostable tools you run, not code copied here.

Read order: `rules.md` (binding gates) -> this file (depth) -> `SKILL.md` (workflows).

---

## 1. Variance reduction with CUPED (the low-traffic answer)

The employee's standing pain: detecting small lifts on low-traffic pages needs enormous samples (1% baseline / 20% lift ~ 97k per variant). CUPED attacks this without changing the experiment design.

- **What it is:** CUPED (Controlled-experiment Using Pre-Experiment Data) subtracts the variance explained by each user's pre-experiment behavior from the metric, leaving a lower-variance estimate of the treatment effect. Same point estimate, tighter confidence interval.
- **Effect:** up to ~2x faster significance (i.e. roughly half the sample) when the pre-period covariate correlates well with the outcome. The gain scales with that correlation; weak correlation = small gain.
- **Inputs:** a pre-experiment lookback window per user (GrowthBook default 14 days) and a covariate that predicts the outcome (e.g. prior sessions, prior conversions, prior revenue).
- **When it helps most:** returning-user populations with history; revenue/engagement metrics; logged-in SaaS funnels. **When it does NOT help:** pure first-touch landing pages where every visitor is new (no pre-period data) - here CUPED gives ~nothing, so fall back to bigger MDE or qualitative.
- **Operating rule:** before declaring a low-traffic page "untestable," check whether a correlated pre-period covariate exists. If yes, CUPED may bring the required sample into reach. If no, the existing "test big swings or do not test" rule stands.
- **Self-host note:** CUPED is built into GrowthBook (NOASSERTION/open-core) and other engines; you enable it in the platform, you do not implement it here.

## 2. Sequential testing / always-valid p-values (peeking, done right)

The blunt rule today is "no peeking." That is correct for a fixed-horizon t-test. But there is a principled way to look early.

- **Fixed-horizon test:** valid only if you decide once, at the pre-computed sample size. Looking early inflates false positives (the "peeking" error in the analysis table).
- **Sequential test:** uses always-valid p-values / confidence sequences that remain valid no matter how often you look. You may stop as soon as the always-valid interval excludes zero.
- **Tradeoff:** sequential methods require a somewhat larger maximum sample for the same power - you pay a peeking premium in exchange for the right to stop early.
- **When to switch from fixed-horizon to sequential:** high-risk changes (need to kill a bad variant fast), time-sensitive launches, or any case where a stakeholder will look at the dashboard regardless. Choosing sequential up front is honest; peeking at a fixed-horizon test is not.
- **Hard rule update:** "no peeking" applies to fixed-horizon tests. If early looks are needed, declare a **sequential** test at design time and size for its larger maximum. Never convert a running fixed-horizon test into a sequential one mid-flight.
- **Self-host note:** available in GrowthBook (always-valid p-values), Optimizely Stats Accelerator, VWO SmartStats.

## 3. SRM detection, operationalized

rules.md already says "SRM detected -> test invalid" but never says how to detect it. Operationalize:

- **What SRM is:** Sample Ratio Mismatch - observed traffic split differs from the intended split (e.g. you set 50/50 but observe 52/48 over large N) by more than chance. It signals a broken assignment/logging pipeline and **invalidates the result**, win or lose.
- **The test:** chi-square goodness-of-fit on the observed counts vs the intended ratio.
  - Expected per arm = total * intended share.
  - chi-square = sum over arms of (observed - expected)^2 / expected.
  - For a 2-arm test, df = 1; **SRM is flagged when the SRM p-value < 0.001** (the standard conservative threshold - much stricter than 0.05 because false SRM alarms are costly and real SRM is usually gross).
- **Worked example:** intended 50/50, observed 10,400 / 9,600 (N=20,000). Expected 10,000/10,000. chi-square = (400^2)/10000 + (400^2)/10000 = 16+16 = 32. df=1 -> p ~ 1.5e-8 << 0.001 -> **SRM, test invalid.** Diagnose assignment (bot filtering, redirect timing, flag bucketing, logging gaps) before rerunning.
- **Counter-example:** observed 10,070 / 9,930 -> chi-square = (70^2)/10000 * 2 = 0.98 -> p ~ 0.32 -> no SRM.
- **Rule:** run the SRM check FIRST, before reading the primary metric. A failed SRM voids the readout entirely.

## 4. Multi-armed bandits (a test class the employee did not have)

Standard A/B tests hold the split fixed and optimize for *learning* (clean per-variant estimates). Bandits move traffic toward winners during the run and optimize for *earning* (total conversions).

- **Mechanism:** Thompson sampling (Bayesian) allocates traffic proportional to each arm's probability of being best; a floor (GrowthBook: 1% min per arm) keeps exploring in case behavior shifts.
- **Requires:** a single decision metric, and fast data (events landing in minutes lets allocation adapt within hours).
- **Use bandits when:** short-lived opportunities (campaign/seasonal/launch creative), many variants to triage, headline/CTA/creative selection where you mainly want the best one live - not a precise lift estimate. You can add new arms mid-run.
- **Do NOT use bandits when:** you need a defensible per-variant lift for a roadmap decision, when the metric is slow/delayed (conversion lags days), or when novelty effects would mislead early allocation. For those, fixed-horizon A/B remains correct.
- **Honest caveat:** bandits maximize total conversions but blur the individual-arm read; you trade inferential precision for cumulative reward. Pick the tool by whether you are *deciding* (A/B) or *harvesting* (bandit).
- **Self-host note:** GrowthBook bandits (NOASSERTION/open-core); methodology only here.

## 5. Behavioral-signal taxonomy (qualitative before quantitative)

rules.md mandates heatmaps + session replay from day 1 but does not name the signals to look for. Standardize the vocabulary (from OpenReplay + Microsoft Clarity friction metrics):

| Signal | What it means | Readiness category it feeds |
|---|---|---|
| Rage click | Rapid repeated clicks on one element | Friction & UX - broken/unresponsive control or false affordance |
| Dead click / dead zone | Click on something that looks interactive but does nothing | Friction & UX - misleading design, missing handler |
| Excessive / thrashing scroll | Up-down hunting | Value-prop clarity or scent loss - user cannot find the next step |
| Quick-back | Land then immediately leave | Traffic-message match break - page did not continue the ad/email promise |
| Scroll-depth cliff | Sharp drop-off at a section | Section is a dead end - move CTA above it or fix the section |
| Click map vs intended CTA | Attention going to non-CTA elements | Conversion goal focus - competing CTAs / weak hierarchy |
| Form field abandonment | Drop-off at a specific field | Form Health - that field is the cost; justify or cut it |

- **Operating rule:** segment every map by **device and traffic source** before concluding - a blended heatmap hides a broken mobile or a broken paid-source experience (mirrors the "1% blended rate hides one broken source" audit rule).
- **Loop:** behavioral signals -> hypothesis -> (readiness >= 70) -> test. Qualitative data precedes the first test idea; it never substitutes for the significance gate.
- **Tooling default:** Microsoft Clarity (MIT, free, unlimited, no sampling) is the safe day-1 default. OpenReplay (Apache-2.0 core, self-hosted) when data residency / self-hosting is required. Both run as tools; no code here.

## 6. Rolling out the winner safely (the missing last mile)

Workflow 3 ends with "winner becomes the new control" but specifies no safe-deploy method. A winning test result is a probability, not a guarantee; deploy it like one.

- **Gradual rollout:** ramp the winner 5% -> 25% -> 50% -> 100% behind a feature flag, watching guardrails at each step, instead of a hard 100% cutover.
- **Kill switch:** keep an instant-rollback flag on the change for at least one full business cycle post-launch; a winning A/B result can still regress under full traffic or novelty decay.
- **Server-side targeting** for changes that must not flash/flicker (avoids the CLS/INP cost of client-side swaps - ties back to the speed gate).
- **Flag hygiene:** schedule removal of the flag + losing variant once the winner is stable; stale flags are tech debt and a source of future SRM.
- **Self-host note:** Unleash (AGPL-3.0 - methodology only, never bundle code) or Flagsmith (BSD-3, permissive) provide gradual rollout + kill switch + lifecycle. Methodology only here.

---

## Source basis note - the sample-size anchor table

The anchor table in SKILL.md/rules.md is transcribed from alirezarezvani/claude-skills `sample-size-guide.md` (re-verified 2026-06-13). Those figures are deliberately conservative and run ~2x a textbook pooled two-proportion calculation (e.g. the guide lists 1% baseline / 20% lift = 97k per variant; a pooled normal-approximation gives ~43k). Treat the table as a safe upper-bound planning anchor. For an exact number, run a calculator (Evan Miller / abtestguide / VWO) on the **page-specific** baseline and your chosen MDE - never the site-wide average. The anchors exist to answer "is this even feasible?" fast, not to replace a per-test calculation.

## Inline sample-size method (when no calculator is at hand)

Per-variant n for a two-proportion test (pooled normal approximation, 95% two-sided / 80% power):

```
n = ( z_alpha * sqrt(2 * p_bar * (1 - p_bar)) + z_beta * sqrt(p1*(1-p1) + p2*(1-p2)) )^2 / (p2 - p1)^2
where p1 = baseline, p2 = p1 * (1 + MDE_relative), p_bar = (p1 + p2)/2,
      z_alpha = 1.96 (two-sided 95%), z_beta = 0.84 (80% power).
```

This is the textbook estimate; it will read lower than the conservative anchor table. Use the table for go/no-go feasibility, this formula or a calculator for the committed number, and CUPED (section 1) to potentially reduce the requirement when a correlated pre-period covariate exists.

---

## Build log
- 2026-06-13: Created. Absorbed (methodology only): GrowthBook statistics engine (CUPED, sequential/always-valid p-values, SRM chi-square operationalization, multi-armed bandits); OpenReplay + Microsoft Clarity behavioral-signal taxonomy; Unleash/Flagsmith safe-rollout patterns. Added sample-size source-basis note + inline pooled formula. No third-party code bundled; flagged-license sources (GrowthBook/PostHog/OpenReplay NOASSERTION, Unleash AGPL) carry self-host notes.
