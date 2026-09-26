# Mobile Developer - Learnings (Pending)

```
Format: - **<YYYY-MM-DD> - <project/context>**: <what> *Proposed rule: <takeaway>* Tags: [#ios], [#android], [#rn], [#flutter], [#native], [#perf], [#security], [#store], [#promoted?]
```

---

## Pending observations

- **2026-04-24 - Mobile Developer rebuild**: wshobson's mobile-developer agent is the richest capability matrix in the 6-repo set (200 lines, covers everything from Fabric to ARKit to WidgetKit to App Clips). Absorbed as primary. Sickn33's 8-ref mobile-design suite adds depth on typography, color, testing, performance, navigation, debugging - complementary rather than overlapping.
  *Proposed rule: For engineering employees, capability matrices (wshobson style) are better primary sources than narrative skills. Designers/analysts get narrative; developers get structured lists.*
  Tags: [#source-selection], [#promoted?]

- **2026-04-24 - Mobile Developer rebuild**: Cross-platform vs native is the highest-leverage mobile decision. Built explicit decision tree with default (RN + Expo + TS) to prevent endless debate.
  *Proposed rule: When a decision repeats across projects, codify a default path; the owner still overrides, but starts from a sane baseline.*
  Tags: [#default-decision-tree]

- **2026-04-24 - Mobile Developer rebuild**: Cross-referenced UI/UX Designer's Design Review Protocol as a hard gate BEFORE implementation. Mobile especially suffers from "build first, figure out flow later" - the 4 questions catch flow gaps.
  *Proposed rule: Gate all mobile feature work behind Design Review Protocol completion. Non-negotiable.*
  Tags: [#design-gate], [#cross-employee]

---

## Promotion log

| Date | Observation → Rule | Location |
|------|-------------------|----------|
| | | |

## 2026-04-25 - v0.3.0 absorption (skill scanner v2 catches)
- **mobile-next/mobile-mcp is the unified mobile MCP** - works on iOS + Android, real devices + emulators + simulators. Single npm package, single config, all major MCP clients supported. No reason to use anything else as primary.
- **Accessibility tree > screenshot coordinates.** mobile-mcp's `mobile_list_elements_on_screen` returns labelled elements with coords. ALWAYS use a11y labels first; coord-based clicks break with any UI change.
- **Cross-app workflows are the killer use case.** LLM can chain Substack → WhatsApp → Calendar in a single prompt. None of the prior mobile MCPs supported this end-to-end.
- **infiniV/Android-Ui-MCP is a strict subset** - Android only, screenshots only. Keep as fallback only.
- **dpconde NowInAndroid patterns.** Offline-first + UDF + reactive Flow + multi-module + convention plugins. This is the Google official guidance, not opinion. Default for all new Kotlin work.
- **Convention plugins are non-obvious but huge.** Extracting Gradle setup into `build-logic/convention/` saves hours per project. Default for every Android project.
- **Fakes > Mocks.** dpconde's testing strategy avoids Mockito/MockK. Write `FakeXRepository : XRepository` instead. Faster tests, no reflection, easier to debug.
- **Anti-amnesia signal.** Banner added to SKILL.md description because the coding agent historically forgets these references mid-session. Reinforced in rules.md.
- **Quarterly re-scan targets:** CursorTouch/Android-MCP, minhalvp/android-mcp-server, jsuarezruiz/mobile-dev-mcp-server, skydoves/android-skills-mcp, rcosteira79/android-skills (KMP support is unique), Drjacky/the coding agent-android-ninja (Navigation3 is newer than dpconde).

## 2026-05-01 - M4 absorption: MetaGPT Engineer spec→code handoff (v0.4.0)
- Pattern: 8-step sequence; schema discipline (verbatim signatures); no scope creep; imports from Shared Knowledge
- Anti-patterns refused: improvements, helper additions, renames
- Source: github.com/FoundationAgents/MetaGPT

## 2026-05-13 - Absorbed twostraws/Swift-Agent-Skills (scout 2026-05-11) - iOS GAP FILL
- Paul Hudson (Hacking with Swift) - iOS-community gold standard, strongest possible vouch
- SwiftUI + Swift Concurrency + Swift Testing + SwiftData sub-skills
- MIT. Tier 1 PASS (Paul Hudson reputation).

## 2026-06-13: Depth pass: testing + release pillars operationalized (v0.8.0)
- **Tool names were not methodology.** SKILL.md listed Maestro / Detox / Patrol / Paparazzi / fastlane in capability lists, but Gate-0 grep showed zero operational guidance. The skill is layer-selection + decision rules, not the list. Lifted into `mobile-test-and-release.md`.
- **Test-layer selection table** added: Maestro = cross-platform E2E default; Detox = RN gray-box (runloop sync); Patrol = Flutter native-interaction flows (stock integration_test cannot leave the Flutter layer); Paparazzi = Android JVM visual regression (no emulator, fast PR gate). mobile-mcp stays dev-loop/exploration only.
- **Release gates were prose, now numeric.** crash-free >= 99.5% (7-day), cold-start < 2.0s p50, app-size budget, 60fps, phased rollout with a halt trigger. The Release checklist said "watch"; the gates say "with what number".
- **Lane selection** added to SKILL.md: prototype / small-task / feature / release. Mobile especially over-applies the full pre-dev checklist to one-screen fixes; the lanes fix that. Escalate up, never down.
- **Sources all permissive** (MIT / Apache-2.0): Maestro 14.1k, fastlane 41.3k, Detox 11.8k, Patrol ~1.3k, Paparazzi 2.5k. No GPL/AGPL. Methodology only, no code bundled.
- **Scout watch added:** roborazzi (951), Google first-party Compose Preview screenshot testing (alpha), ComposablePreviewScanner. Re-evaluate Paparazzi vs Google first-party once the latter leaves alpha.

## 2026-07-24 engineering-core upstream
- Default Expo SDK 55+ (RN 0.83, React 19.2). SDK 50 language retired for greenfield.
- Toolchain preflight fails closed with one actionable cause before implementation.
- Source: expo.dev upgrading-to-sdk-55.
## Sources

- Upstream: mobile-dev-inc/Maestro (Apache-2.0); fastlane/fastlane (MIT); wix/Detox (MIT); leancodepl/patrol (Apache-2.0); cashapp/paparazzi (Apache-2.0)
- What was used: methodology absorbed: mobile-dev-inc/Maestro, wix/Detox, leancodepl/patrol, cashapp/paparazzi; methodology only: fastlane/fastlane
- License notes: absorbed sources permissive (MIT/Apache-2.0); no code vendored
