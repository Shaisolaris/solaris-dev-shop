"""M41 independent classification (Grok self-validation). Written from the release_candidate.py docstring and the
programme records, without reading the tool's code. Usage: PY m41_classify.py INPUTS_DIR TOOL_JSON REMOTE_HEADS"""
import json, os, sys
I, TJ, RH = sys.argv[1:4]
q = json.load(open(os.path.join(I, "WORK-QUEUE.json"))); idx = json.load(open(os.path.join(I, "candidate-index.json")))
acc = {}
for f in ("ACCEPTANCE-A.json", "ACCEPTANCE-B.json", "ACCEPTANCE-PR.json"):
    for e in json.load(open(os.path.join(I, f)))["entries"]:
        acc.setdefault(e["id"], []).append((f, e.get("commit")))
cand = {e["id"]: e.get("candidate_sha") for e in idx if e.get("candidate_sha")}
sel = [g for g in q["goals"] if g.get("selected_for_week")]
mine = {}
for g in sel:
    i = g["id"]; st = g.get("status", "")
    if st in ("excluded", "rejected"): mine[i] = "excluded"
    elif i in acc:
        cs = {c for _, c in acc[i] if c}
        mine[i] = "accepted" if (i not in cand or not cs or cand[i] in cs) else "acceptance_stale"
    elif i in cand: mine[i] = "candidate_only"
    else: mine[i] = "missing"
t = json.load(open(TJ)); theirs = {x["id"]: x["disposition"] for x in t["goals"]}
diff = sorted(i for i in set(mine) | set(theirs) if mine.get(i) != theirs.get(i))
print("selected goals %d, not selected %d" % (len(sel), len(q["goals"]) - len(sel)))
print("mine counts", {k: list(mine.values()).count(k) for k in sorted(set(mine.values()))}, "| tool counts", t["counts"])
print("classification differences:", diff, [(i, mine.get(i), theirs.get(i)) for i in diff])
qa = {g["id"] for g in sel if g.get("status") == "accepted"}
print("queue status accepted but no acceptance-file entry:", sorted(qa - set(acc)))
print("acceptance-file entry but queue status not accepted:", sorted((set(acc) & {g["id"] for g in sel}) - qa), [(g["id"], g["status"]) for g in sel if g["id"] in acc and g["id"] not in qa])
mis = []
for g in sel:
    i = g["id"]; ar = (g.get("acceptance_record") or {}).get("exact_revision"); cs = {c for _, c in acc.get(i, []) if c}
    if ar and cs and ar not in cs: mis.append((i, ar[:7], sorted(c[:7] for c in cs)))
print("queue acceptance_record.exact_revision differs from acceptance file commit:", mis)
heads = {}
for l in open(RH):
    sha, ref = l.split()
    heads[ref.replace("refs/heads/", "")] = sha
moved = []
for e in idx:
    i, c = e["id"], e.get("candidate_sha")
    if not c: continue
    br = [b for b in heads if b.startswith("review/grok-%s-" % i.lower())]
    for b in br:
        if heads[b] != c: moved.append((i, mine.get(i), c[:7], b, heads[b][:7]))
print("index candidate differs from the remote review branch head (index stale or post-acceptance commits):")
for m in moved: print("  ", m)
ex = [g["id"] for g in sel if g.get("status") in ("excluded", "rejected")]
print("queue excluded/rejected:", ex, "| statuses present:", sorted({g.get("status") for g in sel}))
print("required final goals and dispositions:", [(i, mine.get(i)) for i in q["release_gate"]["required_final_goals"]])
