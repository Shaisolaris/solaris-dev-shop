#!/usr/bin/env python3
"""M23 prep oracle: WordPress diagnostics that explain actual faults (G23). Grok self-validation, not independent review.

Static, offline, black-box: writes the synthetic bundles from m23_world.py (no WordPress, PHP or MySQL runtime is
used or claimed), runs the bound candidate command once per bundle in a throwaway copy, reads its findings, and
scores localisation of known faults, unflagged valid controls and robustness. Adversarial cases (conflicting
plugins under cache behaviour, speedup comparability, slug traps, historical log lines, malformed input, no
runtime data) are findings only. Binding schema: README.md.

usage: m23_oracle.py BINDING.json OUT_DIR [--only NAME,NAME]
"""
import json, os, re, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m23_world as W

KIND = {"conflict": r"(?i)conflict|redeclare|collision|fatal",
        "slow": r"(?i)slow|query[_ ]?time|expensive|long[- ]running",
        "config": r"(?i)config|wp-config|WP_[A-Z_]{3,}|memory limit"}
SPEED = r"(?i)speed-?up|faster|improv|reduc|before.{0,30}after"
X2_CLAIM = r"\b(19|20|21)(\.\d+)?\s?(x|×|times)\b|\b9[45](\.\d+)?\s?%"
HIST = r"(?i)inactive|not active|historical|older|no longer|removed|deactivated|stale|earlier|previous"
TIME_VAL = r"\b\d+(\.\d+)?\s?(ms|s|sec|secs|seconds)\b"


def get_path(obj, path):
    for k in [p for p in (path or "").split(".") if p]:
        obj = obj[k]
    return obj


def run_one(binding, bdir, name, files, work):
    bun = os.path.join(work, name)
    for rel, txt in files.items():
        rel2 = binding.get("file_map", {}).get(rel, rel)
        p = os.path.join(bun, rel2)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)
    out = os.path.join(work, name + ".out")
    os.makedirs(out, exist_ok=True)
    cmd = [c.replace("{bundle}", bun).replace("{out}", out).replace("{binding_dir}", bdir) for c in binding["cmd"]]
    cwd = os.path.join(bdir, binding.get("cwd", "."))
    t = time.time()
    try:
        cp = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=binding.get("timeout_s", 60))
        rc, so, se, to = cp.returncode, cp.stdout, cp.stderr, False
    except subprocess.TimeoutExpired as e:
        rc, so, se, to = None, e.stdout or "", e.stderr or "", True
    secs = round(time.time() - t, 2)
    findings, perr = [], None
    try:
        src = so if binding.get("output", "stdout") == "stdout" else open(binding["output"].split(":", 1)[1].replace("{out}", out)).read()
        findings = get_path(json.loads(src), binding.get("findings_path", ""))
        if not isinstance(findings, list):
            raise ValueError("findings is not a list")
    except Exception as e:
        perr = repr(e)[:200]
    tb = "Traceback (most recent call last)" in (se or "") + (so or "")  # checked on the full streams, not the kept tail
    return dict(rc=rc, timeout=to, secs=secs, traceback=tb, stderr_tail=(se or "")[-600:], parse_error=perr, findings=findings)


def benign(binding, f):
    sev = str(f.get(binding.get("severity_field", "severity"), "")).lower() if isinstance(f, dict) else ""
    return sev in [s.lower() for s in binding.get("benign_severities", ["info", "pass", "ok", "clean", "skip", "notice"])]


def judge(binding, name, exp, r):
    txt = lambda f: json.dumps(f, ensure_ascii=False)
    bad = [f for f in r["findings"] if not benign(binding, f)]
    tb = r["traceback"]
    d = {"exit": r["rc"], "timeout": r["timeout"], "traceback": tb, "parse_error": r["parse_error"],
         "findings": len(r["findings"]), "non_benign": len(bad)}
    if exp.get("robust"):
        ok = not tb and not r["timeout"]
        return ok, d
    if r["timeout"] or r["parse_error"]:
        return False, d
    if exp.get("control"):
        d["flagged"] = [txt(f)[:200] for f in bad]
        ok = not bad
        if exp.get("no_timings"):
            tv = [txt(f)[:160] for f in r["findings"] if re.search(TIME_VAL, txt(f))]
            d["time_values_without_runtime_data"] = tv
            d["states_runtime_dependency"] = any(re.search(r"(?i)skip|unavailable|not available|requires|wp-cli|runtime", txt(f)) for f in r["findings"])
            ok = ok and not tv
        return ok, d
    if "speedup" in exp:
        sp = [txt(f) for f in r["findings"] if re.search(SPEED, txt(f))]
        d["speedup_findings"] = [s[:220] for s in sp]
        if not sp:
            d["note"] = "no speedup reported (feature absent or declined)"
            return None, d
        if exp["speedup"] == "accept":
            return any(re.search(a, s) for a in W.X3_ACCEPT for s in sp), d
        refused = any(re.search(W.X2_REFUSE, s) for s in sp)
        claimed = any(re.search(X2_CLAIM, s) for s in sp)
        return (refused or not claimed), dict(d, refused=refused, claimed_20x=claimed)
    kind = re.compile(KIND[exp["kind"]])
    hit = [f for f in bad if kind.search(txt(f)) and all(re.search(t, txt(f), re.I) for t in exp["tokens"])]
    d["localized"] = bool(hit)
    if hit:
        d["matching_finding"] = txt(hit[0])[:300]
    culprit = [t for t in exp["tokens"] if t.startswith("(?<!")]
    blamed = []
    for dec in exp.get("decoys", []):
        rx = W.SLUG.format(re.escape(dec))
        for f in bad:
            s = txt(f)
            if any(f is h for h in hit):  # the localising finding may name where the fault surfaced
                continue
            if re.search(rx, s, re.I) and not any(re.search(c, s, re.I) for c in culprit):
                if exp.get("historical_ok") and re.search(HIST, s):
                    continue
                blamed.append(f"{dec}: {s[:160]}")
    d["decoy_blamed"] = blamed
    return bool(hit) and not blamed, d


def main():
    a = sys.argv[1:]
    bpath, out = os.path.abspath(a[0]), os.path.abspath(a[1])
    only = a[a.index("--only") + 1].split(",") if "--only" in a else None
    binding = json.load(open(bpath))
    bdir = os.path.dirname(bpath)
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="m23prep-run-")
    res, runs = [], {}
    try:
        B = W.bundles()
        for name, exp in W.EXPECT.items():
            if only and name not in only:
                continue
            r = run_one(binding, bdir, name, B[name], work)
            runs[name] = r
            ok, d = judge(binding, name, exp, r)
            res.append({"id": name, "kind": "core" if exp["core"] else "adversarial",
                        "result": {True: "PASS", False: "FAIL", None: "INCONCLUSIVE"}[ok], "detail": d})
            print(f"{name:38s} {res[-1]['kind']:11s} {res[-1]['result']}", flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    r1 = all(not r["timeout"] and not r["traceback"] for r in runs.values())
    res.append({"id": "R1_no_crash_all_bundles", "kind": "core", "result": "PASS" if r1 else "FAIL",
                "detail": {"bundles": len(runs), "max_secs": max([r["secs"] for r in runs.values()] or [0])}})
    print(f"{'R1_no_crash_all_bundles':38s} core        {res[-1]['result']}")
    core = [x for x in res if x["kind"] == "core"]
    rep = {"label": "Grok self-validation (M23 prep oracle); not independent review",
           "subject": binding.get("name"), "runtime": "static/offline only: no WordPress, PHP, MySQL or WP-CLI used; bundles are synthetic",
           "results": res, "core_pass": sum(x["result"] == "PASS" for x in core), "core_total": len(core),
           "adversarial_findings": [x["id"] for x in res if x["kind"] == "adversarial" and x["result"] == "FAIL"],
           "adversarial_inconclusive": [x["id"] for x in res if x["result"] == "INCONCLUSIVE"],
           "raw_findings": {k: v["findings"] for k, v in runs.items()}}
    rep["verdict_core"] = "PASS" if rep["core_pass"] == rep["core_total"] else "FAIL"
    json.dump(rep, open(os.path.join(out, "report.json"), "w"), indent=1, ensure_ascii=False)
    print(f"core {rep['core_pass']}/{rep['core_total']}  adversarial findings {rep['adversarial_findings']}  "
          f"inconclusive {rep['adversarial_inconclusive']}  verdict_core {rep['verdict_core']}")


if __name__ == "__main__":
    main()
