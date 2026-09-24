# Mobile Test & Release Reference

> **Added 2026-06-13** (depth pass). Methodology lifted from five permissive (MIT / Apache-2.0) sources: Maestro, Detox, Patrol, Paparazzi, fastlane. No code is bundled; these are decision rules + canonical shapes. Install commands are the only verbatim lines. All sources are permissive, so no self-host caveat applies.

This file operationalizes the testing + release pillars that SKILL.md previously listed only as tool names. Load it whenever a feature is going to test, when wiring CI, or when preparing a store submission.

---

## 1. Test-layer selection (which tool for which job)

The employee names many testing tools; the actual skill is knowing which layer each one owns. Pick by platform AND by what is being verified.

| Layer | What it verifies | RN / Expo | Flutter | Native iOS | Native Android |
|-------|------------------|-----------|---------|------------|----------------|
| Unit | Logic, mappers, view-models | Jest | flutter test | XCTest | JUnit + Turbine |
| Component / widget | A screen in isolation | RN Testing Library | flutter_test | SwiftUI Preview | Compose UI test |
| Visual regression | Pixels did not drift | Maestro snapshot | golden tests | snapshot | Paparazzi (JVM) |
| E2E (gray/black box) | Real user flow on device | Detox (gray) or Maestro | Patrol or Maestro | Maestro / XCUITest | Maestro / Espresso |
| AI-driven exploration | Ad-hoc, dev-loop, cross-app | mobile-mcp | mobile-mcp | mobile-mcp | mobile-mcp |

Rules:
- **Maestro is the default cross-platform E2E layer** when you want one suite for iOS + Android (+ web). YAML flows, interpreted (no compile), built-in flakiness tolerance and auto-wait. Reach for it before hand-rolling Appium.
- **Detox is the gray-box choice for React Native** specifically. It synchronizes with the RN runloop, so it waits for the app to be idle instead of sleeping. Use it when flakiness from async RN state is the problem.
- **Patrol is the Flutter choice when the flow crosses the OS boundary** (permission dialogs, notifications, WebViews, device settings). Flutter's stock integration_test cannot touch native UI; Patrol can. If the Flutter test never leaves the Flutter layer, plain integration_test is enough.
- **Paparazzi is the Android visual-regression choice**. It renders Compose/View screens on the JVM with no emulator, so it runs in plain unit-test CI in seconds. Use it for the "did the UI drift" gate, not for behavior.
- **mobile-mcp is for AI-driven exploration and the dev loop**, never for the committed regression suite (see mobile-mcp-operator.md "When NOT to use").

---

## 2. Maestro (cross-platform E2E): methodology

Install: curl -fsSL "https://get.maestro.mobile.dev" | bash (needs Java 17+).

Canonical flow shape (YAML, one flow = one file):

    appId: com.solaris.app
    ---
    - launchApp
    - tapOn: "Sign in"
    - inputText: "user@example.com"
    - assertVisible: "Welcome"

Decision rules:
- **Address elements by accessibility text/id, never by coordinates** (same doctrine as mobile-mcp). A flow keyed to a11y labels survives layout changes.
- **One flow per user journey**; keep flows short and composable. Long flows are hard to debug and re-run.
- **Let Maestro wait.** Do not insert sleep; rely on the built-in smart-wait. A manual sleep is a red flag.
- **Run flows in CI on every PR** for the critical-path journeys (login, core action, checkout). Use the open-source CLI in CI; Maestro Cloud is optional paid parallelism, not required.
- **Tag flows** so PR runs hit smoke flows and nightly runs hit the full suite.

## 3. Detox (React Native gray-box): methodology

Install: npm i -D detox then detox init.

Decision rules:
- **Use awaitable matchers + actions** (element(by.id(...)).tap()); Detox auto-synchronizes with the RN bridge/runloop, network, timers, and animations, so you assert without sleeps.
- **Add testID props in the app code** for every element a test touches. testID is the contract between app and E2E suite; treat a missing testID as a code-review failure, not a test problem.
- **Separate build and test**: detox build then detox test, with a debug + a release config. CI runs the release config.
- **Detox is RN-only and gray-box.** If the project is Flutter or you need cross-platform parity with one syntax, prefer Maestro.

## 4. Patrol (Flutter E2E with native interactions): methodology

Install: add patrol dev-dependency + patrol_cli (dart pub global activate patrol_cli).

Decision rules:
- **Reach for Patrol the moment a Flutter flow needs the OS**: granting a permission, tapping a system notification, dismissing a native dialog, toggling a device setting, or driving a WebView. Stock integration_test silently cannot do these.
- **Use Patrol finders for Flutter widgets and the native API for OS UI**; keep the two clearly separated in the test body.
- **Run on Firebase Test Lab / device farm** for the real-permission paths; emulator behavior for permissions can differ from devices.
- **If the flow is pure-Flutter, do not pull in Patrol.** Plain integration_test keeps the dependency surface smaller.

## 5. Paparazzi (Android visual regression): methodology

Apply the Gradle plugin app.cash.paparazzi.

Decision rules:
- **Record once, then compare.** recordPaparazzi writes golden images into the repo; verifyPaparazzi fails the build when a screen drifts. Commit goldens with the feature.
- **It runs on the JVM with no emulator**, so it belongs in the fast unit-test job, gating every PR, not in the slow instrumented job.
- **Test the stateless screen, not the Route** (matches android-architecture.md Screen/Route split). One Paparazzi test per UiState variant (Loading / Success / Error), per theme (light / dark), and per key font scale.
- **Re-record deliberately.** A golden change in a PR must be reviewed like code; never auto-accept drift.
- Alternates: takahirom/roborazzi (Compose + AI assertions) or Google first-party com.android.compose.screenshot (alpha as of 2026-06). Note them, but Paparazzi is the stable default.

---

## 6. fastlane (app-store release automation): lane methodology

Install: brew install fastlane or add to the project Gemfile. License MIT; everything runs on your own machine/CI, no credentials leave the box.

Map each store task to its fastlane tool (the operational layer SKILL.md only hinted at):

| Task | iOS tool | Android tool |
|------|----------|--------------|
| Build / archive | gym | gradle |
| Code signing / certs | match (shared encrypted certs) + sigh | keystore |
| Upload to beta | pilot (TestFlight) | supply (Internal track) |
| Upload to store + metadata | deliver | supply |
| Screenshots | snapshot | screengrab |
| Pre-submission checks | precheck | n/a |

Canonical lane shapes (declare in Fastfile):

    lane :beta do
      match(type: "appstore")     # shared signing, no manual cert juggling
      gym(scheme: "App")          # archive
      pilot                       # ship to TestFlight
    end

    lane :release do
      match(type: "appstore")
      gym(scheme: "App")
      deliver(submit_for_review: true, force: true)  # metadata + binary + review
    end

Decision rules:
- **match is the answer to code-signing pain**: store certs/profiles in an encrypted git repo; every machine + CI pulls the same identity. Never hand-manage provisioning profiles across a team.
- **Three lanes minimum**: beta (TestFlight / Internal), release (production submit), and a screenshots lane.
- **Run lanes from CI**, with signing secrets injected as CI variables, never committed.
- **Pair fastlane with EAS where the project is Expo.** EAS Build/Submit already covers most of this; use fastlane for the bare-RN / native projects (see rules.md expo/skills note).

---

## 7. Operationalized release gates (formulas)

SKILL.md listed targets prose-style. These are the numeric gates a release must pass:

- **Crash-free sessions gate**: crash_free_sessions% = (1 - crashed_sessions / total_sessions) * 100. Ship gate: >= 99.5% measured on the prior release over its first 7 days. Below 99.5% -> block the next phased rollout, fix first.
- **Cold-start gate**: time-to-interactive on a defined mid-range reference device (e.g. Pixel 6a / iPhone SE 3) < 2.0s p50, < 3.5s p90. Regressions > 15% vs last release block release.
- **App-size budget**: download-size budget set per project at kickoff; default ceiling iOS < 200 MB / Android base APK < 150 MB (use App Bundle + dynamic delivery to stay under). A PR that grows download size > 5% requires sign-off.
- **Frame gate**: scroll + key animations hold 60fps (no jank frames > 16.6ms) on the reference device; profile before merge.
- **Phased rollout**: production launch starts at a small slice (e.g. 10% on Play staged rollout / App Store phased release), watch crash-free + ANR for 24h, then ramp. Halt-and-rollback trigger: crash-free drops below the 99.5% gate during ramp.

These gates are the quantitative half of the SKILL.md Release checklist; the checklist says "watch", this says "with what number".

---

## Source provenance
- Maestro: https://github.com/mobile-dev-inc/Maestro (Apache-2.0, 14.1k stars, CLI 2.5.1 2026-04-30)
- Detox: https://github.com/wix/Detox (MIT, 11.8k stars, 20.50.4 ~2026-06)
- Patrol: https://github.com/leancodepl/patrol (Apache-2.0, ~1.3k stars, Patrol 4.0 2026)
- Paparazzi: https://github.com/cashapp/paparazzi (Apache-2.0, 2.5k stars, active 2026)
- fastlane: https://github.com/fastlane/fastlane (MIT, 41.3k stars, 2.232.2 2026-02-27)
- Verified + lifted 2026-06-13 (depth pass). Methodology only; no source code bundled.
