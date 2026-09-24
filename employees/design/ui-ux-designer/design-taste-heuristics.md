# Design "taste" heuristics - anti-slop, high-agency decision rules (methodology)

Absorbed 2026-06-14 from Leonxlnx/taste-skill (MIT, ~43.6k stars), the "anti-slop frontend framework for AI agents." Methodology only; no code bundled. License: MIT (clean). These are taste/judgment heuristics for landing pages, portfolios, and redesigns - the layer ABOVE our Design Intelligence database (which picks the style/palette/font) that stops the agent from shipping templated, generic-looking UI. Gate-0: the design-intelligence DB selects FROM options and runs the 1-to-10 a11y/quality priority checklist; this adds the "read the brief, infer the right direction, then deliberately reach past the LLM defaults" judgment layer plus the mechanical anti-slop pre-flight, which the DB does not carry.

## 1. Read the brief before generating (the Design Read)

Most LLM UI is bad because the model jumps to a default aesthetic instead of reading the room. Before any code, infer and state a one-line Design Read: "Reading this as: <page kind> for <audience>, with a <vibe> language, leaning toward <design system or aesthetic family>."

Signals to read first: page kind (landing / portfolio / redesign / editorial), the vibe words the user used, reference URLs/screenshots/competitor brands, the AUDIENCE (the audience picks the aesthetic, not the designer's taste), existing brand assets (for a redesign these are starting material not optional), and quiet constraints (accessibility-first, public-sector, regulated, trust-first commerce - these OVERRIDE aesthetic preference). If the brief is genuinely ambiguous, ask exactly ONE clarifying question, never a multi-question dump; if you can confidently infer, do not ask.

## 2. The three dials (type-scale rhythm, motion, spacing cadence)

After the Design Read, set three 1-to-10 dials; every layout/motion/density decision is gated by them. Baseline 8 / 6 / 4, overridden by the read.

- DESIGN_VARIANCE: 1 = symmetric 12-col grid, equal padding, centered; 4-7 = offset overlaps, mixed aspect ratios, left-aligned over centered; 8-10 = asymmetric/masonry, fractional grid (2fr 1fr 1fr), large empty zones. Asymmetric layouts above md MUST collapse to strict single-column below 768px.
- MOTION_INTENSITY: 1-3 = static, hover/active only; 4-7 = fluid CSS transitions + load-in cascades (transform/opacity); 8-10 = scroll-driven choreography (CSS animation-timeline or GSAP ScrollTrigger via motion values, never window scroll listeners). "Motion claimed, motion shown": if the dial is >4 the page must actually move; if you cannot ship working motion, drop the dial to 3 and ship clean static. Motion must be motivated (hierarchy / storytelling / feedback / state) - if you cannot name the reason in one sentence, drop the animation.
- VISUAL_DENSITY (the spacing cadence dial): 1-3 = art-gallery air, py-32 to py-48 section gaps; 4-7 = standard app spacing py-16 to py-24; 8-10 = cockpit, tight padding, 1px dividers instead of cards, mono figures for numbers.

Map vibe words to dial values (e.g. minimalist/Linear -> 5-6 / 3-4 / 2-3; premium consumer/Apple -> 7-8 / 5-7 / 3-4; agency/Awwwards -> 9-10 / 8-10 / 3-4; trust-first/public-sector -> 3-4 / 2-3 / 4-5). Overrides happen conversationally, not by editing a settings file.

## 3. Type-scale rhythm and font discipline

- Display/headlines default text-4xl md:text-6xl, tight tracking, tight leading; body text-base, relaxed leading, max ~65ch measure.
- Sans display is the default, not serif. The "creative brief = serif" reflex is the single most-tested AI tell. Serif is acceptable only when the brand names a serif OR the family is genuinely editorial/luxury/heritage AND you can articulate why this serif fits this brand. Inter is discouraged as a default (acceptable for neutral/Linear/public-sector); reach for Geist, Satoshi, Cabinet Grotesk, GT Walsheim, PP Neue Montreal first, with known pairings (Geist + Geist Mono, Satoshi + JetBrains Mono, etc.).
- Emphasis within a headline = italic/bold of the SAME font, never a random serif word dropped into a sans headline (mixed-family emphasis is amateur).
- Italic descender clearance: italic display words with descenders (y g j p q) clip at leading-none; use leading at least 1.1 plus a little bottom reserve, and audit every italic display word before shipping.

## 4. Color cadence

- Max one accent color, saturation under ~80% by default; neutral bases (zinc/slate/stone) with a single high-contrast accent. The "AI purple/blue glow" default is banned unless the brief asks for it.
- Color consistency lock: once an accent is chosen it applies to the WHOLE page; no stray blue CTA in section 7 of a warm-grey site.
- Premium-consumer palette ban: the warm-beige + brass/clay/oxblood + espresso default makes every premium-consumer site look identical. Rotate to a different family (cold luxury, forest, black-and-tan, cobalt+cream, terracotta+slate, monochrome+single pop) and never ship the same warm-craft palette twice in a row. Override only when the brand names those colors.
- One corner-radius scale per page; one theme per page (sections do not invert light/dark mid-scroll).

## 5. Layout anti-slop (hard rules)

- Hero fits in the initial viewport: headline max 2 lines, subtext max ~20 words / 3-4 lines, CTAs visible without scroll. A 4-line hero headline is a font-size error, not a copy-length error. Hero top padding cap ~pt-24. Max 4 text elements in the hero (eyebrow OR brand strip, headline, subtext, CTAs); trust strips / taglines / pricing teasers move to sections below.
- Eyebrow restraint (the #1 violated rule): the small uppercase wide-tracking label above headlines should appear at most once per 3 sections. Mechanical pre-flight: count "uppercase tracking" small-caps labels; if count > ceil(sectionCount / 3), it fails. Default to dropping the eyebrow entirely.
- Layout-family repetition ban: a layout family (3-col cards, full-width quote, split text-image) appears at most once per page; an 8-section page uses at least 4 different families. Zigzag image+text alternation caps at 2 in a row; the 3rd consecutive is a fail.
- Split-header ban (big left headline + small right explainer paragraph) by default; stack vertically instead. Bento grids need rhythm and exactly as many cells as content (no empty/blank tiles); at least 2-3 cells need real visual variation, not white-on-white text cards.
- Navigation renders on one line at desktop (condense/hamburger if it does not fit), height cap ~80px. Use CSS Grid over flexbox percentage math; min-h-[100dvh] not h-screen for full-height heroes.

## 6. Interactive states, content density, copy self-audit

- Implement full state cycles, never just the static success state: skeleton loaders shaped like the final layout, composed empty states, inline/contextual errors, tactile :active feedback. Button contrast check (WCAG AA) and CTA-wrap ban (label fits one line; 1-2 words for primary CTAs) are pre-flight fails. No duplicate-intent CTAs (one label per intent across nav/hero/footer). Labels above inputs, errors below, never placeholder-as-label.
- Cut content ruthlessly: short headline (<=8 words) + short sub (<=25 words) + one asset or one CTA per section. No data-dump tables on a marketing page; long lists (>5 items) get a real component (grouped 2-col, card grid, tabs/accordion, scroll-snap, carousel, marquee), not a longer bulleted list.
- Real visual assets: landing pages and portfolios are visual products. Use an image-gen tool first, real photography second (seeded placeholders described by section), and only as a last resort leave clearly-labeled TODO slots and tell the user. Div-based fake screenshots, hand-rolled decorative SVG illustrations, and plain-text wordmark logo walls are banned tells (use real brand SVGs, e.g. Simple Icons; logo wall = logos only, no category labels).
- Copy self-audit before ship: re-read every visible string and rewrite anything grammatically broken, with unclear referents, that sounds like AI wordplay, or that reads like an LLM trying to sound thoughtful. Plain functional copy beats cute AI copy. Fake-precise invented numbers (92%, 4.1x, 5.8mm) are banned unless from real data or labeled mock.

## 7. High-agency discipline (the meta-rules)

- Every rule here is CONTEXTUAL. None fires automatically. Read the brief, then pull only what fits.
- Anti-default discipline: do not reach for AI-purple gradients, centered hero over dark mesh, three equal feature cards, glassmorphism on everything, Inter + slate-900. These are the defaults; reach past them deliberately.
- Honesty rule: if the brief reads as a real design system (Fluent, Material 3, Carbon, Polaris, Atlaskit, Primer, GOV.UK/USWDS, Radix Themes, shadcn/ui), install and use the OFFICIAL package; do not recreate its CSS by hand or import its tokens then override 90% of them. One system per project. Label borrowed-inspiration aesthetics (glassmorphism, bento, "liquid glass") honestly as approximations.
- Em-dash ban: this skill bans the em-dash entirely (its single most-violated tell) in headlines, eyebrows, body, quotes, attribution, captions, button text, and alt text. Use the regular hyphen. This aligns with the Solaris-wide no-em-dash doctrine.

## CONNECT / pairing notes

- Pairs with the Design Intelligence database (design-intelligence/): the DB picks the style/palette/typography options and runs the a11y priority checklist; these heuristics decide whether the chosen direction is the RIGHT one for the brief and keep the execution off the LLM-default rails.
- taste-skill also ships image-generation skills (imagegen web/mobile, brandkit) for reference boards and an image-to-code pipeline; if a reference-board workflow is wanted the host can install them via `npx skills add https://github.com/Leonxlnx/taste-skill`. Methodology only here; no skill code vendored.
- Cross-reference: frontend-developer implements the design; this taste layer is what frontend should QA against to avoid shipping slop.
