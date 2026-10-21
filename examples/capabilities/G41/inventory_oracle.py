#!/usr/bin/env python3
"""G41 oracle: checks a release-candidate inventory tool by its effects, with expectations derived here.

    python3 examples/capabilities/G41/inventory_oracle.py [--tool PATH] [--only o1,o3]

Each check builds a fresh temporary programme (queue, acceptance, candidate index) and a small repository
copy with release metadata, runs the tool, and reads its JSON report. Prints one line per check and a final
"ACCEPTED n/n" or "REJECTED k/n".
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PY = sys.executable
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
TOOL = REPO / "employees/quality-security/assurance/release_candidate.py"
MADE = []


def sha(n):
    return hashlib.sha1(str(n).encode()).hexdigest()


def prog(goals, acc, cands, gate_fields=False, version="0.61", changelog="0.61", count=3, skills=3, catalog=3):
    """goals: {id: status}; acc: {id: commit}; cands: {id: commit or None}."""
    top = Path(tempfile.mkdtemp(prefix="g41o-"))
    MADE.append(top)
    r = top / "repo"
    (r / "control-plane").mkdir(parents=True)
    (r / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "%s"\ndescription = "%d portable '
                                      'specialist skills"\n' % (version, count))
    (r / "CHANGELOG.md").write_text("# Changelog\n\n## %s (2026-10-18)\n\n- x\n\n## 0.60 (2026-10-16)\n" % changelog)
    for i in range(skills):
        d = r / "employees" / "dept" / ("role-%d" % i)
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("x")
    (r / "control-plane/skills.json").write_text(json.dumps({"catalog_version": 1, "skills": [{"id": i} for i in range(catalog)]}))
    gate = {"state": "NOT_READY", "required_final_goals": [g for g in goals if g in ("G39", "G40", "G41", "G42")],
            "candidate_commit": sha("c") if gate_fields else None, "checks_revision": sha("c") if gate_fields else None,
            "reviewed_revision": sha("c") if gate_fields else None}
    (top / "queue.json").write_text(json.dumps({"goals": [{"id": g, "status": s} for g, s in goals.items()],
                                                "release_gate": gate}))
    (top / "acc.json").write_text(json.dumps({"entries": [{"id": g, "commit": c, "manifest_sha256": "0" * 64}
                                                          for g, c in acc.items()]}))
    (top / "cand.json").write_text(json.dumps([{"id": g, "candidate_sha": c} for g, c in cands.items()]))
    return top


def tree(p):
    h = hashlib.sha256()
    for f in sorted(x for x in p.rglob("*") if x.is_file()):
        h.update(f.relative_to(p).as_posix().encode() + b"\0" + f.read_bytes())
    return h.hexdigest()


def inv(top, *extra, acc=("acc.json",)):
    p = subprocess.run([PY, str(TOOL), "inventory", str(top / "repo"), "--queue", str(top / "queue.json"),
                        "--acceptance"] + [str(top / a) for a in acc] + ["--candidates", str(top / "cand.json"),
                       "--json"] + list(extra), capture_output=True, text=True, env=ENV, timeout=120)
    try:
        return p.returncode, json.loads(p.stdout), p.stderr
    except ValueError:
        return p.returncode, {}, p.stderr


def disp(rep, g):
    for r in rep.get("goals", []):
        if r.get("id") == g:
            return r.get("disposition")
    return None


def state(rep):
    return (rep.get("release_gate") or {}).get("state")


ALL = {"G39": "accepted", "G40": "accepted", "G41": "accepted", "G42": "accepted", "G05": "accepted"}


def o1_clean_ready():
    """Clean control: everything accepted at the current candidate, metadata agrees, root set the gate
    revisions: READY (exit 0). A tool that can never say READY is not reconciling anything."""
    t = prog(ALL, {g: sha(g) for g in ALL}, {g: sha(g) for g in ALL}, gate_fields=True)
    rc, rep, _ = inv(t)
    ok = rc == 0 and state(rep) == "READY" and sorted(rep.get("included_if_released", [])) == sorted(ALL)
    return ok, "rc %s %s included %s" % (rc, state(rep), len(rep.get("included_if_released", [])))


def o2_nothing_accepted():
    """Real shape today: candidates but no acceptance: NOT_READY (exit 1), every goal candidate_only, each
    required final goal named."""
    t = prog(ALL, {}, {g: sha(g) for g in ALL}, gate_fields=True)
    rc, rep, _ = inv(t)
    rs = " ".join((rep.get("release_gate") or {}).get("reasons", []))
    ok = rc == 1 and state(rep) == "NOT_READY" and all(disp(rep, g) == "candidate_only" for g in ALL) and \
        all("required final goal %s" % g in rs for g in ("G39", "G40", "G41", "G42"))
    # one ordinary (not required) goal still unaccepted is enough to block
    g = dict(ALL, G07="candidate")
    t2 = prog(g, {x: sha(x) for x in ALL}, {x: sha(x) for x in g}, gate_fields=True)
    rc2, rep2, _ = inv(t2)
    ok = ok and rc2 == 1 and disp(rep2, "G07") == "candidate_only" and \
        "G07 candidate_only" in (rep2.get("release_gate") or {}).get("reasons", [])
    return ok, "rc %s %s; one ordinary goal unaccepted %s" % (rc, state(rep), rc2)


def o3_acceptance_stale():
    """A candidate that moved after acceptance is not the reviewed revision: acceptance_stale, NOT_READY."""
    c = {g: sha(g) for g in ALL}
    c["G05"] = sha("G05-r2")
    t = prog(ALL, {g: sha(g) for g in ALL}, c, gate_fields=True)
    rc, rep, _ = inv(t)
    ok = rc == 1 and disp(rep, "G05") == "acceptance_stale" and "G05" not in rep.get("included_if_released", [])
    return ok, "rc %s G05 %s" % (rc, disp(rep, "G05"))


def o4_version_mismatch():
    """pyproject version and the top CHANGELOG heading disagree: NOT_READY naming both."""
    t = prog(ALL, {g: sha(g) for g in ALL}, {g: sha(g) for g in ALL}, gate_fields=True, version="0.62")
    rc, rep, _ = inv(t)
    rs = " ".join((rep.get("release_gate") or {}).get("reasons", []))
    ok = rc == 1 and "0.62" in rs and "0.61" in rs
    return ok, "rc %s %s" % (rc, rs[-120:])


def o5_count_mismatch():
    """Skill count in the description, SKILL.md files and skills.json disagree: NOT_READY."""
    res = []
    for kw in ({"skills": 4}, {"catalog": 2}, {"count": 5}):
        t = prog(ALL, {g: sha(g) for g in ALL}, {g: sha(g) for g in ALL}, gate_fields=True, **kw)
        rc, rep, _ = inv(t)
        res.append(rc == 1 and any("skill counts" in r for r in (rep.get("release_gate") or {}).get("reasons", [])))
    return all(res), str(res)


def o6_excluded_stays_out():
    """A rejected goal is excluded and never listed for release, even with an old acceptance."""
    g = dict(ALL, G07="rejected")
    t = prog(g, {x: sha(x) for x in g}, {x: sha(x) for x in g}, gate_fields=True)
    rc, rep, _ = inv(t)
    ok = rc == 0 and disp(rep, "G07") == "excluded" and "G07" not in rep.get("included_if_released", []) and \
        "G07" in rep.get("excluded", [])
    return ok, "rc %s G07 %s" % (rc, disp(rep, "G07"))


def o7_read_only_and_proposal():
    """Nothing in the repository or programme changes; the proposal is one minor step and not applied;
    blocked steps name root."""
    t = prog(ALL, {}, {}, version="0.61")
    before = tree(t)
    rc, rep, _ = inv(t)
    pv = rep.get("proposed_version") or {}
    blocked = " ".join(b.get("step", "") + b.get("owner", "") for b in rep.get("blocked_on_root_or_owner", []))
    ok = tree(t) == before and pv.get("version") == "0.62" and pv.get("applied") is False and \
        (rep.get("release_gate") or {}).get("applied") is False and "tag" in blocked and "root" in blocked
    return ok, "unchanged %s proposed %s" % (tree(t) == before, pv.get("version"))


def o8_gate_fields_unset():
    """All accepted and consistent, but root has not set the gate revisions: NOT_READY."""
    t = prog(ALL, {g: sha(g) for g in ALL}, {g: sha(g) for g in ALL}, gate_fields=False)
    rc, rep, _ = inv(t)
    ok = rc == 1 and any("candidate_commit" in r for r in (rep.get("release_gate") or {}).get("reasons", []))
    return ok, "rc %s %s" % (rc, state(rep))


def o9_conflict_and_invalid():
    """Two acceptance files naming different commits for one goal: NOT_READY with the conflict. Short
    commits, a missing file and duplicate queue ids: exit 2 and no report."""
    t = prog(ALL, {g: sha(g) for g in ALL}, {g: sha(g) for g in ALL}, gate_fields=True)
    (t / "acc2.json").write_text(json.dumps({"entries": [{"id": "G05", "commit": sha("other")}]}))
    rc, rep, _ = inv(t, acc=("acc.json", "acc2.json"))
    conflict = rc == 1 and any(c.get("id") == "G05" for c in rep.get("conflicts", []))
    (t / "bad.json").write_text(json.dumps({"entries": [{"id": "G05", "commit": "abc123"}]}))
    r1 = inv(t, acc=("bad.json",))[0]
    r2 = inv(t, acc=("nope.json",))[0]
    q = json.loads((t / "queue.json").read_text())
    q["goals"].append({"id": "G05", "status": "accepted"})
    (t / "queue.json").write_text(json.dumps(q))
    r3 = inv(t)[0]
    ok = conflict and (r1, r2, r3) == (2, 2, 2)
    return ok, "conflict %s invalid %s" % (conflict, (r1, r2, r3))


def o10_git_ancestry():
    """With --git, a stale acceptance says whether the candidate descends from the accepted commit, using a
    real local repository."""
    g = Path(tempfile.mkdtemp(prefix="g41o-git-"))
    MADE.append(g)
    run = lambda *a: subprocess.run(["git", "-C", str(g)] + list(a), capture_output=True, text=True, env=ENV,
                                    timeout=60).stdout.strip()
    run("init", "-q")
    run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "a")
    a = run("rev-parse", "HEAD")
    run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "b")
    b = run("rev-parse", "HEAD")
    run("checkout", "-q", "--orphan", "other")
    run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "c")
    c = run("rev-parse", "HEAD")
    t = prog({"G05": "accepted", "G06": "accepted"}, {"G05": a, "G06": a}, {"G05": b, "G06": c}, gate_fields=True)
    shutil.rmtree(t / "repo" / "employees")
    for f in ("pyproject.toml", "CHANGELOG.md", "control-plane"):
        src = t / "repo" / f
        dst = g / f
        shutil.move(str(src), str(dst))
    shutil.rmtree(t / "repo")
    os.symlink(str(g), str(t / "repo"))
    rc, rep, _ = inv(t, "--git")
    anc = {r["id"]: r.get("ancestry", "") for r in rep.get("goals", [])}
    ok = rc == 1 and anc.get("G05", "").startswith("candidate descends") and "does not descend" in anc.get("G06", "")
    return ok, "rc %s %s" % (rc, anc)


def cleanup():
    while MADE:
        shutil.rmtree(MADE.pop(), ignore_errors=True)


CHECKS = [o1_clean_ready, o2_nothing_accepted, o3_acceptance_stale, o4_version_mismatch, o5_count_mismatch,
          o6_excluded_stays_out, o7_read_only_and_proposal, o8_gate_fields_unset, o9_conflict_and_invalid,
          o10_git_ancestry]


def main():
    global TOOL
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=str(TOOL))
    ap.add_argument("--only")
    ns = ap.parse_args()
    TOOL = Path(ns.tool).resolve()
    only = set(ns.only.split(",")) if ns.only else None
    passed = total = 0
    for c in CHECKS:
        if only and c.__name__.split("_")[0] not in only:
            continue
        total += 1
        try:
            ok, note = c()
        except Exception as e:
            ok, note = False, "error %s: %s" % (type(e).__name__, str(e)[:160])
        passed += bool(ok)
        print("%s %-28s %s" % ("PASS" if ok else "FAIL", c.__name__, note))
    cleanup()
    print("%s %d/%d" % ("ACCEPTED" if passed == total else "REJECTED", passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
