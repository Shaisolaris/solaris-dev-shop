# KiCad MCP - PCB note (when a part needs a board)

Source: lamaalrajih/kicad-mcp (verified live 2026-06-13: MIT, 468★, last push 2025-10-17). CONNECT - the host runs the KiCad MCP server. Secondary capability; FreeCAD is this employee's spine.

## When to invoke
Only when the design includes electronics - a circuit board, schematic, or PCB layout. For pure mechanical parts, stay in FreeCAD. Typical flow: KiCad designs/inspects the board; FreeCAD models the enclosure/mount around the board's outline.

## Host setup (what the host does)
- Prereqs: macOS/Windows/Linux, Python 3.10+, **KiCad 9.0+**, `uv` 0.8+.
- `git clone https://github.com/lamaalrajih/kicad-mcp && cd kicad-mcp && make install` (uv creates `.venv`).
- `cp .env.example .env`, set `KICAD_SEARCH_PATHS=~/pcb,~/Projects/KiCad` (comma-separated project dirs).
- Run: `python main.py`. Register with the client:
```json
{ "mcpServers": { "kicad": {
  "command": "/abs/path/kicad-mcp/.venv/bin/python",
  "args": ["/abs/path/kicad-mcp/main.py"] } } }
```
- Restart the MCP client to load it.

## MCP model (Resources vs Tools vs Prompts)
- **Resources** - read-only data (like GET): e.g. `kicad://projects` lists all KiCad projects. Use to inspect state.
- **Tools** - actions with side effects (like POST): e.g. `open_project()` launches KiCad on a project. Invoked by the LLM with user approval.
- **Prompts** - reusable templates for common interactions.

## How the employee uses it
- Discover projects via the projects resource; open/inspect a project via tools; drive PCB tasks in natural language.
- Keep mechanical (FreeCAD) and electrical (KiCad) as SEPARATE artifacts that reference each other by the board outline + connector positions. Export the board outline to STEP so the FreeCAD enclosure stays dimensionally honest.

## Notes / honesty
- Requires KiCad 9.0+ installed on the host - older KiCad won't work.
- A higher-star alternative exists (mixelpixx/KiCAD-MCP-Server, 1,250★) - noted for Scout if PCB work becomes a real, recurring need; lamaalrajih is the cleaner MIT base for now.
- Firmware on the board is NOT this employee - that's engineering (iot/full-stack). KiCad here is the board design only.
