#!/usr/bin/env python3
"""release_candidate.py: release-candidate inventory and metadata reconciliation (G41). Read only.

  inventory REPO --queue QUEUE.json --acceptance A.json [A.json...] --candidates INDEX.json
            [--git] [--json] [--out FILE]

QUEUE is the work-queue format (goals[].id/status, release_gate). Acceptance files hold
entries[].id/commit/manifest_sha256. INDEX lists the current candidate per goal (id, candidate_sha).
For every selected goal the report gives one disposition:

  accepted            accepted, and the accepted commit is the current candidate (or no newer candidate)
  acceptance_stale    accepted at one commit but the current candidate is another: the included revision
                      would not be the reviewed one (with --git: whether the candidate descends from it)
  candidate_only      a candidate exists but no acceptance record
  excluded            the queue marks the goal excluded or rejected: it must stay out of the release
  missing             no candidate and no acceptance

It also reconciles release metadata in REPO without changing it: pyproject version against the top
CHANGELOG heading, and the skill count in the pyproject description against employees/*/*/SKILL.md and
control-plane/skills.json. It proposes one next version (minor step) and never applies it.

The computed release gate is READY only when every required final goal and every other selected goal is
accepted or excluded, the metadata agrees, no acceptance conflicts, and the queue's release_gate names a
candidate_commit, checks_revision and reviewed_revision. Otherwise NOT_READY with every reason. Steps
this tool cannot do (version apply, tag, release, catalog or roster regeneration, multi-OS CI, branding
check, PR replies) are listed as blocked_on_root_or_owner.

Exit codes: 0 READY, 1 NOT_READY, 2 invalid input. Nothing is written except --out.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ID_RE = re.compile(r"^[A-Z][0-9]{2}$")
EXCLUDED = ("excluded", "rejected")
BLOCKED = [
    {"step": "apply the proposed version to pyproject.toml and CHANGELOG.md", "owner": "root"},
    {"step": "regenerate or edit control-plane/skills.json, roster.json or counts", "owner": "root"},
    {"step": "supported CI on Linux/macOS/Windows Python 3.12 and Linux 3.10/3.13 at the final revision", "owner": "root"},
    {"step": "protected branding SHA256 check at the final revision", "owner": "root"},
    {"step": "existing PR replies or updates", "owner": "root with owner approval"},
    {"step": "tag, GitHub release and main push", "owner": "root after the owner's final gate"},
]


class Invalid(Exception):
    pass


def _load(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise Invalid("%s unreadable: %s" % (what, type(e).__name__))


def load_queue(path):
    q = _load(path, "queue")
    if not isinstance(q, dict) or not isinstance(q.get("goals"), list) or not isinstance(q.get("release_gate"), dict):
        raise Invalid("queue needs goals (list) and release_gate (object)")
    goals = {}
    for g in q["goals"]:
        if not isinstance(g, dict) or not isinstance(g.get("id"), str) or not ID_RE.match(g["id"]):
            raise Invalid("each queue goal needs an id like G41")
        if g["id"] in goals:
            raise Invalid("goal %s appears twice in the queue" % g["id"])
        goals[g["id"]] = str(g.get("status") or "")
    gate = q["release_gate"]
    req = gate.get("required_final_goals", [])
    if not isinstance(req, list) or not all(isinstance(x, str) and x in goals for x in req):
        raise Invalid("release_gate.required_final_goals must list goals in the queue")
    return goals, gate


def load_acceptance(paths):
    acc, conflicts = {}, []
    for p in paths:
        a = _load(p, "acceptance %s" % Path(p).name)
        if not isinstance(a, dict) or not isinstance(a.get("entries"), list):
            raise Invalid("acceptance %s needs entries (list)" % Path(p).name)
        for e in a["entries"]:
            if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not ID_RE.match(e["id"]):
                raise Invalid("acceptance entries need an id like G03")
            if "commit" not in e and "source_commit" in e:
                # accepted work in another repository (a pull-request follow-up): no commit in this repo
                sc = e.get("source_commit")
                if sc is not None and (not isinstance(sc, str) or not SHA_RE.match(sc)):
                    raise Invalid("source_commit for %s must be a full 40-hex commit or null" % e["id"])
                acc[e["id"]] = {"commit": None, "external_commit": sc, "source": Path(p).name}
                continue
            if not isinstance(e.get("commit"), str) or not SHA_RE.match(e["commit"]):
                raise Invalid("acceptance entry %s needs a full 40-hex commit" % e["id"])
            prev = acc.get(e["id"])
            if prev and prev["commit"] != e["commit"]:
                conflicts.append({"id": e["id"], "commits": sorted({prev["commit"], e["commit"]})})
            acc[e["id"]] = {"commit": e["commit"], "manifest_sha256": e.get("manifest_sha256"),
                            "source": Path(p).name}
    return acc, conflicts


def load_candidates(path):
    c = _load(path, "candidates")
    if isinstance(c, dict):
        c = c.get("candidates")
    if not isinstance(c, list):
        raise Invalid("candidates must be a list of {id, candidate_sha} (or {candidates: [...]})")
    out = {}
    for x in c:
        if not isinstance(x, dict) or not isinstance(x.get("id"), str) or not ID_RE.match(x["id"]):
            raise Invalid("each candidate needs an id like G41")
        sha = x.get("candidate_sha")
        if sha is not None and (not isinstance(sha, str) or not SHA_RE.match(sha)):
            raise Invalid("candidate_sha for %s must be a full 40-hex commit or null" % x["id"])
        out[x["id"]] = sha
    return out


def _git_descends(repo, old, new):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    for c in (old, new):
        if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", c + "^{commit}"], capture_output=True,
                          env=env, timeout=60).returncode != 0:
            return "unknown (commit %s not in this clone)" % c[:12]
    rc = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", old, new], capture_output=True,
                        env=env, timeout=60).returncode
    return "candidate descends from the accepted commit" if rc == 0 else "candidate does not descend from it"


def disposition(gid, status, acc, cand, repo, use_git):
    d = {"id": gid, "queue_status": status}
    a, c = acc.get(gid), cand.get(gid)
    if status in EXCLUDED:
        d["disposition"] = "excluded"
        if a:
            d["note"] = "an acceptance exists but the queue excludes the goal"
        return d
    if a and a["commit"] is None:
        d.update(disposition="accepted", acceptance_source=a["source"], external_commit=a.get("external_commit"),
                 note="accepted work outside this repository; nothing of it is included in this release")
        return d
    if a:
        d["accepted_commit"] = a["commit"]
        d["acceptance_source"] = a["source"]
        if c and c != a["commit"]:
            d.update(disposition="acceptance_stale", candidate_sha=c)
            if use_git:
                d["ancestry"] = _git_descends(repo, a["commit"], c)
        else:
            d["disposition"] = "accepted"
        return d
    if c:
        d.update(disposition="candidate_only", candidate_sha=c)
    else:
        d["disposition"] = "missing"
    return d


def metadata(repo):
    m, problems = {}, []
    pp = repo / "pyproject.toml"
    try:
        text = pp.read_text(encoding="utf-8")
    except OSError:
        raise Invalid("REPO has no readable pyproject.toml")
    v = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    m["pyproject_version"] = v.group(1) if v else None
    desc = re.search(r'(?m)^description\s*=\s*"(\d+)\b', text)
    m["description_skill_count"] = int(desc.group(1)) if desc else None
    try:
        cl = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
        h = re.search(r"(?m)^##\s+v?([0-9][^\s(]*)", cl)
        m["changelog_top_version"] = h.group(1) if h else None
    except OSError:
        m["changelog_top_version"] = None
    m["skill_files"] = len(list((repo / "employees").glob("*/*/SKILL.md")))
    try:
        s = json.loads((repo / "control-plane/skills.json").read_text(encoding="utf-8"))
        m["catalog_skills"] = len(s.get("skills", [])) if isinstance(s, dict) else None
    except (OSError, ValueError):
        m["catalog_skills"] = None
    if not m["pyproject_version"]:
        problems.append("pyproject.toml has no version")
    elif m["pyproject_version"] != m["changelog_top_version"]:
        problems.append("pyproject version %s differs from the top CHANGELOG heading %s"
                        % (m["pyproject_version"], m["changelog_top_version"]))
    counts = {"description": m["description_skill_count"], "SKILL.md files": m["skill_files"],
              "skills.json": m["catalog_skills"]}
    if len(set(counts.values())) != 1:
        problems.append("skill counts disagree: %s" % ", ".join("%s %s" % kv for kv in counts.items()))
    m["problems"] = problems
    return m


def propose(version):
    p = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?$", version or "")
    if not p:
        return None
    return "%s.%d" % (p.group(1), int(p.group(2)) + 1)


def inventory(ns):
    repo = Path(ns.repo)
    if not repo.is_dir():
        raise Invalid("REPO must be a folder")
    goals, gate = load_queue(ns.queue)
    acc, conflicts = load_acceptance(ns.acceptance)
    cand = load_candidates(ns.candidates)
    unknown = sorted((set(acc) | set(cand)) - set(goals))
    rows = [disposition(g, goals[g], acc, cand, repo, ns.git) for g in sorted(goals)]
    meta = metadata(repo)
    reasons = []
    for r in rows:
        if r["disposition"] not in ("accepted", "excluded"):
            reasons.append("%s %s" % (r["id"], r["disposition"]))
    for g in gate.get("required_final_goals", []):
        if next(r for r in rows if r["id"] == g)["disposition"] != "accepted":
            reasons.append("required final goal %s is not accepted" % g)
    reasons += ["conflicting acceptance for %s" % c["id"] for c in conflicts]
    reasons += ["metadata: " + p for p in meta["problems"]]
    for k in ("candidate_commit", "checks_revision", "reviewed_revision"):
        if not gate.get(k):
            reasons.append("release_gate.%s is not set by root" % k)
    counts = {}
    for r in rows:
        counts[r["disposition"]] = counts.get(r["disposition"], 0) + 1
    rep = {
        "schema": "solaris.release-candidate-inventory/1",
        "release_gate": {"state": "NOT_READY" if reasons else "READY", "queue_state": gate.get("state"),
                         "reasons": reasons, "applied": False},
        "counts": counts,
        "included_if_released": [r["id"] for r in rows if r["disposition"] == "accepted"],
        "excluded": [r["id"] for r in rows if r["disposition"] == "excluded"],
        "goals": rows, "conflicts": conflicts, "unknown_ids": unknown, "metadata": meta,
        "proposed_version": {"version": propose(meta["pyproject_version"]), "from": meta["pyproject_version"],
                             "status": "proposed only; root alone applies release metadata after the final gates",
                             "applied": False},
        "blocked_on_root_or_owner": BLOCKED,
        "limits": "reads files and, with --git, local commit ancestry; it does not run CI, verify manifests "
                  "byte for byte, or decide acceptance",
    }
    data = json.dumps(rep, indent=2, sort_keys=True) + "\n"
    if ns.out:
        out = Path(ns.out)
        if not out.parent.is_dir():
            raise Invalid("--out folder does not exist")
        fd, tmp = tempfile.mkstemp(dir=str(out.parent), prefix="." + out.name + ".")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, str(out))
    if ns.json:
        sys.stdout.write(data)
    else:
        g = rep["release_gate"]
        print("release gate (computed): %s   queue state: %s   applied: no" % (g["state"], g["queue_state"]))
        print("dispositions: %s" % ", ".join("%s %d" % kv for kv in sorted(counts.items())))
        for r in reasons[:40]:
            print("  - " + r)
        if len(reasons) > 40:
            print("  - ... %d more" % (len(reasons) - 40))
        pv = rep["proposed_version"]
        print("proposed version: %s (from %s), not applied" % (pv["version"], pv["from"]))
        print("blocked on root or owner: " + "; ".join(b["step"] for b in BLOCKED))
    return 0 if not reasons else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inventory")
    i.add_argument("repo")
    i.add_argument("--queue", required=True)
    i.add_argument("--acceptance", nargs="+", required=True)
    i.add_argument("--candidates", required=True)
    i.add_argument("--git", action="store_true", help="check candidate ancestry with local git")
    i.add_argument("--json", action="store_true")
    i.add_argument("--out")
    ns = ap.parse_args(argv)
    try:
        return inventory(ns)
    except Invalid as e:
        print("invalid: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
