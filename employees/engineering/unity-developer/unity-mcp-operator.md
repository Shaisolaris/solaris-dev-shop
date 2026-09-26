# Unity MCP Operator - IvanMurzak/Unity-MCP (canonical)

> **Absorbed v0.3.0 (2026-04-25)** from `IvanMurzak/Unity-MCP` - a powerful Unity MCP bridge (Apache-2.0, ~2.6-3k stars as of the 2026-05 audit, 100+ native tools, runtime + editor support, Roslyn-powered C# execution, full reflection access). **Status (2026-06-08+): SECONDARY/fallback. The PRIMARY bridge is now CoplayDev/unity-mcp - see `coplaydev-unity-mcp.md`.** IvanMurzak is retained because it owns the Tier-0 autonomous play/edit-mode verify loop, reflection-method-call on private/DLL methods, and 3-line `[McpPluginTool]` custom tools.

Load this file when the owner is doing **anything Unity-Editor-driven** - not just "MCP setup". The point of this skill is that Unity-MCP is now the default Unity automation surface for every Solaris session.

---

## Why this beat the previous "Unity MCP" knowledge

- v1 of this file referenced AnkleBreaker / Coplay / Glade as the recommended bridges. (Update 2026-06: CoplayDev/unity-mcp has since matured into the strongest bridge and is now PRIMARY - see `coplaydev-unity-mcp.md`. The points below remain the reason IvanMurzak is kept as the fallback.)
- IvanMurzak/Unity-MCP supports **both Editor and Runtime (in-game)** - meaning AI can debug compiled builds, drive NPC behavior at runtime, and self-correct by reading live game state. No other Unity MCP does this.
- Roslyn-powered `script-execute` lets the coding agent compile + run arbitrary C# inside the live Editor process - no save-reload-test cycle.
- Reflection-powered `reflection-method-find` + `reflection-method-call` make every method in every loaded assembly callable, including private methods inside compiled DLLs. This is a superpower for debugging closed-source packages.

---

## Install (canonical, 3 steps)

**Step 1 - install the Unity plugin** (CLI, no Editor needed):
```bash
npm install -g unity-mcp-cli
unity-mcp-cli install-plugin /absolute/path/to/UnityProject
unity-mcp-cli login /absolute/path/to/UnityProject
unity-mcp-cli open /absolute/path/to/UnityProject
unity-mcp-cli wait-for-ready /absolute/path/to/UnityProject
```

> Project path **must contain no spaces** (Unity-MCP requirement). Move project under `~/UnityProjects/` if it lives in `~/Documents/` or anywhere with spaces.

**Step 2 - install the AI-agent connector** (a coding agent is the recommended client):
```bash
agent mcp add ai-game-developer "/path/to/UnityProject/Library/mcp-server/osx-arm64/unity-mcp-server" --port=8080 --client-transport=stdio
```

Platform binary paths:
- macOS Apple-Silicon: `Library/mcp-server/osx-arm64/unity-mcp-server`
- macOS Apple-Intel: `Library/mcp-server/osx-x64/unity-mcp-server`
- Windows x64: `Library/mcp-server/win-x64/unity-mcp-server.exe`
- Linux x64: `Library/mcp-server/linux-x64/unity-mcp-server`

**Step 3 - auto-generate Skills** in Unity:
- `Window → AI Game Developer → Auto-generate Skills` (recommended)
- OR via CLI: `npx unity-mcp-cli setup-skills the coding agent-code /path/to/UnityProject`

This generates a coding agent skills tailored to the project's installed packages, Unity version, OS - so the AI agent knows what's actually available, not just generic Unity.

**Docker alternative** (for cloud / CI):
```bash
docker run -p 8080:8080 ivanmurzakdev/unity-mcp-server
# MCP client config: { "mcpServers": { "ai-game-developer": { "url": "http://localhost:8080" } } }
```

---

## The 100+ tools - full reference

### Project & Assets (20 tools)

| Tool | Purpose |
|------|---------|
| `assets-copy` | Copy asset at path → newPath |
| `assets-create-folder` | Create new folder under parent |
| `assets-delete` | Delete assets at paths |
| `assets-find` | Search asset DB with filter string |
| `assets-find-built-in` | Search Editor's built-in assets |
| `assets-get-data` | Get asset data - all serializable fields/properties |
| `assets-material-create` | Create new material with default params |
| `assets-modify` | Modify asset file in project |
| `assets-move` | Move assets (also rename) |
| `assets-prefab-close` | Close currently-open prefab |
| `assets-prefab-create` | Create prefab from a GameObject |
| `assets-prefab-instantiate` | Instantiate prefab in active scene |
| `assets-prefab-open` | Open prefab edit mode for a GameObject |
| `assets-prefab-save` | Save prefab in editing mode |
| `assets-refresh` | Refresh AssetDatabase |
| `assets-shader-list-all` | List all shaders in project + packages |
| `package-add` | Install UPM package from registry, Git URL, or local path |
| `package-list` | List installed UPM packages |
| `package-remove` | Uninstall package |
| `package-search` | Search registry + installed packages |

### Scene & Hierarchy (23 tools)

| Tool | Purpose |
|------|---------|
| `gameobject-component-add` | Add Component to GameObject |
| `gameobject-component-destroy` | Destroy one/many components |
| `gameobject-component-get` | Get detailed info about a Component |
| `gameobject-component-list-all` | List all classes extended from `UnityEngine.Component` |
| `gameobject-component-modify` | Modify Component on GameObject |
| `gameobject-create` | Create GameObject in opened Prefab or Scene |
| `gameobject-destroy` | Destroy GameObject + nested children recursively |
| `gameobject-duplicate` | Duplicate GameObjects |
| `gameobject-find` | Find specific GameObject |
| `gameobject-modify` | Modify GameObjects + attached component fields |
| `gameobject-set-parent` | Set parent for list of GameObjects |
| `object-get-data` | Get data of any Unity Object |
| `object-modify` | Modify any Unity Object |
| `scene-create` | Create new scene asset |
| `scene-get-data` | Get root GameObjects in scene |
| `scene-list-opened` | List currently opened scenes |
| `scene-open` | Open scene from project asset |
| `scene-save` | Save opened scene to asset |
| `scene-set-active` | Set scene as active |
| `scene-unload` | Unload scene |
| `screenshot-camera` | Capture screenshot from camera, returns image |
| `screenshot-game-view` | Capture screenshot from Game View |
| `screenshot-scene-view` | Capture screenshot from Scene View |

### Scripting & Editor (12 tools - the killer category)

| Tool | Purpose |
|------|---------|
| `console-get-logs` | Get Editor logs with filters |
| `editor-application-get-state` | Get Editor state (playmode, paused, compilation) |
| `editor-application-set-state` | Control Editor state (start/stop/pause playmode) |
| `editor-selection-get` | Get current Selection |
| `editor-selection-set` | Set current Selection |
| `reflection-method-call` | Call ANY C# method (even private) with params, get return value |
| `reflection-method-find` | Find method anywhere in codebase via Reflection (incl. private + DLLs) |
| `script-delete` | Delete script file(s) |
| `script-execute` | **Compile + execute C# code dynamically using Roslyn** - no Save-reload cycle |
| `script-read` | Read script file content |
| `script-update-or-create` | Update or create script file with C# code |
| `tests-run` | Execute Unity tests (EditMode/PlayMode) with filtering + detailed results |

### Optional add-on tool packs

| Extension | When to install |
|-----------|----------------|
| [AI Animation](https://github.com/IvanMurzak/Unity-AI-Animation/) | Animator graph automation (any project with rigged characters) |
| [AI ParticleSystem](https://github.com/IvanMurzak/Unity-AI-ParticleSystem/) | Particle FX automation (VFX-heavy projects) |
| [AI ProBuilder](https://github.com/IvanMurzak/Unity-AI-ProBuilder/) | Procedural geometry (level building, prototyping) |

---

## Decision rules - when to reach for which tool

### Setup / scene work
- Building a new screen → `gameobject-create` + `gameobject-component-add` + `assets-prefab-create` + `assets-prefab-save`
- Re-parenting hierarchy → `gameobject-set-parent` (batch - pass array of children)
- Reading the current scene state → `scene-get-data` first, then `gameobject-find` for specific objects
- Adding a UI panel → `gameobject-create` (under Canvas) + `gameobject-component-add` (RectTransform, Image) + `gameobject-component-modify` (anchors, sizing)

### Scripting / debugging
- Want to TEST something quickly without a full save-reload? → `script-execute` (Roslyn). Examples: "execute `GameObject.FindObjectOfType<PlayerController>().speed = 10`" → instant.
- Need to call a method whose source you don't have? → `reflection-method-find` then `reflection-method-call`. Works on compiled DLLs.
- Editor froze / something looks wrong? → `console-get-logs` first, ALWAYS, before guessing.
- Need to verify a fix worked? → `tests-run` with the relevant filter.

### Visual / verification
- Verifying a UI screen looks right → `screenshot-game-view` (no need to reach for the user's phone)
- Verifying scene composition → `screenshot-scene-view`
- Verifying camera framing → `screenshot-camera` with the relevant camera GameObject

### Builds / packages
- Adding a missing package → `package-search` then `package-add` (NEVER manually edit `manifest.json` first - let the tool do it)
- Removing dead deps → `package-list` then `package-remove`
- Importing an asset → `assets-refresh` after dropping into the project folder

---

## Custom tools - extend in 3 lines of C#

When the project needs a tool that doesn't exist, write one. Single C# attribute = new MCP tool.

```csharp
[McpPluginToolType]
public class Tool_GameMechanic
{
    [McpPluginTool("spawn-enemy-wave", Title = "Spawn an enemy wave")]
    [Description("Spawns N enemies of given type at the spawn points. Used by AI to test difficulty curves.")]
    public string SpawnWave(
        [Description("Number of enemies to spawn")] int count,
        [Description("Enemy prefab name")] string enemyType
    )
    {
        return MainThread.Instance.Run(() => {
            for (int i = 0; i < count; i++) GameManager.Spawn(enemyType);
            return $"[Success] Spawned {count} {enemyType}";
        });
    }
}
```

Use `MainThread.Instance.Run(...)` for anything touching Unity API. Skip it for pure background work.

### MCP Prompts - inject project conventions

```csharp
[McpPluginPromptType]
public static class Prompt_ProjectConventions
{
    [McpPluginPrompt(Name = "naming-conventions", Role = Role.Assistant)]
    [Description("Project's naming conventions for C# code.")]
    public string NamingConventions() =>
        "PascalCase for public methods. _camelCase for private fields. " +
        "All MonoBehaviours live in /Scripts/Behaviours/. Manager singletons in /Scripts/Managers/.";
}
```

This is the cure for "the coding agent forgets the project's coding standards every session" - bake it into a Prompt the MCP delivers automatically.

---

## Runtime (in-game) usage - the unique capability

Unity-MCP works **inside the compiled game**, not just the Editor. This is the differentiator.

```csharp
var mcpPlugin = UnityMcpPluginRuntime.Initialize(builder => {
    builder.WithConfig(c => { c.Host = "http://localhost:8080"; c.Token = "your-token"; });
    builder.WithToolsFromAssembly(Assembly.GetExecutingAssembly());
}).Build();

await mcpPlugin.Connect();
// LLM can now drive the game live - for NPC behavior, dynamic content, debugging
```

Use cases:
- Chess-bot AI that asks an LLM for the next move (sample in upstream README)
- NPCs whose dialog is generated live from game-state context
- In-game "ask the AI to fix this bug" debug consoles
- QA harness that lets the LLM play the game and report what's broken

---

## Configuration variables (server side)

| Env var | Default | Purpose |
|---------|---------|---------|
| `MCP_PLUGIN_PORT` / `--port` | 8080 | Client ↔ Server ↔ Plugin port |
| `MCP_PLUGIN_CLIENT_TIMEOUT` / `--plugin-timeout` | 10000ms | Plugin → Server timeout |
| `MCP_PLUGIN_CLIENT_TRANSPORT` / `--client-transport` | streamableHttp | `stdio` for local; `streamableHttp` for cloud/Docker |

Plugin-side overrides:
| Env var | Purpose |
|---------|---------|
| `UNITY_MCP_HOST` | Override server URL |
| `UNITY_MCP_KEEP_CONNECTED` | Force connection on/off |
| `UNITY_MCP_AUTH_OPTION` | `none` / `required` |
| `UNITY_MCP_TOKEN` | Auth token |
| `UNITY_MCP_TOOLS` | Comma-sep tool IDs to enable (whitelist mode) - runtime only, never persisted |

CI batch-mode example:
```bash
Unity.exe -batchmode -nographics \
  -UNITY_MCP_HOST=http://localhost:8080 \
  -UNITY_MCP_KEEP_CONNECTED=true \
  -UNITY_MCP_AUTH_OPTION=required \
  -UNITY_MCP_TOKEN=ci-token
```

---

## When NOT to use Unity-MCP

- **Substantial C# logic.** Use the IDE (Cursor / Rider / VS Code) for writing real systems. The MCP shines at *driving* the Editor + *running* code, not at typing 500 lines of C#.
- **Game design decisions.** Run the Design Review Protocol from `game-design-mentor.md` first. The MCP is a faster hand, not a smarter brain.
- **First-run on an unfamiliar project.** Read `AGENTS.md` + `learnings.md` + run the Absorption Protocol from the parent SKILL.md before driving the Editor.

---

## Source provenance

- Repo: https://github.com/IvanMurzak/Unity-MCP
- Package: `com.ivanmurzak.unity.mcp` (OpenUPM)
- Docker: `ivanmurzakdev/unity-mcp-server`
- License: Apache 2.0
- Caught by: the skill scanner v2 (after v1 missed it for ~6 weeks; see the absorption note in `learnings.md` dated 2026-04-25)

> PRIMARY Unity MCP is now CoplayDev/unity-mcp - see coplaydev-unity-mcp.md. IvanMurzak content below is the secondary/alternative bridge.
