# Unity Developer - Top-5 Verified 2026 Sources

Deep-pass source verification for the unity-developer employee (Solaris Studio is a Unity game studio, so this is a high-value role). All star counts, licenses, and last-commit dates were verified directly against GitHub on 2026-06-13. "Gate-0" = grep of the employee's ACTUAL reference content to determine whether the source's value is already absorbed (content-duplicate) or net-new.

Selection bar: established/safe, 100+ stars OR 50+ with a notable maintainer, permissive license preferred (GPL/AGPL/NOASSERTION flagged), commit activity within ~6 months. Coverage targets: Unity MCP/automation, gameplay patterns, performance/profiling, mobile build+ship (iOS/Android), IAP/ads, testing.

---

## 1. CoplayDev/unity-mcp  -  CONNECT (content-duplicate, re-verified)

- **URL:** https://github.com/CoplayDev/unity-mcp
- **Stars:** 10,062 (verified GitHub API 2026-06-13)
- **License:** MIT (permissive, safe)
- **Last commit / push:** 2026-05-27 (well within 6mo); default branch beta, 1,131 forks, 66 subscribers
- **Maintainer:** Coplay (org, commercial-backed, active; 43 open issues, weekly-ish cadence)
- **What it adds:** The PRIMARY Unity MCP bridge. Tool groups (vfx/animation/ui/testing), Roslyn script validation, multi-instance routing, remote-hosted server with auth, built-in test runner.
- **Gate-0 verdict:** PRESENT / content-duplicate. Already absorbed as PRIMARY in coplaydev-unity-mcp.md (absorbed 2026-06-08) and referenced in rules.md. No new content to absorb.
- **Tag:** CONNECT. Action taken this pass: corrected the stale stars (file said 10.4k, actual 10,062) and fixed the phantom-file problem (it was unregistered in plugin.json, now registered). Re-check stars/version quarterly.

## 2. game-ci/unity-builder (GameCI)  -  ABSORB (net-new)

- **URL:** https://github.com/game-ci/unity-builder  (org: https://github.com/game-ci)
- **Stars:** ~1,000 (verified GitHub repo page 2026-06-13); "Used by 7.8k" dependents
- **License:** MIT (permissive, safe) - explicitly "free for everyone forever"
- **Last commit / release:** v4.8.1 released 2025-11-22; 471 commits, active TypeScript codebase
- **Maintainer:** GameCI open-source project (notable, widely adopted org; backed by OpenCollective)
- **What it adds:** The missing build+ship layer. GitHub Actions to build Unity for iOS/Android/PC/WebGL in CI, license activation, paired with fastlane for code signing + store distribution (TestFlight / Play internal). This is the "took a month to republish 6 games" pain point that Editor-side MCP automation does NOT solve.
- **Gate-0 verdict:** NOT PRESENT. The only CI mention in the employee is -batchmode -nographics for the MCP autonomous loop (unity-testing-pipeline.md, unity-mcp-operator.md). There is NO build-and-ship CI/CD content (Actions workflow, license activation, fastlane lanes, code signing, store upload). Net-new.
- **Tag:** ABSORB (methodology + reference). Lifted into a new reference file unity-build-ship.md this pass.

## 3. GuardianOfGods/unity-mobile-optimization  -  METHODOLOGY (mostly net-new)

- **URL:** https://github.com/GuardianOfGods/unity-mobile-optimization
- **Stars:** 92 (verified 2026-06-13) - under 100 but qualifies on the "50+ with a notable maintainer" exception: HoangVanThu also maintains unity-interview-questions, unity-mobile-developer, and unity-mobile-gamebase (a recognized Unity-mobile maintainer)
- **License:** MIT (permissive, safe)
- **Last commit:** active; 79 commits, embedded asset images timestamped 2026-06 (within 6mo)
- **Maintainer:** HoangVanThu (GuardianOfGods) - focused, ongoing
- **What it adds:** A concrete mobile optimization + build-size playbook: texture import settings (Max Size, POT, atlas, Read/Write off, mipmaps, ASTC/ETC compression), audio compression (Force-to-mono, Vorbis/ADPCM, 22.05kHz, load-type by clip size), mesh compression, animation error tolerances, object pooling, recyclable scroll, centralized Update (manager pattern), physics layer matrix + fixed timestep for low-end, GPU instancing, LOD, fake shadows, graphics API choice.
- **Gate-0 verdict:** MOSTLY NOT PRESENT. The employee has only scattered profiler tips and "Strip Engine Code / Incremental GC" in unity-testing-pipeline.md. The texture/audio/mesh import discipline, build-size reduction, object pooling, and centralized-update guidance are NOT present. Net-new methodology.
- **Tag:** METHODOLOGY. Lifted (no code bundled, knowledge only) into a new unity-performance-mobile.md reference this pass.

## 4. alttester/AltTester-Unity-SDK  -  METHODOLOGY + self-host note (GPL FLAGGED, content-duplicate)

- **URL:** https://github.com/alttester/AltTester-Unity-SDK
- **Stars:** 102 (verified 2026-06-13)
- **License:** GPL-3.0 - FLAGGED. Plus an "Unknown" license on LICENSE.meta (NOASSERTION on one file). Copyleft: do NOT bundle source/binaries into a shipped game build without legal review; use as an external test harness only.
- **Last commit / release:** V.2.3.0 released 2026-01-28; 3,439 commits (very active maintainer)
- **Maintainer:** AltTester (company-backed, active)
- **What it adds:** UI-driven E2E test automation for Unity (the "Playwright for Unity"). C#/Python/Java/Robot drivers, object find/interact, headless run in Editor or against a build.
- **Gate-0 verdict:** PRESENT / content-duplicate. Already documented in unity-testing-pipeline.md (install + Python example + flow list). Two fixes applied this pass: (a) corrected the install URL (alttester-unity-sdk.git -> AltTester-Unity-SDK.git); (b) added the GPL-3.0 flag + self-host/external-harness note that was missing.
- **Tag:** METHODOLOGY + self-host note (GPL). No source bundled; methodology only.

## 5. Unity-Technologies/game-programming-patterns-demo  -  METHODOLOGY (FLAGGED: no license + stale)

- **URL:** https://github.com/Unity-Technologies/game-programming-patterns-demo
- **Stars:** 1,700 (verified 2026-06-13)
- **License:** NONE / NOASSERTION - FLAGGED. No LICENSE file in the repo. Treat as reference-only; do not copy code verbatim. Companion to Unity's free e-book "Level up your code with game programming patterns."
- **Last commit:** STALE - only 9 commits, no releases, no recent activity (fails the ~6mo window). The e-book/patterns themselves remain current and authoritative.
- **Maintainer:** Unity Technologies (official; highest authority, but this companion repo is not actively maintained)
- **What it adds:** Canonical Unity implementations of GoF/game patterns: Observer, State, Command, Factory, Object Pool, MVC/MVP, plus SOLID/KISS/DRY framing.
- **Gate-0 verdict:** PARTIALLY PRESENT. The employee's unity-scene-architecture.md has Singleton + ScriptableObject Event-Channel patterns, but Observer/State/Command/Factory/Object-Pool/MVC are NOT covered as a pattern toolkit. The watchlist note in rules.md (MuharremTozan) flags the gap but no content exists.
- **Tag:** METHODOLOGY only (no code, no bundling - license and staleness both forbid lifting code). The named patterns are well-known and were summarized into the patterns section of unity-scene-architecture.md from general knowledge, with this source cited as a study reference, not copied.

---

## Coverage note: IAP / ads

The IAP/ads category in 2026 is dominated by official, commercial SDKs (Unity LevelPlay / IronSource, Google AdMob, AppLovin MAX) rather than star-bearing community OSS. There is no safe, permissive, high-star community repo that materially beats the official docs here, so no candidate was forced into the Top-5 for this category. Practical IAP/ads integration guidance (Unity IAP, AdMob, sandbox testing in the ship flow) was instead operationalized inside unity-build-ship.md and the CLAUDE_template.md monetization fields, pointing at the official SDKs. Re-scan quarterly in case a strong OSS mediation wrapper emerges.

## Flag summary for Shai

- AltTester (GPL-3.0): methodology absorbed, source NOT bundled. Safe as an external test harness; legal review before shipping any GPL code inside a game binary.
- game-programming-patterns-demo (no license + stale): patterns described from general knowledge and cited as a study reference only; no code lifted. Repo itself is not maintained - rely on the e-book, not the repo.
- GuardianOfGods (92 stars): just under the 100-star bar; included under the notable-maintainer exception. Flagged for transparency.
