# Agentic Commerce Patterns

> Companion to stripe-mcp-operator.md. Patterns for building **AI agents that take payment actions** vs. building **AI products that charge users**.

**Source canon:** stripe/ai monorepo (https://github.com/stripe/ai), Stripe agentic-commerce docs (https://docs.stripe.com/agents).

---

## 2026 update: THREE patterns now (ACP/SPT added)
The original two patterns (A: agent does an op; B: sell AI by usage) are joined by a NET-NEW buyer-side pattern: **C) agent-INITIATED checkout via the Agentic Commerce Protocol (ACP) + Shared Payment Token (SPT)** - Stripe+OpenAI+Meta, Apache-2.0, powers ChatGPT Instant Checkout. The agent hands the merchant a token scoped to a specific merchant + cart total, WITHOUT exposing the buyer's credentials; the merchant charges it via any PSP and stays merchant-of-record. This is the safe agent-era replacement for routing buyer card data through an agent (which stays forbidden). Full treatment in depth-2026-06.md.

## Official SPT charge path (Stripe docs, retrieved 2026-08-13)

Source: https://docs.stripe.com/agentic-commerce/concepts/shared-payment-tokens . ACP spec pin: `spec/2026-04-17` on https://github.com/agentic-commerce-protocol/agentic-commerce-protocol (Apache-2.0). ACP building blocks (https://docs.stripe.com/agentic-commerce/acp): agentic checkout, cart/feed, delegate payment (SPT), delegate authentication, orders/webhooks.

Merchant-side SPT is a `shared_payment.granted_token`. Test-mode only in this employee. Live charge, live SPT issue, and fund movement stay human.

| Trigger | Action | Block if |
|---|---|---|
| SPT received from an agent | Confirm `usage_limits` (`currency`, `max_amount`, `expires_at`) match the cart | limits missing, currency mismatch, or amount > `max_amount` |
| Charge the SPT | Create a PaymentIntent with `payment_method_data[shared_payment_granted_token]`; confirm in TEST MODE only | live keys, or `confirm=true` on live |
| SPT lifecycle | Design webhook handling for `shared_payment.granted_token.deactivated`; never reuse a deactivated token | webhook path not designed |
| Jurisdiction | Confirm the official supported-country list on the Stripe SPT page before designing merchant-side SPT | selling jurisdiction unstated |
| API version | SPT objects are documented on `Stripe-Version: 2026-04-22.preview`; do not silently override the account pin `2026-06-24.dahlia` | preview flag not stated |

Test helper (docs only; never live): `POST /v1/test_helpers/shared_payment/granted_tokens`. This employee does not run `link-cli spend-request` against a live profile.

## Two distinct use cases, two distinct toolchains

### A) Agent takes a payment action on behalf of a human user
Examples: "Issue a refund," "Cancel this subscription," "Generate this invoice," "Set up a new product + price for our SaaS tier."

**Toolchain:** `@stripe/agent-toolkit` framework adapter + scoped `actions` config + always a confirmation step before write operations.

**Confirmation pattern (mandatory for write ops):**
```typescript
// Tool returns "preview" first, requires explicit user confirmation, then executes
const refundPreview = await agent.previewRefund({ paymentIntent, amount });
// Show preview to user → user confirms → then:
const refund = await agent.confirmRefund(refundPreview.token);
```

**Why:** never let a chat-mediated agent write to Stripe without a human-in-the-loop confirmation step on financial actions. Same principle as Cowork's "do not execute trades or move money" rule, applied to client work.

---

### B) Selling AI as a product - billing end-users for AI usage
Examples: a client's chatbot product that charges per conversation, an AI summarizer that charges per summary, a Solaris white-label AI tool delivered with usage-based pricing.

**Toolchain:** `@stripe/token-meter` + Stripe metered subscription pricing + customer attribution via headers.

**Pricing model decisions:**
| Model | When to use | Stripe primitive |
|-------|------------|------------------|
| Pure usage (per token) | Variable usage, low engagement risk | Metered price + usage records |
| Tiered with included quota | Want predictable bill at low end | Tiered metered pricing |
| Subscription + overage | SaaS-style with usage cap | Recurring price + metered overage |
| Credit packs | Prepaid, gift-friendly | Customer balance + usage records |

**Default for Solaris client work:** subscription with included quota + metered overage. Predictable revenue + usage upside.

---

## "Headless commerce" pattern (Stripe Connect + agent flow)

For Solaris marketplace clients (CTT, Turnpike-style), the seller-facing flow can run through agents:
1. Agent onboards a new seller via Connect Express (KYC handoff to Stripe-hosted page).
2. Agent creates products + prices for the seller via `@stripe/agent-toolkit`.
3. End-user purchases go through Checkout Sessions (still PCI-compliant frontend).
4. Stripe routes funds to seller automatically; platform takes application fee.

The agent only ever touches **seller-side ops** (onboarding, catalog, payouts). Buyer-side payment flow stays pure Stripe.js / Checkout. **Never blur the line.**

---

## Anti-patterns

- ❌ **Letting an agent process buyer payments directly.** Buyer payments = Stripe.js + Checkout + 3DS2 + PCI scope. Agent toolkit is for ops, not checkout.
- ❌ **Token meter without customer attribution.** Every metered call must have a `customer_id` - otherwise usage rolls up to "unknown" and you can't bill.
- ❌ **Granting agent broad delete scope.** Refunds yes (with confirmation). Customer.delete? No. Subscription.cancel only with confirmation.
- ❌ **Skipping the docs-search step.** Stripe APIs change. The MCP knowledge base + agent toolkit docs are authoritative - training data is not.
- ❌ **Bundling agent + buyer flow in the same code path.** Keep them in separate services so a bug in agent ops can never affect checkout PCI scope.

---

## Token-meter - handling input vs output token mismatch

Anthropic / OpenAI charge differently for input vs output tokens. Token-meter handles this natively, but the markup model needs to be set explicitly:

```typescript
const meter = new StripeMeter({
  // Bill input + output separately (recommended for transparency)
  inputMeterId: "input_tokens_meter_xxx",
  outputMeterId: "output_tokens_meter_xxx",
  // Or bill blended (simpler invoice but harder to optimize)
  blendedMeterId: "blended_tokens_meter_xxx",
  markup: { multiplier: 1.5 }, // 50% margin on cost
});
```

**Decision rule:** for a v1 product, blended is fine. For a mature product where the customer is asking "why's my bill so high," separate I/O metering with a transparent breakdown wins trust.

---

## ASC 606 + revenue recognition for usage-based billing

Token-meter generates usage records that flow to Stripe invoices, but **revenue recognition** still needs accountant judgment:
- **Pure usage** = recognize as consumed (matches GAAP for services-rendered).
- **Prepaid credits** = deferred revenue until consumed.
- **Subscription with quota** = ratable recognition over period.

Hand off to CFO for any client where revenue rec is non-trivial. Don't try to ship it without their sign-off.

---

## CTT-applicable pattern

If/when CTT adds an AI feature that charges per use:
1. Use Stripe MCP during dev to set up product + metered price.
2. Use token-meter wrapper around the AI SDK call site.
3. Use Connect-style platform fee if charging on top of a third-party model cost.
4. Have CFO review revenue recognition before launch.
