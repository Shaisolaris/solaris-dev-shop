# Codemod Migration + Strangler-Fig + Renovate (full-stack, methodology, license-safe)

Powers the **Codebase Migration Plan** gig for small/all-in-one projects this GENERALIST owns end-to-end. backend-developer holds the deep server-side authority (Java/Spring OpenRewrite recipes, multi-service decomposition, DBA-coordinated data migration); THIS file is the right-sized version for a one-person full-stack migration (a React/Next app, a TS monorepo, a single web app + its API). When the migration crosses into heavy backend territory, hand off to backend-developer.

## 0. Gate-0 (already had vs net-new)
- ALREADY HAD: type-safe-api-layer (tRPC/Prisma/Drizzle/Turborepo), stack-defaults, minimal-change-mode, project-takeover notes, supabase ops.
- NET-NEW (this file): the migration METHOD - codemods for mechanical change, strangler-fig for incremental cutover, Renovate for dependency currency - right-sized for full-stack scope. minimal-change-mode is the spine: a migration is the maximal version of "smallest reversible change", repeated.

## 1. Codemods for mechanical change (the front-end's bread and butter)
A codemod transforms code by rewriting its AST, not by find-replace, so a sweeping API change becomes deterministic and reviewable.
- **jscodeshift** (MIT) - the JS/TS codemod runner. Always dry-run (`-d -p`) -> read the diff -> run tests -> commit the codemod result on its own.
- **Prefer vendor codemods**: Next.js `@next/codemod`, React, MUI, etc. ship official codemods for their own breaking changes - run those before hand-rolling a transform. A framework major upgrade should be "run the vendor codemod, then fix the residue", not "edit every file".
- OpenRewrite exists for the JVM/heavy side - if a migration needs it, that is backend-developer's lane (see its codemod-migration-playbook.md, incl. the MSAL recipe + Moderne-SaaS license flags).

## 2. Strangler-fig for incremental cutover (no big-bang rewrite)
For a framework/platform swap (Pages Router -> App Router, CRA -> Vite/Next, JS -> TS, one web app -> a new stack) where rewriting all at once is the trap.
- Grow the new alongside the old behind the SAME routes. Route traffic over incrementally - one route / one feature at a time - behind feature flags, with rollback tested in staging. The old app keeps serving the whole time (zero-downtime); each step is reversible.
- Establish a parity check (old vs new render/behave the same) before routing real traffic to a migrated slice. Decommission a legacy slice only after its replacement is proven live.
- This is minimal-change-mode at migration scale: many small reversible cutovers, never one catastrophic switch.

## 3. Renovate for dependency currency
Turn Renovate on at the START of a migration so the project stops drifting while you work, and stays current after.
- Automated dependency-update PRs across npm + the rest; group framework bumps; automerge low-risk updates ONLY behind a green test suite; pair each major bump with its vendor codemod (section 1).
- **LICENSE FLAG:** the self-hosted Renovate CLI is **AGPL-3.0** (copyleft + network clause) - fine to RUN on a client repo; flag the AGPL posture before embedding/forking-and-hosting it in a product. Mend's hosted GitHub App is free; commercial tier is paid. **Recommend-only**: default to the free hosted App or running the AGPL CLI as-is.

## 4. Deliverable + execution path
- **Deliverable:** a phased migration plan - inventory + risk map -> Renovate on -> codemod the mechanical debt -> strangler-fig the architectural moves route-by-route with flags + parity tests + rollback -> decommission. Hand off to backend-developer when server-side decomposition, OpenRewrite recipes, or DBA-coordinated data migration is involved.
- WIRED with repo access + github-mcp: run codemods dry-run-first, open PRs, wire Renovate config. PLAN-ONLY otherwise: deliver the plan + codemod list + routing design + Renovate config template; never claim a repo change not made.
- License posture: jscodeshift MIT (clean); Renovate CLI AGPL-3.0 (flag, recommend run-not-fork); OpenRewrite/Moderne flags live in backend-developer's file. Methodology in Solaris voice, no copy-paste.
