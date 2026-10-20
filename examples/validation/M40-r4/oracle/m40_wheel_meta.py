"""M40 wheel package and metadata checks (Grok self-validation). Usage: PY m40_wheel_meta.py WHEEL SRC. Compares the
wheel with the clean source: METADATA fields against pyproject.toml, RECORD hashes, entry point, members against the
source package dirs (no extra, no missing), no bytecode, no employees/."""
import base64, csv, hashlib, io, os, re, sys, zipfile
whl, src = sys.argv[1], sys.argv[2]; z = zipfile.ZipFile(whl); names = z.namelist(); res = {}
di = [n for n in names if n.endswith(".dist-info/METADATA")][0].rsplit("/", 1)[0]
meta = z.read(di + "/METADATA").decode(); py = open(os.path.join(src, "pyproject.toml")).read()
g = lambda k: [l.split(": ", 1)[1] for l in meta.splitlines() if l.startswith(k + ": ")]
pv = lambda k: re.search(r'(?m)^%s\s*=\s*"([^"]+)"' % k, py).group(1)
res["name"] = (g("Name") == ["solaris-dev-shop"], g("Name")); res["version_matches_pyproject"] = (g("Version") == [pv("version")], g("Version"))
res["requires_python_matches"] = (g("Requires-Python") == [pv("requires-python")], g("Requires-Python"))
res["license_present"] = (bool(g("License") or g("License-Expression")), g("License") + g("License-Expression"))
res["summary_matches"] = (g("Summary") == [pv("description")], g("Summary"))
res["no_runtime_requires"] = (g("Requires-Dist") == [], g("Requires-Dist"))
ep = z.read(di + "/entry_points.txt").decode(); res["entry_point"] = ("solaris-intake = solaris_intake:main" in ep, ep.strip())
bad = []
for row in csv.reader(io.StringIO(z.read(di + "/RECORD").decode())):
    if not row or row[0].endswith("RECORD"): continue
    h = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(z.read(row[0])).digest()).rstrip(b"=").decode()
    if row[1] != h or int(row[2]) != len(z.read(row[0])): bad.append(row[0])
rec = {r[0] for r in csv.reader(io.StringIO(z.read(di + "/RECORD").decode())) if r}
res["record_hashes_true"] = (not bad, bad); res["record_lists_every_member"] = (set(names) == rec, sorted(set(names) ^ rec))
res["no_bytecode"] = (not [n for n in names if n.endswith(".pyc") or "__pycache__" in n], 0)
res["no_employees_or_tests"] = (not [n for n in names if n.split("/")[0] in ("employees", "tests", "examples", "control-plane")], 0)
pk = sorted(n for n in names if not n.startswith(di))
want = sorted(["solaris_intake/" + f for f in os.listdir(os.path.join(src, "solaris_intake")) if f.endswith(".py")] +
              ["solaris_intake/control_plane/" + f for f in os.listdir(os.path.join(src, "control-plane")) if f.endswith((".py", ".json", ".md"))])
res["members_equal_source_package_files"] = (pk == want, {"extra": sorted(set(pk) - set(want)), "missing": sorted(set(want) - set(pk))})
same = [n for n in pk if n in want and z.read(n) == open(os.path.join(src, "control-plane" if "/control_plane/" in n else "", n.replace("solaris_intake/control_plane/", "").replace("solaris_intake/", "solaris_intake/") if "/control_plane/" in n else n), "rb").read()]
res["member_bytes_equal_source"] = (len(same) == len(pk), [n for n in pk if n not in same])
res["wheel_tag_pure"] = (whl.endswith("-py3-none-any.whl"), os.path.basename(whl))
for k, v in res.items(): print(("PASS " if v[0] else "FAIL ") + k + " " + str(v[1])[:300])
print("M40 WHEEL META %d/%d" % (sum(v[0] for v in res.values()), len(res)))
# authoring fix (disclosed): members not in the source are skipped in the byte comparison instead of crashing
