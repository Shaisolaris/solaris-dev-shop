# Unreal Scene & Game-Framework Architecture

> Load for: level/world structure, game-state flow, screen/UI stacks, manager patterns, save/load. The UE counterpart to unity-developer's `unity-scene-architecture.md`. Executed via the ChiR24 bridge tools (`manage_level`, `manage_game_framework`, `manage_blueprint`, `manage_widget_authoring`).

## The Gameplay Framework is your state machine
Every UE game runs on the Gameplay Framework - use it, don't reinvent it. Drive it with `manage_game_framework` (game modes, game states, player controllers, match flow).
- **GameMode** (server-authoritative) - rules of the current match/level: who can join, win/loss, spawning. One per level (or default in Project Settings).
- **GameState** - replicated state shared with all clients (score, match phase, timers).
- **PlayerController** - the player's intent layer (input → actions); owns the HUD/UI.
- **Pawn / Character** - the controlled body. `manage_character` for movement/locomotion.
- **PlayerState** - per-player replicated data (name, score, team).
- **Rule:** no free-floating systems. Every new mechanic has a clear owner in this hierarchy. If you can't say which class owns it, the architecture isn't done - fix that first.

## Levels, streaming, and World Partition
Drive with `manage_level` + `manage_level_structure`.
- **Persistent level + sublevels** for classic streaming, OR **World Partition** (UE5 default for large worlds) with **data layers** + **HLOD** for auto-streaming by distance/region.
- **Level streaming triggers** via `manage_volumes` (streaming volumes) - load/unload by player position.
- **Rule:** decide World Partition vs. sublevels at project start and record it in `CLAUDE.md`. Mixing them ad hoc causes streaming bugs.

## Screen / UI flow (UMG)
Drive with `manage_widget_authoring` (UMG widget creation, layout, styling, animations). PlayerController/HUD owns the widget stack.
- **Widget stack pattern:** a UI manager pushes/pops UserWidgets (menu → gameplay HUD → pause → results) - the same "every screen belongs to a state machine" rule as Unity.
- **Rule:** each screen has a defined entry state, exit state(s), and transition triggers. New screen with no defined flow = stop and map the flow first.
- For shared/cross-screen widgets and input routing, CommonUI is the modern UE pattern (enable the plugin if the game has controller + keyboard + touch).

## Manager / system patterns
- **GameInstance** - persists across level loads (use for save data, session info, cross-level state). The closest UE analog to a Unity persistent singleton.
- **Subsystems** (GameInstanceSubsystem / WorldSubsystem / EditorSubsystem) - the modern, lifecycle-managed alternative to manual singletons. Prefer these over global statics.
- **Data-driven config:** DataAssets / DataTables (not magic numbers in C++). Author/inspect via `manage_asset` + `inspect`. Mirrors Unity's ScriptableObject discipline.

## AI architecture
Drive with `manage_ai` + `manage_behavior_tree`.
- **Behavior Trees + Blackboard** for agent logic; **EQS** (Environment Query System) for spatial queries; **StateTree** for hierarchical state; **Smart Objects** for interactable-driven behavior; **AI Perception** for sight/hearing.
- **Rule:** keep AI parameters data-driven (Blackboard keys + DataAssets) so designers can tune without recompiling.

## Save / load
- GameInstance + SaveGame objects (UGameplayStatics Save/Load) for persistence. Define the save schema early and record it in `CLAUDE.md`.

## Networking (if multiplayer)
Drive with `manage_networking` + `manage_sessions`.
- **Server-authoritative** by default; replicate state via the GameState/PlayerState; use RPCs (Server/Client/Multicast) deliberately; client-side prediction for movement.
- **Rule:** plan for desync from day one. Choose dedicated vs. listen server early; sessions/LAN/voice via `manage_sessions` (OnlineSubsystem). Cross-platform via EOS.

## Cross-references
- `unreal-mcp-operator.md` - the tools that execute all of the above.
- `game-design-mentor.md` - the design questions that must be answered before building any of it.
- game-designer employee - owns the GDD, economy balance, and narrative; this employee implements.
