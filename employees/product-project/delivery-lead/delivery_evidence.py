#!/usr/bin/env python3
"""delivery_evidence.py: evidence for a multi-specialist customer delivery (G39).

The delivery lead does not perform specialist work. This tool records that a specialist's existing tool
actually ran in the delivery folder (exit code, tool and output sha256), and later checks a delivery claim
against those records, the files on disk and the G04 work-order status:

  record ROOT --role DEPT/ROLE --outputs PATH... [--inputs PATH...] [--ok-exit 0|0,1] [--worker NAME] [--timeout S]
         -- CMD ARGS...
  verify ROOT --claims CLAIMS.json [--json] [--out FILE] [--strict]

Records live in ROOT/.delivery/contributions.jsonl, one JSON object per line, each carrying the sha256 of
the previous line, and .delivery/head.json holds the sha256 of the last one, so an edited, removed or replaced
record breaks the chain (self-consistency only: someone who rewrites every line and the head is not caught). A record is appended only after the
command has finished; a recorder killed earlier leaves no record and the step is simply run again.
Output digests come from the G05 assurance engine (artifact_digests) and are compared with binding_state,
so a changed output or a changed tool makes the contribution stale and names the command to re-run.
Inputs are bound too (r2, r3): every existing file or folder named in the command (plain, --flag VALUE, --flag=VALUE,
or an absolute path inside ROOT; a named symlink is refused) that is not an output or a .py tool, plus
--inputs PATH... for files and folders the tool reads indirectly, is digested after the run; a later change,
addition or removal makes the contribution stale (inputs_changed). A recorded output file that has disappeared
is stale (removed). The run log must still exist and match its digest. Exit 1 (disclosed gaps) may be accepted
with --ok-exit 0,1 only; it gives the separate state evidenced_with_gaps, which counts only when the claim for
that role says "accept_gaps": true, and then the verdict is GO_WITH_GAPS, never a plain GO. The last record is
unconfirmed while head.json lags one behind it (a cut-short append or a record added by hand): it vouches for
nothing until the next append confirms it. A claim without a work order is EVIDENCED_NO_ORDER, never GO.
An input the run itself rewrote or removed (r5) is bound only to its after-run bytes, so what the tool read is not shown: the
contribution is evidenced_with_gaps (gap input_rewritten_by_run, naming the files) under the same accept_gaps rule
as exit 1, so it is NO_GO unless the claim accepts gaps and then GO_WITH_GAPS, never a plain GO.

Exit codes: record 0 ok, 1 recorded but not ok, 2 invalid input (nothing appended), 3 ledger does not
verify (nothing appended), 4 ledger lock held. verify 0 GO, GO_WITH_GAPS or EVIDENCED_NO_ORDER (read the
verdict word), 1 NO_GO, 2 invalid input. verify --strict (r5, for callers that gate on the exit code): 0 only for
a clean GO, 1 NO_GO, 2 invalid input, 3 GO_WITH_GAPS, 4 EVIDENCED_NO_ORDER. The report says clean_go either way.

Records are evidence that a command ran here with that exit code and produced these bytes. They do not
show that the output is correct beyond each tool's own checks, and --worker is a plain-text claim.
"""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
QOS = REPO / "employees" / "quality-security" / "assurance" / "quality_os.py"
HANDOFF = REPO / "employees" / "infrastructure" / "fleet-dispatcher" / "handoff.py"
LEDGER_DIR = ".delivery"
LEDGER = "contributions.jsonl"
HEAD = "head.json"  # sha256 of the last record, so the last record cannot be edited unnoticed either
GENESIS = "0" * 64
ROLE_RE = re.compile(r"^[a-z][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
TOKEN_RE = re.compile(r"ghp_[A-Za-z0-9]{20,}|github[_]pat_|gho_[A-Za-z0-9]{20,}|\bsk-[A-Za-z0-9]{20,}|xox[abp]-|"
                      r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY")
MAX_LINE = 1 << 20
MAX_TIMEOUT = 3600
STEPS = ("activate", "brief", "deliver")
LIMITS = ("records show that a command ran in this folder with that exit code, read these inputs and produced "
          "these bytes; correctness beyond each tool's own checks is not shown; worker names are plain-text claims; "
          "inputs a tool reads without being named in the command or --inputs are not bound")
OK_EXITS = {0, 1}


class Invalid(Exception):
    pass


class LedgerBroken(Exception):
    pass


def _load_qos():
    """Load the G05 engine by path without leaving a bytecode cache next to it."""
    spec = importlib.util.spec_from_file_location("solaris_quality_os_g39", str(QOS))
    if spec.name in sys.modules:
        return sys.modules[spec.name]
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses in the engine look their module up here
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    finally:
        sys.dont_write_bytecode = keep
    return mod


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic(path, data):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _root(raw):
    root = Path(raw)
    if not root.is_dir() or root.is_symlink():
        raise Invalid("ROOT must be an existing folder (not a symlink)")
    return root


def read_ledger(root):
    """Return (records, good_byte_length, torn_tail). Raises LedgerBroken on an edited or reordered record."""
    p = root / LEDGER_DIR / LEDGER
    hp = root / LEDGER_DIR / HEAD
    if not p.exists():
        if hp.exists() or hp.is_symlink():
            raise LedgerBroken("head.json exists but the ledger is missing (deleted ledger); restore it")
        return [], 0, False
    if p.is_symlink() or not p.is_file():
        raise LedgerBroken("the ledger is not a regular file")
    raw = p.read_bytes()
    lines = raw.split(b"\n")
    tail = lines.pop()  # bytes after the last newline: empty when the file ends cleanly
    recs, prev, good = [], GENESIS, 0
    for n, line in enumerate(lines, 1):
        if len(line) > MAX_LINE:
            raise LedgerBroken("line %d is too long" % n)
        try:
            r = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise LedgerBroken("line %d is not JSON" % n)
        if not isinstance(r, dict) or r.get("prev") != prev or r.get("seq") != n - 1:
            raise LedgerBroken("line %d does not follow line %d (edited, removed or reordered record)" % (n, n - 1))
        prev = hashlib.sha256(line).hexdigest()
        good += len(line) + 1
        recs.append(r)
    if not recs and (hp.exists() or hp.is_symlink()):
        raise LedgerBroken("head.json exists but the ledger holds no record (emptied ledger); restore it")
    if recs:
        try:
            head = json.loads(hp.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            raise LedgerBroken("head.json is missing or unreadable while records exist")
        last_seq = len(recs) - 1
        # the head may lag by one record when an append was cut short between the line and the head write
        lag_ok = last_seq >= 1 and head == {"seq": last_seq - 1, "sha256": recs[-1]["prev"]}
        if head != {"seq": last_seq, "sha256": prev} and not lag_ok:
            raise LedgerBroken("the last record does not match head.json (edited or replaced record)")
    torn = bool(tail)
    if torn:
        try:
            json.loads(tail.decode("utf-8"))
            raise LedgerBroken("the last record has no newline but parses; it was written by something else")
        except (UnicodeDecodeError, ValueError):
            pass  # an append cut short: never committed, ignored
    return recs, good, torn


def head_lags(root, recs):
    """True when head.json names the record before the last one: the last record is then unconfirmed."""
    if not recs:
        return False
    try:
        head = json.loads((root / LEDGER_DIR / HEAD).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    return head == {"seq": len(recs) - 2, "sha256": recs[-1].get("prev")}


def _safe_rel(a):
    return not os.path.isabs(a) and ".." not in Path(a).parts and Path(a).parts[:1] != (LEDGER_DIR,)


def _named_inputs(root, argv, outputs, explicit):
    """Explicit --inputs plus every existing file or folder named in the command (plain, --flag VALUE, --flag=VALUE,
    or absolute inside ROOT, or relative with a ".." segment that resolves inside ROOT) that is not an output or a
    .py tool (tools are bound separately). A symlink named in the command is refused. Returns a sorted,
    de-duplicated list of relative paths, and the sorted arguments that name an existing path outside ROOT
    (recorded as unbound_inputs: they cannot be re-checked later)."""
    outs = {Path(o).as_posix().rstrip("/") for o in outputs}
    named, unbound = [], []
    for i in explicit or []:
        if not _safe_rel(i):
            raise Invalid("input %r must be a relative path inside ROOT and outside %s" % (i[:80], LEDGER_DIR))
        if not (root / i).exists() or (root / i).is_symlink():
            raise Invalid("input %r does not exist in ROOT (or is a symlink)" % i[:80])
        named.append(Path(i).as_posix().rstrip("/"))
    base = Path(os.path.realpath(str(root)))
    for a in argv[1:]:
        if a.startswith("-"):
            a = a.split("=", 1)[1] if "=" in a else ""  # --flag=VALUE names VALUE
        if not a or a.endswith(".py"):
            continue
        if os.path.isabs(a):
            if Path(a).is_symlink():
                raise Invalid("input %r named in the command is a symlink; name its target" % a[:80])
            try:
                a = Path(os.path.realpath(a)).relative_to(base).as_posix()
            except ValueError:
                if os.path.exists(a):
                    unbound.append(a[:200])  # outside ROOT: cannot be re-checked later, but the record says so
                continue
        elif ".." in Path(a).parts:  # inp/../inp/a.csv or ../ROOT/inp/a.csv: resolve as the OS does (M39 r3 P3-1)
            j = os.path.join(str(root), a)
            if os.path.islink(j):
                raise Invalid("input %r named in the command is a symlink; name its target" % a[:80])
            try:
                a = Path(os.path.realpath(j)).relative_to(base).as_posix()
            except ValueError:
                if os.path.exists(j):
                    unbound.append(a[:200])
                continue
        if not _safe_rel(a):
            continue
        k = Path(a).as_posix().rstrip("/")
        if k in outs or k in ("", "."):
            continue
        q = root / a
        if q.is_symlink():
            raise Invalid("input %r named in the command is a symlink; name its target" % a[:80])
        if q.is_file() or q.is_dir():
            named.append(k)
    return sorted(set(named)), sorted(set(unbound))[:50]


def _rewritten(before, after, touched, root):
    """Existing inputs changed/removed by the run; only stable SQLite databases allow
    their conventional -shm index exception. A suffix by itself is never evidence."""
    def sqlite_index(k):
        db = k[:-4]
        if not k.endswith("-shm") or db not in before or before[db] != after.get(db):
            return False
        try:
            with open(root / db, "rb") as fh:
                return fh.read(16) == b"SQLite format 3\x00"
        except OSError:
            return False
    return [k for k in touched if k in before and not sqlite_index(k)]


def _role_ok(role):
    if not isinstance(role, str) or not ROLE_RE.match(role):
        raise Invalid("--role must look like department/role, for example data/data-engineer")
    d = REPO / "employees" / role
    if not (d / "SKILL.md").is_file():
        raise Invalid("%s is not an employee in this repository (no employees/%s/SKILL.md)" % (role, role))


def _tool_digests(argv, root):
    """sha256 of every .py file named in the command, keyed repo:<path> or root:<path> so it can be
    re-checked later; a script elsewhere is keyed other:<name> and cannot be re-checked."""
    out = {}
    base = root.resolve()
    for a in argv:
        if not a.endswith(".py"):
            continue
        p = Path(a) if os.path.isabs(a) else (root / a)
        if not p.is_file():
            continue
        rp = p.resolve()
        if REPO in rp.parents:
            key = "repo:" + rp.relative_to(REPO).as_posix()
        elif base in rp.parents:
            key = "root:" + rp.relative_to(base).as_posix()
        else:
            key = "other:" + p.name
        out[key] = _sha_file(p)
    return out


def _tool_path(key, root):
    kind, _, rel = key.partition(":")
    return {"repo": REPO, "root": root.resolve()}.get(kind, None), rel


def cmd_record(ns):
    root = _root(ns.root)
    _role_ok(ns.role)
    argv = list(ns.cmd)
    if not argv:
        raise Invalid("give the specialist command after --")
    if any(TOKEN_RE.search(a) for a in argv):
        raise Invalid("a credential-shaped value is in the command; it is never recorded")
    if not ns.outputs:
        raise Invalid("--outputs is required: name the files the specialist produces")
    for o in ns.outputs:
        if os.path.isabs(o) or ".." in Path(o).parts or Path(o).parts[:1] == (LEDGER_DIR,):
            raise Invalid("output %r must be a relative path inside ROOT and outside %s" % (o[:80], LEDGER_DIR))
    try:
        ok_exit = sorted({int(x) for x in ns.ok_exit.split(",")})
    except ValueError:
        raise Invalid("--ok-exit must be comma-separated integers")
    if 0 not in ok_exit or not set(ok_exit) <= OK_EXITS:
        raise Invalid("--ok-exit must be 0 or 0,1 (exit 1 means disclosed gaps; other exits never count)")
    if not (0 < ns.timeout <= MAX_TIMEOUT):
        raise Invalid("--timeout must be between 0 and %d seconds" % MAX_TIMEOUT)
    d = root / LEDGER_DIR
    if d.is_symlink():
        raise Invalid("%s must not be a symlink" % LEDGER_DIR)
    (d / "logs").mkdir(parents=True, exist_ok=True)
    # Inspect a committed snapshot before running the specialist command. An
    # appender holds LOCK_EX between its ledger write and atomic head update.
    lockp = d / "ledger.lock"
    preflight_fd = os.open(str(lockp), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(preflight_fd, fcntl.LOCK_SH | (fcntl.LOCK_NB if ns.no_wait else 0))
        except BlockingIOError:
            print("ledger lock held by another recorder; nothing appended", file=sys.stderr)
            return 4
        read_ledger(root)  # broken committed ledgers still refuse before execution
    finally:
        os.close(preflight_fd)
    qos = _load_qos()
    named_inputs, unbound_inputs = _named_inputs(root, argv, ns.outputs, ns.inputs)
    try:
        inputs_before = qos.artifact_digests(root, named_inputs) if named_inputs else {}
    except ValueError as e:
        raise Invalid("inputs: %s" % str(e)[:200])
    log = d / "logs" / ("%s.log" % uuid.uuid4().hex)
    started = _now()
    with open(log, "wb") as lf:
        try:
            rc = subprocess.run(argv, cwd=str(root), stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                timeout=ns.timeout).returncode
            why = None
        except subprocess.TimeoutExpired:
            rc, why = None, "timeout after %gs" % ns.timeout
        except OSError as e:
            rc, why = None, "could not start: %s" % type(e).__name__
    outputs = {}
    try:
        outputs = qos.artifact_digests(root, ns.outputs)
    except ValueError as e:
        why = why or ("outputs: %s" % str(e)[:200])
    inputs = {}
    try:
        inputs = qos.artifact_digests(root, named_inputs) if named_inputs else {}
    except ValueError as e:
        why = why or ("inputs after the run: %s" % str(e)[:200])
    touched = sorted(k for k in set(inputs) | set(inputs_before) if inputs.get(k) != inputs_before.get(k))
    rewritten = _rewritten(inputs_before, inputs, touched, root)
    ok = why is None and rc in ok_exit
    rec = {"role": ns.role, "worker": ns.worker, "argv": argv, "ok_exit": ok_exit, "exit": rc, "ok": ok,
           "reason": why if why else (None if ok else "exit %s not in %s" % (rc, ok_exit)),
           "claimed_outputs": list(ns.outputs), "outputs": outputs, "tools": _tool_digests(argv, root),
           "claimed_inputs": named_inputs, "inputs": inputs, "inputs_changed_during_run": touched[:50],
           "inputs_rewritten_during_run": rewritten[:50],
           "unbound_inputs": unbound_inputs,
           "log": log.relative_to(root).as_posix(), "log_sha256": _sha_file(log),
           "started": started, "ended": _now(), "worker_identity": "claimed in plain text, not authenticated"}
    fd = os.open(str(lockp), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB if ns.no_wait else fcntl.LOCK_EX)
        except OSError:
            print("ledger lock held by another recorder; nothing appended", file=sys.stderr)
            return 4
        recs, good, torn = read_ledger(root)
        p = d / LEDGER
        prev = GENESIS
        if recs:
            with open(p, "rb") as f:
                body = f.read(good)
            prev = hashlib.sha256(body[:-1].split(b"\n")[-1]).hexdigest()
        rec = dict({"seq": len(recs), "prev": prev}, **rec)
        if torn:
            rec["dropped_torn_tail"] = True
        line = json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        with open(p, "ab") as f:
            if torn:
                f.truncate(good)  # the cut-short record was never committed
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        _atomic(d / HEAD, json.dumps({"seq": rec["seq"], "sha256": hashlib.sha256(line[:-1]).hexdigest()},
                                     sort_keys=True).encode("utf-8"))
    finally:
        os.close(fd)
    print("%s record %d: %s exit %s%s" % (ns.role, rec["seq"], "ok" if ok else "NOT OK", rc,
                                          "" if ok else " (%s)" % rec["reason"]))
    return 0 if ok else 1


def _load_claims(path, root):
    try:
        c = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise Invalid("claims file unreadable: %s" % type(e).__name__)
    if not isinstance(c, dict) or c.get("schema") != "solaris.delivery-claims/1":
        raise Invalid('claims must be an object with "schema": "solaris.delivery-claims/1"')
    contribs = c.get("contributions")
    if not isinstance(contribs, list) or not contribs:
        raise Invalid("claims.contributions must be a non-empty list")
    seen = set()
    for x in contribs:
        if not isinstance(x, dict) or not isinstance(x.get("outputs"), list) or not x["outputs"] or \
                not all(isinstance(o, str) and o for o in x["outputs"]):
            raise Invalid("each contribution needs a role and a non-empty outputs list")
        _role_ok(x.get("role"))
        if not isinstance(x.get("accept_gaps", False), bool):
            raise Invalid("accept_gaps must be true or false")
        if x["role"] in seen:
            raise Invalid("role %s is claimed twice" % x["role"])
        seen.add(x["role"])
    order = c.get("order")
    if order is not None and (not isinstance(order, str) or os.path.isabs(order) or ".." in Path(order).parts
                              or not (root / order).is_file()):
        raise Invalid("claims.order must name a work order file inside ROOT")
    return c


def _log_ok(root, r):
    lg = r.get("log")
    if not isinstance(lg, str) or not lg.startswith(LEDGER_DIR + "/logs/") or ".." in Path(lg).parts:
        return False
    p = root / lg
    return p.is_file() and not p.is_symlink() and _sha_file(p) == r.get("log_sha256")


def _contribution(qos, root, claim, recs, unconfirmed_seq=None):
    role, want = claim["role"], claim["outputs"]
    mine = [r for r in recs if r.get("role") == role]
    out = {"role": role, "outputs": want}
    if not mine:
        out.update(state="unevidenced", action="run the %s tool through delivery_evidence.py record" % role)
        return out
    r = mine[-1]
    out.update(record=r["seq"], worker=r.get("worker"), exit=r.get("exit"), argv=r.get("argv"))
    oe = r.get("ok_exit") if isinstance(r.get("ok_exit"), list) else [0]
    if not r.get("ok") or r.get("exit") not in oe or not set(oe) <= OK_EXITS:  # exit 2 never counts, whatever the record says
        out.update(state="failed", reason=r.get("reason"), action="fix the cause and re-run: %s" % " ".join(r["argv"]))
        return out
    if unconfirmed_seq is not None and r.get("seq") == unconfirmed_seq:
        out.update(state="unconfirmed", action="head.json does not confirm this last record (cut-short append or a "
                   "record added by hand); re-run: %s" % " ".join(r["argv"]))
        return out
    if not _log_ok(root, r):
        out.update(state="log_mismatch", action="the run log is missing or changed; re-run: %s" % " ".join(r["argv"]))
        return out
    recorded = r.get("outputs") or {}
    under = lambda p: any(p == w.rstrip("/") or p.startswith(w.rstrip("/") + "/") for w in want)
    gone = sorted(p for p in recorded if under(p) and not (root / p).is_file())
    if gone:
        out.update(state="stale", removed=gone[:20], action="a recorded output was removed; re-run: %s" % " ".join(r["argv"]))
        return out
    try:
        current = qos.artifact_digests(root, want)
    except ValueError as e:
        out.update(state="stale", reason="output no longer readable: %s" % str(e)[:200],
                   action="re-run: %s" % " ".join(r["argv"]))
        return out
    uncovered = sorted(p for p in current if p not in recorded)
    if uncovered:
        out.update(state="not_covered", not_recorded=uncovered[:20],
                   action="the record does not cover these files; re-run with them in --outputs")
        return out
    state, detail = qos.binding_state({"digests": {p: recorded[p] for p in current}}, {"digests": current})
    if state not in ("carried_forward", "current"):
        out.update(state="stale", changed=detail.get("changed", []), action="re-run: %s" % " ".join(r["argv"]))
        return out
    drift = []
    for key, h in sorted((r.get("tools") or {}).items()):
        base, rel = _tool_path(key, root)
        if base is None:
            continue
        p = base / rel
        if not p.is_file() or _sha_file(p) != h:
            drift.append(key)
    if drift:
        out.update(state="stale", tool_changed=drift, action="tool source changed; re-run: %s" % " ".join(r["argv"]))
        return out
    if r.get("unbound_inputs"):
        out["unbound_inputs"] = r["unbound_inputs"][:20]
        out["unbound_note"] = "named in the command but outside ROOT: read by the run, never re-checked by verify"
    ins = r.get("inputs") or {}
    if r.get("claimed_inputs"):
        try:
            now = qos.artifact_digests(root, r["claimed_inputs"])
        except ValueError:
            now = {}
        moved = sorted(k for k in set(ins) | set(now) if ins.get(k) != now.get(k))
        if moved:
            out.update(state="stale", inputs_changed=moved[:20],
                       action="an input changed, appeared or disappeared after the run; re-run: %s" % " ".join(r["argv"]))
            return out
    gap_kinds = []
    if r.get("exit") == 1:
        gap_kinds.append("exit_1")
    rewritten = r.get("inputs_rewritten_during_run", r.get("inputs_changed_during_run"))  # older record: every change
    rewritten = rewritten if isinstance(rewritten, list) else []
    if rewritten:  # r5: the record binds the after-run bytes only, so what the tool read is not shown
        gap_kinds.append("input_rewritten_by_run")
        out["inputs_rewritten_by_run"] = rewritten[:20]
    if gap_kinds:
        out.update(state="evidenced_with_gaps", gap_kinds=gap_kinds, gaps_accepted_by_claim=bool(claim.get("accept_gaps")))
        if not claim.get("accept_gaps"):
            out["action"] = ("%s and the claim does not accept gaps for this role; fix the cause and re-run, or set "
                             "\"accept_gaps\": true in the claim" % _gap_text(out))
        return out
    out["state"] = "evidenced"
    return out


def _gap_text(c):
    """Plain words for a contribution's gaps, e.g. 'exit 1 (disclosed gaps); input rewritten by the run: a.csv'."""
    words = []
    for k in c.get("gap_kinds") or []:
        if k == "exit_1":
            words.append("exit 1 (disclosed gaps)")
        elif k == "input_rewritten_by_run":
            words.append("the run rewrote its input %s, so only the after-run bytes are bound"
                         % ", ".join(c.get("inputs_rewritten_by_run") or []))
    return "; ".join(words)


def _handoff(root, order):
    env = dict({name: os.environ[name] for name in (
                   'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                   'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                   'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                   'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                   'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                   'GITHUB_ACTIONS',
               ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")
    # This status call needs its selected fleet registry, not ambient credentials.
    if "SOLARIS_FLEET_ROOT" in os.environ:
        env["SOLARIS_FLEET_ROOT"] = os.environ["SOLARIS_FLEET_ROOT"]
    p = subprocess.run([sys.executable, str(HANDOFF), "status", order, "--json"], cwd=str(root),
                       capture_output=True, text=True, timeout=120, env=env)
    if p.returncode != 0:
        return {"state": "invalid", "reason": (p.stderr or p.stdout).strip()[:300]}
    try:
        s = json.loads(p.stdout)
    except ValueError:
        return {"state": "invalid", "reason": "status output is not JSON"}
    steps = s.get("steps") or {}
    workers = {k: v[len("done by "):] for k, v in steps.items() if isinstance(v, str) and v.startswith("done by ")}
    cur = [d for d in s.get("deliveries") or [] if d.get("revision") == s.get("revision")]
    out = {"order_id": s.get("order_id"), "revision": s.get("revision"), "owner": s.get("owner"),
           "steps": steps, "workers": workers, "deliveries_this_revision": len(cur),
           "interrupted": s.get("interrupted")}
    intake_ok = True
    try:
        od = json.loads((root / order).read_text(encoding="utf-8"))
        ip = (root / order).parent / od["inputs"]["intake"]["path"]
        intake_ok = ip.is_file() and _sha_file(ip) == od["inputs"]["intake"]["sha256"]
    except (OSError, ValueError, KeyError, TypeError):
        intake_ok = False
    if not intake_ok:
        out.update(state="intake_changed", action="the intake no longer matches the sha256 in the work order; "
                   "issue a new revision and resume it")
    elif set(workers) != set(STEPS):
        out.update(state="incomplete", action="resume the order: handoff.py run %s --worker NAME" % order)
    elif len(cur) != 1:
        out.update(state="delivery_count_wrong", action="exactly one delivery per revision is expected")
    else:
        out["state"] = "delivered"
    return out


def cmd_verify(ns):
    root = _root(ns.root)
    claims = _load_claims(ns.claims, root)
    qos = _load_qos()
    rep = {"schema": "solaris.delivery-verdict/1", "limits": LIMITS}
    try:
        recs, _, torn = read_ledger(root)
        lag = head_lags(root, recs)
        rep["ledger"] = {"records": len(recs), "chain": "intact", "torn_tail_ignored": torn,
                         "last_record_unconfirmed": lag}
    except LedgerBroken as e:
        recs = []
        rep["ledger"] = {"chain": "broken", "reason": str(e)}
    unconf = len(recs) - 1 if rep["ledger"].get("last_record_unconfirmed") else None
    rep["contributions"] = [_contribution(qos, root, c, recs, unconf) for c in claims["contributions"]]
    if rep["ledger"]["chain"] == "broken":
        for c in rep["contributions"]:
            c.update(state="unevidenced", action="the ledger does not verify; no record can be trusted")
    claimed = {c["role"] for c in claims["contributions"]}
    rep["unclaimed_records"] = sorted({r["role"] for r in recs if r.get("role") not in claimed})
    if claims.get("order"):
        rep["handoff"] = _handoff(root, claims["order"])
    blockers = [c["role"] for c in rep["contributions"] if not (c["state"] == "evidenced" or (
        c["state"] == "evidenced_with_gaps" and c.get("gaps_accepted_by_claim")))]
    gaps = [c["role"] for c in rep["contributions"] if c["state"] == "evidenced_with_gaps"]
    if "handoff" in rep and rep["handoff"]["state"] != "delivered":
        blockers.append("handoff")
    if rep["ledger"]["chain"] == "broken":
        blockers.append("ledger")
    if blockers:
        rep["verdict"] = "NO_GO"
    elif not claims.get("order"):
        rep["verdict"] = "EVIDENCED_NO_ORDER"  # contributions only: no work order was named, so no delivery GO
    else:
        rep["verdict"] = "GO_WITH_GAPS" if gaps else "GO"
    rep["blockers"] = blockers
    rep["gaps"] = gaps
    rep["gap_details"] = {c["role"]: c.get("gap_kinds", []) for c in rep["contributions"]
                          if c["state"] == "evidenced_with_gaps"}
    rep["clean_go"] = rep["verdict"] == "GO"
    rep["exit_policy"] = "strict" if ns.strict else "default"
    rep["work_order"] = "named" if claims.get("order") else "not named: this is not a delivery GO"
    data = json.dumps(rep, indent=2, sort_keys=True) + "\n"
    if ns.out:
        _atomic(ns.out, data.encode("utf-8"))
    if ns.json:
        sys.stdout.write(data)
    else:
        print("delivery verdict: %s%s" % (rep["verdict"], {
            "GO_WITH_GAPS": " (accepted gaps, not a clean GO: %s)" % "; ".join(
                "%s: %s" % (c["role"], _gap_text(c)) for c in rep["contributions"] if c["state"] == "evidenced_with_gaps"),
            "EVIDENCED_NO_ORDER": " (contributions evidenced; no work order named, so this is not a delivery GO)"}.get(
                rep["verdict"], "")))
        print("ledger: %s" % (rep["ledger"].get("reason") or "%d records, chain intact" % rep["ledger"]["records"]))
        for c in rep["contributions"]:
            extra = "  (%s: %s)" % (_gap_text(c), "claim accepts gaps" if c.get("gaps_accepted_by_claim") else
                                    "claim does not accept gaps") if c["state"] == "evidenced_with_gaps" else ""
            print("  %-40s %s%s%s" % (c["role"], c["state"], extra, "  -> " + c["action"] if c.get("action") and
                                      c["state"] != "evidenced" else ""))
        if "handoff" in rep:
            h = rep["handoff"]
            print("  %-40s %s %s" % ("handoff (G04 work order)", h["state"], h.get("workers", h.get("reason", ""))))
        print("limits: " + LIMITS)
    if ns.strict:
        return {"GO": 0, "NO_GO": 1, "GO_WITH_GAPS": 3, "EVIDENCED_NO_ORDER": 4}[rep["verdict"]]
    return 1 if rep["verdict"] == "NO_GO" else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd_name", required=True)
    r = sub.add_parser("record", help="run one specialist command in ROOT and record its evidence")
    r.add_argument("root")
    r.add_argument("--role", required=True)
    r.add_argument("--outputs", nargs="+", action="extend", required=True, help="repeatable; every output path is retained")
    r.add_argument("--inputs", nargs="+", action="extend", help="repeatable; files or folders the command reads (beyond those named in it); "
                   "a later change makes the record stale")
    r.add_argument("--ok-exit", default="0", help="0 (default) or 0,1 to accept disclosed gaps")
    r.add_argument("--worker", default="unnamed")
    r.add_argument("--timeout", type=float, default=600)
    r.add_argument("--no-wait", action="store_true", help="exit 4 instead of waiting for the ledger lock")
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = []
    if argv[:1] == ["record"]:
        if "--" not in argv:
            print("invalid: give the specialist command after --", file=sys.stderr)
            return 2
        i = argv.index("--")
        argv, cmd = argv[:i], argv[i + 1:]
    v = sub.add_parser("verify", help="check a delivery claim against records, files and the work order")
    v.add_argument("root")
    v.add_argument("--claims", required=True)
    v.add_argument("--json", action="store_true")
    v.add_argument("--out")
    v.add_argument("--strict", action="store_true", help="exit 0 only for a clean GO: 3 GO_WITH_GAPS, "
                   "4 EVIDENCED_NO_ORDER, 1 NO_GO (default: 0 for all but NO_GO)")
    ns = ap.parse_args(argv)
    ns.cmd = cmd
    try:
        return cmd_record(ns) if ns.cmd_name == "record" else cmd_verify(ns)
    except Invalid as e:
        print("invalid: %s" % e, file=sys.stderr)
        return 2
    except LedgerBroken as e:
        print("ledger does not verify, nothing appended: %s" % e, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
