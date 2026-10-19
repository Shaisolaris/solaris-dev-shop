#!/usr/bin/env python3
"""G38 oracle: license/authority consistency and a synthetic immutable-event log, on the fixture, on the
actual repository, on generated failure cases and on seeded unseen chains.
Usage: authority_oracle.py [--tools DIR] [--seed N]. DIR holds provenance_check.py and event_chain.py
(default: the real ones). Prints ACCEPTED n/n or REJECTED k/n. Expectations are computed here with hashlib."""
import argparse, hashlib, json, os, random, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIX = HERE / "fixtures"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
G = "0" * 64


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def ehash(e):
    return hashlib.sha256(canon({k: e[k] for k in ("seq", "prev", "at", "claimed_by", "body")}).encode()).hexdigest()


def chain(n, rng):
    out, prev = [], G
    for i in range(n):
        e = {"seq": i, "prev": prev, "at": "2026-10-%02dT%02d:%02d:00-07:00" % (1 + i // 300, (i // 60) % 5 + 8, i % 60),
             "claimed_by": rng.choice(["Release desk (synthetic)", "Build bot (synthetic)", "Ana (synthetic)"]),
             "body": {"event": "artifact_recorded", "n": i, "sha256": hashlib.sha256(b"a%d" % i).hexdigest()}}
        e["hash"] = ehash(e); prev = e["hash"]; out.append(e)
    return out


def dump(evs):
    return "".join(canon(e) + "\n" for e in evs).encode()


class C:
    def __init__(self, tools):
        self.pc, self.ec = Path(tools) / "provenance_check.py", Path(tools) / "event_chain.py"
        self.tmp = Path(tempfile.mkdtemp(prefix="g38-oracle-")); self.n = 0

    def dir(self):
        self.n += 1; d = self.tmp / ("w%d" % self.n); d.mkdir(); return d

    def repo(self):
        d = self.dir() / "repo"; shutil.copytree(str(FIX / "repo-clean"), str(d)); return d

    def run(self, tool, *a):
        if not tool.is_file():
            return 127, None, ""
        r = subprocess.run([sys.executable, str(tool)] + [str(x) for x in a], capture_output=True, text=True, env=ENV, timeout=300)
        try:
            j = json.loads(r.stdout)
        except ValueError:
            j = None
        return r.returncode, j, r.stdout + r.stderr

    def check(self, d, *a):
        return self.run(self.pc, "check", d, "--json", *a)

    def verify(self, log, *a):
        return self.run(self.ec, "verify", log, "--json", *a)


def codes(j):
    return sorted((f["code"], f.get("path", f.get("at", ""))) for f in (j or {}).get("findings", []))


def p1(c):
    d = c.repo(); rc, j, _ = c.check(d, "--manifest", d / "MANIFEST.sha256")
    want = {l.split("  ", 1)[1]: l.split("  ", 1)[0] for l in (d / "MANIFEST.sha256").read_text().splitlines()}
    real = {k: hashlib.sha256((d / k).read_bytes()).hexdigest() for k in want}
    ok = (rc == 0 and j and j["result"] == "consistent" and j["license"] == "MIT" and j["declarations"] == 4
          and j["integrity"]["matching"] == 8 and j["integrity"]["subject"]["digests"] == real == want)
    rc2, j2, _ = c.check(ROOT, "--exclude", "examples/capabilities/G38/fixtures")
    ok = ok and rc2 == 0 and j2["result"] == "consistent" and j2["license"] == "MIT" and j2["declarations"] >= 60 \
        and list(j2["excluded"]) == ["examples/capabilities/G38/fixtures"] and len(j2["excluded"]["examples/capabilities/G38/fixtures"]) == 2
    rc3, j3, _ = c.check(ROOT)  # without the exclusion the fixture's own license files are reported, not hidden
    ok = ok and rc3 == 1 and {f["code"] for f in j3["findings"]} == {"upstream_license_unlisted"}
    return ok, "clean fixture and the actual repository (MIT, %s declarations) consistent; fixture exclusion disclosed" % (j2 or {}).get("declarations")


def p2(c):
    cases = []
    def case(name, fn, want):
        d = c.repo(); fn(d); rc, j, _ = c.check(d); cases.append((name, rc == 1 and codes(j) == sorted(want), codes(j)))
    pj = "employees/demo/report-writer/plugin.json"
    case("plugin apache", lambda d: (d / pj).write_text('{"name": "report-writer", "license": "Apache-2.0"}'), [("license_mismatch", pj)])
    case("plugin none", lambda d: (d / pj).write_text('{"name": "report-writer"}'), [("license_undeclared", pj)])
    case("pyproject gpl", lambda d: (d / "pyproject.toml").write_text('[project]\nname = "x"\nlicense = "GPL-3.0-only"\n'), [("license_mismatch", "pyproject.toml")])
    case("badge", lambda d: (d / "README.md").write_text((d / "README.md").read_text().replace("license-MIT-green", "license-Apache--2.0-blue")), [("license_mismatch", "README.md")])
    case("section", lambda d: (d / "README.md").write_text((d / "README.md").read_text().replace("## License\n\nMIT.", "## License\n\nBSD-3-Clause.")), [("license_mismatch", "README.md")])
    case("unlisted", lambda d: (d / "vendor" / "parser" / "COPYING").write_text("synthetic"), [("upstream_license_unlisted", "vendor/parser/COPYING")])
    case("notice missing", lambda d: (d / "vendor" / "parser" / "LICENSE-upstream").unlink(),
         [("notice_path_missing", "NOTICE.md")])
    case("unknown license", lambda d: (d / "LICENSE").write_text("All rights reserved. Internal use only (synthetic)."), [("license_unrecognized", "LICENSE")])
    case("apache header only", lambda d: (d / "LICENSE").write_text(
        "Apache License\nVersion 2.0, January 2004\nTERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n"),
        [("license_unrecognized", "LICENSE")])  # a header alone is not the license (M38 proposed fix)
    bad = [x for x in cases if not x[1]]
    return not bad, "%d single-cause license drifts each give exactly their finding%s" % (len(cases), "; wrong: %s" % bad[:2] if bad else "")


def p3(c):
    ok = True
    d = c.repo(); (d / "src" / "app.py").write_text((d / "src" / "app.py").read_text() + "# changed\n")
    rc, j, _ = c.check(d, "--manifest", d / "MANIFEST.sha256"); ok = ok and rc == 1 and codes(j) == [("digest_mismatch", "src/app.py")]
    d = c.repo(); (d / "vendor" / "parser" / "parse.py").unlink()
    rc, j, _ = c.check(d, "--manifest", d / "MANIFEST.sha256"); ok = ok and rc == 1 and codes(j) == [("artifact_missing", "vendor/parser/parse.py")]
    d = c.repo(); (d / "src" / "app.py").unlink(); outside = d.parent / "outside.py"; outside.write_text("x"); os.symlink(str(outside), str(d / "src" / "app.py"))
    rc, j, _ = c.check(d, "--manifest", d / "MANIFEST.sha256"); ok = ok and rc == 1 and codes(j) == [("artifact_refused", "src/app.py")]
    d = c.repo(); m = d / "MANIFEST.sha256"; m.write_text(m.read_text() + "%s  ../outside.py\n" % ("0" * 64))
    rc, j, _ = c.check(d, "--manifest", m); ok = ok and rc == 1 and codes(j) == [("artifact_refused", "../outside.py")]
    # malformed manifest: refused, an earlier --out is kept byte for byte
    d = c.repo(); out = d.parent / "report.json"
    c.run(c.pc, "check", d, "--manifest", d / "MANIFEST.sha256", "--out", out); before = out.read_bytes() if out.exists() else None
    m = d / "MANIFEST.sha256"; m.write_text("not a manifest line\n")
    rc, _, txt = c.run(c.pc, "check", d, "--manifest", m, "--out", out)
    ok = ok and rc == 2 and before is not None and out.read_bytes() == before and "Nothing was written" in txt
    return ok, "changed, missing, symlinked and escaping artifacts reported; malformed manifest refused, earlier report kept"


def e1(c):
    log = FIX / "events.jsonl"; evs = [json.loads(l) for l in log.read_text().splitlines()]
    prev, ok = G, True
    for i, e in enumerate(evs):
        ok = ok and e["seq"] == i and e["prev"] == prev and ehash(e) == e["hash"]; prev = e["hash"]
    rc, j, _ = c.verify(log, "--anchor", "2:%s" % evs[2]["hash"])
    ok = ok and rc == 0 and j and j["verified"] == len(evs) and j["head"]["hash"] == prev and j["anchor"] == "matches seq 2"
    ok = ok and j["claimed_by"]["identity"] == "claimed in plain text, not authenticated" and "authenticated" not in json.dumps(j["claimed_by"]["counts"])
    rc2, j2, _ = c.verify(log); ok = ok and rc2 == 0 and j2["anchor"].startswith("none")
    return ok, "fixture chain of %d events verifies against an independent recompute; anchor matched; signer only claimed" % len(evs)


def e2(c, seed):
    rng = random.Random(seed); bad = []; n_cases = 0
    for k in range(4):
        evs = chain(rng.randint(40, 400), rng); n = len(evs); i = rng.randint(1, n - 2)
        anc = "%d:%s" % (n - 1, evs[-1]["hash"])
        def run(raw, *a):
            d = c.dir(); p = d / "log.jsonl"; p.write_bytes(raw); return c.verify(p, *a)
        t = json.loads(json.dumps(evs)); t[i]["body"]["n"] = -1
        exp = [("edit body", run(dump(t)), [("hash_mismatch", "line %d" % (i + 1))], i)]
        t = evs[:i] + evs[i + 1:]; exp.append(("delete", run(dump(t)), [("seq_gap", "line %d" % (i + 1))], i))
        t = evs[:i] + [evs[i + 1], evs[i]] + evs[i + 2:]; exp.append(("swap", run(dump(t)), [("seq_gap", "line %d" % (i + 1))], i))
        t = evs[:i + 1] + [evs[i]] + evs[i + 1:]; exp.append(("replay", run(dump(t)), [("seq_repeat", "line %d" % (i + 2))], i + 1))
        raw = dump(evs); exp.append(("torn tail", run(raw[:-7]), [("torn_tail", "line %d" % n)], n - 1))
        # full rewrite from i on with recomputed hashes: self-consistent, caught only by the anchor
        t = json.loads(json.dumps(evs)); t[i]["body"]["n"] = -2; prev = t[i - 1]["hash"]
        for e in t[i:]:
            e["prev"] = prev; e["hash"] = ehash(e); prev = e["hash"]
        r_self = run(dump(t)); r_anc = run(dump(t), "--anchor", anc)
        exp.append(("rewrite no anchor", r_self, [], n)); exp.append(("rewrite anchored", r_anc, [("anchor_mismatch", "")], n))
        exp.append(("truncate anchored", run(dump(evs[:i]), "--anchor", anc), [("anchor_not_reached", "")], i))
        for name, (rc, j, _), want, nver in exp:
            n_cases += 1
            good = j is not None and codes(j) == want and j["verified"] == nver and rc == (0 if not want else 1)
            if not good:
                bad.append((name, rc, codes(j)[:2], j and j["verified"], nver))
    return not bad, "%d tamper cases on 4 seeded chains: each named at its line, nothing after a break trusted%s" % (n_cases, "; wrong: %s" % bad[:2] if bad else "")


def e3(c):
    rng = random.Random(7); evs = chain(30, rng); d = c.dir(); log = d / "log.jsonl"
    t = json.loads(json.dumps(evs)); t[20]["body"]["n"] = 99; raw = dump(t) + b'{"seq": 30, "torn'; log.write_bytes(raw)
    out = d / "recovered.jsonl"
    rc, j, _ = c.run(c.ec, "recover", log, "--out", out, "--json")
    ok = rc == 0 and out.is_file() and out.read_bytes() == dump(evs[:20]) and log.read_bytes() == raw and j["recovered"]["kept"] == 20
    rc2, _, _ = c.run(c.ec, "recover", log, "--out", log); rc3, _, _ = c.run(c.ec, "recover", log, "--out", out)
    ok = ok and rc2 == 2 and rc3 == 2 and log.read_bytes() == raw
    rc4, _, _ = c.run(c.ec, "append", log, "--claimed-by", "x", "--body", "{}", "--at", "2026-10-02T00:00:00-07:00")
    ok = ok and rc4 == 2 and log.read_bytes() == raw
    rc5, _, _ = c.run(c.ec, "append", out, "--claimed-by", "Release desk (synthetic)", "--body", '{"event":"resumed"}', "--at", "2026-10-02T00:00:00-07:00")
    rc6, j6, _ = c.verify(out); ok = ok and rc5 == 0 and rc6 == 0 and j6["verified"] == 21 and j6["head"]["seq"] == 20
    t2 = json.loads(json.dumps(evs)); t2[5]["body"]["n"] = -5; prev = t2[4]["hash"]
    for e in t2[5:]:
        e["prev"] = prev; e["hash"] = ehash(e); prev = e["hash"]
    log2 = d / "rewritten.jsonl"; log2.write_bytes(dump(t2)); out2 = d / "r2.jsonl"
    rc7, _, _ = c.run(c.ec, "recover", log2, "--out", out2, "--anchor", "10:%s" % evs[10]["hash"])
    ok = ok and rc7 == 1 and not out2.exists()
    return ok, "recover keeps the 20 verified events in a new file, original untouched, in-place and overwrite refused; broken log refuses append; rewritten history under an anchor recovers nothing"


def e4(c):
    d = c.dir(); log = d / "log.jsonl"; procs = []
    for w in range(8):
        script = ("import subprocess,sys\nfor i in range(25):\n    r=subprocess.run([sys.executable,%r,'append',%r,'--claimed-by','worker %d (synthetic)','--body','{\"i\":%%d}'%%i])\n"
                  "    sys.exit(r.returncode) if r.returncode else None\n") % (str(c.ec), str(log), w)
        procs.append(subprocess.Popen([sys.executable, "-c", script], env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    rcs = [p.wait(timeout=600) for p in procs]
    rc, j, _ = c.verify(log)
    lines = log.read_text().splitlines() if log.exists() else []
    ok = all(r == 0 for r in rcs) and rc == 0 and j["verified"] == 200 and len(lines) == 200
    ok = ok and sorted(j["claimed_by"]["counts"].values()) == [25] * 8
    return ok, "8 concurrent appenders x 25 events: %s verified, no lost or forked write" % ((j or {}).get("verified"))


def s1(c):
    bad = []
    for t in (c.pc, c.ec):
        src = t.read_text() if t.is_file() else ""
        bad += [w for w in ("urllib", "http.client", "import socket", "smtplib", "import subprocess", "os.system", "web3", "eth_") if w in src]
        if not src:
            bad.append("missing " + t.name)
    return not bad, "no network, process, wallet or chain library use in either tool%s" % (": " + ", ".join(bad) if bad else "")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tools"); ap.add_argument("--seed", type=int, default=38)
    a = ap.parse_args()
    tools = Path(a.tools).resolve() if a.tools else None
    c = C(tools) if tools else C(ROOT / "employees" / "quality-security" / "security-auditor")
    if not tools:
        c.ec = ROOT / "employees" / "engineering" / "blockchain-developer" / "event_chain.py"
    before = {p: p.read_bytes() for p in FIX.rglob("*") if p.is_file()}
    checks = [("p1", p1), ("p2", p2), ("p3", p3), ("e1", e1), ("e2", lambda c: e2(c, a.seed)), ("e3", e3), ("e4", e4), ("s1", s1)]
    passed = 0
    for nm, fn in checks:
        try:
            ok, msg = fn(c)
        except Exception as ex:
            ok, msg = False, "error %s: %s" % (type(ex).__name__, str(ex)[:160])
        if nm == "s1":
            ok = ok and before == {p: p.read_bytes() for p in FIX.rglob("*") if p.is_file()}; msg += "; fixtures byte-identical"
        passed += bool(ok); print("%s %s %s" % ("PASS" if ok else "FAIL", nm, msg))
    shutil.rmtree(str(c.tmp), ignore_errors=True)
    print("%s %d/%d" % ("ACCEPTED" if passed == len(checks) else "REJECTED", passed, len(checks)))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
