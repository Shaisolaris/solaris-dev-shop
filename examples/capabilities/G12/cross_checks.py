#!/usr/bin/env python3
"""G12 cross-goal checks for the day 2 candidates (G04 r2, G05 r2, G07, G08 r2, G09).

Nothing in the checkout is written; every run uses copies of the candidates' own fixtures in a temporary
folder. No network, no cluster, no browser.

  x1  G04 r2 x G07: G07 hands a fleet machine from one owner to another (owner_epoch 1 -> 2). The same
      order revision, updated to the new owner and epoch, must run on that machine, and G04 r2 must
      render a new brief naming the new owner (owner is a receipt input). The old owner's order must be
      refused by the G07 claim check.
  x2  G05 r2 x G04 r2: a G05 gate receipt bound to the digest of the G04 brief must turn stale after the
      owner change re-renders it, and stay current when the order is simply re-run.
  x3  G05 r2 x G08 r2: a G05 receipt bound to the reviewed artifact (revision = the G08 plan's artifact
      sha256) must be current for the release G08 makes live, and stale after a G08 rollback to r1.

Exit 0 when every check holds, 1 when a check produced a finding (listed as FINDING lines).
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PY = sys.executable
HANDOFF = os.path.join(ROOT, "employees/infrastructure/fleet-dispatcher/handoff.py")
REGISTRY = os.path.join(ROOT, "employees/infrastructure/fleet-provisioner/registry.py")
QOS = os.path.join(ROOT, "employees/quality-security/assurance/quality_os.py")
DEPLOY = os.path.join(ROOT, "employees/engineering/devops-engineer/local_deploy.py")
FX04 = os.path.join(ROOT, "examples/capabilities/G04/fixtures")
FX07 = os.path.join(ROOT, "examples/capabilities/G07/fixtures")
WORLD08 = os.path.join(ROOT, "examples/capabilities/G08/make_world.py")
RELEASE_FILES = ["REVISION", "health.json", "index.html", "migrate.sql"]


def run(argv, cwd=None, env=None):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for k in ("SOLARIS_MACHINE_IDENTITY", "SOLARIS_FLEET_ROOT"):  # the checks pass both explicitly
        e.pop(k, None)
    e.update(env or {})
    r = subprocess.run([PY] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=e, timeout=300)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def qos():
    spec = importlib.util.spec_from_file_location("g12_quality_os", QOS)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def fleet_world(tmp):
    """A G04 order folder bound to G07 machine mini1, first owned by ana (epoch 1), then ben (epoch 2)."""
    w = os.path.join(tmp, "w")
    shutil.copytree(FX04, w)
    shutil.copytree(FX07, os.path.join(w, "id"))
    os.mkdir(os.path.join(w, "fleet"))
    steps = [["register", "--root", "fleet", "--alias", "mini1", "--identity", "id/identity-mini1.json",
              "--owner", "ana", "--request-id", "reg-1"]]
    for s in steps:
        rc, out = run([REGISTRY] + s, cwd=w)
        if rc != 0:
            raise RuntimeError("G07 setup %s rc %d: %s" % (s[0], rc, out[-300:]))
    return w


def write_order(w, owner, epoch):
    with open(os.path.join(w, "order.json")) as fh:
        o = json.load(fh)
    o["owner"] = owner
    o["fleet"] = {"machine": "mini1", "owner_epoch": epoch, "registry": "fleet"}
    with open(os.path.join(w, "order.json"), "w") as fh:
        json.dump(o, fh, indent=1)


def handoff(w, worker):
    return run([HANDOFF, "run", "order.json", "--worker", worker, "--identity", "id/identity-mini1.json"], cwd=w)


def brief_path(w):
    for d, _, fs in os.walk(w):
        if "HANDOFF-BRIEF.md" in fs:
            return os.path.join(d, "HANDOFF-BRIEF.md")
    return None


def brief_digest(q, w, revision):
    p = brief_path(w)
    root, name = os.path.dirname(p), os.path.basename(p)
    from pathlib import Path
    return {"digests": q.artifact_digests(Path(root), [name]), "revision": revision}


def x1(findings, lines):
    tmp = tempfile.mkdtemp(prefix="g12x1-")
    try:
        w = fleet_world(tmp)
        write_order(w, "ana", 1)
        rc1, out1 = handoff(w, "ana")
        rc, out = run([REGISTRY, "transfer", "--root", "fleet", "--alias", "mini1", "--from-owner", "ana",
                       "--expect-epoch", "1", "--to-owner", "ben", "--request-id", "t-1"], cwd=w)
        if rc != 0:
            raise RuntimeError("G07 transfer rc %d: %s" % (rc, out[-300:]))
        rc_old, out_old = handoff(w, "ana")
        write_order(w, "ben", 2)
        rc2, out2 = handoff(w, "ben")
        p = brief_path(w)
        text = ""
        if p:
            with open(p) as fh:
                text = fh.read()
        if rc1 != 0:
            findings.append("x1 first fleet-bound run as ana exit %d: %s" % (rc1, out1[-200:]))
        elif rc_old != 2 or "fleet claim refused" not in out_old:
            findings.append("x1 G07 stale owner ana (epoch 1) after transfer: G04 exit %d, not refused: %s" % (rc_old, out_old[-200:]))
        elif rc2 != 0:
            findings.append("x1 new owner ben (epoch 2), same revision: G04 exit %d: %s" % (rc2, out2[-200:]))
        elif "- Owner: ben" not in text or "- Owner: ana" in text:
            findings.append("x1 brief after the owner change does not name ben only (G04 r2 owner receipt input)")
        else:
            lines.append("x1 G07 transfer ana->ben: stale ana order refused (exit 2), ben epoch 2 runs (exit 0), brief names ben")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def x2(findings, lines):
    q = qos()
    tmp = tempfile.mkdtemp(prefix="g12x2-")
    try:
        w = fleet_world(tmp)
        write_order(w, "ana", 1)
        rc, out = handoff(w, "ana")
        if rc != 0:
            raise RuntimeError("x2 first run rc %d: %s" % (rc, out[-300:]))
        rev = "sha256:" + "a" * 64
        reviewed = brief_digest(q, w, rev)
        rc, out = handoff(w, "ana")
        again = q.binding_state(reviewed, brief_digest(q, w, rev))[0]
        run([REGISTRY, "transfer", "--root", "fleet", "--alias", "mini1", "--from-owner", "ana",
             "--expect-epoch", "1", "--to-owner", "ben", "--request-id", "t-1"], cwd=w)
        write_order(w, "ben", 2)
        rc2, out2 = handoff(w, "ben")
        after = q.binding_state(reviewed, brief_digest(q, w, "sha256:" + "b" * 64))[0]
        if again != "current":
            findings.append("x2 a plain re-run changed the reviewed brief: G05 says %s, want current" % again)
        elif rc2 != 0 or after != "stale":
            findings.append("x2 brief re-rendered for ben (G04 exit %d) but G05 receipt is %s, want stale" % (rc2, after))
        else:
            lines.append("x2 G05 receipt on the G04 brief: re-run current, owner change stale")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def x3(findings, lines):
    q = qos()
    from pathlib import Path
    tmp = tempfile.mkdtemp(prefix="g12x3-")
    try:
        w = os.path.join(tmp, "w")
        rc, out = run([WORLD08, w])
        if rc != 0:
            raise RuntimeError("G08 make_world rc %d" % rc)
        with open(os.path.join(w, "plan-r2.json")) as fh:
            sha = json.load(fh)["artifact"]["sha256"]
        reviewed = {"digests": q.artifact_digests(Path(w, "artifact-r2"), RELEASE_FILES), "revision": "sha256:" + sha}
        steps = [("deploy", "plan-r1.json", "approval-r1.json"), ("deploy", "plan-r2.json", "approval-r2.json")]
        for verb, plan, appr in steps:
            rc, out = run([DEPLOY, verb, plan, "--approval", appr], cwd=w)
            if rc != 0:
                raise RuntimeError("G08 %s %s rc %d: %s" % (verb, plan, rc, out[-300:]))

        def live():
            rel = os.path.realpath(os.path.join(w, "env", "current"))
            with open(os.path.join(w, "env", ".deploy", "history.jsonl")) as fh:
                hist = [json.loads(l) for l in fh if l.strip()]
            last = [h for h in hist if h.get("sha256")][-1]
            return os.path.basename(rel), {"digests": q.artifact_digests(Path(rel), RELEASE_FILES),
                                           "revision": "sha256:" + last["sha256"]}
        name2, subj2 = live()
        st2 = q.binding_state(reviewed, subj2)[0]
        rc, out = run([DEPLOY, "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json"], cwd=w)
        name1, subj1 = live()
        st1 = q.binding_state(reviewed, subj1)[0]
        if name2 != "r2" or st2 != "current":
            findings.append("x3 live release %s after G08 deploy of r2: G05 receipt %s, want current" % (name2, st2))
        elif rc != 0 or name1 != "r1" or st1 != "stale":
            findings.append("x3 after G08 rollback (exit %d, live %s) G05 receipt is %s, want stale" % (rc, name1, st1))
        else:
            lines.append("x3 G05 receipt on artifact r2: current for G08 live r2, stale after rollback to r1")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    findings, lines = [], []
    for fn in (x1, x2, x3):
        fn(findings, lines)
    for l in lines:
        print(l)
    for f in findings:
        print("FINDING " + f)
    print("CROSS-CHECKS %s (%d finding%s)" % ("CLEAN" if not findings else "FINDINGS", len(findings), "" if len(findings) == 1 else "s"))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
