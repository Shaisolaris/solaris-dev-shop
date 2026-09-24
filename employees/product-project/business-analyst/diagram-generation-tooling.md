# Diagram-Generation Tooling (ABSORB)

Absorbed 2026-06-13 from hustcc/mcp-mermaid (MIT, npm `mcp-mermaid`). The diagram *methodology* in `rules.md` - BPMN Silver method-and-style, swim-lane rules, gateway labeling, ERD/use-case/data-flow conventions - is unchanged and remains the source of truth for *what* to draw. This file is the *rendering* layer: how to turn that methodology into actual diagram artifacts (SVG/PNG) instead of hand-drawn screenshots or prose descriptions.

## What it adds (net-new vs current BA content)
- The BA could describe a swim-lane / ERD / sequence diagram in words but had no generation path. mcp-mermaid renders **any Mermaid diagram type** from text: flowchart (as-is/to-be process maps), `erDiagram` (data model), `sequenceDiagram` (interaction/data-flow), class, state, Gantt, journey. One tool covers the BA's whole diagram catalog.

## How to use it (rules that make the output good)
1. **Methodology first, then render.** Decide the diagram per `rules.md` (lanes = roles not tools, one start/one end per pool, label every gateway outflow, verb-noun task names) BEFORE generating. The tool draws what you give it - it does not enforce BPMN style. Garbage-in stays garbage.
2. **Use the built-in validation loop.** The server validates Mermaid syntax and supports multi-round correction - if a render fails, fix the syntax and re-emit rather than shipping a broken diagram. This is the intended workflow: model emits → validate → correct → render.
3. **Pick the output format by destination:**
   - `svg` / `svg_url` - crisp, scalable, for BRD/spec docs and web.
   - `png_url` / `png file` (`outputType: "file"`, saved to disk) - for slide decks, email, and clients who want a flat image.
   - `mermaid` (raw text) - embed in markdown docs so the diagram lives as code-in-the-repo and stays editable (preferred for to-be process maps that will iterate).
   - `base64` - inline embedding when no file host is available.
4. **Theme + background** are configurable (`theme`, `backgroundColor`) - match the client/Solaris doc style; default to a clean light theme for deliverables.
5. **Prefer mermaid-as-text in living docs.** For an iterating to-be map, store the mermaid source in the doc so the next revision is a text diff, not a redrawn image. Render to PNG only for the frozen/shared snapshot.

## Scope note
- mcp-mermaid is Mermaid-only. For data *charts* (bar/line/pie from numbers) that is data-analyst's territory (mcp-server-chart / their dashboard tooling) - the BA uses mermaid for **structure** diagrams (process, data model, interaction), not for quantitative charting.

## CONNECT (host installs - auto-deploy does not install external MCP servers)
- **hustcc/mcp-mermaid** (MIT): `npx -y mcp-mermaid` (stdio), or run SSE/streamable (`mcp-mermaid -t sse`, port 3033) / Docker (`susuperli/mcp-mermaid`). No API key, no auth - local render. Free.

---

## Interpret an existing BPMN diagram (added 2026-06-13)

METHODOLOGY/CONNECT absorption from **jtlicardo/bpmn-assistant** (140 stars, MIT, last commit 2026-04-29). Gate-0 PASS (narrow): the BA could AUTHOR BPMN (Silver method-and-style) and RENDER it (mcp-mermaid above), but had no path to REVERSE-READ a BPMN diagram a client hands over. bpmn-assistant adds that interpret direction.

- **When a client supplies an existing process (BPMN XML, a .bpmn file, or a diagram export):** parse it and restate the process in plain language - the start event, each task + its owner lane, every gateway and its branch conditions, and the end state(s). Surface what the diagram implies but does not say: unlabeled gateway outflows, missing end states, tasks with no owner, and rework loops drawn as forward arrows.
- **Use it as the as-is input** for Workflow 2: an interpreted client BPMN becomes the as-is map, then instrument for cycle data (P50/P90) before designing to-be. Do not trust the diagram's implied timings - confirm them.
- **Edit/round-trip:** bpmn-assistant can also apply described edits back to BPMN XML; prefer keeping the canonical map as mermaid-as-text in the living doc (per the rules above) and use BPMN XML only when the client's toolchain (Camunda/Signavio) requires it.
- **CONNECT (host installs; methodology only - the repo's app is not bundled):** jtlicardo/bpmn-assistant (MIT) is a self-hostable LLM BPMN tool (FastAPI + React). For Solaris's purposes the interpret/critique LOGIC above is the absorbable part; run the upstream app only if a client needs interactive BPMN XML editing.
