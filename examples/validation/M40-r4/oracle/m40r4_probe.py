#!/usr/bin/env python3
"""M40 r4 probe (Grok self-validation, not independent review). Black-box checks of wheel-smoke --outside on a
private copy of the candidate checkout. Usage: PY m40r4_probe.py SRC OUT.json   (wheel rows need Python 3.10+)"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
SRC = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]; ROWS = []
TOOL = "employees/quality-security/qa-engineer/host_portability.py"
TOP = Path(tempfile.mkdtemp(prefix="m40r4-"))
REPO = TOP / "repo"
shutil.copytree(SRC, REPO, ignore=shutil.ignore_patterns(".git", "__pycache__", "build", "dist", "*.egg-info"))
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
def run(*a):
    p = subprocess.run([sys.executable, str(REPO / TOOL)] + [str(x) for x in a], capture_output=True, text=True, env=ENV, timeout=900)
    return p.returncode, p.stdout, p.stderr
def tree(p):
    p = Path(p)
    return sorted(str(x.relative_to(p)) for x in p.rglob("*")) if p.is_dir() else None
def row(rid, desc, ok, detail):
    ROWS.append({"id": rid, "desc": desc, "pass": bool(ok), "detail": detail})
    print("%s %s %s %s" % (rid, "PASS" if ok else "FAIL", desc, json.dumps(detail)[:300]))
def snap_repo():
    return tree(REPO)
R0 = snap_repo()
try:
    if sys.version_info < (3, 10):
        rc, o, e = run("wheel-smoke", REPO, "--outside", TOP / "w0")
        row("V0", "3.9: wheel-smoke refused with exit 2, nothing created", rc == 2 and not (TOP / "w0").exists(), {"rc": rc})
    else:
        # V1 existing folder with user files (M40 r3 W3/W3b)
        w = TOP / "mine"; (w / "src").mkdir(parents=True); (w / "src" / "keep.txt").write_text("user data\n")
        (w / "wheels").mkdir(); (w / "wheels" / "other-1.0-py3-none-any.whl").write_text("old"); (w / "notes.txt").write_text("n\n")
        before = tree(w); rc, o, e = run("wheel-smoke", REPO, "--outside", w, "--json")
        row("V1", "existing folder with user files: exit 2, every file kept, nothing added", rc == 2 and tree(w) == before and (w / "src/keep.txt").read_text() == "user data\n",
            {"rc": rc, "stderr": e.strip()[-160:]})
        rc, o, e = run("report", REPO, "--outside", w, "--json")
        row("V2", "report --outside on the same folder: exit 2, kept", rc == 2 and tree(w) == before, {"rc": rc})
        # V3 folder holding only a hidden file
        h = TOP / "hid"; h.mkdir(); (h / ".keep").write_text("x")
        rc, o, e = run("wheel-smoke", REPO, "--outside", h, "--json")
        row("V3", "folder holding only a hidden file counts as not empty", rc == 2 and tree(h) == [".keep"], {"rc": rc})
        # V4 a file
        f = TOP / "afile"; f.write_text("keep\n"); rc, o, e = run("wheel-smoke", REPO, "--outside", f, "--json")
        row("V4", "a file as --outside: exit 2, no traceback, file kept", rc == 2 and "Traceback" not in e and f.read_text() == "keep\n", {"rc": rc})
        # V5 dangling link
        dl = TOP / "dangling"; os.symlink(str(TOP / "nowhere"), str(dl)); rc, o, e = run("wheel-smoke", REPO, "--outside", dl, "--json")
        row("V5", "dangling symlink as --outside: exit 2, target not created", rc == 2 and not (TOP / "nowhere").exists(), {"rc": rc})
        # V6 link to a non-empty folder
        ln = TOP / "link-mine"; os.symlink(str(w), str(ln)); rc, o, e = run("wheel-smoke", REPO, "--outside", ln, "--json")
        row("V6", "symlink to a non-empty folder: exit 2, target kept", rc == 2 and tree(w) == before, {"rc": rc})
        # V7 new nested path -> pass
        n = TOP / "new" / "deep" / "work"; rc, o, e = run("wheel-smoke", REPO, "--outside", n, "--json")
        res = json.loads(o)["result"] if rc in (0, 1) and o.strip() else None
        row("V7", "new nested folder: created, exit 0, result pass", rc == 0 and res == "pass", {"rc": rc, "result": res, "stderr": e.strip()[-200:]})
        # V8 same folder again (now not empty) -> refused, kept
        b8 = tree(n); rc, o, e = run("wheel-smoke", REPO, "--outside", n, "--json")
        row("V8", "rerun into the folder the first run filled: exit 2, its files kept", rc == 2 and tree(n) == b8, {"rc": rc})
        # V9 existing empty folder -> pass
        em = TOP / "empty"; em.mkdir(); rc, o, e = run("wheel-smoke", REPO, "--outside", em, "--json")
        row("V9", "existing empty folder: exit 0 pass", rc == 0 and json.loads(o)["result"] == "pass", {"rc": rc})
        # V10 failed build: message names the folder and is true (only that folder written)
        bad = TOP / "badrepo"; shutil.copytree(REPO, bad)
        pp = bad / "pyproject.toml"; pp.write_text(pp.read_text().replace('build-backend = "setuptools.build_meta"', 'build-backend = "m40_missing_backend"'))
        wf = TOP / "wfail"; outside_before = sorted(x.name for x in TOP.iterdir())
        p = subprocess.run([sys.executable, str(bad / TOOL), "wheel-smoke", str(bad), "--outside", str(wf)], capture_output=True, text=True, env=ENV, timeout=600)
        after = sorted(x.name for x in TOP.iterdir())
        ok = p.returncode == 2 and str(wf) in p.stderr and "Nothing was written" not in p.stderr and set(after) - set(outside_before) == {"wfail"}
        row("V10", "failed build: exit 2, names the work folder, nothing else created next to it", ok, {"rc": p.returncode, "new_entries": sorted(set(after) - set(outside_before)), "stderr_tail": p.stderr.strip()[-160:]})
        # V11 inside the checkout still refused
        rc, o, e = run("wheel-smoke", REPO, "--outside", REPO / "work", "--json")
        row("V11", "--outside under REPO still refused, nothing created", rc == 2 and not (REPO / "work").exists(), {"rc": rc})
    row("V12", "checkout copy unchanged after every run", snap_repo() == R0, {})
finally:
    shutil.rmtree(TOP, ignore_errors=True)
json.dump({"python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1)
print("M40R4 PROBE %d/%d" % (sum(r["pass"] for r in ROWS), len(ROWS)))
