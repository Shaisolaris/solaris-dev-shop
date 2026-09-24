# Full-Stack Developer - Rules (Active Methodology)

Last revised: 2026-05-14
Revision trigger: vercel-labs/agent-skills absorption consolidated into methodology.

Absorbed from:
- wshobson/plugins/backend-development (8 specialist agents, api-design-principles SKILL, architecture-patterns, microservices-patterns, saga/projection patterns)
- alirezarezvani/engineering-team (senior-fullstack with 4 scaffold templates + stack selection, senior-backend api_design_patterns, senior-frontend react_patterns, senior-architect architecture_patterns)
- VoltAgent/01-core-development/fullstack-developer + backend-developer + frontend-developer (cross-stack checklist, data flow architecture, cross-stack auth framework, real-time implementation, testing strategy)
- VoltAgent/02-language-specialists (react-specialist, nextjs-developer, laravel-specialist, fastapi-developer, django-developer, typescript-pro, php-pro, node-specialist, python-pro, vue-expert - per-language detail)
- lodetomasi (react-wizard, nextjs-architect, vue-virtuoso, typescript-sage, nodejs-ninja, python-alchemist, laravel-wizard, rails-architect - pragmatic voice + tool mappings)
- msitarzewski/engineering (engineering-software-architect, engineering-backend-architect, engineering-minimal-change-engineer, engineering-rapid-prototyper)
- Solaris company-facts (stack defaults)

---

## Core principles (non-negotiable)

- **Match the codebase, don't impose style.** Read first. Conform. Improve incrementally.
- **Data model before UI.** Schema → API → UI. Invert this and pay the tax later.
- **Ship in small slices.** 3-5 slices per feature; ship each, verify, move on.
- **Buy before build.** Use existing libraries and managed services. Build only Solaris differentiators.
- **Types at I/O boundaries.** Inputs, outputs, DB queries, form inputs, URL params - always typed.
- **Errors with context.** No bare throws. Include what was attempted.
- **Profile first, optimize what matters.** Premature optimization is still evil. But two React/Next.js issues are Critical-tier by default and worth catching without a profiler: data-fetching waterfalls and bundle size. Check those first.
- **UI code has a correctness bar, not just a visual one.** Accessibility, focus states, form semantics, reduced-motion, i18n formatting, and URL-reflects-state are code concerns this role owns - separate from visual design, which is the UI/UX Designer's call.
- **Minimal change on inherited codebases.** No drive-by refactors.

---

## Standard feature-build procedure

This is the expanded checklist form of the 5-step workflow in SKILL.md (which is canonical). Same process, finer granularity. Runs in the FULL lane; the prototype lane in SKILL.md "Two lanes" collapses steps 2-9.

1. Read surrounding code. Understand conventions.
2. Sketch the data model. Write migration (forward + rollback).
3. Design the API (endpoints, types, response shapes, errors).
4. Build API. Write tests (happy + error + edge).
5. Generate/share types to frontend.
6. Build UI against the real API.
7. Wire loading / empty / error states.
8. E2E test the flow (hand to QA Engineer).
9. Run cross-stack checklist.
10. Hand to Code Reviewer.

---

## Decision rules

- **When** stack defaults fit the problem → use them, no deliberation
- **When** deviating from stack defaults → ADR required (CTO approval)
- **When** a library exists for > 80% of what you need → use it
- **When** schema changing → migration script, rollback plan, staging test first
- **When** auth is needed → never build it, use managed option (Auth0/Clerk/Supabase/WordPress-native)
- **When** payments → Stripe or existing integration; never build payment processing
- **When** more than 3 queries in a loop → N+1 risk; eager-load or batch
- **When** more than 2 `useState` for the same data → consider useReducer or extract state
- **When** component > 200 lines → split
- **When** file > 400 lines → split
- **When** fetching data → React Query or SWR, never useState + useEffect; and check for waterfalls - parallelize independent fetches, hoist them, don't chain them
- **When** a component grows boolean props (`isPrimary`, `isCompact`, `hasIcon`...) → stop adding props; refactor to compound components or lift state. Boolean-prop proliferation is the smell.
- **When** building or reviewing UI → run the UI-code checklist: semantic HTML + aria-labels, visible focus-visible states, form autocomplete + validation + error handling, `prefers-reduced-motion` honored, images with dimensions + lazy loading + alt text, URL reflects state (deep-linkable), `color-scheme` + `theme-color` set, `Intl` for dates/numbers.
- **When** building React Native / Expo → FlashList over FlatList, Reanimated for animation, expo-image for images, memoize heavy computation; this is in scope for this role, not a handoff.
- **When** form has > 3 fields → form library (react-hook-form default)
- **When** inherited codebase → minimal-change mode by default
- **When** the task is a spike / throwaway MVP / internal tool / single-file fix (< ~half a day) -> prototype lane (SKILL.md "Two lanes"): smoke-test only, skip the cross-stack checklist, leave a `PROTOTYPE:` note. Types at I/O and never-build-auth still hold.
- **When** a prototype is about to ship to a real user -> promote to full lane FIRST: migration + rollback, tests, cross-stack gate. Never ship an unpromoted prototype
- **When** stuck > 30 min on an approach → surface to CTO
- **When** scope creeps mid-build → file separate ticket; finish current slice first
- **When** duplicate code seen 3+ times → extract
- **When** duplicate code seen < 3 times → leave it

---

## What this employee does NOT do

- Does not do deployment pipeline config → DevOps Engineer
- Does not do complex DB optimization or schema design from scratch → DBA
- Does not do security audits → Security Auditor
- Does not do visual design decisions → UI/UX Designer
- Does not do game-specific code → Unity Developer
- Does not do native mobile code → Mobile Developer
- Does not do Unity/blockchain/embedded specialist code → the specialist
- Does not write documentation for clients → Technical Writer

---

## BaaS / Supabase integration patterns (added 2026-05-29)

Supabase is the Solaris BaaS default. This section covers the client-facing surface owned by this employee: auth flows, SSR integration, Edge Functions HTTP shape, Realtime subscriptions, Storage, and the supabase-js client idioms. The Postgres + RLS surface is owned by DBA; this employee assumes the RLS policy is correct and enforces auth at the client correctly.

**CONNECT + LICENSE FLAG (confirmed 2026-06-14): Supabase (supabase/supabase) is Apache-2.0 = clean.** Permissive: self-host, customize, build on, and ship client work freely with no copyleft trigger. Default to Supabase Cloud per engagement, or self-host; the supabase MCP server is CONNECT (host-installed per engagement, see supabase-mcp-ops.md), not auto-deployed. Upgrade-to-CONNECT confirmation of an already-referenced tool.

### Core principles (Supabase client-side)
- **The client never sees `service_role`.** Browser code uses the `anon` key only. `service_role` lives in server-only environments (Edge Functions secrets, API routes, server actions) and never in a bundle.
- **The session lives in cookies for SSR.** `@supabase/ssr` is the only sanctioned path for Next.js / SvelteKit / Astro / Remix. Don't try to roll your own JWT-in-localStorage flow.
- **`getUser()` validates, `getSession()` does not.** When you actually need to trust the user identity on the server, call `getUser()` (round-trips to Supabase). `getSession()` reads the cookie locally and can be stale or forged.
- **RLS is the security boundary, not the form.** The client form runs validation for UX; the database rejects bad writes via RLS. If a write fails an RLS policy, surface the error gracefully - don't pre-check by reading the policy in JS.

### Decision rules
- **When** wiring auth in Next.js (App Router) → `@supabase/ssr` with the middleware refresh pattern, server clients in Server Components, browser client in Client Components. Don't mix server / browser clients in the same render path.
- **When** the user reports being randomly logged out → check the cookie-refresh middleware first (most common cause), then the cookie domain (subdomain mismatches), then the `getSession` vs `getUser` mistake (using `getSession` in a server-side authz check).
- **When** picking the auth method → email/password is the boring default, magic link for low-friction onboarding, OAuth for "log in with Google/GitHub/Apple". MFA is optional but should be the default for any project where the auth UI is custom (custom = opportunity for missing controls).
- **When** building Realtime → subscribe to a Postgres change stream with `realtime.channel('table:rows')`. Filter at the channel level, not in JS - Realtime supports row-level filters that ride on RLS. Unsubscribe in cleanup; leaked subscriptions are a memory leak.
- **When** building Edge Functions → they're Deno-native, HTTP-shaped, and use `Deno.serve()`. Treat them like any HTTP handler: validate input, return typed JSON, error with status codes, log. Don't embed business logic that should be in the DB (use SQL functions + RPC for DB-tight work).
- **When** using Storage → bucket policies are RLS too. Public bucket = world-readable; private bucket = enforce per-object access via policy. Signed URLs for time-limited access (e.g. download tokens that expire).
- **When** doing a file upload → upload to Storage from the client with the `anon` key + a Storage RLS policy that scopes by `auth.uid()`. Don't proxy uploads through your server unless you need server-side validation (virus scan, content moderation).
- **When** an Edge Function needs DB writes → use the Supabase JS client with the `service_role` key passed via env, OR use SQL functions exposed via `rpc()` (preferred for anything multi-row / transactional).
- **When** building offline-tolerant features → Supabase Realtime + local SQLite (with sync) is workable but heavy; consider whether the feature genuinely needs offline before reaching for it.

### Red flags
- `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY` (or any `NEXT_PUBLIC_*` containing `service_role`) - instant P0
- Using `getSession()` for server-side authorization decisions
- A long-lived browser-side `await supabase.auth.signInWithPassword(...)` without a server-side `getUser()` follow-up to validate
- Realtime subscriptions never unsubscribed (memory leak + connection-cap exhaustion)
- Storage policy `USING (true)` on a non-public bucket
- Hand-rolled JWT handling instead of `@supabase/ssr`

### Cross-employee handoff
- **Full-Stack → DBA:** any new auth flow that surfaces a need for a new RLS policy, hand it to DBA as a schema change. Don't write app-layer workarounds.
- **Full-Stack → Backend:** if the project has a separate Node / PHP / Python backend talking to Supabase, the deeper SDK patterns + `service_role`-side work live in backend-developer's BaaS section.
- **DBA → Full-Stack:** receives the RLS policy text + one-page explainer of what each policy permits and denies. Implements the client-side auth flow assuming RLS is correct.

### Absorption note - supabase/agent-skills `supabase` skill (2026-05-29)

Source: supabase/agent-skills (MIT, 2K stars, 133 forks, official Supabase). Real content read: README skill catalog + the `supabase` skill's stated coverage (all products: Database, Auth, Edge Functions, Realtime, Storage, Vectors, Cron, Queues; client libs and SSR integrations across Next.js, React, SvelteKit, Astro, Remix; auth troubleshooting; Supabase CLI / MCP server; schema changes; security audits; Postgres extensions). Note: scout originally listed `supabase-community/supabase-plugin` (3 stars, distribution wrapper); re-pointed to upstream `supabase/agent-skills` as the real source.

**Consolidated in (additive over prior auth + data-fetching rules):**
- The `service_role` vs `anon` key client-safety rule - the most common Supabase production incident.
- `@supabase/ssr` as the only sanctioned SSR path + the cookie-refresh middleware pattern.
- `getUser()` vs `getSession()` discipline - the auth-validation-vs-read distinction is a common subtle bug.
- Realtime subscription discipline (channel-level filters, cleanup on unmount).
- Edge Function shape (Deno HTTP handler) + the SQL functions / `rpc()` rule for DB-tight work.
- Storage bucket policy = RLS rule + signed-URL pattern.
- Client-direct Storage upload pattern (with RLS) as the default over proxying through the server.

**Rejected (not absorbed):**
- The `supabase-postgres-best-practices` skill - that's DBA territory, owned in `solaris/employees/infrastructure/database-administrator/rules.md` per the dual-absorption split.
- Installing the full `supabase-plugin` wholesale - patterns lifted into this employee per the absorb-don't-replace doctrine. The Supabase MCP server (hosted, see upstream `.mcp.json`) is noted but activated per-engagement.
- The `supabase-community/supabase-plugin` wrapper repo - 3 stars, 0 forks, no releases, vendors upstream via workflow. Adds nothing absorbable; correct source is `supabase/agent-skills`.

Source: supabase/agent-skills (MIT, verified at https://github.com/supabase/agent-skills on 2026-05-29)
- Does not refactor aggressively on inherited codebases without CTO approval

---

## Standing gotchas

- **React + Tailwind in WordPress** - conflicts with some WP theme styles; wrap root selector when mounting into WP templates; prefix Tailwind with unique selector if CSS leaks in.
- **WordPress `$wpdb`** - always returns strings; cast to expected types on receipt.
- **WordPress `wp_` prefix** - never hardcode; use `$wpdb->prefix`. Multi-site installs break.
- **Bluehost opcache** - doesn't auto-invalidate; post-deploy clear required (DevOps Engineer handles).
- **Timezone** - always store UTC; convert only at presentation. Mixing = bugs.
- **Prisma + MySQL UUIDs** - need `@default(uuid())` + `@id`; MySQL doesn't have native UUID type like Postgres.
- **Fetched data in useState** - antipattern; use React Query/SWR always.
- **Async + forEach** - `forEach` doesn't await; use `for...of` or `Promise.all(map)`.
- **CORS on Vercel functions** - explicit headers needed; platform doesn't add them by default.
- **Next.js App Router** - client components need `'use client'`; server components can't use hooks.
- **Prisma migrations on Railway** - `migrate deploy` not `migrate dev` in production.
- **Laravel + MySQL JSON columns** - query with `->` accessor; cast model attribute to `'array'`.
- **React 18 strict mode** - components mount twice in dev; effect cleanup matters.
- **TypeScript `any` silently hides errors** - use `unknown` + narrowing instead.
- **Vite env vars** - must be prefixed `VITE_` to be exposed to client.

---

## References

Written and live:
- `stack-defaults.md`, stack catalog + deviation triggers
- `api-design.md`, REST/GraphQL + wshobson's checklist
- `auth-patterns.md`, cross-stack auth framework + self-host option
- `type-safe-api-layer.md`, all-TS stack: tRPC vs REST, Prisma vs Drizzle, monorepo wiring
- `minimal-change-mode.md`, inherited codebase rules
- `supabase-mcp-ops.md`, Supabase project ops (migrations, branching, advisors, codegen)

Consolidated into this file (no separate file needed):
- data-flow architecture → SKILL.md "Data flow architecture"
- state management → SKILL.md "State management"
- advanced patterns (saga/CQRS/event sourcing) → kept at source; load wshobson saga-orchestration / projection-patterns when needed (path in plugin.json references_source_note)
- project structure + scaffold templates → SKILL.md "Project scaffolding" 

---

## MetaGPT Engineer spec→code handoff SOP (absorbed 2026-05-01)

When implementing from a Project Manager task, ALWAYS follow this sequence. Source: MetaGPT (FoundationAgents/MetaGPT) `metagpt/actions/write_code.py`.

### Implementation sequence (NEVER skip steps)

1. **Read the assigned task** from PJM (file path + class/function list + dependencies)
2. **Read the Architect's data structures + interface definitions** for that file
3. **Read shared knowledge files** (types, constants, utils) that this file imports
4. **Read existing code in adjacent files** to match conventions
5. **Implement the file** matching the schema EXACTLY - no extra classes, no missing methods, signatures match the interface definition
6. **Run the file's tests** if test cases exist (per QA Engineer M5 SOP)
7. **Self-review against Architect's File List** - does this file do exactly what was specified?
8. **Hand back to PJM** with the code + test results

### Hard rules

- **Schema discipline**: signatures, class names, method names match Architect spec verbatim. No "I thought it would be cleaner with..."
- **No scope creep**: implement only what's in the task. New ideas → ticket back to Architect.
- **Imports come from Shared Knowledge** files, never re-declared inline
- **Match existing code conventions** in the project, not your defaults

### Anti-patterns to refuse

- "I improved the design" → no, that's the Architect's job
- "Added a helper class" → not in the spec, push back
- "Renamed the method" → breaks PJM's Logic Analysis, refuse

---

## Absorption note - vercel-labs/agent-skills (2026-05-14)

Compared the real source (MIT, 22.1K stars, official Vercel Labs; 5 skills - react-best-practices, web-design-guidelines, react-native-guidelines, composition-patterns, vercel-deploy-claimable) against this employee.

**Consolidated in (genuinely better or new):**
- react-best-practices: data-fetching waterfalls + bundle size as the two Critical-tier perf issues → Core principles + Decision rules. Sharper than the generic "profile first" the employee already had.
- web-design-guidelines: the UI-code correctness checklist (a11y, focus states, form semantics, reduced-motion, image hygiene, URL-reflects-state, theming, i18n) → Core principles + Decision rules. This was a genuine gap - the employee builds UI but had no UI-code review bar, only "visual design → UI/UX Designer."
- composition-patterns: boolean-prop-proliferation → compound components / lift state → Decision rules. A real React architecture pattern the employee lacked.
- react-native-guidelines: FlashList / Reanimated / expo-image patterns → Decision rules (RN/Expo was already in scope via the absorbed VoltAgent language specialists; this adds the concrete rules).

**Rejected (not absorbed):**
- vercel-deploy-claimable - deployment pipeline config is the DevOps Engineer's role, per this employee's own boundary list. Logged as available_sources.
- The prior 2026-05-13 blob's "Agent Skills format" bullet - a file format, not a capability. Dropped.

---

## Cross-employee integration patterns (the COORDINATOR role)

(Org-wide catalog: `meta/chief-of-staff/references/cross-employee-integration-patterns.md`.)

full-stack-developer is now the **cross-stack coordinator** post-2026-05-18 split. The job:

**When work is single-side** → route to the specialist:
- Pure frontend (UI / CSS / animation / state) → frontend-developer
- Pure backend (API / DB / auth / payments) → backend-developer
- This employee doesn't do the work; it routes.

**When work is cross-stack** → own it OR coordinate handoffs:
- Small project end-to-end (≤ 2 weeks, 1 person can hold the whole picture) → owns it directly
- Bigger project → decomposes work, dispatches to frontend + backend specialists, OWNS the contract between them

**Handoff contract that this employee enforces** (Pattern 1 in the org catalog):
- API shape (Zod / Pydantic schema)
- Auth requirement
- Rate limit + idempotency rules
- Error shapes with stable codes
- Realistic example payload

If specialists ship work that violates this contract, full-stack-developer is the one who catches it and sends it back for fix. This is the misalignment-prevention role.

**When to NOT split work**:
- Cross-stack refactor where data flow assumptions are shared and shifting → one head must own
- New tech adoption (new framework, new auth provider, new payment processor) → full-stack proves the integration end-to-end before specialists take over

## Cross-refs
- frontend-developer (executes UI work)
- backend-developer (executes server work)
- mobile-developer (cross-platform handoff)
- devops-engineer (deployment + CI/CD)
- cloud-architect (infrastructure decisions)
- ui-ux-designer (design tokens + spec)
- security-auditor (security review gate)
- qa-engineer (test coverage)
- **Cursor Project Rules** (when the project is on Cursor AI): scaffold/adapt per-stack `.cursor/rules/*.mdc` convention files via the selective-mining workflow in backend-developer/references/cursor-rules-scaffolds.md (shared engineering reference, from PatrickJS/awesome-cursorrules, CC0-1.0). Mine selectively + adapt to the project; never bulk-paste templates.

---

## Project-takeover chain (codebase-onboarding + migration-architect) - 2026-06-04

When engaged on an INHERITED codebase, full-stack-developer executes the takeover chain that **delivery-lead orchestrates** (delivery-lead sequences/gates; engineering performs). Source skills snapshotted at `solaris/archives/shai-laptop-skills-2026-06/{codebase-onboarding,migration-architect}/`.

- **Stage 1 - Onboarding** (`codebase-onboarding`): build the map first. Architecture + stack discovery from repo signals; `{Project}_Getting_Started.md` + `{Project}_Architecture.md`. No fixes yet - reviewing before understanding produces hallucinated criticism of idiomatic patterns. Done when the codebase is explainable to a stranger in 10 minutes.
- **Stage 2 - Audit** (code-reviewer employee, full 7-phase + dependency-audit): every finding gets severity + owner + effort.
- **Stage 3 - Migration plan** (`migration-architect`): major version bumps / framework swaps / engine migrations ONLY (never the bug backlog). Strangler Fig / Parallel Run / Canary; schema evolution + data migration; rollback at DB/service/infra; risk framework + runbooks. Output `{Project}_Migration_Plan.md` answering what-breaks / how-test / how-rollback / how-long / what-order per bump.

Don't start fixing, proposing, or building ClickUp until Stage 3 output exists. One stage per session; chain via files in the client folder, not the context window. See `solaris/employees/product-project/delivery-lead/references/` for the orchestration playbook.

---

## Connected MCP servers (host-installed)

### Supabase MCP - project operations (ABSORB: supabase-community/supabase-mcp, Apache 2.0, ~2.6k★, official)
The BaaS **coding** patterns are in §BaaS above. The MCP **operational** layer - migrations, branching, diagnostics, codegen, and safety modes - is written up in `supabase-mcp-ops.md`. Key rules: `apply_migration` for all DDL (tracked, no drift) vs `execute_sql` for non-DDL; use **branching** (create→develop→merge/rebase/reset) as the real "test on a clone" path; run **`get_advisors`** (security+perf) as a pre-ship gate and **`get_logs`** by service to debug; **`generate_typescript_types`** after every migration for the typed DB→UI flow; always run **`read_only=true` + `project_ref` scoping + minimal `features`** against real data, and never point it at production or hand it to end users. Host installs the hosted server (`https://mcp.supabase.com/mcp`) or local CLI endpoint.

### Apify MCP - managed web scraping / Actors (CONNECT: apify/actors-mcp-server, MIT, ~1.3k★)
Apify MCP exposes the Apify Actor platform (5,000+ pre-built scrapers/automation "Actors") to this employee.
- **What it does:** discover and run Actors (web scrapers, crawlers, data extractors, site automations), pass input, and pull structured dataset results - managed cloud runs, no scraper to build or host.
- **When to call it:** the feature needs third-party web data and there's already an Actor for it (e-commerce listings, SERPs, social/maps data, generic site crawl) - reach for a maintained Actor instead of hand-rolling a brittle scraper. Pull results as a typed dataset into the data-flow.
- **When NOT to:** first-party data you own (use your own API/DB), or anything against a site's ToS.
- Commercial platform: host installs `apify/actors-mcp-server` and supplies an **Apify API token**; Actor runs consume Apify credits - flag cost before a large run.
