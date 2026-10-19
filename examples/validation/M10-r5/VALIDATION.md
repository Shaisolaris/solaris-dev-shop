# M10 r5: Grok self-validation of G10 r6 (offline network diagnosis)

Label: Grok self-validation by the same bot that built and validates the programme. This is not independent review and not manager acceptance.

- Candidate: G10 r6 at f79be61580dec0911f6aba56c3bdc746a30898e7 on review/grok-g10-network-diagnosis (parent 865734e, r5), fetched 21:29:30 PT and checked out detached in a /tmp worktree. Not modified. r5 was checked out separately as the old tool.
- Binding (raw/binding-verify.txt): the r5..r6 diff is byte-identical to G10-r6.patch (sha256 e00c218d...); MANIFEST.sha256 checks 25/25, and its file set equals the 02ba9c5..f79be61 diff set. The tool change is one new function, `_split_nonhost`, and its call site.
- Scope: the M10 r4 residual V1 (P3), Q3 (P4, documented), and regressions.
- week-grok: before 21:29:29 PT and after 21:46:18 PT are identical (branch programme/grok-week-20261018, HEAD 02ba9c5, index c28a2f586b3e3001, status af8386300eb96552, 80 lines; full listing byte-identical).

## Verdict: PASS

V1 is fixed with no regression found, and teeth kill every mutant. No new P1 to P3. Q3 (P4) is unchanged and documented. No proposed-fix patch is needed.

## Results (identical on 3.9.6, 3.11.16, 3.12.14, 3.13.15)
| Instrument | Result |
|---|---|
| M10 oracle | 10/10 ACCEPTS |
| Builder diagnosis_oracle.py | 14/14 ACCEPTED (r5: 13/14, o14) |
| Builder suite | G10 49 OK, original 84 OK, full 133 OK; tree status 0 lines before and after |
| M10 adversarial (main 3.12.14, --pythons the other three) | FINDING 1, NOTE 5, OK 9: unchanged from M10 r4 (the FINDING is the pre-existing a04 SNI case) |
| M10 r3 probes | HOLDS 33, GAP 0 |
| M10 r4 probes | HOLDS 18, GAP 0, OBS 1 (at r5: 3 GAPs on 3.9.6) |
| M10 r5 probes u01 to u14 (new, v2) | HOLDS 10, GAP 0, OBS 4 |
| M10 r2 regression script, r6 vs r5 | output identical to M10 r4's r5-vs-r4 record on 3.9.6 and 3.12.14 (results/regressions-compare.txt) |
| Fresh caller (env -i, new HOME, python3 shim, M10 offline guard, doc commands only, 4 new V1 traces with a hand answer written first), 3.9.6 and 3.12.14 | matches the hand answer; batch 4 traces (healthy 1, localized:tls 3); 0 network attempts; no stray files; HOME empty |

## V1 confirmed fixed
- A bare covering name after a URI, email, Registered ID, keytool URIName or DirName in one pasted line is its own entry and covers, so there is no false TLS_NAME_MISMATCH (M10 r4 s01; r5 u01, u02, u07, u12; fresh caller b and c).
- Controls still mismatch when nothing covers:
  - a CN equal to the target inside a DirName (u04, u05);
  - a URI whose host equals the target (u06);
  - a too-broad wildcard after a URI (u08);
  - an RDN-shaped `CN=target` chunk (u13);
  - a type-prefixed `OtherName:target` chunk (u14);
  - fresh caller a.

## Findings by severity
- No P1, P2 or P3.
- P4 (Q3, carried, documented): sub-microsecond timestamp truncation, unchanged.
- Observations (documented limits, not graded):
  - u09: a DirName RDN value written without "=" that equals the target (`DirName:CN=svc, api.shop.example`) splits off and covers. The doc states this limit. The result is the generic TLS_ALERT, not a confident wrong answer.
  - u10: a comma with no space after a URI never splits (doc). Beside a DNS entry that does not cover, the result is TLS_NAME_MISMATCH. openssl and keytool always print ", ", so this needs hand-edited input.
  - u11: a trailing-dot name after a URI covers.
  - u03: a tab after the comma makes the trace invalid (rc 2, "expected a single-line string"), the same as r5.

## Teeth (results/teeth-tally-3.9.6.txt; oracle/make_mutants_r5.py, oracle/m10r5_teeth.sh)
43 mutants: M10 r2's 23 (make_mutants_r2_on_r4.py, unchanged anchors), M10 r4's 14 with the two q2 mutants re-pointed at r6's split line (same meaning), and 6 v1_* mutants on `_split_nonhost`. 4 shards on 3.9.6. A kill means the subject's row differs from the candidate's (probe columns compare the HOLDS/GAP pattern).
- Builder tests 43, builder oracle 38, M10 oracle 17, r3 probes 13, r4 probes 13, r5 probes 8. Union 43/43, no survivors.
- Baselines: the candidate passes every scorer. r5 is caught by the builder oracle, the tests, and the r4 and r5 probes. All 4 stubs are rejected by both oracles.
- v1_eq_ignored, v1_type_ignored, v1_split_any_comma and v1_glue_drops_comma are killed only by the builder tests.

## Harness disclosures
- M10 r5 probes v1 (raw/discarded-harness-error/) had 4 GAPs: u03, u06, u08 and u13. Each was identical on r5, and each was my own expectation error.
  - u06, u08 and u13 had no DNS/IP entry, and with none the tool abstains by design (code comment and r3 behaviour: no confident mismatch, a "not understood" note).
  - u03 is rejected as invalid input.
  - v2 adds `DNS:other.example` to each mismatch control and makes u03 an observation. The change is printed in the probe output.
- The fresh caller keeps the r4 trace file names (a-keytool-mismatch, c-certutil-covering) for new contents; the hand answer says so.
- oracle/ also holds the earlier-round tools, copied unchanged, including the old proposed-fix patches. Those patches do not apply to this pass.

## Not done
- Teeth ran on 3.9.6 only (time budget); the other instruments ran on all 4 interpreters. 3.10 is not installed. No live network.
