# Payments Specialist - Learnings (Pending)

## Pending observations
- **2026-04-25 - Clean rebuild from wshobson payment-processing pod**: Checkout Sessions default, Payment Intents only for bespoke is the cleanest decision rule.
- **2026-04-25 - Webhook idempotency + signature verification** is the most-violated production payment rule.
- **2026-04-27 - stripe/ai absorbed (v0.3.0)**: Stripe shipped its own official agent-toolkit + MCP + token-meter monorepo. The decisive add was the **bright-line split** between agent-ops (uses MCP / agent-toolkit, dev-side, requires human-confirmation on writes) vs buyer-side checkout (still pure Stripe.js + Checkout, PCI-scoped). Without this split, agent codepaths can drag PCI scope into themselves. Documented in agentic-commerce-patterns.md.
- **2026-04-27 - Token-meter customer-attribution gotcha**: Every metered API call must pass `customer_id` via headers. Missing the header makes usage roll up to "unknown" - invisible at billing time. Easy production miss.
- **2026-04-27 - Stripe docs change monthly**: training-data Stripe answers are routinely stale by 30+ days. The MCP `search_stripe_docs` tool is now the answering protocol, not a fallback.

- **2026-06-13 (depth) - ACP + Shared Payment Token absorbed** - the 2026 Stripe+OpenAI+Meta open standard (Apache-2.0) for agent-initiated buyer checkout; SPT is the scoped, credential-free token that makes agent checkout safe (no buyer card data through the agent). Powers ChatGPT Instant Checkout. This is a third agentic pattern beyond agent-ops and usage-billing.
- V5-ORDER-04: removed Claude-is provider lock-in; employee is provider-neutral.
- V5-ORDER-04: PCI DSS v4.0.1 req 6.4.3 / 11.6.1 (mandatory 31 March 2025) + official Stripe SPT charge path (usage_limits, granted_token.deactivated, test-mode only).

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |

## 2026-07-24 engineering-core upstream
- Pin Stripe API to 2026-06-24.dahlia; refuse live keys in agent context.
- Toolchain mismatch / missing MCP fails with one BLOCKED toolchain cause.
- Source: docs.stripe.com/api/versioning.
