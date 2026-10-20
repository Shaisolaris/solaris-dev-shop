#!/usr/bin/env python3
"""M05 oracle (Grok self-validation). Built by Grok from M05.md, G05.md and ASSURANCE.md "Revision binding" after G05
landed; not from the builder's oracle or fixtures. Own synthetic project "lighthouse" (2 revisions, only app/login.py differs).
Packets and digests go through the documented CLI (run, digest); closures, reopen and waivers through the documented API
(can_close_finding, close_finding, closure_is_current, reopen_finding). Core rows score; OBS rows record only.
v3 (disclosed): my findings used severity "high"; the engine's severities are S0 to S4 (ASSURANCE.md), so every closure row
returned INVALID_FINDING and tested nothing (v2 log kept, results/oracle-v2-first-run-3.9.6.txt). v3 uses S2. C06 is not
re-scored; OBS rows C06b and C17c (a finding closed through a waiver) added; C06b (revision only, no digests key) added to adjudicate it.
v4: the API rows run in one guarded block, so a tool without the API (noop control) fails C14 to C17 instead of crashing.
Usage: PY m05_oracle.py PY QUALITY_OS OUT"""
import hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile, time, dataclasses
from datetime import datetime, timedelta, timezone
PY, Q, OUT = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3]; os.makedirs(OUT, exist_ok=True)
T = tempfile.mkdtemp(prefix="m05o-", dir="/tmp"); res = []
def rec(i, ok, det, graded=True): res.append({"id": i, "result": ("PASS" if ok else "FAIL") if graded else "OBS", "detail": det})
def cli(*a, timeout=60):
    t = time.time(); p = subprocess.run([PY, Q] + [str(x) for x in a], cwd=T, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
                                        env={"PATH": "/usr/bin:/bin", "HOME": T, "PYTHONDONTWRITEBYTECODE": "1"})
    return p.returncode, p.stdout, p.stderr, time.time() - t
def runp(packet, name="p.json"):
    open(os.path.join(T, name), "w").write(json.dumps(packet)); rc, o, e, dt = cli("run", name)
    try: j = json.loads(o)
    except Exception: j = {}
    return rc, j, len(o) + len(e), dt
FILES1 = {"app/login.py": "def login(u, p):\n    return check(u, p)\n", "app/cart.py": "def total(items):\n    return sum(items)\n",
          "web/home.html": "<h1>Lighthouse</h1>\n", "notes/readme.md": "# Lighthouse notes\n"}
FILES2 = dict(FILES1, **{"app/login.py": "def login(u, p):\n    if not u:\n        return False\n    return check(u, p)\n"})
R1, R2 = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678", "f0e1d2c3b4a5968778695a4b3c2d1e0f98765432"
def proj(name, files):
    d = os.path.join(T, name)
    for k, v in files.items(): os.makedirs(os.path.dirname(os.path.join(d, k)), exist_ok=True); open(os.path.join(d, k), "w").write(v)
    return d
proj("r1", FILES1); proj("r2", FILES2)
H = lambda s: hashlib.sha256(s.encode()).hexdigest()
def dig(files, prefixes): return {k: H(v) for k, v in sorted(files.items()) if any(k.startswith(p + "/") for p in prefixes)}
REVIEW = {"security": ["app"], "functional": ["app", "web"], "ux": ["web", "notes"]}
ROLE = {"security": "security-auditor", "functional": "qa-engineer", "ux": "ux-researcher"}
def receipt(g, rev=None, files=None, reviewed=True):
    r = {"gate": g, "role": ROLE[g], "summary": "reviewed %s" % g, "artifacts": ["reports/%s.md" % g]}
    if reviewed: r["reviewed"] = {"revision": rev, "digests": dig(files, REVIEW[g])}
    return r
def packet(gates, subject=None, receipts=None):
    p = {"risk_level": "standard", "dimensions": [], "completed_gates": list(gates), "evidence": receipts or {}}
    if subject is not None: p["subject"] = subject
    return p
SUB1 = {"revision": R1, "digests": dig(FILES1, ["app", "web", "notes"])}; SUB2 = {"revision": R2, "digests": dig(FILES2, ["app", "web", "notes"])}
G3 = ["security", "functional", "ux"]
def states(j): return {g: (v or {}).get("state") for g, v in (((j.get("evidence") or {}).get("revision_binding") or {}).get("gates") or {}).items()}
def gates_info(j): return ((j.get("evidence") or {}).get("revision_binding") or {}).get("gates") or {}
# C00 legacy base: packet with no binding passes
rc0, j0, _, _ = runp(packet(G3, receipts={g: receipt(g, reviewed=False) for g in G3})); rec("C00", rc0 == 0 and j0.get("ok") is True, {"rc": rc0, "codes": j0.get("gate_codes")})
# C01 clean control: subject r1, every receipt reviewed r1
rc, j, _, _ = runp(packet(G3, SUB1, {g: receipt(g, R1, FILES1) for g in G3})); rec("C01", rc == 0 and j.get("ok") is True and set(states(j).values()) == {"current"}, {"rc": rc, "states": states(j), "codes": j.get("gate_codes")})
# C02 changed artifact after pass: subject r2, receipts from r1 -> security+functional stale, ux carried forward
rc, j, _, _ = runp(packet(G3, SUB2, {g: receipt(g, R1, FILES1) for g in G3})); gi = gates_info(j)
acts = {g: str(v.get("action", "")) for g, v in gi.items()}; chg = {g: v.get("changed_files") or v.get("changed") for g, v in gi.items()}
rec("C02", rc == 1 and j.get("ok") is False and "STALE_GATE_EVIDENCE" in (j.get("gate_codes") or []) and states(j) == {"security": "stale", "functional": "stale", "ux": "carried_forward"}
    and all(g in acts[g] and R2[:7] in acts[g] for g in ("security", "functional")) and "app/login.py" in json.dumps(chg.get("security")),
    {"rc": rc, "states": states(j), "codes": j.get("gate_codes"), "actions": acts, "changed": chg})
# C03 same revision label, different content (subject says r1 but files are r2's)
rc, j, _, _ = runp(packet(["security"], {"revision": R1, "digests": SUB2["digests"]}, {"security": receipt("security", R1, FILES1)}))
rec("C03", rc == 1 and "STALE_GATE_EVIDENCE" in (j.get("gate_codes") or []) and states(j).get("security") == "stale", {"rc": rc, "states": states(j), "codes": j.get("gate_codes")})
# C04 valid reviewed revision stays acceptable: receipts at r2 (full and abbreviated ids)
rc, j, _, _ = runp(packet(G3, SUB2, {g: receipt(g, R2, FILES2) for g in G3}))
r2b = {g: receipt(g, R2[:7], FILES2) for g in G3}; rcb, jb, _, _ = runp(packet(G3, SUB2, r2b))
rec("C04", rc == 0 and j.get("ok") is True and rcb == 0 and jb.get("ok") is True and set(states(jb).values()) == {"current"}, {"rc": rc, "rc_abbrev": rcb, "states_abbrev": states(jb), "codes": jb.get("gate_codes")})
# C05 recovery: re-run only the stale gates at r2, keep ux from r1
rc, j, _, _ = runp(packet(G3, SUB2, {"security": receipt("security", R2, FILES2), "functional": receipt("functional", R2, FILES2), "ux": receipt("ux", R1, FILES1)}))
rec("C05", rc == 0 and j.get("ok") is True and states(j) == {"security": "current", "functional": "current", "ux": "carried_forward"}, {"rc": rc, "states": states(j)})
# C06 revisions differ with no digest cover -> stale
r = receipt("security", R1, FILES1); r["reviewed"]["digests"] = {}
rc, j, _, _ = runp(packet(["security"], SUB2, {"security": r})); rec("C06", rc == 1 and j.get("ok") is False and states(j).get("security") in ("stale", "unbound"), {"rc": rc, "states": states(j), "codes": j.get("gate_codes")})
r = receipt("security", R1, FILES1); r["reviewed"].pop("digests")
rcb, jb, _, _ = runp(packet(["security"], SUB2, {"security": r})); rec("C06b", True, {"rc": rcb, "states": states(jb), "codes": jb.get("gate_codes")}, graded=False)
# C07 unbound: subject named, receipt without reviewed
rc, j, _, _ = runp(packet(["security"], SUB2, {"security": receipt("security", reviewed=False)}))
rec("C07", rc == 1 and "UNBOUND_GATE_EVIDENCE" in (j.get("gate_codes") or []) and states(j).get("security") == "unbound", {"rc": rc, "states": states(j), "codes": j.get("gate_codes")})
# C08 contradictory receipts, no subject -> REVISION_CONFLICT; same revision, no subject -> passes
rc, j, _, _ = runp(packet(["security", "functional"], None, {"security": receipt("security", R1, FILES1), "functional": receipt("functional", R2, FILES2)}))
rc2, j2, _, _ = runp(packet(["security", "functional"], None, {"security": receipt("security", R2, FILES2), "functional": receipt("functional", R2, FILES2)}))
rec("C08", rc == 1 and "REVISION_CONFLICT" in (j.get("gate_codes") or []) and rc2 == 0, {"rc_conflict": rc, "codes": j.get("gate_codes"), "rc_agree": rc2, "codes_agree": j2.get("gate_codes")})
# C09 legacy shape unchanged: a packet with no binding has no revision_binding and the same keys as the base
rec("C09", "revision_binding" not in json.dumps(j0) and set(j0) >= {"ok", "status", "gate_codes", "evidence"}, {"keys": sorted(j0), "evidence_keys": sorted(j0.get("evidence") or {})})
# C10 malformed bindings fail boundedly: INVALID_PACKET / INVALID_GATE_EVIDENCE, short output, fast
badrev = ["XYZ", "A1B2C3D4", "a1b2c3", "a" * 65, "sha256:" + "a" * 63, "sha256:" + "g" * 64, "", 1234567, None]
c10 = {}
for i, rv in enumerate(badrev):
    rc, j, n, dt = runp(packet(["security"], {"revision": rv, "digests": SUB2["digests"]}, {"security": receipt("security", R2, FILES2)}))
    c10["subject_rev_%d" % i] = [rc, "INVALID_PACKET" in (j.get("gate_codes") or []), n < 4000]
    r = receipt("security", R2, FILES2); r["reviewed"]["revision"] = rv; rc, j, n, dt = runp(packet(["security"], SUB2, {"security": r}))
    c10["reviewed_rev_%d" % i] = [rc, "INVALID_GATE_EVIDENCE" in (j.get("gate_codes") or []), n < 4000]
for k, dg in {"digest_nonhex": {"app/login.py": "zz"}, "digest_upper": {"app/login.py": H("x").upper()}, "path_escape": {"../x.py": H("x")},
              "path_abs": {"/etc/passwd": H("x")}, "digests_list": ["app/login.py"], "digest_int": {"app/login.py": 5}}.items():
    rc, j, n, dt = runp(packet(["security"], {"revision": R2, "digests": dg}, {"security": receipt("security", R2, FILES2)}))
    c10["subject_" + k] = [rc, "INVALID_PACKET" in (j.get("gate_codes") or []), n < 4000]
big = {"app/f%05d.py" % i: H(str(i)) for i in range(10001)}
rc, j, n, dt = runp(packet(["security"], {"revision": R2, "digests": big}, {"security": receipt("security", R2, FILES2)}))
c10["subject_10001_paths"] = [rc, "INVALID_PACKET" in (j.get("gate_codes") or []), n < 4000, round(dt, 2)]
ok10 = all(v[0] == 1 and v[1] and v[2] for v in c10.values())
rec("C10", ok10, c10)
# C11 at most 10000 paths accepted (boundary) and evaluation stays fast; 10000-file subject, 3 gates, 1 changed file
s10 = {"src/f%05d.py" % i: H(str(i)) for i in range(10000)}; s10b = dict(s10, **{"src/f00042.py": H("changed")})
rv = lambda dg: {"revision": R1, "digests": dg}
rcs = {"security": {"gate": "security", "role": "security-auditor", "summary": "s", "artifacts": ["r.md"], "reviewed": rv({k: v for k, v in s10.items() if k < "src/f00100"})},
       "functional": {"gate": "functional", "role": "qa-engineer", "summary": "s", "artifacts": ["r.md"], "reviewed": rv({k: v for k, v in s10.items() if k >= "src/f05000"})}}
rc, j, n, dt = runp(packet(["security", "functional"], {"revision": R2, "digests": s10b}, rcs))
rec("C11", rc == 1 and states(j) == {"security": "stale", "functional": "carried_forward"} and dt < 10, {"rc": rc, "states": states(j), "seconds": round(dt, 2)})
# C12 digest CLI on real files matches hashlib and is usable as a subject
rc, o, e, _ = cli("digest", "r2", "app", "web", "notes", "--revision", R2)
try: dj = json.loads(o)
except Exception: dj = {}
rcp, jp, _, _ = runp(packet(G3, dj if dj else {"revision": "bad"}, {g: receipt(g, R2, FILES2) for g in G3}))
rec("C12", rc == 0 and dj.get("revision") == R2 and dj.get("digests") == SUB2["digests"] and rcp == 0, {"rc": rc, "matches": dj.get("digests") == SUB2["digests"], "as_subject_rc": rcp, "err": e[:160]})
# C13 digest refusals: exit 2 for escape, symlink, missing, empty folder, bad revision, oversize (64 MiB)
os.symlink(os.path.join(T, "r2", "app", "login.py"), os.path.join(T, "r2", "link.py")); os.makedirs(os.path.join(T, "r2", "empty"))
with open(os.path.join(T, "r2", "big.bin"), "wb") as f: f.truncate(64 * 1024 * 1024 + 1)
os.makedirs(os.path.join(T, "r2", "linkdir")); os.symlink(os.path.join(T, "r1", "app"), os.path.join(T, "r2", "linkdir", "app"))
c13 = {k: cli("digest", "r2", *a)[0] for k, a in {"escape": ["../r1/app"], "symlink_file": ["link.py"], "missing": ["nope"], "empty_dir": ["empty"],
       "bad_revision": ["app", "--revision", "XYZ"], "oversize": ["big.bin"], "symlink_in_folder": ["linkdir"], "absolute": [os.path.join(T, "r1", "app")]}.items()}
rec("C13", all(v == 2 for v in c13.values()), c13)
for p in ("link.py", "big.bin"): os.remove(os.path.join(T, "r2", p))
# Closures and reopen through the API
spec = importlib.util.spec_from_file_location("m05_engine", Q); E = importlib.util.module_from_spec(spec); sys.modules["m05_engine"] = E
try: spec.loader.exec_module(E)
except Exception: pass  # v2: register before exec (dataclasses needs it; v1 crashed before any closure row)
try:
    def finding(**kw):
        d = dict(finding_id="F-LH-1", defect_kind="security", severity="S2", title="Login accepts blank user", evidence=["report: blank user logs in"],
                 accountable_role="backend-engineer", reporter_role="security-auditor", status="open", verifier_role="security-auditor")
        d.update(kw); return E.Finding(**d)
    IND = ["retest at fix: blank user now refused"]
    def cc(f, **kw): return E.can_close_finding(f, closer_role=kw.pop("closer", "security-auditor"), independent_evidence=kw.pop("ev", IND), **kw)
    a = cc(finding(), subject_revision=R2, verified_revision=R2); b = cc(finding(), subject_revision=R2, verified_revision=R1)
    c = cc(finding(), subject_revision=R2); d = cc(finding(), subject_revision=R2, verified_revision="XYZ"); e0 = cc(finding())
    ab = cc(finding(), subject_revision=R2, verified_revision=R2[:9])
    rec("C14", a == (True, []) and b == (False, ["STALE_CLOSURE_EVIDENCE"]) and c == (False, ["MISSING_VERIFIED_REVISION"]) and d[0] is False and "INVALID_REVISION" in d[1] and e0[0] is True,
        {"current": a, "stale": b, "missing": c, "malformed": d, "legacy_no_revision": e0, "abbrev_verified": ab})
    # C15 self-approval vs independent; corrected retry with new evidence
    s = cc(finding(), closer="backend-engineer", subject_revision=R2, verified_revision=R2); n = cc(finding(), ev=["report: blank user logs in"], subject_revision=R2, verified_revision=R2)
    rec("C15", s[0] is False and "SELF_APPROVAL_FORBIDDEN" in s[1] and n[0] is False and "NON_INDEPENDENT_CLOSURE_EVIDENCE" in n[1], {"self": s, "non_independent": n})
    # C16 close at r1, then r2 lands: closure_is_current STALE_CLOSURE; reopen; re-close needs new evidence; corrected retry passes at r2
    f1, k1 = E.close_finding(finding(), closer_role="security-auditor", independent_evidence=IND, subject_revision=R1, verified_revision=R1)
    cur1 = E.closure_is_current(f1, R1); cur2 = E.closure_is_current(f1, R2)
    fs, ks = E.reopen_finding(f1, reason="short", current_revision=R2, reopened_by_role="security-auditor")
    fo, ko = E.reopen_finding(f1, reason="login changed again in revision two", current_revision=R2, reopened_by_role="security-auditor")
    again = cc(fo, subject_revision=R2, verified_revision=R2)
    fixed = cc(fo, ev=["retest at r2: blank user refused, new test test_blank_user"], subject_revision=R2, verified_revision=R2)
    f0, _ = E.close_finding(finding(), closer_role="security-auditor", independent_evidence=IND)
    rec("C16", k1 == [] and f1.status == "closed" and f1.closed_at_revision == R1 and cur1 == (True, []) and cur2 == (False, ["STALE_CLOSURE"])
        and ks == ["REOPEN_REASON_REQUIRED"] and ko == [] and fo.status == "open" and not fo.closed_by_role and not fo.closed_at_revision
        and again[0] is False and fixed == (True, []) and E.closure_is_current(f0, R2) == (False, ["UNBOUND_CLOSURE"]) and E.closure_is_current(finding(), R2) == (False, ["NOT_CLOSED"]),
        {"close_r1": k1, "cur_r1": cur1, "cur_r2": cur2, "reopen_short": ks, "reopen": ko, "status": fo.status, "reclose_old_evidence": again, "reclose_new": fixed})
    # C17 waivers keep their meaning: valid waiver closes a waived finding at any revision; expired/revoked/self-approved do not
    fut = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"); past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    def wv(**kw):
        d = dict(waiver_id="W-LH-1", finding_id="F-LH-1", requested_by_role="backend-engineer", approved_by_role="engineering-director", human_authority=True,
                 justification="accepted until the login rewrite ships", expires_at=fut, status="active"); d.update(kw); return E.Waiver(**d)
    fw = finding(status="waived", waiver_id="W-LH-1")
    w_ok = [cc(fw, closer="backend-engineer", ev=[], waiver=wv(), subject_revision=s_, verified_revision=v_) for s_, v_ in ((R2, R1), (R2, None), (None, None))]
    w_exp = cc(fw, closer="backend-engineer", ev=[], waiver=wv(expires_at=past), subject_revision=R2, verified_revision=R2)
    w_rev = cc(fw, closer="backend-engineer", ev=[], waiver=wv(status="rejected"), subject_revision=R2, verified_revision=R2)
    w_self = cc(fw, closer="backend-engineer", ev=[], waiver=wv(approved_by_role="backend-engineer"), subject_revision=R2, verified_revision=R2)
    fwc = dataclasses.replace(fw, status="closed", closed_by_role="backend-engineer")
    rec("C17", all(x[0] is True for x in w_ok) and w_exp[0] is False and "WAIVER_EXPIRED" in w_exp[1] and w_rev[0] is False and "WAIVER_NOT_ACTIVE" in w_rev[1]
        and w_self[0] is False and "WAIVER_SELF_APPROVAL_FORBIDDEN" in w_self[1], {"valid_any_rev": w_ok, "expired": w_exp, "revoked": w_rev, "self_approved": w_self})
    rec("C17b", True, {"reopen_waived": E.reopen_finding(fwc, reason="waived finding reopened by hand", current_revision=R2, reopened_by_role="security-auditor")[1]}, graded=False)
    fwk, kw_ = E.close_finding(fw, closer_role="backend-engineer", independent_evidence=[], waiver=wv(), subject_revision=R2)
    rec("C17c", True, {"close_via_waiver": kw_, "status": fwk.status, "closure_is_current_r2": E.closure_is_current(fwk, R2),
                       "reopen_after_waiver_close": E.reopen_finding(fwk, reason="waived finding reopened by hand", current_revision=R2, reopened_by_role="security-auditor")[1]}, graded=False)
except Exception as ex:
    for i in ("C14", "C15", "C16", "C17"):
        if not any(r["id"] == i for r in res): rec(i, False, {"error": repr(ex)[:160]})
# C18 run-closure fixture accepts both revisions through the CLI
FD = dict(finding_id="F-LH-1", defect_kind="security", severity="S2", title="Login accepts blank user", evidence=["report: blank user logs in"], accountable_role="backend-engineer", reporter_role="security-auditor", status="open", verifier_role="security-auditor")
fx = {"fixture_kind": "closure", "finding": FD, "closer_role": "security-auditor", "independent_evidence": IND, "expect_blocked": True, "subject_revision": R2, "verified_revision": R1}
open(os.path.join(T, "c.json"), "w").write(json.dumps(fx)); rc, o, e, _ = cli("run", "c.json")
try: cj = json.loads(o)
except Exception: cj = {}
rec("C18", rc == 0 and "STALE_CLOSURE_EVIDENCE" in (cj.get("gate_codes") or []), {"rc": rc, "codes": cj.get("gate_codes"), "err": e[:120]})
# C19 self-test still passes
rc, o, e, _ = cli("self-test"); rec("C19", rc == 0, {"rc": rc, "tail": (o + e)[-160:]})
shutil.rmtree(T, ignore_errors=True)
json.dump(res, open(os.path.join(OUT, "m05-oracle.json"), "w"), indent=1)
for r in res: print(r["id"], r["result"], json.dumps(r["detail"], default=str)[:300])
g = [r for r in res if r["result"] != "OBS"]; print("M05 ORACLE %d/%d" % (sum(r["result"] == "PASS" for r in g), len(g)))
