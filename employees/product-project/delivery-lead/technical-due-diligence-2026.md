# Delivery Lead - Technical Due Diligence / Project Audit rubric (2026-06-20, methodology only, nothing bundled)

The ELITE bar for a "Technical PM Analysis" / project-audit gig: not a vibe-check and not a bug list, but the rigorous, evidence-cited assessment a top fractional CTO produces before a client buys, funds, rebuilds, or rescues a build. It answers ONE question with receipts: **what will sink this build, how likely, how bad, and what does it cost to de-risk.** Every finding has a severity, an owner, an effort estimate, and an evidence pointer (file/line, config, metric, or a named gap). Opinion without a pointer is not a finding.

This is delivery-lead's analysis discipline. It SITS ON TOP of the takeover chain: the codebase-onboarding pack (technical-writer Stage 1) and the code-reviewer audit (Stage 2) feed it raw evidence; this rubric turns that evidence into a board-ready verdict with a risk-scored register and a 100-day de-risk plan. Delivery-lead orchestrates and synthesizes; it does not run the scanners itself. Methodology only - no tools installed or run.

---

## The 8 domains (score each; this is the spine of the report)

Score every domain RED / AMBER / GREEN with an evidence pointer and a one-line "what would sink us here". Drawn from the 2026 fractional-CTO / M&A technical-due-diligence standard.

1. **Code quality + architecture** - SOLID adherence, modularity, coupling/cohesion, the dependency graph (circular deps, god-modules, blast radius from the technical-writer onboarding map). Automated first pass (SonarQube-class: aim test-debt ratio <5%), manual review on high-churn / core-business-logic modules. Architecture FIT: does the shape (monolith / modular / microservices / serverless) match the load and the team size, or is it cargo-culted?
2. **Security + compliance** - dependency CVEs (Stage-2 dep audit), secrets in repo, over-privileged IAM, OWASP Top 10 on the public surface, encryption at rest/in transit, and regulatory fit (GDPR / HIPAA / SOC2 / PCI-DSS as applicable). Severity-classified Critical/High/Med/Low with remediation timelines.
3. **Cloud infra + DevOps maturity** - IaC quality, CI/CD (deploy frequency, manual gates, automated tests + security scans in the pipeline), environment parity (staging mirrors prod), rollback capability, cloud cost governance (tagging, budget alerts - uncontrolled spend is a red flag).
4. **Data + database** - schema design, the slow-query reality (EXPLAIN on the top queries against prod-scale data, not a toy DB), indexing, scaling pattern (read replicas / sharding / connection pooling), backup AND restore verification, data-integrity risks.
5. **API design + integration** - versioning + deprecation policy (absence = chaos incoming), auth (OAuth2 / keys), rate limiting, contract clarity (OpenAPI), resilience + error handling of third-party integrations (payment, auth, AI/ML providers).
6. **Performance + load** - SLAs defined? p95/p99 latency, throughput ceiling, behaviour under peak vs typical load, tested at production-scale data. Unscalable = a hard ceiling on business growth.
7. **Tech stack + dependencies** - language/framework appropriateness, version currency (a "no dependency older than 18 months without a documented exception" policy), license compliance (copyleft/GPL in a commercial product is a flag - route to legal), supply-chain risk.
8. **Testing + QA maturity** - coverage on CRITICAL logic (<70-80% on core = every release is a gamble), the test-pyramid shape (broad unit base, thin E2E top), tests as a CI quality gate, test-data strategy (production data in tests = a security finding).

Plus a 9th, non-code domain that sinks more builds than any single bug:

9. **Delivery + team risk (the PM lens)** - key-person risk (a capability map: critical functions x who-can-do-them, single points of failure), bus factor, tribal knowledge vs documentation, schedule realism, scope discipline, and whether GitHub state matches what the team claims is done (GitHub is truth). This is where the technical-PM analysis differs from a pure code audit.

---

## Risk scoring (RAID + a 2026 risk matrix, not a P x I afterthought)

Findings go into a RAID-structured register, each scored on a risk matrix and translated into money and time:

- **RAID** - separate the four: **R**isks (might happen), **A**ssumptions (taken on faith, untested - each one is a latent risk), **I**ssues (already true and hurting now), **D**ependencies (external/internal things the build relies on, incl. key people and third-party vendors). Most amateur audits log only Issues; the elite move is surfacing the untested Assumptions and the hidden Dependencies.
- **Score each: Likelihood x Impact** on a 5x5 matrix -> Low / Medium / High / Critical. 2026 practitioner standard: extend the matrix to cover AI, third-party, and ICT/supply-chain risk, and refresh it (quarterly, or continuous for high-velocity risks) rather than scoring once and filing it.
- **Schedule risk specifically**: 3-point PERT estimates (optimistic/likely/pessimistic) on the remaining critical path, a P50/P80 completion band (Monte-Carlo framing), and the explicit buffer. A single-point "it'll be done in 6 weeks" is itself a red-flag finding.
- **Translate to the deal**: every Critical/High finding gets an effort-to-remediate (time + cost) so the verdict can adjust valuation, set pre-close conditions, or scope a rescue. "Quantify and prioritize - not all red flags are equal" is the difference between a checklist and a strategic instrument.

---

## The deliverable shape (board-ready, white-label clean)

1. **SCQA executive summary, <=500 words** - Situation / Complication / Question / Answer. The verdict in one screen: overall RED/AMBER/GREEN, the 3-5 things that would sink this build, and the headline de-risk cost. A non-technical buyer/board reads only this.
2. **Domain scorecard** - the 9 domains, each RED/AMBER/GREEN with evidence pointer + "what would sink us".
3. **RAID risk register** - every finding: ID, type (R/A/I/D), description, evidence pointer, likelihood x impact -> score, owner, remediation effort (time + cost).
4. **GO / NO-GO / PIVOT gate** - an explicit, evidence-cited recommendation (not "it depends"). Blocking findings vs manageable findings split out.
5. **100-day de-risk plan** - prioritized: patch the Critical security/architecture findings first, then the high-likelihood schedule/delivery risks. This is the bridge from analysis to action - it flows into normal project setup (ClickUp from the register, milestones around fix batches), white-label client summary.

---

## Discipline rules (what makes it elite, not a generated checklist)

- **Evidence or it is not a finding.** Every claim points to a file/line, a config, a metric, a query plan, or a NAMED gap (TODO: could not access X). Zero-hallucination applied to audit: never assert a vulnerability/bottleneck you did not observe.
- **Onboard before you audit.** Run the technical-writer onboarding map first; auditing on Day 1 before you understand the stack produces hallucinated criticism of idiomatic patterns and findings that miss the real problem areas (the takeover anti-patterns rule).
- **Architecture FIT, not architecture fashion.** A monolith for a 3-person team is not a finding; a 40-service mesh for a 3-person team is. Score the shape against the load and the team, not against a trend.
- **Separate bug-fixes from major-version migrations.** A framework/runtime upgrade is a different risk profile - it goes to migration-architect (takeover Stage 3), never into the bug backlog or the same sprint as security fixes.
- **Quantify, prioritize, translate to the deal.** A finding without a severity, an effort, and a money/time impact is half-done.
- **White-label + information wall hold.** The audit report is a client-facing deliverable: "I", no team/tool references; no billing rates, margins, or cross-role figures leak into it. Internal RAID notes and the client verdict are different surfaces.

---

## Boundary (who does what in a Technical PM Analysis)

- **delivery-lead** owns the ANALYSIS: synthesizes the evidence into the 9-domain scorecard, the RAID-scored register, the GO/NO-GO gate, and the 100-day plan. Orchestrates the chain; does not run scanners.
- **technical-writer** produces the onboarding/architecture MAP (Stage 1) that feeds domain 1 - neutral facts, no grading.
- **code-reviewer** runs the 7-phase + dependency audit (Stage 2) that feeds domains 1-8 with severity-tagged findings.
- **migration-architect** owns major-version/framework migration plans (Stage 3) for anything the audit surfaces as a big jump.
- **project-manager** owns the delivery-risk / RAID / schedule-risk MECHANICS at the program level (its risk register, EMV/contingency, PERT, Monte-Carlo) - delivery-lead consumes those for domain 9 and the schedule-risk scoring.
- **CTO employee** owns pure go-forward technical strategy (target architecture, build-vs-buy) - the audit says what IS and what will sink it; the CTO says what to build instead.
- **business-analyst** owns build-vs-buy/feasibility scoring with its weighted scorecard + 3-year TCO when the verdict is "rebuild vs adopt".

## Sources (verified 2026-06-20, methodology only - frameworks/checklists, no tools bundled)
- 2026 technical-due-diligence standard (8 core domains: code+architecture, security+compliance, cloud/DevOps, data/DB, API, performance/load, stack+dependencies, testing/QA) - the fractional-CTO / M&A audit canon.
- RAID (Risks/Assumptions/Issues/Dependencies) + 5x5 likelihood x impact risk matrix (2026: extended to AI/third-party/ICT risk, refreshed continuously) - public PM/risk methodology.
- Key-person-risk capability matrix (critical-function x person, single-point-of-failure / bus-factor) - M&A valuation practice.
- Schedule risk: 3-point PERT + P50/P80 Monte-Carlo framing - PMBOK methodology (shared with project-manager).
- SCQA executive summary + GO/NO-GO/PIVOT evidence-cited gate - already in the BA phase-0 discipline; reused here for the audit verdict.
