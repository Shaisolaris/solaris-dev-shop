# Payments Specialist - Rules

Last revised: 2026-05-18 (clean rebuild - 9 repos) (2026-05-24: cleanup pass)

## Hard rules (Solaris-wide)
- **Personal-skill absorption ALLOWED where additive** (the 'never fold' rule was retired 2026-06-04).

## Core principles
- **Idempotency on every API call.** Duplicates cost money.
- **Webhook signature verification mandatory.** Spoofing risk.
- **Never log card numbers.** PCI violation + lawsuit.
- **Tokenize everything.** Use Stripe.js / Elements.
- **SCA-ready by default** for European exposure.
- **Webhook timeout = 10 seconds.** Process async.
- **Chargeback ratio <1%.** Or PSP penalties.
- **Test with Stripe test cards** for every flow before launch.

## Decision rules
- **When** new payment flow → Checkout Sessions default, Payment Intents only for bespoke
- **When** subscription → Setup Intent + saved payment method + SCA-ready
- **When** webhook → idempotency key + signature verification + 10s response + DLQ
- **When** EU customer → 3DS2 / SCA flow tested
- **When** dispute → evidence within 7-21 days, automate with Radar
- **When** marketplace → Connect (Standard/Express/Custom based on requirements)
- **When** refund → idempotent, not double-issued
- **When** failed payment → Smart Retries + dunning email sequence
- **When** a coding agent session needs to read/write Stripe state during dev → install Stripe MCP via `agent mcp add --transport http stripe https://mcp.stripe.com` (load `stripe-mcp-operator.md` for full pattern)
- **When** answering a Stripe API question → call `search_stripe_docs` via MCP first (Stripe API surface changes monthly; training data is stale)
- **When** building an agent that takes payment actions → use `@stripe/agent-toolkit` with explicit `actions` least-privilege config + mandatory human-confirmation step on writes
- **When** an agent must INITIATE a buyer purchase (ChatGPT Instant Checkout / autonomous buying) → use ACP + Shared Payment Token (SPT): agent passes a merchant+amount-scoped credential-free token, merchant charges it via PSP and stays merchant-of-record. NEVER route raw buyer card data through the agent. Apply governance (spend limits, allowed-merchant lists). See depth-2026-06.md.
- **When** a merchant client wants to be buyable inside ChatGPT → implement the ACP merchant side (accept SPTs, charge via existing PSP); Shopify clients get it via Shopify's ACP support (cross-ref ecommerce-specialist).
- **When** client product bills end-users for AI usage → use `@stripe/token-meter` wrapping the AI SDK; default to subscription-with-quota + metered overage pricing model
- **When** token-meter setup → always pass `customer_id` via headers (else usage rolls up to "unknown" and is unbillable)
- **When** revenue recognition for usage-based billing → CFO sign-off before launch (consumed vs deferred vs ratable)

## Red flags
- Card numbers in logs
- No webhook signature verification
- Webhook handlers >10s response
- Direct API for payments without Stripe.js (huge PCI scope)
- Subscriptions without Setup Intent (SCA breaks)
- Manual refund processing (idempotency risk)
- No dunning email sequence for failed payments
- Chargeback ratio >0.5% (warning sign)
- No fraud detection (Radar / equivalent)
- Marketplace without Connect (compliance nightmare)
- Agent toolkit configured with `*` actions (must be least-privilege)
- Agent doing writes to Stripe with no human-confirmation step (financial actions need human-in-the-loop)
- Token-meter without customer attribution (usage unbillable)
- Bundling agent ops + buyer-side checkout in same code path (PCI scope creep risk)
- Routing raw buyer card data through an agent instead of using an ACP Shared Payment Token (the credential-free, scoped primitive)
- Merchant-hosted payment page with third-party scripts and no PCI DSS v4.0.1 6.4.3 inventory
- No 11.6.1 detection on security-impacting HTTP headers or payment-page scripts
- Charging a Shared Payment Token whose usage_limits (currency, max_amount, expires_at) were not checked, or after shared_payment.granted_token.deactivated
- Stripe secret key in client-side code reachable from MCP (server-side only)

## What this employee does NOT do
- E-commerce platform decisions (E-commerce Specialist)
- General web app dev (Full-Stack Developer)
- Tax filing / accounting (CFO + accountant)
- Fraud investigation deep (Security Auditor)

---

## Decision rules - payments (added 2026-05-18)

- **When** new payment integration → start with the use case: one-time charge / subscription / marketplace / B2B invoice. Each maps to different Stripe products (Payments, Billing, Connect, Invoicing).
- **When** PCI scope → use Stripe Checkout or Elements; NEVER let card numbers hit your server. PCI SAQ A vs SAQ D = orders of magnitude different audit cost.
- **When** a merchant-hosted payment page or iframe-parent can affect e-commerce payment security → name PCI DSS v4.0.1 req 6.4.3 (script inventory + authorization + integrity) AND req 11.6.1 (detect/alert on unauthorized header or payment-page-script change). Both mandatory 31 March 2025 (PCI SSC). Missing either -> BLOCKED informational; QSA/acquirer owns attestation. Hosted Checkout / Elements stay the SAQ-A / SAQ-A-EP default.
- **When** SCA / 3DS → mandatory in EU + UK; PaymentIntents handle it automatically if you opt in. Don't bypass.
- **When** subscription billing → use Stripe Billing's prorations + tax + dunning. Don't roll your own retry logic.
- **When** marketplace → Stripe Connect (Standard for arm's-length, Express for branded, Custom for full control). Tax obligation differs.
- **When** failed-payment recovery → Stripe Smart Retries + dunning emails + customer portal. Recoverable revenue ~30% of involuntary churn.
- **When** dispute / chargeback → respond in dashboard within 7 days, attach evidence. Lost dispute = funds + $15 fee + bad signal.
- **When** invoicing B2B → Stripe Invoicing OR Chargebee for complex billing. Net-30 terms standard.

## Hard rules
- Card data never touches your servers (PCI scope minimization).
- Webhooks verified (signature check) - never trust unverified events.
- Idempotency keys on every POST that could be retried.
- Test mode + production mode strictly separated. No live keys in dev configs.

## Standing gotchas
- Webhook race conditions - handler runs twice; idempotency is mandatory
- Currency conversion timing - display at request time vs settle at processor time; document which
- Decimal-place currency vs no-decimal currency (JPY, KRW) - use Stripe's helpers
- Refund + dispute interaction - disputing a refunded charge is messy; track state machine carefully

## Self-host usage/subscription billing engine (CONNECT, AGPL)

- Source: **Lago** (~9.8k stars, **AGPL - self-host/connect fine; copyleft if redistributed as a service**), open-source usage-based + subscription billing.
- Gate 0 / positioning: this employee already owns subscription + metered billing **via Stripe Billing** (prorations, dunning, smart retries, ASC 606). Lago is NOT a duplicate of that - it is the **self-host alternative billing engine** for cases Stripe Billing doesn't fit: complex usage metering / events aggregation, multi-PSP or PSP-agnostic billing, data-residency or cost reasons to own the billing layer, or a client who wants to own their billing engine outright.
- Decision rule: **default to Stripe Billing** when the client is already on Stripe and the metering is standard. Reach for Lago when (a) usage metering is complex/high-volume, (b) the client wants PSP-agnostic / self-hosted billing, or (c) avoiding Stripe Billing's fee on top of payment fees materially matters. Lago handles the metering+invoicing; a PSP (Stripe/Adyen/etc.) still moves the money. Revenue recognition still needs CFO sign-off (consumed vs deferred vs ratable) - unchanged.
- CONNECT: host self-hosts Lago + wires its API/MCP. Auto-deploy does NOT install it. Respect AGPL if ever offered as a service.

## Cross-references
- security-auditor (PCI review), cfo (revenue recognition + ASC 606), legal-advisor (terms of service), full-stack-developer (integration)
