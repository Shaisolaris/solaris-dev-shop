# Immutable-event validation (event_chain.py)

A synthetic, local append-only log for evidence that must not change after it is written (artifact records,
approvals as claimed, release steps). It is not a blockchain: no wallet, key, signature, network or
transaction is involved.

```
python3 event_chain.py append LOG --claimed-by NAME --body JSON [--at ISO-TIME]   # 0, 2 refused, 4 locked
python3 event_chain.py verify LOG [--anchor SEQ:HASH] [--json]                     # 0 verified, 1 findings, 2 invalid
python3 event_chain.py recover LOG --out NEW [--anchor SEQ:HASH] [--json]          # 0 written, 1 nothing to keep, 2 refused
```

Each line is `{"seq", "prev", "at", "claimed_by", "body", "hash"}`. `hash` is the sha256 of the canonical JSON
(sorted keys, no spaces) of the other five fields; `prev` is the previous hash, 64 zeros for seq 0.

## Findings (verification stops trusting at the first one)

| code | meaning |
|---|---|
| hash_mismatch | the event's content changed after it was written |
| broken_link | `prev` is not the previous event's hash |
| seq_gap / seq_repeat | an event is missing, reordered or replayed |
| time_regression | `at` is earlier than the previous event |
| torn_tail / line_not_json | an interrupted last write, or a line that is not JSON |
| fields_wrong / time_invalid | missing or extra fields, or a time without an offset |
| anchor_mismatch / anchor_not_reached | the history up to the anchored event was rewritten, or the log was truncated before it |

## What a pass means

- Without `--anchor`: the log is self-consistent. Anyone who can write the file can rewrite all of it from any
  point and recompute the hashes; verify alone cannot tell.
- With `--anchor SEQ:HASH` taken from somewhere the writer cannot change (a ticket, a reviewer's receipt, a G05
  subject binding): nothing up to that event was rewritten.
- `claimed_by` is reported as "claimed in plain text, not authenticated", always.

## Append and recovery

`append` takes an exclusive lock, re-verifies the whole log and refuses (exit 2, nothing written) when it does not
verify. `recover` writes only the verified prefix to a new file; it refuses to overwrite the log or any existing
file, and when an anchor shows rewritten history it keeps nothing. The original log is never modified.
