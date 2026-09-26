# Technical Writer - Codebase Onboarding Docs depth (2026-06-20, methodology only, no code bundled)

The ELITE bar for a "Codebase Onboarding Docs" gig: a stranger could deploy and contribute inside a day, the architecture picture is VERIFIED against the real import graph (not narrated from a README), every diagram is one C4 level, the doc set is sorted by Diataxis so a getting-started tutorial is never polluted with reference dumps, and a coding agent can consume the whole thing via llms.txt. This file adds the two pieces the writer did not own: (1) auto architecture/dependency MAPPING as the evidence base, and (2) C4 + Diataxis depth applied specifically to an onboarding pack.

Scope: the writer AUTHORS and OWNS THE VERIFICATION GATE. The host/devops runs the mapping tools. Nothing here is installed or bundled. This is the zero-hallucination protocol pointed at architecture instead of endpoints.

---

## 1. Auto architecture / dependency mapping (the evidence base for the architecture doc)

The architecture overview must be derived from the actual dependency graph, not reconstructed from memory or trusting an outdated README. Generate the map first, read it, THEN write.

### Tool selection (JS/TS first, language-agnostic fallback)
- **madge** (pahen/madge, MIT) - fastest first pass for JS/TS. `npx madge ./src` prints a nested dependency list; `npx madge ./src --image graph.svg` (needs Graphviz) renders it; `npx madge --circular ./src` lists circular dependencies. Colour code in the visual: green = no deps, purple = has deps, red = circular. Use madge to get oriented in minutes and to find import loops.
- **dependency-cruiser** (sverweij/dependency-cruiser, MIT) - the deeper pass and the one to standardize on for a deliverable. It is a graph viewer AND a policy engine: `depcruise -T dot src | dot -T svg > arch.svg` for the diagram; `depcruise -T dot src | dot -T svg | depcruise-wrap-stream-in-html > arch.html` for a NAVIGABLE HTML report (hover a module, see incoming/outgoing deps, directory boundaries drawn in). It supports multiple languages, encodes architectural rules in config (e.g. "router must not import from test", "no module may import upward across a layer"), and fails CI when a boundary is crossed. For an onboarding deliverable its directory-grouped HTML report is the single best artifact to hand a new contributor.
- **skott** (antoine-coulon/skott) - honorable-mention "new madge"; navigable report + claims unused-dependency / dead-code detection. Optional.
- **Non-JS stacks**: madge/dep-cruiser are JS/TS-centric. For other languages the writer still owns the VERIFICATION gate but the map comes from the stack's native tool (the engineering employee runs it): pydeps / import-linter (Python), go mod graph + goda (Go), jdeps (Java), the framework's module graph. The doctrine is identical: machine-generated graph -> writer verifies and narrates -> one C4 level per diagram.

### How the map becomes the doc (the discipline that makes it elite)
1. **Generate before narrating.** Run the dependency map and read it. The architecture doc's container/component boundaries come FROM the graph's clusters, not from what the README claims the architecture is.
2. **Circular dependencies and god-modules are FACTS, not opinions.** A red/circular edge or a node every other module imports is a verified observation - state it neutrally in the architecture doc ("module X is imported by N others; circular dependency between A and B") without grading it. Grading/criticism is the code-reviewer's job; onboarding builds the MAP, no criticism (this preserves the delivery-lead Stage-1 "no fixes, no hallucinated criticism of idiomatic patterns" rule).
3. **Entry points come from the graph's roots + the manifest scripts**, never guessed. Cross-check the dependency roots against package.json scripts / Procfile / Dockerfile CMD / main field.
4. **Hotspots = high fan-in (many importers) and high churn (git log)**. Call these out in the file-structure overview as "read these first" - they are where a new contributor's questions land.
5. **Ship the generated graph as an artifact** in the onboarding pack (the dependency-cruiser HTML report or an SVG), embedded next to the C4 diagrams. A living, generated graph beats a hand-drawn box diagram that rots.
6. **VERIFY the graph against reality before publishing** (zero-hallucination applied to architecture): a generated graph can miss dynamic imports, DI containers, config-driven wiring, and runtime-only edges. Read the narrated architecture back against the running app / entry points; flag anything the static graph cannot see as TODO(owner). Never claim an architecture is complete from a static map alone.

---

## 2. C4 model depth for an onboarding pack

The writer already knows "one C4 level per diagram, Context -> Container -> Component (-> Code only if asked)". The onboarding-specific depth:

- **Always ship Context + Container; add Component only for the 1-2 hotspot containers a new contributor will touch first.** Code level almost never (the generated dependency graph IS the code level - do not hand-draw it).
- **Context (Level 1):** the system as one box, the people/roles who use it, and the external systems it talks to (payment gateway, auth provider, third-party APIs, the client's other systems). This is the "what is this and who is it for" page - it leads the Getting Started doc.
- **Container (Level 2):** the deployable/runnable units (web app, API service, worker, database, cache, CDN, queue) and the protocols between them. This is the spine of the Architecture doc. Each container box pairs with a "what does this do / where does it live in the repo" line - tie every container to a top-level directory.
- **Component (Level 3, selective):** inside the one or two containers with the highest fan-in from the dependency map. Derive the component boundaries from the graph's clusters.
- **Model-as-code option:** Structurizr DSL (one model, many diagrams, the C4 reference implementation) or Mermaid C4 (`C4Context`/`C4Container`) so the diagrams live as text-in-the-repo and stay current. Prefer Mermaid for a lightweight repo, Structurizr DSL when the client wants living architecture docs that evolve with the system. Store the diagram source in the docs/ folder; never ship only a flattened PNG.
- **Every C4 diagram pairs with a "why it's shaped this way" paragraph** (or links the relevant ADR) - the existing rule, enforced harder here because onboarding readers need rationale, not just topology.
- **One level per diagram, never mixed** - a Container diagram with stray code-level detail is a ship-blocker.

---

## 3. Diataxis depth for an onboarding pack (the part most onboarding docs get wrong)

A codebase onboarding pack is a MULTI-QUADRANT deliverable, and the elite move is keeping the quadrants separate inside one pack:

| Onboarding artifact | Diataxis quadrant | Rule |
|---|---|---|
| Getting Started ("clone -> running locally in <30 min") | Tutorial | guaranteed first success; "you"; no reference dumps; ends at a verified running app |
| Common tasks ("add an endpoint", "run the tests", "ship a change") | How-to | problem-titled not screen-titled; brisk; assumes setup done |
| Architecture overview + container/component reference + env/config table | Reference + Explanation (split) | the C4 + dependency-map FACTS are Reference; the "why it's shaped this way" is Explanation - keep the discursive rationale OUT of the lookup tables |
| "Where things live / who owns what / first week" | Explanation | discursive orientation; the mental model |

- **The cardinal onboarding sin is the mega-README** that mixes a tutorial, an architecture essay, and a config reference on one page. Split it: a getting-started tutorial that GUARANTEES a running app, separate how-tos per common task, a reference section for the architecture facts and config, and an explanation page for the mental model and ownership.
- **Getting Started is a tutorial, so it is gated on first success**: another engineer clones into a clean environment and reaches a running app following ONLY that doc, before it ships (same gate as the README/handoff workflows). Every command run, every gap flagged TODO(owner) - never invent an env var or a setup step.
- **Ship an llms.txt + llms-full.txt with the pack** so the new contributor's coding agent (and the owner's) can consume the onboarding docs directly - the architecture map, the getting-started, the how-tos - indexed for agent fetch (see depth-2026-06.md).

---

## 4. Boundary (who maps, who narrates, who criticizes)

- **technical-writer** owns the onboarding DOC pack: runs/consumes the dependency map, builds the C4 set, sorts by Diataxis, verifies, ships with llms.txt. Builds the MAP - no criticism, no fixes.
- **delivery-lead** ORCHESTRATES the takeover chain (Stage 1 onboarding -> Stage 2 audit -> Stage 3 migration); the writer's onboarding pack IS the Stage-1 deliverable shape. Same "no fixes on Day 1" rule.
- **code-reviewer** grades the architecture (circular deps as defects, god-modules as smells) in Stage 2 - the writer states them as neutral facts, the reviewer assigns severity.
- **engineering employees** run the language-native mapping tool when the stack is not JS/TS; the writer owns the verification gate regardless of who runs the tool.

CONNECT honesty: if the mapping tool is not installed, the host installs it (`npm i -g dependency-cruiser madge`, plus Graphviz for rendering) or the writer falls back to manual entry-point tracing with every inferred edge flagged TODO(owner). Never claim an architecture was machine-mapped when it was hand-traced.

## Sources (verified 2026-06-20, methodology only)
- sverweij/dependency-cruiser (MIT) - graph + policy engine, navigable HTML report, CI rule enforcement, multi-language.
- pahen/madge (MIT) - fast JS/TS dependency list + graph + `--circular`.
- antoine-coulon/skott - navigable report, unused-dep / dead-code claims (optional).
- C4 model (c4model.com) + Structurizr DSL (the C4 author's reference "models-as-code" tool) + Mermaid C4 - one model, many diagrams, living architecture for onboarding.
- Diataxis (CC-BY-SA, concepts w/ attribution) - the four-quadrant split applied to a multi-artifact onboarding pack.
