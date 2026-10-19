#!/usr/bin/env python3
"""G06 cross-goal checks for the day 1 candidates (G01, G02, G03).

All work happens in a temporary folder with synthetic data; nothing in the checkout is written and
no socket is opened.

  x1  G02 activation over owner data that G03 protects: a project whose Development/ already holds
      an owner SQLite database in WAL mode, and a G03 snapshot of it under Backups/. Activation and a
      repeated activation must leave every owner byte alone, and G03 must still verify the snapshot,
      report the database healthy against it and find no interrupted swap to recover.
  x2  G03 restore inside an activated project: restoring the snapshot into Development/ (G03 keeps the
      replaced files as pre-restore copies) must not upset G02: resume exits 0 and leaves its
      generated notes as they were.
  x3  G01's assurance engine over the integrated skills: G01 changed quality_os.py, G02 and G03
      changed skill folders; the audit must scan 61 skills with 0 gaps.

Exit 0 when every check holds, 1 when a check produced a finding (listed as FINDING lines).
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PY = sys.executable
ACT = os.path.join(ROOT, "employees/product-project/project-onboarding/activate.py")
REC = os.path.join(ROOT, "employees/infrastructure/database-administrator/sqlite_recovery.py")
QOS = os.path.join(ROOT, "employees/quality-security/assurance/quality_os.py")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(argv, cwd=None):
    r = subprocess.run([PY] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV, timeout=300, cwd=cwd)
    try:
        doc = json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        doc = None
    return r.returncode, doc, (r.stdout + r.stderr).decode("utf-8", "replace")


def digest(top, skip=()):
    out = {}
    for d, dirs, files in os.walk(top):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(d, f)
            rel = os.path.relpath(p, top)
            if rel.split(os.sep)[0] in skip:
                continue
            with open(p, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def owner_project(tmp):
    proj = os.path.join(tmp, "Acme Portal")
    dev = os.path.join(proj, "Development")
    os.makedirs(dev)
    db = sqlite3.connect(os.path.join(dev, "app.db"))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, total TEXT)")
    db.executemany("INSERT INTO orders (total) VALUES (?)", [("%d.00" % i,) for i in range(200)])
    db.commit()
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    with open(os.path.join(dev, "notes.txt"), "w") as fh:
        fh.write("owner notes, not activation's\n")
    return proj, dev


ACT_ARGS = ["--name", "Acme Portal", "--type", "web app", "--brief", "Customer portal rebuild", "--json"]


def x1(findings, lines, tmp):
    proj, dev = owner_project(tmp)
    rc, snap, out = run([REC, "snapshot", dev, "--out", os.path.join(proj, "Backups", "snap1")])
    if rc != 0:
        findings.append("x1 G03 snapshot of the owner database failed (rc=%s): %s" % (rc, out.strip()[-160:]))
        return None
    before = digest(proj)
    for i in (1, 2):
        rc, res, out = run([ACT, "activate", proj] + ACT_ARGS)
        if rc != 0:
            findings.append("x1 G02 activation %d over owner data exited %s: %s" % (i, rc, out.strip()[-160:]))
            return None
    after = digest(proj)
    changed = sorted(k for k in before if after.get(k) != before[k])
    if changed:
        findings.append("x1 G02 activation changed owner files: %s" % ", ".join(changed[:5]))
    rc_v, _, out_v = run([REC, "verify", os.path.join(proj, "Backups", "snap1"), "--expect", "app.db"])
    rc_h, _, out_h = run([REC, "health", dev, "--expect", "app.db", "--snapshot", os.path.join(proj, "Backups", "snap1")])
    rc_r, _, out_r = run([REC, "recover", dev, "--dry-run"])
    for name, rc, out in (("verify", rc_v, out_v), ("health", rc_h, out_h), ("recover --dry-run", rc_r, out_r)):
        if rc != 0:
            findings.append("x1 G03 %s after activation exited %s: %s" % (name, rc, out.strip()[-160:]))
    lines.append("x1 G02 over G03-protected data: %d owner files unchanged, G03 verify/health/recover rc %s/%s/%s"
                 % (len(before) - len(changed), rc_v, rc_h, rc_r))
    return proj, dev


def x2(findings, lines, tmp, ctx):
    if ctx is None:
        findings.append("x2 skipped: x1 did not leave an activated project")
        return
    proj, dev = ctx
    gen = {k: v for k, v in digest(proj).items() if k in ("STATUS.md", os.path.join("Scope", "ROUND-PLAN.md"), os.path.join("Delivery", "CREDENTIALS.md"))}
    db = sqlite3.connect(os.path.join(dev, "app.db"))
    db.execute("DELETE FROM orders WHERE id > 100")
    db.commit()
    db.close()
    with open(os.path.join(proj, "Backups", "snap1", "manifest.json")) as fh:
        sid = json.load(fh).get("snapshot_id")
    rc, _, out = run([REC, "restore", dev, "--snapshot", os.path.join(proj, "Backups", "snap1"), "--confirm", str(sid)])
    if rc != 0:
        findings.append("x2 G03 restore into the activated project exited %s: %s" % (rc, out.strip()[-160:]))
        return
    n = sqlite3.connect(os.path.join(dev, "app.db")).execute("SELECT count(*) FROM orders").fetchone()[0]
    rc2, res, out2 = run([ACT, "resume", proj, "--json"])
    gen2 = {k: v for k, v in digest(proj).items() if k in gen}
    if rc2 != 0:
        findings.append("x2 G02 resume after a G03 restore exited %s: %s" % (rc2, out2.strip()[-160:]))
    if gen2 != gen:
        findings.append("x2 G02 resume rewrote its notes after a G03 restore: %s" % sorted(k for k in gen if gen2.get(k) != gen[k]))
    if n != 200:
        findings.append("x2 G03 restore left %d rows, expected 200" % n)
    lines.append("x2 G03 restore inside an activated project: %d rows back, G02 resume rc %s, notes unchanged %s" % (n, rc2, gen2 == gen))


def x3(findings, lines, tmp):
    rc, doc, out = run([QOS, "audit"], cwd=ROOT)
    if doc is None:
        findings.append("x3 G01 audit output not readable (rc=%s): %s" % (rc, out.strip()[-160:]))
        return
    c = doc.get("counts", {})
    if c.get("skills_scanned") != 61 or c.get("gaps") != 0:
        findings.append("x3 G01 audit over the integrated skills: scanned %s, gaps %s (first %s)" % (
            c.get("skills_scanned"), c.get("gaps"), json.dumps(doc.get("gaps", [])[:1])[:160]))
    lines.append("x3 G01 audit over the integrated skills: scanned %s, gaps %s" % (c.get("skills_scanned"), c.get("gaps")))


def main():
    findings, lines = [], []
    tmp = tempfile.mkdtemp(prefix="g06x-")
    try:
        ctx = x1(findings, lines, tmp)
        x2(findings, lines, tmp, ctx)
        x3(findings, lines, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for l in lines:
        print(l)
    for f in findings:
        print("FINDING " + f)
    print("CROSS-CHECKS %s (%d finding%s)" % ("CLEAN" if not findings else "FINDINGS", len(findings), "" if len(findings) == 1 else "s"))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
