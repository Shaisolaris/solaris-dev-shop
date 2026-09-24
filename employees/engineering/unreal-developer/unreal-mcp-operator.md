# Unreal MCP Operator - ChiR24/Unreal_mcp (canonical)

> **BASE absorption v0.1.0 (2026-06-13)** from `ChiR24/Unreal_mcp` - MIT, the only well-licensed, actively-maintained, native-C++ Unreal Engine MCP bridge in the ecosystem. **Load this file FIRST when ANY Unreal-Editor-driven work begins.** It is the equivalent of unity-developer's `unity-mcp-operator.md`: the canonical reference for the engine-control surface. Claude forgets these tools exist if it doesn't load them at the start of every Unreal session - and falls back to telling Shai to click in the editor, which is exactly what this employee exists to prevent.

Supports **Unreal Engine 5.0-5.8** (5.8 preview validated upstream). Operations route through the **MCP Automation Bridge** C++ plugin running inside the editor. As of v0.5.30 there are TWO transports: a **Native MCP HTTP/SSE server built into the plugin** (recommended - no Node, no bridge; connect the client directly to http://localhost:3000/mcp) OR the classic **TypeScript stdio bridge** (Node 18+). Re-verified against ChiR24/Unreal_mcp on 2026-06-13: 681 stars, MIT, v0.5.30 (Jun 5 2026).

---

## Why this is the base (license + architecture)

- **MIT licensed, fresh, native C++.** The two highest-star UE MCPs (flopperam/unreal-engine-mcp 1,021★, chongdashu/unreal-mcp 1,979★) have **NO LICENSE** - we may reference their tool breadth as concepts but must **never lift code or text**. ChiR24 is the legally clean base. GenOrca/unreal-mcp (Apache-2.0, 108 stars, 84 Python-API tools, v1.4.0 May 2026) is a secondary alternate to compare quarterly.
- **Native C++ Automation Bridge.** Every operation is dispatched through the bridge plugin, not a brittle Python remote-exec shim. Dynamic type discovery introspects lights, debug shapes, and sequencer tracks at runtime.
- **Graceful degradation + on-demand connection.** The server starts even without a live Unreal connection and retries the automation handshake with exponential backoff - so the AI client doesn't crash when the editor isn't up yet.
- **Command safety baked in.** Dangerous console commands are blocked by pattern validation; the automation bridge binds to loopback (127.0.0.1) only by default. Per-IP rate limiting (60 req/min) on the Prometheus metrics endpoint.

---

## Install (canonical, 4 steps)

**Step 1 - install the MCP server.**
```bash
# Option A: NPX (recommended)
npx unreal-engine-mcp-server

# Option B: clone & build
git clone https://github.com/ChiR24/Unreal_mcp.git
cd Unreal_mcp && npm install && npm run build && node dist/cli.js
```

**Step 2 - install the Unreal plugin** (`McpAutomationBridge`, shipped in the repo at `Unreal_mcp/plugins/McpAutomationBridge`):
- **Method 1 (copy):** copy `Unreal_mcp/plugins/McpAutomationBridge/` → `YourUnrealProject/Plugins/McpAutomationBridge/`, then regenerate project files.
- **Method 2 (editor):** Edit → Plugins → Add → browse to `Unreal_mcp/plugins/` → select `McpAutomationBridge`.

> ⚠️ **First-open gotcha (carried verbatim from upstream):** when opening the `.uproject` for the first time UE prompts to rebuild missing modules - click **Yes**. After the rebuild you may still see "Plugin 'McpAutomationBridge' failed to load because module could not be loaded." This is expected: UE rebuilds successfully but doesn't reload the plugin in the same session. **Close and reopen the project** and it loads correctly. (Or build via Visual Studio first to avoid it.) Tell Shai this before he panics.

**Step 3 - enable required + optional plugins** (Edit → Plugins, then restart):
- **Required:** MCP Automation Bridge · Editor Scripting Utilities (asset/actor subsystems) · Niagara (VFX).
- **Auto-enabled on demand** by the bridge: Level Sequence Editor (`manage_sequence`), Control Rig (`animation_physics`), GeometryScripting (`manage_geometry`), Behavior Tree Editor (`manage_behavior_tree`), Environment Query Editor (AI/EQS), Gameplay Abilities (`manage_gas`), MetaSound (`manage_audio`), StateTree + Smart Objects (`manage_ai`), Enhanced Input (`manage_input`), Chaos Cloth, Interchange, Procedural Mesh, OnlineSubsystem(+Utils) for sessions/networking.

**Step 4 - configure the MCP client** (host-side; Claude Code / Claude Desktop / Cursor):
```json
{
  "mcpServers": {
    "unreal-engine": {
      "command": "npx",
      "args": ["unreal-engine-mcp-server"],
      "env": {
        "UE_PROJECT_PATH": "C:/Path/To/YourProject",
        "MCP_AUTOMATION_PORT": "8091"
      }
    }
  }
}
```
(For clone/build, use `"command": "node", "args": ["path/to/Unreal_mcp/dist/cli.js"]`.)

**Docker alternative (CI/cloud):** `docker build -t unreal-mcp . && docker run -it --rm -e UE_PROJECT_PATH=/project unreal-mcp`.

### Key environment variables
| Var | Default | Purpose |
| --- | --- | --- |
| `UE_PROJECT_PATH` | (required) | Absolute path to the `.uproject` directory |
| `MCP_AUTOMATION_HOST` | `127.0.0.1` | Bridge bind host |
| `MCP_AUTOMATION_PORT` | `8091` | Bridge port (must match plugin) |
| `MCP_AUTOMATION_ALLOW_NON_LOOPBACK` | `false` | **Security gate** - only `true` to expose on LAN |
| `LOG_LEVEL` | `info` | `debug`/`info`/`warn`/`error` |
| `MCP_AUTOMATION_REQUEST_TIMEOUT_MS` | `120000` | Long ops (build/package) need this headroom |
| `ASSET_LIST_TTL_MS` | `10000` | Asset list cache TTL |
| `GRAPHQL_ENABLED` | `false` | Optional GraphQL query endpoint (port `GRAPHQL_PORT=4000`) |

> **LAN access is opt-in and risky.** To drive UE from another machine, set `MCP_AUTOMATION_ALLOW_NON_LOOPBACK=true` + `MCP_AUTOMATION_HOST=0.0.0.0` on the server AND enable "Allow Non Loopback" + listen host `0.0.0.0` under Project Settings → Plugins → MCP Automation Bridge → Security. Only on trusted networks behind a firewall.

---

## The tool surface - full reference (re-verified 2026-06-13, v0.5.30)

ChiR24/Unreal_mcp exposes **23 broad MCP tools** in all-tools mode using **action-based dispatch** (one tool fans out to many actions via an `action` parameter; related actions now live on their parent tool so clients load less context). Earlier snapshots counted ~36 narrower tools; upstream consolidated them. Core tools load by default and more can be enabled at runtime via `manage_tools`. Always check this list before writing a custom tool - most things already exist.

### Core (8)
| Tool | Purpose |
| --- | --- |
| `manage_asset` | Assets, Materials, Render Targets, Behavior Trees (browse/import/duplicate/rename/delete/create) |
| `manage_blueprint` | Blueprints, SCS components, graph editing, node manipulation, AND UMG widgets/layout/bindings/animations (UMG was folded in here) |
| `control_actor` | Spawn, delete, transform, physics, tags |
| `control_editor` | PIE sessions, camera, viewport, screenshots |
| `manage_level` | Load/save levels, streaming, lighting |
| `system_control` | UBT, tests, logs, project settings, CVars, AND `execute_python` (the Python escape hatch lives here) |
| `inspect` | Object introspection (read any UObject's properties) |
| `manage_tools` | Dynamic tool management (enable/disable tools at runtime - core tools load by default) |

### World building (4)
| Tool | Purpose |
| --- | --- |
| `build_environment` | Landscapes, foliage, procedural terrain, lighting, spline roads/rivers/fences |
| `manage_level_structure` | Levels, sublevels, World Partition, streaming, data layers, HLOD, volumes |
| `manage_geometry` | Procedural mesh creation + editing (Geometry Script) |
| `manage_pcg` | PCG graph assets, subgraphs, sampler/filter/spawner nodes, pin connections, execution, partition grid (NEW since absorption) |

### Gameplay systems (8)
| Tool | Purpose |
| --- | --- |
| `animation_physics` | Animation BPs, skeletons, sockets, physics assets, cloth, vehicles, ragdolls, Control Rig, IK |
| `manage_effect` | Niagara, particles, debug shapes, GPU simulations |
| `manage_gas` | Gameplay Ability System: abilities, effects, attributes (see `unreal-gameplay-patterns.md` for the METHODOLOGY) |
| `manage_character` | Character creation, movement, advanced locomotion |
| `manage_combat` | Weapons, projectiles, damage, melee combat |
| `manage_ai` | AI controllers, Behavior Trees, EQS, perception, State Trees, Smart Objects, NavMesh/pathfinding |
| `manage_inventory` | Items, equipment, loot tables, crafting |
| `manage_interaction` | Interactables, destructibles, triggers |

### Utility (3)
| Tool | Purpose |
| --- | --- |
| `manage_audio` | Audio assets, components, sound cues, MetaSounds, attenuation |
| `manage_sequence` | Sequencer, cinematics, bindings, tracks, playback, keyframes |
| `manage_networking` | Replication, RPCs, network prediction, sessions, split-screen, LAN/voice, game framework, input mappings (sessions + game-framework + input were consolidated in here) |

> **Migration note (old tool names -> where they live now).** Earlier versions of this file listed ~36 narrower tools. Upstream consolidated. If a habit reaches for one of these, here is the new home: build/cook/package was `manage_pipeline` -> now `system_control` (UBT) + the build actions; UMG was `manage_widget_authoring` -> now `manage_blueprint`; `manage_lighting`/`manage_volumes`/`manage_navigation` -> folded into `manage_level_structure` + `build_environment` + `manage_ai`; `manage_splines` -> `build_environment`; `manage_skeleton`/`manage_texture` -> `animation_physics`/`manage_asset`; `manage_material_authoring` -> `manage_asset` (materials) / `manage_blueprint`; `manage_performance` -> profiling via `system_control` CVars + `manage_networking`-adjacent stats (see `unreal-gameplay-patterns.md` Part 2); `manage_behavior_tree` -> `manage_ai`; `manage_game_framework`/`manage_sessions`/`manage_input` -> `manage_networking`. When in doubt, `manage_tools` lists what is actually enabled at runtime.

**Supported asset types:** Blueprints, Materials, Textures, Static Meshes, Skeletal Meshes, Levels, Sounds, Particles, Niagara Systems, Behavior Trees.

---

## How to operate (the Unity-parity rules, translated to UE)

- **PIE is your play-test loop.** Use `control_editor` to start/stop Play-In-Editor and take screenshots - never ask Shai to press Play and describe what he sees.
- **Verify visually with screenshots.** `control_editor` captures viewport/camera screenshots. Take them yourself after any scene change.
- **Read logs before guessing.** `system_control` → logs first, then form a hypothesis. Same discipline as `console-get-logs` in Unity.
- **`inspect` is your reflection.** Where Unity has `reflection-method-find/call`, UE here has `inspect` for UObject introspection + the Python escape hatch (see the GenAI/asset-gen file) for arbitrary editor scripting. Never say "I can't see inside that asset" - inspect it.
- **Blueprint node-wiring is the weak spot.** Upstream flags node connect/getter-setter bugs (see learnings + GenAI file's known-issues). For complex graphs, prefer C++ where practical and verify the compiled Blueprint, don't assume the wiring took.
- **Build/package via `system_control` (UBT build actions).** (The old `manage_pipeline` tool was consolidated into `system_control`.) Long-running, so make sure `MCP_AUTOMATION_REQUEST_TIMEOUT_MS` is raised before kicking off a cook/package. Methodology: see `unreal-gameplay-patterns.md` Part 4.
- **Respect the safety rails.** Don't try to disable dangerous-command blocking or flip `ALLOW_NON_LOOPBACK` without an explicit reason from Shai.

## Optional GraphQL surface
For complex multi-entity queries, enable the GraphQL endpoint (`GRAPHQL_ENABLED=true`, port 4000). Use it for read-heavy introspection across many actors/assets in one query instead of chaining many `inspect` calls.

## Re-check schedule
- Quarterly: re-fetch ChiR24/Unreal_mcp README + `docs/default` for new action tools, new UE version support, GraphQL schema changes.
- Watch: Epic's official Unreal MCP for UE 5.8+ (announced) - when it ships it likely supersedes third-party bridges; re-evaluate base.
