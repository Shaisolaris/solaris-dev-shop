# Unity Game Dev - Lessons Log

Self-updating log of Unity mistakes, design failures, and repeat patterns across Shai's games. Read at the start of every Unity session.

**Format per entry:**
- **Project / date - specific thing that happened**
  *Rule: the generalized takeaway that prevents repeat.*

**Categories:**
- Design mistakes (player flow, game feel, screen logic)
- Scene architecture mistakes (state machines, UIManager, transitions)
- Testing mistakes (Device Simulator, Unity Remote, QA gaps)
- Build/pipeline mistakes (iOS, Android, WebGL, signing, assets)
- MCP operator mistakes (misusing the Unity MCP bridge, over-automation)
- Client/scope mistakes (game-specific)

---

## Seed entries (kickstart rules before real lessons accumulate)

- **Any project / 2026-04-23 - Claude kept asking "what platform are you targeting?" every session.**
  *Rule: Target platform, input model, orientation, and minimum device are standing decisions. They live in the project's CLAUDE.md. Never ask questions that CLAUDE.md can answer.*

- **Any project / 2026-04-23 - A screen was built before its place in the state machine was defined.**
  *Rule: Every new screen must be placed on the screen flow map BEFORE any GameObject is created. Screens without defined entry/exit states get tossed in rework.*

- **Any project / 2026-04-23 - Testing required a physical phone for basic layout checks.**
  *Rule: Default to Unity Device Simulator for layout / touch / rotation tests. The phone is for final-pass testing only. If someone reaches for a phone to test a button position, the pipeline is broken.*

- **Any project / 2026-04-23 - Visual QA was done by eye and regressions slipped between sessions.**
  *Rule: Every screen gets a screenshot added to the visual regression set on creation. Automated diffing catches regressions the eye misses.*

---

## Promotion log

When a lesson has been observed 2+ times across different projects, it gets promoted into the main body of `SKILL.md` as an enforced rule. Log promotions here so we don't re-promote:

*(none yet)*

## 2026-04-25 - Unity-MCP absorption (v0.3.0, via Talent Scout v2)
- **Root cause of v1 miss**: Talent Scout v1 only grepped 9 cloned source repos. Unity-MCP wasn't in any of them. v2's 7-tier source registry (GitHub trending, MCP registries, per-domain queries, community signals) caught it on the first run.
- **Highest-leverage Unity-MCP capability**: `script-execute` (Roslyn) + `reflection-method-call`. Together they remove the save-reload-test cycle AND give visibility into compiled DLLs. This is the biggest workflow change.
- **Unique vs. early competitors**: Runtime (in-game) MCP. IvanMurzak/Unity-MCP enables AI-driven NPCs, dynamic content, and in-game debugging at runtime, not just Editor automation. (Note 2026-06: CoplayDev/unity-mcp is now the PRIMARY bridge for breadth; IvanMurzak is kept for the runtime layer + the Tier-0 autonomous verify loop.)
- **Anti-amnesia signal**: The phrase "ALWAYS load `unity-mcp-operator.md` FIRST" was added to the SKILL.md description because Claude historically forgets MCP tools exist mid-session and falls back to telling Shai to click manually.
- **Add-on packs to absorb later if Shai's projects need them**: AI Animation, AI ParticleSystem, AI ProBuilder.
- **Quarterly re-scan target**: MiAO-AI-Lab/MiAO-MCP-for-Unity (alternate Unity MCP) - compare and decide if dual-install is worth it.

## 2026-05-01 - M4 absorption: MetaGPT Engineer spec→code handoff (v0.4.0)
- Pattern: 8-step sequence; schema discipline (verbatim signatures); no scope creep; imports from Shared Knowledge
- Anti-patterns refused: improvements, helper additions, renames
- Source: github.com/FoundationAgents/MetaGPT
