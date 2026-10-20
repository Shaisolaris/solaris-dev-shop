# Payments Specialist - Learnings (Pending)

## Pending observations
- **2026-10-19 - G22 export hardening (needs affected recheck)**: the G30 integration check fed books with an unapplied 40.00 refund (evt_007) and a refused out-of-stock order (evt_008) to G14 and G17; export-g14 exited 0 with only the applied rows, so G14 reconciled and G17 decided as if clean. An export of books is a claim that they are final: it now refuses while anything is held, in exception or unapplied.
- **2026-10-19 - G22 webhook ledger**: out-of-order delivery is the quiet loss: a refund that arrives before its capture is usually dropped as "unknown order". Concurrent ingests also exposed a real SQLite trap: switching to WAL on every open fails with "database is locked" when two handlers start together. *Proposed rule: hold events until their prerequisite arrives, keep unapplied money visible, and set WAL once at creation.*
- **2026-04-25 - Clean rebuild from wshobson payment-processing pod**: Checkout Sessions default, Payment Intents only for bespoke is the cleanest decision rule.
- **2026-04-25 - Webhook idempotency + signature verification** is the most-violated production payment rule.
- **2026-04-27 - stripe/ai absorbed (v0.3.0)**: Stripe shipped its own official agent-toolkit + MCP + token-meter monorepo. The decisive add was the **bright-line split** between agent-ops (uses MCP / agent-toolkit, dev-side, requires human-confirmation on writes) vs buyer-side checkout (still pure Stripe.js + Checkout, PCI-scoped). Without this split, agent codepaths can drag PCI scope into themselves. Documented in agentic-commerce-patterns.md.
- **2026-04-27 - Token-meter customer-attribution gotcha**: Every metered API call must pass `customer_id` via headers. Missing the header makes usage roll up to "unknown" - invisible at billing time. Easy production miss.
- **2026-04-27 - Stripe docs change monthly**: training-data Stripe answers are routinely stale by 30+ days. The MCP `search_stripe_docs` tool is now the answering protocol, not a fallback.

- **2026-06-13 (depth) - ACP + Shared Payment Token absorbed** - the 2026 Stripe+OpenAI+Meta open standard (Apache-2.0) for agent-initiated buyer checkout; SPT is the scoped, credential-free token that makes agent checkout safe (no buyer card data through the agent). Powers ChatGPT Instant Checkout. This is a third agentic pattern beyond agent-ops and usage-billing.
- V5-ORDER-04: removed the coding agent-is provider lock-in; employee is provider-neutral.
- V5-ORDER-04: PCI DSS v4.0.1 req 6.4.3 / 11.6.1 (mandatory 31 March 2025) + official Stripe SPT charge path (usage_limits, granted_token.deactivated, test-mode only).

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |

## 2026-07-24 engineering-core upstream
- Pin Stripe API to 2026-06-24.dahlia; refuse live keys in agent context.
- Toolchain mismatch / missing MCP fails with one BLOCKED toolchain cause.
- Source: docs.stripe.com/api/versioning.
## Sources

- Upstream: agentic-commerce-protocol/agentic-commerce-protocol (Apache-2.0 (permissive)); stripe/ai (MIT); https://docs.stripe.com/agentic-commerce/acp (n/a); mcp.stripe.com (n/a); getlago/lago (FLAG: AGPL (copyleft if served))
- What was used: methodology absorbed: agentic-commerce-protocol/agentic-commerce-protocol; connected as external reference: agentic-commerce-protocol/agentic-commerce-protocol, stripe/ai, mcp.stripe.com, getlago/lago; methodology only: https://docs.stripe.com/agentic-commerce/acp
- License notes: getlago/lago: FLAG: AGPL (copyleft if served)
