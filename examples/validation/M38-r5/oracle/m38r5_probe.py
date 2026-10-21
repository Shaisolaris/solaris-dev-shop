"""M38 r5 probe (Grok self-validation, not independent review): G38 r5 company-name holders and README emphasis.
Usage: m38r5_probe.py TREE OUT.json. Cases are written for this pass and differ from the builder tests."""
import json, os, shutil, subprocess, sys, tempfile
TREE = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; ROWS = []
PC = os.path.join(TREE, "employees/quality-security/security-auditor/provenance_check.py")
FX = os.path.join(TREE, "examples/capabilities/G38/fixtures/repo-clean")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
def repo(lic_line=None, readme=None):
    d = tempfile.mkdtemp(prefix="m38r5-"); r = os.path.join(d, "repo"); shutil.copytree(FX, r)
    if lic_line is not None:
        t = open(os.path.join(r, "LICENSE")).read().splitlines()
        i = [k for k, l in enumerate(t) if l.lower().startswith("copyright")][0]; t[i] = lic_line
        open(os.path.join(r, "LICENSE"), "w").write("\n".join(t) + "\n")
    if readme is not None:
        open(os.path.join(r, "README.md"), "w").write("# D\n\n## License\n\n%s\n" % readme)
    p = subprocess.run([sys.executable, PC, "check", r, "--json"], capture_output=True, text=True, env=ENV)
    shutil.rmtree(d, ignore_errors=True)
    try: j = json.loads(p.stdout)
    except ValueError: j = {}
    return p.returncode, j
def row(rid, group, name, ok, detail):
    ROWS.append({"row": rid, "group": group, "name": name, "pass": bool(ok), "detail": detail})
for i, l in enumerate(["Copyright 2025-2026 Freedom Software Labs Ltd", "Copyright 2026 Modify Media LLC",
                       "(c) 2026 Allow Partners AG", "Copyright 2026 Resale Analytics PLC", "Copyright 2026 Sold Out Records, LLC."], 1):
    rc, j = repo(l); row("C%02d" % i, "core", "company holder with a guard word stays MIT and listed: " + l,
                       rc == 0 and j.get("license") == "MIT" and j.get("license_copyright_lines") == [l], [rc, j.get("license")])
for i, l in enumerate(["Copyright 2026 Acme Personal Use Only LLC", "Copyright 2026 Acme Not Transferable Ltd",
                       "Copyright 2026 Acme Non-Commercial Inc", "Copyright 2026 Acme Sellers Six Seven Eight Inc",
                       "Copyright 2026 acme resale corp", "Copyright 2026 Acme Corp, internal evaluation",
                       "Copyright 2026 Acme Exclusively Licensed Inc"], 1):
    rc, j = repo(l); row("R%02d" % i, "core", "restriction still unrecognised: " + l, rc == 1 and j.get("license") == "unrecognized", [rc, j.get("license")])
for i, (sec, want) in enumerate([("__Apache-2.0__", 1), ("`GPL-3.0`, see LICENSE.", 1), ("*BSD-3-Clause*.", 1), ("**MIT**", 0), ("_MIT_", 0)], 1):
    rc, j = repo(readme=sec); f = [(x["code"], x.get("path")) for x in j.get("findings", [])]
    ok = (rc == 1 and ("license_mismatch", "README.md") in f) if want else (rc == 0 and j.get("declarations") == 3)
    row("M%02d" % i, "core", "README section in emphasis read: " + sec, ok, [rc, f, j.get("declarations")])
rc, j = repo(readme="**GPL-3.0*"); row("U01", "core", "mismatched marks are not read as a name (section skipped)", rc == 0 and j.get("declarations") == 2, [rc, j.get("declarations")])
rc, j = repo("Copyright 2026 Restricted Area Games Inc"); row("X01", "obs", "a company name holding a strong word is still unrecognised (false alarm, safe direction)", True, [rc, j.get("license")])
rc, j = repo("Copyright 2026 Acme Never Sold Inc"); row("X02", "obs", "capitalised restriction ending in a suffix without strong words reads MIT but is listed", True, [rc, j.get("license"), j.get("license_copyright_lines")])
json.dump({"python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1)
core = [r for r in ROWS if r["group"] == "core"]
for r in ROWS: print(("PASS " if r["pass"] else "FAIL ") + r["row"] + " " + r["name"] + " " + json.dumps(r["detail"]))
print("M38R5 PROBE core %d/%d" % (sum(r["pass"] for r in core), len(core)))
