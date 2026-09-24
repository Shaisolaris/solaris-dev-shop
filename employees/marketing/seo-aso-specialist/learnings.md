# SEO + ASO Specialist - Learnings (Pending)

```
Format: - **<YYYY-MM-DD> - <project/context>**: <what> *Proposed rule: <takeaway>* Tags: [#seo-tech], [#seo-content], [#seo-local], [#aeo], [#aso-ios], [#aso-android], [#cvr], [#promoted?]
```

---

## Pending observations

- **2026-04-24 - SEO+ASO clean rebuild**: First build had Shai's seo-audit wholesale (640 lines: SKILL + audit methodology + AEO + lessons). Clean rebuild from 6 repos produces strong base covering web SEO + ASO + AEO. Shai's solaris-seo-workflow ABSORBED 2026-06-04 (v0.4.0). The generic Anthropic seo-audit remains a vendor-keep (Layer A).
  *Proposed rule: Combined SEO+ASO in one employee works because audit discipline + keyword research + CVR methodology generalize. Keep them together.*
  Tags: [#combined-employee], [#promoted?]

- **2026-04-24 - SEO+ASO clean rebuild**: ASO content had to be built largely from first-principles + wshobson ui-design mobile accessibility references - none of the 6 repos had a deep, standalone ASO skill. Documented gap.
  *Proposed rule: ASO is a documented coverage gap in the 6-repo set. When Shai web-searches for 2-3 additional repos, prioritize "ASO" / "app-store-optimization" Claude skill repositories.*
  Tags: [#coverage-gap], [#web-search-target]

- **2026-04-24 - SEO+ASO clean rebuild**: AEO (Answer Engine Optimization) is emerging but every source had partial coverage. Unified here as a dedicated reference.
  *Proposed rule: Emerging disciplines (AEO / AI visibility / llms.txt) need a dedicated reference that Scout updates quarterly as the discipline matures.*
  Tags: [#emerging-discipline]

---

## Promotion log

| Date | Observation → Rule | Location |
|------|-------------------|----------|
| | | |

## 2026-05-13 - Absorbed AgriciDaniel/claude-seo (scout 2026-05-11)
- 25 sub-skills + 18 sub-agents: technical/E-E-A-T/schema/GEO-AEO/backlinks/local/maps/semantic/ecom/international
- GEO/AEO now first-class (optimize for LLM citations, not just Google)
- 9.5K stars, MIT, established author. Tier 1 PASS.

## 2026-06-13 - Depth pass + GEO methodology absorption (v0.6.0)
- TOP-5 2026 source scout (TOP5-CANDIDATES.md). New absorptions: Auriti-Labs/geo-optimizer-skill (MIT, 468 star, Princeton KDD-2024 / AutoGEO ICLR-2026 research) as GEO citability rubric methodology; facundoolano/google-play-scraper (MIT, 2888 star) + facundoolano/aso scoring method as the ASO data/keyword-scoring lane.
- Key research anchor (C-SEO Bench 2025): infrastructure beats prose for AI citation. Audit reachability + structure before rewriting sentences. Highest content lever is Cite-Sources (+115% per Princeton).
- PERFECTION findings: rules.md listed 6 phantom reference files that were never created (on-page-checklist, schema-markup-library, aso-audit-playbook, aso-launch-playbook, keyword-research, local-seo) - their content actually lives inline in SKILL.md. Removed phantoms, pointed at the 3 real refs. SKILL.md References table was stale (omitted all 3 real reference files). Added a small-task/prototype lane and operationalized the baseline-snapshot mandate into a concrete checklist.
  *Proposed rule: a reference list that names files which do not exist is worse than no list - it sends a session chasing a 404. Audit references against `ls references/` every depth pass.*
  Tags: [#aeo], [#aso-ios], [#aso-android], [#dedup], [#promoted?]
- FLAGS: ahonn/mcp-server-gsc = NOASSERTION license (avoided in favor of AminForou/mcp-gsc MIT). facundoolano/aso stale since 2023 (methodology kept, package not pinned). geo-optimizer-skill is MIT so self-host is permitted; kept as methodology + self-host note rather than a hard dependency.
