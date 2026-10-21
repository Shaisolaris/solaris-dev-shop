#!/usr/bin/env python3
"""M07 r2 probe (Grok self-validation, not independent review). Written for this pass from M07 P4-1 (bytecode left
in the source tree), P4-2 (case-variant machine id registers as a second machine) and P4-3 (temp file left after a
kill). Inputs chosen here, not copied from the G07 r2 tests. Real processes on temp folders only.
Usage: PY m07r2_probe.py REPO OUT.json"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
TOOL = REPO / "employees/infrastructure/fleet-provisioner/registry.py"; FIX = REPO / "examples/capabilities/G07/fixtures"
BASE_ENV = {"PATH": "/usr/bin:/bin", "HOME": tempfile.mkdtemp(prefix="m07r2-home-"), "LC_ALL": "C"}
ENV = dict(BASE_ENV, PYTHONDONTWRITEBYTECODE="1"); ROWS = []; TOP = Path(tempfile.mkdtemp(prefix="m07r2-"))
def row(rid, name, ok, detail): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "detail": detail})
def R(root, *a, env=None):
    p = subprocess.run([sys.executable, str(TOOL), a[0], "--root", str(root)] + [str(x) for x in a[1:]], env=env or ENV,
                       capture_output=True, text=True, timeout=120); return p.returncode, p.stdout, p.stderr
def world(n):
    t = TOP / n; (t / "fleet").mkdir(parents=True); return t, t / "fleet"
def ident(t, name, mid):
    p = t / ("id-%s.json" % name); p.write_text(json.dumps({"machine_id": mid})); return p
def machines(root):
    return json.loads((root / "registry.json").read_text())["machines"]
# R01 case variants of one id under new aliases are refused (4 spellings)
t, root = world("r01"); R(root, "register", "--alias", "box1", "--identity", ident(t, "a", "Box-0042-alpha"), "--owner", "ana", "--request-id", "q1")
rcs = {}
for i, v in enumerate(["BOX-0042-ALPHA", "box-0042-alpha", "bOx-0042-AlPhA", "Box-0042-Alpha"]):
    rcs[v] = R(root, "register", "--alias", "box%d" % (i + 2), "--identity", ident(t, "v%d" % i, v), "--owner", "ana", "--request-id", "q%d" % (i + 2))[0]
row("R01", "4 case variants of a registered id under new aliases are refused (exit 2); one machine stays",
    all(c == 2 for c in rcs.values()) and len(machines(root)) == 1, {"rc": rcs, "machines": len(machines(root))})
# R02 claim by a case variant works for the right alias, a different id still refused
sys.path.insert(0, str(TOOL.parent)); import registry as reg
try:
    ok1 = reg.check_claim(str(root), "box1", str(ident(t, "lo", "box-0042-alpha")), "ana", 1)["alias"] == "box1"
except reg.Refused:
    ok1 = False
try:
    reg.check_claim(str(root), "box1", str(ident(t, "x", "box-0042-alphb")), "ana", 1); ok2 = False
except reg.Refused as e:
    ok2 = "wrong machine" in str(e)
row("R02", "claim with a case variant of the id is admitted; a one-letter different id is refused as wrong machine", ok1 and ok2, [ok1, ok2])
# R03 different ids that only look alike in case-folding terms stay distinct (digits, dashes)
t, root = world("r03"); a = R(root, "register", "--alias", "m1", "--identity", ident(t, "1", "abcd-0001-x"), "--owner", "o", "--request-id", "a")[0]
b = R(root, "register", "--alias", "m2", "--identity", ident(t, "2", "abcd-00010-x"), "--owner", "o", "--request-id", "b")[0]
row("R03", "control: two different ids register as two machines", a == 0 and b == 0 and len(machines(root)) == 2, [a, b])
# R04 temp files left by killed writers are removed; unrelated files stay
t, root = world("r04"); R(root, "register", "--alias", "m1", "--identity", ident(t, "1", "abcd-0001-x"), "--owner", "o", "--request-id", "a")
for n in (".reg-aaaa.tmp", ".reg-bbbb.tmp", ".reg-.tmp"): (root / n).write_bytes(b"{")
for n in ("reg-keep.tmp", ".reg-keep.tmp.bak", "notes.tmp"): (root / n).write_text("keep")
rc, out, err = R(root, "status")
left = sorted(p.name for p in root.iterdir() if p.name not in ("registry.json", "ops.jsonl", "FLEET.md", ".registry.lock"))
row("R04", "status removes 3 .reg-*.tmp leftovers and keeps 3 unrelated files", rc == 0 and left == [".reg-keep.tmp.bak", "notes.tmp", "reg-keep.tmp"], {"rc": rc, "left": left})
# R05 leftovers removed also before a refused change, and the registry stays verified
(root / ".reg-cccc.tmp").write_bytes(b"x"); rc = R(root, "transfer", "--alias", "m1", "--from-owner", "wrong", "--expect-epoch", "1", "--to-owner", "p", "--request-id", "t1")[0]
rc2 = R(root, "status")[0]
row("R05", "a refused transfer still clears the leftover; status after is clean (exit 0)", rc == 2 and not (root / ".reg-cccc.tmp").exists() and rc2 == 0, [rc, rc2])
# R06 bytecode: fleet-bound order on a copied tree, plain env (no PYTHONDONTWRITEBYTECODE)
src = TOP / "src"
for rel in ("employees/infrastructure/fleet-provisioner", "employees/infrastructure/fleet-dispatcher", "employees/product-project/project-onboarding"):
    shutil.copytree(str(REPO / rel), str(src / rel), ignore=shutil.ignore_patterns("__pycache__"))
t, root = world("r06"); w = t / "wo"; shutil.copytree(str(REPO / "examples/capabilities/G04/fixtures"), str(w))
order = json.loads((w / "order.json").read_text()); idp = ident(t, "m", "fleet-mach-0007")
R(root, "register", "--alias", "m7", "--identity", idp, "--owner", order["owner"], "--request-id", "z")
order["fleet"] = {"machine": "m7", "owner_epoch": 1}; (w / "order.json").write_text(json.dumps(order))
penv = dict(BASE_ENV, SOLARIS_FLEET_ROOT=str(root))
p = subprocess.run([sys.executable, str(src / "employees/infrastructure/fleet-dispatcher/handoff.py"), "run", str(w / "order.json"),
                    "--worker", "w", "--identity", str(idp)], env=penv, capture_output=True, text=True, timeout=300)
pyc = sorted(str(x.relative_to(src)) for x in src.rglob("__pycache__"))
row("R06", "fleet-bound order from a copied tree with bytecode writing on: exit 0 and no __pycache__ anywhere in it (interpreter pycache_prefix set: %s)" % ("yes" if sys.pycache_prefix else "no"),
    p.returncode == 0 and pyc == [], {"rc": p.returncode, "pycache": pyc, "err": p.stderr[-200:]})
# R07 in process: the loader restores sys.dont_write_bytecode
spec_dir = src / "employees/infrastructure/fleet-dispatcher"; sys.path.insert(0, str(spec_dir))
import importlib.util
spec = importlib.util.spec_from_file_location("h_probe", str(spec_dir / "handoff.py")); h = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True; spec.loader.exec_module(h); sys.dont_write_bytecode = False
loader = getattr(h, "_load_module", None); restored = None
if loader:
    loader("solaris_activate_probe", h.ACTIVATE); restored = sys.dont_write_bytecode
row("R07", "the module loader restores sys.dont_write_bytecode (False stays False)", restored is False, {"has_loader": bool(loader), "after": restored})
for r in ROWS: print(r["row"], "PASS" if r["pass"] else "FAIL", r["name"], "|", json.dumps(r["detail"])[:300])
n = sum(r["pass"] for r in ROWS); print("M07R2 PROBE %d/%d" % (n, len(ROWS))); json.dump(ROWS, open(OUT, "w"), indent=1)
shutil.rmtree(str(TOP), True); shutil.rmtree(BASE_ENV["HOME"], True); sys.exit(0 if n == len(ROWS) else 1)
