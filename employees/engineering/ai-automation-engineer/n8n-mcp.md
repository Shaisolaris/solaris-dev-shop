# n8n-mcp - node-aware workflow building (absorbed tool surface)

Source: czlonkowski/n8n-mcp (https://github.com/czlonkowski/n8n-mcp) + companion n8n skills. Verified live 2026-06-22 (re-confirmed maintained). ABSORB the tool surface + workflow methodology; the live MCP is operator-installed. n8n is THIS employee's primary tool, so this closes a confirmed prior miss.

## Gate 0 (net-new)
The employee could describe n8n conceptually but had no node-accurate building surface. n8n-mcp gives the agent the actual n8n node catalog + schemas so it can generate VALID workflow JSON instead of guessing node/param shapes.

## Capability surface
- Node knowledge: query the n8n node catalog (hundreds of nodes), per-node parameter schemas, credentials types, and operation lists.
- Build: generate importable n8n workflow JSON (nodes + connections + parameters) that validates against the real schemas.
- Validate: check a workflow/node config against the schema before import (catches invalid params, missing credentials, wrong connections).
- Docs: pull node documentation inline while building.

## Workflow methodology
1. Resolve the trigger + each action to real node types via the catalog (don't invent node names).
2. Fill parameters from the per-node schema; mark credential placeholders, never hardcode secrets.
3. Validate the assembled workflow against the schema; fix before handing the JSON to the operator to import.
4. Build idempotent / re-runnable flows; add error-handling + retry nodes where the run is side-effecting.

## Connect vs absorb
The live MCP (and an n8n instance + API key) is operator-side. The methodology + the "validate-against-real-schemas before shipping JSON" discipline is absorbed here.
