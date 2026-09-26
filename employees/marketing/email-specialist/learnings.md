# Email Specialist - Learnings (Pending)

## Pending observations
- **2026-04-25 - Clean rebuild from alirezarezvani email + cold-email + template-builder**: Subdomain isolation (marketing vs transactional) is the most-violated deliverability rule that has the largest impact.
- **2026-04-25 - DMARC enforcement** (quarantine or reject, not none) is non-negotiable post-2024 (Gmail/Yahoo bulk sender rules).
- **2026-06-13 - Self-hosting does not relax deliverability**: choosing Listmonk/Mautic moves warm-up, bounce processing, and blocklist response onto Solaris. The mail-tester gate should be automated via a self-hostable harness (happyDeliver) so the launch queue enforces it, not a human.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| 2026-06-13 | Deliverability harness gate in launch protocol + self-hosted ESP option | rules.md Launch step 3, ESP decision rule; email-infrastructure-tooling-2026.md |
| 2026-06-13 | Small-task/prototype lane (skip full audit, keep minimum bar) | rules.md |
## Sources

- Upstream: knadh/listmonk (license not stated: ~21.4k (web)); happyDomain/happydeliver (license not stated: 50+ notable maintainer (happyDomain DNS team)); mjmlio/mjml (license not stated: 18099); maizzle/framework (license not stated: ~1.5k (web)); mautic/mautic (license not stated: ~9.2k (web))
- What was used: noted: knadh/listmonk, happyDomain/happydeliver, maizzle/framework, mautic/mautic; methodology only: mjmlio/mjml
- License notes: licenses not recorded in scan for: knadh/listmonk, happyDomain/happydeliver, mjmlio/mjml, maizzle/framework, mautic/mautic - verify before reuse; no code vendored
