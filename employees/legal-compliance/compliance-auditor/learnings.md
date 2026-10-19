# Compliance Auditor - Learnings (Pending)

## Pending observations
- **2026-10-19 - G37 privacy inventory**: the field most likely to be missed is one the metric pipeline ignores (a birth date column that G13 never declared still sits in the file). A deletion request also met a financial retention hold on two order rows. *Proposed rule: inventory the file header, not the contract, and route deletion-versus-retention conflicts to a qualified reviewer.* Note for review: HARD NUMBERS says a 30-day DSAR clock, while GDPR Art. 12(3) says one month (extendable); the tool takes clocks from configuration.
- **2026-04-25 - Clean rebuild from msitarzewski compliance-auditor**: Substance-over-checkbox + automated evidence + common-controls cross-mapping are the consistent professional principles.
- **2026-04-25 - Auditor mindset**: Think like the auditor, sample like the auditor, ANY sample must pass.

- **2026-06-13 (depth) - AI governance framework added (EU AI Act + ISO/IEC 42001)** - the employee had full SOC2/ISO27001/GDPR/HIPAA/PCI coverage but ZERO AI-governance, a real 2026 gap for an AI fleet. EU AI Act enforcement starts Aug 2 2026 (fines to EUR 35M/7%); ISO 42001 is the certifiable AIMS that maps to AI Act Arts 9-15 and is now bundled in enterprise vendor questionnaires. Added to the common-controls cross-map.
- V5-ORDER-04: removed the coding agent-is provider lock-in; employee is provider-neutral.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
## Sources

- Upstream: EU AI Act (license not stated: EU regulation); ISO/IEC 42001:2023 (license not stated: ISO); getprobo/probo (ISC (permissive)); strongdm/comply (Apache-2.0); Comp AI (FLAG: AGPL (copyleft if served))
- What was used: methodology absorbed: EU AI Act, ISO/IEC 42001:2023; connected as external reference: getprobo/probo, strongdm/comply, Comp AI
- License notes: Comp AI: FLAG: AGPL (copyleft if served)
