# Shopify MCP layer - schema validation + live store data + canonical pattern sources

Added v0.6.0 (2026-06-13, Upgrade Plan Part 2). All sources verified live 2026-06-13. This is the real-client-depth layer on top of the v0.5.0 Shopify-AI-Toolkit base. It does NOT replace the existing Liquid/Functions/Hydrogen/webhook/migration/audit workflows - it makes the GraphQL in them correct and lets ops run on real data.

## 1. Shopify Dev MCP (@shopify/dev-mcp) - CONNECT, the #1 upgrade (non-negotiable)
- Package: `@shopify/dev-mcp` (official Shopify, npm **v1.14.0**, ISC per npm). The docs/schema MCP - no store credentials needed.
- What it does: validates GraphQL against the **live Admin / Storefront / Functions schemas**, introspects the Admin schema, and searches Shopify dev docs. It is how you stop hallucinating fields/arguments.
- Host connect (Claude Code): `claude mcp add shopify-dev -- npx -y @shopify/dev-mcp@latest` (or the equivalent claude_desktop_config.json `mcpServers` entry with `command: npx, args: ["-y","@shopify/dev-mcp@latest"]`).
- **The discipline it enforces (write into every GraphQL task):**
  1. **Learn the API first** - query the dev docs/schema for the objects + fields involved. Never trust memorized GraphQL.
  2. **Write** the query/mutation.
  3. **VALIDATE it against the live schema via dev-MCP BEFORE delivering.** A query that doesn't validate is not delivered.
  This replaces "search current docs" in Workflow 3/4 with "search-then-VALIDATE". Hallucinated fields are the #1 Shopify failure mode; this kills them.

## 2. GeLi2001/shopify-mcp - CONNECT, live store DATA (complements dev-MCP)
- MIT, 218★, last push 2026-04-05. Talks to a real store's **Admin GraphQL API (2026-01)** - 31 tools:
  - Products (8): get/create/update/delete, manage options + variants (bulk), delete variants.
  - Customers (8): CRUD, merge, manage address.
  - Orders (10): smart lookup (name/id/GID), update, cancel, close/open, mark-as-paid, fulfillment, refund, draft orders.
  - Metafields (3), Inventory (1: set absolute quantities at a location), Tags (1).
  - Cursor pagination + sortKeys + Shopify search syntax on all list tools.
- Auth (set up by host, per client): **client credentials** (Dev Dashboard app, Jan 2026+ - clientId/clientSecret, auto-refreshed ~24h tokens) OR legacy static `shpat_` token. Domain = `<shop>.myshopify.com`.
- Host connect (Claude Code): `claude mcp add shopify -- npx shopify-mcp --clientId <ID> --clientSecret <SECRET> --domain <shop>.myshopify.com`.
- **Division of labor:** dev-MCP = docs + schema validation (no store). GeLi2001 = live data + ops on a real store. Use dev-MCP to get the query RIGHT, GeLi2001 (or the AI-Toolkit `store execute` flow) to RUN it.
- **Client safety:** vet the OAuth scopes per client before connecting - request the minimum (the existing "Store operations doctrine" / 7 scope groups). A mutation tool on a live store is a write to the client's business - keep the existing "never deploy/destructively-mutate for the client without sign-off" rule.

## 3. Canonical pattern-source pillars (named upstreams - reference, reinforce existing workflows)
All MIT except dawn. Use these as the ground-truth upstreams behind the workflows already in SKILL.md:
- **Shopify/hydrogen** (MIT, 1,972★) - headless storefront patterns. Ships its own CLAUDE.md / .mcp.json - mine it when building Hydrogen.
- **Shopify/function-examples** (MIT, 242★) - worked examples for checkout/discount/delivery/cart Functions (Workflow 4). The canonical "how a Function is structured" reference.
- **Shopify/theme-tools** (MIT, 216★) - Theme Check / Liquid linting (Workflow 3 step 4 "validate with Shopify theme tooling" = this). The linter to run before delivering a theme component.
- **Shopify/liquid** (MIT, 11,809★) - the Liquid language ground truth (the Liquid-limits rules in Workflow 3 trace here).
- **Shopify/dawn** (source-available, NOASSERTION, 3,018★) - the reference theme (already the Dawn base in Workflow 1/3). PATTERN reference only - do NOT redistribute dawn's code.

## How this layer slots into the existing workflows (no duplication)
- **Workflow 3 (theme):** step 1 "search docs" -> now "learn via dev-MCP"; step 4 "theme tooling" -> theme-tools/Theme Check is the named linter.
- **Workflow 4 (Functions):** input queries get **dev-MCP validated** before build; function-examples is the structure reference.
- **Workflow 1/2 (store setup + migration):** GraphQL run via the AI-Toolkit `store execute` flow OR GeLi2001 tools on live data; validate mutations with dev-MCP first.
- **Conversion/store audits (Workflow 5):** GeLi2001 reads live orders/products/customers/inventory to ground the funnel numbers instead of asking the client to export.
- **Webhooks (Workflow 6):** unchanged (HMAC verification is the AI-Toolkit content); register topics via Admin GraphQL - validate the registration mutation with dev-MCP.

## Honesty / limits
- dev-MCP = docs/schema only, no store access; GeLi2001 = needs real store credentials (client responsibility).
- GeLi2001 is 218★ - pin a known-good version, re-scan on upgrade per Scout security protocol, minimum scopes for client stores.
- The official `Shopify/dev-mcp` GitHub repo was not publicly resolvable on 2026-06-13 (404); the npm package `@shopify/dev-mcp` v1.14.0 is the authoritative artifact and the source of these instructions.
