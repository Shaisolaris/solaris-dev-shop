# CoplayDev/unity-mcp - PRIMARY Unity MCP bridge (absorbed 2026-06-08)

Source: https://github.com/CoplayDev/unity-mcp · MIT · v9.7.1 (2026-05-24) · 10.4k stars · maintained by Aura/Coplay.
Status: this is now the PRIMARY Unity MCP for this employee. IvanMurzak/Unity-MCP (prior absorption, ~2.6k stars) is kept as a secondary/alternative reference; CoplayDev has overtaken it in stars, release cadence (61 releases), and feature surface.

## What it is
Bridges AI assistants (Claude, Codex, VS Code, local LLMs) with the Unity Editor via MCP. Tools to manage assets, control scenes, edit scripts, run tests, and automate Editor workflows.

## Install (UPM)
Unity → Window → Package Manager → + → Add package from git URL:
`https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#main`  (beta channel: `#beta`)
Then: Window → MCP for Unity → "Configure All Detected Clients". Docs: https://coplaydev.github.io/unity-mcp/

## Capabilities net-new over IvanMurzak (the reason to absorb)
- **Tool groups** - vfx / animation / ui / testing / etc., so the LLM gets a scoped, relevant toolset per task instead of one flat list.
- **Roslyn script validation** - compile-checks generated C# before applying it (distinct from IvanMurzak's Roslyn execute).
- **Multi-instance routing** - drive multiple Unity Editor instances at once.
- **Remote-hosted server with auth** - run the MCP server remotely behind authentication, not just local.
- **Built-in test runner** over MCP.
- Active maintenance (v9.x, weekly-ish releases) and a large contributor base.

## When to use which
- Default to CoplayDev for new game work (Solaris Studio titles).
- Fall back to IvanMurzak only if a specific tool/behavior is needed that CoplayDev lacks.
