"""M16 r6 teeth (Grok self-validation). Usage: PY run_teeth_r6.py PY SRC OUT [i/n]. Per mutant: rsync SRC (no .git) to
/tmp/m16r6-mut-<name>, apply, score with builder G16 tests, the M16 r6 wide table, M16 r6 probes, M16 r4 adversarial and
M16 r5 probes. A kill is any deviation from the unmutated candidate on that instrument."""
import json, os, re, shutil, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import make_mutants_r6 as MM
PY, SRC, OUT = sys.argv[1:4]; os.makedirs(OUT, exist_ok=True)
REL = "employees/engineering/llm-agent-designer/grounded_eval.py"
env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}
run = lambda a, cwd=None: subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=600, env=env)
def score(root, tag):
    t = os.path.join(root, REL); r = {}
    r["builder_tests"] = "OK" if run([PY, "-m", "unittest", "tests.test_g16_capability"], cwd=root).returncode == 0 else "FAIL"
    j = os.path.join(OUT, f"table-{tag}.json"); run([PY, os.path.join(here, "m16r6_table.py"), os.path.dirname(t), j])
    try:
        d = json.load(open(j)); r["table"] = sorted(json.dumps(x, sort_keys=True) for x in (d["rows"] if isinstance(d, dict) and "rows" in d else d))
    except Exception as e:
        r["table"] = ["ERR " + repr(e)[:80]]
    for a in ("m16r6_probes", "m16r4_adversarial", "m16r5_probes"):
        cp = run([PY, os.path.join(here, a + ".py"), PY, t])
        r[a] = sorted(m.group(1) + ":" + m.group(2) for m in re.finditer(r"^(\w+) (HOLDS|GAP)", cp.stdout, re.M)) or ["NOOUT rc%d" % cp.returncode]
    return r
base = score(SRC, "base"); json.dump(base, open(os.path.join(OUT, "baseline.json"), "w"), indent=1)
src = open(os.path.join(SRC, REL)).read(); rows = []
LIST = MM.M
if len(sys.argv) > 4:
    i, n = map(int, sys.argv[4].split("/")); LIST = MM.M[i::n]
for name, old, new in LIST:
    assert src.count(old) == 1, name
    root = f"/tmp/m16r6-mut-{name}"; shutil.rmtree(root, ignore_errors=True)
    subprocess.run(["rsync", "-a", "--exclude", ".git", SRC + "/", root + "/"], check=True)
    open(os.path.join(root, REL), "w").write(src.replace(old, new))
    s = score(root, name); k = {key: (s[key] != base[key]) for key in base}
    diff = {key: sorted(set(s[key]) ^ set(base[key]))[:12] for key in base if isinstance(base[key], list) and s[key] != base[key]}
    rows.append({"mutant": name, "kills": k, "diff": diff}); print(json.dumps(rows[-1])[:400], flush=True)
    shutil.rmtree(root, ignore_errors=True)
json.dump(rows, open(os.path.join(OUT, "teeth.json"), "w"), indent=1); print("DONE")
