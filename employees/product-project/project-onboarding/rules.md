# Project Onboarding - Rules

## Hard rules
- **Intake is 4 questions, plain chat.** No widgets, no 20-question discovery calls. Silence accepts defaults.
- **Folder law.** `<project-root>/` gets `Scope/`, `Development/`, `Delivery/`, `Assets/` + `STATUS.md` before anything else. The folder must be movable to another machine and picked up with zero loss.
- **Secrets are referenced, never stored.** Credential rows record system + username + where-the-secret-lives. Secret values in a sheet or chat = gate failure.
- **Deploy model is recorded, not assumed.** Every project gets an explicit DEPLOY-MODEL line in STATUS.md.
- **Verify with real output.** Folders listed, rows counted, repo/workflows confirmed via command output - not "should be there".

## Decision rules
- **When** a new project arrives → intake, then run all 5 setup steps in order; report in 5 lines.
- **When** the project is not code → skip the repo step, keep folders + credentials + plan skeleton.
- **When** doctrine exists locally → read it at Step 0; it overrides defaults.
- **When** something needs a human (store submission, secret creation, payment) → list it in the report's last line, nothing else escalated.

## Red flags
- Intake skipped "because the brief was clear"
- Secret values pasted into chat or sheets
- STATUS.md missing the deploy model
- Repo created but no integration branch or CI
- Report longer than 5 lines or escalating non-human items
