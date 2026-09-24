# Email infrastructure + tooling depth (2026) - reference

METHODOLOGY absorption (2026-06-13, web research). Companion to email-marketing-depth-2026.md (strategy). This file is the TOOLING/INFRASTRUCTURE layer: the self-hosted ESP spectrum, a self-hostable deliverability test harness, and the template-paradigm matrix. No vendor code is bundled. AGPL/GPL tools are documented as self-host options only (run it yourself; do not vendor its source into a Solaris repo).

## 1. The self-hosted ESP spectrum (when Solaris owns the sending system)
Use when a client needs owned-list control, data residency/GDPR, or to escape per-contact SaaS pricing. Trade-off: you now own deliverability operations (warm-up, bounce processing, blocklist response) that a SaaS ESP handles for you. The rules.md deliverability + hygiene rules apply unchanged - self-hosting does not relax them, it makes them YOUR job.

| Layer | Tool | Stack | License | Fit |
|-------|------|-------|---------|-----|
| Newsletter + transactional, single binary | Listmonk (knadh/listmonk) | Go + PostgreSQL | AGPL-3.0 (self-host only) | Fastest setup; millions of subscribers/server; single+double opt-in; built-in bounce + click + top-link analytics; Go-template content with 100+ functions. Best default for an owned list. |
| Full marketing automation | Mautic (mautic/mautic) | PHP + MySQL | GPL-3.0 (self-host only) | Visual campaign builder, lead scoring, dynamic segments, landing pages, multi-channel. The open-source HubSpot alternative. Heaviest to operate; reach for it only when automation/scoring beyond Listmonk is required. |
| Lightweight Laravel option | SendPortal | PHP/Laravel | MIT | Lighter than Mautic; multi-workspace. Mentioned for completeness, not a primary pick. |

Decision rule: owned newsletter/transactional with minimal ops -> Listmonk. Need campaign automation + lead scoring + landing pages -> Mautic. Otherwise stay on the SaaS ESP table in rules.md (Postmark/Resend transactional, Customer.io lifecycle, Klaviyo ecommerce). NEVER mix marketing and transactional even when self-hosting: separate Listmonk transactional config/domain from the marketing one, same as the SaaS separation rule.

Self-host note (AGPL/GPL): deploy via the project's own Docker image; treat as an external service Solaris operates, not source to fork into a client repo. If a client modifies an AGPL tool (Listmonk) and exposes it over a network, the AGPL network-use clause requires offering the modified source. Keep deployments stock to avoid that obligation.

## 2. Self-hostable deliverability test harness (operationalizes the mail-tester gate)
rules.md requires "mail-tester.com score >=8" as a manual pre-send gate. happyDeliver (happyDomain/happydeliver, AGPL-3.0, self-host only) turns that into a scriptable, repeatable check:
- Scores SPF, DKIM, DMARC, BIMI, ARC, plus SpamAssassin and rspamd content scores, DNS records, and blocklist status.
- REST API to create a test and pull a report; built-in LMTP server so an MTA can route a probe message in.
- All-in-one Docker bundles Postfix + authentication_milter + SpamAssassin + the app.

Methodology - wire it into the launch protocol (rules.md Launch + monitoring): before the 10-20% rollout, send the campaign HTML+text through happyDeliver via its API; block the send if SpamAssassin score fails the >=8-equivalent threshold or any of SPF/DKIM/DMARC fails alignment. This makes the existing "verify mail-tester >=8" step a gate the CI/queue can enforce rather than a human remembering to paste into a web form. Self-host note: run the project's Docker image as an internal service; do not vendor its source.

## 3. Template-paradigm matrix (pick ONE per project, do not mix)
rules.md names "React Email or MJML" but gives no selection criteria or component model. The three live paradigms:

| Paradigm | Tool | When |
|----------|------|------|
| Markup language + compiler | MJML (mjmlio/mjml, MIT) | Designers/marketers editing templates; non-React stack; want Outlook-safe output for free. Semantic components (mj-section / mj-column / mj-button / mj-image) compile to table-based responsive HTML. Industry default for portable templates. |
| React components | React Email (resend/react-email, MIT) | React/TypeScript product team; templates live in the app repo; want typed props + local preview + the same component model as the product. |
| Tailwind utility-first | Maizzle (maizzle/framework, MIT) | Team already on Tailwind; wants utility classes in email with automatic inlining, important-pruning, and minification. |

Cross-paradigm methodology (applies to all three, extends rules.md Templates):
- Base layout component + reusable partials (header/footer/button) so brand changes are one edit.
- Always emit a hand-written plain-text part alongside HTML (multipart) - the compiler gives you HTML, not the text part; write it.
- Dark-mode via prefers-color-scheme media queries; test in Apple Mail + Outlook + Gmail (MJML handles Outlook tables; React-Email/Maizzle need explicit Outlook checks).
- Inline CSS before send (MJML and Maizzle inline automatically; React-Email render inlines). Outlook ignores most non-inline CSS.
- Run the rendered output through the deliverability harness (section 2) as the pre-ship spam-score check, not just a render test.

## Sources
github.com/knadh/listmonk (Listmonk, AGPL-3.0, v6.1.0 2026-03-29), github.com/mautic/mautic (Mautic, GPL-3.0), github.com/happyDomain/happydeliver (happyDeliver, AGPL-3.0), github.com/mjmlio/mjml (MJML, MIT, 2026-06-12), github.com/resend/react-email (React Email, MIT), github.com/maizzle/framework (Maizzle, MIT, v6.0.0-rc.23 2026-05-24). See TOP5-CANDIDATES.md for full Gate-0 trail and verification notes.
