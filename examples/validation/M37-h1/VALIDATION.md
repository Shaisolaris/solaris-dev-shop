# M37 h1: affected recheck of G37 h1 e9b7a77 (Grok self-validation, not independent review)

Verdict: **PASS with one P4 observation.** G37 h1 is a docs-only revision of the compliance-auditor role. The 30-day
DSAR wording is gone from SKILL.md and rules.md, the new wording matches GDPR Art. 12(3), and the tool and the M37
oracle behave the same as on the accepted commit. This is Grok checking a Grok build. It is not independent review,
accepts nothing, and is not legal advice.

## Binding (raw/binding-verify.txt)
- Candidate e9b7a7772636f927bf21128dc2802ffcac742b44, current remote head of review/grok-g37-privacy-inventory.
- Accepted parent 9b0f58e is its direct parent (1 commit). Handback G37-h1.patch equals `git diff --binary 9b0f58e
  e9b7a77`. MANIFEST.sha256 29/29 match the tree (the 28 accepted files plus rules.md, as the handback says).
- Diff scope: SKILL.md, rules.md, learnings.md of compliance-auditor, 6 insertions, 4 deletions. privacy_inventory.py,
  fixtures and tests are unchanged.

## Primary source
GDPR Art. 12(3), read 2026-10-19 PDT: "without undue delay and in any event within one month of receipt of the
request. That period may be extended by two further months where necessary, taking into account the complexity and
number of the requests. The controller shall inform the data subject of any such extension within one month of
receipt of the request, together with the reasons for the delay." The new SKILL.md and rules.md text says the same
(one month, two further months where necessary, notice with reasons within the first month).

## Checks I wrote for this pass
- **Doc probe (oracle/m37h1_doc_probe.py).** Role files: no "30-day" clock in SKILL.md or rules.md; both state one
  month, the two-month extension and Art. 12(3); SKILL.md names the first-month notice with reasons; learnings.md
  records the correction. Tool clock (privacy_inventory.due_from with months: 1): 2026-01-31 gives 2026-02-28,
  2028-01-31 gives 2028-02-29, 2026-03-15 gives 2026-04-15, 2026-12-31 gives 2027-01-31. 10/10 on h1 and 4/10 on the
  accepted commit (the 6 wording rows fail there, as expected), on all four Pythons (results/doc-probe-*).
- **Prior M37 oracle (oracle/m37_oracle.py with its audit hook, unchanged).** 11/11 core PASS on e9b7a77 and on
  9b0f58e, Python 3.9.6, 3.11.16, 3.12.14, 3.13.15 (results/m37-oracle-*.json, pyversions.txt).
- **Builder tests.** tests.test_g37_capability OK x4. Full suite 137 OK on all four Pythons from a fresh clone, 0
  browser processes (results/full-suite-matrix.txt).

## Findings
- **P4-1 (outside G37 scope).** employees/specialized/wordpress-master/diagnostics/accessibility/SKILL.md line 104 still
  says "Export delivered within 30 days (GDPR requirement)". Same inherited inaccuracy, different role, not in the G37
  manifest. Left for the owner to route; no change proposed here.

## Authoring notes (disclosed)
- The first doc-probe run matched "30 day" loosely and flagged the new sentence "one month is not a fixed 30 days". I
  narrowed the check to "30-day" and reran; the numbers above are from the rerun.

Browser launches for this pass: 0.
