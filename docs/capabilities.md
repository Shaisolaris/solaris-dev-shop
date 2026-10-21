# Executable specialist workflows

Solaris keeps its 61 specialist roles and chief of staff. Selected roles include deterministic helpers that produce inspectable artifacts. These run through the host's existing tools and permissions; installing the source does not start employees, connect accounts or authorize external actions.

| Work | Useful behavior and examples |
|---|---|
| Recoverable delivery | [Activate a project](../examples/capabilities/G02/README.md), [resume an interrupted handoff](../examples/capabilities/G04/README.md), and [track offline fleet claims](../examples/capabilities/G07/README.md). |
| Infrastructure | [Restore SQLite safely](../examples/capabilities/G03/README.md), [rehearse local deployment rollback](../examples/capabilities/G08/README.md), [inspect Kubernetes manifests](../examples/capabilities/G09/README.md), [diagnose network traces](../examples/capabilities/G10/README.md), and [check incident evidence](../examples/capabilities/G11/README.md). |
| Data and decisions | [Reconcile dirty CSV inputs](../examples/capabilities/G13/README.md), [reconcile cash and revenue](../examples/capabilities/G14/README.md), [read an experiment](../examples/capabilities/G15/README.md), and [compare resource decisions](../examples/capabilities/G17/README.md). |
| Application state | [Probe duplicate and tenant boundaries](../examples/capabilities/G19/README.md), [handle stale UI responses](../examples/capabilities/G20/README.md), [replay offline synchronization](../examples/capabilities/G21/README.md), and [resolve payment-ledger exceptions](../examples/capabilities/G22/README.md). |
| Product evidence | [Evaluate grounded answers](../examples/capabilities/G16/README.md), [check scope acceptance](../examples/capabilities/G31/README.md), and [compare options against pinned evidence](../examples/capabilities/G33/README.md). |
| Operations | [Diagnose saved WordPress traces](../examples/capabilities/G23/README.md), [inspect page evidence](../examples/capabilities/G34/README.md), [account for campaign events](../examples/capabilities/G35/README.md), and [exercise replayable device protocols](../examples/capabilities/G25/README.md). |
| Consent and provenance | [Prepare consent-aware follow-up drafts](../examples/capabilities/G32/README.md), [inspect privacy inventories](../examples/capabilities/G37/README.md), and [check license/provenance consistency](../examples/capabilities/G38/README.md). |
| Quality and transfer | [Bind review to artifact bytes](../examples/capabilities/G05/README.md), [run the cross-employee recovery drill](../examples/capabilities/G39/README.md), [inspect host portability](../examples/capabilities/G40/README.md), and [inventory release readiness](../examples/capabilities/G41/README.md). |

The example pages contain the actual commands, fixtures, useful positive outcomes, negative controls and limitations. They are synthetic local exercises, not evidence of a customer deployment or a live external service.

## Start with a composed outcome

From a source checkout on a supported POSIX host:

```bash
python3 control-plane/meta_control_plane.py self-test
python3 examples/capabilities/G39/drill.py
```

The delivery drill interrupts a work order, resumes it with another worker and suppresses duplicate delivery. It then changes an upstream input and removes a snapshot file: readiness must fail until the original bytes are restored. It uses local fixtures and disposable state.

The Python wheel provides `solaris-intake` and its catalog. Keep the source tree for specialist helpers and their companion files. Git-dependent integration checks need the named commits in a full source checkout; a copied skill folder or wheel cannot supply that history.

## Boundaries that matter

- Router installation requires Python 3.10+. Helpers state their own requirements; local locking, process and filesystem workflows often require POSIX.
- Grounded-answer filtering recognizes a documented lexical policy. Unrecognized instructions can evade it, and conservative exclusions can remove benign prose. The host still enforces instruction priority and tool permissions.
- Statistical outputs depend on valid inputs and independent population evidence. An operator-supplied count is an assumption, not authentication.
- Identity, approval, waiver and resolution fields record claims unless the workflow explicitly establishes stronger evidence. Local hash checks do not authenticate a hostile writer.
- Privacy and license helpers check consistency and evidence. They do not establish legal permission or certify compliance.
- Drafts, deployment rehearsals and ledger simulations do not send messages, deploy a customer system or move real money.
