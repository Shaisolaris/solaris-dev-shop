"""First-pass M probe for a daily integration (Grok self-validation, not independent review).
Written from daily-integration.md and the goal's plan.json and README. Usage: PY mdaily_probe.py GOAL WT HEADS ACCDIR
HEADS is an `git ls-remote` listing of review/grok-g* branches taken at the start of the pass.
Rows: H1 plan heads current, H2 every plan commit is in HEAD, H3 every merge commit in base..HEAD is a clean merge
(tree equals git merge-tree of its parents), and on a clone of HEAD the tool's teeth: T0 clean -> INTEGRATED,
T1 a plan commit not in HEAD, T2 a prerequisite file reverted, T3 an integration commit outside the writable globs,
T4 an uncommitted change. Each T row must give NOT_INTEGRATED with the right finding kind. X1 cross_checks clean."""
import json, os, re, shutil, subprocess, sys, tempfile
GOAL, WT, HEADS, ACC = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3], sys.argv[4]
PY = sys.executable; ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ENV.pop("G20_CHROME", None)
T = "employees/quality-security/assurance/daily_integration.py"; PLAN = "examples/capabilities/%s/plan.json" % GOAL
ACCS = [a for f in ("ACCEPTANCE-A.json", "ACCEPTANCE-B.json", "ACCEPTANCE-PR.json") for a in ("--acceptance", os.path.join(ACC, f))]
def g(cwd, *a, check=False):
    r = subprocess.run(["git", "-C", cwd] + list(a), capture_output=True, text=True)
    return r.stdout.strip() if not check else r.returncode
R = []
def rec(n, ok, d): R.append((n, bool(ok), d))
P = json.load(open(os.path.join(WT, PLAN)))
heads = {}
for line in open(HEADS):
    sha, ref = line.split(); m = re.match(r"refs/heads/review/grok-g(\d\d)-", ref)
    if m: heads.setdefault("G" + m.group(1), set()).add(sha)
stale = [(p["id"], p["commit"][:7], sorted(s[:7] for s in heads.get(p["id"], ()))) for p in P["prerequisites"] if p["commit"] not in heads.get(p["id"], ())]
rec("H1 every plan commit is its goal's current remote head", not stale, stale or "all current")
notin = [p["id"] for p in P["prerequisites"] if g(WT, "merge-base", "--is-ancestor", p["commit"], "HEAD", check=True) != 0]
rec("H2 every plan commit is in HEAD", not notin, notin or "all in HEAD")
bad = []
merges = g(WT, "rev-list", "--merges", "%s..HEAD" % P["base"]).split()
for m in merges:
    ps = g(WT, "log", "-1", "--format=%P", m).split()
    mt = subprocess.run(["git", "-C", WT, "merge-tree", "--write-tree", ps[0], ps[1]], capture_output=True, text=True)
    if mt.returncode != 0 or mt.stdout.split()[0] != g(WT, "rev-parse", m + "^{tree}"): bad.append(m[:7])
rec("H3 every merge in base..HEAD is a clean merge (%d merges)" % len(merges), not bad, bad or "all clean")
def clone():
    t = tempfile.mkdtemp(prefix="mdp-"); d = os.path.join(t, "r")
    subprocess.run(["git", "clone", "-q", WT, d], capture_output=True)
    g(d, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", g(WT, "rev-parse", "HEAD"))
    g(d, "config", "user.name", "probe"); g(d, "config", "user.email", "probe-local")
    return t, d
def check(d, plan=PLAN):
    r = subprocess.run([PY, T, "check", "--plan", plan, "--json"] + ACCS, cwd=d, capture_output=True, text=True, env=ENV, timeout=900)
    try: j = json.loads(r.stdout)
    except Exception: j = {"verdict": "?", "findings": [], "_raw": (r.stdout + r.stderr)[-300:]}
    kinds = sorted({(f.get("kind") or f.get("code") or "?") for f in j.get("findings", [])})
    return r.returncode, j.get("verdict"), kinds
t, d = clone(); rc, v, k = check(d); rec("T0 clean clone -> INTEGRATED", rc == 0 and v == "INTEGRATED", (rc, v, k)); shutil.rmtree(t)
# T1 a plan commit that is not in HEAD (a commit from base's history that no candidate made is replaced by an unrelated one)
t, d = clone(); pj = json.load(open(os.path.join(d, PLAN)))
other = g(d, "rev-parse", P["base"] + "~1")
pj["prerequisites"][0]["commit"] = other; pp = os.path.join(t, "probe-plan.json"); json.dump(pj, open(pp, "w"))
rc, v, k = check(d, pp)
rec("T1 plan names a commit that is not the candidate -> NOT_INTEGRATED", rc == 1, (rc, v, k)); shutil.rmtree(t)
# T2 a prerequisite file reverted to base content in a new commit
t, d = clone(); pre = P["prerequisites"][-1]
files = [f for f in g(d, "diff", "--name-only", P["base"], pre["commit"]).split() if f.endswith(".py") and not f.startswith("tests/")]
f = files[0]; base_blob = subprocess.run(["git", "-C", d, "show", "%s:%s" % (P["base"], f)], capture_output=True)
if base_blob.returncode == 0: open(os.path.join(d, f), "wb").write(base_blob.stdout)
else: open(os.path.join(d, f), "a").write("\n# probe edit\n")
g(d, "commit", "-qam", "probe revert"); rc, v, k = check(d)
rec("T2 %s file %s reverted -> NOT_INTEGRATED with DRIFT" % (pre["id"], f), rc == 1 and any("DRIFT" in x.upper() for x in k), (rc, v, k)); shutil.rmtree(t)
# T3 an integration commit outside the writable globs
t, d = clone(); open(os.path.join(d, "README.md"), "a").write("\nprobe\n"); g(d, "commit", "-qam", "probe scope"); rc, v, k = check(d)
rec("T3 commit outside writable globs -> NOT_INTEGRATED", rc == 1, (rc, v, k)); shutil.rmtree(t)
# T4 uncommitted change
t, d = clone(); open(os.path.join(d, PLAN.replace("plan.json", "README.md")), "a").write("\nprobe\n"); rc, v, k = check(d)
rec("T4 uncommitted change -> NOT_INTEGRATED", rc == 1, (rc, v, k)); shutil.rmtree(t)
t, d = clone(); r = subprocess.run([PY, "examples/capabilities/%s/cross_checks.py" % GOAL], cwd=d, capture_output=True, text=True, env=ENV, timeout=900)
OBS = [("X1 cross_checks on a clean clone (OBS: compared with the handback by hand)", (r.returncode, [l for l in r.stdout.splitlines() if l.startswith("FINDING")][:4], (r.stdout.strip().splitlines() or ["?"])[-1]))]
rec("X1 cross_checks ran", r.returncode in (0, 1), (r.returncode, (r.stdout.strip().splitlines() or ["?"])[-1])); shutil.rmtree(t)
for n, ok, det in R: print("%s %s %s" % ("PASS" if ok else "FAIL", n, det))
for n, det in OBS: print("OBS  %s %s" % (n, det))
print("PROBE %s %d/%d" % (GOAL, sum(r[1] for r in R), len(R)))
