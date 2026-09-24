# Proposal Writer - TOP-5 verified 2026 source scan (2026-06-13)

Domain: proposals / SOW / MSA / NDA / RFP / pricing / e-sign.

| # | Source | Stars | License | Last commit | Maintainer | What it adds | Gate-0 | Tag |
|---|--------|-------|---------|-------------|------------|--------------|--------|-----|
| 1 | github.com/borghei/Claude-Skills (business-growth/contract-and-proposal-writer + commercial-policy guardrails) | 262 | NOASSERTION / "MIT + Commons Clause" (FLAG) | 2026-05-27 | borghei | SOW deliverables-matrix + acceptance criteria, jurisdiction clause library (US-DE/EU/UK/DACH), MSA<-SOW attachment framework, GDPR Art.28 DPA trigger, contract review checklist, change-order clauses | PASS - employee owned proposal craft + pricing + flag analysis but had NO contract-clause depth, no SOW deliverables matrix, no jurisdiction library, no DPA trigger | METHODOLOGY (self-host note; Commons Clause = no reselling the tooling) |
| 2 | github.com/msitarzewski/agency-agents (sales-proposal-strategist) | 112,861 | MIT | 2026-06-07 | msitarzewski | win-theme + exec-summary structure | CONTENT-DUPLICATE (already absorbed; cited in SKILL.md) | (absorbed) |
| 3 | github.com/alirezarezvani/claude-skills (proposal/pricing) | 17,992 | MIT | 2026-06-12 | alirezarezvani | pricing frameworks | CONTENT-DUPLICATE (overlaps inline pricing playbook) | (absorbed/overlap) |
| 4 | DeepRFP / CLEATUS (commercial GovCon RFP tools) | n/a | proprietary | n/a | vendors | compliance-matrix automation | NOT OSS - proprietary SaaS, cannot absorb | REJECT |
| 5 | github topics: proposal-generation (assorted) | mixed/<100 | mixed | mixed | various | template generators | mostly <100 stars or thin; nothing clears bar | REJECT |

## Verdict
One clear win: **borghei/Claude-Skills contract-and-proposal-writer (262 stars)** adds the contract/SOW LEGAL-STRUCTURE layer the employee lacked - SOW deliverables matrix + acceptance criteria, a US-DE/EU/UK/DACH jurisdiction clause library, the MSA<-SOW attachment framework, the GDPR DPA trigger, and a pre-send review checklist. License is NOASSERTION at repo level / "MIT + Commons Clause" in the skill metadata - the Commons Clause restricts SELLING the software, not the methodology, so this is absorbed as METHODOLOGY ONLY with a self-host note; the repo's .py scripts (contract_clause_checker, proposal_cost_estimator) are NOT bundled. Heavy contract redlining/negotiation stays with Legal Advisor (boundary preserved). Commercial RFP SaaS (DeepRFP, CLEATUS) are proprietary, not absorbable.
