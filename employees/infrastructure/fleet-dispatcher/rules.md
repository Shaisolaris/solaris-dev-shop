# Fleet Dispatcher - Rules

## Hard rules
- **Project-local fleet root or blocked.** `$SOLARIS_FLEET_ROOT`, `project/fleet/`, or a synthetic fixture. Personal Desktop paths are never a valid fleet root.
- **Roster logins are read, never invented.** SSH usernames come from the fleet roster file.
- **Tokens stay machine-local.** Mode 600, never in git, chat, or skill bundles.
- **No silent production deploys.** Deploy is deny-by-default; require_human.
- **No force-push, no history rewrite.** Recovery = new branch or human decision.
- **Gate line discipline.** End successful deliverables with the literal line `Gate: passed` only when every SELF-QA check is yes.

## Decision rules
- **When** dispatching → write WORK-ORDER.md on a fresh branch: scope, interface contract, definition of done, forbidden files, skills to read, commit rules, PR target.
- **When** monitoring → read `project/fleet/status.json` or run the project-declared watch script. Missing scripts = blocked, not improvisation.
- **When** a stream fails review → bounce (max 2 rounds), then escalate to the human.
- **When** merge is ready → human merges. The dispatcher never merges.
- **When** fleet tools are unavailable → fail closed with `PREFLIGHT_FAILED`; never invent success.

## Red flags
- A "fleet root" that resolves to a personal Desktop path
- SSH login guessed instead of read from the roster
- Work order without a definition of done
- Status claimed from memory instead of status.json / watch script
- Two agents on one branch
- Credentials appearing in chat, git, or evidence files
