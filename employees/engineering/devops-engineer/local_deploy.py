#!/usr/bin/env python3
"""Local deployment preflight, deploy and rollback drill on disposable fixtures (G08).

A plan names the intended environment, the target folder, the artifact (folder, revision, sha256) and the
health conditions. `preflight` checks, without writing anything:

  environment   the target's ENVIRONMENT.json names the plan's environment and is a local fixture
  artifact      the artifact's REVISION file and content digest match the plan; no symlink or secret-like file
  authority     an approval file names this environment, revision and artifact digest
  health        the release that is live now passes its health check (so a failure later is this deploy's)
  rollback      the live release is intact and the data can be snapshotted (G03 sqlite_recovery.py); no
                unfinished deploy is pending

`deploy`, `rollback` and `recover` take an exclusive per-target lock (flock on the target folder, released by
the kernel when the process ends, even on SIGKILL); a second caller on the same target is refused with exit 2
and nothing changed. A repeat deploy of the release that is already live changes nothing, but still needs
the approval and a healthy live release: exit 0 only then, otherwise exit 2.

`deploy` refuses (exit 2, nothing changed) unless every check passes. It then records a journal, snapshots
and verifies the data with G03, stages the release, applies the artifact's migrate.sql in one transaction,
switches the `current` link atomically and runs the health check on the new release. If that fails it rolls
back by itself (link back, data restored from the snapshot with G03 restore) and exits 1. `recover` finishes
the rollback of a deploy that was interrupted. `rollback` returns to the previous release on approval.

Local only: no cloud account, secret, network call or billable resource. Exit codes: 0 done; 1 deploy failed
its health check and was rolled back (or recover rolled one back); 2 refused or invalid, nothing changed;
75 a --fail-at drill ended the process abruptly mid-deploy.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - not POSIX
    fcntl = None

PLAN_SCHEMA = "solaris.deploy-plan/1"
ENV_SCHEMA = "solaris.local-environment/1"
APPROVAL_SCHEMA = "solaris.deploy-approval/1"
REV_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
DB_RE = re.compile(r"^[A-Za-z0-9_-]{1,60}\.(db|sqlite|sqlite3)$")
SECRET_RE = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_rsa.*|id_ed25519.*|credentials(\.json)?|.*\.p12)$", re.I)
G03 = Path(__file__).resolve().parents[2] / "infrastructure" / "database-administrator" / "sqlite_recovery.py"
FAIL_POINTS = ("staged", "migrated", "switched")
CRASH_EXIT = 75


class Refused(Exception):
    pass


@contextmanager
def target_lock(plan):
    """Exclusive, non-blocking lock on the target folder for one mutating command. Writes nothing."""
    if fcntl is None:
        raise Refused("the per-target lock needs a POSIX system (fcntl); refusing to deploy without it")
    try:
        fd = os.open(str(plan["target"]), os.O_RDONLY)
    except OSError:
        raise Refused("target %s cannot be opened" % plan["target"].name)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Refused("another deploy, rollback or recover holds the lock on target %s; nothing changed"
                          % plan["target"].name)
        yield
    finally:
        os.close(fd)  # closing the descriptor releases the lock


def g03():
    if not G03.is_file():
        raise Refused("G03 sqlite_recovery.py not found at %s" % G03)
    spec = importlib.util.spec_from_file_location("solaris_sqlite_recovery", str(G03))
    mod = importlib.util.module_from_spec(spec)
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # leave no __pycache__ in the role folder
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = keep
    return mod


def sha(b):
    return hashlib.sha256(b).hexdigest()


def tree_digest(root):
    """sha256 over sorted (relative path, file sha256); refuses symlinks and special files."""
    root, items = Path(root), []
    for dp, dns, fns in os.walk(str(root)):
        dns.sort()
        for n in dns + fns:
            p = Path(dp) / n
            if p.is_symlink() or not (p.is_dir() or p.is_file()):
                raise Refused("%s is a symlink or special file" % p.relative_to(root))
        for n in sorted(fns):
            p = Path(dp) / n
            items.append("%s\0%s" % (p.relative_to(root).as_posix(), sha(p.read_bytes())))
    return sha("\n".join(sorted(items)).encode("utf-8")), [i.split("\0")[0] for i in sorted(items)]


def read_json(p, what):
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise Refused("%s unreadable: %s" % (what, p))
    if not isinstance(d, dict):
        raise Refused("%s must be a JSON object" % what)
    return d


def inside(base, rel, what):
    if not isinstance(rel, str) or not rel or os.path.isabs(rel) or "\x00" in rel:
        raise Refused("%s must be a relative path" % what)
    p = (base / rel).resolve()
    if p != base and base not in p.parents:
        raise Refused("%s leaves the plan's folder" % what)
    return p


def load_plan(path):
    path = Path(path)
    p = read_json(path, "plan")
    if p.get("schema") != PLAN_SCHEMA:
        raise Refused("plan schema must be %s" % PLAN_SCHEMA)
    base = path.resolve().parent
    art, health = p.get("artifact"), p.get("health", {})
    if not isinstance(p.get("environment"), str) or not NAME_RE.match(p["environment"]):
        raise Refused("environment must be 1-40 lowercase letters, digits or dashes")
    if not isinstance(art, dict) or not isinstance(art.get("revision"), str) or not REV_RE.match(art["revision"]) \
            or not isinstance(art.get("sha256"), str) or not re.match(r"^[0-9a-f]{64}$", art["sha256"]):
        raise Refused("artifact needs path, revision (1-64 safe characters) and sha256 (64 lowercase hex)")
    files, dbs = health.get("required_files", []), health.get("databases", [])
    if not isinstance(health, dict) or not isinstance(files, list) or not isinstance(dbs, list) or not files \
            or not all(isinstance(f, str) and f and not os.path.isabs(f) and ".." not in f.split("/") for f in files) \
            or not all(isinstance(d, str) and DB_RE.match(d) for d in dbs):
        raise Refused("health needs required_files (relative paths, at least one) and databases (plain .db names)")
    return {"environment": p["environment"], "target": inside(base, p.get("target"), "target"),
            "artifact": inside(base, art.get("path"), "artifact.path"), "revision": art["revision"],
            "artifact_sha": art["sha256"], "files": files, "dbs": dbs}


class Env:
    def __init__(self, plan):
        self.t = plan["target"]
        self.releases, self.data, self.current = self.t / "releases", self.t / "data", self.t / "current"
        self.dd = self.t / ".deploy"
        self.journal, self.history = self.dd / "journal.json", self.dd / "history.jsonl"

    def live(self):
        if not os.path.islink(str(self.current)):
            return None
        return Path(os.readlink(str(self.current))).name

    def hist(self):
        if not self.history.exists():
            return []
        return [json.loads(x) for x in self.history.read_text(encoding="utf-8").splitlines() if x.strip()]

    def record(self, rec):
        self.dd.mkdir(exist_ok=True)
        with open(self.history, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def write_journal(self, j):
        self.dd.mkdir(exist_ok=True)
        tmp = self.dd / ".journal.tmp"
        tmp.write_text(json.dumps(j, sort_keys=True), encoding="utf-8")
        os.replace(str(tmp), str(self.journal))

    def point(self, rev):
        tmp = self.t / ".current.tmp"
        if os.path.lexists(str(tmp)):
            os.unlink(str(tmp))
        if rev is None:
            if os.path.lexists(str(self.current)):
                os.unlink(str(self.current))
            return
        os.symlink(os.path.join("releases", rev), str(tmp))
        os.replace(str(tmp), str(self.current))


def health(plan, env, rev):
    """Problems with release rev and the data; empty list means healthy."""
    probs = []
    rdir = env.releases / rev
    for f in plan["files"]:
        p = rdir / f
        if not p.is_file() or p.stat().st_size == 0:
            probs.append("release %s: %s missing or empty" % (rev, f))
    if plan["dbs"]:
        res = g03().health(str(env.data), plan["dbs"])
        if res["status"] != "ok":
            probs.extend("data: %s" % m for m in res["messages"][:3])
    hj = rdir / "health.json"
    if hj.is_file() and plan["dbs"] and not probs:
        want = read_json(hj, "health.json").get("user_version")
        con = sqlite3.connect("file:%s?mode=ro" % (env.data / plan["dbs"][0]), uri=True)
        try:
            have = con.execute("PRAGMA user_version").fetchone()[0]
        finally:
            con.close()
        if want is not None and have != want:
            probs.append("data: %s user_version %s, release %s needs %s" % (plan["dbs"][0], have, rev, want))
    return probs


def preflight(plan, approval_path, action="deploy"):
    """Read-only. Returns (checks, context); checks is a list of (name, ok, detail)."""
    checks, env, ctx = [], Env(plan), {}

    def add(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    try:
        e = read_json(plan["target"] / "ENVIRONMENT.json", "ENVIRONMENT.json")
        ok = e.get("schema") == ENV_SCHEMA and e.get("name") == plan["environment"] and e.get("kind") == "local-fixture"
        add("environment", ok, "target is %s (%s)" % (e.get("name"), e.get("kind")) if ok else
            "target is %r (%s), plan says %r; only local-fixture targets" % (e.get("name"), e.get("kind"),
                                                                              plan["environment"]))
    except Refused as x:
        add("environment", False, str(x))
    live = env.live()
    ctx["live"] = live
    if action == "deploy":
        try:
            rev_file = (plan["artifact"] / "REVISION").read_text(encoding="utf-8").strip()
            digest, files = tree_digest(plan["artifact"])
            secrets = [f for f in files if SECRET_RE.search(f)]
            ok = rev_file == plan["revision"] and digest == plan["artifact_sha"] and not secrets
            add("artifact", ok, "revision %s, sha256 matches" % rev_file if ok else
                "REVISION %r vs plan %r; digest %s; secret-like files %s" % (
                    rev_file, plan["revision"], "matches" if digest == plan["artifact_sha"] else "differs", secrets))
        except (OSError, Refused) as x:
            add("artifact", False, "artifact unreadable: %s" % x)
        want = {"action": "deploy", "environment": plan["environment"], "revision": plan["revision"],
                "artifact_sha256": plan["artifact_sha"]}
    else:
        prev = [h for h in env.hist() if h.get("event") == "deployed" and h.get("revision") == live]
        ctx["back_to"] = prev[-1].get("previous") if prev else None
        ctx["snapshot"] = prev[-1].get("snapshot") if prev else None
        want = {"action": "rollback", "environment": plan["environment"], "revision": ctx["back_to"]}
    try:
        a = read_json(approval_path, "approval") if approval_path else None
        missing = [k for k, v in want.items() if a is None or a.get(k) != v]
        ok = a is not None and a.get("schema") == APPROVAL_SCHEMA and not missing and \
            isinstance(a.get("approved_by"), str) and a["approved_by"].strip()
        add("authority", ok, "approved by %s" % a["approved_by"] if ok else
            "no approval file" if a is None else "approval does not cover %s" % (missing or ["approved_by/schema"]))
    except Refused as x:
        add("authority", False, str(x))
    if os.path.lexists(str(env.journal)):
        add("rollback", False, "an unfinished deploy is recorded in .deploy/journal.json; run recover first")
        return checks, ctx
    if live:
        probs = health(plan, env, live)
        add("health", not probs, "live release %s healthy" % live if not probs else "; ".join(probs))
    else:
        dbs_ok = all((env.data / d).is_file() for d in plan["dbs"])
        add("health", dbs_ok, "first deploy; data present" if dbs_ok else "first deploy; data missing")
    if action == "deploy":
        rec = [h for h in env.hist() if h.get("event") == "deployed" and h.get("revision") == live]
        intact = live is None or (rec and tree_digest(env.releases / live)[0] == rec[-1].get("sha256"))
        existing = env.releases / plan["revision"]
        # a release folder may be reused (redeploy after a rollback) only if it still holds this exact artifact
        fresh = not os.path.lexists(str(existing)) or (plan["revision"] != live and existing.is_dir() and
                                                       not existing.is_symlink() and
                                                       tree_digest(existing)[0] == plan["artifact_sha"])
        ctx["reuse"] = os.path.lexists(str(existing))
        snap_ok = all((env.data / d).is_file() and not (env.data / d).is_symlink() for d in plan["dbs"])
        add("rollback", intact and fresh and snap_ok,
            ("rollback to %s available" % (live or "no release (first deploy)")) if intact and fresh and snap_ok else
            "live release %s does not match its deploy record" % live if not intact else
            ("release %s is already live" if plan["revision"] == live else
             "release folder %s exists with other content") % plan["revision"] if not fresh
            else "data cannot be snapshotted")
    else:
        ok = bool(ctx["back_to"]) and (env.releases / ctx["back_to"]).is_dir() and ctx["snapshot"] and \
            g03().verify(str(env.dd / "snapshots" / ctx["snapshot"]), plan["dbs"])["status"] == "ok"
        add("rollback", ok, "rollback to %s with snapshot %s" % (ctx["back_to"], ctx["snapshot"]) if ok else
            "no previous release with a verified snapshot to return to")
    return checks, ctx


def _restore_data(plan, env, snap_dir):
    mod = g03()
    sid = json.loads((snap_dir / "manifest.json").read_text())["snapshot_id"]
    res = mod.restore(str(env.data), str(snap_dir), sid)
    if res["status"] not in ("ok", "nothing_to_do"):
        raise Refused("data restore failed: %s" % "; ".join(res["messages"][:2]))


def _undo(plan, env, j, why):
    """Roll back a recorded deploy from whatever phase it reached. Idempotent."""
    phase = j.get("phase")
    if phase in ("migrated", "switched", "checked"):
        _restore_data(plan, env, env.dd / "snapshots" / j["deploy_id"])
    env.point(j.get("previous"))
    new = env.releases / j["revision"]
    if j.get("created") and new.is_dir():
        os.replace(str(new), str(env.releases / (".failed-%s-%s" % (j["revision"], j["deploy_id"]))))
    env.record({"event": "rolled_back", "deploy_id": j["deploy_id"], "revision": j["revision"],
                "restored": j.get("previous"), "reason": why})
    os.unlink(str(env.journal))


def deploy(plan, approval, fail_at=None):
    with target_lock(plan):
        return _deploy(plan, approval, fail_at)


def _deploy(plan, approval, fail_at=None):
    env = Env(plan)
    checks, ctx = preflight(plan, approval)
    if env.live() == plan["revision"] and not os.path.lexists(str(env.journal)):
        rec = [h for h in env.hist() if h.get("event") == "deployed" and h.get("revision") == plan["revision"]]
        if rec and rec[-1].get("sha256") == plan["artifact_sha"] and \
                tree_digest(env.releases / plan["revision"])[0] == plan["artifact_sha"]:
            # a repeat changes nothing, but is only a success when it is approved and the live release is healthy
            bad = [c for c in checks if not c["ok"] and c["check"] != "rollback"]
            if bad:
                return 2, {"result": "refused: %s is already live but %s failed; nothing changed" % (
                    plan["revision"], ", ".join(c["check"] for c in bad)), "checks": checks}
            return 0, {"result": "%s is already live with this artifact, approved and healthy; nothing changed"
                       % plan["revision"], "checks": [c for c in checks if c["check"] != "rollback"]}
    bad = [c for c in checks if not c["ok"]]
    if bad:
        return 2, {"result": "refused before any change", "checks": checks}
    env, mod = Env(plan), g03()
    did = "d%s-%s" % (time.strftime("%Y%m%d%H%M%S"), os.urandom(3).hex())
    j = {"deploy_id": did, "revision": plan["revision"], "previous": ctx["live"], "phase": "started", "created": False}
    snaps = env.dd / "snapshots"
    if plan["dbs"]:
        snaps.mkdir(parents=True, exist_ok=True)
        res = mod.snapshot(str(env.data), str(snaps / did), plan["dbs"])
        if res["status"] != "ok" or mod.verify(str(snaps / did), plan["dbs"])["status"] != "ok":
            shutil.rmtree(str(snaps / did), ignore_errors=True)
            return 2, {"result": "refused: data snapshot failed; nothing deployed", "checks": checks,
                       "messages": res["messages"][:3]}
    env.write_journal(j)
    stage = env.releases / (".staging-%s" % did)
    env.releases.mkdir(exist_ok=True)
    if not ctx.get("reuse"):
        shutil.copytree(str(plan["artifact"]), str(stage), symlinks=True)
        if tree_digest(stage)[0] != plan["artifact_sha"]:
            shutil.rmtree(str(stage))
            os.unlink(str(env.journal))
            return 2, {"result": "refused: staged copy does not match the artifact digest", "checks": checks}
        os.replace(str(stage), str(env.releases / plan["revision"]))
    j.update(phase="staged", created=not ctx.get("reuse"))
    env.write_journal(j)
    if fail_at == "staged":
        os._exit(CRASH_EXIT)
    mig = env.releases / plan["revision"] / "migrate.sql"
    report = {"deploy_id": did, "revision": plan["revision"], "previous": ctx["live"], "checks": checks}
    j["phase"] = "migrated"  # recorded before the transaction: restoring an unchanged database is harmless
    env.write_journal(j)
    if mig.is_file() and plan["dbs"]:
        con = sqlite3.connect(str(env.data / plan["dbs"][0]), isolation_level=None)
        try:
            con.execute("BEGIN IMMEDIATE")
            for stmt in [s for s in mig.read_text(encoding="utf-8").split(";\n") if s.strip()]:
                con.execute(stmt)
            con.execute("COMMIT")
        except sqlite3.Error as e:
            con.execute("ROLLBACK")
            report["migration_error"] = str(e)
        finally:
            con.close()
    if fail_at == "migrated":
        os._exit(CRASH_EXIT)
    env.point(plan["revision"])
    j["phase"] = "switched"
    env.write_journal(j)
    if fail_at == "switched":
        os._exit(CRASH_EXIT)
    probs = health(plan, env, plan["revision"])
    if probs:
        _undo(plan, env, j, "post-deploy health failed: %s" % "; ".join(probs))
        report.update(result="health check failed; rolled back to %s" % (ctx["live"] or "no release"), problems=probs)
        return 1, report
    env.record({"event": "deployed", "deploy_id": did, "revision": plan["revision"], "previous": ctx["live"],
                "sha256": plan["artifact_sha"], "snapshot": did if plan["dbs"] else None})
    os.unlink(str(env.journal))
    report["result"] = "deployed %s (rollback to %s available)" % (plan["revision"], ctx["live"] or "no release")
    return 0, report


def recover(plan):
    with target_lock(plan):
        return _recover(plan)


def _recover(plan):
    env = Env(plan)
    if not os.path.lexists(str(env.journal)):
        return 0, {"result": "nothing to recover"}
    j = read_json(env.journal, "deploy journal")
    stage = [p for p in env.releases.glob(".staging-%s" % j.get("deploy_id"))] if env.releases.is_dir() else []
    for p in stage:
        shutil.rmtree(str(p))
    _undo(plan, env, j, "interrupted at phase %s; recovered" % j.get("phase"))
    return 1, {"result": "rolled back interrupted deploy %s of %s to %s" % (j["deploy_id"], j["revision"],
                                                                             j.get("previous") or "no release")}


def rollback(plan, approval):
    with target_lock(plan):
        return _rollback(plan, approval)


def _rollback(plan, approval):
    checks, ctx = preflight(plan, approval, action="rollback")
    if [c for c in checks if not c["ok"]]:
        return 2, {"result": "refused before any change", "checks": checks}
    env = Env(plan)
    _restore_data(plan, env, env.dd / "snapshots" / ctx["snapshot"])
    env.point(ctx["back_to"])
    probs = health(plan, env, ctx["back_to"])
    env.record({"event": "deployed", "deploy_id": "rollback-%s" % os.urandom(3).hex(), "revision": ctx["back_to"],
                "previous": None, "sha256": tree_digest(env.releases / ctx["back_to"])[0], "snapshot": None,
                "rollback_from": ctx["live"]})
    return (0 if not probs else 1), {"result": "rolled back %s to %s" % (ctx["live"], ctx["back_to"]),
                                     "checks": checks, "problems": probs}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Local deployment preflight and rollback drill (see module docstring).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = {n: sub.add_parser(n) for n in ("preflight", "deploy", "rollback", "recover", "status", "digest")}
    for n, p in ps.items():
        p.add_argument("plan" if n != "digest" else "artifact")
        p.add_argument("--json", action="store_true")
    for n in ("preflight", "deploy", "rollback"):
        ps[n].add_argument("--approval")
    ps["deploy"].add_argument("--fail-at", choices=FAIL_POINTS, help="crash drill")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        if a.cmd == "digest":
            code, rep = 0, {"sha256": tree_digest(Path(a.artifact))[0]}
        else:
            plan = load_plan(a.plan)
            if a.cmd == "preflight":
                checks, ctx = preflight(plan, a.approval)
                code, rep = (0 if all(c["ok"] for c in checks) else 2), {"checks": checks, "live": ctx["live"]}
            elif a.cmd == "deploy":
                code, rep = deploy(plan, a.approval, a.fail_at)
            elif a.cmd == "rollback":
                code, rep = rollback(plan, a.approval)
            elif a.cmd == "recover":
                code, rep = recover(plan)
            else:
                env = Env(plan)
                code, rep = 0, {"live": env.live(), "pending": os.path.lexists(str(env.journal)), "history": env.hist()}
    except Refused as e:
        sys.stderr.write("refused: %s\n" % e)
        return 2
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    else:
        for c in rep.get("checks", []):
            print("  %-12s %s  %s" % (c["check"], "ok  " if c["ok"] else "FAIL", c["detail"]))
        for k in ("result", "sha256", "live"):
            if k in rep:
                print("%s: %s" % (k, rep[k]))
    return code


if __name__ == "__main__":
    sys.exit(main())
