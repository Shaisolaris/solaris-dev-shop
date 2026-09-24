# Minimal-change mode (inherited codebases)

When taking over a client's existing codebase (Kellbell, CTT, Turnpike rescue, any handoff), the default mode flips from "build it right" to "change as little as possible while shipping what's asked."

## Hard rules

1. **Read 3 surrounding files before editing.** Match conventions exactly: naming, indentation, comment style, error-handling pattern.
2. **No drive-by refactors.** Even if a function is awful, leave it unless the ticket says fix it.
3. **No new dependencies** without explicit approval. Use what's already in package.json / composer.json.
4. **No formatter / linter blast.** Don't reformat files you didn't need to touch. PR with 200 changed files and 5 actual fixes is a no.
5. **Match the existing test style.** If they use Jest, stay Jest. Don't introduce Vitest in a Jest project.
6. **Preserve existing comments**, even outdated ones, unless the ticket explicitly says remove them.

## When you're tempted to refactor

Ask three questions:
1. Is this in the ticket scope? If no, don't touch.
2. Will I break a passing test? If unsure, don't touch.
3. Can the client accept a separate PR for this cleanup? If yes, file a separate ticket - don't bundle.

## Acceptable cleanup INSIDE the scope

- Adding tests for the function you're modifying (always allowed, often expected)
- Renaming a variable you're already changing the value of
- Adding a TODO/NOTE comment marking smell for later
- Fixing a bug that the ticket's change exposed (cite in PR)

## Unacceptable cleanup

- Renaming files
- Restructuring directories
- Changing build tools / package manager
- Upgrading dependency major versions
- Switching state-management or HTTP libraries
- Adding new lint rules

## Handoff signals

When you genuinely think the codebase needs structural work, write it as a separate "technical-debt audit" deliverable for the client to approve. Never silently restructure on a feature ticket.

## Cross-reference

- code-review skill - comprehensive review mode (for the initial intake of an inherited codebase)
- migration-architect skill - when the client approves a larger structural change
