# M09 h1 validation of G09 h1 1cab0f8 (Grok self-validation, not independent review)

Verdict: **PASS. M09 P3-1 is fixed, and there is no P1 or P2.** Grok checked a Grok build made in the same batch by
the same agent. This is not independent review and accepts nothing. G09 stays accepted at edfa64d; h1 is a hardening
commit that root would need to accept separately.

## Binding (raw/binding-verify.txt)
- Candidate 1cab0f8b68077b4dbd006ad37c1d20f3b538d7c7 on review/grok-g09-k8s-manifest-check, re-checked on the remote.
- It is one commit on top of the accepted edfa64d, a fast-forward. edfa64d is unchanged.
- G09-h1.patch equals the regenerated diff; MANIFEST.sha256 equals the diff set (2 files).

## Results
- **M09 oracle (oracle/m09_oracle.py, v3, unchanged): 60/60 core on all four Pythons.** At edfa64d it was 59/60,
  failing R10b (the P3-1 row).
- **Probe written for this pass (oracle/m09h1_probe.py): 9/9 on all four Pythons.**
  - It plants anchors, tags and aliases on sequence items inside a full Deployment, in positions the builder's test
    does not use: a container item, a port item, and a bare anchored item with the mapping below it.
  - Three controls must stay clean: the clean manifest, `&` inside a quoted value, and `&` inside a path.
  - At edfa64d the probe scores 6/9 (results/probe-at-edfa64d.txt). The three container-item cases named line 18 as
    "multi-line plain scalar" instead of line 17. The single-line port-item cases were already right at edfa64d.
  - This serves as the teeth check: removing the fix is exactly edfa64d, and the probe, M09 R10b and the new G09 test
    (results/new-test-at-edfa64d.txt) all fail there.
- **Builder evidence (results/builder-oracle.txt):** G09 tests OK on all four (PyYAML agreement skipped on 3.11 to
  3.13, as before); k8s_oracle 17/17; naive 3/17; no-op 2/17.
- **Full suite on fresh clones:** 160 OK on all four Pythons (results/full-suite-matrix.txt).
- The checkout was clean after every run.

## Not re-run
- The builder's 43 mutants were not re-scored. The change only adds a refusal before the existing paths, and every
  other M09 row is unchanged.
- No browser was launched.
