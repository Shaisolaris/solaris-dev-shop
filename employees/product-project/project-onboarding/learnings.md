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
- The 2026-10-19 root QA batch showed that Hangul filler, braille blank and combining marks alone still counted as a deploy answer, that zero-width or fullwidth `UNRESOLVED` finished complete, and that a deeply nested journal or lock escaped as a RecursionError traceback through the activation API. Blank-looking marks are now treated as blank, UNRESOLVED is matched after NFKC and mark stripping, and nested or corrupted journal/lock input returns a bounded blocked result with owner files preserved.
- The 2026-10-19 M02 r3 self-validation found that the r3 fold deleted spaces before matching, so `UNRESOLVED ask the owner`, `Unresolved until the owner decides` and `unresolved pending call` lost the word boundary and were recorded as real answers (they were unresolved at r2), and an accent on a letter (`U\u0301NRESOLVED`) still hid the word. The fold now keeps spaces, uses NFKD and drops combining marks.
- The 2026-10-19 M02 r3 self-validation (P4-1, OBS-1) found that placeholder answers (`TBD`, `?`, `-`, `n/a`) finished complete and were recorded as the deploy model, and that `UNRESOLVED` with a Cyrillic E was read as an answer. A whole-answer placeholder list and a small look-alike letter fold now keep both unresolved; both checks fail closed (the owner is asked again).
- The M02 r4 probe then found that dotted placeholders (`t.b.d.`) and a few look-alike letters (Cherokee, Armenian, Cyrillic palochka) still passed. Single letters separated by dots or spaces are now joined before the placeholder check, and those letters are in the fold.
