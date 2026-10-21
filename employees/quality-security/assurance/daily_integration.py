#!/usr/bin/env python3
"""Daily integration evidence matrix for review candidates (Solaris quality-security/assurance).

A daily integration goal stacks several review candidates (merge commits on one branch) and must
show that the stacked tree is what the candidates said it was, that their own tests and oracles
still pass together, and which of them root has accepted at exactly that revision. This tool checks
one plan against one git checkout and writes one evidence matrix. It only reads the repository and
runs the commands the plan names; it never commits, pushes, merges or edits a tracked file.

Checks, in order:
  bindings   every prerequisite commit exists and is an ancestor of HEAD, and so is the base;
  drift      every file a prerequisite changed (against the base) has, at HEAD, the blob of the
             newest prerequisite that changed it; two unrelated prerequisites that disagree about a
             file are an OVERLAP unless the plan names the file in resolved_overlaps;
  scope      files HEAD changed that no prerequisite changed must match the plan's writable globs;
  tree       the working tree is clean (HEAD alone cannot identify uncommitted work), before and
             after the runs;
  acceptance per prerequisite: ACCEPTED (an acceptance record names this exact commit),
             ACCEPTED_OTHER_REVISION (accepted, but at another commit: acceptance does not carry),
             CANDIDATE (no record) or UNKNOWN (no acceptance file given). Information, not a failure:
             root alone accepts;
  external   accepted contributions outside this repository (no commit here) must match their
             acceptance record (source_commit, reply_sha256, validation_manifest_sha256); a supplied
             reply readback or validation manifest must hash to the recorded value;
  runs       ({python} in a command argument is replaced by the integration interpreter)
             --run tests: each prerequisite's test modules and commands plus the plan's
             cross_checks; --run all also runs the repository gates CI runs (full suite, control-plane
             self-test, Quality OS audit, manifest parse, catalog check, no symlinks, skill metadata).

Usage:
  daily_integration.py check --plan PLAN.json [--repo DIR] [--acceptance FILE]... [--reply ID=FILE]...
                             [--manifest ID=FILE]... [--run none|tests|all] [--skip-gate NAME]...
                             [--python PATH] [--timeout SECONDS] [--json] [--out REPORT]
Exit codes: 0 INTEGRATED, 1 NOT_INTEGRATED (findings listed), 2 INVALID_INPUT (nothing written).
Python 3.9+, standard library and the git command only.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

SCHEMA = "solaris.daily-integration/1"
REPORT_SCHEMA = "solaris.daily-integration-report/1"
ID_RE = re.compile(r"^[A-Z][0-9]{2}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MOD_RE = re.compile(r"^tests\.test_[a-z0-9_]{1,80}$")
GATES = ("suite", "control_plane", "quality_audit", "manifests", "catalog", "symlinks", "metadata")
MAX_PLAN = 1 << 20


class Invalid(Exception):
    pass


def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise Invalid("duplicate key %r" % k[:40])
        out[k] = v
    return out


def _const(name):
    raise Invalid("non-finite number %s" % name)


def load_json(path, what, limit=MAX_PLAN):
    try:
        with open(path, "rb") as fh:
            raw = fh.read(limit + 1)
    except OSError as exc:
        raise Invalid("%s: cannot read (%s)" % (what, exc.strerror or exc.__class__.__name__)) from None
    if len(raw) > limit:
        raise Invalid("%s: larger than %d bytes" % (what, limit))
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_no_dupes, parse_constant=_const), raw
    except Invalid as exc:
        raise Invalid("%s: %s" % (what, exc)) from None
    except (ValueError, RecursionError) as exc:
        raise Invalid("%s: not JSON (%s)" % (what, str(exc)[:80])) from None


def _str(v, where, rx=None, limit=300):
    if not isinstance(v, str) or not v or len(v) > limit:
        raise Invalid("%s: expected a non-empty string" % where)
    if rx is not None and not rx.match(v):
        raise Invalid("%s: %r has the wrong form" % (where, v[:60]))
    return v


def _relpath(v, where):
    v = _str(v, where)
    if v.startswith(("/", "\\")) or "\\" in v or ".." in v.split("/") or ":" in v or "\x00" in v:
        raise Invalid("%s: %r must be a relative path inside the repository" % (where, v[:60]))
    return v


def _argv(v, where):
    if not isinstance(v, list) or not v or len(v) > 40:
        raise Invalid("%s: expected a list [script, arg...]" % where)
    out = [_relpath(v[0], where + "[0]")]
    if not out[0].endswith(".py"):
        raise Invalid("%s[0]: commands are Python scripts run with the integration interpreter" % where)
    for i, a in enumerate(v[1:], 1):
        out.append(_str(a, "%s[%d]" % (where, i)))
    return out


def _list(v, where, limit=100):
    if v is None:
        return []
    if not isinstance(v, list) or len(v) > limit:
        raise Invalid("%s: expected a list of at most %d items" % (where, limit))
    return v


def parse_plan(doc):
    if not isinstance(doc, dict):
        raise Invalid("plan: expected an object")
    if doc.get("schema") != SCHEMA:
        raise Invalid("plan: schema must be %r" % SCHEMA)
    known = {"schema", "goal", "base", "writable", "prerequisites", "external", "cross_checks",
             "resolved_overlaps", "notes"}
    extra = sorted(set(doc) - known)
    if extra:
        raise Invalid("plan: unknown key %r" % extra[0][:40])
    plan = {"goal": _str(doc.get("goal"), "goal", ID_RE), "base": _str(doc.get("base"), "base", SHA_RE)}
    plan["writable"] = [_relpath(w, "writable[%d]" % i) for i, w in enumerate(_list(doc.get("writable"), "writable"))]
    if not plan["writable"]:
        raise Invalid("writable: name at least one glob the integration may change")
    seen = set()
    pre = []
    raw_pre = _list(doc.get("prerequisites"), "prerequisites", 50)
    if not raw_pre:
        raise Invalid("prerequisites: at least one is required")
    for i, p in enumerate(raw_pre):
        w = "prerequisites[%d]" % i
        if not isinstance(p, dict) or set(p) - {"id", "commit", "tests", "commands", "note"}:
            raise Invalid("%s: expected {id, commit, tests, commands}" % w)
        pid = _str(p.get("id"), w + ".id", ID_RE)
        if pid in seen:
            raise Invalid("%s: duplicate id %s" % (w, pid))
        seen.add(pid)
        tests = [_str(t, "%s.tests[%d]" % (w, j), MOD_RE) for j, t in enumerate(_list(p.get("tests"), w + ".tests"))]
        cmds = [_argv(c, "%s.commands[%d]" % (w, j)) for j, c in enumerate(_list(p.get("commands"), w + ".commands"))]
        pre.append({"id": pid, "commit": _str(p.get("commit"), w + ".commit", SHA_RE), "tests": tests, "commands": cmds})
    plan["prerequisites"] = pre
    ext = []
    for i, e in enumerate(_list(doc.get("external"), "external", 20)):
        w = "external[%d]" % i
        if not isinstance(e, dict) or set(e) - {"id", "source_commit", "reply_url", "reply_sha256", "validation_id",
                                                 "validation_manifest_sha256", "consumes", "note"}:
            raise Invalid("%s: unexpected keys" % w)
        eid = _str(e.get("id"), w + ".id", ID_RE)
        if eid in seen:
            raise Invalid("%s: duplicate id %s" % (w, eid))
        seen.add(eid)
        sc = e.get("source_commit")
        if sc is not None:
            sc = _str(sc, w + ".source_commit", SHA_RE)
        vid = e.get("validation_id")
        if vid is not None:
            vid = _str(vid, w + ".validation_id", ID_RE)
        url = _str(e.get("reply_url"), w + ".reply_url")
        if not url.startswith("https://"):
            raise Invalid("%s.reply_url: expected an https URL" % w)
        ext.append({"id": eid, "source_commit": sc, "reply_url": url,
                    "reply_sha256": _str(e.get("reply_sha256"), w + ".reply_sha256", SHA256_RE),
                    "validation_id": vid,
                    "validation_manifest_sha256": _str(e.get("validation_manifest_sha256"), w + ".validation_manifest_sha256", SHA256_RE),
                    "consumes": _str(e.get("consumes", "response evidence"), w + ".consumes")})
    plan["external"] = ext
    plan["cross_checks"] = [_argv(c, "cross_checks[%d]" % i) for i, c in enumerate(_list(doc.get("cross_checks"), "cross_checks"))]
    ro = {}
    for i, r in enumerate(_list(doc.get("resolved_overlaps"), "resolved_overlaps")):
        w = "resolved_overlaps[%d]" % i
        if not isinstance(r, dict) or set(r) != {"path", "reason"}:
            raise Invalid("%s: expected {path, reason}" % w)
        ro[_relpath(r["path"], w + ".path")] = _str(r["reason"], w + ".reason")
    plan["resolved_overlaps"] = ro
    return plan


def git(repo, *args, ok=(0,)):
    r = subprocess.run(["git", "-C", repo] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode not in ok:
        raise RuntimeError("git %s: %s" % (args[0], r.stderr.decode("utf-8", "replace").strip()[:200]))
    return r.returncode, r.stdout


def exists(repo, sha):
    return git(repo, "cat-file", "-e", sha + "^{commit}", ok=(0, 1, 128))[0] == 0


def is_anc(repo, a, b):
    return git(repo, "merge-base", "--is-ancestor", a, b, ok=(0, 1, 128))[0] == 0


def changed(repo, a, b):
    out = git(repo, "diff", "--name-only", "-z", "--no-renames", a, b)[1]
    return set(p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p)


def tree(repo, rev):
    out = git(repo, "ls-tree", "-r", "-z", rev)[1]
    res = {}
    for ent in out.split(b"\0"):
        if ent:
            meta, path = ent.split(b"\t", 1)
            res[path.decode("utf-8", "surrogateescape")] = meta.split()[2].decode()
    return res


def dirty(repo):
    out = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")[1]
    return sorted(e.decode("utf-8", "surrogateescape")[3:] for e in out.split(b"\0") if e[2:3] == b" ")


def matches(path, globs):
    for g in globs:
        if g.endswith("/**"):
            if path.startswith(g[:-2]):
                return True
        elif fnmatch.fnmatchcase(path, g):
            return True
    return False


def acceptance_index(files):
    idx = {}
    for f in files:
        doc, _ = load_json(f, "acceptance %s" % os.path.basename(f), 16 << 20)
        ents = doc.get("entries") if isinstance(doc, dict) else None
        if not isinstance(ents, list):
            raise Invalid("acceptance %s: expected an object with an entries list" % os.path.basename(f))
        for e in ents:
            if isinstance(e, dict) and isinstance(e.get("id"), str):
                rec = dict(e)
                rec["_file"] = os.path.basename(f)
                idx.setdefault(e["id"], []).append(rec)
    return idx


def _pairs(values, what, ids):
    out = {}
    for v in values or []:
        if "=" not in v:
            raise Invalid("%s: expected ID=FILE, got %r" % (what, v[:60]))
        k, p = v.split("=", 1)
        if k not in ids:
            raise Invalid("%s: %s is not an external id or validation id in the plan" % (what, k[:10]))
        out[k] = p
    return out


def sha256_file(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
    except OSError as exc:
        raise Invalid("cannot read %s (%s)" % (os.path.basename(path), exc.strerror)) from None
    return h.hexdigest()


def _tail(b):
    lines = b.decode("utf-8", "replace").strip().splitlines()
    return [l[:200] for l in lines[-3:]]


def run_one(kind, rid, argv, repo, timeout):
    shown = [os.path.basename(argv[0])] + argv[1:]  # the plan's own words: no interpreter path in the report
    argv = [argv[0]] + [x.replace("{python}", argv[0]) for x in argv[1:]]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    t0 = time.monotonic()
    try:
        r = subprocess.run(argv, cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        rc, tail = r.returncode, _tail(r.stdout)
    except subprocess.TimeoutExpired as exc:
        rc, tail = None, _tail(exc.stdout or b"") + ["timed out after %ss" % timeout]
    except OSError as exc:
        rc, tail = None, ["could not start: %s" % (exc.strerror or exc)]
    return {"kind": kind, "id": rid, "argv": shown, "rc": rc,
            "seconds": round(time.monotonic() - t0, 1), "tail": tail}


MANIFEST_CHECK = r"""
import glob, json
bad = []
for f in sorted(glob.glob('employees/*/*/plugin.json') + glob.glob('employees/*/*/capability.contract.json') + glob.glob('chief-of-staff/capability.contract.json')):
    try:
        d = json.load(open(f))
        if f.endswith('plugin.json'):
            bad += ['%s: missing %s' % (f, k) for k in ('name', 'version', 'description') if k not in d]
    except Exception as e:
        bad.append('%s: %s' % (f, e))
print('\n'.join(bad) if bad else 'all manifests parse OK')
raise SystemExit(1 if bad else 0)
"""


def gate_runs(py, repo, timeout, skip, findings, not_run):
    runs = []
    cmds = {"suite": [py, "-m", "unittest", "discover", "-s", "tests"],
            "control_plane": [py, "control-plane/meta_control_plane.py", "self-test"],
            "manifests": [py, "-c", MANIFEST_CHECK],
            "catalog": [py, "tools/build_skill_catalog.py", "--check"],
            "metadata": [py, "tools/validate_skill_metadata.py"]}
    for name in GATES:
        if name in skip:
            not_run.append({"gate": name, "reason": "skipped by the caller"})
            continue
        if name == "symlinks":
            out = git(repo, "ls-files", "-s", "-z")[1]
            links = [e.split(b"\t", 1)[1].decode("utf-8", "replace") for e in out.split(b"\0") if e.startswith(b"120000 ")]
            runs.append({"kind": "gate", "id": name, "argv": ["git", "ls-files", "-s"], "rc": 1 if links else 0,
                         "seconds": 0.0, "tail": links[:3] or ["no symbolic links"]})
        elif name == "quality_audit":
            argv = [py, "employees/quality-security/assurance/quality_os.py", "audit"]
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            t0 = time.monotonic()
            r = {"kind": "gate", "id": name, "argv": ["quality_os.py", "audit"], "rc": None, "tail": []}
            try:
                res = subprocess.run(argv, cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
                r["rc"] = res.returncode
                try:
                    c = json.loads(res.stdout.decode("utf-8"))["counts"]
                    r["tail"] = ["scanned=%s gaps=%s" % (c["skills_scanned"], c["gaps"])]
                    if r["rc"] == 0 and c["gaps"] != 0:
                        r["rc"] = 1
                except (ValueError, KeyError, TypeError):
                    r["rc"] = r["rc"] or 1
                    r["tail"] = _tail(res.stdout) + ["audit output not readable"]
            except subprocess.TimeoutExpired:
                r["tail"] = ["timed out after %ss" % timeout]
            r["seconds"] = round(time.monotonic() - t0, 1)
            runs.append(r)
        else:
            if name == "metadata":
                probe = subprocess.run([py, "-c", "import yaml"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if probe.returncode != 0:
                    findings.append({"code": "GATE_UNAVAILABLE", "id": name,
                                     "detail": "PyYAML is not importable by this interpreter; use --python with one that has it, or --skip-gate metadata"})
                    continue
            runs.append(run_one("gate", name, cmds[name], repo, timeout))
    return runs


def check(a):
    repo = os.path.abspath(a.repo)
    # Commit ancestry is immutable for this read-only check. Cache only within
    # this invocation, so a later check always observes its own repository state.
    ancestry = {}
    def ancestor(old, new):
        pair = (old, new)
        if pair not in ancestry:
            ancestry[pair] = is_anc(repo, old, new)
        return ancestry[pair]
    doc, raw = load_json(a.plan, "plan")
    plan = parse_plan(doc)
    for s in a.skip_gate or []:
        if s not in GATES:
            raise Invalid("--skip-gate: unknown gate %r (gates: %s)" % (s[:30], ", ".join(GATES)))
    ext_ids = {e["id"] for e in plan["external"]} | {e["validation_id"] for e in plan["external"] if e["validation_id"]}
    replies = _pairs(a.reply, "--reply", {e["id"] for e in plan["external"]})
    manifests = _pairs(a.manifest, "--manifest", ext_ids)
    acc = acceptance_index(a.acceptance) if a.acceptance else None
    try:
        top = git(repo, "rev-parse", "--show-toplevel")[1].decode().strip()
        head = git(repo, "rev-parse", "HEAD")[1].decode().strip()
        head_tree = git(repo, "rev-parse", "HEAD^{tree}")[1].decode().strip()
    except (RuntimeError, OSError):
        raise Invalid("--repo: not a git checkout with a commit") from None
    if os.path.realpath(top) != os.path.realpath(repo):
        raise Invalid("--repo: name the top of the checkout, not a subfolder")
    findings, notes, not_run = [], [], []
    fail = findings.append
    d0 = dirty(repo)
    if d0:
        fail({"code": "DIRTY_TREE", "id": plan["goal"], "detail": "%d uncommitted path(s), first %s" % (len(d0), d0[0][:120])})
    base = plan["base"]
    if not exists(repo, base):
        fail({"code": "UNKNOWN_COMMIT", "id": "base", "detail": base})
    elif not ancestor(base, head):
        fail({"code": "BASE_NOT_ANCESTOR", "id": "base", "detail": "%s is not an ancestor of HEAD" % base[:12]})
    pre_rows, ch, trees, live = [], {}, {}, []
    for p in plan["prerequisites"]:
        row = {"id": p["id"], "commit": p["commit"], "ancestor_of_head": False, "changed_files": 0}
        if not exists(repo, p["commit"]):
            fail({"code": "UNKNOWN_COMMIT", "id": p["id"], "detail": p["commit"]})
        elif not ancestor(p["commit"], head):
            fail({"code": "PREREQUISITE_NOT_INTEGRATED", "id": p["id"], "detail": "%s is not an ancestor of HEAD" % p["commit"][:12]})
        else:
            row["ancestor_of_head"] = True
            if exists(repo, base):
                ch[p["id"]] = changed(repo, base, p["commit"])
                trees[p["id"]] = tree(repo, p["commit"])
                row["changed_files"] = len(ch[p["id"]])
                live.append(p)
        if acc is None:
            row["acceptance"] = "UNKNOWN"
        else:
            recs = acc.get(p["id"], [])
            hit = [r for r in recs if r.get("commit") == p["commit"]]
            if hit:
                row["acceptance"] = "ACCEPTED"
                row["acceptance_record"] = hit[0]["_file"]
            elif recs:
                row["acceptance"] = "ACCEPTED_OTHER_REVISION"
                other = recs[0].get("commit")
                row["accepted_commit"] = other
                if isinstance(other, str) and SHA_RE.match(other) and exists(repo, other) and ancestor(other, p["commit"]):
                    row["note"] = "descends from the accepted commit; acceptance does not carry to a changed candidate"
            else:
                row["acceptance"] = "CANDIDATE"
        pre_rows.append(row)
    drift, overlaps = [], []
    if live and exists(repo, base) and ancestor(base, head):
        head_files = tree(repo, "HEAD")
        union = set().union(*(ch[p["id"]] for p in live))
        for f in sorted(union):
            owners = [p for p in live if f in ch[p["id"]]]
            latest = [p for p in owners if not any(q is not p and f in ch[q["id"]] and p["commit"] != q["commit"]
                                                   and ancestor(p["commit"], q["commit"]) for q in owners)]
            want = {}
            for p in latest:
                want.setdefault(trees[p["id"]].get(f), []).append(p["id"])
            got = head_files.get(f)
            if len(want) > 1:
                if f in plan["resolved_overlaps"]:
                    notes.append({"code": "RESOLVED_OVERLAP", "path": f, "ids": sorted(sum(want.values(), [])),
                                  "reason": plan["resolved_overlaps"][f]})
                else:
                    overlaps.append(f)
                    fail({"code": "OVERLAP", "id": "+".join(sorted(sum(want.values(), []))), "detail": f})
                continue
            exp = next(iter(want))
            if got != exp:
                drift.append(f)
                fail({"code": "DRIFT", "id": ",".join(next(iter(want.values()))),
                      "detail": "%s %s at HEAD" % (f, "missing" if got is None else "differs from the candidate")})
        own = sorted(changed(repo, base, "HEAD") - union)
        for f in own:
            if not matches(f, plan["writable"]):
                fail({"code": "OUT_OF_SCOPE", "id": plan["goal"], "detail": f})
        own_count = len(own)
    else:
        own_count = None
    ext_rows = []
    for e in plan["external"]:
        row = {"id": e["id"], "source_commit": e["source_commit"], "consumes": e["consumes"], "reply_url": e["reply_url"]}
        if acc is None:
            row["acceptance"] = "UNKNOWN"
            fail({"code": "EXTERNAL_UNVERIFIED", "id": e["id"], "detail": "no acceptance file given; an outside contribution has no other binding here"})
        else:
            recs = acc.get(e["id"], [])
            if not recs:
                row["acceptance"] = "CANDIDATE"
                fail({"code": "EXTERNAL_NOT_ACCEPTED", "id": e["id"], "detail": "no acceptance record"})
            else:
                r = recs[0]
                bad = [k for k in ("source_commit", "reply_sha256", "validation_manifest_sha256") if r.get(k) != e[k]]
                if r.get("reply") is not None and r.get("reply") != e["reply_url"]:
                    bad.append("reply")
                row["acceptance"] = "ACCEPTED" if not bad else "ACCEPTED_OTHER_REVISION"
                row["acceptance_record"] = r["_file"]
                if bad:
                    fail({"code": "EXTERNAL_BINDING_MISMATCH", "id": e["id"], "detail": "plan and acceptance record differ on " + ", ".join(bad)})
        if e["id"] in replies:
            rd, _ = load_json(replies[e["id"]], "--reply %s" % e["id"], 16 << 20)
            body = rd.get("body") if isinstance(rd, dict) else None
            if not isinstance(body, str):
                raise Invalid("--reply %s: expected a comment readback with a body" % e["id"])
            h = hashlib.sha256(body.encode("utf-8")).hexdigest()
            row["reply_verified"] = h == e["reply_sha256"]
            if h != e["reply_sha256"]:
                fail({"code": "REPLY_HASH_MISMATCH", "id": e["id"], "detail": "readback body sha256 %s" % h[:16]})
            url = rd.get("html_url")
            if isinstance(url, str) and url != e["reply_url"]:
                row["reply_verified"] = False
                fail({"code": "REPLY_URL_MISMATCH", "id": e["id"], "detail": url[:120]})
        else:
            not_run.append({"external": e["id"], "reason": "reply body not supplied; only its recorded hash is compared"})
        mk = e["validation_id"] if e["validation_id"] in manifests else e["id"]
        if mk in manifests:
            h = sha256_file(manifests[mk])
            row["validation_manifest_verified"] = h == e["validation_manifest_sha256"]
            if h != e["validation_manifest_sha256"]:
                fail({"code": "VALIDATION_MANIFEST_MISMATCH", "id": mk, "detail": "file sha256 %s" % h[:16]})
        else:
            not_run.append({"external": e["id"], "reason": "validation manifest not supplied; only its recorded hash is compared"})
        ext_rows.append(row)
    runs = []
    py = a.python or sys.executable
    if a.run != "none":
        for p in plan["prerequisites"]:
            for m in p["tests"]:
                runs.append(run_one("test", p["id"], [py, "-m", "unittest", m], repo, a.timeout))
            for c in p["commands"]:
                runs.append(run_one("command", p["id"], [py] + c, repo, a.timeout))
        for c in plan["cross_checks"]:
            runs.append(run_one("cross_check", plan["goal"], [py] + c, repo, a.timeout))
        if a.run == "all":
            runs += gate_runs(py, repo, a.timeout, set(a.skip_gate or []), findings, not_run)
        else:
            not_run.append({"gate": "repository gates", "reason": "--run tests"})
        for r in runs:
            if r["rc"] != 0:
                fail({"code": "TIMEOUT" if r["rc"] is None else "RUN_FAILED", "id": r["id"],
                      "detail": "%s %s rc=%s" % (r["kind"], " ".join(r["argv"])[:120], r["rc"])})
        d1 = dirty(repo)
        if d1 != d0:
            fail({"code": "RUN_CHANGED_TREE", "id": plan["goal"], "detail": "runs left %d changed path(s), first %s" % (len(d1), (sorted(set(d1) - set(d0)) or d1)[0][:120])})
    else:
        not_run.append({"runs": "all", "reason": "--run none"})
    verdict = "NOT_INTEGRATED" if findings else "INTEGRATED"
    return {"schema": REPORT_SCHEMA, "goal": plan["goal"], "verdict": verdict, "head": head, "head_tree": head_tree,
            "base": base, "plan_sha256": hashlib.sha256(raw).hexdigest(), "run_mode": a.run,
            "interpreter": "%d.%d.%d" % sys.version_info[:3] if not a.python else os.path.basename(a.python),
            "prerequisites": pre_rows, "external": ext_rows, "integration_files": own_count,
            "drift": drift, "overlaps": overlaps, "runs": runs, "findings": findings, "notes": notes,
            "not_run": not_run, "read_only": True}


def text(rep):
    out = ["daily integration %s at %s (tree %s)" % (rep["goal"], rep["head"][:12], rep["head_tree"][:12])]
    for p in rep["prerequisites"]:
        out.append("  %s %s %s%s" % (p["id"], p["commit"][:12], p["acceptance"],
                                    "" if p["ancestor_of_head"] else " NOT IN HEAD"))
    for e in rep["external"]:
        out.append("  %s external %s %s" % (e["id"], (e["source_commit"] or "no code commit")[:12], e["acceptance"]))
    for r in rep["runs"]:
        out.append("  run %s %s %s rc=%s %ss" % (r["kind"], r["id"], " ".join(r["argv"])[:70], r["rc"], r["seconds"]))
    for n in rep["not_run"]:
        out.append("  not run: %s" % "; ".join("%s=%s" % kv for kv in sorted(n.items())))
    for f in rep["findings"]:
        out.append("  FINDING %s %s: %s" % (f["code"], f["id"], f["detail"]))
    out.append("VERDICT %s" % rep["verdict"])
    return "\n".join(out) + "\n"


def write_atomic(path, data):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".di-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description="Daily integration evidence matrix (read-only).")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check")
    c.add_argument("--plan", required=True)
    c.add_argument("--repo", default=".")
    c.add_argument("--acceptance", action="append")
    c.add_argument("--reply", action="append")
    c.add_argument("--manifest", action="append")
    c.add_argument("--run", choices=("none", "tests", "all"), default="none")
    c.add_argument("--skip-gate", action="append")
    c.add_argument("--python")
    c.add_argument("--timeout", type=float, default=600.0)
    c.add_argument("--json", action="store_true")
    c.add_argument("--out")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if a.cmd != "check":
        ap.print_usage(sys.stderr)
        return 2
    try:
        if a.timeout <= 0 or a.timeout > 3600:
            raise Invalid("--timeout: between 0 and 3600 seconds")
        rep = check(a)
    except Invalid as exc:
        sys.stderr.write("invalid input: %s\nVERDICT INVALID_INPUT\n" % exc)
        return 2
    except RuntimeError as exc:
        sys.stderr.write("invalid input: %s\nVERDICT INVALID_INPUT\n" % str(exc)[:300])
        return 2
    body = json.dumps(rep, indent=1, sort_keys=True) + "\n" if a.json else text(rep)
    if a.out:
        write_atomic(a.out, json.dumps(rep, indent=1, sort_keys=True) + "\n")
    sys.stdout.write(body)
    return 0 if rep["verdict"] == "INTEGRATED" else 1


if __name__ == "__main__":
    sys.exit(main())
