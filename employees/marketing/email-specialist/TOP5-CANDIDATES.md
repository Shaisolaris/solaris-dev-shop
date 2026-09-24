# TOP-5 verified 2026 sources - email/lifecycle marketing tooling

Research pass 2026-06-13 (web). Scope: ESP platforms, deliverability tooling, template/MJML, automation, segmentation. Gate-0 run against ALL existing files (SKILL.md, rules.md, email-marketing-depth-2026.md, plugin.json) via grep on actual content. The prior depth pass (email-marketing-depth-2026.md) covers strategy/methodology (post-MPP KPIs, lifecycle flow priority, segmentation multiplier, newsletter cadence). These five are TOOLING/INFRASTRUCTURE, no content overlap with that pass.

Verification: GitHub repo metadata cross-checked via GitHub API + web. Unauthenticated GitHub API was rate-limiting during the pass; star counts marked (web) come from GitHub HTML/search, approximate to the stated date.

| # | Source | URL | Stars | License | Last commit/release | Maintainer | What it adds | Gate-0 verdict | Tag |
|---|--------|-----|-------|---------|---------------------|-----------|--------------|----------------|-----|
| 1 | knadh/listmonk | https://github.com/knadh/listmonk | ~21.4k (web) | AGPL-3.0 (FLAG) | v6.1.0, 2026-03-29 | Kailash Nadh (knadh) | Self-hosted single-binary newsletter + mailing-list + transactional manager (Go + PostgreSQL, millions of subscribers/server, Go-template content, single+double opt-in, built-in bounce/click analytics). Fills the total absence of an owned-list / self-hosted ESP option (current ESP table is 100% SaaS). | NOT present (0 hits). New. | ABSORB (methodology + self-host note; AGPL = no code bundled) |
| 2 | happyDomain/happydeliver | https://github.com/happyDomain/happydeliver | 50+ notable maintainer (happyDomain DNS team) | AGPL-3.0 (FLAG) | active, ~2026-05 | happyDomain | Self-hosted deliverability test harness: scores SPF/DKIM/DMARC/BIMI/ARC + SpamAssassin/rspamd, DNS, blocklist, content quality. REST API + built-in LMTP server for MTA integration; all-in-one Docker (Postfix + authentication_milter + SpamAssassin). Operationalizes the "mail-tester >=8" gate as a self-hostable, scriptable check. | NOT present (0 hits; only mail-tester.com/MXToolbox referenced). New. | ABSORB (methodology + self-host note; AGPL) |
| 3 | mjmlio/mjml | https://github.com/mjmlio/mjml | 18099 | MIT | pushed 2026-06-12 | mjmlio (Mailjet origin) | The MJML responsive-email markup language + compiler: semantic component library (mj-section/mj-column/mj-button), Outlook-safe table output, deterministic responsive HTML. rules.md only NAMES MJML; no component model / anatomy methodology exists. | Name-present in rules.md Templates + tags; deep methodology absent (content-duplicate at name level only). | METHODOLOGY (deepen template-anatomy layer; permissive) |
| 4 | maizzle/framework | https://github.com/maizzle/framework | ~1.5k (web) | MIT | v6.0.0-rc.23, 2026-05-24 | Cosmin Popovici / Maizzle | Tailwind-CSS-for-email framework (utility-first, automatic CSS inlining, important-pruning, minification, responsive presets). A distinct template paradigm vs MJML/React-Email for Tailwind teams. | NOT present (0 hits). New. | CONNECT (named option in template paradigms + methodology note) |
| 5 | mautic/mautic | https://github.com/mautic/mautic | ~9.2k (web) | GPL-3.0 (FLAG) | v7.x (2026); 5.2/6.0 security EOL lines | Mautic / Acquia community | Full self-hosted marketing-automation platform (PHP): visual campaign builder, lead scoring, multi-channel, dynamic segments, landing pages. The open-source HubSpot alternative, the automation+segmentation engine above Listmonk. | NOT present (0 hits). New. | CONNECT (methodology + self-host note; GPL = no code bundled) |

## Runners-up (considered, not selected)
- resend/react-email (19290 stars, MIT, 2026-06-02): already absorbed via alirezarezvani email-template-builder and named in rules.md Templates; folding MJML deepening covers the same template-anatomy need without duplicating an existing credit.
- pentacent/keila (~145 stars, AGPL-3.0, 2026-04-23): privacy-first Elixir ESP, below the 100-star bar; Listmonk covers the self-hosted-newsletter slot more strongly.
- mjmlio/email-templates (MIT): useful starter gallery, not methodology.

## License flags (carry into ledger)
- AGPL-3.0: listmonk, happydeliver, keila -> methodology + self-host note ONLY, never bundle code.
- GPL-3.0: mautic -> methodology + self-host note ONLY, never bundle code.
- MIT (safe): mjml, maizzle, react-email.

## Net absorption decision
Deepen ONE new reference file email-infrastructure-tooling-2026.md: the self-hosted ESP spectrum (Listmonk -> Mautic), the self-hostable deliverability test harness (happyDeliver, operationalizing the existing mail-tester gate), and the template-paradigm matrix (MJML vs React-Email vs Maizzle). Methodology only; AGPL/GPL get explicit self-host notes and zero bundled code.
