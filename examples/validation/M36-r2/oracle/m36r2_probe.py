#!/usr/bin/env python3
"""M36 r2 probe (Grok self-validation, not independent review). Written for this pass to check the G36 r3 refresh
from git objects alone: pins, ancestry, overlap blobs, carried files, the r2 history, and the carried tool fix.
Usage: PY m36r2_probe.py REPO OUT.json [R2_COMMIT] [--remote]"""
import json, os, re, subprocess, sys, tempfile
REPO = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
R2 = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else "92ca6c3272b9dcbfd854fc5cfdf9359ddefa1ab4"
REMOTE = "--remote" in sys.argv
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ROWS = []
def row(rid, name, ok, detail, obs=False): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "obs": obs, "detail": detail})
def g(*a):
    return subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True).stdout.strip()
def anc(a, b): return subprocess.run(["git", "-C", REPO, "merge-base", "--is-ancestor", a, b]).returncode == 0
def blob(rev, f): return g("rev-parse", "%s:%s" % (rev, f))[:7] or "-"
plan = json.load(open(os.path.join(REPO, "examples/capabilities/G36/plan.json"), encoding="utf-8"))
old = json.loads(g("show", "%s:examples/capabilities/G36/plan.json" % R2))
pre = {p["id"]: p["commit"] for p in plan["prerequisites"]}; prev = {p["id"]: p["commit"] for p in old["prerequisites"]}
base = plan["base"]
BR = {"G04": "g04-handoff", "G13": "g13-csv-reconciliation", "G14": "g14-cash-revenue", "G17": "g17-resource-decision", "G31": "g31-scope-acceptance",
      "G32": "g32-consent-followthrough", "G33": "g33-evidence-decision", "G34": "g34-content-diagnostics", "G35": "g35-campaign-accounting"}
if REMOTE:
    heads = {}
    for line in g("ls-remote", "origin", "refs/heads/review/grok-*").splitlines():
        sha, ref = line.split("\t"); heads[ref.rsplit("review/grok-", 1)[1]] = sha
    bad = {i: (pre[i][:7], heads.get(BR[i], "-")[:7]) for i in pre if heads.get(BR[i]) != pre[i]}
    row("R01", "every plan pin is the current remote head of that goal's review branch", not bad, bad or "all 9")
bad = [i for i, c in pre.items() if not anc(c, "HEAD")]
row("R02", "every pin is an ancestor of HEAD", not bad, bad or "all")
bad = {i: (prev[i][:7], pre[i][:7]) for i in pre if prev.get(i) and not anc(prev[i], pre[i])}
moved = sorted(i for i in pre if prev.get(i) != pre[i])
row("R03", "each r2 pin is an ancestor of its r3 pin (candidates moved forward, nothing rewritten)", not bad, {"bad": bad, "moved": moved})
row("R04", "the r2 head is an ancestor of HEAD (the r1 and r2 history is kept)", anc(R2, "HEAD"), R2[:7])
ro = {r["path"]: r["reason"] for r in plan["resolved_overlaps"]}
bad = {}
for path, reason in ro.items():
    named = set(re.findall(r"\b[0-9a-f]{7}\b", reason))
    known = {blob(c, path) for c in pre.values()} | {blob("HEAD", path), blob(base, path)}
    commits = {c[:7] for c in pre.values()} | {base[:7]}
    hb = blob("HEAD", path)
    blobs_named = named - commits
    # every 7-hex token in a reason must be a pin, the base, a known blob of the path, or an older G-head mentioned by name
    unknown = sorted(t for t in blobs_named if t not in known and not g("rev-parse", "--verify", "-q", t + "^{commit}"))
    head_named = hb in reason or "HEAD is the" in reason
    if unknown or not head_named: bad[path] = {"unknown": unknown, "head": hb}
row("R05", "every blob a resolved_overlaps reason names is a real blob of that path at a pin, HEAD or base, and HEAD is accounted for", not bad, bad or "8 of 8")
def changed(c): return set(g("-c", "core.quotepath=false", "diff", "--name-only", base, c).splitlines())
ch = {i: changed(c) for i, c in pre.items()}
lost = {}
for i, c in pre.items():
    for f in ch[i]:
        if f in ro: continue
        hb, cb = blob("HEAD", f), blob(c, f)
        if hb == cb: continue
        # allowed when another pin that descends from this one carries the HEAD blob
        if any(anc(c, c2) and blob(c2, f) == hb for c2 in pre.values() if c2 != c): continue
        if f.startswith(("employees/quality-security/assurance/", "employees/quality-security/qa-engineer/", "examples/capabilities/G36/", "tests/test_g36")): continue
        lost.setdefault(i, []).append(f)
row("R06", "outside the plan's writable paths and the resolved overlaps, HEAD keeps each candidate's file (or a descendant candidate's)", not lost, lost or "none lost")
missing = []
ids = list(pre)
for k, a in enumerate(ids):
    for b in ids[k + 1:]:
        if anc(pre[a], pre[b]) or anc(pre[b], pre[a]): continue
        for f in ch[a] & ch[b]:
            if blob(pre[a], f) != blob(pre[b], f) and f not in ro: missing.append((a, b, f))
row("R07", "every file two unrelated candidates change differently is listed in resolved_overlaps", not missing, missing or "none missing")
T = os.path.join(REPO, "employees/quality-security/assurance/daily_integration.py")
with tempfile.TemporaryDirectory() as d:
    bad_plan = dict(plan); bad_plan["resolved_overlaps"] = [dict(plan["resolved_overlaps"][0], reason="q" * 333)]
    p = os.path.join(d, "p.json"); json.dump(bad_plan, open(p, "w"))
    r = subprocess.run([sys.executable, T, "check", "--plan", p, "--repo", REPO], capture_output=True, text=True, env=ENV, timeout=300)
row("R08", "the carried tool fix: a 333-character reason exits 2 named as 333 characters, at most 300", r.returncode == 2 and "333 characters is too long; at most 300" in r.stderr, {"rc": r.returncode})
row("R09", "the tool blob equals G12 r3 a245f1f's", blob("HEAD", "employees/quality-security/assurance/daily_integration.py") == blob("a245f1f61739526f049bb86452d41069aa4a799a", "employees/quality-security/assurance/daily_integration.py"), None)
r = subprocess.run([sys.executable, T, "check", "--plan", os.path.join(REPO, "examples/capabilities/G36/plan.json"), "--repo", REPO], capture_output=True, text=True, env=ENV, timeout=300)
row("R10", "check --plan on the shipped plan is VERDICT INTEGRATED", r.returncode == 0 and "VERDICT INTEGRATED" in r.stdout + r.stderr, {"rc": r.returncode})
row("R11", "OBS: G34 h1 6ad99da is a post-acceptance commit that M36 has not seen; this pass only checks it is the branch head and carried", True, None, obs=True)
scored = [x for x in ROWS if not x["obs"]]; n = sum(x["pass"] for x in scored)
json.dump({"probe": "m36r2", "python": sys.version.split()[0], "rows": ROWS, "score": "%d/%d" % (n, len(scored))}, open(OUT, "w"), indent=1)
for x in ROWS: print("%s %s %s" % ("OBS " if x["obs"] else ("PASS" if x["pass"] else "FAIL"), x["row"], x["name"]))
print("SCORE %d/%d" % (n, len(scored))); sys.exit(0 if n == len(scored) else 1)
