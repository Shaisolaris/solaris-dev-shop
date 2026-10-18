# Changelog

## 0.61 (2026-10-18)

- Harden assurance finding closure and human waivers: reject expired or malformed waivers, malformed severity/status, blank closers and invalid evidence containers before mutation.
- Preserve legitimate independent closure and valid human-waiver closure, including empty evidence where a valid waiver authorizes it. Authority and evidence remain declared inputs, not authenticated or dereferenced proof.
- Add 40 focused API and real CLI regression tests; independently verify supported Python 3.12, fixed-clock expiry boundaries and correction/retry behavior.

## 0.60 (2026-10-16)

- Enforce typed, nonblank Quality OS gate evidence and block receipts reporting open findings. Malformed packet containers now yield diagnostics instead of false passes or tracebacks.
- Reject unknown gate/dimension inputs and nested validation failures; document receipt validation versus actual execution and owner approval.
- Add independent regression coverage for valid and malformed handoffs. Assurance engine is 1.0.1; intake engine/schema remain 1.3.0 and the roster remains 61.

## 0.59 (2026-10-15)

- Package the canonical router directly without source symlinks or duplicate package layout, including source-to-wheel validation.

## 0.58 (2026-10-15)

- Preserve requested supporting specialists and source handoffs in compound assignments; add contributor quickstart and corrected new-skill instructions.

## 0.57 (2026-10-15)

- Repair 14 malformed YAML descriptions and 22 discovery-metadata compatibility failures in total, including overlong fields and bracket comparisons. Skill names and detailed bodies remain unchanged.
- Add a safe YAML/name/description gate for all 61 specialists plus the coordinator. PyYAML is a developer-only dependency; the intake runtime remains standard-library only.
- Retain engine 1.2.1 and the existing roster. No provider, tool permission or specialist is added.
- Restore the original project preview artwork and preserve its branding; custom preview settings are unchanged.

## 0.56 (2026-10-15)

- Recognize production action and target words even when an application name separates them; run the human-review risk gate before ambiguity or context routing.
- Cover ordinary deployment/release wording and non-production/whole-word boundaries with regressions. Document conservative lexical matching and host permission limits.

## 0.55 (2026-10-15)

- Ask for clarification on long unknown requests instead of silently assigning a backend specialist. Retain specific keyword and multi-domain routes.
- Add offline skill search by terms and department, plus source paths and links in assignment packets. Validate the catalog against all 61 active skills in CI.
- Align the 3D Artist contract ID with its existing roster and route. No roster additions.
- Provide a complete clone-to-handoff quickstart, a worked first-task guide and verifiable project facts. Clarify host execution and benchmark limits.
- Repair 34 shared-standard paths so they resolve from the skill folder, with a source-file regression check. Document shared dependencies when copying skills.
- Refresh repository preview assets with matching editable source and 2:1 output.

## 0.54 (2026-10-15)

- Fixed self-test fixture discovery: checkout fixtures are now executed and their expectations enforced.
- Added `intake --explain`, relative keyword confidence and distinct runner-up evidence.
- Added bounded Spanish/French review phrases, matching risk signals and Unicode word boundaries.
- Added opt-in local follow-up routing context with no stored request text; safety gates run on every request.
- Added escaped, offline Quality OS HTML reports.
- Expanded adversarial fixtures from 3 to 14 and added CLI, privacy, Unicode and installer regressions.
- Added actual multi-domain/escalation examples and a reproducible 100-request benchmark.
- Added a read-only Actions routing playground and Windows manual installation checks.
- CI now checks Python 3.10/3.12/3.13 and Linux/macOS/Windows, including an installed wheel outside the checkout.
- The Bash uninstaller preserves checkouts and unrecognized commands; install refuses overwriting an unrelated command.
- Clarified that the AI Agents Directory backlink supports a pending verification.

## 0.53

Elite QA pass: every claim verified, every path live.

- Router repaired: accountable always equals the matched specialist; personal health/finance signals escalate to the owner; 66 routing probes green
- `quality_os.py audit` repaired: scans all 61 employees across 12 departments, 0 gaps
- All 61 capability contracts scrubbed to public identity; all manifests valid
- Dead internal paths removed; canonical QA loop documented in `docs/QA-LOOP.md`
- New: `fixtures/control-plane/` honest fixtures, `.github/workflows/ci.yml`, `docs/QA-LOOP.md`

## 0.52


Public edition of the private V5.2.2 workforce.

Included:

- 61 canonical employees under `employees/<department>/<name>/`
- The existing chief of staff under `chief-of-staff/`
- Four control-plane companions under `control-plane/`, so routing still runs

Not included:

- Alfred
- Marketplace catalogs
- Patent material
- Newer employees and protocols
- Eval receipts, fixtures, and private Git history

Identity in public skills is Solaris Dev Shop. A model vendor is not the employee.
