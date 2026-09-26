# Sellable / productizable OSS platforms (client-deliverable stack)

Added 2026-06-14. A short index of the open-source platforms Solaris can deliver to clients or productize (host/resell/white-label), each with a one-line "what we could sell or host" and the license-for-resale note. Productization (turning any of these into a paid managed/white-label line) is **the owner's business decision** - this file is the menu, not the commitment.

Per-platform ownership: each tool's operational/methodology home is the named employee; delivery-lead carries this consolidated sellable view because productization and client delivery are delivery/business decisions.

## The stack

| Platform | License | What we could sell / host | License-for-resale note | Owner employee |
| --- | --- | --- | --- | --- |
| **Ghost** | MIT | White-label publishing: a client's blog/publication + newsletter + paid membership/subscription in one platform. | **Clean resale.** MIT is permissive; self-host, customize, white-label, and resell freely with no copyleft trigger. The cleanest of the set. | content-marketer (email-specialist owns deliverability) |
| **Medusa** | MIT | Headless commerce: a self-hosted Shopify alternative for custom-commerce / platform-fee-averse / owned-data clients. We bring storefront + PSP. | **Clean white-label resale.** MIT permissive; self-host, customize, resell freely; no copyleft trigger. | ecommerce-specialist |
| **Coolify** | Apache-2.0 | PaaS + managed hosting: our deploy platform and a "we host and manage it" managed-hosting revenue line on infra we control. | **Clean for hosting-as-a-service.** Apache-2.0 permissive; self-host, offer hosting-as-a-service, and modify freely; no copyleft trigger. | devops-engineer |
| **cal.com** | AGPL-3.0 | Scheduling product: booking pages, team/round-robin scheduling, calendar sync, payments, embeds for clients; also internal scheduling. | **AGPL - host-as-service OK.** Running it (modified or not) as a hosted service for clients is fine; the trigger is MODIFY + redistribute/serve - modified source served over a network must be offered to users (AGPL section 13). The `/ee` enterprise edition is a separate commercial license; check per-package before redistributing. Flag client-specific code changes to legal. | delivery-lead |
| **Plausible** | AGPL-3.0 | Privacy-first web analytics: cookie-free, GDPR/CCPA-friendly analytics on our own + client sites (a GA alternative). | **AGPL - self-host/host OK.** Self-hosting for own or client sites is fine; the trigger is modifying-and-serving the source over a network (section 13 source disclosure). Unmodified self-host or Plausible Cloud does not trigger it. | seo-aso-specialist |

## Resale-license cheat sheet

- **MIT (Ghost, Medusa):** the cleanest. Self-host, modify, white-label, resell - no obligations beyond keeping the license/copyright notice.
- **Apache-2.0 (Coolify):** permissive like MIT, plus an explicit patent grant. Hosting-as-a-service and modification are fine; no copyleft.
- **AGPL-3.0 (cal.com core, Plausible):** copyleft that reaches NETWORK use. Hosting an UNMODIFIED build as a service is fine. The obligation fires when we MODIFY the source AND make it available over a network - then the modified source must be offered to those users. Practical rule: ship client-specific changes as separate, non-AGPL integration code where possible, and flag any fork/modify-and-serve of the AGPL platform itself to legal.

## How to use this

- During scoping, when a client need maps to one of these (publishing/newsletter, commerce, hosting, scheduling, analytics), reach for the OSS platform instead of putting them on a paid SaaS - it can become a recurring managed/hosted line for Solaris.
- Confirm the per-platform CONNECT note in the owner employee's rules.md for the operational detail; this file is the business/menu view.
- Any decision to productize (price it, host it at scale, white-label it as a Solaris product) is escalated to the owner. Note the n8n caveat held by ai-automation-engineer: n8n is fair-code and its RESALE/hosting-to-clients is restricted, so it is deliberately NOT on this sellable list.
