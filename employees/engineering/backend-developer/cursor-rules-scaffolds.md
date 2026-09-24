# Cursor Project Rules scaffolds - the per-stack .cursorrules / .mdc convention (methodology)

Shared engineering reference. Added 2026-06-14 (LIGHT absorb) from PatrickJS/awesome-cursorrules (CC0-1.0, ~40k stars). Methodology + pointer only; NO templates bulk-imported. This file is owned by backend-developer but is the shared engineering entry point; frontend-developer and full-stack-developer point here. Gate-0: no cursor-rules content existed anywhere in engineering before this.

## What this is and why it matters to us

When a client project (or our own) runs on Cursor AI, "Cursor Project Rules" are the per-project guidance files that steer the editor's code generation toward the project's stack, architecture, naming, libraries, and review expectations. They are the Cursor-native equivalent of an AGENTS.md / AGENTS.md convention layer: reusable project knowledge given to the AI up front so suggestions fit the codebase on the first pass instead of being re-corrected each time. For a white-label shop, dropping a good rules file into a client repo is a cheap, high-leverage way to make any developer's (human or AI) output consistent with that project's conventions.

## The convention (modern format)

- Rules live as Markdown-based `.mdc` files in `.cursor/rules/` (the modern Project Rules format). The older single-file `.cursorrules` at repo root is the legacy form; prefer `.cursor/rules/*.mdc` for new work because it is scoped and composable (one file per concern - framework usage, security, testing conventions, workflow), and shared `.cursor/rules/*.mdc` keeps AI assistance aligned across all contributors.
- A rule file is plain prose guidance: local architecture, preferred libraries, common methods/idioms, domain constraints, naming/structure conventions, and review expectations. It is not code; it is the project's "how to behave here" brief for the AI.
- Scope rules narrowly. A focused per-concern rule that the editor can attach to the relevant file types beats one giant monolithic rules blob.

## How to use the awesome-cursorrules repo (mine selectively, do not vendor wholesale)

The repo is a curated INDEX of community `.mdc` rule files organized by category: frontend frameworks/libraries, backend and full-stack, mobile, games/graphics, CSS/styling, state management, database and API, testing, hosting/deployments, build tools, language-specific, security, documentation. Treat it as a starting-point catalog, not a drop-in product.

Workflow when a client/project is on Cursor:
1. Identify the project stack (e.g. Next.js + Tailwind, FastAPI, Laravel, NestJS, .NET, React Native, etc.).
2. Browse the matching category in the repo and read the candidate `.mdc` file(s) for that stack.
3. Mine selectively: lift only the rules that actually match this project's real conventions and tooling. Do not paste 500 templates into a repo, and do not adopt a rule that contradicts the project's existing patterns. Community rules vary in quality - review each before adopting.
4. Adapt to the project: rewrite the rule to name THIS project's libraries, versions, architecture, and review bar. A generic "use best practices" rule adds nothing; a rule that encodes the project's actual decisions does.
5. Place the adapted file(s) in `.cursor/rules/` and keep them in version control so all contributors share them.

## Boundaries and license

- NOT a bulk import. We carry the convention and the selective-mining workflow as methodology; we do not bundle the template corpus. If a specific scaffold is needed for a project, fetch and adapt that one file at adoption time.
- License: PatrickJS/awesome-cursorrules is CC0-1.0 (public-domain dedication), so individual rule files can be reused/adapted freely; still review per-file quality and that nothing references third-party material with a different license.
- This is editor-config tooling, not a runtime dependency. Nothing is host-installed by us; the rule files live in the target repo.

## Cross-references

- frontend-developer and full-stack-developer carry one-line pointers to this file for their stacks.
- Conceptually parallel to project-level AGENTS.md / AGENTS.md guidance; if a project uses both Cursor and a coding agent, keep the two convention layers consistent.
