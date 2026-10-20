#!/usr/bin/env python3
"""M38 r4 probe (Grok self-validation, not independent review; not a legal opinion). Each line replaces the copyright
line of the G38 clean fixture LICENSE; provenance_check.py check is run through its CLI.
Usage: PY m38r4_probe.py SRC OUT.json
Authoring note (disclosed): C04 first used "Acme, Inc., et al". A period inside the holder is refused by the documented r3
rule (no . ; : ! ? inside a holder), so it moved to the X02 false-alarm observation and C04 now reads "Acme Inc, et al"."""
import json, os, shutil, subprocess, sys, tempfile
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; ROWS = []
PC = os.path.join(SRC, "employees/quality-security/security-auditor/provenance_check.py")
FX = os.path.join(SRC, "examples/capabilities/G38/fixtures/repo-clean")
def check(line, extra_lines=""):
    d = tempfile.mkdtemp(); r = os.path.join(d, "r"); shutil.copytree(FX, r)
    mit = open(os.path.join(r, "LICENSE")).read(); cl = [l for l in mit.splitlines() if l.lower().startswith("copyright")][0]
    open(os.path.join(r, "LICENSE"), "w").write(mit.replace(cl, line + extra_lines))
    p = subprocess.run([sys.executable, PC, "check", r, "--json"], capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    t = subprocess.run([sys.executable, PC, "check", r], capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    shutil.rmtree(d); j = json.loads(p.stdout)
    return j["license"], p.returncode, j.get("license_copyright_lines"), t.stdout
def row(rid, group, desc, ok, detail):
    ROWS.append({"id": rid, "group": group, "desc": desc, "pass": bool(ok), "detail": detail})
    print("%s %-4s %s %s %s" % (rid, group, "PASS" if ok else ("FAIL" if group == "core" else "GAP"), desc, json.dumps(detail)[:200]))
H = "Copyright (c) 2026 Oracle Test Holdings"
# core: restrictions written in new ways (not the builder's test lines)
for i, line in enumerate([H + ", strictly non-commercial", H + ", resale is not permitted", H + " (noncommercial)",
                          H + ", internal evaluation", "Copyright 2026 Acme; academic use", H + ", students only",
                          "Copyright 2026 Acme selling prohibited", H + ", which may not be sold"], 1):
    lic, rc, cr, _ = check(line)
    row("R%02d" % i, "core", "restricted line is not MIT: %s" % line, lic == "unrecognized" and rc == 1, {"license": lic, "rc": rc})
# core: ordinary holders stay MIT and the line is listed in JSON and text
for i, line in enumerate(["Copyright (c) 2026 Acme, Inc. All rights reserved.", "Copyright 2019-2026 Jane Doe and other contributors",
                          "\u00a9 2026 Acme BV", "Copyright 2026 Acme Inc, et al"], 1):
    lic, rc, cr, txt = check(line)
    row("C%02d" % i, "core", "ordinary holder stays MIT and is listed: %s" % line,
        lic == "MIT" and rc == 0 and cr == [line] and line in txt, {"license": lic, "rc": rc, "listed": cr})
lic, rc, cr, _ = check("Copyright 2026 First Holder", "\nCopyright 2026 Second Holder")
row("C05", "core", "two copyright lines: both listed", lic == "MIT" and cr == ["Copyright 2026 First Holder", "Copyright 2026 Second Holder"], {"listed": cr})
# gap: residual the builder discloses (no comma, no listed word): expected to pass as MIT but be listed
lic, rc, cr, txt = check("Copyright 2026 Acme for students and teachers")
row("X01", "gap", "disclosed residual: no comma, no listed word -> MIT but the line is listed for a person",
    lic == "MIT" and cr == ["Copyright 2026 Acme for students and teachers"], {"license": lic, "listed": cr})
# gap: false alarms on real-looking company names (safe direction: unrecognised, not a false MIT)
fa = {}
for line in ["Copyright 2026 Sellers Inc", "Copyright 2026 Purpose Labs", "Copyright 2026 Distributed Systems Inc",
             "Copyright 2026 Never Settle GmbH", "Copyright 2026 Copy Corp", "Copyright 2026 Acme Co., Ltd.",
             "Copyright 2026 Acme, Inc., et al"]:
    fa[line] = check(line)[0]
row("X02", "obs", "company names that contain a guard word (unrecognised = false alarm, safe direction)", True, fa)
json.dump({"python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1)
core = [r for r in ROWS if r["group"] == "core"]
print("M38R4 PROBE core %d/%d; X01 residual %s; false alarms %d/%d" % (sum(r["pass"] for r in core), len(core),
      "listed" if ROWS[-2]["pass"] else "NOT listed", sum(v != "MIT" for v in fa.values()), len(fa)))
