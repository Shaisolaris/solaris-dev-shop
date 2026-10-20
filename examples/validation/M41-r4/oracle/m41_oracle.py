#!/usr/bin/env python3
"""M41 oracle (Grok self-validation, not independent review). Written from M41.md, G41.md and the release_candidate.py
docstring before reading the builder's inventory_oracle.py. Synthetic programme records on a private copy of the
candidate. R rows are scored; O rows are observations. Usage: PY m41_oracle.py SRC OUT.json [--tool PATH]"""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; PY = sys.executable; ROWS = []
TOOL = os.path.join(SRC, "employees/quality-security/assurance/release_candidate.py")
if "--tool" in sys.argv: TOOL = os.path.abspath(sys.argv[sys.argv.index("--tool") + 1])
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
def row(name, ok, det, scored=True):
    sub = {k: bool(v[0]) for k, v in det.items() if isinstance(v, (tuple, list)) and len(v) == 2 and isinstance(v[0], bool)}
    ROWS.append({"row": name, "pass": bool(ok), "sub": sub, "detail": det, "scored": scored})
    print(("PASS " if ok else "FAIL ") + name[:100] + " " + json.dumps(det, default=str)[:520], flush=True)
def safe(fn):
    def g():
        try: fn()
        except Exception as e: row(fn.__name__ + " crash", False, {"crash": repr(e)[:300]})
    return g
S = lambda n: hashlib.sha1(("c%d" % n).encode()).hexdigest()
REQ = ["G39", "M39", "G40", "M40"]
class W:
    def __init__(s):
        s.top = tempfile.mkdtemp(prefix="m41o-"); s.repo = os.path.join(s.top, "repo")
        shutil.copytree(SRC, s.repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        s.goals = {i: {"id": i, "status": "accepted", "selected_for_week": True} for i in ["G01", "G02", "M01", "M02", "P01"] + REQ}
        s.acc = {"A": [{"id": i, "commit": S(k), "manifest_sha256": "a" * 64} for k, i in enumerate(["G01", "G02", "M01", "M02"] + REQ)], "PR": [{"id": "P01", "source_commit": S(99), "reply": "https://example.invalid/r"}]}
        s.idx = [{"id": i, "candidate_sha": S(k)} for k, i in enumerate(["G01", "G02", "M01", "M02"] + REQ)]
        s.gate = {"state": "NOT_READY", "required_final_goals": list(REQ), "candidate_commit": S(50), "checks_revision": S(50), "reviewed_revision": S(50)}
    def write(s):
        q = {"goals": list(s.goals.values()), "release_gate": s.gate}; p = {}
        for n, o in (("queue", q), ("idx", s.idx)): p[n] = os.path.join(s.top, n + ".json"); json.dump(o, open(p[n], "w"))
        p["acc"] = []
        for k, v in s.acc.items():
            f = os.path.join(s.top, "ACCEPTANCE-%s.json" % k); json.dump({"entries": v}, open(f, "w")); p["acc"].append(f)
        return p
    def run(s, *extra, out=None):
        p = s.write(); a = [PY, TOOL, "inventory", s.repo, "--queue", p["queue"], "--acceptance"] + p["acc"] + ["--candidates", p["idx"], "--json"] + list(extra)
        r = subprocess.run(a, capture_output=True, text=True, env=ENV, timeout=120, cwd=s.top)
        try: j = json.loads(r.stdout)
        except ValueError: j = {}
        return r.returncode, j, r.stderr
    def close(s): shutil.rmtree(s.top, ignore_errors=True)
def disp(j): return {x["id"]: x["disposition"] for x in j.get("goals", [])}
def gate(j): return (j.get("release_gate") or {}).get("state")
def tree(p):
    h = hashlib.sha256()
    for d, ds, fs in sorted(os.walk(p)):
        ds.sort()
        for f in sorted(fs): h.update(os.path.relpath(os.path.join(d, f), p).encode()); h.update(open(os.path.join(d, f), "rb").read())
    return h.hexdigest()

@safe
def r01():
    w = W(); before = tree(w.repo); rc, j, e = w.run(); res = {}
    res["clean_ready_exit_0"] = (rc == 0 and gate(j) == "READY", (rc, gate(j), (j.get("release_gate") or {}).get("reasons")))
    res["all_accepted"] = (set(disp(j).values()) == {"accepted"}, disp(j))
    res["pr_followup_accepted_without_commit"] = (disp(j).get("P01") == "accepted", disp(j).get("P01"))
    pv = j.get("proposed_version") or {}
    res["proposes_0_62_not_applied"] = (pv.get("version") == "0.62" and pv.get("applied") is False and pv.get("from") == "0.61", pv)
    res["repo_untouched"] = (tree(w.repo) == before, 0)
    w.close()
    row("R01 clean control: every selected goal accepted at its candidate, metadata agrees and root named the revisions: READY, exit 0, proposal 0.62 not applied, REPO untouched", all(v[0] for v in res.values()), res)

@safe
def r02():
    res = {}
    def case(name, mut, want_disp=None, want_reason=None):
        w = W(); mut(w); rc, j, e = w.run(); d = disp(j); rs = " ".join((j.get("release_gate") or {}).get("reasons") or [])
        ok = rc == 1 and gate(j) == "NOT_READY" and (want_disp is None or all(d.get(k) == v for k, v in want_disp.items())) and (want_reason is None or re.search(want_reason, rs))
        res[name] = (bool(ok), (rc, gate(j), {k: d.get(k) for k in (want_disp or {})}, rs[:160])); w.close()
    case("candidate_moved_after_acceptance_stale", lambda w: w.idx[0].update(candidate_sha=S(77)), {"G01": "acceptance_stale"}, "G01")
    case("candidate_without_acceptance", lambda w: w.acc["A"].pop(1), {"G02": "candidate_only"}, "G02")
    case("no_candidate_no_acceptance_missing", lambda w: (w.acc["A"].pop(1), w.idx.pop(1)), {"G02": "missing"}, "G02")
    case("required_final_goal_not_accepted", lambda w: w.acc["A"].pop(4), {"G39": "candidate_only"}, "G39")
    case("required_final_goal_excluded_blocks", lambda w: w.goals["G39"].update(status="excluded"), {"G39": "excluded"}, "G39")
    case("conflicting_acceptance_commits", lambda w: w.acc.setdefault("B", []).append({"id": "G01", "commit": S(88), "manifest_sha256": "b" * 64}), None, "G01|conflict")
    for f in ("candidate_commit", "checks_revision", "reviewed_revision"):
        case("root_%s_unset" % f, lambda w, f=f: w.gate.update({f: None}), None, f)
    row("R02 honest NOT_READY: a moved candidate, a missing acceptance, a missing goal, a required final goal not accepted or excluded, conflicting acceptances and unset root revisions each give NOT_READY, exit 1, with the reason named", all(v[0] for v in res.values()), res)

@safe
def r03():
    res = {}
    w = W(); w.goals["G09"] = {"id": "G09", "status": "rejected", "selected_for_week": True}; rc, j, e = w.run(); d = disp(j)
    res["rejected_goal_excluded_and_not_included"] = (d.get("G09") == "excluded" and rc == 0 and "G09" not in json.dumps(j.get("included_if_released", [])), (rc, d.get("G09"), gate(j)))
    w.close()
    w = W(); w.goals["G26"] = {"id": "G26", "status": "held_environment_unverified", "selected_for_week": False}; rc, j, e = w.run(); d = disp(j)
    res["unselected_held_goal_does_not_block"] = (rc == 0 and gate(j) == "READY" and d.get("G26") in (None, "excluded", "not_selected"), (rc, gate(j), d.get("G26")))
    w.close()
    w = W(); w.goals["R01"] = {"id": "R01", "status": "accepted", "selected_for_week": True}; rc, j, e = w.run(); d = disp(j); rs = " ".join((j.get("release_gate") or {}).get("reasons") or [])
    res["queue_accepted_without_acceptance_record_not_ready_named"] = (rc == 1 and "R01" in rs, (rc, d.get("R01"), rs[:120]))
    w.close()
    row("R03 selection: a rejected goal is excluded and kept out; a goal not selected for the week does not block; a queue-accepted goal with no acceptance record is not ready and named", all(v[0] for v in res.values()), res)

@safe
def r04():
    res = {}
    def meta(name, mut):
        w = W(); mut(w.repo); before = tree(w.repo); rc, j, e = w.run(); pr = (j.get("metadata") or {}).get("problems") or []
        res[name] = (rc == 1 and gate(j) == "NOT_READY" and bool(pr) and tree(w.repo) == before, (rc, gate(j), [str(p)[:80] for p in pr][:2])); w.close()
    def sub(path, old, new):
        def f(repo):
            p = os.path.join(repo, path); s = open(p).read(); assert old in s, (path, old); open(p, "w").write(s.replace(old, new, 1))
        return f
    meta("changelog_top_heading_ahead", lambda r: sub("CHANGELOG.md", "0.61", "0.62")(r))
    meta("description_count_wrong", sub("pyproject.toml", "61 portable", "62 portable"))
    def extra_skill(r):
        os.makedirs(os.path.join(r, "employees", "design", "zz-new")); open(os.path.join(r, "employees", "design", "zz-new", "SKILL.md"), "w").write("---\nname: zz-new\n---\n")
    meta("extra_skill_file", extra_skill)
    def cat_drop(r):
        p = os.path.join(r, "control-plane", "skills.json"); c = json.load(open(p))
        if isinstance(c, dict):
            k = [k for k, v in c.items() if isinstance(v, list)][0]; c[k] = c[k][:-1]
        else: c = c[:-1]
        json.dump(c, open(p, "w"))
    meta("catalog_missing_one", cat_drop)
    row("R04 metadata reconciliation: a CHANGELOG heading ahead of pyproject, a wrong description count, an extra SKILL.md and a catalog missing one skill each give NOT_READY with a named problem, and REPO is not changed", all(v[0] for v in res.values()), res)

@safe
def r05():
    res = {}; w = W(); o = os.path.join(w.top, "inv.json"); before = tree(w.repo); rc, j, e = w.run("--out", o)
    res["out_written_equals_stdout"] = (os.path.exists(o) and json.load(open(o)) == j, rc)
    res["only_out_written"] = (tree(w.repo) == before, 0)
    p = w.write()
    for nm, args in (("bad_queue", [PY, TOOL, "inventory", w.repo, "--queue", os.path.join(w.top, "nope.json"), "--acceptance"] + p["acc"] + ["--candidates", p["idx"]]),
                     ("bad_repo", [PY, TOOL, "inventory", os.path.join(w.top, "nope"), "--queue", p["queue"], "--acceptance"] + p["acc"] + ["--candidates", p["idx"]]),
                     ("out_missing_folder", [PY, TOOL, "inventory", w.repo, "--queue", p["queue"], "--acceptance"] + p["acc"] + ["--candidates", p["idx"], "--out", os.path.join(w.top, "no", "x.json")])):
        r = subprocess.run(args, capture_output=True, text=True, env=ENV, timeout=60)
        res["%s_exit_2" % nm] = (r.returncode == 2 and "Traceback" not in r.stderr, (r.returncode, r.stderr.strip()[-100:]))
    json.dump({"goals": "x"}, open(p["queue"], "w")); r = subprocess.run([PY, TOOL, "inventory", w.repo, "--queue", p["queue"], "--acceptance"] + p["acc"] + ["--candidates", p["idx"]], capture_output=True, text=True, env=ENV)
    res["malformed_queue_exit_2"] = (r.returncode == 2 and "Traceback" not in r.stderr, r.returncode)
    w.close()
    row("R05 --out equals the report and is the only write; unreadable or malformed inputs and a missing --out folder exit 2 without a traceback", all(v[0] for v in res.values()), res)

@safe
def o06():
    det = {}
    for v, want in (("0.9", "0.10"), ("1.2.3", "1.3.0"), ("2", None)):
        w = W(); p = os.path.join(w.repo, "pyproject.toml"); s = open(p).read(); open(p, "w").write(s.replace('version = "0.61"', 'version = "%s"' % v, 1))
        c = os.path.join(w.repo, "CHANGELOG.md"); open(c, "w").write(open(c).read().replace("0.61", v, 1)); rc, j, e = w.run()
        det["version_%s" % v] = [rc, (j.get("proposed_version") or {}).get("version"), want, "Traceback" in e]; w.close()
    w = W(); w.goals["X1"] = {"id": "X1", "status": "accepted", "selected_for_week": True}; rc, j, e = w.run(); det["unknown_id_shape"] = [rc, j.get("unknown_ids"), gate(j)]; w.close()
    row("O06 OBS: next-version proposals for other version shapes and an id outside the G/M/P/R pattern (recorded, not scored)", True, det, scored=False)

for f in (r01, r02, r03, r04, r05, o06): f()
json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
core = [r for r in ROWS if r.get("scored", True)]; n = sum(r["pass"] for r in core)
print("M41 ORACLE %d/%d scored %s" % (n, len(core), "PASS" if n == len(core) else "FAIL"))
