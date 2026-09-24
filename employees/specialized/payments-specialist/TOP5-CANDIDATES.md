# Payments Specialist - TOP 5 verified 2026 candidates

Domain: Stripe / billing / payments. Verified 2026-06-13.

| # | Source | Stars/Status | License | Last update | Maintainer | What it adds | Gate-0 | Tag |
|---|--------|--------------|---------|-------------|------------|--------------|--------|-----|
| 1 | https://github.com/agentic-commerce-protocol/agentic-commerce-protocol | open standard | Apache-2.0 (permissive) | 2026 (since 2025-09) | OpenAI + Stripe + Meta | ACP + Shared Payment Token (SPT): new primitive letting agents (ChatGPT Instant Checkout) initiate scoped, merchant+amount-bound payments WITHOUT exposing buyer credentials; merchant of record intact, charge via any compliant PSP. Powers ChatGPT Instant Checkout (Etsy, Shopify brands). | grep: "ACP"/"Agentic Commerce Protocol"/"Shared Payment Token" ABSENT = not a content-duplicate; major real gap | ABSORB methodology / CONNECT |
| 2 | https://github.com/stripe/ai | ~1.5k | MIT | 2026-05 | Stripe | Owned agent-toolkit/MCP/token-meter monorepo. Confirmed current (~1,506). | grep: present = content-duplicate | CONNECT (confirmed) |
| 3 | https://docs.stripe.com/agentic-commerce/acp | docs | n/a | 2026 | Stripe | Stripe's ACP implementation docs (SPT issuance, merchant charge flow, governance: spend limits/allowed-merchant lists/fraud screening). | grep: ABSENT = not a content-duplicate | METHODOLOGY (impl reference) |
| 4 | mcp.stripe.com (Stripe MCP, 25 tools) | hosted | n/a | 2026 | Stripe | Dev-side Stripe ops MCP, already absorbed. | grep: present = content-duplicate | CONNECT (confirmed) |
| 5 | https://github.com/getlago/lago | ~9.8k | FLAG: AGPL (copyleft if served) | 2026 | getlago | Self-host usage/subscription billing engine, already absorbed (CONNECT, flagged). | grep: present = content-duplicate | CONNECT (flagged, confirmed) |

## Notes
- Net-new and important: ACP + Shared Payment Token (#1/#3) - the 2026 open standard for agent-initiated payments (Stripe + OpenAI + Meta, Apache-2.0). This is squarely this employee's "agentic commerce" domain and was absent; the existing agentic-commerce-patterns.md predates it.
- #2/#4/#5 confirmed current. stripe/ai ~1.5k MIT.
- ACP relationship to existing content: the employee's "agent takes a payment action" (agent-toolkit) and "selling AI by usage" (token-meter) patterns are about ops/metering; ACP/SPT is the new BUYER-side primitive for agent-initiated checkout - a third, distinct pattern that updates the buyer-flow bright line.
