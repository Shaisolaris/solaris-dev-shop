# Frontend Developer - Rules (Active Methodology)

Last revised: 2026-06-09 (rebuild - content written in from real sources; see plugin.json absorbed_from)
Inherits: full-stack-developer's stack-defaults, api-design (consumption side), auth-patterns, minimal-change-mode.

**Framework + motion references** (new at v0.7.0): `vue-angular-and-nuxt.md` carries Vue 3 (incl Laravel+Vue/Inertia), Angular, and Nuxt 4 as additional supported frameworks - each maps the gates below (§1/§2/§4/§6/§7/§8) onto its own idioms. `motion-system.md` carries the full motion.dev/Framer-Motion system (tokens, springs, gestures, SSR-safe a11y) behind the "Framer Motion for complex animation" stack default. The React/Next methodology in this file is the canonical source; those two files translate and extend it, they do not duplicate it.

## 1. Before any build or recommendation - four assumptions, on paper
*Source: alirezarezvani/claude-skills senior-frontend (SKILL.md + references/forcing_questions.md)*

Do not pick a framework, rendering model, or perf strategy until these four are answered and written down:
1. **Primary device + network** - mobile-4G / desktop-fiber / low-end-Android / corporate. Kill criterion: "all users equally" → STOP, pull analytics. Every frontend optimizes for one floor and tolerates the rest.
2. **LCP target as a number in ms** (plus INP < 200ms, CLS < 0.1). Kill criterion: "as fast as possible" → STOP, pick a number. ~100ms LCP improvement ≈ 1% conversion.
3. **SEO-dependent or auth-walled.** "Both" = split the surface (public pages static/SSR, app SPA/RSC). Kill criterion: SEO-dependent + SPA-only rendering → change rendering or get the SEO penalty accepted in writing.
4. **WCAG target (2.2 AA default) + named a11y owner.** Kill criterion: customer-facing + no owner → assign before scaffolding. Retrofit costs 5–10× building it in.

Every recommendation must state: CWV targets at p75 on the primary device, a per-route JS budget in KB-gzip, and a Lighthouse a11y/perf floor. Missing any → the recommendation is incomplete.

**The three gates, made executable** (full method in verification-and-tokens.md):
- **Bundle gate.** Pick the per-route budget from the §2 profile (e.g. 150KB-gzip/route for next-app-router). Add `size-limit` or `bundlewatch` in CI with that number as a *failing* threshold before the next feature ships. Default budget if none stated: 170KB-gzip first-load JS per route (the next-app-router profile ceiling).
- **CWV gate.** Lab Lighthouse in CI catches regressions; field RUM via `web-vitals` is the only true p75. A route is not done without a field-measurement plan. Pass = LCP <= profile target, INP < 200ms, CLS < 0.1, all at field p75 on the primary device.
- **A11y gate.** axe-core scan scoped to the declared WCAG tags (`wcag2a wcag2aa wcag21aa wcag22aa`) = zero violations of the targeted level, PLUS the §7 manual contracts (axe catches ~30-50%; the manual walk catches the rest).

## 2. Rendering strategy decision table
*Source: alirezarezvani profiles/ + forcing_questions Q3; VoltAgent nextjs-developer; lodetomasi nextjs-architect*

- Marketing / docs / blog → **SSG** (Astro-or-static profile: LCP budget ~1200ms, ~30KB JS/page).
- SEO-dependent + dynamic content → **SSR or RSC** (next-app-router profile: ~2000ms LCP mobile-4G p75, 150KB-gzip/route).
- Auth-walled app → **SPA** (vite-spa profile: ~2500ms, 200KB init + 80KB/route) - no SEO cost, heavier bundle tolerable.
- Content-heavy + personalization → **RSC**.
- 2.5s LCP / 0.1 CLS are the CWV *ceilings*; the profile numbers are the *working budgets*. Never pick RSC "because it's newest" without measuring against an SSR baseline.
- ISR (`revalidate`) > SSR for content that changes on a schedule; on-demand revalidation (`revalidatePath`/`revalidateTag`) on mutation; PPR where available.

## 3. Component architecture
*Source: vercel-labs/agent-skills composition-patterns (8 rules) + alirezarezvani react_patterns.md*

- **Never grow boolean props** (`isThread`, `isEditing`, `isCompact`...). Each boolean doubles the state space. Refactor to **explicit variant components** (`<ThreadComposer/>` not `<Composer isThread/>`) built from **compound components** sharing a context.
- Compound components: provider holds `{state, actions, meta}`; subcomponents read context, never props-drill; throw a clear error when used outside the provider.
- **Lift state into provider components** so siblings outside the visual tree (dialog footers, toolbars) can reach it. Only the provider knows how state is stored - consumers see the interface, not the implementation.
- Prefer `children` over `renderX` props. Render-prop style only where the caller needs per-item data (generic `List<T>` with `renderItem` + `keyExtractor`).
- React 19: `ref` is a regular prop - no `forwardRef`; `use()` over `useContext()`. HOCs are legacy; use hooks + wrapper components unless matching existing codebase convention.
- **Never define a component inside another component** - new type every render = full remount, state destroyed. Pass props instead.
- Component > 200 lines → split. Props extend the matching HTML attributes type (`React.ButtonHTMLAttributes<...>`). Model async UI as a discriminated union (`idle | loading | success | error`) with an exhaustive switch.
- Variants via CVA (variant + size + defaultVariants) merged with `cn()`.

## 4. State management - strict decision order
*Source: lodetomasi react-wizard (tool ladder) + vercel rerender rules + alirezarezvani react_patterns + VoltAgent react-specialist (URL state)*

Walk this ladder top-down; stop at the first rung that fits:
1. **Derivable from props/state? Don't store it.** Compute in render (useMemo only if expensive). Never setState-in-an-effect for computable values.
2. Local interaction state → `useState` (lazy initializer for expensive initial values; functional updates for stable callbacks).
3. One piece of data spread over >2 useState calls, or interdependent transitions → `useReducer`.
4. State the user should be able to link/refresh/back-button → **URL** (search params), not memory.
5. Shared across a subtree → context - but context value = `{state, actions, meta}`, split providers so consumers don't re-render on unrelated changes.
6. Shared app-wide client state → **Zustand** (+ `persist` where needed). Redux Toolkit only when inheriting a codebase that has it.
7. **Server data → TanStack Query / SWR / RSC. NEVER useState + useEffect + fetch** - no dedup, no cache, race conditions, leaks. SWR/Query dedupes across component instances automatically.
8. Genuine state machines (multi-step wizards w/ guards) → XState; don't fake it with booleans.
- Forms: > 3 fields → react-hook-form + zod resolver. Form state is its own category - don't put it in global stores.

## 5. Next.js App Router rules
*Source: alirezarezvani nextjs_optimization_guide.md + vercel react-best-practices (server-* rules) + VoltAgent nextjs-developer*

- **Server Components by default.** `'use client'` only for: event handlers, state/effects, browser APIs. Push the directive to the leaves - a client island inside a server page, not a client page.
- **Caching is an explicit decision per route**: choose `force-static` / `revalidate = N` / `force-dynamic` consciously; tag fetches (`next: { tags }`) and revalidate by tag on mutation. Never ship the framework default unexamined.
- `React.cache()` for per-request dedup of auth/db lookups. Gotcha: it keys by `Object.is` - inline-object args never hit the cache; pass primitives.
- **Minimize RSC-boundary serialization**: pass `user.name`, not the 50-field `user` object - everything crossing the boundary is serialized into the HTML payload.
- **Server Actions are API routes**: validate input (zod), authenticate, rate-limit, return typed errors. Optimistic updates via `useOptimistic` / `useActionState`.
- Don't block the page shell on slow data: wrap slow sections in `<Suspense>` with skeleton fallbacks; parallel routes (`@slot`) for independent dashboard panels.
- Identical fetches in one render pass are auto-memoized - fetch where the data is used; don't prop-drill server data to avoid "duplicate" requests.
- Images: `next/image` always; `priority` on the LCP image; `fill` + `sizes` for responsive; explicit dimensions or `aspect-ratio` (CLS); `remotePatterns` allow-list; avif/webp.
- Fonts: `next/font`, `display: swap`, CSS variables. Third-party scripts: `<Script strategy="afterInteractive">` (analytics) or `lazyOnload` (chat widgets).
- SEO when it matters (Q3 said so): Metadata API, sitemap, robots, OG images, canonical, structured data.
- Secrets stay server-side (route handlers / server components). `NEXT_PUBLIC_*` = public by definition.

## 6. Performance - fix in this order, never out of order
*Source: vercel-labs react-best-practices priority ladder (72 rules); lodetomasi react-wizard ("profile first"); alirezarezvani bundle_analyzer tables*

Profile before optimizing (React DevTools profiler, Lighthouse, bundle analyzer). Then work the tiers top-down:
1. **Waterfalls (CRITICAL)** - `Promise.all` independent fetches (2–10× wins); move `await` into the branch that uses it; check cheap sync conditions before awaiting; in API routes start promises early / await late; stream slow sections behind Suspense instead of blocking the layout.
2. **Bundle size (CRITICAL)** - never import via third-party barrel files (icon/component libs cost 200–800ms + thousands of modules); fix with `optimizePackageImports` (keeps TS types) or direct paths. Local barrels for your own small `ui/` folder are fine. `next/dynamic` for heavy components (editors, charts, maps - `ssr: false` if client-only); defer analytics/error-tracking until after hydration; preload on hover/focus for perceived speed. Heavy-dep swaps: moment→date-fns/dayjs, lodash→lodash-es, axios→fetch/ky, MUI→shadcn/Radix.
3. **Server (HIGH)** - React.cache dedup, LRU for cross-request, hoist static I/O to module level, minimize RSC serialization, `after()` for non-blocking work.
4. **Client fetching (MED-HIGH)** - SWR/TanStack Query dedup; passive scroll listeners; versioned + minimal localStorage.
5. **Re-renders (MED)** - derive don't store; don't subscribe to state only read in callbacks; subscribe to derived booleans not raw values; split hooks with independent deps; `startTransition`/`useDeferredValue` for non-urgent updates; memoize only where profiling shows churn (React 19 compiler reduces the need).
6. **Rendering (MED)** - `content-visibility` or @tanstack/react-virtual for long lists; hoist static JSX; ternary not `&&` when the condition can be 0/NaN.
7. **JS micro-opts (LOW)** - last, and only with a profile in hand.
- **Hydration**: client-only data (theme, localStorage) → inline synchronous script before hydrate - never useEffect (flash) or direct read (SSR crash). `suppressHydrationWarning` only for *expected* mismatches (timestamps). React 18 strict mode double-mounts in dev - effect cleanup must be correct.

## 7. Accessibility + UI-code correctness (code concerns, not design concerns)
*Source: alirezarezvani frontend_best_practices.md + vercel web-design-guidelines*

- Semantic HTML first; ARIA second. `<button>`, `<nav>`, `<main>` - never clickable divs.
- **Modal contract**: `role="dialog"` + `aria-modal` + focus moves in on open + focus trapped + Escape closes + focus returns on close.
- **Form contract**: every input has a `<label htmlFor>` (placeholder is not a label); `aria-invalid` + `aria-describedby` pointing at the error; error rendered with `role="alert"`; autocomplete attributes set.
- Dynamic status → `aria-live="polite"`; loading buttons → `disabled` + `aria-busy`; nav → `aria-current="page"`; toggles → `aria-pressed`; disclosure → `aria-expanded` + `aria-controls`.
- Contrast 4.5:1 body / 3:1 large; never meaning by color alone (icon + text); visible `focus-visible` styles - `outline: none` without replacement is a violation; skip link; icon-only buttons get `aria-label`, icons get `aria-hidden`.
- `prefers-reduced-motion` honored; `Intl` for dates/numbers; URL reflects state.
- UI review output format: terse `file:line - finding` list (vercel web-design-guidelines convention), not prose.
- **Verify, don't assert**: run axe-core (jest-axe at component level, `@axe-core/playwright` at E2E) scoped to the declared WCAG tags as the mechanical floor; the contracts above + the manual keyboard/SR walk are the ceiling (verification-and-tokens.md §2).

## 8. Security at the UI boundary
*Source: alirezarezvani frontend_best_practices.md (Security)*

- React escapes by default - `dangerouslySetInnerHTML` only after DOMPurify with an explicit ALLOWED_TAGS/ATTR allow-list.
- All form input through a zod schema (client UX + server enforcement - client validation is not security).
- Never put secrets in client code; proxy third-party APIs through route handlers.

## 9. Testing hand-off
*Source: alirezarezvani frontend_best_practices.md (Testing) + VoltAgent frontend-developer (handoff) + wshobson frontend-developer (stack)*

- Component tests: React Testing Library, query **byRole/byLabelText** (asserts a11y for free), `userEvent` not `fireEvent`. Hooks: `renderHook` + `act`.
- Integration: mock the API layer, walk the user flow (fill → submit → assert call + UI).
- E2E (Playwright) reserved for money flows (checkout, auth, publish). Method in verification-and-tokens.md §3: `getByRole` locators, web-first auto-waiting assertions, trace viewer, `@axe-core/playwright` for a11y-in-flow. Stable `data-testid` scheme documented and handed to qa-engineer for elements with no accessible name.
- Hand-off package: files created/changed, component API + usage, architectural decisions made, test IDs, bundle-analysis output, a11y audit result.

## 10. Inherited codebases & migrations
*Source: wshobson react-modernization + VoltAgent frontend-developer (context-first) + Solaris minimal-change-mode*

- Before writing code in an existing repo: map component conventions, design-token usage, state patterns in play, testing expectations, build pipeline. Conform; no drive-by refactors.
- React upgrades are stepwise (16→17→18→19), codemod-assisted; key traps: React 18 automatic batching + strict-mode double-invocation, React 19 forwardRef removal. Class→hooks migration is gradual, component-by-component, tests first.

## Red flags (any of these = stop and fix)
- Fetched data in useState / useEffect+fetch - use a query lib or RSC.
- Boolean-prop proliferation on a shared component.
- A component defined inside another component.
- Barrel import from an icon/component library without optimizePackageImports.
- setState in an effect computing something derivable.
- `&&` rendering with a numeric condition.
- Bundle complaint without analyzer output; perf complaint without a profile.
- `outline: none` with no focus replacement; input without label; modal without focus trap.
- Server Action without validation/auth; full DB objects crossing the RSC boundary.
- `eslint-disable` without justification.

## Standing gotchas
*Sources: vercel react-best-practices (hydration, cache, strict mode); alirezarezvani nextjs_optimization_guide (caching)*

- React 18+ strict mode mounts twice in dev - effect cleanup must be correct or you'll chase ghost bugs.
- Vite env vars must be prefixed `VITE_`; Next.js public vars `NEXT_PUBLIC_`.
- Next.js App Router caches aggressively - `revalidate` + `dynamic` need explicit per-route decisions.
- `React.cache()` keys by reference - inline-object arguments mean a cache miss every call.
- TypeScript narrowing doesn't survive function boundaries - keep narrowing in scope or write type guards.
- `useImmutableSWR`-style config for data that never changes; default SWR revalidation will refetch it pointlessly.

## Cross-employee integration patterns
(Org-wide catalog: `meta/chief-of-staff/references/cross-employee-integration-patterns.md`.)

- **backend-developer** - when consuming a new API: request the zod/Pydantic schema (never infer); confirm auth, rate limit, error shapes BEFORE writing the call; client function fully typed, never `any`.
- **ui-ux-designer** - implement Figma with design tokens (colors/spacing/typography), not hex/px literals; UX owns the spec, frontend owns focus states + contrast (token pipeline: verification-and-tokens.md §4).
- **Design taste / anti-slop:** for taste/judgment heuristics (the three dials, eyebrow restraint, layout-family-no-repeat, serif restraint, palette cadence, real-asset discipline, em-dash ban) that keep AI-built UI off the LLM-default rails, QA against ui-ux-designer/references/design-taste-heuristics.md (absorbed from Leonxlnx/taste-skill, MIT). Pointer, not an absorb; the taste layer is owned by ui-ux-designer.
- **performance-engineer** - when CWV fails, bring lighthouse + waterfall + bundle analyzer + `web-vitals` field data; don't optimize before measuring; they lead deep diagnosis.
- **qa-engineer** - E2E handoff: document the user flows needing Playwright coverage + the `data-testid` attribution scheme so tests survive refactors.
- **cro-landing-designer** - landing-page conversion patterns.
- **Cursor Project Rules:** when a project runs on Cursor AI, scaffold/adapt per-stack .cursor/rules/*.mdc convention files from the selective-mining workflow in backend-developer/references/cursor-rules-scaffolds.md (shared engineering reference, from PatrickJS/awesome-cursorrules, CC0-1.0). Mine selectively and adapt to the project; never bulk-paste templates.

---

## Connected MCP servers (host-installed)

### Figma MCP - design-to-code (ABSORB: GLips/Figma-Context-MCP, MIT, ~15k★)
The design-to-code methodology is written up in `design-to-code.md`. When a Figma link is in play, pull the **structured node tree** via this MCP instead of working from a screenshot, translate auto-layout → flex/grid, and map returned values to design tokens. Host installs `figma-developer-mcp` (npx) and supplies a `FIGMA_API_KEY`.

### Context7 - live, version-correct library docs (CONNECT: upstash/context7, MIT, ~57k★)
Context7 fetches **up-to-date, version-specific documentation and code examples** for a library straight into context, killing the "trained on an old version, hallucinated an API that no longer exists" failure mode.
- **What it does:** resolve a library name → pull current docs/snippets for the exact version, on demand.
- **When to call it:** before writing against any fast-moving dependency where the API may have changed since training cutoff - Next.js App Router APIs, React 19 features, TanStack Query/Router, shadcn/ui, Tailwind v4, Framer Motion. Use it the moment you're unsure whether an API still exists or changed signature, instead of guessing.
- **When NOT to:** stable, well-known APIs you're certain of - don't burn a call confirming `useState`.
- Host installs the server (`@upstash/context7-mcp` via npx, or the hosted HTTP endpoint); no project secret required for public docs.
