# Decision quality protocol (2026)

**Status:** methodology absorbed into leadership + delivery operations  
**Issue:** skill-8qr  
**Evaluation slice:** meta/skill-rotation/evaluations/20260724/leadership-operations/  
**Scope:** CEO, CTO, CFO, COO, business-analyst, delivery-lead  
**License:** MIT (Solaris in-house + public decision-science patterns)  
**Pin:** document_version decision-quality-protocol-2026  

Synthetic / professional only. No real company financials, board secrets, or personal data.

## Purpose

Every material recommendation from leadership and delivery capabilities must be
evidence-grounded and authority-bounded. Outputs distinguish what is known,
what is assumed, what is optional, what is risky, who owns the call, and what
evidence is still required before action.

## Mandatory decision record fields

When a deliverable includes a recommendation or decision, emit all of:

| Field | Meaning |
|-------|---------|
| **facts** | Dated, sourced observations (or UNVERIFIED/STALE if not) |
| **assumptions** | Explicit beliefs that could be wrong; each has a test |
| **options** | At least two viable paths (including status quo when relevant) |
| **risk** | Likelihood x impact, owners, and mitigations |
| **dissent** | Best counter-argument or minority view (never silent monoculture) |
| **decision_owner** | Named role with authority level (L0 draft / L1 operator / L2 budget / L3 exec) |
| **required_evidence** | What must be true or collected before commit |

## Decision spine (DECIDE + evidence)

1. **Define** the decision and cost of delay  
2. **Establish** criteria and constraints  
3. **Consider** options with facts vs assumptions labeled  
4. **Identify** preferred option + dissent  
5. **Develop** action plan with decision_owner and required_evidence  
6. **Evaluate** after commit (metric + review date)

## Authority and escalation

- Skills operate at **L0 (draft-only)** unless a sealed order raises authority.  
- Spend, fund movement, contract signature, legal filing, production deploy,
  and external send/publish require human authority via `APPROVAL_PREVIEW`.  
- Financial and legal-adjacent outputs remain **bounded**: model, analyze,
  recommend - never execute corporate, investment, or legal acts.  
- High-stakes attempts without authority: fail closed with one actionable cause
  (`PERMISSION_DENIED` or `SAFETY_VIOLATION`); never fabricate success.

## Budget and milestone framing

- **Budget** proposals name envelope, assumptions, residual risk, and authority needed.  
- **Milestones** name acceptance criteria, dependencies, RAID items, and who
  may declare done (never tool silence).  

## Rollback

- Failed or revoked authority: retain drafts; do not execute queued external actions.  
- Capability rollback: restore prior `identity.version` from git for the employee path.  
- Bad claim after draft: amend claim ledger; do not silent-edit already-approved
  customer-facing artifacts without a new preview.

## Provenance rules

- Prefer primary, pinned, currently maintained, clearly licensed sources.  
- Map each adopted pattern to a measurable gain (decision clarity, cycle time,
  risk visibility, or authority correctness).  
- Reject AGPL code copy, proprietary-only playbooks without license clarity,
  and stale unmaintained sources for absorption.

## Gate

Emit `Gate: passed` only when:
- decision record fields are complete for material recommendations  
- no autonomous external action was taken  
- material claims are sourced or marked UNVERIFIED/STALE  
- high-stakes paths either previewed for human authority or blocked  
