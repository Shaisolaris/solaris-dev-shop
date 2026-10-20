#!/usr/bin/env python3
"""G20 oracle: runs the black-box scenarios in oracle_checks.js on a JavaScript shell, and inspects the demo page statically.

  python3 examples/capabilities/G20/ui_oracle.py [--core PATH] [--jsc PATH] [--seed N] [--scale N] [--json]

Behaviour checks (o1 to o11) run the DOM-free core in JavaScriptCore (macOS ships it as the jsc helper) with a virtual clock
and hand-resolved responses. Static checks (s1 to s6) read demo/index.html as text. No browser is started: rendering, real
focus movement, the CSS media query and screen-reader output are NOT exercised, and the report says so.
Exit 0 when every check passes, 1 when a check fails, 2 when no JavaScript shell is available or an argument is invalid.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CORE = ROOT / "employees/engineering/frontend-developer/async_search_core.js"
DEMO = HERE / "demo" / "index.html"
JSC_DEFAULT = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
UNRUN = ("not run: browser rendering, real keyboard focus, the CSS media query at 40rem, colour contrast as rendered, "
         "and screen-reader output. Only the DOM-free core (in JavaScriptCore) and the demo source text were checked here; "
         "browser_checks.py renders the page in headless Chrome (one launch per run) when a browser is named. Screen readers and other browsers are not run by either.")


def find_jsc(explicit):
    for c in ([explicit] if explicit else []) + [os.environ.get("G20_JSC"), shutil.which("jsc"), JSC_DEFAULT]:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return c
    return None


def run_checks(jsc, core, seed, scale, timeout=120):
    p = subprocess.run([jsc, str(core), str(HERE / "oracle_checks.js"), "--", str(seed), str(scale)],
                       capture_output=True, text=True, timeout=timeout)
    checks, scale_info = {}, {}
    for line in p.stdout.splitlines():
        m = re.match(r"CHECK (o\d+) (PASS|FAIL)(?: (.*))?$", line)
        if m:
            checks[m.group(1)] = {"pass": m.group(2) == "PASS", "detail": m.group(3) or ""}
        elif line.startswith("SCALE "):
            scale_info = json.loads(line[6:])
    complete = "DONE 11" in p.stdout and len(checks) == 11
    return {"checks": checks, "scale": scale_info, "complete": complete, "rc": p.returncode, "stderr": p.stderr[-400:]}


def static_checks():
    out = {}
    html = DEMO.read_text(encoding="utf-8")
    core_src = CORE.read_text(encoding="utf-8")
    def chk(cid, ok, detail):
        out[cid] = {"pass": bool(ok), "detail": "" if ok else detail}
    tag = re.search(r"<input[^>]*id=\"q\"[^>]*>", html, re.S)
    t = tag.group(0) if tag else ""
    chk("s1", tag and all(a in t for a in ('role="combobox"', 'aria-expanded="false"', 'aria-controls="results"',
                                            'aria-autocomplete="list"')) and '<label for="q"' in html
        and 'role="listbox"' in html and 'q.setAttribute("aria-activedescendant"' in html,
        "the input must be a labelled ARIA combobox controlling a listbox, with aria-activedescendant set by script")
    st = re.search(r"<div[^>]*id=\"status\"[^>]*>", html)
    er = re.search(r"<div[^>]*id=\"error\"[^>]*>", html)
    chk("s2", st and 'role="status"' in st.group(0) and 'aria-live="polite"' in st.group(0)
        and er and 'role="alert"' in er.group(0) and re.search(r"<button[^>]*id=\"retry\"", html)
        and 'setAttribute("aria-busy"' in html and "status.textContent = said" in html,
        "a polite live region, an alert for errors, a Retry button and aria-busy while loading are required")
    px = int(re.search(r"NARROW_MAX_PX = (\d+)", core_src).group(1))
    mq = re.search(r"@media \(min-width: ([\d.]+)rem\)", html)
    chk("s3", mq and float(mq.group(1)) * 16 == px + 1, f"the CSS breakpoint must be NARROW_MAX_PX + 1 = {px + 1}px at 16px per rem")
    src = re.search(r'<script src="([^"]*async_search_core\.js)"', html)
    chk("s4", src and (DEMO.parent / src.group(1)).resolve() == CORE.resolve(),
        "the demo must load the same core file the checks run")
    remote = re.findall(r"""(?:src|href)\s*=\s*["'](?:https?:)?//""", html) + re.findall(r"\bfetch\(\s*['\"]https?:", html)
    chk("s5", not remote and "fixture-data.js" in html, "the demo must be offline: no remote scripts, styles or fetches")
    svg = (ROOT / "assets/social-preview.svg").read_text(encoding="utf-8").lower()
    brand = {k: v.lower() for k, v in re.findall(r"--sol-(navy|cream|amber|line):\s*(#[0-9a-fA-F]{6})", html)}
    chk("s6", len(brand) == 4 and all(v in svg for v in brand.values()) and "georgia" in svg and "Georgia" in html
        and "prefers-reduced-motion" in html and ":focus-visible" in html,
        "Solaris brand colours and font must come from assets/social-preview.svg; focus-visible and reduced motion required")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--core", default=str(CORE))
    ap.add_argument("--jsc")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not (1 <= a.scale <= 50):
        print("invalid: --scale must be 1 to 50"); return 2
    core = Path(a.core)
    if not core.is_file():
        print(f"invalid: --core {core} is not a file"); return 2
    jsc = find_jsc(a.jsc)
    if not jsc:
        print("no JavaScript shell found (jsc); behaviour checks not run. " + UNRUN); return 2
    beh = run_checks(jsc, core, a.seed, a.scale)
    sta = static_checks() if core.resolve() == CORE.resolve() else {}
    allc = dict(beh["checks"], **sta)
    ok = beh["complete"] and all(c["pass"] for c in allc.values())
    rep = {"core": str(core), "js_shell": jsc, "seed": a.seed, "scale": beh["scale"], "checks": allc,
           "complete": beh["complete"], "passed": sum(c["pass"] for c in allc.values()), "total": len(allc), "unrun": UNRUN}
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for cid in sorted(allc, key=lambda k: (k[0], int(k[1:]))):
            c = allc[cid]
            print(f"{'PASS' if c['pass'] else 'FAIL'} {cid}{(' ' + c['detail'][:300]) if c['detail'] else ''}")
        if not beh["complete"]:
            print(f"incomplete run: rc={beh['rc']} {beh['stderr']}")
        print(f"scale: {json.dumps(beh['scale'])}")
        print(f"{rep['passed']}/{rep['total']} checks passed")
        print(UNRUN)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
