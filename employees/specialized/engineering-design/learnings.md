# Engineering Design (CAD) - Learnings

Dated observations. A pattern seen 2-3 times graduates into rules.md.

## Design conventions log (update per job)
| Part | Method (print/CNC/mold) | Material | Key parameters | Tolerance designed-for | Export format |
|---|---|---|---|---|---|
| _(none yet)_ | | | | | |

## Lessons
### 2026-06-13 - employee created
- **Built v1.0.0** on branch build/utility. CONNECT: FreeCAD MCP (parametric CAD spine) + KiCad MCP (PCB, secondary). Nothing live until the host starts FreeCAD's RPC server.
- *Rules already promoted:* parametric-or-it's-not-CAD; design for the manufacturing method; tolerances explicit; export to the downstream contract; FEM is a sanity check; precision here / art in Blender. (See rules.md.)
- **Open:** host has not connected FreeCAD or KiCad. First real use starts with the connect steps in references.

### 2026-06-13 (depth)
- **freecad-mcp stars corrected** ~1,113 (inflated) -> ~642 verified.
- **KiCad re-tiered**: lamaalrajih (~468) light / mixelpixx (~1,157, 122 tools) deep-PCB - promoted from Scout-note.
- **Code-CAD lane added**: build123d / CadQuery (Apache-2.0) for script-driven parametric parts.

## Tags
[#parametric] [#printability] [#tolerances] [#export] [#fem] [#freecad] [#kicad] [#blender-boundary]
