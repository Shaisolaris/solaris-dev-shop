#!/usr/bin/env python3
"""M40 r6 probe (Grok self-validation, not independent review). Written for this pass from M40 r5 P4-2 (skill-copy
without --dest leaves a g40-skill-* folder in TMPDIR on every run) and the G40 r6 doc. CLI rows run skill-copy with
TMPDIR pointed at an empty folder made here; unit rows import the tool. Inputs chosen here.
Usage: PY m40r6_probe.py REPO OUT.json"""
import importlib.util, json, os, shutil, subprocess, sys, tempfile
REPO = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
REL = "employees/quality-security/qa-engineer/host_portability.py"; TOOL = os.path.join(REPO, REL); ROLE = "quality-security/qa-engineer"
ROWS = []
def row(rid, name, ok, detail, obs=False): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "obs": obs, "detail": detail})
def cli(tmpdir, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=tmpdir)
    p = subprocess.run([sys.executable, TOOL] + list(args), capture_output=True, text=True, env=env, timeout=120)
    try: j = json.loads(p.stdout)
    except Exception: j = None
    return p.returncode, j, p.stderr
def left(d): return sorted(os.listdir(d))
top = tempfile.mkdtemp(prefix="m40r6-")
try:
    t1 = os.path.join(top, "t1"); os.mkdir(t1)
    rc, j, e = cli(t1, "skill-copy", REPO, ROLE, "--json")
    row("R01", "skill-copy without --dest: rc 1, status broken, TMPDIR empty afterwards", rc == 1 and (j or {}).get("status") == "broken" and left(t1) == [],
        {"rc": rc, "status": (j or {}).get("status"), "left_in_tmpdir": left(t1)})
    row("R02", "the JSON says the copy is gone: dest is null and temp_copy names the removal and --dest", j is not None and j.get("dest") is None and "--dest" in str(j.get("temp_copy", "")),
        {"dest": (j or {}).get("dest"), "temp_copy": (j or {}).get("temp_copy")})
    t2 = os.path.join(top, "t2"); os.mkdir(t2)
    for _ in range(5): cli(t2, "skill-copy", REPO, ROLE)
    row("R03", "five back-to-back runs without --dest leave nothing in TMPDIR", left(t2) == [], {"left": left(t2)})
    t3 = os.path.join(top, "t3"); os.mkdir(t3); keep = os.path.join(top, "keep")
    rc2, j2, _ = cli(t3, "skill-copy", REPO, ROLE, "--dest", keep, "--json")
    ok = rc2 == 1 and os.path.isfile(os.path.join(keep, "qa-engineer", "capability.contract.json")) and (j2 or {}).get("dest") == os.path.join(keep, "qa-engineer") and "temp_copy" not in (j2 or {})
    row("R04", "--dest DIR still keeps the copy and reports its path; no temp_copy key", ok, {"rc": rc2, "dest": (j2 or {}).get("dest"), "keys": sorted((j2 or {}).keys())})
    same = j is not None and j2 is not None and j.get("missing") == j2.get("missing") and j.get("resolved") == j2.get("resolved") and j.get("copied_files") == j2.get("copied_files")
    row("R05", "the findings are the same with and without --dest (missing, resolved, copied_files)", same,
        {"missing_no_dest": len((j or {}).get("missing") or []), "missing_dest": len((j2 or {}).get("missing") or []), "copied": [(j or {}).get("copied_files"), (j2 or {}).get("copied_files")]})
    t4 = os.path.join(top, "t4"); os.mkdir(t4)
    rc4, _, e4 = cli(t4, "skill-copy", REPO, "no-such/role")
    row("R06", "a bad ROLE exits 2 and creates nothing in TMPDIR", rc4 == 2 and left(t4) == [], {"rc": rc4, "left": left(t4)})
    # unit: a failure during the copy still removes the temp folder
    t5 = os.path.join(top, "t5"); os.mkdir(t5)
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("hp", TOOL); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    old = tempfile.tempdir; tempfile.tempdir = t5
    real = m.shutil.copytree
    def boom(*a, **k):
        real(*a, **k); raise OSError("injected after copy")
    m.shutil.copytree = boom; raised = None
    try:
        m.skill_copy(REPO, ROLE)
    except OSError as ex:
        raised = str(ex)
    finally:
        m.shutil.copytree = real; tempfile.tempdir = old
    row("R07", "an error during the copy still removes the temp folder and the error is raised, not swallowed", raised == "injected after copy" and left(t5) == [],
        {"raised": raised, "left": left(t5)})
    doc = open(os.path.join(REPO, "employees/quality-security/qa-engineer/host-portability.md"), encoding="utf-8").read()
    row("R08", "host-portability.md states the temp copy is removed and --dest keeps it", "removed before the command returns" in doc and "--dest DIR` to keep it" in doc, None)
    row("R09", "OBS: the report command still has no --dest of its own, so its skill-copy part can only be inspected by rerunning skill-copy --dest", True, None, obs=True)
finally:
    shutil.rmtree(top, ignore_errors=True)
scored = [r for r in ROWS if not r["obs"]]; n = sum(r["pass"] for r in scored)
json.dump({"probe": "m40r6", "python": sys.version.split()[0], "rows": ROWS, "score": "%d/%d" % (n, len(scored))}, open(OUT, "w"), indent=1)
for r in ROWS: print("%s %s %s" % ("OBS " if r["obs"] else ("PASS" if r["pass"] else "FAIL"), r["row"], r["name"]))
print("SCORE %d/%d" % (n, len(scored)))
sys.exit(0 if n == len(scored) else 1)
