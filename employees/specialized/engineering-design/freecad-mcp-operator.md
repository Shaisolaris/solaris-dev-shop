# FreeCAD MCP Operator

Source: neka-nat/freecad-mcp (verified live 2026-06-13: MIT, 1,113★, last push 2026-06-11). CONNECT - the host runs FreeCAD with the MCP addon; this file is how the employee drives it.

## What it is
A FreeCAD addon + MCP server that lets Claude control FreeCAD: create/edit objects, run arbitrary FreeCAD Python, pull standard parts from the FreeCAD parts library, screenshot the view, and run a CalculiX FEM analysis. It turns FreeCAD into a parametric-CAD execution backend.

## Host install (what the host does)
1. Clone the repo and copy the addon into FreeCAD's Mod directory:
   - macOS (FreeCAD 1.1): `~/Library/Application Support/FreeCAD/v1-1/Mod/`
   - Linux (Ubuntu): `~/.FreeCAD/Mod/` (or `~/snap/freecad/common/Mod/`)
   - Windows: `%APPDATA%\FreeCAD\Mod\`
   Copy `addon/FreeCADMCP` into that Mod directory, then **restart FreeCAD**.
2. In FreeCAD: switch to the **MCP Addon** workbench, then **Start RPC Server** from the FreeCAD MCP toolbar.
   - Optional: check **Auto-Start Server** so it starts on every launch (saved to freecad_mcp_settings.json).
3. Register the MCP server with the client (uvx - no separate install needed):
```json
{ "mcpServers": { "freecad": { "command": "uvx", "args": ["freecad-mcp"] } } }
```
   - Token-saver: add `"--only-text-feedback"` to skip screenshots.
   - Dev mode: `"command": "uv", "args": ["--directory", "/path/to/freecad-mcp/", "run", "freecad-mcp"]`.
4. **Remote FreeCAD** (server on another machine): in the toolbar enable **Remote Connections** (binds 0.0.0.0), set **Allowed IPs** (CIDR ok, 127.0.0.1 always allowed), restart the RPC server; then point the MCP server with `"--host", "192.168.x.x"`.

## Tools (the employee's vocabulary)
- `create_document` - new FreeCAD document.
- `create_object` / `edit_object` / `delete_object` - object lifecycle.
- `execute_code` - **run arbitrary FreeCAD Python** in the running instance. The power tool: use for any real parametric build (sketches, constraints, features, spreadsheets). Read back after.
- `insert_part_from_library` + `get_parts_list` - pull standard parts from the FreeCAD-library (don't re-model hardware).
- `get_view` - screenshot of the active view (visual verify).
- `get_objects` / `get_object` - inspect document objects + their parameters (verify dimensions).
- `run_fem_analysis` - run the CalculiX solver on an existing `Fem::FemAnalysis`; returns max von Mises stress, max displacement, node count, working dir. Auto-creates a SolverCcxTools if the analysis has none. (See the repo's examples/cantilever_fem.py for an end-to-end example.)

## How the employee uses it
- Build parametric: `create_document` -> `execute_code` to author the constrained sketch + features + named parameters -> `get_object` to confirm dims -> `get_view` to eyeball -> export.
- Standard hardware: `get_parts_list` -> `insert_part_from_library`.
- Load check: set up a Fem::FemAnalysis, then `run_fem_analysis` -> report stress/displacement as a SANITY CHECK only.
- Export (via execute_code calling FreeCAD's exporters): STEP for CAD/CNC, STL/3MF for print, FCStd to keep the tree.

## Limits / honesty
- `execute_code` runs real Python in FreeCAD - verify the result by read-back, don't assume success.
- FEM is a sanity check, not a certified analysis.
- No server started -> no model. Hand the host the start steps; never claim a model exists.
