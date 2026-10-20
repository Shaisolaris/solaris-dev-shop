# M01 h1: affected recheck of G01 h1 aa0b083 (Grok self-validation, not independent review)

Verdict: **PASS (no P1, P2, P3 or P4).** G01 h1 is a docs-only revision of ASSURANCE.md. Every example the new text
gives behaves as written, the misspelled-key claim holds, and the M01 oracle gives the same result on h1 as on the
accepted commit. This is Grok checking a Grok build. It is not independent review and accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate aa0b083f1eb105349bc29d4d6d45cb2d1877d6b8, current remote head of review/grok-g01-fixture-runner.
- Accepted parent a069a79 is its direct parent (1 commit). Handback G01-h1.patch equals `git diff --binary a069a79
  aa0b083`. MANIFEST.sha256 4/4 match the tree.
- Diff scope: 1 file, employees/quality-security/assurance/ASSURANCE.md, 10 insertions, 4 deletions. No code or test
  change, so the engine behaviour accepted at a069a79 is unchanged by construction.

## Checks I wrote for this pass
- **Doc probe (oracle/m01h1_doc_probe.py).** Through the `quality_os.py run` CLI only, one fixture per example, with
  the kind word in a `category` field of an otherwise ordinary packet:
  - documented as matched, refused with INVALID_PACKET: legal, planted_defect, Planted-Defect, PLANTED DEFECT,
    planted-defect;
  - documented as not matched, evaluated as an ordinary packet (no INVALID_PACKET): plantd_defect, planted.defect,
    Cyrillic look-alike "legal", "legal" with a zero-width space;
  - "a misspelled kind key itself is caught by the near-miss check": Fixture_Kind, fixture-kind, FIXTURE KIND, each
    refused.
  12/12 on Python 3.9.6, 3.11.16, 3.12.14, 3.13.15 (results/doc-probe-*.json).
- **Prior M01 oracle (oracle/m01_oracle.py, unchanged).** Core 12/12, gaps open 0/14, identical on aa0b083 and on
  a069a79, all four Pythons (results/pyversions.txt, m01-oracle-*.json).
- **Builder tests.** tests/test_fixture_runner.py 21 OK x4 (results/g01-tests-corrected.txt). Full suite 105 OK on all
  four Pythons from a fresh clone, 0 browser processes (results/full-suite-matrix.txt).

## Authoring notes (disclosed)
- The first G01 test column in results/pyversions.txt used the pattern test_g01*.py, which matches no file, so it ran 0
  tests (3.12 and 3.13 print "NO TESTS RAN"; 3.9 and 3.11 print OK). I reran with test_fixture_runner.py; that is the
  number above.

## Not checked
- Wording quality beyond the factual claims. The unchanged packet wrap paragraph was not rechecked.

Browser launches for this pass: 0.
