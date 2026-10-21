"""M42 r5 overlap audit (Grok self-validation, not independent review). For every resolved_overlaps entry in the plan at
HEAD: recompute, from git alone, which prerequisites changed the path from base, the blob each carries, and the HEAD
blob; check every abbreviated blob the reason names exists at the commit it is attributed to, that HEAD's blob is one
of the prerequisite blobs (or a line superset of all of them), and that no line any prerequisite added is lost in HEAD
unless the losing blob is an older revision in the winner's own history of that path (newer revision of the
same file). Entries r5 changed or added are marked R5. Usage: python3 m42r5_overlaps.py REPO"""
import json, re, subprocess, sys
R = sys.argv[1]
def g(*a, ok=False):
    p = subprocess.run(["git", "-C", R] + list(a), capture_output=True, text=True)
    return p.stdout.strip() if (p.returncode == 0 or ok) else None
plan = json.loads(g("show", "HEAD:examples/capabilities/G42/plan.json")); base = plan["base"]
pre = {p["id"]: p["commit"] for p in plan["prerequisites"]}
def blob(c, f): return g("rev-parse", "%s:%s" % (c, f))
def anc(a, b): return subprocess.run(["git", "-C", R, "merge-base", "--is-ancestor", a, b]).returncode == 0
def hist(c, f):
    return set(filter(None, (blob(h, f) for h in (g("log", "--format=%H", c, "--", f) or "").split())))
r4 = {o["path"]: o["reason"] for o in json.loads(g("show", "1611581:examples/capabilities/G42/plan.json"))["resolved_overlaps"]}
def lines(b): return set(l.rstrip() for l in (g("cat-file", "-p", b) or "").splitlines() if l.strip()) if b else set()
bad = 0
for o in plan["resolved_overlaps"]:
    f = o["path"]; hb = blob("HEAD", f); bb = blob(base, f)
    touch = {i: blob(c, f) for i, c in pre.items() if blob(c, f) != bb}
    winners = [i for i, b in touch.items() if b == hb]
    named = re.findall(r"\b[0-9a-f]{7}\b", o["reason"])
    allblobs = set(touch.values()) | {hb}
    unknown = [n for n in named if not any(b and b.startswith(n) for b in allblobs) and not g("cat-file", "-t", n, ok=True)]
    # lost lines: every line a losing prerequisite added (vs base) must be in HEAD, unless the winner descends from the loser
    lost = {}
    for i, b in touch.items():
        if b == hb: continue
        if any(b in hist(pre[w], f) for w in winners): continue
        add = lines(b) - lines(bb); miss = add - lines(hb)
        if miss: lost[i] = len(miss)
    ok = len(touch) >= 2 and (winners or not lost) and not lost and not unknown
    if not ok: bad += 1
    tag = "R5 " if r4.get(f) != o["reason"] else "   "
    print("%s%s %s: %d prereqs touch it; HEAD %s = %s; losers older revisions of the winner: %s%s%s" % (
        tag, "OK  " if ok else "FAIL", f, len(touch), (hb or "-")[:7], winners or "union/other",
        all(any(touch[l] in hist(pre[w], f) for w in winners) for l in touch if touch[l] != hb) if winners else "n/a",
        "; lost lines %s" % lost if lost else "", "; reason names unknown blob(s) %s" % unknown if unknown else ""))
print("OVERLAPS %d entries, %d failing" % (len(plan["resolved_overlaps"]), bad))
