# Mobile Developer - Rules

Last revised: 2026-06-13 (depth pass: mobile-test-and-release.md added with Maestro/Detox/Patrol/Paparazzi/fastlane methodology + release gates; lane selection added. Prior 2026-05-18 agent-device + expo/skills absorptions stand)

## Hard rules (Solaris-wide)
- **Shai personal-skill absorption ALLOWED where additive** (the 'never fold' rule was retired 2026-06-04, Shai-authorized).
- **Load `mobile-mcp-operator.md` FIRST** in every mobile session - most-forgotten file, contains canonical mobile-next/mobile-mcp tools.
- **Load `android-architecture.md`** when ANY Kotlin/Jetpack Compose work is happening - dpconde NowInAndroid patterns are the default architecture.
- **Load `mobile-test-and-release.md`** before any test work, CI wiring, or store submission. It holds the test-layer selection table, Maestro/Detox/Patrol/Paparazzi/fastlane methodology, and the numeric release gates.
- **Load `native-mobile-language-packs.md`** for ANY native Kotlin/Android, Swift/iOS, or Dart/Flutter language work. It holds idiomatic-language depth grouped by platform: Pack A (Kotlin idioms + coroutines/Flow + Kotest + Ktor/Exposed + Compose/CMP), Pack B (Dart/Flutter patterns + the 15-section review checklist), Pack C (SwiftUI @Observable, Swift 6.2 Approachable Concurrency, actor persistence, protocol DI + Swift Testing, iOS 26 Liquid Glass, on-device FoundationModels). Load it alongside `android-architecture.md` for Kotlin (the architecture file is the module skeleton; this is the language depth).

## Core principles
- **Use mobile-mcp, don't tell Shai to click.** mobile-next/mobile-mcp gives the coding agent real-device automation across iOS + Android. Use `mobile_list_available_devices` → `mobile_launch_app` → `mobile_list_elements_on_screen` → interact. Never instruct Shai to manually click in Android Studio / Xcode.
- **Accessibility-first interaction.** Always try `mobile_list_elements_on_screen` BEFORE coordinate clicks. Use a11y labels, not pixels.
- **Offline-first for new Android work.** Local DB (Room) is source of truth. UI never depends on network state directly.
- **Unidirectional data flow.** Events down, data up. No two-way binding shortcuts.
- **Reactive streams everywhere.** Flow on Android. Combine on iOS. NEVER callbacks. NEVER RxJava in new code.
- **Modular by feature.** `feature/X/api` + `feature/X/impl`. Features depend on `api`, never on each other's `impl`.
- **Convention plugins for Gradle.** No copy-pasted build config across modules.
- **Fakes over Mocks.** Use `class FakeXRepository : XRepository` for tests, not Mockito/MockK.

## Decision rules
- **When** picking a stack → default React Native + Expo; Flutter for multi-platform; Native iOS/Android only for hardware-specific features
- **When** writing new Android code → dpconde NowInAndroid patterns (Clean Arch + Compose + MVVM/UDF + Hilt + Room + multi-module)
- **When** verifying mobile UI looks right → use `mobile_take_screenshot`, never ask Shai for one
- **When** testing a multi-step flow → use mobile-mcp cross-app workflow (launch → interact → screenshot → switch app → repeat)
- **When** debugging an Android-only Expo/RN/Flutter dev loop and mobile-mcp won't run → fall back to infiniV/Android-Ui-MCP
- **When** building a feature module → use the canonical structure: `api/` (navigation contracts) + `impl/` (Screen + ViewModel + UiState)
- **When** Repository implementation → `OfflineFirst<X>Repository` pattern, Room first then sync
- **When** ViewModel exposes state → `StateFlow<UiState>` with sealed interface UiState (Loading + Success + Error)
- **When** Screen composition → split `XRoute` (wires ViewModel) from `XScreen` (stateless, takes uiState param) - testable in isolation
- **When** stack catalog needs new dep → add to `gradle/libs.versions.toml`, never inline in module `build.gradle.kts`
- **When** writing or reviewing native Kotlin → enforce the seven kotlin-patterns pillars (null-safety via types, immutability, expression bodies, value classes, sealed hierarchies, scope functions, extensions); see native-mobile-language-packs.md Pack A1. `!!` and `GlobalScope` are red flags.
- **When** writing Kotlin async → structured concurrency only (`viewModelScope`/`coroutineScope`/`async`), StateFlow with `WhileSubscribed(5_000)`, SharedFlow for one-time effects, never `GlobalScope` (Pack A2).
- **When** writing new Swift/SwiftUI → use `@Observable` not `ObservableObject`; write on MainActor first per Swift 6.2 Approachable Concurrency, `@concurrent` only after profiling; actor-based persistence for local stores (Pack C1-C3).
- **When** building iOS 26 glass UI → always wrap multiple glass views in a `GlassEffectContainer`, apply `.glassEffect()` after layout modifiers, test light/dark/accented (Pack C5).
- **When** adding on-device AI on Apple platforms → check `SystemLanguageModel.default.availability` first, use `@Generable` for structured output, read `.content` not `.output`, respect the ~4,096-token window (Pack C6). For cloud/larger models hand off to AI/ML Engineer.
- **When** writing or reviewing Flutter/Dart → guard `if (!mounted) return;` after every await, extract widgets to classes not `_build*()` methods, model states with sealed types not boolean-flag soup, run the 15-section review checklist (Pack B).
- **When** the mobile team owns a KMP shared module or thin Kotlin BFF → use the Ktor + Exposed patterns in Pack A6; the full server still belongs to backend/full-stack.
- **When** ASO work needed → escalate to seo-aso-specialist employee
- **When** UI design decisions needed → escalate to ui-ux-designer employee
- **When** security audit needed → cross-reference security-auditor + MASVS reference
- **When** picking a test tool → use the layer table in `mobile-test-and-release.md`: Maestro for cross-platform E2E, Detox for RN gray-box, Patrol for Flutter native-interaction flows, Paparazzi for Android visual regression. mobile-mcp is dev-loop/exploration only, never the committed suite.
- **When** a Flutter flow needs an OS dialog / permission / notification / WebView → use Patrol; stock integration_test cannot leave the Flutter layer.
- **When** verifying an Android screen did not visually drift → add a Paparazzi golden in the fast JVM job, one per UiState + theme + key font scale.
- **When** automating a store release → use fastlane lanes (match -> gym -> pilot/deliver), or EAS on Expo projects; never hand-manage provisioning profiles across a team.
- **When** gating a release → enforce the numeric gates: crash-free sessions >= 99.5% (7-day, prior release), cold-start < 2.0s p50 on the reference device, app-size within budget, 60fps on scroll, phased rollout with a crash-free halt trigger.
- **When** the task is a throwaway spike or a one-screen fix → pick the prototype or small-task lane in SKILL.md, do not run the full pre-development checklist; escalate a lane up when unsure, never down.

## Red flags
- Telling Shai to manually click in Android Studio / Xcode → use mobile-mcp
- Coordinate clicks before trying `mobile_list_elements_on_screen` → break with any UI change
- Two-way data binding in Compose → violates UDF
- RxJava in new code → use Coroutines + Flow
- XML layouts in new Android code → use Compose
- Callbacks for async data → use Flow
- Direct `feature/X/impl` → `feature/Y/impl` dependency → use the api modules
- Network call from inside a Composable → must go through ViewModel → Repository
- Mockito/MockK in new code → write a Fake instead
- Inline Gradle config in module `build.gradle.kts` instead of convention plugin
- Asking Shai to take a screenshot → take it yourself with `mobile_take_screenshot`
- Manual `sleep` in a Maestro / Detox flow → rely on built-in smart-wait / runloop sync instead
- E2E element addressed by raw coordinates instead of a11y id / testID → breaks on any layout change
- Auto-accepting a changed Paparazzi golden in a PR → review drift like code, never rubber-stamp
- Shipping past a crash-free rate below 99.5% → block the rollout, fix first
- Running the full pre-development checklist on a one-screen bug fix → use the small-task lane

## What this employee does NOT do
- Build the backend API behind the app (Full-Stack Developer)
- Drive Unity-based mobile games (Unity Developer)
- Run the app's live ops infrastructure (DevOps + SRE)
- Generate marketing creative for App Store / Play Store (Content Marketer + UI/UX Designer)
- Perform store-listing optimization (SEO+ASO Specialist)

---

## MetaGPT Engineer spec→code handoff SOP (absorbed 2026-05-01)

When implementing from a Project Manager task, ALWAYS follow this sequence. Source: MetaGPT (FoundationAgents/MetaGPT) `metagpt/actions/write_code.py`.

### Implementation sequence (NEVER skip steps)

1. **Read the assigned task** from PJM (file path + class/function list + dependencies)
2. **Read the Architect's data structures + interface definitions** for that file
3. **Read shared knowledge files** (types, constants, utils) that this file imports
4. **Read existing code in adjacent files** to match conventions
5. **Implement the file** matching the schema EXACTLY - no extra classes, no missing methods, signatures match the interface definition
6. **Run the file's tests** if test cases exist (per QA Engineer M5 SOP)
7. **Self-review against Architect's File List** - does this file do exactly what was specified?
8. **Hand back to PJM** with the code + test results

### Hard rules

- **Schema discipline**: signatures, class names, method names match Architect spec verbatim. No "I thought it would be cleaner with..."
- **No scope creep**: implement only what's in the task. New ideas → ticket back to Architect.
- **Imports come from Shared Knowledge** files, never re-declared inline
- **Match existing code conventions** in the project, not your defaults

### Anti-patterns to refuse

- "I improved the design" → no, that's the Architect's job
- "Added a helper class" → not in the spec, push back
- "Renamed the method" → breaks PJM's Logic Analysis, refuse

---

## Absorption note - twostraws/Swift-Agent-Skills (2026-05-14): REJECTED for absorption

Read the real source (MIT, Paul Hudson / Hacking with Swift, 84 stars, 2 commits). Finding: **it is not a skill - it is a curated directory of links** to other people's Swift skill repos (twostraws/SwiftUI-Agent-Skill, twostraws/Swift-Concurrency-Agent-Skill, twostraws/SwiftData-Agent-Skill, twostraws/Swift-Testing-Agent-Skill, plus community accessibility / App Store / Core Data / performance skills). The repo itself contains no SwiftUI, concurrency, or testing content - just a README index. It explicitly states being listed there is "not an endorsement."

So there is nothing to consolidate into this employee's methodology. The prior 2026-05-13 entry listed "patterns absorbed" from sub-skills that were never actually fetched or read - that was a description-based guess, not an absorption.

**Correct disposition (per the Absorption Doctrine - logical analysis, not dogma):**
- twostraws/Swift-Agent-Skills → **Talent Scout watchlist source.** It is a human-vetted index of Swift skills - exactly what the scout should mine. Moved to `available_sources_for_scout`.
- The individual linked repos (SwiftUI-Agent-Skill, Swift-Concurrency-Agent-Skill, SwiftData-Agent-Skill, Swift-Testing-Agent-Skill) are real, absorbable skills - but each must be fetched and run through the real 5-step protocol individually. That is a future scout pass, not this one. Listed as scout candidates.
- This employee already carries native iOS/Swift/SwiftUI coverage (wshobson native iOS/Android matrix). No methodology change was warranted from this source.

---

## Absorption note - callstackincubator/agent-device (2026-05-18)

Source: callstackincubator/agent-device (MIT, Callstack official - Callstack is the React Native consultancy of record, credible source). CLI to control iOS / Android / tvOS / Android TV / macOS / Linux devices for AI agents. Verified: `skills/agent-device/SKILL.md` exists with the documented patterns, real platform backends (XCTest / ADB+snapshot / local macOS helper / AT-SPI).

**Consolidated in (patterns layered on top of mobile-next/mobile-mcp + Android-Ui-MCP):**
- **Treat agent-device as the testing-layer companion to mobile-mcp, not a replacement.** mobile-mcp drives live interaction; agent-device adds .ad replay scripts, snapshot diffs, component-tree dumps, and tvOS/Android TV/desktop reach.
- **When platform is tvOS, Android TV, macOS, or Linux app** → mobile-mcp doesn't cover these, agent-device does. Use agent-device.
- **When recording a regression for a flaky bug** → capture an .ad replay script (runs in CI) rather than writing a fresh Appium/Detox test by hand.

---

## Absorption note - expo/skills (2026-05-18)

Source: expo/skills (Expo official - the React Native + EAS company). Skills authored by the Expo team specifically for a coding agent, Cursor, Codex. Fine-tuned for Opus models.

**Consolidated in (patterns lifted; layered on top of existing VoltAgent expo-react-native-expert coverage):**
- **For Expo + EAS workflows, prefer the official Expo skill patterns over generic React Native patterns.** Things like config-plugin idioms, EAS Build/Submit/Update flow, OTA update strategy, dev-client vs Expo Go choice - the official version is more current than what VoltAgent or generic RN sources document.
- **Skills are fine-tuned for Opus.** When using these patterns on Sonnet/Haiku, expect more hand-holding; the original skill prompts assume Opus reasoning.

**Rejected:** Installing the official `expo/skills` package wholesale via `bunx skills add expo/skills`. Per absorb-don't-replace doctrine, patterns lift into this employee. The Expo repo is a watchlist source - when Expo ships SDK 53/54 patterns, Talent Scout re-evaluates.

---

## Absorption note - ECC native-mobile language packs (2026-06-14)

Source: `affaan-m/everything-the coding agent-code` (ECC, MIT). 15 native-mobile skills lifted into `native-mobile-language-packs.md` (methodology only, NO code bundled).

**Consolidated in (layered on top of the existing RN/Expo default + `android-architecture.md` skeleton + `mobile-test-and-release.md`):**
- **Kotlin/Android/Compose** (kotlin-patterns, kotlin-coroutines-flows, kotlin-testing, kotlin-ktor-patterns, kotlin-exposed-patterns, android-clean-architecture, compose-multiplatform-patterns) - language idioms, structured-concurrency + Flow, Kotest+MockK+Turbine+Kover, layered module rules, Compose state/nav/perf, plus Ktor/Exposed for a KMP shared backend.
- **Dart/Flutter** (dart-flutter-patterns, flutter-dart-code-review) - null safety + Freezed + async `mounted` discipline + BLoC/Riverpod + GoRouter + Dio, and a 15-section library-agnostic review checklist.
- **Swift/SwiftUI/iOS** (swiftui-patterns, swift-concurrency-6-2, swift-actor-persistence, swift-protocol-di-testing, liquid-glass-design, foundation-models-on-device) - `@Observable` UI, Swift 6.2 Approachable Concurrency, actor persistence, protocol DI + Swift Testing, iOS 26 Liquid Glass, and Apple's on-device LLM.

**Disposition:** absorb-don't-replace per doctrine. The native packs are the language-depth companion to `android-architecture.md` (skeleton) and `mobile-test-and-release.md` (committed test/release suite). React Native + Expo remains the cross-platform default; native depth is for platform-specific features, fidelity, or performance. ECC remains a watchlist source for future SDK/version updates.

## Cross-employee integration patterns

(Org-wide catalog: `meta/chief-of-staff/references/cross-employee-integration-patterns.md`.)

**Mobile ↔ backend-developer** - mobile-specific backend (push notifications, deep links, in-app purchase server) is still backend. Backend owns the server side; mobile owns the app side.

**Mobile ↔ ui-ux-designer** - Apple HIG + Material guidelines per platform. UX provides specs; mobile flags platform conflicts.

**Mobile ↔ seo-aso-specialist** - ASO metadata (title, subtitle, keywords, screenshots). ASO owns strategy; mobile implements + submits.

**Mobile ↔ qa-engineer** - .ad replay scripts, device matrix testing. agent-device tooling is shared.

---

## Scout watch-list (NOT absorbed - below bar)
- **expo-mcp (~5★)** - an MCP server for Expo/EAS operations. WATCH only: at ~5 stars it is below the absorption bar, and this employee already carries Expo + EAS workflow patterns (config plugins, EAS Build/Submit/Update, OTA, dev-client vs Expo Go) absorbed from `expo/skills` (2026-05-18) plus VoltAgent's expo-react-native-expert. Re-evaluate as the "build-ship gate" only if it grows materially (stars + maintenance + a distinct capability our Expo coverage lacks). Do not install or absorb now.
