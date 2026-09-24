# Motion system - tokens, springs, gestures, SSR-safe a11y

A complete, layered animation system for React / Next.js using `motion/react` (the modern Motion for React package; the legacy import path is `framer-motion`). This deepens the existing "Framer Motion for complex animation, CSS transitions for micro-interactions" stack default into an actual methodology: a token + spring foundation, a pattern library, an advanced/gesture layer, and the accessibility + SSR rules that bind them.

Methodology only - distilled, no code vendored. The code snippets are illustrative shape, not files to copy verbatim; verify the live `motion/react` API per project version (Context7).

Absorbed from (methodology, not code), all github.com/affaan-m/everything-the coding agent-code (MIT), verified 2026-06-14:
- skills/motion-foundations - tokens, spring presets, the `shouldAnimate()` gate, reduced-motion + SSR rules.
- skills/motion-patterns - button/modal/toast/stagger/page-transition/scroll/layout patterns.
- skills/motion-advanced - drag, gestures, text, SVG, custom hooks, imperative `useAnimate` sequences, loaders.
- skills/motion-ui - the consolidated motion.dev / Framer-Motion system (v4.2): version discipline, device adaptation, modal essentials, debugging + QA checklists.

The four ECC skills are a deliberate stack: foundations is the base layer everything imports; patterns and advanced both consume foundations and never redefine its values; motion-ui is the consolidated overview. Read foundations first.

---

## 0. Should this animation exist at all
Motion must do at least one of: **guide attention**, **communicate state**, **preserve spatial continuity**. If it does none, remove it - decoration is not a reason. And the overriding trade-off: **responsiveness outranks smoothness**. A 60fps animation that adds input delay is worse than no animation. This is the same "measure, do not assert" spirit as the perf ladder (rules.md §6).

---

## 1. Foundation layer (set up once per project)
*Source: ECC motion-foundations. Every other layer imports these; nothing downstream redefines them.*

### The token system
One source of truth for every animation value, so component files never hardcode a duration or easing:
- **`motionTokens`** - `duration` (instant 0.08 / fast 0.18 / normal 0.35 / slow 0.6 / crawl 1.0 seconds), `easing` (smooth / sharp / bounce / linear cubic-bezier arrays), `distance` (xs 4 -> xl 48 px), `scale` (subtle 0.98 / press 0.95 / pop 1.04).
- **`springs`** - five named presets: `snappy` (default UI), `gentle` (cards/modals/panels), `bouncy` (playful/onboarding), `instant` (tooltips/popovers), `release` (drag release physics).
- This is the animation analogue of the design-token pipeline (verification-and-tokens.md §4): named tokens with a single home, never literals in components. A raw `transition={{ duration: 0.4 }}` inline is the same class of bug as a raw `#3B82F6`.

### Duration + spring choice (decision tables)
- Duration: `instant` for tooltip/focus-ring/badge; `fast` for button/icon/chip feedback; `normal` for modal open / card expand / element enter; `slow` for hero/full-page; `crawl` sparingly for deliberate storytelling.
- Spring: `snappy` for buttons/chips/nav; `gentle` for cards/modals landing softly; `bouncy` for empty states/onboarding; `instant` for tooltips/dropdowns; `release` for drag release.

### The animation gate
A `shouldAnimate({ essential })` runtime check returns `false` (skip the animation) when: reduced motion is preferred, OR the device is low-end and the animation is non-essential, OR the element is off-screen and will never enter the viewport, OR the animation is purely decorative. Device detection combines CPU cores **and** `navigator.deviceMemory` (Chrome/Android; treat undefined elsewhere as capable, falling back to `hardwareConcurrency <= 4`). Always guard `window`/`navigator` reads with `typeof ... !== "undefined"` - never read them at module level (breaks SSR).

### The eight non-negotiable foundation rules
1. **`motion/react` only.** Never `framer-motion` in a modern project, never both in one tree (mixing breaks `AnimatePresence` exit coordination - two schedulers).
2. **`initial` must match server output.** If the server renders `opacity: 1`, `initial` must be `opacity: 1`. Defer the entrance to a client-mount flag (`useEffect(() => setMounted(true))`) or `AnimatePresence`. This is the rules.md hydration rule (§6, Workflow 3) applied to motion.
3. **Reduced motion overrides everything.** When `useReducedMotion()` is true, disable all transforms; the only permitted fallback is an opacity fade <= 0.2s.
4. **Never animate layout properties** (`width`/`height`/`top`/`left`/`margin`/`padding`). Use `transform` + `opacity` only - they are GPU-composited; layout props trigger reflow/paint. (Same as the rules.md §6 "animate the wrapper not the SVG" rule, generalized.)
5. **All duration/easing/distance values come from `motionTokens`.** No inline numbers.
6. **All spring configs come from the `springs` map.** No inline `stiffness`/`damping`.
7. **`"use client"` on every file importing `motion/react`** (Next.js App Router - rules.md §5).
8. **No `window`/`navigator` at module level** - always typeof-guarded.

### Accessibility priority order
1. `prefers-reduced-motion: reduce` - disables transforms, caps transitions at opacity <= 0.2s. Provide both the JS path (`useReducedMotion` / a `useSafeMotion` hook that zeroes the `y` offset) and the CSS path (`@media (prefers-reduced-motion: reduce)` + Tailwind `motion-safe:` / `motion-reduce:` variants).
2. Low-end device - reduce duration, drop non-essential animations.
3. Design preference - everything else.
Motion must degrade gracefully: never disappear abruptly in a way that causes layout shift or breaks orientation. This operationalizes the rules.md §7 "`prefers-reduced-motion` honored" contract.

---

## 2. Pattern layer (the common UI animations)
*Source: ECC motion-patterns. Built entirely on the foundation tokens/springs - imports values, never redefines them.*

### The AnimatePresence contract (memorize this - it fails silently)
For any enter/exit animation, **all three** must be true or the exit silently never fires:
1. `AnimatePresence` wraps the conditional render.
2. The direct child has a stable `key`.
3. The child has an `exit` prop (always define `exit` whenever you define `initial` + `animate` - an animation without an exit is incomplete).

### AnimatePresence `mode` - always set it explicitly
The default `"sync"` overlaps enter and exit, which is wrong for most UI:
- `"wait"` - exit finishes before enter starts. **Modals, toasts, page transitions, content swaps.**
- `"sync"` - enter/exit overlap. Only when overlap is intentional (crossfade carousels, stacked notifications).
- `"popLayout"` - exiting element pops out of flow immediately, remaining items reflow to fill. **Lists, tabs, dismissible cards.**

### Pattern selection
| Situation | Pattern |
|---|---|
| Element appears / disappears | `AnimatePresence` (+ correct `mode`) |
| List loading in sequence | Stagger variants (parent `staggerChildren`, child variants) |
| Navigating between routes | Page-transition wrapper keyed on `usePathname()`, `mode="wait"` |
| Element changes size in place | `layout` prop (small isolated shifts only) |
| Same element across contexts | `layoutId` (unique per mounted instance) |
| Enter when scrolled into view | `whileInView` + `viewport={{ once: true }}` |
| Value tied to scroll position | `useScroll` + `useTransform` |
| Hover / tap feedback | `whileHover` / `whileTap` |

### Pattern-layer rules
- **Stagger interval 0.05s-0.10s.** Below feels mechanical, above feels sluggish. Cap it even on long lists.
- **`layout` only on small, isolated shifts** (single element, under roughly 5 children / <~300px change). Large subtrees or full-viewport containers get explicit `x`/`y` transforms or CSS Grid/Flex transitions - Framer's layout animation measures positions and the measurement cost causes jank + CLS at scale. For a moving element across a large reflow, use `layoutId` on the specific child only. Use `layout="position"` on text inside an expanding container to stop the reflow from animating the text.
- **Page transitions use `mode="wait"`** keyed on the pathname.
- **Scroll reveals use `viewport={{ once: true }}`** - repeating on scroll-out distracts rather than informs.
- **Scroll-linked values** via `useScroll().scrollYProgress` fed through `useTransform` (e.g. a progress bar `style={{ scaleX: scrollYProgress }}`, or parallax `useTransform(scrollYProgress, [0,1], [0,-80])`).

### Modal essentials (non-negotiable, ties to rules.md §7 modal contract)
A motion modal must always include: **focus trap**, **Escape closes**, **scroll lock** (`document.body.style.overflow = "hidden"` with cleanup), **`role="dialog"` + `aria-modal="true"` + `aria-labelledby`**, and **`AnimatePresence mode="wait"`** so exit completes before any next modal enters. The animation is on top of the rules.md §7 contract, never a substitute for it.

---

## 3. Advanced layer (drag, gestures, text, SVG, imperative)
*Source: ECC motion-advanced. Requires the foundation layer. Use when the pattern layer is not enough.*

### The reactive-value primitives
- **`useMotionValue` + `useTransform`** compute derived values **without re-rendering** - e.g. a drag `y` value driving `opacity` every frame with no setState. This is the motion equivalent of "derive, don't store" (rules.md §4 rung 1). Motion values are SSR-safe and do not cause hydration errors. Never `new MotionValue(0)` in render - always `useMotionValue(0)`.
- **`useSpring`** smooths a motion value over time with physics (cursor follower, pointer-tracked value) - use it for continuous per-frame values; use a spring *transition* (`transition: springs.*`) for discrete state changes.
- **`useAnimate`** returns `[scope, animate]` for imperative multi-step sequences with `async/await`. Interrupt-safe: calling `animate()` mid-flight cancels the previous run. The scope ref must be attached to a mounted DOM element (calling before mount throws silently).

### Advanced-layer rules
1. **Test drag/gesture on touch devices**, not just mouse - feel and thresholds differ.
2. **Infinite animations must pause when `document.visibilityState === "hidden"`** - background tabs must not burn GPU/CPU. (Spinner, shimmer, pulse all need a `visibilitychange` listener.)
3. **Swipe/dismiss thresholds are explicit and combine offset + velocity** - never infer intent from velocity alone (`if (info.offset.y > 120 || info.velocity.y > 500) onClose()`).
4. **`useAnimate` scope ref attached to a mounted element** before any `animate()` call.
5. **Never recreate motion values on render** (`useMotionValue`, not a fresh constructor).
6. **All values from `motionTokens`** - no inline numbers.
7. **Every custom hook cleans up** - each `addEventListener` needs a matching `removeEventListener` in the effect return; each `controls`/`animate` loop needs `.stop()` on unmount. (This is the rules.md §6 strict-mode / effect-cleanup discipline.)
8. **SVG morphing requires equal path command counts** - mismatched command structures snap instead of interpolating; normalize first.

### Advanced API map
Drag-with-physics -> `drag` + `dragTransition: springs.release`; reorderable list -> `Reorder.Group`/`Reorder.Item`; dismiss-on-drag -> `drag="y"` + `onDragEnd` offset/velocity check; swipe -> `drag="x"` + same; long press -> a `useLongPress` pointer-timer hook; value smoothed -> `useSpring`; value derived -> `useTransform`; multi-step sequence -> `useAnimate` async; text entering word-by-word -> stagger on `inline-block` spans; SVG draw-on -> `pathLength` 0->1; SVG circular progress -> `strokeDashoffset` tween; counter -> imperative `animate(0, to, { onUpdate })` with `controls.stop` cleanup. Loaders (spinner, shimmer skeleton, pulse dot, progress bar, button loading state) all follow rule 2 (visibility pause) + rule 7 (cleanup).

---

## 4. Debugging + QA checklist
*Source: ECC motion-ui. Run before any motion deliverable is "done".*

**When animations break, check first:** wrong import (mixing `motion/react` + `framer-motion`); missing `"use client"` (Next App Router); missing `key` on `AnimatePresence` children; hydration mismatch (initial state differs SSR vs client); `layout` misuse on a large container; state-driven animation not firing (dependency arrays).

**Motion Definition of Done (additive to the rules.md Definition of Done):**
- No CLS introduced by the animation.
- Keyboard still works; focus trapped in modals; ARIA roles correct (`role="dialog"`, `aria-modal`).
- Reduced motion respected (both `useReducedMotion` and the CSS media query).
- No hydration warnings in Next.js (`initial` matches server output).
- Animations stop cleanly on unmount - no leaked listeners or running loops.
- `AnimatePresence mode` set explicitly at every usage site.
- Every value sourced from `motionTokens`/`springs` - no inline numbers in component files.

---

## Where this plugs into existing methodology
- Stack default ("Framer Motion for complex animation, CSS transitions for micro-interactions") - this file is the methodology behind that one-liner.
- rules.md §6 (perf) - "never animate layout properties", "animate the wrapper", profile-first, effect cleanup, hydration rules all reappear here as motion rules.
- rules.md §7 (a11y) - `prefers-reduced-motion` honored, modal focus-trap/Escape/scroll-lock/roles. The motion modal sits on top of the §7 contract.
- rules.md §5 (Next App Router) - `"use client"` on motion files, SSR-safe initial states.
- verification-and-tokens.md §4 (token pipeline) - the `motionTokens`/`springs` map is the animation analogue of design tokens: one home, never literals.

## Non-goals (what this system does not cover)
CSS-only / Tailwind `animate-*` without `motion/react`; other JS animation libs (GSAP, anime.js); Canvas/WebGL (Three.js, Pixi); full external-state drag-and-drop systems (dnd-kit, react-beautiful-dnd); game-loop / frame-by-frame animation; and the *design* decision of what to emphasize (a design concern, not a code constraint). For Vue/Angular/Nuxt animation, see vue-angular-and-nuxt.md - the SSR-safe + reduced-motion principles transfer, but the API is the framework's own (Vue transitions, Angular animations).
