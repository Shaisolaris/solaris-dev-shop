# Top-5 Verified Sources, Full-Stack Developer depth pass (2026-06-13)

Scope: end-to-end app frameworks, BaaS, auth, type-safe API layers, deployment, monorepo.
All candidates verified live via GitHub API on 2026-06-13. Gate-0 = grep of this employee's ACTUAL current content (SKILL.md + rules.md + references/).

Legend: ABSORB = lift methodology into this employee. CONNECT = note as a tool/integration to reach for. METHODOLOGY = patterns only, no code bundling.

---

## 1. tRPC, type-safe API layer (the headline gap)

- URL: https://github.com/trpc/trpc
- Stars: 40,326
- License: MIT (permissive, clean)
- Last commit: 2026-06-13 (same day)
- Maintainer: trpc org (1,621 forks, active, used by Fortune 500 teams)
- What it adds: end-to-end TypeScript type safety between server and client WITHOUT codegen or a schema layer. The router/procedure model (query/mutation/subscription), input validation via zod, and direct type inference into the client. This is the single most-requested capability in the brief that the employee has zero coverage of. The employee's data-flow section says "types shared end-to-end" but offers only OpenAPI/Prisma codegen and hand-written TS as the mechanism. tRPC is the no-codegen path for the all-TypeScript Solaris stack (React+Vite+Node/Fastify monorepo, already a template).
- Gate-0: 0 hits for `trpc`. Genuine gap, NOT a content-duplicate.
- Tag: ABSORB (methodology into a new type-safe-api-layer reference)

## 2. create-t3-app, opinionated full-stack typesafe scaffold

- URL: https://github.com/t3-oss/create-t3-app
- Stars: 28,975
- License: MIT
- Last commit: 2025-12-13 (within 6 months)
- Maintainer: t3-oss org (1,517 forks)
- What it adds: the canonical 2026 scaffold for Next.js + tRPC + Prisma/Drizzle + Auth.js + Tailwind, all wired together, with a documented "install only what you need" philosophy. The employee has 6 scaffold templates but the "Next.js app" template lists Auth.js + shadcn and stops there, no type-safe API layer baked in, no Drizzle option at scaffold time. create-t3-app is the reference design for a 7th template (or an upgrade to the Next.js template).
- Gate-0: 0 hits for `t3`/`create-t3`. Gap, not duplicate.
- Tag: METHODOLOGY (lift the scaffold composition as a template; do not bundle the CLI)

## 3. Better Auth, framework-agnostic self-hostable auth for TypeScript

- URL: https://github.com/better-auth/better-auth
- Stars: 28,699
- License: MIT
- Last commit: 2026-06-13 (same day)
- Maintainer: better-auth org (2,611 forks, very high engagement)
- What it adds: a self-hostable, framework-agnostic TS auth library with 2FA, multi-tenant/organization support, and a plugin ecosystem, that owns its own tables in YOUR database. The employee's auth-patterns.md is entirely managed-provider-first (Auth0/Clerk/Supabase/WP-native/Laravel Breeze) and says "never build auth." Better Auth is the missing middle: NOT building auth from scratch, but also not handing the client's user table to a third-party SaaS. Important for data-residency-sensitive or cost-sensitive clients who can't put auth behind Clerk/Auth0. Slots into the "never build it, use a managed option" rule as a fourth bucket: self-host a maintained library.
- Gate-0: 0 hits for `better-auth`. Gap, not duplicate.
- Tag: ABSORB (add to auth-patterns.md decision matrix as the self-host option)

## 4. Drizzle ORM, type-safe SQL-first ORM (deepen existing thin mention)

- URL: https://github.com/drizzle-team/drizzle-orm
- Stars: 34,781
- License: Apache-2.0 (permissive)
- Last commit: 2026-06-11
- Maintainer: drizzle-team org (1,445 forks)
- What it adds: a ~7.4kb, zero-dependency, serverless-ready TS ORM supporting Postgres/MySQL/SQLite with both relational and SQL-like query builders, plus Drizzle Kit migrations and Drizzle Studio. The employee mentions Drizzle exactly once ("if Prisma perf issues") with no methodology behind it. Drizzle is now a first-class scaffold choice (an option inside create-t3-app) and the default for edge/serverless runtimes where Prisma's engine is heavier. Worth promoting from a one-line fallback to a real "when Drizzle vs Prisma" decision rule.
- Gate-0: 1 passing mention in SKILL.md (`Drizzle if Prisma perf issues`). Content-thin, NOT a content-duplicate, no methodology exists.
- Tag: ABSORB (Prisma-vs-Drizzle decision rule into the type-safe-api reference)

## 5. Turborepo, monorepo build orchestration (deepen existing thin mention)

- URL: https://github.com/vercel/turborepo
- Stars: 30,539
- License: MIT
- Last commit: 2026-06-13 (same day)
- Maintainer: vercel org
- What it adds: high-performance monorepo task running with content-aware caching, task pipelines, and remote cache. The employee's "React + Vite + Node/Fastify" template says "Monorepo (pnpm workspaces)" with no build-orchestration layer, pnpm workspaces handle dependency hoisting but not cached/parallelized task graphs across packages, which is exactly the pain on any monorepo with a shared types package (the tRPC pattern). Turborepo is the orchestration layer on top of pnpm workspaces.
- Gate-0: 1 mention (`Monorepo (pnpm workspaces)` in SKILL.md). Thin, no methodology. NOT a duplicate.
- Tag: CONNECT / METHODOLOGY (note as the orchestration layer for the monorepo template; deployment/CI mechanics stay with DevOps Engineer per existing boundary)

---

## Notes / boundary respect

- Deployment specifics (Vercel deploy, CI pipeline config) stay with the DevOps Engineer per this employee's own boundary list. Turborepo enters only as the dev-time build-graph/caching concept the full-stack dev configures, not as a deploy pipeline.
- Supabase (BaaS) is already deeply absorbed (coding patterns in rules.md BaaS section + operational layer in references/supabase-mcp-ops.md), so a 6th BaaS candidate (Appwrite 56.3K / Directus 36K) was evaluated and de-prioritized: Appwrite is BSD-3 and Directus is NOASSERTION (flag), and neither fills a gap Supabase leaves. Logged here for the scout, not absorbed.
- Hono (30.9K, MIT) evaluated as an edge-runtime backend framework; deferred, overlaps existing Express/Fastify guidance and deep backend work routes to backend-developer.
