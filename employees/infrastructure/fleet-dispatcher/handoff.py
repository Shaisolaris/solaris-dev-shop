#!/usr/bin/env python3
"""Restartable local work orders: one owner, a revision, input and output references, resumable partial state (G04).

A work order names its owner, a revision number, a hashed intake file and a fixed three-step workflow:

  activate  run project activation (project-onboarding/activate.py, G02) on the order's project root
  brief     render HANDOFF-BRIEF.md for this revision from the intake and the activated STATUS.md
  deliver   append one delivery record to the outbox ledger (the effect that must never be duplicated)

Every finished step appends a receipt to a hash-chained journal: the step, the revision, the hashes of the
inputs it used (including the order owner for activate and brief) and of the outputs it produced. A later worker (any process that runs `run` on the same order)
re-checks each receipt against the current inputs and outputs and reuses it only if both still match;
otherwise the step is stale and is redone. Delivery is keyed by order, revision and brief hash, and the
ledger is checked under a lock before appending, so a worker that crashed after delivering but before writing
its receipt is not delivered twice.

This runs locally. It does not launch, schedule or contact workers or a router; "worker" is just the name the
caller passes. Exclusion uses fcntl locks, so it is for one machine (POSIX), not a shared network folder.

Exit codes: 0 done; 1 a step failed (receipt says why; fix and rerun); 2 invalid order, input mismatch,
stale revision or a journal that does not verify (nothing run); 3 stopped early on request (--stop-after;
resume with `run`); 4 another worker holds the order (nothing written). A --fail-at crash drill ends the
process abruptly with 75 after the step's effect and before its receipt, like a killed worker.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SCHEMA = "solaris.work-order/1"
JOURNAL_SCHEMA = "solaris.work-order-journal/1"
STEPS = ("activate", "brief", "deliver")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ACTIVATE = Path(__file__).resolve().parents[2] / "product-project" / "project-onboarding" / "activate.py"
REGISTRY = Path(__file__).resolve().parents[1] / "fleet-provisioner" / "registry.py"
CRASH_EXIT = 75


class OrderError(Exception):
    pass


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    try:
        with open(p, "rb") as f:
            return sha_bytes(f.read())
    except OSError:
        return None


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".wo-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def inside(base, rel, what):
    if not isinstance(rel, str) or not rel or os.path.isabs(rel) or "\x00" in rel:
        raise OrderError("%s must be a relative path" % what)
    p = (base / rel).resolve()
    if p != base and base not in p.parents:
        raise OrderError("%s leaves the work-order folder" % what)
    return p


def load_order(path):
    path = Path(path)
    try:
        raw = path.read_bytes()
        order = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise OrderError("work order unreadable: %s" % e.__class__.__name__)
    if not isinstance(order, dict) or order.get("schema") != SCHEMA:
        raise OrderError("work order schema must be %s" % SCHEMA)
    oid, rev, owner = order.get("order_id"), order.get("revision"), order.get("owner")
    if not isinstance(oid, str) or not ID_RE.match(oid):
        raise OrderError("order_id must be 1-64 letters, digits, dot, dash or underscore")
    if type(rev) is not int or rev < 1:
        raise OrderError("revision must be a whole number of at least 1")
    if not isinstance(owner, str) or not owner.strip() or len(owner) > 120:
        raise OrderError("owner must name one accountable person or role (1-120 characters)")
    if order.get("steps", list(STEPS)) != list(STEPS):
        raise OrderError("steps must be exactly %s" % ", ".join(STEPS))
    base = path.resolve().parent
    inputs = order.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != {"intake"} or not isinstance(inputs["intake"], dict):
        raise OrderError("inputs must hold exactly one entry, intake: {path, sha256}")
    ip, isha = inputs["intake"].get("path"), inputs["intake"].get("sha256")
    if not isinstance(isha, str) or not HEX64.match(isha):
        raise OrderError("inputs.intake.sha256 must be 64 lowercase hex characters")
    fleet = order.get("fleet")
    if fleet is not None:
        if not isinstance(fleet, dict) or not set(fleet) <= {"registry", "machine", "owner_epoch"}:
            raise OrderError("fleet must be {machine, owner_epoch[, registry]}")
        if not isinstance(fleet.get("machine"), str) or type(fleet.get("owner_epoch")) is not int \
                or fleet["owner_epoch"] < 1:
            raise OrderError("fleet needs machine (registered alias) and owner_epoch (whole number of at least 1)")
        reg = fleet.get("registry")
        if reg is None and not os.environ.get("SOLARIS_FLEET_ROOT"):
            raise OrderError("fleet.registry or SOLARIS_FLEET_ROOT is required")
        fleet = {"machine": fleet["machine"], "owner_epoch": fleet["owner_epoch"],
                 "registry": inside(base, reg, "fleet.registry") if reg is not None
                 else Path(os.environ["SOLARIS_FLEET_ROOT"]).resolve()}
    return {"order_id": oid, "revision": rev, "owner": owner.strip(), "base": base, "fleet": fleet,
            "intake": inside(base, ip, "inputs.intake.path"), "intake_sha": isha,
            "project_root": inside(base, order.get("project_root"), "project_root"),
            "outbox": inside(base, order.get("outbox"), "outbox"), "order_sha": sha_bytes(raw)}


class Journal:
    """Append-only, hash-chained JSON lines. A torn last line (no newline) is reported and cut on next append."""

    def __init__(self, path):
        self.path = Path(path)
        self.entries, self.torn = [], False
        if not self.path.exists():
            return
        data = self.path.read_bytes()
        if data and not data.endswith(b"\n"):
            self.torn = True
            data = data[:data.rfind(b"\n") + 1]
        self.good_len = len(data)
        prev = "0" * 64
        for n, line in enumerate(data.splitlines(), 1):
            try:
                rec = json.loads(line.decode("utf-8"))
                body = rec["entry"]
                ok = isinstance(rec, dict) and set(rec) == {"prev", "hash", "entry"} and rec["prev"] == prev and rec["hash"] == sha_bytes((prev + canon(body)).encode("utf-8"))
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                ok = False
            if not ok:
                raise OrderError("journal line %d does not verify; do not resume from it (inspect %s)" % (n, self.path))
            prev = rec["hash"]
            self.entries.append(body)
        self.head = prev

    def append(self, entry):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.torn:
            with open(self.path, "r+b") as f:
                f.truncate(self.good_len)
            self.torn = False
            self.append({"type": "recovered_torn_tail"})
        prev = getattr(self, "head", "0" * 64)
        h = sha_bytes((prev + canon(entry)).encode("utf-8"))
        with open(self.path, "ab") as f:
            f.write((canon({"prev": prev, "hash": h, "entry": entry}) + "\n").encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        self.head = h
        self.good_len = self.path.stat().st_size
        self.entries.append(entry)


def try_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


def load_activate():
    import importlib.util
    if not ACTIVATE.is_file():
        raise OrderError("project activation (G02) not found at %s" % ACTIVATE)
    spec = importlib.util.spec_from_file_location("solaris_activate", str(ACTIVATE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ledger_records(outbox):
    out = []
    p = outbox / "ledger.jsonl"
    if p.exists():
        for line in p.read_bytes().splitlines():
            try:
                out.append(json.loads(line.decode("utf-8")))
            except (ValueError, UnicodeDecodeError):
                out.append({"unreadable": True})
    return out


def render_brief(o, intake, status_sha):
    lines = ["# Handoff brief: %s revision %d" % (o["order_id"], o["revision"]), "",
             "- Owner: %s" % o["owner"],
             "- Project: %s (%s)" % (intake.get("name", ""), intake.get("project_type", "")),
             "- Brief: %s" % intake.get("brief", ""),
             "- Intake sha256: %s" % o["intake_sha"],
             "- Activated STATUS.md sha256: %s" % status_sha,
             "- Steps: activate, brief, deliver. Live deployment and every external step stay with the owner.", ""]
    return "\n".join(lines).encode("utf-8")


def check_intake(o):
    if sha_file(o["intake"]) != o["intake_sha"]:
        raise OrderError("intake does not match the sha256 in the work order; issue a new revision instead of "
                         "editing the input")


def check_fleet(o, identity):
    """G07: only the registered machine, for the order's owner at the current owner_epoch, may take the order."""
    if not o.get("fleet"):
        return
    if not identity:
        raise OrderError("this order is bound to fleet machine %s; pass --identity (or SOLARIS_MACHINE_IDENTITY)"
                         % o["fleet"]["machine"])
    import importlib.util
    if not REGISTRY.is_file():
        raise OrderError("fleet registry (G07) not found at %s" % REGISTRY)
    spec = importlib.util.spec_from_file_location("solaris_fleet_registry", str(REGISTRY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.check_claim(o["fleet"]["registry"], o["fleet"]["machine"], identity, o["owner"], o["fleet"]["owner_epoch"])
    except mod.Refused as e:
        raise OrderError("fleet claim refused: %s" % e)


def run(o, state, worker, stop_after=None, fail_at=None, identity=None):
    check_intake(o)  # before anything is created; checked again under the lock
    check_fleet(o, identity)  # likewise
    sdir = state / o["order_id"]
    sdir.mkdir(parents=True, exist_ok=True)
    fd = try_lock(sdir / ".worker.lock")
    if fd is None:
        holder = (sdir / "holder.json").read_text(encoding="utf-8") if (sdir / "holder.json").exists() else "{}"
        return 4, {"status": "held", "holder": json.loads(holder or "{}"), "steps": {}}
    try:
        check_fleet(o, identity)
        return _run(o, sdir, worker, stop_after, fail_at)
    finally:
        os.close(fd)


def _run(o, sdir, worker, stop_after, fail_at):
    j = Journal(sdir / "journal.jsonl")
    if j.entries and (j.entries[0].get("order_id") != o["order_id"] or j.entries[0].get("schema") != JOURNAL_SCHEMA):
        raise OrderError("journal belongs to another order")
    worked = [e.get("revision", 0) for e in j.entries if e.get("type") == "claim"]
    if worked and o["revision"] < max(worked):
        raise OrderError("revision %d is older than revision %d already worked; refusing a stale order"
                         % (o["revision"], max(worked)))
    check_intake(o)
    try:
        intake = json.loads(o["intake"].read_text(encoding="utf-8"))
        if not isinstance(intake, dict):
            raise ValueError
    except (OSError, ValueError):
        raise OrderError("intake is not a JSON object")
    notes = []
    if j.torn:
        notes.append("journal had a torn last line (a crash mid-write); it was cut and recorded")
    if not j.entries:
        j.append({"type": "open", "schema": JOURNAL_SCHEMA, "order_id": o["order_id"]})
    claims = [e for e in j.entries if e.get("type") == "claim"]
    released = bool(j.entries) and j.entries[-1].get("type") in ("release", "open")
    prior = claims[-1]["worker"] if claims else None
    takeover = bool(prior) and not released
    atomic_write(sdir / "holder.json", canon({"worker": worker, "order_id": o["order_id"],
                                             "revision": o["revision"], "pid": os.getpid()}).encode())
    j.append({"type": "claim", "worker": worker, "revision": o["revision"], "owner": o["owner"],
              "order_sha256": o["order_sha"], "takeover_from": prior if takeover else None})
    status_p = o["project_root"] / "STATUS.md"
    rdir = sdir / ("rev%d" % o["revision"])
    brief_p = rdir / "HANDOFF-BRIEF.md"
    report = {"order_id": o["order_id"], "revision": o["revision"], "owner": o["owner"], "worker": worker,
              "takeover_from": prior if takeover else None, "steps": {}, "notes": notes}

    def receipt(step):
        for e in reversed(j.entries):
            if e.get("type") == "step_done" and e.get("step") == step and e.get("revision") == o["revision"]:
                return e
        return None

    def current_inputs(step):
        # Owner is part of the order identity for brief (and activate): a same-revision owner
        # change must not reuse a brief that still names the previous owner.
        if step == "activate":
            return {"intake": o["intake_sha"], "owner": o["owner"]}
        if step == "brief":
            return {"intake": o["intake_sha"], "STATUS.md": sha_file(status_p), "owner": o["owner"]}
        return {"brief": sha_file(brief_p)}

    def outputs_hold(step, rec):
        if step == "activate":
            return sha_file(status_p) == rec["outputs"].get("STATUS.md")
        if step == "brief":
            return sha_file(brief_p) == rec["outputs"].get("brief")
        return any(r.get("key") == rec["outputs"].get("key") for r in ledger_records(o["outbox"]))

    # receipts chain by hash (brief's inputs hold STATUS.md's hash, deliver's hold the brief's), so a changed
    # upstream output makes every later receipt stale without a separate cascade flag
    for step in STEPS:
        rec = receipt(step)
        if rec:
            ins = current_inputs(step)
            if rec.get("inputs") == ins and outputs_hold(step, rec):
                report["steps"][step] = "reused (receipt by %s)" % rec.get("worker")
                continue
            why = "inputs changed" if rec.get("inputs") != ins else "recorded output no longer matches"
            j.append({"type": "stale", "step": step, "revision": o["revision"], "worker": worker, "reason": why})
            report["notes"].append("%s receipt is stale (%s); redone" % (step, why))
        ins = current_inputs(step)
        if step == "activate":
            res = load_activate().activate(str(o["project_root"]), intake)
            if res.get("status") not in ("complete", "partial"):
                j.append({"type": "step_failed", "step": step, "revision": o["revision"], "worker": worker,
                          "status": res.get("status"), "errors": (res.get("errors") or [])[:3],
                          "problems": (res.get("problems") or [])[:3]})
                report["steps"][step] = "failed: %s" % "; ".join(str(x) for x in (res.get("errors") or
                                                                                  res.get("problems") or [res.get("status")]))
                j.append({"type": "release", "worker": worker})
                return 1, report
            outs = {"STATUS.md": sha_file(status_p), "changed": res.get("changed", [])}
            outcome = "done (activation %s, changed %d)" % (res["status"], len(res.get("changed", [])))
        elif step == "brief":
            data = render_brief(o, intake, ins["STATUS.md"])
            atomic_write(brief_p, data)
            outs = {"brief": sha_bytes(data)}
            outcome = "done"
        else:
            key = sha_bytes(("%s\n%d\n%s" % (o["order_id"], o["revision"], ins["brief"])).encode())
            o["outbox"].mkdir(parents=True, exist_ok=True)
            lfd = os.open(str(o["outbox"] / ".ledger.lock"), os.O_RDWR | os.O_CREAT, 0o644)
            try:
                fcntl.flock(lfd, fcntl.LOCK_EX)
                if any(r.get("key") == key for r in ledger_records(o["outbox"])):
                    outcome = "done (already delivered; duplicate suppressed)"
                else:
                    line = canon({"key": key, "order_id": o["order_id"], "revision": o["revision"],
                                  "owner": o["owner"], "brief_sha256": ins["brief"], "delivered_by": worker})
                    lp = o["outbox"] / "ledger.jsonl"
                    torn = lp.exists() and lp.stat().st_size and not lp.read_bytes().endswith(b"\n")
                    with open(lp, "ab") as f:
                        # a torn last record stays unreadable on its own line instead of swallowing this one
                        f.write((("\n" if torn else "") + line + "\n").encode("utf-8"))
                        f.flush()
                        os.fsync(f.fileno())
                    outcome = "done (delivered)"
            finally:
                os.close(lfd)
            outs = {"key": key}
        if fail_at == step:
            os._exit(CRASH_EXIT)  # crash drill: the effect happened, the receipt was never written
        j.append({"type": "step_done", "step": step, "revision": o["revision"], "worker": worker,
                  "inputs": ins, "outputs": outs})
        report["steps"][step] = outcome
        if stop_after == step and step != STEPS[-1]:
            j.append({"type": "release", "worker": worker, "stopped_after": step})
            return 3, report
    j.append({"type": "release", "worker": worker})
    superseded = sorted({r.get("revision") for r in ledger_records(o["outbox"])
                         if r.get("order_id") == o["order_id"] and isinstance(r.get("revision"), int)
                         and r["revision"] < o["revision"]})
    if superseded:
        report["notes"].append("earlier deliveries of this order (revision %s) remain in the ledger as "
                               "superseded; a delivery cannot be recalled" % ", ".join(map(str, superseded)))
    return 0, report


def status(o, state):
    sdir = state / o["order_id"]
    j = Journal(sdir / "journal.jsonl")
    done = {}
    for e in j.entries:
        if e.get("type") == "step_done" and e.get("revision") == o["revision"]:
            done[e["step"]] = e.get("worker")
        if e.get("type") == "stale" and e.get("revision") == o["revision"]:
            done.pop(e["step"], None)
    claims = [e for e in j.entries if e.get("type") == "claim"]
    open_claim = bool(claims) and j.entries[-1].get("type") not in ("release",)
    return {"order_id": o["order_id"], "revision": o["revision"], "owner": o["owner"],
            "steps": {s: ("done by %s" % done[s]) if s in done else "pending" for s in STEPS},
            "last_worker": claims[-1]["worker"] if claims else None,
            "interrupted": open_claim, "journal_entries": len(j.entries), "journal_torn_tail": j.torn,
            "deliveries": [r for r in ledger_records(o["outbox"]) if r.get("order_id") == o["order_id"]]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Restartable local work orders (see the module docstring).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run or resume a work order")
    s = sub.add_parser("status", help="show what is done, by whom, and what is pending")
    for p in (r, s):
        p.add_argument("order")
        p.add_argument("--state", help="journal folder (default: .handoff next to the order)")
        p.add_argument("--json", action="store_true")
    r.add_argument("--worker", required=True, help="name of the worker running this command")
    r.add_argument("--stop-after", choices=STEPS[:-1], help="stop cleanly after this step (handoff drill)")
    r.add_argument("--identity", default=os.environ.get("SOLARIS_MACHINE_IDENTITY"),
                   help="machine identity file, required for orders with a fleet block (G07)")
    r.add_argument("--fail-at", choices=STEPS, help="crash after this step's effect, before its receipt (drill)")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        o = load_order(a.order)
        state = Path(a.state).resolve() if a.state else o["base"] / ".handoff"
        if a.cmd == "run":
            if not a.worker.strip() or len(a.worker) > 80:
                raise OrderError("--worker must be 1-80 characters")
            code, rep = run(o, state, a.worker.strip(), a.stop_after, a.fail_at, a.identity)
        else:
            code, rep = 0, status(o, state)
    except OrderError as e:
        sys.stderr.write("error: %s\n" % e)
        return 2
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    else:
        print("%s revision %s (owner %s)%s" % (rep.get("order_id", o["order_id"]), o["revision"], o["owner"],
                                               ": held by %s" % rep["holder"].get("worker") if code == 4 else ""))
        for k, v in rep.get("steps", {}).items():
            print("  %-8s %s" % (k, v))
        for n in rep.get("notes", []):
            print("  note: %s" % n)
        if rep.get("takeover_from"):
            print("  resumed work left unfinished by %s" % rep["takeover_from"])
    return code


if __name__ == "__main__":
    sys.exit(main())
