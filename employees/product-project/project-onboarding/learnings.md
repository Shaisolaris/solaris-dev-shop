# Project Onboarding - Learnings

## Sources
- Upstream: none; authored for this library.
- License: MIT.
- Absorbed: project-kickoff checklists from standard PM runbooks.

## Durable lessons
- The deploy model question prevents the most expensive onboarding mistake: assuming main auto-deploys when it doesn't (or vice versa). An unanswered question must stay unresolved; a default is an assumption.
- Folders before tools. A project with a clean folder tree and no CI beats a project with CI and no one knowing where anything lives.
- A rejected 2026-10 activation candidate showed that fixing each reported example is not enough: symlinked folders, predictable temp files and a `.git` link let writes escape the project, an existing repository's staged files were committed, and a resume compared against an already-updated file. The current tool checks every controlled path before writing, uses random exclusive temp files, never mutates an existing repository, and resumes from a journal of the hashes it wrote.
- The 2026-10-18 M02 self-validation (findings F1 to F8) showed that a journal without an identity lets a copied folder pass one client's live deploy model to another, that `str.strip()` leaves zero-width characters, and that a broad shape check on the journal top level still lets a list inside it crash the run. The journal now records its folder, invisible-only answers are blank, every journal entry is type-checked, and the lock and path errors return a result instead of a traceback.
- Secret detection is a guard, not proof. Accept only the three reference fields and refuse secret-shaped values without echoing them.
