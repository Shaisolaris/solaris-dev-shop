#!/usr/bin/env python3
"""Build a disposable G08 world: a local-fixture environment with a SQLite dataset, artifacts, plans, approvals.

usage: make_world.py DEST   (DEST must not exist). Digests are computed with local_deploy.py's own `digest`
rule (sha256 over sorted relative path and file sha256), which the oracle re-derives independently.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(root):
    items = []
    for dp, _, fns in os.walk(str(root)):
        for n in fns:
            p = Path(dp) / n
            items.append("%s\0%s" % (p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest()))
    return hashlib.sha256("\n".join(sorted(items)).encode("utf-8")).hexdigest()


def build(dest):
    dest = Path(dest)
    shutil.copytree(str(HERE / "fixtures"), str(dest))
    (dest / "env" / "data").mkdir()
    con = sqlite3.connect(str(dest / "env" / "data" / "app.db"))
    con.executescript((dest / "seed.sql").read_text())
    con.close()
    for d in sorted(dest.glob("artifact-*")):
        name, rev = d.name[len("artifact-"):], (d / "REVISION").read_text().strip()
        sha = digest(d)
        plan = {"schema": "solaris.deploy-plan/1", "environment": "staging-local", "target": "env",
                "artifact": {"path": d.name, "revision": rev, "sha256": sha},
                "health": {"required_files": ["index.html"], "databases": ["app.db"]}}
        (dest / ("plan-%s.json" % name)).write_text(json.dumps(plan, indent=2) + "\n")
        appr = {"schema": "solaris.deploy-approval/1", "action": "deploy", "environment": "staging-local",
                "revision": rev, "artifact_sha256": sha, "approved_by": "release-manager: A. Example"}
        (dest / ("approval-%s.json" % name)).write_text(json.dumps(appr, indent=2) + "\n")
    for rev in ("r1", "r2"):
        appr = {"schema": "solaris.deploy-approval/1", "action": "rollback", "environment": "staging-local",
                "revision": rev, "approved_by": "release-manager: A. Example"}
        (dest / ("approval-rollback-to-%s.json" % rev)).write_text(json.dumps(appr, indent=2) + "\n")
    return dest


if __name__ == "__main__":
    if len(sys.argv) != 2 or os.path.lexists(sys.argv[1]):
        sys.exit("usage: make_world.py DEST (must not exist)")
    print(build(sys.argv[1]))
