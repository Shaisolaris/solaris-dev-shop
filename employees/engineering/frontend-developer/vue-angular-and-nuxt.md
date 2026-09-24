# Vue 3, Angular, Nuxt 4 - new framework abilities

Adds Vue 3 (including the Laravel + Vue stack the owner runs), Angular, and Nuxt 4 as supported frameworks alongside the existing React / Next.js coverage. The React-specific gates (four-assumptions in rules.md §1, the perf priority ladder §6, the a11y contracts §7, the state ladder §4) are framework-agnostic in spirit and still apply; this file translates them to each new framework and adds what is genuinely different.

Methodology only - distilled from the ECC sources below, no code vendored. Verify the live API per framework version before writing (Context7, rules.md "Connected MCP servers"); framework defaults move fast.

Absorbed from (methodology, not code), all github.com/affaan-m/everything-the coding agent-code (MIT), verified 2026-06-14:
- skills/angular-developer (origin ECC) - Angular signals / forms / DI / routing / aria / testing methodology.
- skills/nuxt4-patterns (origin ECC) - Nuxt 4 hydration safety, data fetching, route rules, lazy hydration.
- skills/ui-to-vue (origin community) - screenshot to Vue 3 batch conversion workflow + privacy guardrails.

---

## When to use which framework
- **React / Next.js** - the Solaris default (rules.md stack-defaults). Reach for the others only when the project already uses them or the client mandates them.
- **Vue 3** - the owner's own stack runs **Laravel + Vue**. Use Vue 3 Composition API when working any Laravel + Inertia/Vue or Vite + Vue project, and when batch-converting design screenshots (ui-to-vue lane below).
- **Angular** - large, opinionated, DI-heavy apps; teams that already standardized on Angular CLI + the Angular style guide. Do not introduce Angular into a React or Vue shop.
- **Nuxt 4** - the SSR / hybrid-rendering meta-framework for Vue, the Vue analogue of Next.js. Use it when a Vue project needs SSR, SSG, ISR, or route-level rendering strategy.

---

## 1. Vue 3 (Composition API)

Vue 3's reactivity + SFC model maps cleanly onto the methodology already in rules.md. The translations:

- **Composition API + `<script setup>` by default.** `ref`/`reactive` for state, `computed` for derived values (this is the rules.md §4 rung 1 "derive, don't store" rule in Vue form - never watch-and-assign what `computed` can derive). `watch`/`watchEffect` only for genuine side effects, never for derived state.
- **State ladder, Vue dialect** (mirrors rules.md §4): local `ref`/`reactive` -> `provide`/`inject` for a subtree -> **Pinia** for app-wide client state (the Zustand-equivalent; Vuex only when inheriting it) -> **TanStack Query (Vue)** or Nuxt `useFetch`/`useAsyncData` for server state, never a hand-rolled `onMounted` + `fetch` (same anti-pattern as React's useEffect+fetch, rules.md §4 rung 7). URL/route state via `vue-router` query, not memory.
- **Component architecture, Vue dialect** (mirrors rules.md §3): props down, events up (`defineProps`/`defineEmits`); `v-model` for two-way bindings; **slots** are Vue's `children`/composition primitive - prefer named slots over a pile of boolean props (the boolean-proliferation rule of rules.md §3 applies identically). Scoped slots are the render-prop equivalent for per-item data. Extract a component when it crosses ~200 lines or a region repeats.
- **Forms:** vee-validate + zod (or yup) for anything past ~3 fields, same threshold as react-hook-form in rules.md §4.
- **Performance, Vue dialect** (mirrors rules.md §6): the React perf ladder maps almost one-to-one. `v-once`/`v-memo` for static or rarely-changing subtrees (the memo tier); `shallowRef`/`shallowReactive` when deep reactivity is wasted on large payloads; async components + `defineAsyncComponent` and route-level code splitting for the bundle tier; `<Suspense>` for async setup; virtual scrolling for long lists. Profile with Vue DevTools before optimizing - same "measure first" discipline.
- **Reactivity gotchas:** do not destructure a `reactive` object (loses reactivity - use `toRefs`); `ref` needs `.value` in script but auto-unwraps in template; `props` are readonly (never mutate - emit instead).
- **a11y + security:** the rules.md §7 contracts (semantic HTML, modal focus trap, labelled inputs, `prefers-reduced-motion`) and §8 boundaries (no secrets client-side, sanitize before `v-html` - Vue's `v-html` is the `dangerouslySetInnerHTML` equivalent and needs the same DOMPurify allow-list) carry over unchanged.

### Laravel + Vue (the owner's stack)
- **Inertia.js is the usual bridge.** Treat Inertia pages as the routing + data layer: server-side controllers return Inertia responses (props), the Vue page component receives them as props. There is no separate client-side API call for first-paint data - it arrives in the Inertia payload (the Laravel analogue of RSC props / Nuxt payload). Do not re-fetch on mount what Inertia already passed.
- **Validation lives in two places, enforced server-side.** Laravel FormRequest / validator is the security boundary; client zod/vee-validate is UX only (same split as rules.md §8 - client validation is never security).
- **Vite is the build tool** (`laravel-vite-plugin`); env vars exposed to the client must be prefixed `VITE_` (rules.md standing gotcha holds). Secrets stay in Laravel `.env` server-side.
- **Auth + CSRF:** Laravel session + CSRF token; Inertia forwards it. Never put API secrets in the Vue bundle - proxy through Laravel routes (the rules.md §8 "proxy third-party APIs" rule).
- **SSR option:** Inertia SSR or Nuxt-in-front only when SEO demands it (rules.md §1 Q3). A logged-in Laravel app behind auth is the SPA profile (rules.md §2) - no SEO cost, heavier bundle tolerable.

### ui-to-vue batch lane (screenshots -> Vue 3 components)
*Source: ECC ui-to-vue. Use when a directory of design screenshots needs a first-pass Vue 3 scaffold, target lib Vant / Element Plus / Ant Design Vue.*

- **When to use:** a *directory* of screenshots grouped by module/page-state, Vue 3 target, you want a first pass of page components + shared components + router wiring against a named UI library. **When not to:** a single bespoke component (just build it), non-Vue target, designs needing real interaction/data/a11y depth, or **any screenshot containing private customer data** (it is sent to an external model API - get permission first).
- **Input shape:** screenshots grouped `Module/PageState/`, asset folders named one of `assets`/`icons`/`sprites`/`cut`/`images`/`cut-images`, nested under the matching page or module.
- **Conversion model:** combine list/detail/form/loading/empty screenshots of one page into a single page component; map native visuals to the chosen lib's components; asset priority page-level -> module-level -> global; extract a shared component only when a region repeats more than once.
- **Run pinned, key in env:** `export DASHSCOPE_API_KEY=...` then `npx ui-to-vue-converter@1.0.2 --input ./screenshots --ui vant --output ./src` (or `--ui element-plus` / `--ui antd-vue`). **Pin the version**, never `@latest`, in any repeatable workflow. If a config file is needed, gitignore `.ui-to-vue.config.json` and never commit keys, generated secrets, or customer screenshots.
- **This is a first pass, not a deliverable.** The output is unreviewed generated code: run it through the project formatter/linter/type-checker/build, confirm router style matches, confirm the UI library is used consistently, replace placeholder copy/mock data, and apply the rules.md §7 a11y contracts the converter does not. Then it re-enters the normal Definition of Done.

---

## 2. Angular
*Source: ECC angular-developer.*

Angular is version-sensitive: features and best practice differ sharply across major versions. **Always detect the project's Angular version first** (`ng version`) and tailor guidance to it before writing code. For a new project, do not pin a version unless asked - let the CLI take latest stable.

- **CLI-first, build-verified.** Scaffold components/services/directives/pipes/guards/routes with the Angular CLI for consistency, follow the Angular style guide. After generating code, **run `ng build` and fix every error before handing off** - this is the Angular analogue of the rules.md Definition-of-Done "it compiles and the budget holds" floor, and it is not optional.
- **Reactivity = Signals (modern Angular).** `signal()` for writable state, `computed()` for derived (the §4 rung-1 "derive don't store" rule - never use an `effect()` to compute what `computed()` can; that is the Angular form of setState-in-effect). `linkedSignal()` for writable state that tracks a source. `resource()` for pulling async data directly into signal state (the server-state primitive - prefer it over manual subscribe-and-assign, mirroring rules.md §4 rung 7). `effect()` only for true side effects (logging, third-party DOM, `afterRenderEffect`), never for derived state.
- **Forms decision:** prefer **Signal Forms** for new forms when the target version supports them; otherwise match the app's existing strategy (reactive forms for complex, template-driven for simple). Signal-forms traps: initial field values must be `''`/`0`/`[]`, never `null`/`undefined`; call the field then read flags (`form.field().valid()`, not `form.field.valid()`); set `min`/`max`/`value`/`disabled`/`readonly` as schema rules, not HTML attributes on `[formField]`.
- **Dependency injection** is Angular's core idiom: `inject()` over constructor params in modern code, `providedIn: 'root'` for app-wide singletons, `InjectionToken` + `useClass`/`useValue`/`useFactory` for configurable providers, hierarchical injectors (`EnvironmentInjector` vs `ElementInjector`, `optional`/`skipSelf`, `providers` vs `viewProviders`) for scoping. Never call `inject()` outside an injection context - wrap in `runInInjectionContext` when needed.
- **Routing:** define routes with static/dynamic segments + wildcards + redirects; lazy-load feature routes (the bundle tier of rules.md §6); guard access with `CanActivate`/`CanMatch`; pre-fetch with `ResolveFn` data resolvers; rendering strategies CSR / SSG (prerender) / SSR-with-hydration map onto the rules.md §2 decision table; route transitions via the View Transitions API.
- **Accessibility:** for Accordion/Listbox/Combobox/Menu/Tabs/Toolbar/Tree/Grid, build on Angular's headless aria primitives and style the ARIA attributes - do not hand-roll roles/focus from scratch. The rules.md §7 contracts (focus management, labelled controls, contrast) are the acceptance bar.
- **Styling:** Tailwind integrates with Angular; component styles are encapsulated by default (Shadow DOM-like) - know the encapsulation mode before fighting specificity. Animations: prefer native CSS, legacy DSL only when needed.
- **Testing:** `TestBed` + component harnesses for robust interaction (query by harness, not brittle CSS), `RouterTestingHarness` for navigation, Cypress/Playwright for E2E (the rules.md §9 money-flow lane). Same byRole-over-CSS spirit.
- **Angular anti-patterns to flag in review:** `effect()` for derived state; `inject()` outside context; `$parent.$index` in nested `@for` (unsupported - use `let outerIdx = $index`); starting new forms on legacy APIs when Signal Forms are available; `null`/`undefined` signal-form initial values.

---

## 3. Nuxt 4 (Vue SSR meta-framework)
*Source: ECC nuxt4-patterns. Nuxt is to Vue what Next.js is to React - the rules.md §5 App-Router instincts transfer, with Nuxt's own primitives.*

- **Hydration safety (the Nuxt equivalent of the rules.md hydration playbook / Workflow 3).** Keep the first render deterministic: no `Date.now()`, `Math.random()`, browser APIs, or storage reads in SSR-rendered template state. Push browser-only logic behind `onMounted()`, `import.meta.client`, `<ClientOnly>`, or a `.client.vue` component. Use Nuxt's `useRoute()` (not vue-router's). Do not drive SSR markup off `route.fullPath` (URL fragments are client-only -> mismatch). Treat `ssr: false` as an escape hatch for truly browser-only areas, not the default fix.
- **Data fetching (the server-state rule, Nuxt dialect - mirrors rules.md §4 rung 7 and §5 RSC fetching):**
  - `await useFetch()` for SSR-safe page/component reads - it forwards server-fetched data into the Nuxt payload and avoids a second fetch on hydration (the Nuxt analogue of RSC data arriving in the HTML payload).
  - `useAsyncData(key, fetcher)` when the fetcher is not a plain `$fetch`, when you need a custom key, or when composing multiple async sources. Give it a **stable key** for cache reuse; keep handlers side-effect free (they run on SSR and hydration).
  - `$fetch()` only for user-triggered writes / client actions, never top-level page data.
  - `lazy: true` / `useLazyFetch` / `useLazyAsyncData` for non-critical data that should not block navigation - and handle `status === 'pending'` in the UI (explicit loading state, same as a Suspense fallback).
  - `server: false` only for data not needed for SEO or first paint. Trim payloads with `pick`; use shallower payloads when deep reactivity is unnecessary.
- **Route rules = rendering strategy per route group** (this is the rules.md §2 decision table, expressed as Nuxt config). In `nuxt.config.ts`'s `routeRules`: `prerender: true` (static HTML at build - marketing/docs), `swr: N` (serve cached + revalidate in background - catalogs), `isr: true` (incremental static regen on supported hosts - blogs), `ssr: false` (client-rendered - admin/dashboards), `cache`/`redirect` (Nitro response behavior - APIs). Pick per group, never globally: marketing pages, catalogs, dashboards, and APIs each want a different strategy.
- **Lazy loading + performance** (the bundle + rendering tiers of rules.md §6): Nuxt already route-splits - keep route boundaries meaningful before micro-splitting. `Lazy` prefix to dynamically import non-critical components; pair with `v-if` so the chunk loads only when the UI needs it. Lazy hydration for below-the-fold interactive UI (`hydrate-on-visible`, or `defineLazyHydrationComponent()` with a visibility/idle strategy) - note passing new props to a lazily hydrated component triggers hydration immediately. Use `NuxtLink` for internal nav so Nuxt prefetches route components + payloads.
- **Nuxt review checklist:** first SSR render matches hydrated client render; page data uses `useFetch`/`useAsyncData`, not top-level `$fetch`; non-critical data is lazy with explicit loading UI; route rules match each page's SEO + freshness needs; heavy interactive islands are lazy-loaded or lazily hydrated.

---

## Cross-framework discipline (what does not change)
- The **four assumptions** (rules.md §1) precede framework choice, not the reverse. Device+network, LCP number, SEO-vs-auth, WCAG+owner are framework-agnostic.
- The **rendering decision table** (rules.md §2) maps onto each framework: SSG -> Nuxt `prerender` / Angular prerender; SSR/RSC -> Nuxt `useFetch`+SSR / Angular SSR-hydration; SPA -> Vue+Vite / Angular CSR / Laravel-auth apps.
- The **perf priority ladder** (rules.md §6: waterfalls -> bundle -> server -> client -> re-renders) is framework-agnostic; only the tool names change (Vue DevTools / Angular DevTools instead of React Profiler; `v-memo`/`OnPush`+signals instead of `memo`).
- The **a11y contracts** (rules.md §7) and **security boundaries** (rules.md §8 - including `v-html`/Angular sanitizer = `dangerouslySetInnerHTML`) are identical across frameworks.
- The **verification gates** (verification-and-tokens.md): web-vitals is framework-agnostic; axe-core has Vue/Angular bindings (`vitest-axe`, jasmine/karma integrations) and `@axe-core/playwright` works on any rendered page; Playwright money-flow E2E and the Style Dictionary token pipeline are framework-neutral.
- **Inherited codebases** (rules.md §10): detect framework + version first (especially Angular - run `ng version`), map conventions, conform, no drive-by refactors.
