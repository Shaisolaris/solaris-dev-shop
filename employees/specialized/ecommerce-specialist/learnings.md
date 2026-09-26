# E-commerce Specialist - Learnings (Pending)

## Pending observations
- **2026-06-09 - Source gap CLOSED**: Shopify/Shopify-AI-Toolkit (official org, MIT, 378★) shipped 20 skills; Phase-E web-search recommendation from 2026-04-25 fulfilled. Unmined remainder: shopify-polaris-* (4 skills), shopify-pos-ui, shopify-partner, shopify-payments-apps - candidates for next bump.
- **2026-06-09 - Telemetry caution**: official Shopify skills embed prompt-logging instrumentation (log_skill_use.mjs, base64 user prompt → shopify.dev/mcp/usage). Workflows absorbed, instrumentation excluded. Recheck on any future re-sync.
- **2026-04-25 - Apple Pay + Google Pay + Shop Pay** = 15-20% mobile conversion lift. Mandatory baseline.

- **2026-06-13 (depth) - dev-mcp license clarified MIT** - the Shopify AI Toolkit (incl. Dev MCP) was open-sourced MIT 2026-04-09; v1.14.0 current. No net-new source needed; field already covered.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| 2026-06-09 | Drafts-first imports, @idempotent inventory, 100-variant/3-option limits | rules.md Catalog + migration |
| 2026-06-09 | HMAC base64 raw-body + 200-within-5s webhook contract | rules.md Webhook rules |
| 2026-06-13 | Shopify Dev MCP search-then-VALIDATE before delivering GraphQL; GeLi2001 live-data MCP for store ops (min scopes) | rules.md GraphQL discipline + references/shopify-mcp-layer.md |
## Sources

- Upstream: @shopify/dev-mcp (MIT (AI Toolkit open-sourced 2026-04-09)); GeLi2001/shopify-mcp (MIT); Shopify/Shopify-AI-Toolkit (MIT); Shopify/hydrogen (MIT); Shopify/liquid (MIT)
- What was used: connected as external reference: @shopify/dev-mcp, GeLi2001/shopify-mcp, Shopify/Shopify-AI-Toolkit, Shopify/hydrogen, Shopify/liquid
- License notes: absorbed sources permissive (MIT/Apache-2.0); no code vendored
