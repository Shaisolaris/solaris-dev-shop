# Toolchain and Stack Patterns - methodology reference

Net-new depth pass 2026-06-15 (methodology only, no code vendored). Adds capabilities the employee did not previously carry: a fast lint/format toolchain doctrine (Biome + Oxc), a shadcn/ui ownership-model workflow, the TanStack Router and Table lanes (only Query was covered), a Zod schema-design methodology (Zod was named as a noun, never methodized), and an Astro content-site lane (Astro existed only as a budget-profile label in rules.md §2).

Every source below was license-verified and star/activity-checked on 2026-06-15. All are OSI-permissive. See plugin.json absorbed_from for the ledger.

This file does NOT duplicate: the react-best-practices priority ladder (rules.md §6), web-vitals / axe-core / Playwright / Style Dictionary (verification-and-tokens.md), TanStack Query as server-state default (rules.md §4 rung 7, §6 tier 4), the composition-patterns architecture (rules.md §3), or the Figma codegen path (design-to-code.md). Those stay where they are; this adds the gaps around them.

---

## 1. Fast lint/format toolchain - Biome and Oxc (the missing toolchain doctrine)

The employee enforces gates (bundle, CWV, a11y) and flags `eslint-disable` without justification, but never said WHAT lints/formats the code. That choice has real cost on large repos and in CI. Two Rust-native toolchains now make this fast enough that a per-commit + CI gate is free.

Sources (verified 2026-06-15):
- biomejs/biome (Apache-2.0 OR MIT dual, ~24.9k stars, v2.4.16 May 2026, 144 releases) - one binary that formats AND lints JS/TS/JSX/JSON/CSS/GraphQL; 500+ rules ported from ESLint/typescript-eslint; ~97% Prettier output compatibility; LSP, can lint malformed code as you type.
- oxc-project/oxc (MIT, ~21.5k stars, oxlint v1.69.0 Jun 2026) - VoidZero's Rust toolchain; powers Rolldown (Vite's bundler); oxlint is the linter, oxfmt the formatter. Used in prod by Shopify, ByteDance, Preact, Nuxt.

### When to reach for which
- **Greenfield Solaris project, or a repo with no entrenched ESLint config** -> Biome. One tool replaces Prettier + ESLint, zero-config defaults are sane, single `biome.json`. The cohesion (shared parser, one config, one pass) is the win, not just speed.
- **Large existing repo with a deep custom ESLint ruleset you cannot drop yet** -> oxlint as the FAST first gate alongside the existing ESLint. oxlint runs 50-100x faster and catches the correctness-class issues in seconds; keep ESLint for the type-aware/custom rules oxlint does not yet implement, and run oxlint pre-commit, ESLint in CI. This is the documented migration on-ramp, not a rip-and-replace.
- **Formatter only, Prettier is the pain point** -> Biome format or oxfmt; both are near-Prettier output at a fraction of the time. Biome is the safer drop-in because of its measured Prettier-compat percentage.

### Doctrine
- **Pick ONE formatter per repo.** Biome format OR oxfmt OR Prettier - never two, or the diff war never ends. Wire it as a pre-commit hook (so the diff is clean before it is staged) and re-check in CI (`biome ci` is the CI-shaped command that checks without writing).
- **The linter is a gate, not a suggestion.** Lint failures fail the build. This is the mechanical home for the rules.md red flags (index-as-key, `&&` with numeric conditions, missing effect deps, no-array-index-key, no-dangerously-set-inner-html) - many map directly onto Biome/oxlint rules, so the "stop and fix" list stops being honor-system.
- **`eslint-disable` / `biome-ignore` needs a reason inline.** rules.md already bans bare disables; Biome's ignore comments support a stated suppression reason - require it.
- **Do not bundle or vendor either tool here.** They are dev dependencies installed by the host (`npm i -D @biomejs/biome`, `npx oxlint`). This reference is the decision methodology, not the tool.
- **Honest limit:** oxlint does not yet implement the full type-aware rule set typescript-eslint offers; Biome's rule coverage, while large, is not 1:1 with the ESLint plugin ecosystem. For projects that genuinely depend on a niche ESLint plugin, keep ESLint for that slice and use the fast linter as the speed layer in front.

### Plugs into existing methodology
- rules.md "Red flags" list -> many become enforced linter rules instead of review-by-eyeball.
- Workflow 4 (PR review) -> the mechanical correctness sweep (step 2a) is partly automatable; the reviewer then spends attention on architecture/perf/a11y that linters cannot judge.
- Definition of done -> add "lint + format gate green" alongside the bundle/CWV/a11y gates.

---

## 2. shadcn/ui - the ownership-model workflow (not a dependency)

shadcn/ui is the SKILL.md stack default and appears in heavy-dep-swap advice (MUI -> shadcn/Radix), but the employee carried zero methodology for HOW it is consumed - and shadcn's whole point is that it is consumed differently from every other component library.

Source: shadcn-ui/ui (MIT, the canonical registry + CLI). Built on Radix primitives + Tailwind + CVA - all already in the stack.

### The mental model that changes the workflow
shadcn/ui is **not an installed runtime dependency.** The CLI copies component source INTO the repo (`components/ui/*`). You own the code. There is no `node_modules/@shadcn` to upgrade. This inverts the usual library workflow:
- **Add a component** with `npx shadcn@latest add button` -> it writes the source into your project. Read it, then it is yours to edit.
- **Customization is editing the copied file**, not fighting a theming API or wrapping to override. A variant the design needs that the default does not have -> add it to the CVA config in the owned file (this is exactly the CVA variant pattern in rules.md §3).
- **Upgrades are deliberate, per-component diffs**, not a version bump. Re-run `add` to get the latest source and reconcile against your edits. There is no automatic update; that is the trade for owning the code.
- **Tokens, not the default palette.** shadcn ships CSS-variable-based theming - map those variables to the project's semantic design tokens (the Style Dictionary output in verification-and-tokens.md §4 / design-to-code.md §3). A raw shadcn default color in shipped output is the same "literal not token" bug.

### Doctrine
- **Reconcile with the existing library before generating new markup** - this is the same rule as design-to-code.md step 7. Before hand-rolling a component, check if shadcn (or the in-house copy) already has it.
- **Do not pull the whole registry.** Add only the components a screen needs; the registry is a menu, not a bundle. This keeps the dependency surface honest and the bundle small (rules.md §6 tier 2).
- **Accessibility comes from Radix underneath** - shadcn components inherit Radix's focus management, ARIA, and keyboard handling. That satisfies the rules.md §7 contracts BY DEFAULT, but the §7 contracts still get verified (axe + manual walk); do not assume "it's shadcn so it's accessible" for COMPOSED widgets you build on top.
- **MIT, copy-in model = no vendoring concern for us** - the code lands in the client's repo under MIT; attribute per the license. We do not vendor shadcn source into this skill; this is the consumption method.

---

## 3. TanStack Router and Table (the two TanStack lanes that were missing)

The employee defaults to TanStack Query for server state (covered, do not re-document) but carried nothing on the other two TanStack libraries that come up constantly in app work. Both MIT (TanStack family, Tanner Linsley).

### TanStack Router - when the app outgrows file-based routing
Sources: TanStack/router (MIT). Use when an SPA (the vite-spa profile in rules.md §2) needs more than a flat route list - specifically when you need **type-safe, search-param-first routing.**
- **Reach for it when:** a Vite SPA with complex nested layouts, or any app where URL state matters (rules.md §4 rung 4 says "linkable/refreshable state -> URL"). TanStack Router treats **search params as first-class typed state** with validation, which operationalizes that ladder rung better than hand-rolled `useSearchParams` + manual parsing.
- **Do NOT reach for it when:** the project is Next.js (App Router file-based routing is the default and rules.md §5 already governs it) - Router is the SPA answer, not a Next.js replacement.
- **Key methodology:** define routes with typed params + a search-param schema (validate with Zod, see §4 below); the router gives you end-to-end type safety from URL to component. Pair with TanStack Query for loader-style data (Router's loaders + Query's cache compose cleanly). This is the typed, URL-as-state lane the state ladder pointed at but never named a tool for.

### TanStack Table - the headless table lane
Sources: TanStack/table (MIT). The employee mentions virtualization (`@tanstack/react-virtual`, rules.md §6 tier 6) but never the table primitive that the virtualizer usually wraps.
- **Reach for it when:** any data grid with sorting, filtering, pagination, column visibility, row selection, or grouping - i.e. a dashboard table that is more than a static `<table>`.
- **Headless by design:** it owns the LOGIC (sort/filter/paginate/select state machines), you own the MARKUP. This fits the composition-over-config doctrine (rules.md §3) and the headless-UI principle the ui-ux-designer also holds - render your own semantic `<table>`/`<thead>`/`<tbody>` (which keeps a11y honest) while Table manages state.
- **Compose with virtualization for big data:** >50 rows -> wrap with `@tanstack/react-virtual` (the same library rules.md §6 names). Table handles the data model, the virtualizer handles the DOM window. Keep server-side pagination/filtering for genuinely large sets (push the work to the API, do not ship 100k rows to filter client-side).
- **A11y caveat:** because Table is headless, the accessible table semantics are YOUR responsibility - real `<table>` markup, `scope` on headers, `aria-sort` on sortable columns, a visible sort indicator (not color-alone, per rules.md §7). Headless means you cannot blame the library for missing roles.

---

## 4. Zod - schema-design methodology (it was a noun, now it is a method)

Zod is referenced four ways in the existing files (react-hook-form resolver, Server Action validation, "get the zod schema from backend", API contract) but there is no guidance on DESIGNING schemas well. Zod is the validation spine of the whole stack; it deserves method.

Source: colinhacks/zod (MIT, Colin McDonnell). TypeScript-first schema validation with static type inference.

### Core methodology
- **Schema is the single source of truth; infer the type, never duplicate it.** Write the Zod schema, then `type Foo = z.infer<typeof fooSchema>`. Never hand-maintain a parallel `interface` next to a schema - they drift. This is the central Zod discipline and it is what makes it worth the runtime cost.
- **Validate at every trust boundary** - this is where the existing files gesture but do not systematize. The boundaries: (1) form input (RHF + zodResolver, already in rules.md §4); (2) Server Action / route-handler input (rules.md §5 / §8 - parse the incoming payload, never trust client validation as security); (3) external API responses and `fetch` results (the response is `unknown` until parsed - this catches the "API changed shape" failure that TypeScript alone cannot, because TS types are compile-time fiction over runtime data); (4) `localStorage` / URL search params before use (rules.md §4 rung 4 URL state + the versioned-localStorage rule in §6 tier 4).
- **`safeParse` at boundaries you do not control, `parse` where a throw is correct.** External data -> `safeParse` and handle the typed error union (maps onto the discriminated-union async-state model in rules.md §3: `idle | loading | success | error`). Internal invariants you expect to hold -> `parse` and let it throw (a programmer error, not a user error).
- **Compose, do not repeat.** `.extend()`, `.pick()`, `.omit()`, `.merge()`, `.partial()` to derive request/response/form variants from one base schema. A `CreateUser` schema and an `UpdateUser` schema should share a base, not be two hand-written walls.
- **Transform and coerce at the edge.** `z.coerce.number()` for query-string params (everything in a URL is a string); `.transform()` to normalize at parse time so the rest of the app sees clean data. Keep transforms at the boundary, not scattered through components.
- **Error messages are UX.** Custom messages per field (`z.string().email("Enter a valid email")`) feed the form's inline errors (rules.md §7 form contract: error rendered with `role="alert"`, tied via `aria-describedby`). The schema is where the error copy lives, so it stays consistent between client and server validation.

### Plugs into existing methodology
- rules.md §4 (forms -> RHF + zod), §5 (Server Actions validate input), §8 (all form input through a zod schema) -> this file is the "how to design the schema" those rules assumed.
- TanStack Router (§3 above) -> search-param schemas are Zod schemas.
- backend-developer integration (rules.md cross-employee) -> "request the zod/Pydantic schema, never infer" - this is the consumption discipline for the schema once you have it.

---

## 5. Astro - the content-site lane (was only a budget label)

rules.md §2 lists an "Astro-or-static profile" as a bundle budget (~30KB JS/page) but carried no Astro methodology. For marketing sites, blogs, docs, and content-heavy pages, Astro is often the right tool over Next.js, and the employee should be able to reach for it deliberately.

Source: withastro/astro (MIT, Fred K. Schott / Astro team).

### When Astro is the right call (decision, slotted into rules.md §2)
- **Content-first sites with little interactivity** - marketing, blog, docs, landing pages that are mostly static content. Astro ships **zero JS by default**; you opt INTO interactivity per-component. This is the structurally-lowest-JS option, which is why it owns the bottom of the §2 budget table.
- **Choose Astro over Next.js SSG when:** the site is genuinely content-led and the islands of interactivity are small and isolated. Choose Next.js when the app has app-like interactivity throughout or shares a codebase/auth with a larger Next app.

### Core methodology
- **Islands architecture is the whole point.** The page is static HTML; interactive components are "islands" hydrated independently. Use the `client:*` directives as a deliberate cost decision: `client:load` (hydrate immediately - expensive, reserve for above-fold interactive), `client:idle` (hydrate when the browser is idle), `client:visible` (hydrate when scrolled into view - the default for below-fold widgets), `client:media` (hydrate at a breakpoint). Every `client:` directive is JS you are choosing to ship - treat it like the rules.md §6 bundle budget: justify each one.
- **Bring your own framework for the islands.** Astro is framework-agnostic; the islands can be React (the Solaris default), so the component knowledge transfers - a React island in Astro follows the same rules.md §3 composition and §7 a11y contracts.
- **Content Collections for typed content.** Astro's content layer validates frontmatter with - again - Zod schemas (`defineCollection` + a Zod schema per collection). This makes Markdown/MDX content type-safe; the §4 Zod methodology applies directly. Mistyped frontmatter fails the build, not silently at runtime.
- **View Transitions for SPA-feel without an SPA.** Astro's built-in view-transitions give app-like navigation on a static site; honor `prefers-reduced-motion` (same rule as rules.md §7 and motion-system.md).
- **The gates still apply.** An Astro site still meets the four-assumptions gate (rules.md §1), the CWV targets (its low-JS default makes LCP/INP easy but does not exempt measurement - verification-and-tokens.md §1 still applies), and the a11y contracts (§7).

### Plugs into existing methodology
- rules.md §2 rendering decision table -> Astro is now a NAMED option for the "marketing/docs/blog -> SSG" row, not just a budget number.
- Zod (§4 above) -> Content Collections are Zod-validated.
- motion-system.md -> Astro View Transitions honor reduced-motion like every other animation.

---

## Source ledger (all verified 2026-06-15, methodology only, no code vendored)
- biomejs/biome - Apache-2.0 OR MIT (dual, permissive) - ~24.9k stars - v2.4.16 (May 2026), 144 releases - active. Fast format+lint toolchain.
- oxc-project/oxc (oxlint/oxfmt) - MIT - ~21.5k stars - oxlint v1.69.0 (Jun 2026), 247 releases - active, VoidZero, used by Shopify/ByteDance/Nuxt/Preact. Fast Rust linter/formatter.
- shadcn-ui/ui - MIT - copy-in registry+CLI, Radix+Tailwind+CVA. Ownership-model component workflow.
- TanStack/router - MIT - TanStack family. Type-safe, search-param-first SPA routing.
- TanStack/table - MIT - TanStack family. Headless table logic.
- colinhacks/zod - MIT - TypeScript-first schema validation; infer-don't-duplicate. Schema-design methodology.
- withastro/astro - MIT - islands architecture, zero-JS-default content sites; Zod-validated Content Collections.
