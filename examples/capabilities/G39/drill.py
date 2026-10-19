#!/usr/bin/env python3
"""G39 drill: one synthetic customer delivery composed from existing specialist tools, with a forced
interruption, another worker resuming, and a review invalidated by a changed output.

    python3 examples/capabilities/G39/drill.py [--keep DIR]

Every step runs a real tool from this repository in a fresh temporary folder (or DIR):
  G04 handoff.py (work order, crash drill, resume), G02 activation (inside G04), G13 csv_reconcile.py,
  G19 ledger_api.py probed by boundary_probe.py, G03 sqlite_recovery.py, G05 digests (inside
  delivery_evidence.py). Nothing leaves the folder; the API listens on 127.0.0.1 only.
Exit 0 when every step gave the outcome printed next to it, 1 otherwise.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PY = sys.executable
T = {
    "evidence": REPO / "employees/product-project/delivery-lead/delivery_evidence.py",
    "handoff": REPO / "employees/infrastructure/fleet-dispatcher/handoff.py",
    "csv": REPO / "employees/data/data-engineer/csv_reconcile.py",
    "api": REPO / "employees/engineering/backend-developer/ledger_api.py",
    "probe": REPO / "employees/quality-security/security-auditor/boundary_probe.py",
    "sqlite": REPO / "employees/infrastructure/database-administrator/sqlite_recovery.py",
}
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def sh(root, *args):
    p = subprocess.run([PY] + [str(a) for a in args], cwd=str(root), capture_output=True, text=True, env=ENV,
                       timeout=600)
    return p.returncode, p.stdout + p.stderr


def record(root, role, worker, outputs, *cmd, ok_exit="0"):
    return sh(root, T["evidence"], "record", ".", "--role", role, "--worker", worker, "--ok-exit", ok_exit,
              "--outputs", *outputs, "--", PY, *cmd)


def setup(root):
    fx = Path(__file__).resolve().parent / "fixtures"
    for f in ("intake.json", "order.json", "claims.json"):
        shutil.copy2(fx / f, root / f)
    shutil.copytree(REPO / "examples/capabilities/G13/fixtures/clean", root / "data")
    (root / "api").mkdir()
    shutil.copy2(REPO / "examples/capabilities/G19/fixtures/principals.json", root / "api/principals.json")
    (root / "reports").mkdir()


def api_probe(root, worker):
    ready = root / "api" / "ready.json"
    srv = subprocess.Popen([PY, str(T["api"]), "serve", "--db", "api/ledger.db", "--principals", "api/principals.json",
                            "--port", "0", "--ready-file", "api/ready.json"], cwd=str(root), env=ENV,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(200):
            if ready.exists():
                break
            time.sleep(0.05)
        port = json.loads(ready.read_text())["port"]
        return record(root, "quality-security/security-auditor", worker, ["reports/api-boundary.json"], T["probe"],
                      "--base-url", "http://127.0.0.1:%d" % port, "--principals", "api/principals.json",
                      "--out", "reports/api-boundary.json")
    finally:
        srv.terminate()
        srv.wait(timeout=30)
        ready.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep")
    ap.add_argument("--tool", help="delivery-evidence tool to drive (default: the delivery-lead tool)")
    ns = ap.parse_args()
    if ns.tool:
        T["evidence"] = Path(ns.tool).resolve()
    root = Path(ns.keep) if ns.keep else Path(tempfile.mkdtemp(prefix="g39-drill-"))
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        print("--keep folder must be empty"); return 2
    try:
        return drill(root, ns)
    finally:
        if not ns.keep:
            shutil.rmtree(root, ignore_errors=True)


def drill(root, ns):
    setup(root)
    bad = 0

    def step(label, want, got):
        nonlocal bad
        rc, out = got
        ok = rc == want
        bad += not ok
        print("%-4s %-70s exit %s (want %s)" % ("ok" if ok else "FAIL", label, rc, want))
        if not ok:
            print("     " + out.strip().replace("\n", "\n     ")[-800:])
        return out

    step("ana: G04 work order, crash after delivery before receipt", 75,
         sh(root, T["handoff"], "run", "order.json", "--worker", "ana", "--fail-at", "deliver"))
    step("ana: G13 reconcile the month (data-engineer)", 0,
         record(root, "data/data-engineer", "ana", ["reports/metrics.json"], T["csv"], "reconcile",
                "data/contract.json", "--out", "reports/metrics.json"))
    step("verify while interrupted: NO_GO (API, snapshot, handoff pending)", 1,
         sh(root, T["evidence"], "verify", ".", "--claims", "claims.json"))
    step("ben: G19 API probed for duplicates and tenant leaks (security-auditor)", 0, api_probe(root, "ben"))
    step("ben: G03 snapshot of the API database (database-administrator)", 0,
         record(root, "infrastructure/database-administrator", "ben", ["snapshots/s1"], T["sqlite"], "snapshot",
                "api", "--out", "snapshots/s1"))
    step("ben: resume the work order (duplicate delivery suppressed)", 0,
         sh(root, T["handoff"], "run", "order.json", "--worker", "ben"))
    step("ben: verify: GO", 0, sh(root, T["evidence"], "verify", ".", "--claims", "claims.json", "--out",
                                   "reports/verdict-1.json"))
    with open(root / "reports/metrics.json", "a") as f:
        f.write(" ")
    out = step("metrics edited after review: NO_GO, data-engineer stale", 1,
               sh(root, T["evidence"], "verify", ".", "--claims", "claims.json"))
    if "stale" not in out:
        bad += 1; print("FAIL stale not reported")
    step("cy: re-run the stale reconciliation", 0,
         record(root, "data/data-engineer", "cy", ["reports/metrics.json"], T["csv"], "reconcile",
                "data/contract.json", "--out", "reports/metrics.json"))
    step("cy: verify: GO again", 0, sh(root, T["evidence"], "verify", ".", "--claims", "claims.json", "--json",
                                       "--out", "reports/verdict-2.json"))
    v = json.loads((root / "reports/verdict-2.json").read_text())
    led = (root / "outbox/ledger.jsonl").read_text().splitlines()
    print("deliveries in outbox: %d; handoff workers %s" % (len(led), v["handoff"]["workers"]))
    print("contributions: %s" % ", ".join("%s by %s" % (c["role"], c["worker"]) for c in v["contributions"]))
    if len(led) != 1:
        bad += 1; print("FAIL expected exactly one delivery")
    print("drill folder: %s" % (root if ns.keep else "(temporary, removed)"))
    print("DRILL %s" % ("PASSED" if not bad else "FAILED (%d)" % bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
