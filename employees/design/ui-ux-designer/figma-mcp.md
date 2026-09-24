# Figma MCP bridge - live canvas read/analyze/modify (absorbed tool surface + connect)

Source: arinspunk/claude-talk-to-figma-mcp (https://github.com/arinspunk/claude-talk-to-figma-mcp). MIT, ~595 stars, v1.0.0 2026-04-18, ~250 commits, active. ABSORB (MIT) the tool surface + connect method; the live bridge is operator-installed.

## Gate 0 (why this is net-new)
This employee already has Figma CRAFT (Dev Mode inspect, Tokens Studio export, Style Dictionary pipeline, variables-vs-styles). It had NO live Figma MCP. This adds a new tool category: agentic READ / ANALYZE / MODIFY of the live Figma canvas.

## Capability surface
- Read: traverse the document tree, read nodes/styles/variables/components, export frame specs.
- Analyze: in-canvas WCAG contrast audits, token/style consistency checks, spacing/type-scale audits.
- Modify: bulk style/variable updates, rename/restructure layers, apply tokens across selections.
- Generate: emit React / Vue / SwiftUI from a selected frame.
- Multi-agent-safe command queue (serialized writes).

## Key advantage
Works with ANY Figma account. Figma's own first-party MCP requires a paid Dev Mode seat; this bridge does not - so the design lane can act on the canvas without that license.

## Connect steps (operator-side, live bridge)
1. Install the repo's MCP server + the Figma plugin/socket bridge it ships.
2. Open the target Figma file; pair the plugin to the MCP socket.
3. Drive via the MCP tools (read first, then modify on a copy/branch).

## Multi-agent / safety rules
- parentId rule: when creating/moving nodes, always pass the explicit parent node id; never rely on current selection across agents (selection is shared, races corrupt the tree).
- Write on a Figma branch or a duplicated page first; review before merging to main.

## Keep distinct
Accessibility-critique METHODOLOGY (from knowledge-work-plugins design plugin) is separate from this LIVE MCP bridge. Methodology says what good looks like; this acts on the canvas.
