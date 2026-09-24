# Probo GRC Workflow Patterns (ABSORB) + Comp AI (CONNECT)

Absorbed 2026-06-13 from getprobo/probo (**ISC license - permissive, self-hostable**; note: the 2026-06 gates doc listed it as MIT - corrected to ISC after reading the repo). Probo is a self-hostable GRC platform with 270+ MCP tools. The compliance-auditor already owns the framework catalogs (SOC 2 TSC, ISO 27001 Annex A, GDPR), the evidence-as-scheduled-tickets program, vendor assessment, and compliance-as-code (trestle/OSCAL). This file lifts only the **net-new GRC workflow patterns** Probo adds on top - Gate-0 confirmed these were not already in the employee's content.

## Net-new patterns lifted

### 1. Statement of Applicability (SoA) as a first-class artifact
- For ISO 27001 (and by analogy any control framework), maintain an explicit **SoA**: every control marked applicable / not-applicable **with justification**, mapped to its implementation state. The auditor previously built a gap matrix; the SoA is the auditor-facing companion that records *why a control is in or out of scope*. Auditors ask for the SoA directly - produce it, don't reconstruct it at fieldwork.

### 2. Inherent vs residual risk scoring + treatment strategy
- Score each risk **twice**: inherent (before controls) and residual (after controls). The delta is the control's demonstrated value.
- Assign an explicit **treatment strategy** per risk: mitigate / accept / avoid / transfer. "Accept" requires a named owner sign-off. This makes the risk register defensible: every risk has a decision and an owner, not just a number.

### 3. Access-review campaigns
- Run periodic **access reviews as campaigns**: per-entry decisions (keep / revoke / modify) across SaaS, cloud infra, and source-code access, with the decisions logged as evidence. This is a recurring SOC 2 CC6 / ISO A.5.18 control the prior evidence program named but didn't operationalize as a campaign with per-entry sign-off.

### 4. Electronic sign-off with approval quorums
- Policy and document approval uses **versioned docs + approval quorums + electronic signature**, producing an immutable approval chain. Distinct from the e-sign legal-advisor owns (contracts): this is *internal control-document* sign-off (policies, procedures, risk acceptances) and it IS audit evidence. A policy without a recorded approval chain is a finding.

### 5. Automated vendor website risk assessment
- Augment the existing VTR questionnaire loop with **automated vendor website/risk scanning** as a first-pass triage before sending the full questionnaire - triage vendors by automated signal, reserve the deep questionnaire for material/high-risk vendors.

## What was NOT lifted (already covered - Gate 0)
- Framework catalogs (SOC 2 TSC, ISO Annex A, GDPR) - already in rules.md.
- Evidence collection as scheduled tickets - already the employee's evidence program.
- DPIA/TIA, DPA/BAA tracking, subprocessor inventory - already in vendor/GDPR sections.
- Compliance-as-code - already covered via trestle/OSCAL.

## CONNECT - host installs (auto-deploy does NOT install external MCP servers)
- **Probo** (ISC, self-host): clone with submodules, `make stack-up && make build`, run `bin/probod` (web console at :8080); its MCP exposes 270+ tools, plus `prb` CLI and a GraphQL API. Use as the live GRC system-of-record when a client wants a self-hosted Vanta/Drata alternative. The patterns above apply whether or not Probo itself is installed.
- **Comp AI** (~1.6k stars, **AGPL - self-host/connect fine, copyleft if served**): open-source Vanta/Drata-style continuous-compliance automation. CONNECT as the automated-evidence + monitoring platform for clients who want continuous control monitoring rather than point-in-time readiness. Self-host; respect AGPL if offered as a service.
