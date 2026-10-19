#!/usr/bin/env python3
"""Oracle for daily_integration.py: builds its own throwaway git repositories with known stacking
defects and checks the JSON matrix a candidate writes for each. Exit 0 alone proves nothing.

  python3 daily_integration_oracle.py -- PYTHON daily_integration.py      # ACCEPTED 13/13
  python3 daily_integration_oracle.py -- PYTHON daily_integration_controls/naive.py   # REJECTED
  python3 daily_integration_oracle.py -- PYTHON daily_integration_controls/noop.py    # REJECTED

o1 clean control; o2 a merge that reverted a candidate file (drift); o3 a named candidate never
merged; o4 two candidates disagree about one file (overlap) and an explicit resolution; o5 an
integration change outside the writable globs; o6 uncommitted and untracked work; o7 a candidate's
test broken by another candidate, and a test that rewrites a tracked file; o8 acceptance only at the
exact commit (another revision does not carry, a descendant is named as such); o9 outside
contributions bound to their acceptance record and reply readback; o10 invalid input exits 2 and
keeps the previous report, then recovery; o11 a subfolder is refused and reruns are byte-identical;
o12 a hung command times out; o13 a later candidate that changes an earlier one's file.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

GENV = None


def sh(repo, *args):
    r = subprocess.run(["git", "-C", repo] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=GENV)
    if r.returncode:
        raise RuntimeError("git %s failed: %s" % (" ".join(args[:2]), r.stderr.decode()[-200:]))
    return r.stdout.decode().strip()


def write(repo, rel, text):
    p = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write(text)


def commit(repo, msg):
    sh(repo, "add", "-A")
    sh(repo, "commit", "-q", "-m", msg)
    return sh(repo, "rev-parse", "HEAD")


TEST_OK = "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n"


def test_reads(rel, needle):
    return ("import os, unittest\nROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n"
            "class T(unittest.TestCase):\n    def test_content(self):\n"
            "        self.assertIn(%r, open(os.path.join(ROOT, %r)).read())\n" % (needle, rel))


def build(tmp, overlap=False, breaking=False, rewriting=False):
    """base -> A (alpha), base -> B (beta), base -> C (never merged); integration merges A and B."""
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    sh(repo, "init", "-q", "-b", "main")
    write(repo, "README.md", "base\n")
    write(repo, "shared.txt", "one\n")
    write(repo, "tests/__init__.py", "")
    write(repo, "tests/test_base.py", TEST_OK)
    base = commit(repo, "base")
    sh(repo, "checkout", "-q", "-b", "a", base)
    write(repo, "alpha/tool.py", "VALUE = 'alpha-v1'\n")
    write(repo, "tests/test_alpha.py", test_reads("alpha/tool.py", "alpha-v1"))
    if overlap:
        write(repo, "shared.txt", "one\nfrom A\n")
    a = commit(repo, "A")
    sh(repo, "checkout", "-q", "-b", "b", base)
    write(repo, "beta/tool.py", "VALUE = 'beta-v1'\n")
    write(repo, "tests/test_beta.py", test_reads("README.md", "base") if not breaking else test_reads("README.md", "base"))
    if rewriting:
        write(repo, "tests/test_beta.py", "import os, unittest\nROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n"
              "class T(unittest.TestCase):\n    def test_w(self):\n        open(os.path.join(ROOT, 'beta/tool.py'), 'a').write('#x\\n')\n")
    if overlap:
        write(repo, "shared.txt", "one\nfrom B\n")
    b = commit(repo, "B")
    sh(repo, "checkout", "-q", "-b", "c", base)
    write(repo, "gamma/tool.py", "VALUE = 'gamma'\n")
    c = commit(repo, "C")
    sh(repo, "checkout", "-q", "-b", "integ", a)
    if overlap:
        r = subprocess.run(["git", "-C", repo, "merge", "-q", "--no-ff", "-m", "merge B", b], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=GENV)
        write(repo, "shared.txt", "one\nfrom A\nfrom B\n")
        sh(repo, "add", "-A")
        sh(repo, "commit", "-q", "--no-edit")
    else:
        sh(repo, "merge", "-q", "--no-ff", "-m", "merge B", b)
    if breaking:
        write(repo, "alpha/tool.py", "VALUE = 'alpha-v1'\n")
        write(repo, "README.md", "rewritten by A's follow-up\n")  # breaks B's test; README is nobody's candidate file
    write(repo, "integ/report.md", "integration\n")
    head = commit(repo, "integration")
    return repo, {"base": base, "a": a, "b": b, "c": c, "head": head}


def plan(revs, extra=None, **kw):
    p = {"schema": "solaris.daily-integration/1", "goal": "G99", "base": revs["base"],
         "writable": ["integ/**", "README.md"] if kw.pop("readme_ok", False) else ["integ/**"],
         "prerequisites": [{"id": "G91", "commit": revs["a"], "tests": ["tests.test_alpha"]},
                           {"id": "G92", "commit": revs["b"], "tests": ["tests.test_beta"]}]}
    if extra:
        p.update(extra)
    return p


class Ctx:
    def __init__(self, cmd):
        self.cmd = cmd
        self.tmp = tempfile.mkdtemp(prefix="dio-")

    def run(self, repo, planobj, args=(), raw=None):
        pf = os.path.join(self.tmp, "plan-%d.json" % len(os.listdir(self.tmp)))
        with open(pf, "w") as fh:
            fh.write(raw if raw is not None else json.dumps(planobj))
        argv = self.cmd + ["check", "--plan", pf, "--repo", repo, "--json"] + list(args)
        r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, env=GENV)
        try:
            doc = json.loads(r.stdout.decode())
        except ValueError:
            doc = None
        return r.returncode, doc, r.stdout, r.stderr.decode("utf-8", "replace")

    def fresh(self, **kw):
        d = tempfile.mkdtemp(dir=self.tmp)
        return build(d, **kw)


def codes(doc):
    return sorted(f.get("code") for f in (doc or {}).get("findings", []))


def acc_file(ctx, entries):
    p = os.path.join(ctx.tmp, "acc-%d.json" % len(os.listdir(ctx.tmp)))
    with open(p, "w") as fh:
        json.dump({"entries": entries}, fh)
    return p


def o1(ctx):
    repo, r = ctx.fresh()
    rc, doc, _, _ = ctx.run(repo, plan(r), ["--run", "tests"])
    ok = rc == 0 and doc and doc["verdict"] == "INTEGRATED" and doc["head"] == r["head"] and not doc["findings"]
    runs = (doc or {}).get("runs", [])
    ok = ok and len([x for x in runs if x.get("kind") == "test" and x.get("rc") == 0]) == 2
    ok = ok and [p["acceptance"] for p in doc["prerequisites"]] == ["UNKNOWN", "UNKNOWN"]
    return ok, "clean control rc=%s %s" % (rc, codes(doc))


def o2(ctx):
    repo, r = ctx.fresh()
    write(repo, "beta/tool.py", "VALUE = 'beta-v0'\n")  # a bad conflict resolution reverted B's file; A's test still passes
    commit(repo, "fixup")
    rc, doc, _, _ = ctx.run(repo, plan(r), ["--run", "tests"])
    d = [f for f in (doc or {}).get("findings", []) if f.get("code") == "DRIFT"]
    ok = rc == 1 and doc and doc["verdict"] == "NOT_INTEGRATED" and len(d) == 1 and "beta/tool.py" in d[0]["detail"] and d[0]["id"] == "G92"
    os.remove(os.path.join(repo, "alpha/tool.py"))
    commit(repo, "lost")
    rc2, doc2, _, _ = ctx.run(repo, plan(r))
    d2 = [f for f in (doc2 or {}).get("findings", []) if f.get("code") == "DRIFT" and "alpha/tool.py" in f.get("detail", "")]
    return ok and rc2 == 1 and len(d2) == 1 and "missing" in d2[0]["detail"], "drift %s / %s" % (codes(doc), codes(doc2))


def o3(ctx):
    repo, r = ctx.fresh()
    p = plan(r)
    p["prerequisites"].append({"id": "G93", "commit": r["c"], "tests": []})
    rc, doc, _, _ = ctx.run(repo, p)
    ok = rc == 1 and "PREREQUISITE_NOT_INTEGRATED" in codes(doc)
    p["prerequisites"][2]["commit"] = "0" * 40
    rc2, doc2, _, _ = ctx.run(repo, p)
    return ok and rc2 == 1 and "UNKNOWN_COMMIT" in codes(doc2), "unmerged %s / unknown %s" % (codes(doc), codes(doc2))


def o4(ctx):
    repo, r = ctx.fresh(overlap=True)
    rc, doc, _, _ = ctx.run(repo, plan(r))
    ok = rc == 1 and codes(doc) == ["OVERLAP"] and "shared.txt" in doc["findings"][0]["detail"]
    p = plan(r, {"resolved_overlaps": [{"path": "shared.txt", "reason": "both lines kept"}]})
    rc2, doc2, _, _ = ctx.run(repo, p)
    ok2 = rc2 == 0 and doc2 and doc2["verdict"] == "INTEGRATED" and any(n.get("code") == "RESOLVED_OVERLAP" for n in doc2.get("notes", []))
    return ok and ok2, "overlap %s / resolved rc=%s" % (codes(doc), rc2)


def o5(ctx):
    repo, r = ctx.fresh()
    write(repo, "docs/extra.md", "outside\n")
    commit(repo, "scope")
    rc, doc, _, _ = ctx.run(repo, plan(r))
    ok = rc == 1 and codes(doc) == ["OUT_OF_SCOPE"] and "docs/extra.md" in doc["findings"][0]["detail"]
    return ok, "scope %s" % codes(doc)


def o6(ctx):
    repo, r = ctx.fresh()
    write(repo, "integ/report.md", "edited, not committed\n")
    rc, doc, _, _ = ctx.run(repo, plan(r))
    sh(repo, "checkout", "-q", "--", "integ/report.md")
    write(repo, "integ/new.md", "untracked\n")
    rc2, doc2, _, _ = ctx.run(repo, plan(r))
    return rc == 1 and "DIRTY_TREE" in codes(doc) and rc2 == 1 and "DIRTY_TREE" in codes(doc2), "dirty %s / untracked %s" % (codes(doc), codes(doc2))


def o7(ctx):
    repo, r = ctx.fresh(breaking=False)
    write(repo, "README.md", "changed by the integration\n")
    commit(repo, "readme")
    rc, doc, _, _ = ctx.run(repo, plan(r, readme_ok=True), ["--run", "tests"])
    bad = [f for f in (doc or {}).get("findings", []) if f.get("code") == "RUN_FAILED"]
    ok = rc == 1 and len(bad) == 1 and bad[0]["id"] == "G92"
    repo2, r2 = ctx.fresh(rewriting=True)
    rc2, doc2, _, _ = ctx.run(repo2, plan(r2), ["--run", "tests"])
    return ok and rc2 == 1 and "RUN_CHANGED_TREE" in codes(doc2), "broken %s / rewriting %s" % (codes(doc), codes(doc2))


def o8(ctx):
    repo, r = ctx.fresh()
    sh(repo, "checkout", "-q", "a")
    write(repo, "alpha/tool.py", "VALUE = 'alpha-v1'\n# repaired\n")
    write(repo, "tests/test_alpha.py", test_reads("alpha/tool.py", "alpha-v1"))
    a2 = commit(repo, "A r2")
    sh(repo, "checkout", "-q", "integ")
    sh(repo, "merge", "-q", "--no-ff", "-m", "merge A r2", a2)
    p = plan(r)
    p["prerequisites"][0]["commit"] = a2
    acc = acc_file(ctx, [{"id": "G91", "commit": r["a"]}, {"id": "G92", "commit": r["b"]}])
    rc, doc, _, _ = ctx.run(repo, p, ["--acceptance", acc])
    st = {x["id"]: x for x in (doc or {}).get("prerequisites", [])}
    ok = rc == 0 and st.get("G92", {}).get("acceptance") == "ACCEPTED" and st.get("G91", {}).get("acceptance") == "ACCEPTED_OTHER_REVISION"
    ok = ok and "descends" in st.get("G91", {}).get("note", "") and st["G91"].get("accepted_commit") == r["a"]
    acc2 = acc_file(ctx, [{"id": "G92", "commit": r["b"]}])
    rc2, doc2, _, _ = ctx.run(repo, p, ["--acceptance", acc2])
    st2 = {x["id"]: x for x in (doc2 or {}).get("prerequisites", [])}
    return ok and st2.get("G91", {}).get("acceptance") == "CANDIDATE", "acceptance %s" % {k: v.get("acceptance") for k, v in st.items()}


def o9(ctx):
    repo, r = ctx.fresh()
    body = "Follow-up: narrowed rule, both counterexamples still fail.\n"
    bh = hashlib.sha256(body.encode()).hexdigest()
    man = os.path.join(ctx.tmp, "R95.sha256")
    with open(man, "w") as fh:
        fh.write("abc  file\n")
    mh = hashlib.sha256(open(man, "rb").read()).hexdigest()
    url = "https://example.invalid/pr/1#issuecomment-1"
    ext = {"id": "P95", "source_commit": None, "reply_url": url, "reply_sha256": bh, "validation_id": "R95", "validation_manifest_sha256": mh}
    reply = os.path.join(ctx.tmp, "reply.json")
    with open(reply, "w") as fh:
        json.dump({"html_url": url, "body": body}, fh)
    acc = acc_file(ctx, [{"id": "P95", "source_commit": None, "reply": url, "reply_sha256": bh, "validation_manifest_sha256": mh}])
    p = plan(r, {"external": [ext]})
    rc, doc, _, _ = ctx.run(repo, p, ["--acceptance", acc, "--reply", "P95=" + reply, "--manifest", "R95=" + man])
    e = ((doc or {}).get("external") or [{}])[0]
    ok = rc == 0 and e.get("acceptance") == "ACCEPTED" and e.get("reply_verified") is True and e.get("validation_manifest_verified") is True
    with open(reply, "w") as fh:
        json.dump({"html_url": url, "body": body + "edited"}, fh)
    rc2, doc2, _, _ = ctx.run(repo, p, ["--acceptance", acc, "--reply", "P95=" + reply])
    acc3 = acc_file(ctx, [{"id": "P95", "source_commit": "1" * 40, "reply": url, "reply_sha256": bh, "validation_manifest_sha256": mh}])
    rc3, doc3, _, _ = ctx.run(repo, p, ["--acceptance", acc3])
    rc4, doc4, _, _ = ctx.run(repo, p)
    ok = ok and rc2 == 1 and "REPLY_HASH_MISMATCH" in codes(doc2) and rc3 == 1 and "EXTERNAL_BINDING_MISMATCH" in codes(doc3)
    ok = ok and rc4 == 1 and "EXTERNAL_UNVERIFIED" in codes(doc4)
    return ok, "external rc=%s tampered %s record %s none %s" % (rc, codes(doc2), codes(doc3), codes(doc4))


def o10(ctx):
    repo, r = ctx.fresh()
    out = os.path.join(ctx.tmp, "report.json")
    with open(out, "w") as fh:
        fh.write("previous\n")
    good = plan(r)
    bads = ['{"schema": "solaris.daily-integration/1", "schema": "x"}', "not json", json.dumps(dict(good, base="abc")),
            json.dumps(dict(good, prerequisites=[{"id": "G91", "commit": r["a"], "commands": [["../escape.py"]]}])),
            json.dumps(dict(good, surprise=1)), json.dumps(dict(good, prerequisites=[])),
            json.dumps(dict(good, prerequisites=[{"id": "G91", "commit": r["a"]}, {"id": "G91", "commit": r["b"]}]))]
    rcs = []
    for b in bads:
        rc, doc, so, se = ctx.run(repo, None, ["--out", out], raw=b)
        rcs.append(rc == 2 and "Traceback" not in se and open(out).read() == "previous\n")
    rc, _, _, se = ctx.run(os.path.join(ctx.tmp, "nowhere"), good, ["--out", out])
    rcs.append(rc == 2 and "Traceback" not in se and open(out).read() == "previous\n")
    rc, doc, _, _ = ctx.run(repo, good, ["--out", out])
    try:
        rec = json.load(open(out)).get("verdict") == "INTEGRATED"
    except ValueError:
        rec = False
    return all(rcs) and rc == 0 and rec, "invalid %s recovery rc=%s" % (rcs, rc)


def o11(ctx):
    repo, r = ctx.fresh()
    rc, _, _, se = ctx.run(os.path.join(repo, "alpha"), plan(r))
    _, _, a, _ = ctx.run(repo, plan(r))
    _, _, b, _ = ctx.run(repo, plan(r))
    return rc == 2 and "Traceback" not in se and a == b and a, "subfolder rc=%s identical %s" % (rc, a == b)


def o12(ctx):
    repo, r = ctx.fresh()
    write(repo, "integ/hang.py", "import time\ntime.sleep(30)\n")
    commit(repo, "hang")
    p = plan(r, {"cross_checks": [["integ/hang.py"]]})
    rc, doc, _, _ = ctx.run(repo, p, ["--run", "tests", "--timeout", "2"])
    return rc == 1 and "TIMEOUT" in codes(doc), "hang %s" % codes(doc)


def o13(ctx):
    repo, r = ctx.fresh()
    sh(repo, "checkout", "-q", "-b", "a2", r["a"])
    write(repo, "alpha/tool.py", "VALUE = 'alpha-v1'\n# second goal builds on the first\n")
    a2 = commit(repo, "A2 on A")
    sh(repo, "checkout", "-q", "integ")
    sh(repo, "merge", "-q", "--no-ff", "-m", "merge A2", a2)
    p = plan(r)
    p["prerequisites"].append({"id": "G94", "commit": a2, "tests": []})
    rc, doc, _, _ = ctx.run(repo, p)
    ok = rc == 0 and doc and not doc["findings"]
    write(repo, "alpha/tool.py", "VALUE = 'alpha-v1'\n")
    commit(repo, "back to the first goal's version")
    rc2, doc2, _, _ = ctx.run(repo, p)
    d = [f for f in (doc2 or {}).get("findings", []) if f.get("code") == "DRIFT"]
    return ok and rc2 == 1 and len(d) == 1 and d[0]["id"] == "G94", "descendant rc=%s / reverted %s" % (rc, codes(doc2))


CHECKS = [o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12, o13]


def main(argv):
    global GENV
    if "--" not in argv or argv.index("--") == len(argv) - 1:
        sys.stderr.write(__doc__)
        return 2
    cmd = argv[argv.index("--") + 1:]
    home = tempfile.mkdtemp(prefix="dio-home-")
    who = "oracle" + chr(64) + "example.invalid"  # throwaway identity for the throwaway repositories
    GENV = dict(os.environ, HOME=home, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="Oracle", GIT_COMMITTER_NAME="Oracle",
                GIT_AUTHOR_EMAIL=who, GIT_COMMITTER_EMAIL=who, PYTHONDONTWRITEBYTECODE="1")
    GENV.pop("GIT_DIR", None)
    ctx = Ctx(cmd)
    passed = 0
    try:
        for fn in CHECKS:
            try:
                ok, msg = fn(ctx)
            except Exception as exc:  # a crashing candidate fails the check, never the oracle
                ok, msg = False, "error %s: %s" % (exc.__class__.__name__, str(exc)[:160])
            passed += bool(ok)
            print("%s %s %s" % ("PASS" if ok else "FAIL", fn.__name__, msg))
    finally:
        shutil.rmtree(ctx.tmp, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)
    verdict = "ACCEPTED" if passed == len(CHECKS) else "REJECTED"
    print("%s %d/%d" % (verdict, passed, len(CHECKS)))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
