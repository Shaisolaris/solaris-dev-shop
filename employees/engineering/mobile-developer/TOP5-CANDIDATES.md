# Top-5 Verified 2026 Sources: Mobile Developer Strengthening Pass

> Verification pass run 2026-06-13. Each source verified against live GitHub (stars, license, last commit) plus a Gate-0 grep of THIS employee's actual content. Pillars targeted: React Native/Expo, Flutter, native iOS/Android, app-store release, push, mobile testing.

## Selection summary

| # | Source | Stars | License | Last commit / release | Maintainer | Pillar | Gate-0 verdict | Tag |
|---|--------|-------|---------|-----------------------|------------|--------|----------------|-----|
| 1 | [mobile-dev-inc/Maestro](https://github.com/mobile-dev-inc/Maestro) | 14.1k | Apache-2.0 | CLI 2.5.1, 2026-04-30 | mobile.dev (commercial backer) | Mobile testing (cross-platform E2E, CI-grade) | NAMED ONLY (listed in SKILL.md testing line + 1 passing mention in mobile-mcp-operator.md "for production CI use Detox / Maestro / Espresso"); NO methodology, no flow syntax, no CI lane | ABSORB (methodology) |
| 2 | [fastlane/fastlane](https://github.com/fastlane/fastlane) | 41.3k | MIT | 2.232.2, 2026-02-27 | fastlane team (Google-stewarded) | App-store release / CI-CD | NAMED ONLY (SKILL.md DevOps line "Fastlane (build + match + deliver + supply)"); no operational lane, no tool-to-task mapping | METHODOLOGY (deepen) |
| 3 | [wix/Detox](https://github.com/wix/Detox) | 11.8k | MIT | 20.50.4, ~2026-06 | Wix (official) | React Native E2E testing | NAMED ONLY (SKILL.md testing list "Detox + Maestro + Patrol"); no setup/methodology | ABSORB (methodology) |
| 4 | [leancodepl/patrol](https://github.com/leancodepl/patrol) | ~1.3k | Apache-2.0 | Patrol 4.0, 2026 | LeanCode (official) | Flutter E2E + native-interaction testing | NAMED ONLY (SKILL.md testing list); no methodology, native-interaction gap (permissions/notifs/webviews) uncovered | ABSORB (methodology) |
| 5 | [cashapp/paparazzi](https://github.com/cashapp/paparazzi) | 2.5k | Apache-2.0 | active 2026 (1.x line) | Cash App / Block (official) | Native Android visual regression (JVM, no device) | CONTENT-GAP (employee only has generic "Visual regression (Chromatic-style for mobile)"; no JVM screenshot-test methodology, no Compose preview test path) | ABSORB (methodology) |

## Pillar coverage check
- **React Native / Expo** -> Detox (#3); Expo/EAS already absorbed 2026-05-18.
- **Flutter** -> Patrol (#4): fills the Flutter native-interaction test gap (integration_test cannot touch OS dialogs).
- **Native iOS / Android** -> Paparazzi (#5, Android JVM screenshot); Maestro (#1) covers iOS too.
- **App-store release** -> fastlane (#2): deliver/supply/match/pilot lanes.
- **Push** -> not a top-5 (employee already lists FCM/APNs/rich/silent at competency level; no high-signal permissive push library rose above the testing/release gaps). Flagged for Shai below.
- **Mobile testing** -> Maestro, Detox, Patrol, Paparazzi (four-way depth).

## License flags
- None flagged. All five are MIT or Apache-2.0 (permissive). No GPL / AGPL / NOASSERTION.

## Alternates considered (not selected)
- [takahirom/roborazzi](https://github.com/takahirom/roborazzi): 951 stars, Apache-2.0, 1.63.0 (2026-05-02). Strong Compose+AI-assertion screenshot tool; below Paparazzi on stars/maturity. Logged as scout watch.
- Google official **Compose Preview Screenshot Testing** (`com.android.compose.screenshot`): first-party, but still alpha as of 2026-06. Note in methodology, do not hard-depend.
- [sergio-sastre/ComposablePreviewScanner](https://github.com/sergio-sastre/ComposablePreviewScanner): auto-generates screenshot tests from previews across libraries. Scout watch.

## Gate-0 method
Greps run against the live employee dir (SKILL.md, rules.md, android-architecture.md, mobile-mcp-operator.md, learnings.md): `maestro`, `fastlane`, `detox`, `patrol`, `paparazzi/roborazzi/screenshot test`, `crash-free/99.5`, `app size/bundle size/cold start`. Findings: tool NAMES appear in capability lists but carry zero operational methodology; visual-regression and release-automation have no formulas or lanes. This pass adds the missing methodology, not new tool names.
