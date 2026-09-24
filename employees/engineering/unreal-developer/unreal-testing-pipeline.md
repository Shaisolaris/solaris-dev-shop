# Unreal Testing & Build/Package Pipeline

> Load for: testing, PIE/standalone, automation tests, building/cooking/packaging, target platforms, visual QA. The UE counterpart to unity-developer's `unity-testing-pipeline.md`. Executed via `control_editor` + `system_control` (UBT build/cook/package actions; the old `manage_pipeline` tool was consolidated into `system_control` as of ChiR24 v0.5.30).

## Test in the cheapest mode first
1. **PIE (Play-In-Editor)** - fastest loop. Start/stop via `control_editor`; screenshot the viewport. Use this for almost all iteration. Never reach for a packaged build to test basic logic.
2. **Standalone / New Editor Window (PIE variants)** - when you need a real game window (input focus, multiple clients for MP testing).
3. **Packaged build** - only for platform-specific behavior, perf on target hardware, or store submission.
- **Rule:** if Shai is building/cooking to test something that PIE would catch, the pipeline is being misused.

## Automation tests over MCP
- UE has a built-in **Automation** framework (Functional tests, unit-style tests, Gauntlet for device automation). Run them via `system_control` (tests) and read results.
- **Rule:** every new gameplay system gets at least a smoke Functional test; run it via `system_control` before declaring a fix done - the UE parity of Unity's `tests-run`.
- Read logs via `system_control` BEFORE guessing at a failure.

## Visual QA is automated, not optional
- After any level/scene change, capture a viewport/camera screenshot via `control_editor` and eyeball it yourself. For repeatable checks, capture from a fixed camera/bookmark so screenshots are comparable across sessions (visual regression).
- **Rule:** don't ask Shai to take a screenshot; take it.

## Build / cook / package
Drive with `system_control` (UBT build/cook/package actions, project settings, CVars; this absorbed the old `manage_pipeline` tool). Methodology in `unreal-gameplay-patterns.md` Part 4.
- **Raise the request timeout first:** set `MCP_AUTOMATION_REQUEST_TIMEOUT_MS` well above the 120s default - a real cook/package takes minutes.
- **Sequence:** compile (UBT) → cook content for target → package. Check status between steps via `system_control`.
- **Project settings / CVars** for scalability + platform config via `system_control`.

## Target platforms
- **PC:** Win64 (primary), Linux, Mac.
- **Console:** PS5, Xbox Series X/S, Switch - require devkits + certification (route cert/store logistics to product-manager + the anthropic-skills unity build/deploy skill where it overlaps; UE packaging here, store submission there).
- **Mobile:** iOS/Android (Win64/Mac toolchains; UnrealGenAISupport notes mobile + console platform support for its plugin).
- **Rule:** record the target platform set in `AGENTS.md`; don't guess scalability settings - derive from the target.

## Performance
- Drive with `manage_performance` (profiling, optimization, scalability) + `profiler`-style CVars via `system_control`.
- **Rule:** profile before optimizing. Nanite/Lumen are not free - verify on the lowest target platform, not just the dev machine.

## Cross-references
- `unreal-mcp-operator.md` - the tool surface.
- `unreal-scene-architecture.md` - what you're testing.
- anthropic-skills:unity - overlapping build/deploy/store knowledge for Solaris Studio titles (the Unity skill already covers store submission; reuse that discipline for UE store work).
