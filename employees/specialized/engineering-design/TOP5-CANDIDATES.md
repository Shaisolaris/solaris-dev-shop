# Engineering Design (CAD) - TOP 5 verified 2026 candidates

Domain: CAD / FreeCAD / KiCad. Verified 2026-06-13.

| # | Source | Stars | License | Last update | Maintainer | What it adds | Gate-0 | Tag |
|---|--------|-------|---------|-------------|------------|--------------|--------|-----|
| 1 | https://github.com/mixelpixx/KiCAD-MCP-Server | ~1,157 | MIT (permissive) | 2026-06 | mixelpixx | 122 tools (board/component/export/DRC/schematic/library/routing/AUTOROUTE) + JLCPCB + Freerouting. Far deeper than the current lamaalrajih primary (~468, basic). Promote from Scout-note to deep-PCB primary. | grep: noted only in "available_sources_for_scout" = not operationalized = real upgrade | CONNECT (promote to deep-PCB primary) |
| 2 | https://github.com/gumyr/build123d | rising | Apache-2.0 (permissive) | 2026 | gumyr | Python BREP code-CAD on OCCT; scriptable, diffable, version-controllable parametric modeling complementary to FreeCAD's GUI tree. | grep: "build123d"/"code-CAD" ABSENT = not a content-duplicate | ABSORB methodology (code-CAD lane) |
| 3 | https://github.com/CadQuery/cadquery | high | Apache-2.0 (permissive) | 2026 | CadQuery | The other major Python code-CAD framework on OCCT; build123d is derived from it. Alt code-CAD path. | grep: ABSENT = not a content-duplicate | ABSORB methodology (code-CAD lane) |
| 4 | https://github.com/neka-nat/freecad-mcp | ~642 | MIT | 2026-06-11 | neka-nat | Owned CAD spine. Star count CORRECTED: ~1,113 (inflated in file) -> ~642 verified. 10 tools incl. execute_code + run_fem_analysis. | grep: present (owned) = content-duplicate; fix inflated stars | CONNECT (refresh + correct stars) |
| 5 | https://github.com/lamaalrajih/kicad-mcp | ~468 | MIT | 2025-10 | lamaalrajih | Current KiCad primary (basic: BOM/netlist/DRC/read-only resources). Keep as the lightweight option; mixelpixx for deep PCB. | grep: present = content-duplicate; re-tier | CONNECT (re-tier to lightweight) |

## Notes
- Net-new: mixelpixx KiCad server (#1, promote for deep PCB) + build123d/CadQuery code-CAD lane (#2/#3).
- Correction: neka-nat/freecad-mcp star count was inflated to ~1,113 in the file; verified ~642 (2026). The build_notes "grew since 617" narrative is wrong - corrected.
- KiCad re-tier: lamaalrajih (~468, basic, simple BOM/netlist/check) stays the lightweight default; mixelpixx (~1,157, 122 tools, autoroute + JLCPCB + Freerouting) is the deep-PCB pick. Both MIT.
- License note on the apps themselves unchanged: FreeCAD LGPL, KiCad GPL (host runs them; we drive via MCP).
