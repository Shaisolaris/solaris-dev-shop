# Consent-aware follow-through (G32)

Tool: `followthrough.py` (stdlib, Python 3.9+, POSIX locks, local files only). It turns an account's event
history into follow-up **drafts** for a person to review. It has no send path: no mail, network or process
call. Every draft says `send: not performed; a person reviews and sends`.

```bash
python3 followthrough.py run STATE --account ACCOUNT.json --events EVENTS.jsonl --now 2026-10-08T12:00:00-07:00 --worker NAME [--json]
python3 followthrough.py status STATE [--json]
```

Exit codes: 0 done; 2 invalid input or a state that does not verify (nothing written); 4 another worker holds
the state lock (nothing written); 75 crash drill (`--fail-at drafted|ledgered`).

## Inputs

- Account (schema `solaris.cs-account/1`): `account_id`, `owner`, `contacts` [{id, name, handle, consent
  granted|unknown}]. Handles are opaque ids; the sending system maps them to addresses. Every contact
  needs a handle, and the handle names the person: two contacts whose handles match once case, spacing and
  character width are ignored are one person imported twice, and the account is refused (exit 2, nothing
  written) until the duplicate import is merged.
- Events: JSON lines with `id`, `type`, `at` (ISO time with offset) and, by type, `contact`, `thread`,
  `scope`, `kind` or `owner`. Types: signup, ticket_opened, agent_response, reply_received, ticket_closed,
  opt_out (scope all|marketing), opt_in, bounce (kind hard|soft), owner_change. An exact redelivered line
  counts once; the same id with different content is refused.

## Playbook (derived from the whole history at `--now`)

| trigger | action | kind | due |
|---|---|---|---|
| first signup of a contact | welcome, checkin, training | onboarding | +0, +3, +7 days |
| ticket_opened | ack | support | +0 |
| agent_response | nudge | support | +2 days |
| ticket_closed | feedback | feedback | +1 day |

- **Suppression**: an opt-out (scope all) or a hard bounce suppresses every action for the person (every
  contact record carrying that handle), not only the record id the event named; an
  opt-out with scope marketing suppresses onboarding and feedback but not support replies to the customer's own
  ticket. Contacts with consent `unknown` get no onboarding or feedback. Suppression is permanent: a later
  `opt_in` is reported as `consent_review_required` and changes nothing.
- **Reply state**: a reply on the thread after our response cancels that response's nudge; a closed ticket
  cancels it too; a reply on the onboarding thread cancels the check-in (not the training invite).
- **Withdrawal**: a draft already written for an action that is now suppressed or cancelled is rewritten with
  `status: withdrawn` and `send: do not send`, and never drafted again.
- **Ownership**: drafts are signed by the current owner (the latest owner_change at `--now`); unsent drafts
  under a previous owner are re-rendered and reported as `reassigned`.

## Duplicate safety and resume

The action key is sha256 of (account, contact, action, trigger event). Under an exclusive lock on the state
folder, the tool checks the ledger for the key, writes the draft to a path derived from the key, then appends
the ledger record. A crash between the two leaves a draft that the next run rewrites in place, never a second
one; a crash after the ledger record is simply resumed. A torn ledger line cannot swallow the next record.
Each run appends a receipt to the G04 hash-chained journal (`journal.jsonl`); a journal that does not verify,
or state belonging to another account, is refused. A ledgered action whose draft file was removed is noted
(`draft_file_missing`) and not redrafted. `status` gives the next worker the runs, open and withdrawn drafts.
