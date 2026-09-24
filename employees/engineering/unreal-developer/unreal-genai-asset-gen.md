# Unreal In-Engine GenAI + Asset Generation - UnrealGenAISupport + shared asset layer

> **Absorbed v0.1.0 (2026-06-13)** from `prajwalshettydev/UnrealGenAISupport` (MIT). This is the "create the assets" + "LLM inside the engine" layer that complements the engine-control bridge (`unreal-mcp-operator.md`). Load it whenever a task needs generated content (3D models, textures, audio/voice) OR LLM behavior running inside the game (dynamic NPCs, runtime decision-making).

The pattern that unlocks "command → playable" in games is **three layers, not one**: engine-control (the bridge) + asset-generation (this file) + design/orchestration (game-designer + OpenGame methodology). Unreal, Unity, and game-designer all draw on the **same shared asset layer** described at the bottom.

---

## What UnrealGenAISupport gives you

A UE5.4–5.7+ C++ plugin that removes the "LLM/GenAI integration layer" so you focus on game logic. Two surfaces:

### 1. LLM APIs (C++ AND Blueprint, edit-time AND packaged runtime)
- **OpenAI** - chat (`gpt-4.1`, `gpt-4.1-mini/nano`, `o4-mini`, `o3`, `o3-pro`, `o3-mini`) + **Structured Outputs** (pass a JSON schema inline or from a file, get schema-conformant JSON back).
- **Anthropic Claude** - chat (`claude-4-latest`, `claude-3-7-sonnet`, `claude-3-5-sonnet`, `claude-3-5-haiku`).
- **XAI Grok** - chat (`grok-3-latest`, `grok-3-mini-beta`).
- **DeepSeek** - chat (`deepseek-chat` V3.1) + reasoning (`deepseek-reasoner`). Note: system message is mandatory for the reasoner; never feed `reasoning_content` back in (400 error); raise UE HTTP timeouts in `DefaultEngine.ini` (`HttpConnectionTimeout=180`, `HttpReceiveTimeout=180`) because R1 calls exceed the 30s default.
- All calls are async with a completion delegate. Example (Anthropic):
```cpp
FGenClaudeChatSettings ChatSettings;
ChatSettings.Model = EClaudeModels::Claude_3_7_Sonnet;
ChatSettings.MaxTokens = 4096;
ChatSettings.Messages.Add(FGenChatMessage{TEXT("system"), TEXT("You are a helpful assistant.")});
ChatSettings.Messages.Add(FGenChatMessage{TEXT("user"), TEXT("Describe a forest level.")});
UGenClaudeChat::SendChatRequest(ChatSettings, FOnClaudeChatCompletionResponse::CreateLambda(
    [this](const FString& Response, const FString& Error, bool bSuccess){ /* use Response */ }));
```
- **Use case (runtime):** "Become Human"-style NPCs as agentic LLM instances inside a shipped build - the engine-parity of Unity-MCP's in-game runtime layer.

### 2. MCP handshake (edit-time editor control via Claude Desktop / Claude Code / Cursor)
A **FastMCP**-based Python MCP server (`Content/Python/mcp_server.py`) that lets an AI client drive the editor: spawn objects + transform/scale/rotate, change materials/color, generate blueprints (+ functions/variables/components), **run Python scripts**, **run console commands**, create/edit project files. This overlaps the ChiR24 bridge - **prefer ChiR24 for structured engine control; use UnrealGenAISupport's MCP mainly for its Python-script-execute escape hatch and its asset-gen tools.**

> ⚠️ **Upstream honesty (carried, do not hide from Shai):** UnrealGenAISupport's MCP is **"not actively developed"** per its maintainer, and Epic is building an official UE 5.8+ MCP. Known MCP issues: nodes fail to connect properly; no undo/redo over MCP; no streaming for DeepSeek reasoning; create-material tool can't do complex materials; some valid LLM-generated Python fails; Blueprint compile errors aren't surfaced cleanly; getter/setter node spawning is flaky; editor windows don't always dock/focus right. Treat MCP-driven Blueprint graph work as best-effort + verify.

---

## Prompt-to-3D and TTS (the asset-gen providers)

UnrealGenAISupport wires generative-asset providers so you can go **text/image → 3D model → into the level**, and **text → voice/SFX**, without leaving the engine. Providers (the free repo exposes the wiring; full coverage is in the paid Fab "GenAI Model Generator" plugin - **CONNECT, commercial APIs, not absorbed**):

| Modality | Providers | Notes |
| --- | --- | --- |
| **Text/Image → 3D** | Meshy, Tripo, Hunyuan3D (Tencent), TripoSR (fast <1s image→3D), Trellis 2 (Microsoft), Rodin (Hyper3D) | PBR textures, retexture, **auto-rigging** (Meshy/Rodin). Import the result as a Static/Skeletal Mesh, then place via `control_actor`. |
| **TTS / audio** | ElevenLabs (`eleven_v3`, sound effects), Inworld | Game voices, narration, SFX. |
| **2D / textures** | Gemini PBR texture gen (free); commercial Scenario.com (sprites), Layer.ai (textures) | CONNECT-only for commercial. |

**MCP status (free repo):** prompt-to-3D fetch+spawn is marked in-progress upstream - for reliable 3D gen today, drive the providers' own MCPs/APIs (below) and import the mesh, rather than relying on the in-editor prompt-to-3D path.

---

## The SHARED ASSET LAYER (common to unreal-developer, unity-developer, game-designer)

These are **CONNECT** items - the host wires the MCP/API once; all three game employees use the same backbone. Do NOT re-absorb per-employee.

- **ahujasid/blender-mcp** (~22k★, MIT) - **the in-house 3D core / hub.** Full Blender control: modeling, scene assembly, rendering, and a hub other gen tools plug into. Generate/clean/retopo/UV a mesh in Blender, export FBX/glTF, import into UE (Interchange) or Unity. This is where ownership of the 3D pipeline lives.
- **elevenlabs/elevenlabs-mcp** (MIT, free tier; commercial API behind) - SFX + music + voice for both engines.
- **VAST-AI-Research/tripo-mcp** (MIT, official) + **meshy-dev/meshy-mcp-server** (MIT, official) - text/image → 3D with PBR; pipe into Blender or import directly.
- **Commercial 3D/2D/audio gen (CONNECT, never absorb):** Meshy, Tripo, Rodin (3D + auto-rig), Scenario.com (style-trained 2D sprites + PBR), Layer.ai (textures), Suno/Udio (music).
- **Known OSS gaps (commercial-only as of 2026-06):** OSS rigging/animation gen, OSS 2D sprite gen, OSS music MCP. Flag to Shai when a task needs these; don't pretend an OSS option exists.

**Flow:** design intent (game-designer) → generate raw asset (Tripo/Meshy/blender-mcp/ElevenLabs) → refine in Blender (blender-mcp) → import + place + wire in-engine (ChiR24 bridge for UE / CoplayDev for Unity) → PIE/play-mode verify → iterate.

---

## API keys + security
- Editor env vars: `PS_OPENAIAPIKEY`, `PS_ANTHROPICAPIKEY`, `PS_DEEPSEEKAPIKEY`, `PS_GOOGLEAPIKEY`, `PS_METAAPIKEY` etc. (set via `setx` on Windows or `~/.zshrc` export on macOS/Linux; restart editor AND the connected IDE after).
- **Never ship API keys in packaged builds.** For test builds, set the key at runtime via `GenSecureKey::SetGenAIApiKeyRuntime` (C++ or Blueprint). For production, route LLM calls through your own backend - never expose keys client-side.
- **MCP grants the AI client direct control of the project.** Back up + use version control before enabling MCP; use only in a controlled environment.

## Install (host-side, summary)
1. Add as a git submodule: `git submodule add https://github.com/prajwalshettydev/UnrealGenAISupport Plugins/GenerativeAISupport`, regenerate project files, enable in Edit → Plugins, and for C++ projects add `GenerativeAISupport` to `PrivateDependencyModuleNames` in `Build.cs`.
2. For MCP: enable UE's Python Editor Script Plugin, `pip install fastmcp`, and add the `unreal-handshake` server (command `python <project>/Plugins/GenerativeAISupport/Content/Python/mcp_server.py`, env `UNREAL_HOST=localhost`, `UNREAL_PORT=9877`) to your MCP client config. Optionally enable AutoStart in the plugin settings.
