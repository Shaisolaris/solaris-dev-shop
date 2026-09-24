# Network Engineer - Learnings (Pending)

## Pending observations
- **2026-06-14 - Clean build (v1.0.0)**: built for the owner's own multi-system network (dev shop + game studio homelab + networking). Methodology absorbed from ECC (affaan-m/everything-the coding agent-code, MIT) - 11 source skills, methodology only, no code bundled. The spine that recurs across every ECC network skill is "read-only first, change in a window, never lock yourself out" - codified as the core principle block in rules.md.
- **2026-06-14 - Source note**: ECC skill was named `homelab-network-readiness`, not `homelab-readiness` (the brief's working name). Confirmed via the GitHub tree; `homelab-readiness` does not exist. Lifted the readiness checklist (inventory table, trust-zone default policies, DNS-as-dependency, lockout-prevention, small-reversible change sequence) as the planning/review front door for Workflows 1-5.
- **2026-06-14 - Design lesson**: the most defensible single security upgrade for a home/office network is VLAN segmentation WITH firewall rules - VLANs alone are not security because inter-VLAN routing is open by default. Rule ordering (allow Pi-hole:53 before the RFC1918 block) is the subtle gotcha that breaks DNS for IoT if reversed.
- **2026-06-14 - For Shai's setup specifically**: dev-shop client code and game-studio test rigs are different trust zones - flagged a Dev/Build vs Game-Test VLAN split beyond the default 5 zones in SKILL.md Workflow 2 and rules.md. Revisit once the actual machine inventory (build agents, console dev kits, NAS count) is known.
- **2026-06-14 - Boundary lesson**: the four-way split (network vs devops vs cloud vs sre vs iot) keeps this employee from drifting into pipeline/cloud/reliability/firmware work. Network Engineer owns the packets and the topology; it supplies evidence to SRE during incidents and a VLAN to IoT, but does not run the pager or write firmware.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
## 2026-07-24 platform-reliability wave (skill-edl)
- Contract `1.1.0`: plan-dryrun-rollback step; provenance_ledger + partial_or_blocked_note + bounded_plan outputs.
- RUNTIME HARDENING: mutation authority only after plan, dry-run evidence, failure notes, cost/security, and rollback.
- Provider adapters retain default_deny + require_human for deploy/spend/mutate_external.
- Evaluation packet: meta/skill-rotation/evaluations/20260724/platform-reliability/.
