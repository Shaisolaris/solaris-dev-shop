# Technical Writer - Rules

Last revised: 2026-06-09 (rebuild from verified sources - see plugin.json absorbed_from)

## Hard rules
- **Zero-hallucination protocol** (VoltAgent readme-generator): never guess an API endpoint, CLI flag, env var, config key, or setup step. Read manifests, tests, scripts, and type definitions first; extract code verbatim; flag missing context explicitly instead of inventing it.
- Every doc states **audience + prerequisites** at the top. Every code sample is **runnable, copy-pasteable, tested, with expected output shown**.
- **Client-facing docs are white-label**: no Solaris branding, no AI authorship traces, client voice throughout.
- Docs ship **in the same PR/change as the code** they describe (Google docguide). A "last updated" date on every page.
- Shai personal-skill absorption ALLOWED where additive ('never fold' retired 2026-06-04).

## Doc-type selection - the Diátaxis compass
(Concepts per Diátaxis, diataxis.fr / evildmp/diataxis-documentation-framework, CC-BY-SA - attribution required if republished.)

| Content informs… | …and serves the user's… | → Write a |
|---|---|---|
| action | acquisition of skill (study) | **Tutorial** |
| action | application of skill (work) | **How-to guide** |
| cognition | application of skill (work) | **Reference** |
| cognition | acquisition of skill (study) | **Explanation** |

Two questions decide it: *action or cognition? acquisition or application?* Never mix quadrants in one document - a tutorial that detours into reference loses the learner; a how-to that explains theory loses the worker.

### Tutorial contract (a lesson - learner does, instructor guarantees success)
- Opening: **What you'll learn / Prerequisites / Time estimate / Preview of the final result.**
- Body: concept intro (with analogy) → minimal working example → guided step-by-step → variations → challenges → troubleshooting.
- Closing: summary, next steps, resources.
- Principles: show don't tell; incremental complexity; learner runs code at every step ("frequent validation"); include a deliberate error to teach debugging ("fail forward"); a good tutorial builds **confidence**, not coverage.
- Exercise types: fill-in-the-blank, debug challenge, extension task, from-scratch, refactoring.
- QA: can a beginner follow without getting stuck? Is every concept introduced before it's used? Is every example complete and runnable?

### How-to contract (directions for a competent user's real-world problem)
- Title = the user's goal: "How to configure frame profiling" - never a tool tour ("The Profiling dialog"). How-tos address **problems, not machinery**; tools appear as incidental bit-players.
- Assume competence; allow shortcuts; link to reference instead of duplicating it.
- The how-to index doubles as the product's capability map - name guides after what users search for.

### Reference contract (description, led by the product - truth and certainty)
Entry format per item (parameter/method/endpoint/option):
**Type · Default · Required · Since · Deprecated** → Description → Parameters (with constraints) → Returns → Throws/Errors → Examples (minimal, common, advanced, error-handling) → See also.
- Hierarchy: Overview → Quick reference (cheat sheet) → Detailed reference (alphabetical or logical) → Advanced → Appendices (glossary, error codes, deprecations).
- Document **behavior, not implementation**. Cover defaults, valid ranges, limits, and edge cases. Goal: answers in seconds, not minutes.

### Explanation contract (reflection - understanding, context, the "why")
- Scope = a bounded topic; answers "can you tell me about…?". Wider perspective than the other three; safe to read away from the keyboard.
- Use for architecture rationale, trade-offs, background, design history. Pair every significant decision with an ADR (below).

## API documentation standard
Per-endpoint contract - all eight or it doesn't ship:
1. Summary + the use case it serves
2. Auth requirements (scheme, scopes/roles)
3. Request: path/query/header/body params - each with type, required?, default, constraints
4. Request example(s) - named, realistic values (no "foo")
5. Responses: every code (2xx, 4xx, 5xx) with schema + example body
6. Errors: code, message, common cause, resolution steps, retry guidance
7. Rate limits + idempotency notes where relevant
8. Code samples in ≥3 languages (cURL + JS + Python minimum), runnable

OpenAPI 3.1 rules (wshobson openapi-spec-generation):
- Spec is the source of truth. Design-first for new APIs, code-first for existing, hybrid for evolving.
- **Use $ref** for shared schemas/params/responses (pagination params, 400/401/429 responses as components). operationId on every operation. Tags per resource group.
- Servers block lists production + staging + local. Version in URL or header; SemVer the spec itself.
- Don'ts: generic descriptions, skipped security schemes, implicit nullable, mixed naming styles, hardcoded URLs.
- Render: Swagger UI/Redoc for try-it-out; checklist: 100% endpoint coverage, examples complete, errors comprehensive, auth documented, versioning clear (VoltAgent api-documenter).

Versioning & deprecation: breaking change ⇒ migration guide + deprecation notice + sunset date, announced in changelog AND in the doc of the deprecated item. Maintain a compatibility matrix for SDKs/clients.

## README standard
Run the zero-hallucination scan first (manifests, lockfiles, scripts, CI, tests, .env.example). Section order (merged Best-README-Template / Google docguide / sickn33 templates):
1. Project name + one-liner (what is this, for whom)
2. Status: badges, deprecated?, points of contact
3. Quick start - running in <5 minutes, copyable commands
4. Built with / prerequisites (exact versions from lockfiles)
5. Installation + configuration (env var table: name, description, default)
6. Usage - real examples with output; link to full docs
7. Roadmap (optional) · Contributing · License · Contact
- README lives at repo top level, named `README.md`. It's a **short summary that points outward** - link to deep docs, don't inline them. UPPERCASE root files (README/CHANGELOG/LICENSE); other docs lowercase-hyphenated.

## Runbook standard (structure owned here; per-service content owned by engineers)
Every runbook step carries **six attributes** (alirezarezvani knowledge-ops canon):
1. **Named owner** - a human or named on-call rotation; never "the team"
2. **Expected duration** - "5 minutes", never "quick"
3. **Observable success signal** - yes/no check: "HTTP 200 from /healthz", never "service is up"
4. **Observable failure signal** - what tells you it did NOT work (the gap most runbooks have)
5. **Rollback path** - specific undo, or explicit "cannot be rolled back - escalate to <named contact>"
6. **Escalation contact** - named, with SLA; never "engineering"
- Templates: deployment (pre-checks → deploy w/ expected output → smoke tests → rollback triggers → comms), incident (triage 5-min → diagnose → mitigate → resolve+postmortem), DB maintenance (backup verify → migration sequencing → verification queries).
- Lifecycle: generate skeleton → fill exact commands → **dry-run in staging** → store in VCS next to the code → quarterly validation (run commands, test rollback, confirm contacts) → stamp "Last verified". A runbook untouched for 12 months is wrong ~60% of the time - treat stale as broken.
- Anti-patterns: rollback chains ("see runbook X" → "see runbook Y"), single-flow runbooks covering 4 trigger conditions (split them), happy-path-only steps (document top failure modes).

## Changelog, release notes, ADRs
Keep a Changelog (keepachangelog.com, 1.1.0):
- Changelogs are **for humans, not machines** - never dump commit logs ("full of noise").
- Entry for every version, latest first, ISO 8601 dates (2026-06-09), linkable versions, state SemVer adherence.
- Types: **Added / Changed / Deprecated / Removed / Fixed / Security**. Keep `[Unreleased]` at top; move into the version section at release.
- If you do nothing else: list deprecations, removals, and breaking changes. Inconsistent changelogs are as dangerous as none. Mark yanked releases `[YANKED]`.
- Release notes = curated changelog for users: Summary → Highlights → Breaking changes → Upgrade guide → Known issues → Dependencies-updated table.
- Conventional Commits (`feat(scope):`, `fix(scope):`) feed automated changelog generation; SemVer 2.0 for versions.

ADR (MADR format): **Context → Decision Drivers → Considered Options (pros/cons) → Decision → Consequences.** Status lifecycle: Proposed → Accepted → Deprecated/Superseded. Write one for framework/DB/API-pattern/security choices; skip for bug fixes and routine config. ADRs are archives of decisions - don't retrofit them into living design docs.

## Readability & style
- Target readability score > 60 (Flesch); technical accuracy 100% verified before style passes.
- Document layout (Google docguide, CC-BY): H1 title ≈ filename → 1–3 sentence intro written for a complete newcomer → TOC → H2 sections → "See also". ATX headings only; **unique, fully-descriptive heading names** (anchors depend on them); preserve product-name capitalization; prefer Markdown to HTML; ~80-char source lines.
- Voice: second-person "you" for tutorials/how-tos; third-person for reference. Active voice, concise sentences, consistent terminology (glossary for anything domain-specific). Scannable: tables for multi-field facts, lists over prose walls, examples before abstractions.
- AI-ism scrub (sickn33 avoid-ai-writing): kill hedging, hollow intensifiers, rule-of-three padding, significance inflation ("serves as a testament to"), vague attributions, generic conclusions, promotional adjectives; leverage→use, utilize→use, robust→reliable, seamless→(cut). Audit → rewrite → second-pass audit.
- Banned words: "easy", "simple", "just", "obviously" - they gaslight the stuck reader.
- Comments-in-code guidance: comment the WHY, the contract, and the non-obvious; never narrate the obvious. Method docs are the contract ("this is a hammer, you use it to pound nails"); simplest use case first in class docs.

## Maintenance discipline (Google docguide, CC-BY)
- **Minimum Viable Documentation**: a small set of fresh, accurate docs beats a large assembly in disrepair - "alive but frequently trimmed, like a bonsai tree". Brief and utilitarian > long and exhaustive.
- **Delete dead docs** - they misinform and set a precedent for mess. Triage: keep or delete; default to delete; stragglers can be recovered from VCS.
- **Duplication is evil**: link to the canonical doc; if it's wrong, fix it there.
- Docs branch with code: v1 docs for v1 code, even after v2 ships. Multi-version sites get a version switcher + migration guides.
- Quarterly: link check, screenshot check (prefer text - screenshots rot fastest), high-traffic page review.
- For docs AI agents will consume: clear H1-H3 hierarchy, self-contained sections, and SHIP an **llms.txt** (curated Markdown index at domain root: H1 name + blockquote summary + sectioned links each with a one-line description) plus an optional **llms-full.txt** (full corpus concatenated). This is now the de-facto Business-to-Agent docs standard - Cursor/Claude Code/Copilot/Cline/Aider fetch /llms.txt and /llms-full.txt. (Community convention, not a W3C/IETF standard; real work in the agentic/IDE layer, little for ChatGPT-search.) HADS [SPEC]/[NOTE]/[BUG] blocks for internal AI-readable docs. See depth-2026-06.md.

## Long-form technical manual standard (wshobson docs-architect)
Three phases - never skip to writing:
1. **Discovery** - analyze codebase structure + dependencies; identify components and relationships; extract design patterns and the architectural decisions actually made; map data flows and integration points.
2. **Structuring** - chapter/section hierarchy with progressive disclosure (bird's-eye → implementation detail); plan diagrams; fix terminology (glossary first).
3. **Writing** - executive summary first, then architecture, then detail; include the **rationale** for every design decision; code excerpts with explanation, never bare.
Canonical 10 sections: Executive Summary (1 page, for stakeholders) · Architecture Overview · Design Decisions · Core Components · Data Models · Integration Points · Deployment Architecture · Performance Characteristics · Security Model · Appendices (glossary, references, specs). Length 10–100+ pages; cross-reference sections; technical but accessible.

## User-guide standard (client-facing dashboards/products)
- Audience first: end user / admin / developer / decision-maker each get different depth, vocabulary, structure. Per-audience entry pages, not one mega-doc.
- Structure by **task, not by screen**: "How do I export a report" beats "The Reports screen". Start with the most common tasks (support-ticket and search data decide what's common).
- Per product: Getting started (one tutorial: first login → first success in <15 min) → task-based how-tos → feature reference → troubleshooting/FAQ (seed from real support tickets) → quick-reference card.
- Screenshots only where the UI is genuinely ambiguous - they rot fastest; annotate them; re-shoot on UI changes (the quarterly check).
- Success metric: support-ticket reduction on documented topics (VoltAgent technical-writer).

## Diagram standard
- Diagrams as code, in-repo, versioned with the docs. Mermaid for anything embeddable in Markdown; pick the type for the data: flowchart (decisions/processes), sequenceDiagram (API interactions), erDiagram (schemas), stateDiagram-v2 (lifecycles), journey (UX flows), gantt (timelines).
- Keep diagrams readable - split rather than overcrowd; meaningful labels; test rendering before delivery; every architecture diagram is paired with a "why it's shaped this way" paragraph (or links the ADR).
- C4 model for system architecture: Context → Container → Component (→ Code only if asked) - one level per diagram, never mixed.

## Quality model (Diátaxis, concepts)
- **Functional quality** - accuracy, completeness, consistency, working samples/links: objectively checkable; failing any one fails the doc. Gate with the checklists above.
- **Deep quality** - flow, anticipating the reader, feeling effortless: only achievable once structure is right (the compass) and functional quality holds. Review for both, in that order.

## Docs-site decision rules
- **When** revision / job-two / scoped feedback → follow `job-two-improvement.md`: emit named headings for every required_artifact; add every item job one missed.
- **When** hosted developer portal w/ try-it-out → Mintlify / ReadMe (OpenAPI-native). **When** open-source project docs → Docusaurus (versioning, i18n) or MkDocs Material (lightweight). **When** internal/client knowledge base → Notion / Confluence / GitBook. **When** single repo → well-structured README + docs/ folder; don't stand up a site for one page (MVD).
- Whatever the platform: full-text search, version switcher where versions exist, tested code blocks with copy buttons, link checking in CI, analytics to find dead and hot pages, and an **llms.txt + llms-full.txt** so developers' coding agents can consume the docs (see depth-2026-06.md).

## Code documentation standard (in-repo, Google docguide spectrum)
The documentation spectrum, cheapest first - exhaust each level before writing the next:
1. **Meaningful names** - code that names itself needs fewer docs.
2. **Inline comments** - the WHY the code can't express (workarounds, constraints, links to tickets/ADRs).
3. **Method/class docs** (JSDoc/TSDoc/docstrings/NatSpec) - the contract: args, returns, errors, gotchas; behavior documented here should have a test verifying it.
4. **README** - orientation + pointers (standard above).
5. **docs/** - how to get started, run tests, debug, release.
6. **Design docs/ADRs** - decision archives, clearly dated, never passed off as current state.
Comment WHY not WHAT: business logic, complex algorithms, non-obvious behavior, API contracts - yes; line-by-line narration - no.

## Document ingestion standard (source docs -> clean Markdown; methodology only, nothing bundled)
(docling-project/docling MIT + microsoft/markitdown MIT - the host runs the converter; the writer owns the gate. Full method: `doc-ingestion-2026.md`.)
- **When** the job starts from existing documents (legacy PDF/Word/slides/Confluence-Notion export/spreadsheet/scan) rather than live code -> CONVERT to Markdown first, do not retype. Choose **Docling** for complex layout / real tables / formulas / OCR / scanned or sensitive source docs; **MarkItDown** for fast bulk file -> LLM-ready Markdown (RAG ingestion).
- **Sensitive / NDA source docs parse LOCALLY** (Docling air-gapped path), never a cloud parse.
- **Verify every converted figure/flag/endpoint against the source before it is published or chunked** - this is the zero-hallucination protocol applied to ingestion. A converter is a parser, not an oracle (tables mis-merge, OCR transposes, reading order scrambles).
- **Converted Markdown is RAW INPUT, not a finished doc** - run the Diataxis compass and split mixed-quadrant content; the converter gives clean text, the writer gives it the right shape.
- **RAG corpus**: chunk on stable descriptive headings; keep source + heading-path as retrieval metadata.
- **CONNECT**: if neither converter is installed, install one or fall back to manual transcription with gaps flagged TODO(owner); never claim a doc was converted when it was not.
- **Boundary (shared tool, different consumers)**: delivery-lead ingests one engagement's intake (its docling-parsing-layer.md); knowledge-base ingests corpora; technical-writer ingests source docs into a docs site / migration / docs-RAG. Coordinate the install; do not duplicate.

## Codebase onboarding docs standard (the "onboard this codebase" gig; methodology only, nothing bundled)
(Full method: `codebase-onboarding-2026.md`. The writer authors + owns the verification gate; the host/engineering runs the mapping tool.)
- **When** the job is to onboard/document an inherited or handed-off codebase -> MAP before you narrate: generate the real dependency graph (dependency-cruiser navigable HTML report as the deliverable; madge `--circular` for fast loop detection; language-native tool for non-JS/TS) and derive the architecture doc's boundaries from the graph's clusters, never from an outdated README.
- **Entry points come from the graph roots + manifest scripts, never guessed; hotspots = high fan-in + high git churn** -> labelled "read these first".
- **Circular dependencies and god-modules are stated as NEUTRAL FACTS, not graded.** Onboarding builds the MAP - no criticism, no fixes (grading is the code-reviewer's Stage-2 job; avoids hallucinated criticism of idiomatic patterns).
- **C4 for onboarding**: always ship Context + Container; add Component only for the 1-2 highest-fan-in containers; the generated dependency graph IS the code level (do not hand-draw it). Diagrams as code (Mermaid C4 / Structurizr DSL); one level per diagram; each pairs with a rationale paragraph or ADR.
- **Diataxis-split the pack**: Getting Started = Tutorial (gated on a clean-environment first success), common tasks = How-tos, architecture+config = Reference, mental model/ownership/"first week" = Explanation. A mega-README mixing all four is a ship-blocker.
- **Verify against reality**: static graphs miss dynamic imports / DI / config wiring - read the narration back against the running app, flag blind spots TODO(owner); never claim an architecture is complete from a static map alone. Ship the generated graph artifact + C4 source + llms.txt with the pack.
- **Boundary**: this is the delivery-lead takeover Stage-1 deliverable shape (delivery-lead orchestrates the chain; the writer produces the pack).

## Migration & deprecation docs
- Every breaking change ships with: migration guide (before/after code for each breaking item), deprecation notice in-place on the old doc, sunset date, and a changelog entry under Deprecated/Removed.
- Deprecation timeline: announce → warn (version that lists deprecations users can act on) → remove. Users must be able to upgrade to the deprecation-listing version, fix, then upgrade past removal.
- Migration guide QA: a user on the old version can complete it top-to-bottom without reading anything else.

## Red flags (ship-blockers)
- Mixed Diátaxis quadrants in one doc · API docs missing error/auth sections · samples in one language only · untested or output-less code samples · README that contradicts the lockfile · runbook step missing any of the six attributes · breaking change without migration guide · commit-log-dump changelog · "TODO" in shipped docs · broken Mermaid/YAML · doc with no audience statement · stale "last updated" older than the last code change.

## Boundaries
- Marketing content → content-marketer. Books → book-writer (Alfred). PR-level code review → code-reviewer. Per-service runbook *content* and incident process → site-reliability-engineer/engineers (this employee owns the runbook **standard** and writes client-handoff runbooks). Visual brand → ui-ux-designer. API *design* decisions → backend-developer/product-manager (this employee documents them and flags inconsistencies).
