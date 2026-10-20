# M22 h1: affected recheck of G22 h1 8bc3553 (Grok self-validation, not independent review)

Verdict: **PASS with one P3.** export-g14 now refuses books with open held or exception events or unapplied money:
exit 1, nothing written, the open items named. Clean books still export and reconcile in G14, and a held event stops
blocking once its missing events arrive. The P3: an exception can never be cleared, so after one over-refund or
out-of-stock order the ledger can never export again, for any period, while the doc says to "resolve or re-deliver the
events first". This is Grok checking a Grok build. It is not independent review and accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate 8bc3553713c31548dda240da81a816802de1d375, current remote head of review/grok-g22-payment-ledger.
- Accepted G22 1faee8d is its direct parent (1 commit). Handback G22-h1.patch equals `git format-patch --stdout
  1faee8d..8bc3553`. MANIFEST.sha256 6/6 match; manifest set equals the diff set.
- Diff scope: payment_ledger.py (open_items() and the refusal in cmd_export_g14; docstring exit codes), webhook-ledger.md,
  SKILL.md, learnings.md, G22 README, tests/test_g22_capability.py. ingest, report and check are unchanged.

## Probe written for this pass (oracle/m22h1_probe.py, results/probe-*)
From the shipped september fixture lines only, ingested at the fixture time (--now 1790000200):
- Q1 the full september stream: exit 1, --out not created, stdout JSON lists evt_007 and evt_008 and the unapplied
  40.00 refund, stderr names evt_007.
- Q2 `check` on that ledger still exits 0: the refusal is about open items, not a corrupt ledger.
- Q3 september without evt_007 and evt_008: exit 0; G14 reconciles, net cash and recognized revenue 32.69.
- Q4 the evt_004 refund delivered before its order: held, export refused naming evt_004; after the rest arrives the
  refund applies and export exits 0. The block lifts on its own when the events resolve.
- Q5 (observation, the P3 below) and Q6 a non-empty --out still exit 2 with the file kept.
- 6/6 on h1 and 4/6 on the accepted 1faee8d (Q1 and Q4 export with exit 0 there), on Python 3.9.6, 3.11.16, 3.12.14 and
  3.13.15.

## Prior M22 oracle (oracle/m22_oracle.py, unchanged)
16/16 core on 1faee8d and 15/16 on 8bc3553, all four Pythons. The one change is B10, and it is the intended effect of
the hardening: B10's september and crash_stream sub-cases each carry an open 40.00 over-refund, so export now exits 1
and G14 has nothing to read (export 1, G14 2); the base sub-case still exports and reconciles at 32.49, and the
outside-period export still works. M22's B10 expected books with open exceptions to reconcile as clean, which is the
exact behaviour G30 x2 flagged and G22 h1 removes. I treat the B10 change as expected, not as a regression.

## Builder checks
ledger_oracle PASSED 10/10; naive REJECTED 5/10; no-op REJECTED 0/10 (all four Pythons). tests.test_g22_capability 15 OK
x4. Full suite on fresh clones (results/full-suite-matrix.txt): 165 tests OK on all four Pythons; browser processes 0.

## Finding
- **P3-1 An exception can never be cleared, so export is blocked forever, and the doc says otherwise.** Probe Q5: after
  the evt_007 over-refund exception, re-delivering evt_007 leaves it open (ingest exit 1), and an export for November,
  a period with no events at all, is still refused naming evt_007. The tool has no resolve command (init, sign, ingest,
  report, check, export-g14), and re-delivering a corrected event under the same id is a conflicting replay that is
  refused. webhook-ledger.md says "resolve or re-deliver the events first", which only works for held events.
  P3, not P2: the behaviour fails closed (books are never shown as clean while money is unexplained), but a ledger
  becomes permanently un-exportable after one routine exception, and the doc points to a path that does not exist.
  Suggested direction for the builder (not applied): either scope the refusal to items inside the export period and
  say so, or add an explicit, recorded write-off or acknowledge step for an exception; at minimum, state in the doc that
  an exception cannot be cleared with this tool.

Browser launches for this pass: 0.
