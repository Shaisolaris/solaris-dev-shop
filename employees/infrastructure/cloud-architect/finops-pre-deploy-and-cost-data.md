# FinOps - pre-deploy cost gate + normalized cost data + workflow library

Methodology absorbed 2026-06-13 from three verified 2026 sources. No code bundled; the architect uses these patterns and connects the tools (host installs). Extends rules.md §6 (cost architecture), which until now was entirely post-hoc audit.

Sources:
- infracost/infracost (Apache-2.0, 12.4k stars, v0.10.44 @ 2026-04-06): shift-left cost estimation + FinOps policy in the IaC/PR loop.
- FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec (FinOps Foundation, 283 stars, v1.3 @ 2025-12-08; FLAG non-OSI spec license, CC-BY family): vendor-neutral billing-data schema. Self-host note below.
- openops-cloud/openops (Apache-2.0, 1.0k stars, 0.6.23 @ 2026-03-18): pre-built FinOps workflow library + human-in-the-loop controls.

## 1. Shift-left cost gate (Infracost) - cost moves into design, not just audit
The existing §6 doctrine reacts to spend that already happened. Add a pre-deploy gate so cost is a design input:
- **Price-lookup during design**: answer "how much is an `m7i.xlarge` in `us-east-1`?" or "what does this Aurora config cost/mo?" with no code written yet - price the pattern-vs-scale choice before naming the service.
- **Cost diff on the PR**: every IaC change (Terraform / Terragrunt / CloudFormation / CDK) gets a monthly-cost delta posted on the pull request before merge. A change that moves the bill materially must be acknowledged, not discovered on the next invoice.
- **FinOps policy as code**: enforce tagging (the §1 `Environment/Owner/CostCenter/Project/ManagedBy` set), allowed regions, and budget thresholds at PR time - reject non-compliant IaC instead of cleaning it up later.
- **Where it sits**: this is a devops-engineer/CI concern to wire up, but the architect owns the policy definition (what tags, which regions, what budget ceilings) and reads the cost diff during design review. CONNECT the CLI + agent skill; do not hand-roll a pricing engine.
- **Doctrine shift**: §6 right-sizing + commitments stay reactive (you need real utilization), but greenfield cost is now estimated and gated, not guessed.

## 2. Normalized cost data (FOCUS) - one vocabulary across clouds
Raw AWS/Azure/GCP billing exports are not comparable; column names and cost meanings differ. FOCUS is the FinOps Foundation's vendor-neutral schema that maps every provider's billing data onto a common set of columns. Use it as the target format for any cost report or cross-cloud comparison.
- **Core cost columns to reason in** (provider-agnostic): `BilledCost` (what's invoiced for the period), `EffectiveCost` (amortized, incl. prepaid commitments), `ListCost` (pre-discount), `ContractedCost` (negotiated-rate). Quote bill-cut and multi-cloud numbers in these terms so they mean the same thing on every provider.
- **Classification columns**: `ChargeCategory` (Usage / Purchase / Tax / Credit / Adjustment), `CommitmentDiscount*` (ties RI/SP/CUD coverage to the rows it discounts), `ServiceCategory`, `Region`, resource + tag columns for allocation.
- **v1.3 (Dec 2025) adds a dedicated contract-commitment dataset**: start/end dates, remaining units, descriptions isolated from cost/usage rows - so reservation/commitment coverage is structured, not inferred. Use it to drive the §6 "reservation utilization ~100%" check across providers.
- **When to invoke**: any cross-cloud cost comparison, any chargeback/showback model, any multi-account cost report that has to be comparable over time. For single-cloud one-off audits the §6 CLI pack is still fine.
- **Self-host / license note**: FOCUS is a SPECIFICATION under a non-OSI spec license (Community Specification / CC-BY family), not a code library. Reference the column model and cite the spec; do NOT bundle or vendor the spec text into Solaris. Providers' native FOCUS exports (AWS/Azure/GCP all publish FOCUS-conformant data) are the implementation path.

## 3. FinOps workflow library + human-in-the-loop (OpenOps)
The §6 bill-cut workflow's weakest step is execution safety ("validate with owners -> execute"). OpenOps formalizes the operational layer:
- **Opportunity lifecycle**, not a one-shot delete: every savings finding (idle instance, unattached volume, oversized SKU) becomes a tracked opportunity that can be approved, dismissed, marked false-positive, or snoozed - with an audit log. Maps onto the §6 snooze->stop->delete cadence and the "validate with owners" gate.
- **Human-in-the-loop approval gate before any de-provisioning**: no resource is deleted or downsized without an explicit approval through a channel (Slack/ticket). This is the durable doctrine - keep it even without the platform: destructive cost actions require a logged human approval, never auto-fire.
- **Pre-built workflow taxonomy** worth mirroring in engagements: cost allocation + tagging enforcement, unit-economics reporting, anomaly management (detect -> route -> approve -> act), workload optimization, safe de-provisioning of idle resources, budget + reporting rollups.
- **Consolidation**: pull findings from multiple visibility sources (native Cost Explorer/Cost Management + third-party) into one opportunity list rather than chasing each console separately.
- **Doctrine line**: surface savings automatically, but require human approval to realize them - the bigger the blast radius, the higher the approval bar.

## CONNECT note (host installs)
- Infracost: `brew install infracost` (or curl installer) + `infracost setup`; wire the agent skill (iac-generation / scan / price-lookup) and the CI integration. Architect defines the FinOps policies; devops-engineer wires CI.
- OpenOps: self-host via docker-compose, or managed cloud. Scoped read-first cloud credentials; destructive actions behind HITL.
- FOCUS: no install - consume providers' FOCUS-conformant billing exports; reference the spec at focus.finops.org.
