#!/usr/bin/env python3
"""M02 r3 probe (Grok self-validation, not independent review). Written from the root finding for G02
(blank-looking or disguised UNRESOLVED deploy answers; deep or corrupt journal and lock JSON escaping as
tracebacks) and the G02 r3 commit message, with inputs chosen here, not copied from the G02 r3 tests.
Drives activate() in process and the CLI as a subprocess. P rows are scored; X rows are observations.
Usage: PY m02r3_probe.py REPO OUT.json"""
import json, os, shutil, subprocess, sys, tempfile, importlib.util, io, contextlib
REPO = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(REPO, "employees/product-project/project-onboarding/activate.py")
spec = importlib.util.spec_from_file_location("act", TOOL); act = importlib.util.module_from_spec(spec); spec.loader.exec_module(act)
ROWS = []
def row(rid, name, ok, detail, scored=True): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "scored": scored, "detail": detail})
def base(**kw):
    d = {"name": "Probe Project", "project_type": "website", "brief": "a small site"}; d.update(kw); return d
def run_api(intake, pre=None, resume=False):
    t = tempfile.mkdtemp(prefix="m02r3-"); root = os.path.join(t, "proj")
    if pre: pre(root)
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            r = act.activate(root, intake, resume=resume)
        out = ("ok", r)
    except BaseException as e:  # a raise is the defect class under test
        out = ("raised", "%s: %s" % (type(e).__name__, str(e)[:120]))
    files = sorted(os.listdir(root)) if os.path.isdir(root) else None
    shutil.rmtree(t, ignore_errors=True)
    return out, files
def deploy_state(r):
    return r["status"], (r.get("intake") or {}).get("deploy_model")

# P01 blank-looking answers outside the r3 test list must stay unresolved
blank = {"hangul jungseong filler U+1160": "\u1160", "combining grapheme joiner U+034F": "\u034f", "khmer inherent U+17B4 U+17B5": "\u17b4\u17b5",
         "variation selector alone U+FE0F": "\ufe0f", "tag space U+E0020": "\U000e0020", "combining acute alone": "\u0301\u0301",
         "halfwidth hangul filler + ZWSP": "\uffa0\u200b", "braille blank x3 + ideographic space": "\u2800\u2800\u3000\u2800",
         "mongolian free variation selector U+180B": "\u180b", "invisible separator U+2063": "\u2063"}
bad = {}
for k, v in blank.items():
    (kind, r), _ = run_api(base(deploy_model=v))
    if kind != "ok" or r["status"] == "complete" or deploy_state(r)[1] is not None: bad[k] = (kind, r if kind != "ok" else deploy_state(r))
row("P01", "blank-looking deploy answers (10 not in the r3 tests) stay UNRESOLVED and not complete", not bad, bad or "all unresolved")
# P02 disguised UNRESOLVED
disg = {"fullwidth": "\uff35\uff2e\uff32\uff25\uff33\uff2f\uff2c\uff36\uff25\uff24", "ZWSP inside": "UN\u200bRESOLVED", "combining mark inside": "U\u0301NRESOLVED",
        "hangul filler prefix": "\u3164unresolved", "soft hyphen inside": "Unre\u00adsolved", "math bold (NFKC)": "\U0001d414\U0001d40d\U0001d411\U0001d404\U0001d412\U0001d40e\U0001d40b\U0001d415\U0001d404\U0001d403",
        "circled (NFKC)": "\u24ca\u24c3\u24c7\u24ba\u24c8\u24c4\u24c1\u24cb\u24ba\u24b9", "lower + trailing note": "unresolved - ask the owner"}
bad = {}
for k, v in disg.items():
    (kind, r), _ = run_api(base(deploy_model=v))
    if kind != "ok" or r["status"] == "complete" or deploy_state(r)[1] is not None: bad[k] = (kind, r if kind != "ok" else deploy_state(r))
row("P02", "disguised UNRESOLVED (8 spellings) stays unresolved", not bad, bad or "all unresolved")
# P03 controls: real answers with marks or non-Latin script are recorded and complete
ctl = {"accented": "Caf\u00e9 site deploys via Vercel from main", "cjk": "\u4e3b\u5206\u652f\u81ea\u52a8\u90e8\u7f72", "arrow": "main \u2192 live on push",
       "mentions unresolved mid-text": "deploys from main; DNS question unresolved", "decomposed accent": "Cafe\u0301 deploys nightly"}
bad = {}
for k, v in ctl.items():
    (kind, r), _ = run_api(base(deploy_model=v))
    if kind != "ok" or r["status"] != "complete" or not deploy_state(r)[1]: bad[k] = (kind, r if kind != "ok" else deploy_state(r))
row("P03", "controls: 5 real deploy answers (accents, CJK, arrow, mid-text 'unresolved', decomposed accent) are complete and recorded", not bad, bad or "all complete")
# P04 deep or corrupt journal and lock: bounded result, nothing raised, owner files kept
J = act.JOURNAL; L = act.LOCK
def plant(name, data):
    def f(root):
        os.makedirs(root, exist_ok=True)
        open(os.path.join(root, "OWNER.txt"), "w").write("mine")
        open(os.path.join(root, name), "wb").write(data)
    return f
cases = {"journal deep objects": (J, b'{"a":' * 100000 + b"1" + b"}" * 100000), "journal deep mixed": (J, b'[{"x":' * 60000 + b"0" + b"}]" * 60000),
         "journal unclosed deep": (J, b"[" * 300000), "lock deep": (L, b"[" * 300000), "lock deep objects": (L, b'{"p":' * 100000 + b"1" + b"}" * 100000),
         "journal huge int": (J, b'{"schema": ' + b"9" * 20000 + b"}"), "journal latin-1": (J, b'{"schema": "caf\xe9"}')}
bad = {}
for k, (name, data) in cases.items():
    for resume in (False, True):
        (kind, r), files = run_api(None if resume else base(deploy_model="vercel"), pre=plant(name, data), resume=resume)
        if kind != "ok" or r["status"] not in ("blocked", "invalid", "failed") or "OWNER.txt" not in (files or []):
            bad["%s resume=%s" % (k, resume)] = (kind, r if kind != "ok" else (r["status"], r["errors"][:1]))
row("P04", "deep, unclosed, huge-int and non-UTF-8 journal or lock (7 shapes, activate and resume): bounded blocked/invalid, owner file kept", not bad, bad or "all bounded")
# P05 lone surrogates through the API and a Latin-1 byte through the CLI
bad = {}
for field in ("name", "brief", "deploy_model"):
    (kind, r), files = run_api(base(**{field: "Bad\udcffValue"}))
    if kind != "ok" or r["status"] != "invalid" or files is not None: bad["api " + field] = (kind, r if kind != "ok" else (r["status"], files))
t = tempfile.mkdtemp(prefix="m02r3-cli-")
p = subprocess.run([sys.executable, TOOL, "activate", os.path.join(t, "p").encode(), b"--name", b"Caf\xe9", b"--type", b"website"], capture_output=True)
if p.returncode != 2 or b"Traceback" in p.stderr or os.path.exists(os.path.join(t, "p")): bad["cli latin-1 name"] = (p.returncode, p.stderr[-200:].decode("utf-8", "replace"))
shutil.rmtree(t, ignore_errors=True)
row("P05", "lone surrogate in name/brief/deploy (API) and a Latin-1 byte in --name (CLI): invalid, exit 2, no traceback, nothing created", not bad, bad or "all invalid")
# P06 regression check against G02 r2 bbe682b: answers that start with the word UNRESOLVED and go on were partial there
reg = {"then words": "UNRESOLVED ask the owner", "title case": "Unresolved until the owner decides", "lower": "unresolved pending call",
       "colon": "UNRESOLVED: main=live", "comma": "Unresolved, ask owner", "nbsp then words": "UNRESOLVED\u00a0ask the owner",
       "tab then words": "unresolved\tpending"}
bad = {}
for k, v in reg.items():
    (kind, r), _ = run_api(base(deploy_model=v))
    if kind != "ok" or r["status"] == "complete" or deploy_state(r)[1] is not None: bad[k] = (kind, r if kind != "ok" else deploy_state(r))
row("P06", "regression vs r2: 7 answers starting with UNRESOLVED followed by words stay unresolved (partial at r2 bbe682b)", not bad, bad or "all unresolved")
# X01 observations: homoglyph and placeholder answers (not in the finding; recorded only)
obs = {}
for k, v in {"cyrillic E homoglyph": "UNR\u0415SOLVED", "TBD": "TBD", "question mark": "?", "dash": "-", "n/a": "n/a", "unresolved items line": "Unresolved items: none; deploys via Vercel"}.items():
    (kind, r), _ = run_api(base(deploy_model=v))
    obs[k] = (r["status"], deploy_state(r)[1]) if kind == "ok" else (kind, r)
row("X01", "observation: homoglyph and placeholder deploy answers", True, obs, scored=False)
sc = [r for r in ROWS if r["scored"]]
json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
for r in ROWS: print("%s %s %s | %s" % (r["row"], "PASS" if r["pass"] else "FAIL", r["name"], json.dumps(r["detail"], default=str)[:300]))
print("M02R3 PROBE %d/%d" % (sum(r["pass"] for r in sc), len(sc)))
