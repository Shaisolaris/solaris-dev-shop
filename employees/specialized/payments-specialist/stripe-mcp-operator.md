# Stripe Agent-Toolkit + MCP Operator

> ⚠️ ALWAYS load this file FIRST when the owner mentions Stripe, payments, agentic commerce, AI billing, or token metering.

**Source canon:** [stripe/ai monorepo](https://github.com/stripe/ai) - Stripe's official agent toolkit. 1,506 stars, MIT, daily commits. Contains:
- `@stripe/agent-toolkit` - framework adapters (OpenAI / LangChain / CrewAI / Vercel AI SDK / Anthropic)
- `@stripe/ai-sdk` - Vercel AI integration with Stripe billing
- `@stripe/token-meter` - usage metering with native SDKs from OpenAI, Anthropic, Google
- Stripe MCP server (hosted at `https://mcp.stripe.com`)
- Bridge to docs.stripe.com knowledge base

This is **the** source for any Stripe + AI work going forward. It supersedes the wshobson stripe-integration source as the *primary* reference for agent-driven payment ops, while wshobson remains the source for human-developer Stripe REST integration patterns.

---

## When to use Stripe MCP vs. raw Stripe API vs. wshobson patterns

| Scenario | Use |
|----------|-----|
| a coding agent session needs to read/write Stripe state during dev work | Stripe MCP server (`agent mcp add --transport http stripe https://mcp.stripe.com`) |
| Building an end-user agent that creates customers, manages subscriptions, issues refunds, generates invoices | `@stripe/agent-toolkit` adapters for the framework being used |
| Billing AI products by usage (per-token, per-call) | `@stripe/token-meter` |
| Static REST integration in a long-lived codebase (no agent involvement) | wshobson stripe-integration patterns (Checkout Sessions / Payment Intents / Setup Intents) - still canonical |
| Production subscription billing with proration / dunning / SCA | wshobson billing-automation patterns + Stripe SDK directly |

**Bright line:** Stripe MCP and agent-toolkit are for **agent-mediated** Stripe ops. Webhook handlers, subscription billing logic, and PCI-scoped customer-facing checkout still go through the standard SDK + Stripe.js - same as before. The MCP is a developer/agent-side tool, not a replacement for the runtime payment layer.

---

## Install commands

```bash
# Stripe MCP server - for a coding agent dev sessions
agent mcp add --transport http stripe https://mcp.stripe.com

# Authenticate (OAuth flow opens in browser)
# Or use a restricted API key for read-only access:
agent mcp add --transport http stripe https://mcp.stripe.com -e STRIPE_API_KEY=rk_test_xxx

# Agent toolkit (npm) - for building production agents
npm install @stripe/agent-toolkit

# Token meter - for billing AI usage
npm install @stripe/token-meter
```

---

## Stripe MCP - 25 tools across 13 resource categories

(Catalog as of 2026-04 - Stripe ships new tools continuously; check `/tools list` in MCP for live inventory.)

### Customers
- Create customer
- Read customer (by ID or email)
- Update customer
- List customers (filtered)

### Products + Prices
- Create product
- Create price (one-time or recurring)
- List products / prices
- Update price (deprecate old, ship new - Stripe prices are immutable for amount changes)

### Subscriptions
- Create subscription
- Update subscription (plan change, quantity, pause/resume, cancel)
- Read subscription state + upcoming invoice
- Preview proration

### Invoices
- Create invoice (one-off or finalize draft)
- Send invoice
- Mark uncollectible / void
- Read invoice + line items

### Refunds + Disputes
- Create refund (full or partial)
- List disputes
- Submit dispute evidence (read-only in MCP - full submission via dashboard or SDK to keep audit trail clean)

### Coupons + Promotion Codes
- Create coupon
- Create promotion code
- Apply to subscription / customer

### Checkout
- Create Checkout Session
- Read Checkout Session state

### Payment Links
- Create payment link
- Read payment link analytics

### Connect (marketplace)
- Read connected account state
- Create transfer
- Read payout state

### Knowledge base
- Search Stripe docs (semantic)
- Search Stripe support articles
- Validate API call (lint before sending)

---

## Agent toolkit usage pattern

```typescript
import { StripeAgentToolkit } from "@stripe/agent-toolkit/openai";

const toolkit = new StripeAgentToolkit({
  secretKey: process.env.STRIPE_SECRET_KEY!,
  configuration: {
    actions: {
      customers: { create: true, read: true },
      paymentLinks: { create: true },
      products: { create: true },
      prices: { create: true },
      // ... only enable what the agent needs (least-privilege)
    },
  },
});

// Use with OpenAI / Anthropic / etc. - toolkit exposes typed tool schemas
const tools = toolkit.getTools();
```

**Critical: configure the `actions` block to least-privilege.** Don't enable all actions by default. An agent that only needs to create payment links should not have `customers.delete`.

---

## Token-meter pattern (billing AI products)

For Solaris white-label work where the deliverable is itself an AI product, the client needs to bill end-users for AI usage. `@stripe/token-meter` ships native middleware for OpenAI / Anthropic / Google SDKs that:
1. Counts input + output tokens per call.
2. Reports usage to Stripe metered billing automatically.
3. Handles per-customer attribution via header pass-through.
4. Supports markup pricing (cost-plus or fixed-margin).

```typescript
import { StripeMeter } from "@stripe/token-meter";
import Anthropic from "@anthropic-ai/sdk";

const meter = new StripeMeter({
  apiKey: process.env.STRIPE_SECRET_KEY!,
  meterId: "tokens_meter_xxx",
});

// Wrap the Anthropic client
const anthropic = meter.wrap(new Anthropic());

// Now every call is metered to Stripe under customer_id from headers
await anthropic.messages.create({
  model: "the coding agent-sonnet-4-6",
  // ...
}, {
  headers: { "X-Stripe-Customer": customerId },
});
```

**Decision rule:** if a client wants to bill end-users for AI usage, default to token-meter. If it's an internal tool with fixed-cost AI, skip metering.

---

## Stripe MCP knowledge base - replace doc-stale Stripe answers

The MCP exposes a `search_stripe_docs` tool that hits Stripe's live documentation index. Use this **before** answering any Stripe API question from training data - Stripe's API surface changes monthly, and stale answers cost time.

**Workflow:**
1. The owner asks a Stripe question.
2. Call `search_stripe_docs` with the topic.
3. Cross-check against latest API version.
4. Answer with link to canonical doc.

This is the same pattern as Context7 for general libraries, but Stripe-specific.

---

## Anti-patterns (do NOT do)

- ❌ Using Stripe MCP to bypass webhook idempotency - webhooks still need signature verification + idempotency keys, MCP doesn't change that.
- ❌ Granting `*` actions to an agent toolkit - least-privilege only.
- ❌ Storing Stripe secret keys in client-side code via the MCP - the MCP is server-side / a coding agent session only.
- ❌ Using token-meter for non-AI charges - it's a metering middleware, not a generic billing layer.
- ❌ Replacing Stripe.js / Elements / Checkout for end-user payments with MCP - MCP is dev-side. End-user payments still need PCI-compliant frontend.

---

## Cross-references inside Solaris

- **wshobson stripe-integration** patterns - kept as canonical for static REST integration; this MCP layer adds on top.
- **wshobson billing-automation** - still the reference for production subscription / dunning logic.
- **DevOps Engineer secrets-management discipline** - Stripe API keys MUST go through the same secret-management discipline as any production credential; never commit, never log. See DevOps Engineer's deployment + secrets handling references.
- **CTO** - Stripe MCP install is part of the standard "new client project" checklist when payments are involved.
- **Code Reviewer** - flag any direct `stripe.*` SDK call in PR diffs that should be going through the MCP for agent code, or any agent-toolkit call missing `actions` least-privilege scope.
