#!/usr/bin/env python3
"""M38 r2 oracle (Grok self-validation, not independent review): the M38 v2 oracle unchanged in P01-S08, plus R10
(r2 repairs probed beyond the M38 rows: small edits to whole license texts, text hidden in copyright lines and the
Apache appendix, CRLF texts and logs, lost newlines, --out on a folder) and O11 (OBS). Original M38 docstring follows.
M38 oracle (Grok self-validation, not independent review), written from M38.md, G38.md, provenance-integrity.md and
immutable-event-validation.md. It builds its own synthetic repositories and hash chains, computes every expectation
itself with hashlib, and drives the two CLIs. Every run goes through an audit hook; no process, network or mail use is
allowed at all. Usage: PY m38_oracle.py TREE OUT.json [--tools DIR]   (DIR holds provenance_check.py and event_chain.py)"""
import hashlib, json, os, random, re, shutil, subprocess, sys, tempfile, threading
from pathlib import Path
TREE = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2])
if "--tools" in sys.argv:
    TD = Path(sys.argv[sys.argv.index("--tools") + 1]).resolve(); PC, EC = TD / "provenance_check.py", TD / "event_chain.py"
else:
    PC = TREE / "employees/quality-security/security-auditor/provenance_check.py"; EC = TREE / "employees/engineering/blockchain-developer/event_chain.py"
HERE = Path(__file__).resolve().parent; AUD = HERE / "audit"; APACHE = (HERE / "data/apache-2.0.txt").read_text()
WORK = Path(tempfile.mkdtemp(prefix="m38o-", dir="/tmp")); ALOG = WORK / "audit.log"; ROWS = []; OUTS = []
MIT = """MIT License

Copyright (c) 2026 Oracle Test Holdings (synthetic)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
MIT0 = MIT.replace("MIT License", "MIT No Attribution").replace(", subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n", ".\n")

def run(tool, *args, cwd=None, timeout=120):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(WORK / "home"), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(AUD), "M32_AUDIT_LOG": str(ALOG), "LC_ALL": "C"}
    try:
        p = subprocess.run([sys.executable, str(tool)] + [str(a) for a in args], cwd=str(cwd or WORK), env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        OUTS.append("TIMEOUT"); return 124, "", "TIMEOUT"
    OUTS.append(p.stdout + p.stderr); return p.returncode, p.stdout, p.stderr
def js(s):
    try: return json.loads(s)
    except Exception: return None
def row(name, sub, obs=False):
    ok = True if obs else all(v[0] for v in sub.values())
    ROWS.append({"row": name, "pass": ok, "obs": obs, "sub": {k: bool(v[0]) for k, v in sub.items()}, "detail": {k: repr(v[1])[:400] for k, v in sub.items()}})
def tb(o, e): return "Traceback" in o + e
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def snap(d): return {str(p.relative_to(d)): (sha(p) if p.is_file() and not p.is_symlink() else "L") for p in sorted(Path(d).rglob("*"))}

# ---------------- provenance: my own synthetic repository ----------------
def repo(name, lic=MIT):
    r = WORK / name; shutil.rmtree(r, ignore_errors=True); (r / "employees/ops/notes-writer").mkdir(parents=True); (r / "third_party/tok").mkdir(parents=True); (r / "lib").mkdir()
    if lic is not None: (r / "LICENSE").write_text(lic)
    (r / "pyproject.toml").write_text('[project]\nname = "oracle-demo"\nversion = "1.2.0"\nlicense = { text = "MIT" }\n')
    (r / "employees/ops/notes-writer/plugin.json").write_text(json.dumps({"name": "notes-writer", "version": "1.0.0", "license": "MIT"}, indent=2))
    (r / "README.md").write_text("# Oracle demo (synthetic)\n\n[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)\n\nText.\n\n## License\n\nMIT. See LICENSE.\n")
    (r / "third_party/tok/LICENSE.txt").write_text(MIT.replace("Oracle Test Holdings", "Tok Authors"))
    (r / "NOTICE.md").write_text("# Notice\n\nThird-party license files:\n\n- `third_party/tok/LICENSE.txt`\n")
    (r / "lib/core.py").write_text("X = 1\n"); (r / "lib/data.bin").write_bytes(bytes(range(256)))
    return r
def manifest(r, files, extra=""):
    m = r / "MANIFEST.sha256"; m.write_text("".join("%s  %s\n" % (sha(r / f), f) for f in files) + extra); return m
def check(r, *extra):
    rc, o, e = run(PC, "check", r, "--json", *extra); return rc, js(o), o, e
def codes(j): return sorted((f.get("code"), f.get("path")) for f in (j or {}).get("findings", []))
def only(j, code, path): return codes(j) == [(code, path)]

def p01():
    res = {}; r = repo("p01"); files = ["LICENSE", "NOTICE.md", "README.md", "pyproject.toml", "employees/ops/notes-writer/plugin.json", "third_party/tok/LICENSE.txt", "lib/core.py", "lib/data.bin"]
    m = manifest(r, files); before = snap(r); rc, j, o, e = check(r, "--manifest", m)
    sub = ((j or {}).get("integrity") or {}).get("subject") or {}
    res["clean_consistent"] = (rc == 0 and j and j.get("result") == "consistent" and j.get("license") == "MIT" and j.get("findings") == [], (rc, codes(j), (j or {}).get("license")))
    res["declarations_4"] = ((j or {}).get("declarations") == 4, (j or {}).get("declarations"))
    res["subject_is_my_sha256"] = (sub.get("digests") == {f: sha(r / f) for f in files}, sub)
    res["upstream_listed"] = ((j or {}).get("upstream_license_files") == ["third_party/tok/LICENSE.txt"], (j or {}).get("upstream_license_files"))
    res["statement_no_opinion_no_auth"] = (j is not None and "not a legal opinion" in j.get("statement", "") and "no identity is authenticated" in j.get("statement", ""), (j or {}).get("statement"))
    res["root_unchanged"] = (snap(r) == before, "")
    # the actual repository at the candidate revision
    plugins = [p for p in TREE.rglob("plugin.json") if "examples/capabilities/G38/fixtures" not in str(p) and ".git" not in p.parts]
    rc1, j1, o1, e1 = check(TREE, "--exclude", "examples/capabilities/G38/fixtures")
    res["repo_excluded_consistent"] = (rc1 == 0 and j1 and j1.get("result") == "consistent" and j1.get("license") == "MIT", (rc1, codes(j1)))
    res["OBS_repo_declarations"] = (True, ((j1 or {}).get("declarations"), len(plugins) + 3))
    res["exclusion_disclosed"] = (bool((j1 or {}).get("excluded")) and "examples/capabilities/G38/fixtures" in json.dumps((j1 or {}).get("excluded")), (j1 or {}).get("excluded"))
    rc2, j2, o2, e2 = check(TREE)
    fx = sorted(str(p.relative_to(TREE)) for p in (TREE / "examples/capabilities/G38/fixtures").rglob("*") if re.match(r"(LICEN[CS]E|COPYING)", p.name))
    res["repo_unexcluded_names_fixture_files"] = (rc2 == 1 and codes(j2) == [("upstream_license_unlisted", f) for f in fx], (rc2, codes(j2), fx))
    row("P01 clean controls: my synthetic MIT repo is consistent with 4 declarations and a subject equal to my own sha256 of all 8 listed files; the actual repository is consistent with the fixture folder excluded (and the exclusion disclosed) and names exactly the fixture's license files without it; nothing written", res)

def p02():
    res = {}
    def drift(key, edit, code, path):
        r = repo("p02-" + key); edit(r); rc, j, o, e = check(r); res[key] = (rc == 1 and only(j, code, path) and not tb(o, e), (rc, codes(j)))
    drift("plugin_apache", lambda r: (r / "employees/ops/notes-writer/plugin.json").write_text('{"name": "notes-writer", "license": "Apache-2.0"}'), "license_mismatch", "employees/ops/notes-writer/plugin.json")
    drift("pyproject_pep639_string", lambda r: (r / "pyproject.toml").write_text('[project]\nname = "d"\nlicense = "Apache-2.0"\n'), "license_mismatch", "pyproject.toml")
    drift("pyproject_no_license", lambda r: (r / "pyproject.toml").write_text('[project]\nname = "d"\nversion = "1"\n'), "license_undeclared", "pyproject.toml")
    drift("badge_gpl", lambda r: (r / "README.md").write_text((r / "README.md").read_text().replace("license-MIT-blue", "license-GPL--3.0-blue")), "license_mismatch", "README.md")
    drift("section_apache_first_word", lambda r: (r / "README.md").write_text((r / "README.md").read_text().replace("MIT. See LICENSE.", "Apache-2.0. See LICENSE.")), "license_mismatch", "README.md")
    drift("unlisted_copying", lambda r: (r / "third_party/tok/COPYING").write_text("GPL text (synthetic)\n"), "upstream_license_unlisted", "third_party/tok/COPYING")
    drift("unlisted_licence_spelling", lambda r: (r / "lib/LICENCE").write_text(MIT), "upstream_license_unlisted", "lib/LICENCE")
    r = repo("p02-notice"); (r / "NOTICE.md").write_text((r / "NOTICE.md").read_text() + "- `third_party/gone/LICENSE`\n"); rc, j, o, e = check(r)
    fs = (j or {}).get("findings") or []
    res["notice_names_missing"] = (rc == 1 and len(fs) == 1 and fs[0].get("code") == "notice_path_missing" and "third_party/gone/LICENSE" in (fs[0].get("path", "") + fs[0].get("detail", "")), (rc, fs))
    def nested(r):
        d = r / "employees/ops/deep/x/y"; d.mkdir(parents=True); (d / "plugin.json").write_text('{"name": "y", "version": "1"}')
    drift("nested_plugin_undeclared", nested, "license_undeclared", "employees/ops/deep/x/y/plugin.json")
    r = repo("p02-norights", lic="Copyright 2026 Someone. All rights reserved.\n"); rc, j, o, e = check(r)
    res["unrecognized_compares_nothing"] = (rc == 1 and [c for c, _ in codes(j)] == ["license_unrecognized"], (rc, codes(j)))
    r = repo("p02-apache", lic=APACHE); rc, j, o, e = check(r)
    res["apache_text_under_mit_declarations"] = (rc == 1 and (j or {}).get("license") == "Apache-2.0" and {p for c, p in codes(j) if c == "license_mismatch"} == {"pyproject.toml", "employees/ops/notes-writer/plugin.json", "README.md"} and (j or {}).get("declarations") == 4, (rc, (j or {}).get("license"), codes(j)))
    r = repo("p02-none", lic=None); rc, j, o, e = check(r)
    res["missing_license"] = (rc == 1 and "license_missing" in [c for c, _ in codes(j)], (rc, codes(j)))
    row("P02 single-cause license drifts on my own repo: each gives exactly its documented code at its path (plugin, PEP 639 pyproject string, no pyproject license, badge, section, COPYING, LICENCE spelling, NOTICE naming a missing file, a nested plugin), unrecognised text compares nothing, Apache text against 4 MIT declarations gives 4 mismatches, no LICENSE is named", res)

def p03():
    res = {}
    r = repo("p03-restricted", lic=MIT.rstrip("\n") + "\n\nThe Software may not be used for commercial purposes without written permission.\n"); rc, j, o, e = check(r)
    res["mit_plus_restriction_not_called_mit"] = (not (rc == 0 and (j or {}).get("result") == "consistent"), (rc, (j or {}).get("license"), codes(j)))
    r = repo("p03-mit0", lic=MIT0); rc, j, o, e = check(r)
    res["mit0_not_called_mit"] = (not (rc == 0 and (j or {}).get("result") == "consistent"), (rc, (j or {}).get("license"), codes(j)))
    r = repo("p03-prose"); (r / "README.md").write_text((r / "README.md").read_text().replace("MIT. See LICENSE.", "This project is licensed under the Apache License 2.0."))
    rc, j, o, e = check(r); res["section_prose_apache_named"] = (rc == 1 and ("license_mismatch", "README.md") in codes(j), (rc, codes(j)))
    r = repo("p03-substr"); (r / "old/third_party/tok").mkdir(parents=True); (r / "old/third_party/tok/LICENSE.txt").write_text(MIT)
    (r / "NOTICE.md").write_text("# Notice\n\n- `old/third_party/tok/LICENSE.txt`\n"); rc, j, o, e = check(r)
    res["notice_substring_not_coverage"] = (rc == 1 and ("upstream_license_unlisted", "third_party/tok/LICENSE.txt") in codes(j), (rc, codes(j)))
    r = repo("p03-loop"); os.symlink("..", r / "lib/loop"); rc, j, o, e = check(r)
    res["symlink_loop_terminates"] = (rc in (0, 1) and not tb(o, e), (rc, codes(j), e[-200:]))
    r = repo("p03-badjson"); (r / "employees/ops/notes-writer/plugin.json").write_text('{"name": "notes-writer", "license": "MIT",'); rc, j, o, e = check(r)
    res["malformed_plugin_not_consistent"] = (rc != 0 and not tb(o, e), (rc, codes(j), e[-200:]))
    r = repo("p03-nonstr"); (r / "employees/ops/notes-writer/plugin.json").write_text('{"name": "notes-writer", "license": ["MIT", "GPL-3.0"]}'); rc, j, o, e = check(r)
    res["nonstring_license_not_consistent"] = (rc != 0 and not tb(o, e), (rc, codes(j), e[-200:]))
    r = repo("p03-nonotice"); (r / "NOTICE.md").unlink(); rc, j, o, e = check(r)
    res["no_notice_upstream_unlisted"] = (rc == 1 and ("upstream_license_unlisted", "third_party/tok/LICENSE.txt") in codes(j), (rc, codes(j)))
    r = repo("p03-comma"); (r / "README.md").write_text((r / "README.md").read_text().replace("MIT. See LICENSE.", "GPL, see LICENSE.")); rc, j, o, e = check(r)
    res["section_name_then_comma_read"] = (rc == 1 and ("license_mismatch", "README.md") in codes(j), (rc, codes(j), (j or {}).get("declarations")))
    r = repo("p03-rootplugin"); (r / "agent-desk").mkdir(); (r / "agent-desk/plugin.json").write_text('{"name": "agent-desk", "license": "Apache-2.0"}'); rc, j, o, e = check(r)
    res["root_level_plugin_checked"] = (rc == 1 and ("license_mismatch", "agent-desk/plugin.json") in codes(j), (rc, codes(j)))
    cp = TREE / "chief-of-staff/plugin.json"
    if cp.exists():
        r = WORK / "p03-repo"; shutil.copytree(TREE, r, ignore=shutil.ignore_patterns(".git", "__pycache__")); q = r / "chief-of-staff/plugin.json"; q.write_text(q.read_text().replace('"license": "MIT"', '"license": "Apache-2.0"'))
        rc, j, o, e = check(r, "--exclude", "examples/capabilities/G38/fixtures"); res["actual_repo_chief_of_staff_plugin_checked"] = (rc == 1 and ("license_mismatch", "chief-of-staff/plugin.json") in codes(j), (rc, codes(j)))
        shutil.rmtree(r, ignore_errors=True)
    r = repo("p03-outdir"); rc, o, e = run(PC, "check", r, "--out", WORK / "nodir-p/x.json"); res["out_missing_dir_exit2"] = (rc == 2 and not tb(o, e), (rc, e[-140:]))
    row("P03 unseen license cases: MIT text with an added commercial-use restriction and MIT-0 text are not reported as consistent MIT; a README License section naming Apache in prose is a mismatch; NOTICE naming a longer path that contains the upstream path is not coverage; no NOTICE at all; a symlink loop terminates; a malformed or non-string plugin license is never consistent and never a traceback; a License section 'GPL, see LICENSE.' is read; a plugin.json outside employees/ (my repo, and chief-of-staff in a copy of the actual repo) is checked; --out into a missing folder exits 2", res)

def p04():
    res = {}; r = repo("p04"); outside = WORK / "p04-outside"; outside.mkdir(exist_ok=True); (outside / "secret.txt").write_text("s\n")
    os.symlink(str(outside), r / "lnkdir"); os.symlink("lib/core.py", r / "core-link.py")
    good = ["lib/core.py", "lib/data.bin", "README.md"]
    def mcase(key, extra, code, path, pre=None):
        if pre: pre()
        m = manifest(r, good, extra); rc, j, o, e = check(r, "--manifest", m)
        res[key] = (rc == 1 and (code, path) in codes(j) and not tb(o, e), (rc, codes(j)))
        return j
    hx = hashlib.sha256(b"s\n").hexdigest()
    mcase("symlink_entry", "%s  core-link.py\n" % sha(r / "lib/core.py"), "artifact_refused", "core-link.py")
    mcase("symlinked_parent_dir_outside", "%s  lnkdir/secret.txt\n" % hx, "artifact_refused", "lnkdir/secret.txt")
    mcase("dotdot_escape", "%s  ../p04-outside/secret.txt\n" % hx, "artifact_refused", "../p04-outside/secret.txt")
    mcase("absolute_path", "%s  %s\n" % (hx, outside / "secret.txt"), "artifact_refused", str(outside / "secret.txt"))
    mcase("folder_entry", "%s  lib\n" % ("0" * 64), "artifact_refused", "lib")
    mcase("missing_file", "%s  lib/gone.py\n" % ("1" * 64), "artifact_missing", "lib/gone.py")
    j = mcase("changed_bytes", "%s  NOTICE.md\n" % hashlib.sha256(b"old notice").hexdigest(), "digest_mismatch", "NOTICE.md")
    sub = (((j or {}).get("integrity") or {}).get("subject") or {}).get("digests") or {}
    res["subject_only_matching"] = (sub == {f: sha(r / f) for f in good}, sub)
    m = manifest(r, good, "%s  lib/core.py\n" % ("2" * 64)); rc, j, o, e = check(r, "--manifest", m)
    res["duplicate_conflicting_entry_named_or_refused"] = ((rc == 1 and any(p == "lib/core.py" for _, p in codes(j))) or (rc == 2 and not tb(o, e)), (rc, codes(j), e[-120:]))
    # malformed manifest: exit 2, earlier --out kept
    outf = WORK / "p04-report.json"; m = manifest(r, good); rc0, o0, e0 = run(PC, "check", r, "--manifest", m, "--out", outf)
    kept = outf.read_bytes() if outf.exists() else None
    (r / "MANIFEST.sha256").write_text("not a manifest line\n"); rc, o, e = run(PC, "check", r, "--manifest", r / "MANIFEST.sha256", "--out", outf)
    res["malformed_manifest_exit2_report_kept"] = (rc0 == 0 and kept is not None and rc == 2 and outf.read_bytes() == kept and not tb(o, e), (rc0, rc, kept is not None, e[-160:]))
    row("P04 manifest integrity on my repo: a symlink entry, a path through a symlinked folder leading outside ROOT, a .. escape, an absolute path and a folder are refused; missing and changed files are named; the subject holds only my sha256 of the matching files; a conflicting duplicate entry is named; a malformed manifest exits 2 and keeps the earlier --out report", res)

def r09():
    """v2 (added after the v1 mutation run): documented forms the v1 rows did not pin down."""
    res = {}
    r = repo("r09-both", lic=MIT + "\n" + APACHE); rc, j, o, e = check(r)
    res["two_license_texts_unrecognized"] = (rc == 1 and [c for c, _ in codes(j)] == ["license_unrecognized"], (rc, codes(j)))
    wrapped = " ".join(MIT.split()).replace(" Copyright", "\nCopyright").replace(" Permission", "\n\nPermission")
    wrapped = wrapped.replace('"AS IS"', "\u201cAS IS\u201d").replace('"Software"', "\u201cSoftware\u201d")
    import textwrap; wrapped = "\n".join(textwrap.fill(par, 60) for par in wrapped.split("\n"))
    r = repo("r09-wrap", lic=wrapped); rc, j, o, e = check(r)
    res["rewrapped_curly_mit_is_mit"] = (rc == 0 and (j or {}).get("license") == "MIT", (rc, (j or {}).get("license"), codes(j)))
    r = repo("r09-alias"); (r / "pyproject.toml").write_text('[project]\nname = "d"\nlicense = { text = "MIT License" }\n'); rc, j, o, e = check(r)
    res["mit_license_wording_is_mit"] = (rc == 0, (rc, codes(j)))
    r = repo("r09-git"); (r / ".git/objects").mkdir(parents=True); (r / ".git/LICENSE").write_text(MIT); rc, j, o, e = check(r)
    res["dot_git_not_walked"] = (rc == 0, (rc, codes(j)))
    r = repo("r09-ex"); rc, o, e = run(PC, "check", r, "--exclude", "no/such/folder"); res["exclude_typo_refused"] = (rc == 2 and not tb(o, e), (rc, e[-120:]))
    rc, o, e = run(PC, "check", r, "--exclude", "../r09-alias"); res["exclude_outside_refused"] = (rc == 2 and not tb(o, e), (rc, e[-120:]))
    m = manifest(r, ["lib/core.py", "README.md"], "garbage line here\n"); rc, o, e = run(PC, "check", r, "--manifest", m)
    res["malformed_line_among_good_exit2"] = (rc == 2 and not tb(o, e), (rc, e[-120:]))
    (r / "MANIFEST.sha256").write_text("\n"); rc, o, e = run(PC, "check", r, "--manifest", r / "MANIFEST.sha256")
    res["empty_manifest_not_consistent"] = (rc != 0 and not tb(o, e), (rc, e[-120:]))
    ev = chain(40, 4); ev[20]["seq"] = 25; rechain(ev, 20); rc, j, o, e = verify(wlog("r09-renum", ev))
    res["renumbered_seq_rehashed_is_gap"] = (rc == 1 and first(j) == ("seq_gap", "line 21"), (rc, first(j)))
    for key, val in (("seq_bool", True), ("seq_string", "1"), ("seq_float", 1.0)):
        ev = chain(5, 3); ev[1]["seq"] = val; rechain(ev, 1); rc, j, o, e = verify(wlog("r09-" + key, ev)); res[key + "_never_verified"] = (rc == 1 and first(j)[1] == "line 2", (rc, first(j)))
    ev = chain(50, 11); L = [canon(x) for x in ev]; L[-1] = L[-1][:37]; p = WORK / "r09-torn"; p.write_text("\n".join(L)); rc, j, o, e = verify(p)
    res["torn_last_write_is_torn_tail"] = (rc == 1 and first(j) == ("torn_tail", "line 50"), (rc, first(j)))
    # G05 loaded by path must leave no bytecode cache, also when the caller does not set PYTHONDONTWRITEBYTECODE
    g5 = PC.resolve().parents[1] / "assurance"; b4 = sorted(x.name for x in g5.iterdir()) if g5.is_dir() else []
    r = repo("r09-g05"); manifest(r, ["lib/core.py"]); env = {"PATH": "/usr/bin:/bin", "HOME": str(WORK / "home"), "PYTHONPATH": str(AUD), "M32_AUDIT_LOG": str(ALOG)}
    p2 = subprocess.run([sys.executable, str(PC), "check", str(r), "--manifest", str(r / "MANIFEST.sha256")], env=env, capture_output=True, text=True, timeout=120); OUTS.append(p2.stdout + p2.stderr)
    af = sorted(x.name for x in g5.iterdir()) if g5.is_dir() else []
    res["no_g05_cache_without_env"] = (p2.returncode == 0 and af == b4, (p2.returncode, sorted(set(af) - set(b4))))
    row("R09 (v2) documented forms: two license texts together are unrecognised; rewrapped MIT with curly quotes is MIT; 'MIT License' declares MIT; .git is not walked; a mistyped or outside --exclude and a malformed line among good manifest lines exit 2; an empty manifest is never consistent; a renumbered rehashed seq is a gap; bool, string and float seq never verify; a torn last write without newline is torn_tail; loading G05 leaves no bytecode cache when the caller does not disable it", res)

def o05():
    res = {}
    for key, lic in (("mit_and_apache_concatenated", MIT + "\n" + APACHE),):
        r = repo("o05-" + key, lic=lic); rc, j, o, e = check(r); res[key] = (True, (rc, (j or {}).get("license"), codes(j)))
    r = repo("o05-lower"); (r / "employees/ops/notes-writer/plugin.json").write_text('{"name": "n", "license": "mit"}'); rc, j, o, e = check(r); res["plugin_lowercase_mit"] = (True, (rc, codes(j)))
    r = repo("o05-spdxor"); (r / "employees/ops/notes-writer/plugin.json").write_text('{"name": "n", "license": "MIT OR Apache-2.0"}'); rc, j, o, e = check(r); res["plugin_spdx_or"] = (True, (rc, codes(j)))
    r = repo("o05-filelic"); (r / "pyproject.toml").write_text('[project]\nname = "d"\nlicense = { file = "LICENSE" }\n'); rc, j, o, e = check(r); res["pyproject_license_file_form"] = (True, (rc, codes(j)))
    r = repo("o05-lowerfile"); (r / "lib/license.txt").write_text(MIT); rc, j, o, e = check(r); res["lowercase_license_txt_unlisted"] = (True, (rc, codes(j)))
    r = repo("o05-licmd", lic=None); (r / "LICENSE.md").write_text(MIT); rc, j, o, e = check(r); res["root_LICENSE_md_only"] = (True, (rc, (j or {}).get("license"), codes(j)))
    r = repo("o05-mf"); good = ["lib/core.py"]
    for key, line in (("star_binary_marker", "%s *lib/core.py\n"), ("uppercase_hex", None), ("crlf", "%s  lib/core.py\r\n"), ("dot_slash", "%s  ./lib/core.py\n")):
        h = sha(r / "lib/core.py")
        txt = (h.upper() + "  lib/core.py\n") if line is None else (line % h)
        (r / "MANIFEST.sha256").write_text(txt); rc, j, o, e = check(r, "--manifest", r / "MANIFEST.sha256")
        res["manifest_" + key] = (True, (rc, codes(j), (((j or {}).get("integrity") or {}).get("matching"))))
    (r / "MANIFEST.sha256").write_text(""); rc, j, o, e = check(r, "--manifest", r / "MANIFEST.sha256"); res["manifest_empty"] = (True, (rc, codes(j)))
    r2 = repo("o05-nl"); (r2 / "lib/license.txt").write_text(MIT); (r2 / "NOTICE.md").write_text((r2 / "NOTICE.md").read_text() + "- `lib/license.txt`\n"); rc, j, o, e = check(r2); res["notice_lists_lowercase_file"] = (True, (rc, codes(j)))
    r2 = repo("o05-plain"); (r2 / "NOTICE.md").write_text("# Notice\n\nThird-party: third_party/tok/LICENSE.txt\n"); rc, j, o, e = check(r2); res["notice_plain_text_path"] = (True, (rc, codes(j)))
    outin = r / "report.json"; rc, o, e = run(PC, "check", r, "--out", outin); res["out_inside_root"] = (True, (rc, outin.exists(), e[-120:]))
    row("O05 (OBS) license and manifest edge forms recorded, not scored: concatenated texts, lowercase and SPDX OR values, pyproject license file form, lowercase license.txt, LICENSE.md only, shasum binary marker, uppercase hex, CRLF, ./ prefix, empty manifest, --out inside ROOT", res, obs=True)

def lic_of(lic):
    r = repo("r10-%d" % (abs(hash(lic)) % 10**8), lic=lic); rc, j, o, e = check(r); return rc, (j or {}).get("license"), codes(j), tb(o, e)
def r10():
    res = {}
    CR = lambda t: t.replace("\n", "\r\n")
    rc, l, c, t = lic_of(CR(MIT)); res["mit_crlf_is_mit"] = (rc == 0 and l == "MIT" and not t, (rc, l, c))
    rc, l, c, t = lic_of(CR(APACHE)); res["apache_crlf_is_apache"] = (rc == 1 and not t and "Apache" in str(l), (rc, l, c[:3]))  # my repo declares MIT, so Apache gives mismatches
    for key, txt in (("mit_author_singular", MIT.replace("AUTHORS OR COPYRIGHT", "AUTHOR OR COPYRIGHT")), ("mit_merge_removed", MIT.replace("modify, merge, publish", "modify, publish")),
                     ("mit_noninfringement_removed", MIT.replace(" AND NONINFRINGEMENT", "")), ("mit_sublicense_removed", MIT.replace("sublicense, and/or sell", "and/or sell")),
                     ("mit_restriction_in_copyright_line", MIT.replace("Copyright (c) 2026 Oracle Test Holdings (synthetic)", "Copyright (c) 2026 Oracle Test Holdings (synthetic). Commercial use of the Software is prohibited.")),
                     ("mit_restriction_as_extra_c_line", MIT.replace("Copyright (c) 2026 Oracle Test Holdings (synthetic)\n", "Copyright (c) 2026 Oracle Test Holdings (synthetic)\n(c) The Software may not be used for commercial purposes.\n")),
                     ("mit_restriction_as_copyright_line", MIT.replace("Copyright (c) 2026 Oracle Test Holdings (synthetic)\n", "Copyright (c) 2026 Oracle Test Holdings (synthetic)\nCopyright holders forbid any commercial use of the Software.\n")),
                     ("apache_word_changed_in_terms", (lambda t: t.replace("worldwide, non-exclusive, no-charge", "worldwide, exclusive, no-charge", 1) if "worldwide, non-exclusive, no-charge" in t else None)(APACHE)),
                     ("apache_terms_cut_before_end", APACHE[:APACHE.index("9. Accepting Warranty")] + "END OF TERMS AND CONDITIONS\n"),
                     ("apache_appendix_with_added_terms", APACHE.replace("limitations under the License.", "limitations under the License.\n\nAdditional term: no commercial use.\n\nSee the License for the specific language governing permissions and limitations under the License.")),
                     ("apache_extra_text_inside_appendix", APACHE.replace("APPENDIX: How to apply the Apache License to your work.", "APPENDIX: How to apply the Apache License to your work.\n\nNOTWITHSTANDING THE ABOVE, NO COMMERCIAL USE IS PERMITTED.\n"))):
        rc, l, c, t = lic_of(txt); res[key + "_unrecognized"] = (l in (None, "unrecognized") and ("license_unrecognized", "LICENSE") in c and not t, (rc, l, c[:2]))
    rc, l, c, t = lic_of(APACHE.replace("{yyyy} {name of copyright owner}", "2026 Oracle Test Holdings (synthetic)") if "{yyyy} {name of copyright owner}" in APACHE else None); res["apache_appendix_filled_in_is_apache"] = ("Apache" in str(l) and not t, (rc, l))
    # README section forms
    r = repo("r10-readme"); (r / "README.md").write_text("# D\n\n## License\n\nApache License 2.0, see LICENSE.\n"); rc, j, o, e = check(r)
    res["readme_comma_form_mismatch_found"] = (rc == 1 and ("license_mismatch", "README.md") in codes(j) and not tb(o, e), (rc, codes(j)))
    for key, sec in (("parenthesis", "GPL-3.0 (see LICENSE)"), ("bold", "**GPL-3.0**")):
        r = repo("r10-rd-" + key); (r / "README.md").write_text("# D\n\n## License\n\n%s\n" % sec); rc, j, o, e = check(r)
        res["readme_%s_gpl_mismatch_found" % key] = (rc == 1 and ("license_mismatch", "README.md") in codes(j), (rc, codes(j)))
    # root-level plugin.json anywhere under ROOT
    r = repo("r10-rootplug"); (r / "chief").mkdir(); (r / "chief/plugin.json").write_text('{"name": "c", "license": "Apache-2.0"}'); rc, j, o, e = check(r)
    res["root_level_plugin_mismatch_found"] = (rc == 1 and only(j, "license_mismatch", "chief/plugin.json"), (rc, codes(j)))
    # --out on an existing folder and into a missing folder: exit 2, no traceback, nothing written
    r = repo("r10-out"); (WORK / "r10-outdir").mkdir(exist_ok=True)
    for key, tgt in (("existing_folder", WORK / "r10-outdir"), ("missing_folder", WORK / "nope" / "r.json")):
        rc, o, e = run(PC, "check", r, "--out", tgt); res["provenance_out_" + key + "_exit_2"] = (rc == 2 and not tb(o, e), (rc, e[-140:]))
    g = wlog("r10-g", chain(4, 3))
    for key, tgt in (("existing_folder", WORK / "r10-outdir"), ("missing_folder", WORK / "nope2" / "r.jsonl")):
        rc, o, e = run(EC, "recover", g, "--out", tgt); res["event_recover_out_" + key + "_exit_2"] = (rc == 2 and not tb(o, e), (rc, e[-140:]))
    # lost trailing newline: append twice, each time after the newline was lost again
    ev = chain(6, 11); p = wlog("r10-nl", ev); p.write_bytes(p.read_bytes()[:-1])
    a1 = run(EC, "append", p, "--claimed-by", "x", "--body", "{}")[0]; p.write_bytes(p.read_bytes()[:-1]); a2 = run(EC, "append", p, "--claimed-by", "y", "--body", "{}")[0]
    rv, j, o, e = verify(p); L = p.read_bytes().split(b"\n")
    res["lost_newline_twice_two_appends_verify"] = (a1 == 0 and a2 == 0 and rv == 0 and (j or {}).get("verified") == 8 and L[-1] == b"", (a1, a2, rv, (j or {}).get("verified")))
    # CRLF log: verify must not crash; append must refuse unchanged or leave a log that verifies with one more event
    ev = chain(5, 12); p = WORK / "r10-crlf.jsonl"; p.write_bytes(b"".join(canon(x).encode() + b"\r\n" for x in ev)); before = p.read_bytes()
    rv, j, o, e = verify(p); t1 = tb(o, e); ra, oa, ea = run(EC, "append", p, "--claimed-by", "x", "--body", "{}"); rv2, j2, o2, e2 = verify(p)
    res["crlf_log_no_traceback_and_append_safe"] = (not t1 and not tb(oa, ea) and not tb(o2, e2) and ((ra == 2 and p.read_bytes() == before) or (ra == 0 and rv2 == 0 and (j2 or {}).get("verified") == 6)), (rv, first(j), ra, rv2, (j2 or {}).get("verified")))
    # newline lost after a CR (a CRLF writer cut between the two bytes)
    ev = chain(5, 13); p = WORK / "r10-cr.jsonl"; p.write_bytes(b"".join(canon(x).encode() + b"\n" for x in ev)[:-1] + b"\r"); before = p.read_bytes()
    rv, j, o, e = verify(p); ra, oa, ea = run(EC, "append", p, "--claimed-by", "x", "--body", "{}"); rv2, j2, o2, e2 = verify(p)
    res["cr_only_tail_append_safe"] = (not tb(o, e) and not tb(oa, ea) and ((ra == 2 and p.read_bytes() == before) or (ra == 0 and rv2 == 0 and (j2 or {}).get("verified") == 6)), (rv, first(j), ra, rv2, (j2 or {}).get("verified")))
    row("R10 r2 repairs probed beyond M38: CRLF license texts are recognised; small word edits to MIT or Apache, terms hidden in copyright lines or the Apache appendix are unrecognised; a filled-in appendix is Apache; the comma README form and a root-level plugin.json are read; --out on a folder or a missing folder exits 2; two lost newlines, a CRLF log and a CR-only tail are append-safe", res)

def o11():
    res = {}
    for key, txt in (("spdx_header_line_then_mit", "SPDX-License-Identifier: MIT\n\n" + MIT), ("bom_mit", "\ufeff" + MIT), ("copyright_before_title", MIT.replace("MIT License\n\nCopyright (c) 2026 Oracle Test Holdings (synthetic)", "Copyright (c) 2026 Oracle Test Holdings (synthetic)\n\nMIT License")),
                     ("wrapped_copyright_two_lines", MIT.replace("Copyright (c) 2026 Oracle Test Holdings (synthetic)", "Copyright (c) 2026 Oracle Test Holdings (synthetic)\n    and contributors")),
                     ("apache_copyright_line_on_top", "Copyright 2026 Oracle Test Holdings (synthetic)\n\n" + APACHE), ("mit_british_licence_title", MIT.replace("MIT License", "MIT Licence")), ("apache_without_appendix", APACHE[:APACHE.index("APPENDIX")])):
        rc, l, c, t = lic_of(txt); res[key] = (True, (rc, l, c[:2], t))
    for key, py in (("file_form", 'license = { file = "LICENSE" }'), ("single_quotes", "license = 'MIT'"), ("table_form", '[project.license]\ntext = "MIT"'), ("spdx_expression", 'license = "MIT OR Apache-2.0"')):
        r = repo("o11-py-" + key); body = '[project]\nname = "d"\n' + (py if not py.startswith("[") else "") + "\n" + (py if py.startswith("[") else ""); (r / "pyproject.toml").write_text(body); rc, j, o, e = check(r); res["pyproject_" + key] = (True, (rc, codes(j)))
    for key, sec in (("parenthesis", "MIT (see LICENSE)"), ("bold", "**MIT**"), ("lowercase_words", "Licensed under the MIT License."), ("semicolon", "Apache-2.0; see LICENSE")):
        r = repo("o11-rd-" + key); (r / "README.md").write_text("# D\n\n## License\n\n%s\n" % sec); rc, j, o, e = check(r); res["readme_" + key] = (True, (rc, codes(j)))
    r = repo("o11-nm"); (r / "node_modules/x").mkdir(parents=True); (r / "node_modules/x/plugin.json").write_text('{"license": "GPL-3.0"}'); (r / "fixtures/repo").mkdir(parents=True); (r / "fixtures/repo/plugin.json").write_text('{"license": "GPL-3.0"}')
    rc, j, o, e = check(r); res["plugin_in_node_modules_and_fixture_dir"] = (True, (rc, codes(j)))
    row("O11 (OBS) recorded, not scored: SPDX header line, BOM, copyright before title, wrapped copyright, Apache with a copyright line on top, British title, Apache without appendix; pyproject file, single-quote, table and SPDX forms; README parenthesis, bold, sentence and semicolon forms; plugin.json in node_modules and a fixture folder", res, obs=True)

# ---------------- event chain ----------------
Z = "0" * 64
def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"))
def ehash(e): return hashlib.sha256(canon({k: e[k] for k in ("seq", "prev", "at", "claimed_by", "body")}).encode()).hexdigest()
def chain(n, seed=0, t0=1760000000):
    rnd = random.Random(seed); ev = []; prev = Z
    for i in range(n):
        at = "2026-10-%02dT%02d:%02d:00-07:00" % (1 + i // 1440 % 28, i // 60 % 24, i % 60)
        e = {"seq": i, "prev": prev, "at": at, "claimed_by": rnd.choice(["Ops desk (synthetic)", "Release bot (synthetic)"]), "body": {"step": i, "artifact": "a%d.zip" % rnd.randrange(999)}}
        e["hash"] = ehash(e); ev.append(e); prev = e["hash"]
    return ev
def rechain(ev, start):
    for i in range(start, len(ev)):
        if i: ev[i]["prev"] = ev[i - 1]["hash"]
        ev[i]["hash"] = ehash(ev[i])
    return ev
def wlog(name, ev, raw_lines=None):
    p = WORK / name; p.write_text("".join((l if isinstance(l, str) else canon(l)) + "\n" for l in (raw_lines if raw_lines is not None else ev))); return p
def verify(p, *a):
    rc, o, e = run(EC, "verify", p, "--json", *a); return rc, js(o), o, e
def first(j):
    f = (j or {}).get("findings") or [{}]; return f[0].get("code"), f[0].get("at")

def e01():
    res = {}; fx = TREE / "examples/capabilities/G38/fixtures/events.jsonl"; lines = [json.loads(l) for l in fx.read_text().splitlines()]
    res["fixture_hashes_recompute"] = (all(ehash(e) == e["hash"] for e in lines) and all(lines[i]["prev"] == (lines[i - 1]["hash"] if i else Z) for i in range(len(lines))), len(lines))
    rc, j, o, e = verify(fx, "--anchor", "2:%s" % lines[2]["hash"])
    res["anchored_verify"] = (rc == 0 and (j or {}).get("result") == "verified" and (j or {}).get("verified") == len(lines) and ((j or {}).get("head") or {}).get("hash") == lines[-1]["hash"], (rc, (j or {}).get("result"), (j or {}).get("head")))
    res["anchored_not_self_only"] = ("self-consistent only" not in str((j or {}).get("anchor")), (j or {}).get("anchor"))
    ev = chain(60, 7); p = wlog("e01.jsonl", ev); rc, j, o, e = verify(p)
    res["my_chain_verifies_self_only"] = (rc == 0 and (j or {}).get("verified") == 60 and "self-consistent only" in str((j or {}).get("anchor")), (rc, (j or {}).get("anchor")))
    cnt = {}; [cnt.__setitem__(x["claimed_by"], cnt.get(x["claimed_by"], 0) + 1) for x in ev]
    res["claimed_by_counts_not_authenticated"] = (((j or {}).get("claimed_by") or {}).get("counts") == cnt and ((j or {}).get("claimed_by") or {}).get("identity") == "claimed in plain text, not authenticated", (j or {}).get("claimed_by"))
    rc2, o2, e2 = run(EC, "verify", p); res["text_says_not_authenticated"] = (rc2 == 0 and "not authenticated" in o2, o2[-200:])
    row("E01 clean controls: the fixture's hashes and links recompute with my canonical JSON; anchored verify passes with the head I compute and does not say self-consistent only; my 60-event chain verifies as self-consistent only with claimed_by counts equal to mine and reported as not authenticated", res)

def e02():
    res = {}
    def case(key, mut, codeset, line, n=50, extra=()):
        ev = chain(n, 11); lines = mut(ev); p = wlog("e02-" + key, ev, lines); rc, j, o, e = verify(p, *extra); c, at = first(j)
        exp_v = line - 1 if line else None
        ok = rc == 1 and c in codeset and at == "line %d" % line and (j or {}).get("verified") == exp_v and (j or {}).get("unverified_after_break") == (j or {}).get("events_total", -1) - exp_v
        res[key] = (ok and not tb(o, e), (rc, c, at, (j or {}).get("verified"), (j or {}).get("unverified_after_break"), (j or {}).get("events_total")))
    def edit(ev): ev[20]["body"]["artifact"] = "forged.zip"; return None
    case("edit_body", edit, {"hash_mismatch"}, 21)
    def edit_rehash(ev): ev[20]["body"]["artifact"] = "forged.zip"; ev[20]["hash"] = ehash(ev[20]); return None
    case("edit_rehash_one", edit_rehash, {"broken_link"}, 22)
    def delete(ev): del ev[20]; return None
    case("delete_middle", delete, {"seq_gap", "broken_link"}, 21)
    def swap(ev): ev[20], ev[21] = ev[21], ev[20]; return None
    case("swap", swap, {"seq_gap", "broken_link", "seq_repeat"}, 21)
    def replay(ev): ev.insert(21, dict(ev[20])); return None
    case("replay", replay, {"seq_repeat", "broken_link"}, 22)
    def torn(ev): L = [canon(x) for x in ev]; L[-1] = L[-1][:37]; return L
    case("torn_tail", torn, {"torn_tail", "line_not_json"}, 50)
    def torn_nonl(ev): L = [canon(x) for x in ev]; L[-1] = L[-1][:37]; return L
    ev = chain(50, 11); L = torn_nonl(ev); p = WORK / "e02-torn-nonl"; p.write_text("\n".join(L)); rc, j, o, e = verify(p); c, at = first(j)
    res["torn_tail_no_newline"] = (rc == 1 and c in {"torn_tail", "line_not_json"} and at == "line 50" and (j or {}).get("verified") == 49, (rc, c, at, (j or {}).get("verified")))
    def junk(ev): L = [canon(x) for x in ev]; L.insert(30, "not json {"); return L
    case("junk_line", junk, {"line_not_json"}, 31)
    def regress(ev): ev[25]["at"] = "2026-09-01T00:00:00-07:00"; rechain(ev, 25); return None
    case("time_regression_rehashed", regress, {"time_regression"}, 26)
    def naive(ev): ev[25]["at"] = "2026-10-01T00:25:00"; rechain(ev, 25); return None
    case("naive_time_rehashed", naive, {"time_invalid"}, 26)
    def extra(ev): ev[25]["note"] = "x"; rechain(ev, 25); return None
    case("extra_field", extra, {"fields_wrong"}, 26)
    def missing(ev): del ev[25]["claimed_by"]; return [canon(x) for x in ev]
    case("missing_field", missing, {"fields_wrong"}, 26)
    # rewrite from 10 recomputed: no anchor passes (self-only), anchor at original 30 fails
    ev0 = chain(50, 11); a30 = ev0[30]["hash"]; ev = chain(50, 11); ev[10]["body"]["artifact"] = "rewritten.zip"; rechain(ev, 10); p = wlog("e02-rewrite", ev)
    rc, j, o, e = verify(p); res["rewrite_unanchored_self_only"] = (rc == 0 and "self-consistent only" in str((j or {}).get("anchor")), (rc, (j or {}).get("anchor")))
    rc, j, o, e = verify(p, "--anchor", "30:%s" % a30); res["rewrite_anchored_mismatch"] = (rc == 1 and first(j)[0] == "anchor_mismatch", (rc, (j or {}).get("findings")))
    ev = chain(50, 11)[:20]; p = wlog("e02-trunc", ev); rc, j, o, e = verify(p, "--anchor", "30:%s" % a30); res["truncated_before_anchor"] = (rc == 1 and first(j)[0] == "anchor_not_reached", (rc, (j or {}).get("findings")))
    ev = chain(50, 11); a5 = ev[5]["hash"]; ev[40]["body"]["step"] = -1; p = wlog("e02-latetamper", ev); rc, j, o, e = verify(p, "--anchor", "5:%s" % a5)
    res["anchor_ok_later_tamper_found"] = (rc == 1 and first(j) == ("hash_mismatch", "line 41"), (rc, first(j)))
    for key, a in (("anchor_garbage", "five:zz"), ("anchor_short_hash", "3:abc")):
        rc, o, e = run(EC, "verify", wlog("e02-ok", chain(10, 1)), "--anchor", a); res[key] = (rc == 2 and not tb(o, e), (rc, e[-120:]))
    # seeded soak: random single tamper on chains of 40..300; first finding line equals the tampered line
    rnd = random.Random(38); bad = []
    for k in range(10):
        n = rnd.randrange(40, 300); i = rnd.randrange(1, n - 1); ev = chain(n, 100 + k); ev[i]["claimed_by"] = "Someone else (synthetic)"
        rc, j, o, e = verify(wlog("e02-soak%d" % k, ev))
        if not (rc == 1 and first(j) == ("hash_mismatch", "line %d" % (i + 1)) and (j or {}).get("verified") == i): bad.append((n, i, rc, first(j), (j or {}).get("verified")))
    res["seeded_soak_10"] = (not bad, bad[:2])
    row("E02 tamper evidence on my seeded chains: an edit, an edit with that event's hash recomputed, a deletion, a swap, a replay, a torn tail, a junk line, a rehashed time regression, a rehashed naive time, extra and missing fields are each named at their line with nothing after trusted; an unanchored rewrite passes only as self-consistent while the original anchor catches it; truncation before the anchor and a tamper after a good anchor are named; bad anchors exit 2; a 10-chain seeded soak", res)

def o06():
    res = {}
    for key, val in (("seq_bool", True), ("seq_string", "1"), ("seq_float", 1.0)):
        ev = chain(5, 3); ev[1]["seq"] = val; rechain(ev, 1); rc, j, o, e = verify(wlog("o06-" + key, ev)); res[key] = (True, (rc, first(j)))
    ev = chain(5, 3); ev[2]["hash"] = ev[2]["hash"].upper(); rc, j, o, e = verify(wlog("o06-upper", ev)); res["stored_hash_uppercase"] = (True, (rc, first(j)))
    ev = chain(5, 3); ev[2]["body"] = {"note": "caf\u00e9 \u00fc"}; rechain(ev, 2); p = WORK / "o06-utf8"
    p.write_text("".join(json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for x in ev), encoding="utf-8")
    rc, j, o, e = verify(p); res["non_ascii_body_utf8_lines"] = (True, (rc, first(j)))
    q = WORK / "o06-ownutf8"; rc1, _, _ = run(EC, "append", q, "--claimed-by", "Z\u00fcrich desk", "--body", json.dumps({"n": "caf\u00e9"}, ensure_ascii=False)); rc2, j2, _, _ = verify(q)
    res["own_append_non_ascii_verifies"] = (True, (rc1, rc2, (q.read_text(encoding="utf-8") if q.exists() else "")[:200]))
    p = WORK / "o06-empty"; p.write_text(""); rc, j, o, e = verify(p); res["empty_log"] = (True, (rc, (j or {}).get("result"), (j or {}).get("findings")))
    ev = chain(5, 3); p = wlog("o06-blank", ev, [canon(x) for x in ev[:2]] + [""] + [canon(x) for x in ev[2:]]); rc, j, o, e = verify(p); res["blank_line_middle"] = (True, (rc, first(j)))
    ev = chain(3, 3); ev[2]["claimed_by"] = "General Counsel (authenticated, signed)"; rechain(ev, 2); rc, j, o, e = verify(wlog("o06-claim", ev))
    res["claim_text_saying_authenticated"] = (True, (rc, (j or {}).get("claimed_by")))
    row("O06 (OBS) event edge forms recorded, not scored: seq as bool, string or float with hashes recomputed, a stored uppercase hash, a non-ASCII body written as UTF-8, an empty log, a blank line, a claimed_by that says authenticated", res, obs=True)

def e03():
    res = {}; p = WORK / "e03.jsonl"
    rcs = [run(EC, "append", p, "--claimed-by", "Ops desk (synthetic)", "--body", json.dumps({"n": i}), "--at", "2026-10-1%dT09:00:00-07:00" % i)[0] for i in range(3)]
    L = [json.loads(l) for l in p.read_text().splitlines()]
    res["append_from_empty"] = (rcs == [0, 0, 0] and len(L) == 3 and L[0]["prev"] == Z and all(x["seq"] == i and x["hash"] == ehash(x) and x["prev"] == (L[i - 1]["hash"] if i else Z) for i, x in enumerate(L)), (rcs, len(L)))
    ev = chain(20, 5); ev[8]["body"]["step"] = 99; b = wlog("e03-broken", ev); bb = b.read_bytes()
    rc, o, e = run(EC, "append", b, "--claimed-by", "x", "--body", "{}"); res["append_broken_refused"] = (rc == 2 and b.read_bytes() == bb and not tb(o, e), (rc, e[-150:]))
    g = wlog("e03-good", chain(5, 5)); gb = g.read_bytes()
    for key, args in (("naive_at", ["--at", "2026-10-30T09:00:00"]), ("bad_body", ["--body-x"]), ("list_body", ["--body", "[1]"]), ("blank_claim", ["--claimed-by", " "])):
        a = ["append", g, "--claimed-by", "x", "--body", "{}"] + args
        if key == "bad_body": a = ["append", g, "--claimed-by", "x", "--body", "{not json"]
        if key == "list_body": a = ["append", g, "--claimed-by", "x", "--body", "[1]"]
        if key == "blank_claim": a = ["append", g, "--claimed-by", " ", "--body", "{}"]
        rc, o, e = run(EC, *a); res["refused_" + key] = (rc == 2 and g.read_bytes() == gb and not tb(o, e), (rc, e[-120:]))
    ev = chain(4, 5); nn = WORK / "e03-nonl"; nn.write_text("".join(canon(x) + "\n" for x in ev[:3]) + canon(ev[3])); nb = nn.read_bytes()
    rc, o, e = run(EC, "append", nn, "--claimed-by", "x", "--body", "{}"); rv, j, _, _ = verify(nn)
    res["no_trailing_newline_never_merges"] = ((rc == 0 and rv == 0 and (j or {}).get("verified") == 5) or (rc == 2 and nn.read_bytes() == nb), (rc, rv, (j or {}).get("verified"), first(j)))
    # lock held by me (flock on the log) -> exit 4, nothing written
    import fcntl
    lk = wlog("e03-lock", chain(3, 5)); lb = lk.read_bytes(); fd = os.open(str(lk), os.O_RDWR); fcntl.flock(fd, fcntl.LOCK_EX)
    try: rc, o, e = run(EC, "append", lk, "--claimed-by", "x", "--body", "{}")
    finally: os.close(fd)
    res["lock_held_exit4"] = (rc == 4 and lk.read_bytes() == lb, (rc, e[-120:]))
    # concurrency: 8 appenders x 20 into one log
    cc = WORK / "e03-conc.jsonl"; errs = []
    def worker(w):
        for i in range(20):
            for _ in range(20):
                rc, o, e = run(EC, "append", cc, "--claimed-by", "w%d" % w, "--body", json.dumps({"w": w, "i": i}))
                if rc == 0: break
                if rc != 4: errs.append((w, i, rc, e[-100:])); break
    ts = [threading.Thread(target=worker, args=(w,)) for w in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]
    rc, j, o, e = verify(cc); L = [json.loads(l) for l in cc.read_text().splitlines()]
    res["concurrent_8x20_all_kept"] = (not errs and rc == 0 and (j or {}).get("verified") == 160 and sorted((x["body"]["w"], x["body"]["i"]) for x in L) == sorted((w, i) for w in range(8) for i in range(20)), (errs[:2], rc, len(L)))
    rc, o, e = run(EC, "append", g, "--claimed-by", "x", "--body", "{}", "--at", "2020-01-01T00:00:00+00:00"); last = json.loads(g.read_text().splitlines()[-1])
    res["OBS_earlier_at_clamped"] = (True, (rc, last.get("at")))
    row("E03 append: from no file it writes seq 0 on 64 zeros and hashes I recompute; a broken log, a naive --at, non-JSON or list bodies and a blank claim are refused with exit 2 and the log byte-identical; a last line without a newline is never merged; a lock I hold gives exit 4 with nothing written; 8 concurrent appenders x 20 keep all 160 events in one verified chain", res)

def e04():
    res = {}; ev = chain(40, 9); ev[15]["body"]["step"] = -5; p = wlog("e04-t.jsonl", ev); pb = p.read_bytes(); orig = pb.decode().splitlines(True)
    out = WORK / "e04-new.jsonl"; rc, o, e = run(EC, "recover", p, "--out", out, "--json")
    res["prefix_kept_byte_equal"] = (rc == 0 and out.exists() and out.read_text() == "".join(orig[:15]) and p.read_bytes() == pb, (rc, out.exists() and len(out.read_text().splitlines())))
    rv, j, _, _ = verify(out); rc2, _, _ = run(EC, "append", out, "--claimed-by", "x", "--body", "{}"); rv2, j2, _, _ = verify(out)
    res["recovered_verifies_and_appends"] = (rv == 0 and rc2 == 0 and rv2 == 0 and (j2 or {}).get("verified") == 16, (rv, rc2, rv2, (j2 or {}).get("verified")))
    ex = WORK / "e04-exists"; ex.write_text("keep me\n")
    for key, target in (("out_is_log", p), ("out_exists", ex), ("out_alias_of_log", WORK / "sub/../e04-t.jsonl"), ("out_missing_dir", WORK / "nodir/x.jsonl")):
        (WORK / "sub").mkdir(exist_ok=True); rc, o, e = run(EC, "recover", p, "--out", target)
        res[key] = (rc == 2 and p.read_bytes() == pb and ex.read_text() == "keep me\n" and not tb(o, e) and not (WORK / "nodir").exists(), (rc, e[-120:]))
    ev0 = chain(30, 9); a20 = ev0[20]["hash"]; ev = chain(30, 9); ev[3]["body"]["step"] = 7; rechain(ev, 3); rw = wlog("e04-rw", ev); o2 = WORK / "e04-rw-out"
    rc, o, e = run(EC, "recover", rw, "--out", o2, "--anchor", "20:%s" % a20); res["anchored_rewrite_keeps_nothing"] = (rc == 1 and not o2.exists(), (rc, o2.exists()))
    ev = chain(10, 9); L = [canon(x) for x in ev]; L[-1] = L[-1][:20]; tt = wlog("e04-torn", ev, L); o3 = WORK / "e04-torn-out"; rc, o, e = run(EC, "recover", tt, "--out", o3)
    res["torn_tail_recovers_9"] = (rc == 0 and o3.exists() and len(o3.read_text().splitlines()) == 9, (rc, o3.exists() and len(o3.read_text().splitlines())))
    row("E04 recovery: the verified prefix is written byte-equal to a new file, verifies and accepts an append, and the original is untouched; --out as the log, an existing file, a path alias of the log or a missing folder is refused with exit 2; an anchored rewrite keeps nothing and writes no file; a torn tail recovers 9 of 10", res)

def c07():
    res = {}; txt = "\n".join(OUTS)
    bad = re.findall(r"(?i)(?<!not )(?<!no )\b(legally (?:valid|binding|compliant)|is compliant|certified|signature (?:is )?verified|identity (?:is )?verified|authenticated as|legal opinion:|licen[cs]es? (?:are|is) compatible|we advise)", txt)
    res["no_positive_legal_or_identity_claim_in_outputs"] = (not bad, bad[:5])
    pos_auth = [l for l in txt.splitlines() if re.search(r"(?i)\bauthenticated\b", l) and not re.search(r"(?i)not authenticated|no identity is authenticated|authenticates no one|\(authenticated, signed\)", l)]
    res["authenticated_only_negated"] = (not pos_auth, pos_auth[:3])
    docs = {}
    for f in ("employees/quality-security/security-auditor/provenance-integrity.md", "employees/engineering/blockchain-developer/immutable-event-validation.md", "employees/legal-compliance/legal-advisor/SKILL.md", "employees/quality-security/security-auditor/SKILL.md", "employees/engineering/blockchain-developer/SKILL.md", "examples/capabilities/G38/README.md"):
        s = (TREE / f).read_text() if (TREE / f).exists() else ""
        docs[f] = [l.strip()[:160] for l in s.splitlines() if re.search(r"(?i)(cosign|in-toto|slsa|signature|attestation)", l) and re.search(r"(?i)\b(verified|verifies|we verify)\b", l) and not re.search(r"(?i)(not|never|unavailable|need|requires|absent|no )", l)]
    res["docs_never_claim_signature_verification"] = (not any(docs.values()), {k: v for k, v in docs.items() if v})
    row("C07 claims: across every output of this oracle run no positive legal-validity, compliance, certification, verified-signature or verified-identity claim appears, 'authenticated' only ever appears negated, and the changed docs never say signatures or attestations are verified here", res)

def s08(before):
    res = {}; log = ALOG.read_text() if ALOG.exists() else ""
    res["no_process_network_mail"] = (log == "", log[:300])
    imp = {}
    for t in (PC, EC):
        s = t.read_text() if t.exists() else ""; imp[t.name] = sorted(set(re.findall(r"(?m)^\s*(?:import|from)\s+(socket|urllib|http|subprocess|requests|smtplib|ssl|web3|eth_\w+|ftplib|asyncio)\b", s)))
    res["no_network_process_imports"] = (not any(imp.values()), imp)
    res["tree_byte_identical_no_pycache"] = (snap(TREE / "examples/capabilities/G38") == before[0] and snap(TREE / "employees") == before[1] and not list(TREE.rglob("__pycache__")), "")
    row("S08 nothing contacted or changed: the audit hook saw no process, network or mail event in any run; neither tool imports a network, process or chain library; the candidate's G38 and employees trees are byte-identical with no __pycache__", res)

before = (snap(TREE / "examples/capabilities/G38"), snap(TREE / "employees"))
for f in (p01, p02, p03, p04, r09, o05, e01, e02, o06, e03, e04, c07, r10, o11):
    try: f()
    except Exception as ex:
        import traceback; ROWS.append({"row": f.__name__ + " CRASHED", "pass": False, "obs": False, "sub": {"crash": False}, "detail": {"tb": traceback.format_exc()[-600:]}})
s08(before)
OUT.write_text(json.dumps({"tool": [str(PC), str(EC)], "python": sys.version.split()[0], "rows": ROWS}, indent=1))
shutil.rmtree(WORK, ignore_errors=True)
core = [r for r in ROWS if not r["obs"]]; ok = sum(r["pass"] for r in core)
for r in ROWS: print(("OBS " if r["obs"] else ("PASS" if r["pass"] else "FAIL")), r["row"][:90], "" if r["pass"] and not r["obs"] else [k for k, v in r["sub"].items() if not v] if not r["obs"] else "")
print("M38 R2 ORACLE %d/%d core %s" % (ok, len(core), "PASS" if ok == len(core) else "FAIL"))
