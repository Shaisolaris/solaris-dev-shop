# Elite Manual QA: visual-regression discipline, WCAG conformance, deterministic flake elimination, client-ready bug reports (2026)

Net-new ELITE methodology absorbed 2026-06-20. This is the elite/client-delivery tier on TOP of the existing methodology, not a replacement. Gate-0 against what was already held:
- Visual regression TOOLS already named (Chromatic/Percy/Playwright `toHaveScreenshot`, snapshot diffs, "human approval"). What was MISSING: baseline-generation DISCIPLINE. Added in section 1.
- Accessibility already held (axe ~30%, manual sweeps, WCAG 2.1 AA, P0-P3). What was MISSING: WCAG 2.2 + the formal CONFORMANCE audit method + the conformance-report deliverable. Added in section 2.
- Flake root-cause catalog already in the Playwright Pro absorption. What was MISSING: the hermetic/deterministic-test doctrine consolidated as a standard. Added (delta only) in section 3.
- An INTERNAL P0-P3 taxonomy + output format already exist. What was MISSING: the CLIENT-READY bug-report standard (severity-vs-priority as independent axes + the deliverable template). Added in section 4.

---

## 1. Visual-regression baseline discipline (the missing rigor)

The tools were named; the discipline that makes them trustworthy was not. A visual suite without baseline discipline produces noise, the team learns to rubber-stamp diffs, and the suite dies. The discipline:

### Generate baselines in CI, never on a developer laptop
- Screenshots differ by OS, font rendering, GPU, and device-pixel-ratio. A baseline captured on a Mac will diff against a Linux CI runner forever. **Generate and update baselines inside the SAME containerized environment CI uses** (the official `mcr.microsoft.com/playwright` Docker image, pinned by digest per the fleet SHA-pin doctrine). One environment = one source of truth for pixels.
- Commit baselines to the repo (or a baseline store) only after they were produced in that environment. A baseline produced anywhere else is invalid.

### Make the render deterministic BEFORE you snapshot
- Freeze animations + transitions (`reducedMotion: 'reduce'` plus a global CSS kill for `animation`/`transition` where needed). An un-frozen carousel is a permanent false diff.
- Freeze time/clock for any timestamp, relative-date, or "X minutes ago" UI (see section 3).
- Stub network so the same data renders every run (HAR or route mocks; section 3).
- Wait for fonts (`document.fonts.ready`) and for the element to be stable, not just visible, before capturing.

### Mask, do not delete, dynamic regions
- Use the framework `mask` option (Playwright `toHaveScreenshot({ mask: [...] })`) for genuinely dynamic regions (live counts, ads, user avatars, dates that cannot be frozen). Masking is surgical; lowering the global threshold to swallow the diff is not - a high threshold hides REAL regressions everywhere.

### Threshold tuning is per-component, not global
- Prefer a near-zero pixel diff with masking over a loose global `maxDiffPixelRatio`. If a component genuinely needs tolerance (anti-aliasing on a gradient), set it on THAT assertion, documented, not project-wide.

### Baseline-update governance (the human gate, formalized)
- A diff is one of two things: a BUG (reject, file it) or an INTENDED change (approve, update the baseline). The reviewer must consciously choose - auto-update-on-diff defeats the entire purpose.
- The baseline-update commit is reviewed like code: who approved, which intended change it reflects, linked to the PR/ticket. "Update all baselines" with no per-diff inspection is the anti-pattern that kills visual suites.
- Scope snapshots to components/stable regions over full-page where possible - smaller surface = fewer false diffs = a suite people trust.

### When to leave the framework
- Built-in Playwright visual testing is the right default. Switch to a cloud diffing tool (Chromatic/Percy) when you need cross-browser baseline matrices, a managed approval UI for non-engineers, or parallel baseline storage at scale. The DISCIPLINE above is identical either way.

---

## 2. Accessibility as WCAG CONFORMANCE (not just an axe pass)

The existing methodology runs axe + manual sweeps at WCAG 2.1 AA. Elite delivery treats accessibility as a CONFORMANCE claim a client can stand behind legally, which means a defined target, a defined method, and a conformance report.

### Pin the target version + level explicitly
- **WCAG 2.2 AA** is the 2026 baseline (EN 301 549 and most procurement now reference it; it is also an ISO/IEC standard). 2.2 AA = 56 criteria (the 2.1 set plus the new ones below). State the exact target in the report: "WCAG 2.2, Level AA."
- The 2.2 additions teams most often FAIL (test these explicitly, they did not exist in 2.1): Focus Not Obscured (Minimum) 2.4.11, Focus Appearance 2.4.13, Dragging Movements 2.5.7 (every drag needs a single-pointer alternative), Target Size (Minimum) 2.5.8 (24x24 CSS px minimum), Consistent Help 3.2.6, Redundant Entry 3.3.7, Accessible Authentication 3.3.8 (no cognitive-function test / copy-paste must be allowed on auth).

### Automated is the FIRST pass, never the claim
- **axe-core** [MPL-2.0] surfaces ~57% of real issues by volume but FULLY automates only ~29.5% of WCAG 2.2 success criteria, and it includes W3C ACT-rule conformance. **pa11y** [supports WCAG 2.0/2.1 + Section 508, JSON/CSV/HTML output] is a useful second engine for CI gating + machine-readable reports; Lighthouse a11y is a third quick signal. Run automated to clear the high-volume, machine-decidable defects (contrast, missing labels, missing alt) cheaply.
- Then spend HUMAN effort only where it is the sole option: keyboard operation + focus management, screen-reader semantics, meaningful sequence, error identification, and the cognitive/2.2 criteria above. This automated-floor / human-ceiling split is the method, not a nice-to-have.

### The manual conformance pass (per page/flow)
- Keyboard-only: complete every task; logical tab order; visible + non-obscured focus (2.4.11/2.4.13); no keyboard trap; escape-to-close; arrow-key for composite widgets.
- Screen reader on the real flow: VoiceOver (Safari/macOS+iOS), NVDA (Firefox/Windows), TalkBack (Android); narrate the page - is it understandable + operable, are names/roles/states correct.
- Contrast measured by tool (4.5:1 body, 3:1 large/UI), never eyeballed.
- Reflow at 320px CSS width + 400% zoom with no horizontal scroll; `prefers-reduced-motion` honored.
- Target size 24x24 (2.2) / 44x44 where the stricter platform HIG applies.

### The deliverable: a conformance report (VPAT-style), not a defect dump
- Per success criterion: Supports / Partially Supports / Does Not Support / Not Applicable, with the evidence. This is the format procurement + legal expect (the ACR/VPAT shape).
- Findings carry BOTH the WCAG SC reference AND the severity (map to the existing P0-P3: P0 = blocks an assistive-tech user, e.g. keyboard trap or unlabeled control on a critical path).
- State the exact tooling + assistive-tech versions + the conformance target, so the claim is reproducible.

---

## 3. Deterministic / hermetic test doctrine (flake elimination, consolidated)

The Playwright Pro absorption holds a flake ROOT-CAUSE catalog (layout shift, networkidle, animation, stale state, iframe). This section adds the upstream doctrine: make the test HERMETIC so the flake never has a chance to occur. Delta only - it does not repeat the catalog.

### A test is deterministic only if it controls all four non-determinism sources
1. **Time** - freeze the clock. Pin to a fixed instant (Playwright `page.clock.install({ time: ... })` / `setFixedTime`) so weekend/month-boundary/timezone/"5 minutes ago" logic is identical every run and on every runner. Unfrozen time is a silent flake AND a visual-diff source.
2. **Network** - make it hermetic. Record once to a HAR and replay (`page.routeFromHAR`), or stub specific responses (`page.route`). No test on a committed suite should hit a live third party - upstream latency/outages become your flake. (Live-target smoke checks are a separate, explicitly-non-hermetic lane.)
3. **Data** - seed the generator. `faker.seed(n)` (already in the test-data rule) so a failure reproduces with identical data; never unseeded random.
4. **Concurrency/state** - isolate per test (unique tenant/IDs per worker, `beforeEach` reset or `storageState`); never depend on test order or shared globals.

### Anti-flake rules promoted to standard
- Never `waitForTimeout`; web-first assertions with built-in retry only.
- `reducedMotion: 'reduce'` plus animation kill, globally, in the config (also required for visual, section 1).
- `networkidle` is unreliable in SPAs that poll - wait on a specific response or element, not idle.
- Register route handlers BEFORE `goto`, not after (a top-8 Playwright flake pattern).
- Retry-once in CI is a DETECTOR, not a fix: a test that needs the retry is flaky and gets root-caused (existing 48h rule), not left to lean on the retry.
- Quarantine, do not delete-on-sight: move a confirmed flake to a quarantine lane so it stops blocking CI, but it stays visible and gets fixed - a deleted test is lost coverage.

---

## 4. Client-ready bug-report standard (the gig deliverable)

The employee has an INTERNAL P0-P3 taxonomy + an internal output format. The Manual QA gig delivers bug reports to a CLIENT, which needs a different, stricter standard. (Sourced from the 2026 bug-reporting standards.)

### Severity and priority are INDEPENDENT axes - report both
- **Severity** = technical impact (how badly it breaks the product). 4-level objective scale: Critical / High / Medium / Low, with objective criteria, not vibes.
- **Priority** = business urgency (how soon it must be fixed).
- They are orthogonal: a Critical-severity bug in a retired feature can be Low priority; a Minor spelling error on the checkout button can be High priority because it costs conversion. Reporting only one axis is the most common amateur tell. Map severity to the existing P0-P3 internally; expose both axes to the client.

### Mandatory fields (non-negotiable on EVERY report)
1. **Title** - specific + scannable ("Checkout 'Pay' button does nothing on iOS Safari 17", not "payment broken").
2. **Environment** - OS + version, browser/app + version, device, build/commit, URL, account/role used.
3. **Steps to reproduce** - numbered, sequential, with EXACT values + pages + interactions. Anyone must be able to follow them blind.
4. **Expected result.**
5. **Actual result.**
6. **Visual evidence** - screenshot or (better) a short screen recording; annotate it.
7. **Severity + Priority** (both axes).
8. **Supporting data** - console errors, failing network request, stack trace, relevant logs, when applicable.
9. **Reporter + date.**

### Reproduction discipline (what separates a usable report from a thrown-over-the-wall one)
- A bug you can reproduce in numbered steps is a bug the developer can fix on the first read. If it is intermittent, SAY SO and give the observed frequency + any conditions that increase it - do not pretend it is deterministic.
- One bug per report. Bundling three issues into one ticket guarantees two get lost.
- Confirm it is reproducible on a clean state (fresh session/incognito) to rule out local cache/state.

### The deliverable format (client-facing)
- A summary line at the top: counts by severity (e.g. "3 Critical, 5 High, 8 Medium, 4 Low") + the one-sentence headline risk.
- Then the itemized reports, ordered by priority, each with the mandatory fields.
- Plus a "what was tested + what was NOT tested (scope + coverage gaps)" section, so the client knows the boundaries of the pass - this is the honesty that earns repeat engagements.

---

## Host-wiring needed for the elite/live tier
- **Chrome / browsers** - the visual + a11y + E2E passes need real browser engines. Host installs the Playwright browsers + the pinned Playwright Docker image for CI-parity baseline generation (`npx playwright install --with-deps`); for live agent-driven exploratory checks the playwright-mcp CONNECT already documented in rules.md drives a real browser.
- **CI with Docker** - baseline generation, Testcontainers integration, and the api-fuzz job all need Docker in CI; pin images by digest.
- **Assistive tech** - the manual conformance pass needs real screen readers (VoiceOver on macOS/iOS, NVDA on Windows, TalkBack on Android) on real or virtualized devices; simulators lie for AT behavior (existing real-device rule).
- **Automated a11y engines** - axe-core + pa11y installed in CI for the automated floor; both are free/OSS.
