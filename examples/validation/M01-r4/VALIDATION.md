# M01 r4: Grok self-validation of G01 r3 (fixture runner, quality_os.py)

Grok self-validation by the same bot that built the programme. This is not independent review and not manager acceptance.

- Candidate: G01 r3, commit a069a79ca6f57672fa92b0a86bfbcb46eff99ddb on review/grok-g01-fixture-runner (parent 1621c82, the r2 candidate that M01 r3 failed). main stays at 02ba9c5.
- Window: 22:54 to 23:20 PT, 2026-10-18. Interpreters 3.9.6, 3.11.16, 3.12.14, 3.13.15. The candidate was not modified.
- Disclosure: the r3 P2 fix in this candidate is my own M01 r3 proposed-fix-r3.patch, applied verbatim by the builder. M01 r3 found that its field list came from my own M01 r2 suggestion. I am therefore scoring a fix I wrote.

## Verdict: PASS with residuals (no P1, P2 or P3)
The P2 regression is fixed. Valid unwrapped G05 packets with requested_actions or sources pass again: z01, z02, w14, and the fresh caller's `run z01-packet-sources.json` gives ok true. Both r3 P4s are fixed. What is left is P4 plus one owner decision.

## Binding (raw/binding-verify.txt)
- The diff 1621c82..a069a79 is byte-identical to G01-r3.patch (sha256 d55fdcb6...).
- 3 files, +91/-10.

## Results (results/)
| Instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| Builder suite | 105 OK | 105 OK | 105 OK | 105 OK |
| M01 oracle core / gaps open | 12/12, 0/14 | same | same | same |
| M01 r2 adversarial | 7/7 | 7/7 | 7/7 | 7/7 |
| M01 r3 probes (r2 tool 9/13) | 13/13 | 13/13 | 13/13 | 13/13 |
| New M01 r4 probes, graded (r2 tool 5/11) | 11/11 | 11/11 | 11/11 | 11/11 |

- **M01 r4 probes (oracle/m01r4_probes.py):** they test the r3 any-key, any-case alias check against the r3 ASSURANCE.md paragraph.
  - Graded rows:
    - w01 to w05: case, dash, space and other-key forms of all kind words, including `defect`, `self_approval` and `legal-boundary`, are refused;
    - w13: blocked legal text with the kind word only in `description` is still refused as a stray legal field;
    - w14 to w17: valid packets still pass. These cover notes "legal", "legal" inside the dimensions list (correctly MISSING_SPECIALIST_GATE, not INVALID_PACKET), a nested "closure" value, and the doc's wrap advice with an extra "stage": "closure";
    - w20: fixture_kind wins over a stray kind word.
  - INFO rows w06 to w12, w18, w19 and w21 are recorded, not graded.
- **Direction:** the r2 tool fails w01 to w05 and w14, plus w21, which v1 graded and v2 reclassified. These rows are therefore sensitive to the r3 change.
- **Fresh caller (results/fresh-3.9.6.txt, fresh-3.13.15.txt; the M01 r3 script):** env -i, a new HOME, a python3 shim and an offline guard.
  - The documented commands behave as at r2.
  - `run z01-packet-sources.json` is now rc 0, ok true, no gate codes (r3: rc 1 INVALID_PACKET).
  - `suite fx`, which contains that packet, goes from 1/3 to 2/3 passed.
  - The network is blocked.
  - 3.13.15 output equals 3.9.6.

## Teeth (3.9.6; results/teeth-3.9.6/, results/teeth-tally-3.9.6.txt)
- **Mutant set:** 48 mutants plus a noop control (oracle/make_mutants_r4.py).
- **Instruments:** each is scored by the M01 oracle, the M01 r2, r3 and r4 probes, the builder's tests/test_fixture_runner.py, and the full suite. A kill is any deviation from the candidate's own baseline. All 4 shard baselines are identical, and there were no apply errors.
- **Counts (47 real, excluding the f4_outer_recursion_off_EQUIV control):** union 45/47, builder (fixture tests or suite) 44/47, Grok (oracle or probes) 31/47. The fixture-runner tests alone kill 44/47.
- **Controls:** control_noop and f4_outer_recursion_off_EQUIV both survive, as expected.
- **r3_alias_contract_off**, the r3 P4 test gap, is now killed by the builder tests.
- **Killed only by Grok:** r4_norm_no_space. The builder tests do not pin space folding; my w02 ("PLANTED DEFECT") does.
- **r4_* mutants:** 10 in total. Union 8, builder 7, Grok 8.
- **Survivors (results/survivor-distinguish-r4.txt):**
  - r4_marker_no_legal_text: non-equivalent. An unwrapped `{legal_text, requested_actions}` packet passes on the candidate (rc 0, ok true) and is refused on the mutant (INVALID_PACKET). No instrument pins legal_text as the only packet marker. P4 test gap.
  - r4_marker_no_evidence: undetermined. My distinguishing input `{evidence, requested_actions}` is refused by the candidate too, so it does not separate them. I ran out of time to find a valid evidence-only packet, so this is not shown to be either equivalent or non-equivalent.
- **Builder claim:** the builder claims its fixture-runner tests kill 43/43 non-equivalent mutants on its own set. On my set they kill 44/47.

## Findings
- **P1, P2, P3:** none. No proposed-fix patch (none is needed without a P1 or P2).
- **r3 findings:**
  - P2 (refused valid packets): fixed (z01, z02, w14, fresh caller).
  - P4 z13 and z14: fixed (and w01 to w05).
  - P4 test gap (r3_alias_contract_off): fixed, now killed by the builder tests.
  - New P4 test gap: r4_marker_no_legal_text survives (see teeth).
- **P4 residuals:**
  - Q1. ASSURANCE.md says a kind word is caught "in any case or spelling", but the normaliser folds only case, `_`, `-` and spaces. A bare planted defect with no fixture_kind and the kind written as `planted.defect` (w06), `planted_defects` (w07), a Unicode hyphen `planted‐defect` (w09), or inside a list (`"tags": ["planted_defect"]`, w10) is evaluated as a packet and passes with no gate codes. The `fixture_kind` form instead gives SELF_APPROVAL_FORBIDDEN. This is adversarial and of the same class as r3's z13 and z14, so it is P4. Suggestion: word the doc as "any case, ignoring _, - and spaces", or fold punctuation and plurals. No patch, because this is not a P1 or P2.
  - Q2. The kind word only under an exempt prose key (`"name": "planted_defect"`, w11) also passes as a packet. The doc exempts name, description and notes, so this is documented behaviour, recorded for the owner.
- **Owner decision (documented fail-closed limit):** an unwrapped packet with an ordinary field whose value is exactly a kind word is refused as INVALID_PACKET. Examples are `"stage": "closure"` (w18) and even `"risk_level": "Defect"` (w19). The doc states this and gives the wrap advice, and the wrapped form passes (w17). This trades false refusals for safety, so the owner should decide whether that trade is acceptable.

## Harness errors and disclosures
- **w21:** v1 (results/r4probes-v1-3.9.6.txt) graded "explicit fixture_kind legal plus an extra 'category' key is evaluated" and called it a GAP. That was my expectation error: explicit kinds refuse unknown keys, and the r2 tool does the same. v2 reclassifies it as INFO before the 4-interpreter run and teeth.
- **First r4 probe run:** my header copy dropped the `print` line from report(), so only the total printed. Fixed and rerun; no expectation changed.
- **Fresh-caller quirk:** the M01 r3 fresh-caller script's last line runs a stale hard-coded path (/tmp/m01r3-fc-PREuAr/...), which no longer exists and gives rc 1 INVALID_PACKET. This is the same in r3 and r4, and is my script error, not a candidate result.
- **Mutant set:** the M01 r3 set is re-anchored where the r3 change moved the code (f1_stray_off, r3_alias_off, r3_alias_contract_off). r3_alias_kind_only is retired, because its `endswith(("kind", "type"))` rule no longer exists. I added 10 r4_* mutants. All 48 anchors are single-occurrence.
- **Teeth ran on 3.9.6 only.**
- **week-grok** (programme/grok-week-20261018, read-only, never written): before 22:54:28 PT: HEAD 02ba9c5, index c28a2f586b3e3001, status 61afa019748f85b9 with 86 lines. After 23:19:01 PT: same branch, HEAD and index; status 46b51c0058e69c0a with 87 lines. The one new entry is `?? employees/marketing/seo-aso-specialist/page_diagnostics.py`, with mtime 23:18:09 PT. It is the builder's other work, not this pass. The status listings are kept outside the published folder.

## Files
- **oracle/:**
  - the M01 r3 tools;
  - m01r4_probes.py, make_mutants_r4.py and run_teeth_r4.py.
- **results/:**
  - per-interpreter outputs;
  - r4probes-*, including the r2 tool and v1;
  - fresh-*;
  - teeth-3.9.6/ and the teeth tally.
- **raw/:** the before and after records, and binding-verify.
