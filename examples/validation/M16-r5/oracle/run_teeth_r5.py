"""M16 r5 teeth (Grok self-validation; M16 r4 runner on /tmp/m16r5-eval with make_mutants_r5 and shard i/n). Usage: PY run_teeth_r4.py PY OUT. Per mutant: copy /tmp/m16r4-eval (no .git) to
/tmp/m16r4-mut-<name>, apply, score with builder G16 tests, builder grounding_oracle, m16_oracle, M16 r3 and r4
adversarial sets. A kill is any deviation from the unmutated candidate on that instrument."""
import json, os, re, shutil, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import make_mutants_r5 as MM
PY, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
SRC = "/tmp/m16r5-eval"; REL = "employees/engineering/llm-agent-designer/grounded_eval.py"
env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}
def run(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=600, env=env)
def score(root):
    t = os.path.join(root, REL); r = {}
    cp = run([PY, "-m", "unittest", "tests.test_g16_capability"], cwd=root)
    r["builder_tests"] = "OK" if cp.returncode == 0 else "FAIL"
    cp = run([PY, os.path.join(root, "examples/capabilities/G16/grounding_oracle.py"), "--tool", f"{PY} {t}"], cwd=root)
    r["builder_oracle"] = (cp.stdout.strip().splitlines() or ["?"])[-1]
    cp = run([PY, os.path.join(here, "m16_oracle.py"), "--", PY, t])
    r["m16_oracle"] = "\n".join(cp.stdout.strip().splitlines()[-3:])
    for a in ("m16r3_adversarial", "m16r4_adversarial"):
        cp = run([PY, os.path.join(here, a + ".py"), PY, t])
        r[a] = sorted(m.group(1) for m in re.finditer(r"^(\w+) HOLDS", cp.stdout, re.M))
    return r
base = score(SRC); json.dump(base, open(os.path.join(OUT, "baseline.json"), "w"), indent=1)
src = open(os.path.join(SRC, REL)).read(); rows = []
LIST = MM.M
if len(sys.argv) > 3:
    i, n = map(int, sys.argv[3].split("/")); LIST = MM.M[i::n]
for name, old, new in LIST:
    root = f"/tmp/m16r5-mut-{name}"; shutil.rmtree(root, ignore_errors=True)
    shutil.copytree(SRC, root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    open(os.path.join(root, REL), "w").write(MM.apply(src, old, new))
    r = score(root)
    k = {i: (sorted(set(base[i]) ^ set(r[i])) if isinstance(base[i], list) else r[i] != base[i]) for i in base}
    rows.append({"mutant": name, "kills": k, "raw": {i: r[i] for i in ("builder_tests", "builder_oracle")}})
    print(json.dumps({"mutant": name, **{i: k[i] for i in k}}), flush=True)
    shutil.rmtree(root, ignore_errors=True)
json.dump(rows, open(os.path.join(OUT, "teeth.json"), "w"), indent=1); print("DONE")
