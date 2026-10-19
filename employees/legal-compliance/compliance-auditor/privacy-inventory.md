# Privacy inventory, retention and request handling (G37)

Tool: `privacy_inventory.py` (stdlib, Python 3.9+, local files only). It plans and traces; it never deletes,
exports, sends or contacts anyone, and its output is not legal advice. This operationalizes data inventory,
retention and data-subject requests inside the existing compliance-auditor and legal-advisor roles; the
separate data-privacy officer role stays an open contributor proposal (issue 10) and is not registered here.

## Package (`solaris.privacy-inventory/1`)
| Key | Meaning |
|---|---|
| `as_of` | review time, with Z or an offset |
| `contracts` | the data engineer's G13 `csv_reconcile.py` contracts; every facts and dimension file they read is a table. G13 runs on each, and its `ignored_columns` are inventoried too, because a column a metric ignores is still data that is held |
| `inventory` | `systems` (flow targets with an owner role) and `tables`: per file a `subject_key`, a `retention` (`days`, `anchor` column, `basis`, optional `hold_for_review`) and `fields` with `category` (identifier, contact, financial, location, behavioral, free_text, special_category, not_personal), `purpose`, `basis` and `flows` |
| `requests` | JSON lines: `request_id`, `type` (access, deletion, correction), `subject`, `received_at`, `identity_verified`, `jurisdiction`, optional `closed_at` |
| `clocks` | response clock per jurisdiction: `days` or `months` plus a `source`. These are configured values, never built in |

## Rules
1. **Inventory against the data.** Each actual header column (after G13 aliases) needs an entry
   (`unmapped_field`, with `ignored_by_g13`); entries for columns not in the data are `stale_inventory_entry`;
   personal fields need a purpose and a basis; personal tables need a retention and a subject key; flows must
   name a declared system.
2. **Retention.** A record is due when anchor + days <= `as_of` (the exact boundary is due). Unreadable anchors
   are named, never guessed. Due records become an obligation for the data engineer to review; with
   `hold_for_review` they also go to a qualified reviewer. Nothing is deleted.
3. **Requests.** Exact re-sends collapse; the same id with another body is refused and named. Due = received +
   clock (months clamp to the month end: Jan 31 + 1 month = Feb 28). Open past due = `overdue_request`; closed
   after due = `closed_late`; no clock = `unknown_jurisdiction_clock` plus a review item. An unverified request
   looks nothing up and shows nothing. Verified: every record whose subject key matches, by file and line;
   access gets the personal fields only; deletion splits into `delete` and `retain_pending_review` (held tables)
   with `propagate_to` systems; correction lists the personal fields.
4. **Human review boundaries.** `qualified_review` always lists every configured clock, free-text and special
   category fields, retention holds and deletion conflicts. Obligations carry ids, file/line refs, owner role and
   whether review is operational or qualified.

## Output and exit
`review PACKAGE [--json] [--out DIR]`: `report.json` and `handoff.md` (for legal-advisor and a qualified
reviewer), written atomically outside the package folder. Exit 0 `complete`, 1 `complete_with_findings`, 2 invalid
(nothing written; an earlier report stays).

## Limits
Synthetic data only. The subject is matched by exact key; there is no identity resolution across keys, no
search of free text for names, and no lawful-basis judgement. A checklist result never certifies compliance.
