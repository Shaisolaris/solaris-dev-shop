# CLAUDE.md - Project Memory for [GAME NAME]

This file lives at the root of the Unreal project. Claude reads it at the start of every session so no question gets asked twice. Fill in what you know; leave blanks - Claude will help close them.

Last updated: [DATE]

---

## 1. Game concept (one paragraph)
> Example: *"VaultRunner is a 3rd-person UE5 action-platformer for PC. Players chain wall-runs and grapple swings through collapsing vaults against a timer. One run = one vault; failure restarts instantly. Rewards come from time medals + cosmetic unlocks. Target audience is core action players who play 10-20 minute sessions."*

[fill in]

## 2. Pillars (3-5 core experiences)
- [e.g. "flow-state traversal", "high-stakes timer tension", "readable, fair failure"]

## 3. Target platform & technical constraints
- **Primary platform:** [Win64 / PS5 / Xbox / Switch / iOS / Android / Multiple]
- **Min spec / target device:** [...]
- **Target framerate:** [30 / 60 / 120]
- **UE version:** [e.g. "5.4" - check the `.uproject` + engine association]
- **Rendering:** [Nanite on/off, Lumen vs baked GI, Forward vs Deferred]
- **Input:** [Enhanced Input - controller / KBM / touch]
- **Online:** [Single-player / Multiplayer - dedicated vs listen; EOS? Steam?]
- **World structure:** [World Partition / persistent + sublevels]

## 4. Architecture decisions (Gameplay Framework)
- **GameMode(s):** [...]
- **GameState / PlayerState replicated data:** [...]
- **Persistent state owner:** [GameInstance / Subsystem - which]
- **Save schema:** [SaveGame object fields]
- **Data-driven config:** [DataAssets / DataTables used]
- **AI:** [Behavior Trees / StateTree / EQS - where]

## 5. Screen / level flow map
> The state machine. Every level + UMG screen has an entry state, exit state(s), and transition triggers.

[Main Menu] → [Level Select] → [Gameplay (level N)] → [Pause | Results] → ...

## 6. MCP / tooling setup
- **Engine-control MCP:** ChiR24/Unreal_mcp (McpAutomationBridge) - server on port [8091], `UE_PROJECT_PATH=[...]`.
- **In-engine GenAI:** UnrealGenAISupport [enabled? AutoStart MCP? which LLM providers + keys via PS_* env vars].
- **Shared asset layer connected:** [blender-mcp / Tripo / Meshy / ElevenLabs - which are wired].

## 7. Art / asset budget
- **Poly / triangle budget per scene:** [...]
- **Texture memory budget:** [...]
- **Asset source:** [in-house Blender / prompt-to-3D providers / marketplace]

## 8. Standing decisions & conventions
- **Naming:** [BP_ / M_ / T_ / SK_ prefixes, folder structure]
- **C++ vs Blueprint split:** [what goes where]
- [other project-specific calls]

## 9. Known constraints / gotchas (seed from past sessions)
- [e.g. "node-wiring over MCP is flaky - author complex graphs in C++"]
- [e.g. "raise MCP request timeout before any cook/package"]

---
*Claude: update sections 4-9 whenever a new standing decision is made this session.*
