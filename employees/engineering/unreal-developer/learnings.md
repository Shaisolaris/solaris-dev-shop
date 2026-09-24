# Unreal Developer - Learnings

Read at the start of every Unreal session. Append at the end when a lesson surfaces. Promote to SKILL.md when a lesson recurs across 2+ games.

## Seed entries (from source absorption, 2026-06-13)

### MCP / operator mistakes
- **2026-06-13 - First-open plugin "failed to load" is expected.** When opening a `.uproject` for the first time with McpAutomationBridge, UE rebuilds modules then still reports the plugin failed to load in the SAME session. **Rule:** close + reopen the project (or build in Visual Studio first); never debug this as a real failure - warn Shai up front.
- **2026-06-13 - Cook/package times out at the default 120s.** Long-running pipeline ops exceed `MCP_AUTOMATION_REQUEST_TIMEOUT_MS=120000`. **Rule:** raise the timeout before any `system_control` build/cook/package call (this op was `manage_pipeline` pre-v0.5.30; now consolidated into `system_control`).
- **2026-06-13 - Blueprint node-wiring over MCP is flaky (upstream-acknowledged).** Nodes fail to connect; getter/setter spawning is buggy; compile errors aren't surfaced cleanly. **Rule:** prefer C++ for complex graphs; after any MCP Blueprint edit, verify the compile + inspect the result rather than assuming it took.

### Asset-gen mistakes
- **2026-06-13 - UnrealGenAISupport in-editor prompt-to-3D is in-progress upstream.** Don't rely on the in-editor prompt→3D→spawn path for production. **Rule:** generate 3D via the providers' own MCPs/APIs (Tripo/Meshy) + refine in blender-mcp, then import the mesh.
- **2026-06-13 - DeepSeek reasoner needs UE HTTP timeout bumps + a mandatory system message.** R1 calls exceed UE's 30s default; setting `HttpRequest->SetTimeout` alone isn't enough. **Rule:** add `HttpConnectionTimeout=180` / `HttpReceiveTimeout=180` to `DefaultEngine.ini`; always include a system message; never feed `reasoning_content` back (400).

### Security mistakes
- **2026-06-13 - Never ship API keys in packaged builds.** **Rule:** route LLM calls through a backend for production; runtime-set keys only for test builds; never expose client-side.
- **2026-06-13 - MCP gives the AI client direct project control.** **Rule:** back up + version-control before enabling MCP; keep loopback-only bind unless Shai explicitly wants LAN.

### Depth-absorption learnings (2026-06-13, v0.2.0 - from GASDocumentation + ActionRoguelike concepts + base re-verify)
- **2026-06-13 - BASE DRIFT: ChiR24 is 23 tools now, not 36.** Re-verified upstream (v0.5.30, UE 5.0-5.8, 681 stars). Tools were consolidated (UMG into `manage_blueprint`, sessions/game-framework/input into `manage_networking`, `manage_pipeline` into `system_control`); `manage_pcg` was added; a Native MCP HTTP/SSE transport now exists (no Node bridge). **Rule:** trust the operator file's corrected table + migration note; if unsure what is live, call `manage_tools`.
- **2026-06-13 - Never modify a GAS attribute directly.** `Health -= X` in a Blueprint breaks prediction, replication, and the buff stack. **Rule:** route ALL stat changes through GameplayEffects; clamp/react in `PostGameplayEffectExecute`; use a `Damage` meta-attribute. (gameplay-patterns Part 1.)
- **2026-06-13 - Decide ASC ownership before building GAS.** Pawn (state resets on respawn) vs PlayerState (state survives respawn, MOBA-style). Moving it later is painful. **Rule:** record ASC owner + replication mode (Mixed for players, Minimal for AI) in `CLAUDE.md` at project start.
- **2026-06-13 - `stat unit` before any optimization.** The dominant thread (Game/Draw/GPU) is the only one worth fixing. **Rule:** "feels slow" is not a report; name the bottleneck thread first. Tick is the usual Game-thread culprit; pool actors; use the Significance Manager for many AI.
- **2026-06-13 - Don't reach for full GAS on a prototype.** A component-based Action pattern (ActionComponent + tagged abilities) is faster to stand up. **Rule:** match the pattern to stakes; full GAS only when the ability/stat matrix is combinatorial or networked prediction is required.
- **2026-06-13 - For replicated STATE use properties + RepNotify, not Multicast RPCs.** RPCs are unreliable/fire-and-forget by default. **Rule:** properties + `DOREPLIFETIME` + RepNotify for state; reserve RPCs for one-off events; test MP with PIE multi-client EARLY.

### C++ language-quality learnings (2026-06-14, v0.3.0 - from affaan-m/ECC cpp-* skills, methodology only)
- **2026-06-14 - Smart pointers are for plain C++, NOT UObjects.** `std::unique_ptr`/`std::shared_ptr` (or `TUniquePtr`/`TSharedPtr`) manage native resources and non-UObject types; UObjects are GC-owned and kept alive by `UPROPERTY()`/`TObjectPtr`. **Rule:** never `new`/`delete` a UObject (use `NewObject`/`SpawnActor`); hold non-owning UObject refs as `TWeakObjectPtr` and check validity. (cpp-quality-and-build Part 1+2.)
- **2026-06-14 - Block C++ on memory-safety or data-race defects, warn on style.** Triage every C++ change CRITICAL/HIGH/MEDIUM: raw new/delete, use-after-free, uninitialized vars, data races, manual lock/unlock are blockers; copies/const-correctness/magic-numbers are warnings. **Rule:** a memory-safety or concurrency bug is never "ship and clean up later".
- **2026-06-14 - Never touch UObjects/world off the Game thread.** Most engine APIs are not thread-safe. **Rule:** marshal back via `AsyncTask(ENamedThreads::GameThread, ...)`; apply CP.* (RAII named locks, scoped_lock/FScopeLock for multiple mutexes, no volatile-for-sync, no detached threads) to all task/async/server code.
- **2026-06-14 - Pick the cheaper test surface.** Plain non-UObject C++ (math, parsers, data structs, server/tool code) -> GoogleTest/CTest in CI (fast, no editor; pin GoogleTest via FetchContent; ASan/UBSan/TSan builds). Anything needing a world/actors/PIE -> UE Automation via `system_control`. **Rule:** do not boot the editor to unit-test logic GoogleTest could cover.
- **2026-06-14 - Build errors: read the FIRST one, fix surgically, do not thrash.** Compilers cascade. **Rule:** read first error -> read the file -> minimal fix (no refactor while fixing a build) -> rebuild -> re-run tests. Stop after 3 failed attempts on the same error or if a fix needs architectural change. In UE, read the UHT/reflection error (missing GENERATED_BODY, Build.cs module, .generated.h order), not just the compiler error.

- **2026-08-13 - named-heading protocol**: measured D5 gap was job-two omitting contract-required artifact headings; closed by named-heading protocol in `job-two-improvement.md`.

## Promotion log
| Date | Rule | Promoted to |
|------|------|-------------|
| | | |

## absorbed_from (this folder's record - mirrors plugin.json)
- 2026-06-13 v0.2.0 DEPTH: tranek/GASDocumentation (MIT, 5.8k stars) -> GAS methodology in `unreal-gameplay-patterns.md` (Gate-0 PASS). tomlooman/ActionRoguelike (NOASSERTION, 4.4k - concepts only, license FLAGGED) -> perf/pooling/async/PSO/replicate-early concepts. insthync/awesome-unreal (Unlicense, 1.5k) -> scouting index. Base re-verified: ChiR24/Unreal_mcp now 23 tools / UE 5.0-5.8 / v0.5.30. See TOP5-CANDIDATES.md.

- 2026-06-14 v0.3.0 ECC LANGUAGE DEPTH: affaan-m/ECC (everything-claude-code, MIT, renamed) cpp-reviewer + cpp-coding-standards + cpp-testing + cpp-build-resolver (Core Guidelines) -> unreal-cpp-quality-and-build.md (C++ review triage + standards checklist + GoogleTest/CTest + sanitizers + C++/CMake/UBT build-fix loop). Methodology only, NO code bundled; adapted to Unreal (UObject GC / TObjectPtr / UBT / Epic coding standard / Game-thread). Gate-0 PASS (zero prior C++-language methodology). Kept a delta vs the engine files.
