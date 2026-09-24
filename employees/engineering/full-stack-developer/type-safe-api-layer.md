# Type-safe API layer, all-TypeScript stack (tRPC, ORM choice, monorepo wiring)

When the whole stack is TypeScript (React/Next/Vite frontend + Node/Fastify/Next backend), you can get end-to-end type safety with NO codegen and NO drift. This file is the methodology for that path. It complements api-design.md (which is the REST/GraphQL canon, still the default for multi-language or public APIs) and stack-defaults.md.

Sources (methodology only, nothing bundled):
- tRPC, github.com/trpc/trpc (MIT, 40.3K stars, verified 2026-06-13)
- create-t3-app, github.com/t3-oss/create-t3-app (MIT, 29K stars)
- Drizzle ORM, github.com/drizzle-team/drizzle-orm (Apache-2.0, 34.8K stars)
- Turborepo, github.com/vercel/turborepo (MIT, 30.5K stars)
- Better Auth, github.com/better-auth/better-auth (MIT, 28.7K stars), see auth-patterns.md for the auth decision; here only as it relates to the typed stack

---

## When to reach for tRPC vs REST vs GraphQL

| Situation | Use |
|---|---|
| One TS frontend + one TS backend you control, same repo/monorepo | **tRPC**, types flow by inference, zero codegen |
| Public API, or any non-TS consumer (mobile native, third party, PHP) | **REST** (api-design.md), language-neutral contract |
| 4+ clients needing different shapes of the same data | **GraphQL** (api-design.md) |
| Next.js App Router, server-side data | Server Components + Server Actions OR tRPC; don't double up |

tRPC is not a replacement for REST on public surfaces. It's the internal-app accelerator. If a client ever needs the API from outside your TS code, REST/GraphQL is still the answer.

## tRPC core model (the part that matters)

- **Router = procedures.** A procedure is a `query` (read, GET-like), a `mutation` (write), or a `subscription` (stream). Group them into routers; routers compose into one app router whose TYPE is exported (not the implementation) to the client.
- **Validate input with zod** at the procedure boundary. The validated type IS the input type the client sees, one source, no duplication.
- **The client infers everything.** `createTRPCClient<AppRouter>()` gives full autocomplete on inputs, outputs, and errors. Rename a field on the server, the frontend fails to compile immediately. This is the whole point: a type error at build time instead of a runtime bug.
- **Context** carries request-scoped data (db handle, session/user). Auth lives in middleware: a `protectedProcedure` that checks the session in context and throws `TRPCError({ code: 'UNAUTHORIZED' })` before the handler runs. Backend enforces; the typed client just surfaces the error code.
- **Error shape is built-in and typed**, `code` (UNAUTHORIZED, FORBIDDEN, NOT_FOUND, BAD_REQUEST, ...) plus message. The frontend branches on `code`, never on message strings (same rule as the REST error contract).

### tRPC red flags
- Exporting the router IMPLEMENTATION to the client instead of just its TYPE (ships server code to the browser).
- Skipping zod input validation because "TypeScript already checks it", TS types are erased at runtime; the network boundary is untrusted. Validate.
- Using tRPC for a public/third-party API. Wrong tool; use REST.
- A `publicProcedure` doing a privileged read because auth "is handled in the UI." Auth is middleware on the procedure, full stop.

## ORM: Prisma vs Drizzle (deciding, not defaulting blindly)

Prisma is the Solaris default (stack-defaults.md). Drizzle is the considered alternative, not just "if Prisma perf issues."

| Choose Prisma when | Choose Drizzle when |
|---|---|
| Standard Node server, want the richest tooling + Studio + mature migrations | Edge / serverless runtime (Cloudflare Workers, Vercel Edge, Deno) where Prisma's engine is heavy |
| Team values the declarative schema DSL and generated client | You want SQL-first queries, ~7.4kb zero-dep footprint, tree-shakeable |
| You're already on it (don't migrate without reason) | Greenfield serverless, or you want the query builder to read like SQL |

Both give end-to-end types. Drizzle adds Drizzle Kit (migration generation/apply) and Drizzle Studio (data browser). On a tRPC stack, either works, the db type flows into the tRPC context and out through procedure return types. Don't run both in one project.

Migration discipline is the same regardless of ORM: forward + rollback, test on a clone (or a Supabase branch, see supabase-mcp-ops.md), never edit a shipped migration.

## Monorepo wiring (Turborepo over pnpm workspaces)

The "React + Vite + Node/Fastify" template is a pnpm-workspaces monorepo with a shared types package. pnpm workspaces handle dependency hoisting; they do NOT orchestrate builds. That's Turborepo's job.

- **Shape:** `apps/web`, `apps/api`, `packages/shared` (zod schemas, tRPC AppRouter type, shared types). The shared package is the single type source both apps import.
- **Turborepo adds:** a task pipeline (`build` depends on upstream `build`; `test`/`lint`/`typecheck` run in parallel) with content-aware caching so unchanged packages don't rebuild. Remote cache shares that across machines/CI.
- **Why it matters with tRPC:** the typed contract lives in `packages/shared`; touch it and only the affected apps rebuild. Without orchestration you rebuild everything every time.
- **Boundary:** Turborepo here is the dev-time build graph the full-stack dev configures (`turbo.json` pipeline). Deploy pipeline + CI runner config is the DevOps Engineer's call (this employee's standing boundary). Hand off the deploy side.

## Scaffold composition (the create-t3-app reference design)

create-t3-app is the canonical 2026 typed-stack scaffold. Don't bundle the CLI; use its composition as the blueprint for a Next.js typed template:

- Next.js (App Router) + TypeScript strict
- tRPC (server router + typed client, server-component integration)
- Prisma OR Drizzle (offered as a choice at scaffold time, mirror that)
- Auth.js (NextAuth v5) for managed-ish auth, OR Better Auth for self-hosted (see auth-patterns.md)
- Tailwind (+ shadcn/ui when a component library is wanted)
- zod for validation, shared between tRPC input and forms

Its stated philosophy is "install only what you need", every piece is optional and addable later. Follow that: scaffold the minimum, add layers when the project earns them. This is the typed-stack sibling of the existing 6 templates; treat it as a 7th (or as the upgrade path for the existing "Next.js app" template, which currently stops at Auth.js + shadcn with no typed API layer).

## The end-to-end typed flow (this stack's version of the data-flow diagram)

```
DB schema (Prisma/Drizzle), typed
 -> ORM client, typed rows
 -> tRPC context (db + session)
 -> tRPC procedure (zod-validated input, typed output)
 -> AppRouter TYPE exported (not impl)
 -> tRPC client (full inference: input/output/error)
 -> React Query under the hood (tRPC wraps it), server state cached correctly
 -> UI components
```

One type source per boundary, inference everywhere, no hand-duplicated interfaces. A change at the DB ripples to a compile error in the UI before it ever ships. That is the bar this stack hits that codegen/hand-written REST types do not.
