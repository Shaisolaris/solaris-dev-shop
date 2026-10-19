# CFO - Learnings (Pending)

## Pending observations
- **2026-04-24 - Clean DAP rebuild**: Tier-1-first reporting discipline (ARR / Runway / NDR before everything) prevents board-deck dilution. Codified.
- **2026-04-24 - Clean DAP rebuild**: Variance-with-forward-impact is the single biggest FP&A craft upgrade - past-only commentary is useless.
- **2026-04-24 - Clean DAP rebuild**: Deferred revenue from annual billing is the most under-utilized cash-extension lever in early SaaS.
- V5-ORDER-04: restored `decision-quality-protocol-2026.md` path on the RUNTIME HARDENING decision-quality line.
- **2026-10-19 - G14 revenue versus cash**: a cash-basis sheet that sums payment rows as revenue and adds currencies together reports a "revenue" figure that is neither revenue nor cash, double-counts re-sent rows and hides overpayments inside AR. *Proposed rule: reconcile per currency with an AR roll-forward and revenue-to-cash bridge that close to the cent before quoting either number; unapplied cash, undelivered invoices and late rows are listed, not netted.*
- **2026-10-19 - G14 r2 negative transactions**: a book where refunds exceed the payments and credit notes exceed the invoice still closes to the cent and showed negative revenue with exit 0, because every control only checks that the arithmetic adds up. *Proposed rule: a reconciliation that closes is not a clean one; challenge any reversal larger than what it reverses and name it as an exception next to the number.*

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |

## 2026-05-13 - Absorbed anthropics/financial-services-plugins (scout 2026-05-11)
- 10 named workflow agents: pitch-builder, kyc-screener, month-end-closer, model-builder, market-researcher, valuation-reviewer, gl-reconciler, statement-auditor, earnings-reviewer, meeting-preparer
- Official Anthropic source, Apache 2.0, 14.2K stars
- Security verification: Tier 1 PASS (official org). CLI tiers + sandbox pending Mac.
## Sources

- Upstream: EveryInc/charlie-cfo-skill (MIT); alirezarezvani/the coding agent-skills (MIT); OctagonAI/skills (license not stated: (varies))
- What was used: methodology absorbed: EveryInc/charlie-cfo-skill, alirezarezvani/the coding agent-skills, OctagonAI/skills; rejected (not used): borghei/the coding agent-skills, Anthropic finance team's 150 internal skills
- License notes: borghei/the coding agent-skills: NOASSERTION (FLAG)
