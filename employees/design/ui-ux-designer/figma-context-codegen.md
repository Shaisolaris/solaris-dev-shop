# Figma → Code via Figma-Context-MCP (ABSORB)

Absorbed 2026-06-13 from GLips/Figma-Context-MCP ("Framelink", npm `figma-developer-mcp`, **MIT**).

## Gate 0 - why this is net-new (not a duplicate of existing Figma content)
The ui-ux-designer already had **token-export** Figma workflows: Figma Tokens / Tokens Studio → JSON → Style Dictionary, Figma Dev Mode for inspect/measure, Figma variables-over-styles discipline. Those move *design tokens* into a build pipeline.
Figma-Context-MCP is a **different capability**: it pulls **live Figma file/frame/node layout + styling data directly into the coding agent's context** so the agent can one-shot-implement a design from a Figma link - far more accurate than pasting a screenshot. It is the *frame-to-code* path, not the *token-export* path. No overlap → ABSORB.

## Patterns lifted
1. **Link, don't screenshot.** When implementing a Figma design, give the agent the Figma file/frame/group **link** via the MCP, not a screenshot. The MCP fetches real layout/styling metadata; the agent codes from structured data, not pixels. This is the new default for design→code handoff.
2. **Context reduction is the point.** The server simplifies/translates the raw Figma API response down to the layout + styling that matters before it hits the model. Fewer, more-relevant tokens = more accurate output. Don't dump the whole Figma API payload at the model; let the MCP pre-digest it. Implication: target a specific frame/node, not an entire file, for best fidelity.
3. **Designs still pass our standards.** Generated code is a starting point, not the deliverable. It still goes through the design-system layer (token hierarchy primitive→semantic→component), WCAG 2.1/2.2 AA checks (contrast, touch targets, ARIA, keyboard), and responsive review per `rules.md`. Figma-to-code accelerates the first pass; it does not replace design QA or the token system.
4. **Pairs with, doesn't replace, the token pipeline.** Use Figma-Context-MCP for *building the components/screens*; keep Tokens Studio → Style Dictionary for *the token source of truth*. The frame codegen consumes the tokens; it doesn't redefine them.

## CONNECT (host installs - auto-deploy does NOT install external MCP servers)
- **figma-developer-mcp** (MIT): `npx -y figma-developer-mcp --figma-api-key=YOUR-KEY --stdio` (or set `FIGMA_API_KEY` in env). Requires a **Figma personal access token** (host-side). Free/OSS; the Framelink hosted tier is optional. Useful cross-cutting for frontend-developer too (same codegen-from-Figma use).

## Update 2026-06-13 - official Figma Dev Mode MCP is now the PRIMARY path
Figma ships a first-party Dev Mode MCP server (since mid-2025): it exposes the selected layer, node tree, variant info, layout constraints, DESIGN TOKENS/variables, components, and assets to the agent, and since March 2026 is BIDIRECTIONAL (push a VS Code-rendered UI back into Figma as editable frames). Because it is variables/tokens-aware it integrates better with our token pipeline than the community server.
- PRIMARY: official Figma Dev Mode MCP - enable in Figma desktop (Preferences -> Enable local MCP Server, Dev Mode); point a coding agent/Cursor/VS Code at it. CONNECT (Figma ToS; host enables; no code bundled).
- FALLBACK/OSS: GLips figma-developer-mcp (MIT, ~14.3k stars) - when an MIT/self-hosted server or PAT-only access is required.
Both remain design-to-code accelerators only; Tokens Studio -> Style Dictionary stays the token source of truth, and generated code still passes token-hierarchy + WCAG QA.
