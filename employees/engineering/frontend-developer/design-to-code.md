# Design-to-Code (Figma → implementation)

Absorbed from GLips/Figma-Context-MCP "Framelink MCP for Figma" (MIT, ~15k★, verified 2026-06-13) - the design-to-code patterns, not the server code. The MCP server itself is host-installed (see SKILL "Connected MCP servers"); these are the rules for using it well.

## Why pasting a screenshot is the wrong default
A screenshot loses the layout tree, the exact spacing/typography/color tokens, auto-layout intent, and component boundaries. The model then *guesses* pixel values and re-derives a structure that the design already encodes. Pulling the **structured Figma node data** instead - and pruning it to only layout + styling - produces accurate one-shot implementations. The core lesson Framelink encodes: **less, well-chosen context beats more raw context.** Fetch the node, strip it to what matters, then write code.

## Workflow - implementing a Figma frame
1. **Get the node, not a picture.** Take the Figma file/frame/group link. Pull the simplified node tree via the MCP (`get_figma_data`-style call). Never start from a screenshot when the file is available.
2. **Read the layout tree first.** Map auto-layout → flex/grid: direction, gap, padding, alignment, sizing (hug / fill / fixed). Auto-layout is the design's flexbox; translate it literally before touching visuals.
3. **Lift tokens, never literals.** Colors, spacing, radii, typography come back as values - map each to the project's existing design tokens / Tailwind theme. A raw `#3B82F6` in the output is a bug; it must resolve to the token. (This is the same rule as "Frontend ↔ UI/UX designer: use tokens not literals" - the MCP just makes the source values explicit.)
4. **Respect component boundaries.** A Figma component instance → one React component. Repeated instances → one component rendered in a list, not copy-pasted markup. Variants → props, not separate components.
5. **Pull image/SVG assets via the MCP's asset download**, don't re-trace icons by hand or inline base64 blobs the model invented.
6. **Prune before prompting.** If the node tree is huge (whole page), fetch frame-by-frame. Over-large context degrades accuracy - the whole reason this MCP simplifies the API response.
7. **Reconcile with the live component library.** Before generating new markup, check whether the design maps to an existing shadcn/ui or in-house component. Implement against what exists; only generate net-new structure.

## Guardrails
- The MCP needs a **Figma personal access token** (host-side secret) and a Figma file the user can read. No token → no structured data → fall back to the design spec from UI/UX, not to guessing.
- Structured data still needs human design judgment for states the static frame doesn't show (hover/focus/disabled/empty/loading) - frontend owns those per the a11y contracts.
- MIT-licensed: patterns above are distilled, not copied. The server is installed and run by the host, not vendored here.
