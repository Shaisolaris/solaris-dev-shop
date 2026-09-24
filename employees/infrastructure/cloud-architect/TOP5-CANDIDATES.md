# Cloud Architect - Top-5 verified 2026 source candidates

Research pass 2026-06-13. All repos verified live via GitHub (HTML; API rate-limited). Bar: established/safe, 100+ stars OR notable maintainer (50+), permissive license preferred (GPL/AGPL/NOASSERTION flagged), commit/release within ~6 months. Gate-0 = grep of existing SKILL.md + rules.md for the actual content (present? content-duplicate?).

## Summary table

| # | Repo | Stars | License | Last release/commit | Maintainer | What it adds (net-new) | Gate-0 | Tag |
|---|---|---|---|---|---|---|---|---|
| 1 | [awslabs/landing-zone-accelerator-on-aws](https://github.com/awslabs/landing-zone-accelerator-on-aws) | 804 | Apache-2.0 | v1.15.5, 2026-06-02 | awslabs (AWS-official) | Control Tower + Account Factory reference impl; 35+ AWS services as CDK; sample-configurations per compliance regime; CentralLogsBucket CMK pattern | PASS - no Control Tower / account-factory / accelerator content in either file | METHODOLOGY + CONNECT |
| 2 | [infracost/infracost](https://github.com/infracost/infracost) | 12.4k | Apache-2.0 | v0.10.44, 2026-04-06 | Infracost | Shift-left cost: cost diff + FinOps policy check on PR BEFORE deploy; price-lookup; agent-skills (iac-generation/scan/price-lookup); 1,100+ resources AWS/Azure/GCP; tagging+budget guardrails in IaC | PASS - employee cost doctrine is 100% post-hoc audit (CLI reads live spend); zero pre-deploy estimation | ABSORB (methodology) + CONNECT |
| 3 | [aws-samples/sample-well-architected-skills-and-steering](https://github.com/aws-samples/sample-well-architected-skills-and-steering) | 6 | MIT-0 | 8 commits, 2026 (recent) | aws-samples (AWS-official; notable-maintainer exception, under 100-star bar) | AWS-native 6 WAF pillars incl. Sustainability (employee has none); 8 review-skill playbooks (wa-review, reliability/SPOF, security-assessment, cost-optimization-audit, performance-efficiency, sustainability, migration-readiness 7Rs, ADR-with-pillar-impact) | PASS - employee reviews against 8 ALZ design areas, NOT 6 WAF pillars; no Sustainability pillar; no SPOF playbook | METHODOLOGY |
| 4 | [openops-cloud/openops](https://github.com/openops-cloud/openops) | 1.0k | Apache-2.0 | 0.6.23, 2026-03-18 | OpenOps | Pre-built FinOps workflow library (allocation, unit economics, anomaly mgmt, safe de-provisioning); human-in-the-loop approval gates; snooze/dismiss/false-positive opportunity lifecycle; consolidates findings across visibility tools | PASS - no HITL approval, no opportunity-lifecycle, no anomaly-workflow content beyond one-line "anomaly alerts" | METHODOLOGY |
| 5 | [FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec) | 283 | FLAG: spec license (Community Spec / CC-BY family, non-OSI; not a code license) | v1.3, 2025-12-08 | FinOps Foundation | Vendor-neutral billing-data schema (BilledCost/EffectiveCost/ListCost/ContractedCost, ChargeCategory, CommitmentDiscount columns); v1.3 adds dedicated contract-commitment dataset; enables cross-cloud cost merge + comparable reporting | PASS - employee has no normalized cost schema; reports are raw per-service spend, not comparable cross-provider | METHODOLOGY (self-host: spec only, cite + reference, no bundled spec text) |

## Notes per candidate

**1. LZA (awslabs).** AWS-official multi-account foundation accelerator. Apache-2.0, actively released (v1.15.5 Jun 2026, 1,972 commits, 56 releases). Directly extends the existing AWS Organizations + SCP + log-archive doctrine (rules.md §3) with the canonical reference implementation and Control Tower pairing. Architect does not write the CDK (devops-engineer does), so this is a design-reference + CONNECT, absorbed as methodology into rules.md §3.

**2. Infracost.** 12.4k stars, dominant shift-left cost tool. Net-new and high-value: the entire cost-architecture (rules.md §6) is reactive (audits spend that already happened). Infracost moves cost into the design/PR loop (cost diff on every IaC change, price-lookup during design, policy enforcement). First-party agent-skills for Claude Code. ABSORB the doctrine (pre-deploy cost gate), CONNECT the tool.

**3. WA skills & steering (aws-samples).** Below 100-star bar (6 stars) but qualifies on the notable-maintainer exception (AWS-official aws-samples, MIT-0). Single most on-domain net-new methodology: WARs currently run against the 8 ALZ design areas (Azure-flavored), with no AWS-native 6-pillar framework and no Sustainability pillar. The 8 standalone playbooks (esp. reliability SPOF-elimination and ADR-with-pillar-impact) sharpen Workflow 4. METHODOLOGY only.

**4. OpenOps.** 1k stars, Apache-2.0, active. Adds the operational layer the bill-cut workflow lacks: a HITL approval gate before any de-provisioning, an opportunity lifecycle (approve/dismiss/false-positive/snooze), and a pre-built workflow taxonomy. Maps onto rules.md §6 bill-cut step 3 ("validate with owners") and the governance cadence. METHODOLOGY only.

**5. FOCUS_Spec.** 283 stars, FinOps Foundation (industry standard, ratified v1.3 Dec 2025). FLAG: licensed under a specification license (Community Specification License / CC-BY family), not an OSI code license; treat as methodology + self-host note, cite the spec and reference its column model, never bundle spec text. Net-new: a vendor-neutral cost-data vocabulary so reports and cross-cloud comparisons are normalized rather than raw per-provider line items.

## License flags
- **FOCUS_Spec**: non-OSI spec license (CC-BY family). Methodology + self-host note only; do not vendor the spec text.
- All others: Apache-2.0 or MIT-0 (permissive, safe).
- No GPL/AGPL among the five.
