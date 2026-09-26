# Cloud Architect - Learnings (Pending)

**Memory scope:** key engagement memory as `{client}:cloud-architect:{project}` (e.g. account IDs, chosen regions, RTO/RPO tiers, reserved-capacity commitments, cost baselines). Never mix one client's cost or topology facts into another's scope.

## Pending observations
- **2026-04-24 - Clean build**: alirezarezvani has per-cloud architects (AWS / GCP / Azure) - absorbed patterns from all three so Solaris can advise regardless of cloud. rohitg00 toolkit adds plugin-level cloud helpers.
  *Proposed rule: Multi-cloud advisory requires absorbing per-cloud sources rather than a single "cloud" source. The 6 Well-Architected pillars converge across clouds; specifics diverge.*
- **2026-04-24 - Clean build**: Clear altitude boundary with DevOps Engineer (Cloud Architect designs; DevOps executes). Written into both employees' SKILLs.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |

## 2026-05-01 - M2 + R4 absorptions: STRUCK 2026-06-10 (kept for history)
- ~~M2 (v0.4.0) MetaGPT Architect 5-section schema~~ - struck: off-domain (software system design, not cloud architecture); schema removed from rules.md.
- ~~R4 (v0.5.0) Ruflo swarm topologies + consensus -> references/swarm-topologies.md~~ - struck: source repo unverifiable AND off-domain (agent orchestration); reference file deleted.
- Both rolled back in the v0.6.0 rebuild. Do not re-cite. Lesson: verify domain-fit and repo existence BEFORE absorbing; a real, popular repo can still be off-domain.

## 2026-06-10 - Full rebuild (v0.6.0)
- Rebuilt from 9 GitHub-API-verified sources; struck lodetomasi (149 stars, stale), MetaGPT schema (off-domain: software design, not cloud), ruvnet swarm topologies (unverifiable repo + off-domain; reference file deleted).
- Lesson confirmed: vendor-official landing-zone repos (Azure/Enterprise-Scale, Azure/review-checklists, GCP cloud-foundation-fabric) carry deeper prescriptive content than any community agent repo for account structure + WAR checklists. Search vendor orgs first.
- sickn33 pattern repeated from k8s rebuild: its cloud-* skills are wshobson mirrors; only aws-cost-optimizer/-cleanup were unique. Always diff before crediting.
## 2026-07-24 platform-reliability wave (skill-edl)
- Contract `1.1.0`: plan-dryrun-rollback step; provenance_ledger + partial_or_blocked_note + bounded_plan outputs.
- RUNTIME HARDENING: mutation authority only after plan, dry-run evidence, failure notes, cost/security, and rollback.
- Provider adapters retain default_deny + require_human for deploy/spend/mutate_external.
- Evaluation packet: meta/skill-rotation/evaluations/20260724/platform-reliability/.
## Sources

- Upstream: awslabs/landing-zone-accelerator-on-aws (Apache-2.0); infracost/infracost (Apache-2.0); aws-samples/sample-well-architected-skills-and-steering (MIT-0); openops-cloud/openops (Apache-2.0); FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec (FLAG: spec license (Community Spec / CC-BY family, non-OSI; not a code license))
- What was used: methodology only: awslabs/landing-zone-accelerator-on-aws, aws-samples/sample-well-architected-skills-and-steering, openops-cloud/openops, FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec; connected as external reference: awslabs/landing-zone-accelerator-on-aws, infracost/infracost; methodology absorbed: infracost/infracost
- License notes: FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec: FLAG: spec license (Community Spec / CC-BY family, non-OSI; not a code license)
