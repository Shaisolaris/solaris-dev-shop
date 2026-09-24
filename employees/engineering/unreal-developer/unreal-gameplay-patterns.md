# Unreal Gameplay Patterns - GAS, performance, networking, packaging (depth)

> **Depth absorption 2026-06-13 (v0.2.0).** Methodology lifted from `tranek/GASDocumentation` (MIT, 5.8k stars - Gate-0 PASS, the de-facto-standard GAS reference) and informed by concepts from `tomlooman/ActionRoguelike` (NOASSERTION - concepts only, no code/text lifted) and general UE net-mode methodology. Load this when a task goes past spawning/wiring and into building an actual gameplay system: abilities/stats/damage, multiplayer correctness, frame-budget, or shipping a build. The operator file (`unreal-mcp-operator.md`) is the HOW-to-drive-the-editor; this file is the WHAT-to-build-and-why. The employee previously had the `manage_gas` / `manage_performance` / `manage_networking` tools but no methodology behind them - this file is that methodology.

This is engine-knowledge, not tool-knowledge. Apply it through the bridge: author the structure with `manage_gas` / `manage_blueprint` / `manage_networking` / `manage_performance`, but make the design decisions here first. As always: prefer C++ for the load-bearing logic and verify the compiled result (the bridge's Blueprint node-wiring is the known weak spot).

---

## Part 1 - Gameplay Ability System (GAS): when and how

### Decision gate: do you even need GAS?
GAS is powerful and heavy. Use it when the game has many interacting abilities, stats, buffs/debuffs, and especially multiplayer with prediction. For a small single-player prototype with two or three abilities, a lighter component-based "Action" pattern (the ActionRoguelike approach: an ActionComponent holding UAction objects gated by GameplayTags) is faster to stand up and easier to reason about. **Rule:** don't reach for full GAS on a prototype; reach for it when the ability/stat matrix is genuinely combinatorial or when networked prediction is required.

### The five GAS pieces (the mental model)
1. **AbilitySystemComponent (ASC).** The brain. Lives on the Pawn (for respawn-resetting state) or the PlayerState (for state that must survive respawn, e.g. MOBA/MP). **Rule:** decide ASC ownership at project start and record it in `CLAUDE.md` - moving it later is painful.
2. **AttributeSet.** The stats (Health, Mana, Stamina, AttackPower). Each attribute has a BaseValue and a CurrentValue. Clamp and react to changes in `PreAttributeChange` / `PostGameplayEffectExecute`, not in ad-hoc Blueprint.
3. **GameplayAbility (GA_).** A self-contained activatable action (Dash, Fireball, Reload). Has cost, cooldown, and tags that gate activation. Abilities are granted to the ASC, then activated by tag or input.
4. **GameplayEffect (GE_).** How attributes change. Three durations: **Instant** (one-shot, modifies BaseValue - e.g. damage), **Duration** (timed buff, modifies CurrentValue - e.g. 10s speed boost), **Infinite** (until removed - e.g. equipped-item bonus). **Periodic** effects tick (e.g. damage-over-time). Use **modifiers** for simple math and **Execution Calculations** (C++) for complex formulas (armor mitigation, crit).
5. **GameplayTags + GameplayCues.** Tags (hierarchical, e.g. `State.Stunned`, `Ability.Dash`) are the gameplay vocabulary: gate activation, mark state, classify everything. **GameplayCues** are the cosmetic layer (VFX/SFX) fired by tag, so visuals replicate cleanly without bespoke RPCs.

### The damage pattern (the canonical worked example)
Damage is an Instant GameplayEffect with a `SetByCaller` magnitude (the weapon sets the number at runtime), applied through an Execution Calculation that reads the target's Armor attribute and the source's AttackPower, mitigates, and writes the result to a meta-attribute (`Damage`) that `PostGameplayEffectExecute` subtracts from Health. Health is never modified directly. **Rule:** route all stat changes through GameplayEffects, never `Health -= X` in a Blueprint - that breaks prediction, replication, and the buff stack.

### GAS replication modes (pick deliberately)
- **Full** - replicate GameplayEffects to everyone. Single-player / small co-op.
- **Mixed** - GEs replicate to the owning client only; tags/cues to everyone. The standard for player-controlled multiplayer characters.
- **Minimal** - no GE replication; only tags/cues. AI minions in multiplayer.
**Rule:** Mixed for players, Minimal for AI, in a real MP game. Set the mode on the ASC at init.

---

## Part 2 - Performance methodology (profile, then fix the right thing)

### Always profile before optimizing
The number-one Unreal performance mistake is optimizing by vibes. Measure first.
- **`stat unit`** - the first command, every time. Splits frame time into Game (CPU gameplay), Draw (CPU render-thread / draw calls), GPU, and RHIT. Whichever is highest is your bottleneck - optimize THAT, ignore the rest.
- **`stat game`, `stat scenerendering`, `stat gpu`** - drill into the dominant cost.
- **Unreal Insights** - the real profiler for frame-level investigation (Window > Developer Tools, or `-trace=` on launch). Use it for hitches and per-frame breakdowns; drive captures via `system_control` console commands and `manage_performance`.
- **Rule:** "the game feels slow" is not a bug report. `stat unit` it, name the bottleneck thread, then act.

### The high-leverage CPU fixes (in rough order)
1. **Kill Tick.** Per-frame `Tick` on many actors is the most common Game-thread killer. Prefer event-driven logic, timers (`SetTimerByEvent`), and lower tick intervals (`SetActorTickInterval`) or tick groups. ActionRoguelike's "aggregate ticking" idea: one manager ticks and updates N pooled objects, instead of N actors each ticking.
2. **Object / actor pooling.** Spawning and destroying actors (projectiles, impact FX) every frame thrashes memory and the GC. Pool them: pre-spawn, deactivate/reactivate, reuse. (The OSS `JanSeliv/PoolManager` is a concrete option; ActionRoguelike ships its own.)
3. **Significance Manager.** For many AI/actors, drive update frequency by distance/importance - distant enemies tick their AI far less often. This is the scalable answer to "100 enemies tank the frame."
4. **Async loading via Asset Manager.** Don't hard-reference heavy assets that load synchronously and hitch. Use soft references + `StreamableManager` async loads (ActionRoguelike does this for UI icons and DataAssets).

### The GPU / render-thread fixes
- **Draw calls (Draw thread high):** merge meshes, use instanced static meshes (ISM/HISM), enable Nanite for dense static geometry, cull aggressively (HLOD, distance culling).
- **Nanite and Lumen are NOT free.** They move cost around and add a GPU floor. Verify on the LOWEST target platform, not the dev machine. For mobile/Switch they are often the wrong call entirely.
- **Shader/PSO hitching:** precache PSOs (Pipeline State Objects) and bundle them so the first time an effect plays it does not stutter. ActionRoguelike ships a PSO-precaching + bundled-PSO setup for DX12 - adopt the same discipline for any shipped Windows build.

---

## Part 3 - Networking methodology (correctness from day one)

Multiplayer cannot be bolted on. Decide the model at project start and record it in `CLAUDE.md`. Concepts here are general UE net methodology (informed by the GASDocumentation MP sample and standard net-mode references; no text lifted).

### Net modes and the authority model
- **Net modes:** Standalone (no net), Dedicated Server (authoritative server, no local player - the production MP target), Listen Server (one player IS the host - convenient but the host has unfair zero-latency).
- **Roles:** **Authority** (the server's copy, the source of truth), **Autonomous Proxy** (the client controlling THIS pawn - gets prediction), **Simulated Proxy** (everyone else's pawn on your screen - interpolated). **Rule:** ask "what role is this code running on?" before writing any replicated logic. `HasAuthority()` gates server-only logic.

### The replication toolkit
- **Replicated properties:** mark with `Replicated` + register in `GetLifetimeReplicatedProps` (`DOREPLIFETIME`). The server changes the value; clients receive it.
- **RepNotify (`ReplicatedUsing`):** a callback fires on clients when a replicated value arrives - use it to trigger reactions (play a sound when Health drops), not just to store the value. Cheaper and more reliable than a Multicast RPC for state changes.
- **RPCs:** **Server** (client asks server to do X - must `WithValidation`), **Client** (server tells one client), **Multicast** (server tells everyone). **Rule:** RPCs are unreliable by default and fire-and-forget; for STATE use replicated properties + RepNotify, reserve RPCs for events.
- **Relevancy and dormancy:** the server only replicates relevant actors (distance/visibility) and can mark idle actors **dormant** to stop wasting bandwidth. Tune these for large MP worlds.
- **Prediction:** client-side movement prediction (CharacterMovementComponent does this for you) and GAS ability prediction keep the game responsive under latency. **Rule:** plan for desync - the server reconciles; the client predicts and corrects.

### The MP discipline
- Build and test multiplayer EARLY with PIE's multiple-client mode (`control_editor` PIE, set Number of Players > 1). A feature that works in Standalone but not over the network is not done.
- ActionRoguelike's lesson: design every feature replicated from the start; retrofitting replication onto single-player code is a rewrite.

---

## Part 4 - Packaging and shipping methodology

The bridge drives the build (`system_control` UBT build actions); this is the methodology for getting a clean, shippable artifact.

### The pipeline (what actually happens)
1. **Compile** the C++ (UBT) for the target configuration (Development for testing, Shipping for release).
2. **Cook** content for the target platform - converts assets to the platform's runtime format. This is the slow step; it is what blows past the default request timeout. (Under the hood: `RunUAT BuildCookRun`.)
3. **Stage and package** into the distributable (a `.pak`/IoStore container + the executable).
- **Rule (carried from learnings):** raise `MCP_AUTOMATION_REQUEST_TIMEOUT_MS` well above 120s before any cook/package, or it WILL time out mid-cook.

### Build configurations
- **Development** - debuggable, with editor-ish tooling, slow. For test packages.
- **Shipping** - optimized, stripped logging, no console by default. For release and for real performance numbers. **Rule:** never report perf from a Development build; profile in Shipping on target hardware.

### Shipping hygiene
- **Chunking / asset cooking:** for large games or patching, split content into chunks (pak chunks) via the Asset Manager / PrimaryAssetLabels so you can deliver and patch in pieces.
- **PSO precaching:** bundle collected PSOs into the build so players do not get first-encounter shader hitches (see Part 2). This is a shipping requirement on DX12/console, not a nicety.
- **Secrets:** never ship API keys in the package (carried rule - for any in-engine LLM/GenAI features route keys through a backend). 
- **Store submission logistics** (cert, age ratings, store assets) are NOT this employee - route to product-manager and reuse the unity build/deploy/store discipline (anthropic-skills:unity) which already covers store flow.

---

## Cross-references
- `unreal-mcp-operator.md` - the tools that execute all of the above (note: 23 broad tools, `manage_gas` / `manage_performance` / `manage_networking` are the relevant entry points).
- `unreal-scene-architecture.md` - where these systems hang in the Gameplay Framework (ASC ownership, GameState replication).
- `unreal-testing-pipeline.md` - PIE multi-client testing + the cook/package timeout rule.
- `game-design-mentor.md` - answer the four design questions before building any of this.
- `game-designer` employee - owns the economy/balance numbers these systems express.

## Re-check schedule
- Quarterly with the rest of the stack: re-fetch GASDocumentation (tracks UE versions) for API/prediction changes; re-skim ActionRoguelike's main branch for new shipped patterns (concepts only).
