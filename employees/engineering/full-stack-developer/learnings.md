# Full-Stack Developer - Learnings (Pending)

```
Format: - **<YYYY-MM-DD> - <project/context>**: <what> *Proposed rule: <takeaway>* Tags: [#frontend], [#backend], [#db], [#deploy], [#api], [#auth], [#state], [#perf], [#GAP], [#promoted?]
```

---

## Pending observations

- **2026-04-24 - FS Developer rebuild**: State management decision order (local → lifted → Context → Zustand → React Query → Redux → XState) is the single most important piece of React methodology absorbed from lodetomasi. Most dev sessions default to overusing Context; the ordered hierarchy prevents that.
  *Proposed rule: When React state question comes up, always show the 7-tier decision order. Don't let the default jump to Redux or Context when local state or React Query would suffice.*
  Tags: [#state], [#react], [#promoted?]

- **2026-04-24 - FS Developer rebuild**: VoltAgent's 8-item cross-stack checklist is the best pre-ship gate I've absorbed. DB↔API↔UI alignment checks catch most type drift bugs.
  *Proposed rule: Every feature runs the cross-stack checklist before marking done. Not optional.*
  Tags: [#process], [#promoted?]

- **2026-04-24 - FS Developer rebuild**: msitarzewski's minimal-change-engineer concept unique to that source. Inherited codebase work dominates Solaris client book (Upwork rescues, takeovers). This mode should default on.
  *Proposed rule: When the project is an inherited codebase (determined by: 'rescue', 'takeover', 'inherited', or the /Desktop/CTO/skills/codebase-onboarding pattern active), switch to Minimal-change mode by default. Broader refactors require explicit CTO approval.*
  Tags: [#inherited-work], [#promoted?]

---

## Promotion log

| Date | Observation → Promoted rule | Rule location |
|------|-----------------------------|---------------|
| | | |
```

## 2026-05-01 - M4 absorption: MetaGPT Engineer spec→code handoff (v0.4.0)
- Pattern: 8-step sequence; schema discipline (verbatim signatures); no scope creep; imports from Shared Knowledge
- Anti-patterns refused: improvements, helper additions, renames
- Source: github.com/FoundationAgents/MetaGPT

## 2026-05-13 - Absorbed vercel-labs/agent-skills (scout 2026-05-11)
- 40+ React/Next.js performance rules across 8 categories, official Vercel
- web-design-guidelines + deployment patterns from platform owner
- MIT, official Vercel Labs. Tier 1 PASS (official org).

## 2026-06-13, Depth pass: type-safe API layer + self-host auth (v1.1.0)
- Absorbed (methodology, no code bundled): tRPC (no-codegen end-to-end TS types), create-t3-app (typed scaffold composition), Drizzle (Prisma-vs-Drizzle decision), Turborepo (monorepo orchestration) -> new references/type-safe-api-layer.md. All MIT/Apache, 28K+ stars, verified 2026-06-13.
- Better Auth -> auth-patterns.md as the self-hosted-library bucket (middle path between managed SaaS and hand-rolling).
- Gate-0: tRPC / create-t3-app / better-auth = 0 hits (genuine gaps). Drizzle + Turborepo = 1 thin mention each, deepened not duplicated.
- Perfection: two-lane model (full vs prototype) added; cross-stack checklist made an ordered ship gate; stale reference tables fixed; 5-step vs 10-step workflow deconflicted (SKILL.md canonical).

## 2026-07-24 engineering-core upstream
- Align FE+BE greenfield pins with specialist employees (Next 16, Laravel 13, Node 24, PG 17).
- Shared-type + migration rollback gates retained; toolchain preflight added.
## Sources

- Upstream: trpc/trpc (MIT (permissive, clean)); t3-oss/create-t3-app (MIT); better-auth/better-auth (MIT); drizzle-team/drizzle-orm (Apache-2.0 (permissive)); Turborepo, monorepo build orchestration (MIT)
- What was used: noted: trpc/trpc, t3-oss/create-t3-app, better-auth/better-auth, drizzle-team/drizzle-orm, Turborepo, monorepo build orchestration
- License notes: absorbed sources permissive (MIT/Apache-2.0); no code vendored
