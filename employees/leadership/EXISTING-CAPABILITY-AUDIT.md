# Existing-capability audit - skill-solaris-business-hardening

Date: 2026-07-23  
Scope: `solaris/employees/{leadership,marketing,sales-outreach,creative-media}/**`  
Architecture: Alfred/Solaris capability and quality architecture

## Adopted

| Asset | Disposition |
|-------|-------------|
| Domain checklists, hard numbers, workflows in SKILL.md / rules.md | **Adopted** into contracts as procedure + evidence acceptance |
| OUTPUT CONTRACT / SELF-QA patterns where present (cto, content-marketer, market-researcher, seo-aso, proposal-writer) | **Adopted** as output fields + Gate: passed |
| Paid-ads / outreach "humans push publish" norms already in prose | **Adopted** as `require_human` scopes + approval_preview |
| plugin.json reference lists | **Adopted** as dependency reference hints (packaging still marketplace-validated) |
| Progressive disclosure (rules.md, depth files, learnings.md) | **Adopted**; contracts point at SKILL.md surface |

## Corrected

| Defect | Correction |
|--------|------------|
| Provider lock-in ("Claude is…") | Provider-neutral runtime block + `compatibility.providers` four defaults |
| Missing operational contracts | Added `capability.contract.json` per active employee (20) |
| Tools/authority only in prose | Explicit tools[], permissions.default_deny, approval_points |
| External send/spend/publish risk | message_send / spend / mutate_external → require_human; deploy/move_funds → deny |
| Invented or stale metrics risk | claim_ledger + source_ledger requirements; adversarial fixtures fail unsupported claims |
| Financial self-authorization | financial authority ladder L0 for skills; spend never mode=allow |
| Brand-unaware public drafts | brand_check / brand policy gates in shared RUNTIME-POLICY.md |
| No forward tests for business workflows | fixtures/solaris/business/** + tests/solaris/business/** |

## Retired (as norms for these directories)

- Autonomous message send, media buy, CMS/social publish, or contract signature from a skill turn  
- Treating marketplace packaging pass as behavioral quality  
- Provider prompt identity as source of truth for grants  
- Using undated benchmarks as current market truth  

## Unresolved limitations

- Full encyclopedic SKILL.md files not fully slimmed to ≤200-line surface (progressive disclosure debt remains).  
- Not all depth reference files rewritten as formal `references/` trees.  
- L4 signing/canary/observability channel not in this bead (deployment-profiles).  
- Live MCP connectors for ads/ESP/social remain undeclared until real connector packs exist; contracts fail closed without granting them.  
- Human authorization UX lives in Workspace runtime - skills only emit approval_preview.

## Rollback / recovery evidence

- Each contract sets `lifecycle.rollback_target` and `failure.preserve_partial: true`.  
- Adversarial fixtures prove permission denials do not require destructive cleanup.  
- No control-plane, Dolt, or marketplace identity changes in this wave.

## Inventory (20 capabilities → L2 packaged + L3 fixture coverage)

See capability.contract.json beside each employee SKILL.md and fixtures under fixtures/solaris/business/.
