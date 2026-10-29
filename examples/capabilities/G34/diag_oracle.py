#!/usr/bin/env python3
"""G34 oracle: runs the page diagnostic against the declared fixtures and the failure/recovery variants.

Every expectation comes from the fixture generator (each seeded defect declares its finding key) or from the
documented exit-code contract, not from the tool's own output. Works on copies in a temporary folder; the
committed fixtures are never modified. No network.

  python3 diag_oracle.py [--tool PATH] [--json] [--scale N]
Exit 0 all checks pass, 1 a check failed, 2 usage error.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_TOOL = os.path.join(ROOT, "employees", "marketing", "seo-aso-specialist", "page_diagnostics.py")
FIX = os.path.join(HERE, "fixtures")
UNRUN = ("not run: fetching live pages or external links, browser rendering, Core Web Vitals, screen-reader "
         "output and search-engine indexing. Only saved HTML snapshots were read.")


def run(tool, *args, cwd=None):
    env = dict({name: os.environ[name] for name in (
                   'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                   'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                   'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                   'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                   'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                   'GITHUB_ACTIONS',
               ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, tool] + [str(a) for a in args], capture_output=True, text=True,
                       cwd=cwd, env=env, timeout=600)
    return p.returncode, p.stdout, p.stderr


def report(tool, site, config, *extra):
    code, out, err = run(tool, site, "--config", config, "--json", *extra)
    try:
        rep = json.loads(out)
    except ValueError:
        rep = None
    return code, rep, out, err


def keys(rep):
    return {f.get("key") for f in rep.get("findings", [])} if isinstance(rep, dict) else None


def read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def tree_hash(root):
    h = hashlib.sha256()
    for d, dirs, files in os.walk(root):
        dirs.sort()
        for fn in sorted(files + [x for x in dirs if os.path.islink(os.path.join(d, x))]):
            p = os.path.join(d, fn)
            h.update(os.path.relpath(p, root).encode("utf-8", "surrogateescape"))
            if os.path.islink(p):
                h.update(b"L" + os.readlink(p).encode())
            else:
                with open(p, "rb") as f:
                    h.update(hashlib.sha256(f.read()).digest())
    return h.hexdigest()


def expected(name):
    with open(os.path.join(FIX, name, "expected.json"), encoding="utf-8") as f:
        return set(json.load(f))


def make_scale_site(base, n):
    """n pages in 20 folders; every 7th page lacks alt text, every 11th links to a missing page, page 0 is the entry."""
    site = os.path.join(base, "site")
    exp = set()
    words = "harbour lantern tide ledger compass anchor beacon current".split()
    for i in range(n):
        key = "/s%02d/p%05d.html" % (i % 20, i) if i else "/index.html"
        nxt = "/s%02d/p%05d.html" % ((i + 1) % 20, i + 1) if i + 1 < n else "/index.html"
        title = ("Scale page %05d about the %s and its keepers today" % (i, words[i % 8]))[:60].ljust(52, ".")
        desc = ("Synthetic scale page %05d. " % i + "A plain description of the %s used only to measure how the "
                "diagnostic behaves on a larger snapshot of saved pages." % words[i % 8])
        desc = desc[:160].ljust(150, ".")
        alt = "" if i % 7 == 3 else ' alt="Figure %d"' % i
        broken = '<a href="/missing/p%05d.html">Missing page %d</a>' % (i, i) if i % 11 == 5 else ""
        body = ('<p><img src="/f.png"%s> <a href="%s">Next page %d</a> %s <a href="/">Home</a></p>'
                % (alt, nxt, i + 1, broken))
        html = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
                'content="width=device-width, initial-scale=1"><title>%s</title><meta name="description" '
                'content="%s"><link rel="canonical" href="https://scale.example%s"></head><body><h1>Page %d</h1>'
                '%s</body></html>\n' % (title, desc, key if i else "/", i, body))
        p = os.path.join(site, *key.strip("/").split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(html)
        if i % 7 == 3:
            exp.add("img_alt_missing|%s|1 image(s) without alt" % key)
        if i % 11 == 5:
            exp.add("broken_link|%s|link /missing/p%05d.html" % (key, i))
    exp.add("sitemap_missing|/sitemap.xml|no sitemap.xml at the snapshot root")
    cfg = os.path.join(base, "config.json")
    with open(cfg, "w") as f:
        json.dump({"base_url": "https://scale.example"}, f)
    return site, cfg, exp


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=DEFAULT_TOOL)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--scale", type=int, default=2000)
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    tool = os.path.abspath(a.tool)
    if not os.path.isfile(tool) or a.scale < 2:
        sys.stderr.write("error: --tool must be a file and --scale at least 2\n")
        return 2
    results = []

    def check(cid, name, ok, detail=""):
        results.append({"id": cid, "name": name, "ok": bool(ok), "detail": detail})

    tmp = tempfile.mkdtemp(prefix="g34-oracle-")
    try:
        for n in ("clean", "before", "after", "unseen"):
            shutil.copytree(os.path.join(FIX, n), os.path.join(tmp, n), symlinks=True)
        S = lambda n: os.path.join(tmp, n, "site")
        C = lambda n: os.path.join(tmp, n, "config.json")
        hashes = {n: tree_hash(S(n)) for n in ("clean", "before", "after", "unseen")}

        code, rep, out, _ = report(tool, S("clean"), C("clean"))
        check("o1", "clean control: no findings, complete, exit 0",
              code == 0 and rep is not None and keys(rep) == set() and rep.get("complete") is True
              and rep.get("pages_scanned") == 3, "exit %s, findings %s" % (code, None if rep is None else len(keys(rep))))
        code, before, out, _ = report(tool, S("before"), C("before"), "--fail-on", "none")
        exp = expected("before")
        got = keys(before)
        check("o2", "before: exactly the %d declared seeded defects" % len(exp), got == exp,
              "missing %s, extra %s" % (sorted(exp - (got or set()))[:3], sorted((got or set()) - exp)[:3]))
        bpath = os.path.join(tmp, "before-report.json")
        with open(bpath, "w") as f:
            f.write(out)
        code, after, _, _ = report(tool, S("after"), C("after"), "--baseline", bpath)
        d = (after or {}).get("diff", {})
        check("o3", "after: no findings, and versus before every seeded defect is fixed and nothing is new",
              code == 0 and keys(after) == set() and set(d.get("fixed", [])) == exp and d.get("new") == []
              and d.get("persisting") == [], "exit %s, fixed %d/%d" % (code, len(d.get("fixed", [])), len(exp)))
        code, un, _, _ = report(tool, S("unseen"), C("unseen"), "--fail-on", "none")
        expu = expected("unseen")
        got = keys(un)
        check("o4", "unseen: the %d declared defects, none of the correct-markup traps" % len(expu), got == expu,
              "missing %s, extra %s" % (sorted(expu - (got or set()))[:3], sorted((got or set()) - expu)[:3]))
        check("o5", "findings carry severity, area, evidence detail and a concrete fix",
              bool(before and before.get("findings")) and all(
                  f.get("severity") in ("high", "medium", "low") and f.get("area") and f.get("detail")
                  and len(f.get("fix", "")) > 15 for f in before["findings"] + (un or {}).get("findings", [])))
        r1 = run(tool, S("before"), "--config", C("before"), "--json")[1]
        r2 = run(tool, S("before"), "--config", C("before"), "--json")[1]
        t1 = run(tool, S("unseen"), "--config", C("unseen"))[1]
        t2 = run(tool, S("unseen"), "--config", C("unseen"))[1]
        check("o6", "deterministic: repeated runs give byte-identical JSON and text", r1 == r2 and t1 == t2 and r1)
        same = all(tree_hash(S(n)) == hashes[n] for n in hashes)
        check("o7", "the snapshot folders are byte-identical after every run", same)

        # failure variants on a copy of the clean site
        fs = os.path.join(tmp, "failsite")
        shutil.copytree(S("clean"), fs)
        outside = os.path.join(tmp, "outside.html")
        with open(outside, "w") as f:
            f.write("<title>outside</title>")
        os.symlink(outside, os.path.join(fs, "escape.html"))
        os.symlink(tmp, os.path.join(fs, "loopdir"))
        code, rep, _, _ = report(tool, fs, C("clean"))
        sk = {s.get("path"): s for s in (rep or {}).get("skipped", [])}
        check("o8", "a symlink out of the snapshot is skipped and named, the rest still scanned, exit 3",
              code == 3 and rep is not None and rep.get("complete") is False and "/escape.html" in sk
              and "/loopdir" in sk and rep.get("pages_scanned") == 3 and keys(rep) == set(),
              "exit %s, skipped %s" % (code, sorted(sk)))
        sizes = sorted(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(S("clean")) for f in fs
                       if f.endswith(".html"))
        code, rep, _, _ = report(tool, S("clean"), C("clean"), "--max-bytes", str(sizes[-1] - 1))
        sk = (rep or {}).get("skipped", [])
        check("o9", "a page over --max-bytes is skipped and named, the rest still scanned, exit 3",
              code == 3 and rep is not None and rep.get("complete") is False and len(sk) == 1
              and "max-bytes" in sk[0].get("reason", "") and rep.get("pages_scanned") == 2,
              "exit %s, skipped %d" % (code, len(sk)))

        # recovery: a failed run must leave an earlier --out report untouched and leave no temporary file.
        # (The failure here is detected before writing; the mid-write path, a failing os.replace, is
        # fault-injected in tests/test_g34_capability.py.)
        od = os.path.join(tmp, "reports")
        os.makedirs(od)
        outp = os.path.join(od, "report.json")
        c1 = run(tool, S("before"), "--config", C("before"), "--out", outp)[0]
        good = read_bytes(outp)
        bad = os.path.join(tmp, "bad-baseline.json")
        with open(bad, "w") as f:
            f.write('{"schema": "g34/1", "findings": [')
        c2 = run(tool, S("after"), "--config", C("after"), "--out", outp, "--baseline", bad)[0]
        still = read_bytes(outp)
        c3 = run(tool, S("after"), "--config", C("after"), "--out", outp)[0]
        new = read_bytes(outp)
        leftovers = [x for x in os.listdir(od) if x != "report.json"]
        check("o10", "--out recovery: a failed run keeps the earlier report byte-identical, a good run replaces it, no temp file left",
              good is not None and c1 == 1 and c2 == 2 and still == good and c3 == 0 and new is not None
              and new != good and not leftovers and json.loads(new.decode()).get("findings") == [], "exits %s %s %s, leftovers %s" % (c1, c2, c3, leftovers))
        badcfg = os.path.join(tmp, "bad-config.json")
        with open(badcfg, "w") as f:
            json.dump({"base_url": "lantern.example"}, f)
        inside = os.path.join(S("clean"), "report.json")
        e1 = run(tool, S("clean"), "--config", C("clean"), "--out", inside)
        e2 = run(tool, S("clean"), "--config", badcfg)
        e3 = run(tool, os.path.join(tmp, "nope"), "--config", C("clean"))
        e4 = run(tool, S("clean"), "--config", C("clean"), "--out", os.path.join(tmp, "no-such-dir", "r.json"))
        check("o11", "usage errors exit 2 with a message and write nothing (out inside snapshot, bad config, "
              "missing site, missing out folder)",
              all(e[0] == 2 and e[2].startswith("error:") and not e[1] for e in (e1, e2, e3, e4))
              and not os.path.exists(inside) and tree_hash(S("clean")) == hashes["clean"],
              "exits %s" % [e[0] for e in (e1, e2, e3, e4)])
        th = [run(tool, S("unseen"), "--config", C("unseen"), "--fail-on", lvl)[0]
              for lvl in ("high", "medium", "low", "none")]
        thc = [run(tool, S("clean"), "--config", C("clean"), "--fail-on", lvl)[0] for lvl in ("high", "low")]
        sev = {f["severity"] for f in (un or {}).get("findings", [])}
        check("o12", "--fail-on thresholds follow the severities found", th == [1, 1, 1, 0] and thc == [0, 0]
              and sev == {"high", "medium", "low"}, "unseen %s clean %s" % (th, thc))

        scale_dir = os.path.join(tmp, "scale")
        site, cfg, sexp = make_scale_site(scale_dir, a.scale)
        t0 = time.perf_counter()
        code, rep, _, _ = report(tool, site, cfg, "--fail-on", "none")
        secs = time.perf_counter() - t0
        scale = {"pages": a.scale, "seconds": round(secs, 2), "findings": None if rep is None else len(keys(rep))}
        check("o13", "scale: %d pages in 20 folders, exactly the generated defects" % a.scale,
              code == 0 and rep is not None and rep.get("pages_scanned") == a.scale and keys(rep) == sexp,
              "exit %s, %.2fs, findings %s/%d" % (code, secs, scale["findings"], len(sexp)))
        with open(tool, encoding="utf-8") as f:
            src = f.read()
        net = re.findall(r"^\s*(?:import|from)\s+(socket|http|urllib\.request|ssl|ftplib|smtplib|requests)\b",
                         src, re.M)
        check("s1", "static: the tool imports no network module", not net, "found %s" % net)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(r["ok"] for r in results)
    rep = {"passed": passed, "total": len(results), "complete": True, "checks": results, "scale": scale,
           "unrun": UNRUN}
    if a.json:
        print(json.dumps(rep, indent=2))
    else:
        for r in results:
            print("%s %-4s %s%s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["name"],
                                    "" if r["ok"] or not r["detail"] else "  [%s]" % r["detail"]))
        print("scale: %s" % json.dumps(scale))
        print("%d/%d checks passed" % (passed, len(results)))
        print(UNRUN)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
