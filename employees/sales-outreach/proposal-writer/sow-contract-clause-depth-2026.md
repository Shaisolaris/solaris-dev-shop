# SOW + contract clause depth + e-sign workflow - depth reference

METHODOLOGY absorption (2026-06-13). Source: github.com/borghei/Claude-Skills business-growth/contract-and-proposal-writer (262 stars; license NOASSERTION at repo / "MIT + Commons Clause" in skill metadata = FLAG). Methodology only - the repo's Python scripts (contract_clause_checker.py, proposal_cost_estimator.py, contract_comparison_analyzer.py) are NOT bundled; Commons Clause forbids reselling that software, so if Solaris ever wants the tooling it must self-host the upstream repo, not redistribute. Gate-0 PASS: the employee owned proposal craft (3-act, win themes, opening-line algorithm), pricing (floor/target/ceiling), and flag analysis - but had no contract-clause depth, no SOW deliverables matrix, no jurisdiction-aware library, and no GDPR DPA trigger. Heavy redlining/negotiation remains Legal Advisor's domain; this is the document-STRUCTURE layer a proposal writer needs to hand off clean.

## 1. Requirements intake before drafting any SOW/contract
Gather first (missing answer = `[REQUIRED - description]`, never a silent blank): document type (proposal/SOW/NDA/MSA) - jurisdiction (US-Delaware / EU / UK / DACH) - engagement model (fixed/hourly/retainer/rev-share) - legal party names + registered addresses - 1-3 sentence scope - total value or rate (drives payment terms + liability cap) - timeline + milestones - special requirements (IP assignment, white-label, subcontractors, non-compete) - personal data involved? (triggers a GDPR DPA in EU/DACH).

## 2. SOW structure (deliverables matrix + acceptance criteria)
A SOW attaches to an MSA or stands alone. Required sections: scope statement - **deliverables matrix** (each row: deliverable / description / acceptance criteria / due date / owner) - explicit out-of-scope list - milestones tied to payment - acceptance process (who signs off, in how many business days, what "accepted" means) - change-order clause (any scope add = written change order with re-price, never silent absorption) - assumptions + dependencies. Acceptance criteria must be objective and testable, not "client is satisfied".

## 3. Jurisdiction-aware clause library (pick by the client's governing law)
- **US (Delaware default):** work-made-for-hire + IP assignment on full payment; limitation-of-liability capped at fees paid; Delaware governing law + venue.
- **EU / DACH (German law):** GDPR Art. 28 Data Processing Addendum is MANDATORY when personal data is processed (controller/processor roles, sub-processor list, SCCs for transfers); moral-rights nuance (author rights are not fully assignable under German law - license instead); statutory warranty periods.
- **UK:** post-Brexit data-transfer wording (UK GDPR + IDTA), governing law England & Wales.
- Universal: payment terms matched to engagement model, IP transfers ONLY on payment, mutual vs one-way NDA chosen deliberately, termination-for-convenience + termination-for-cause split.

## 4. Pre-send review checklist (gate before any contract/SOW leaves)
- [ ] All `[BRACKETED]` placeholders filled (no blanks)
- [ ] One jurisdiction selected and consistent throughout
- [ ] Payment terms match the engagement model + a liability cap is present
- [ ] IP clause matches jurisdiction (assignment vs license; on-payment trigger)
- [ ] GDPR DPA attached if personal data is in scope (EU/UK/DACH)
- [ ] Deliverables matrix has objective acceptance criteria
- [ ] Change-order clause present
- [ ] Over $50K or complex IP/equity/regulatory -> route to Legal Advisor before send (template is a starting point, not counsel)

## 5. E-sign workflow (operationalizes the existing CONNECT note in rules.md)
Once the doc passes the checklist: (1) lock the final (PDF/DOCX), (2) send via the e-signature connector (rules.md "Document delivery + e-signature connectors") with signer order set (client first or countersign as policy), (3) track open/view, (4) on full execution store the signed copy + start the delivery clock and hand to Customer Success / Delivery Lead with the SOW deliverables matrix as the source of truth. Never start work on a verbal yes before signature on engagements with real scope/value.

## Sources
- github.com/borghei/Claude-Skills business-growth/contract-and-proposal-writer/SKILL.md + commercial-policy/references/contract-and-commercial-guardrails.md (methodology; scripts left upstream; Commons Clause = self-host the tooling, do not redistribute).
