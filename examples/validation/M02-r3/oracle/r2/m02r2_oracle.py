#!/usr/bin/env python3
"""M02 r2 oracle (Grok self-validation, not independent review).

Black box: drives only the CLI documented in SKILL.md (activate / resume / --json).
Usage: python m02r2_oracle.py [--only C01,C04] -- <python> <path/to/activate.py>
Every check is PASS or FAIL; there is no SKIP. A candidate that creates no project files is ENTRY_ABSENT (FAIL).
Lines starting with REC are recorded observations (not graded).
"""
import hashlib, json, os, shutil, signal, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
INJECT = HERE / "inject"
CMD = []
FILES = ("STATUS.md", "Scope/ROUND-PLAN.md", "Delivery/CREDENTIALS.md")
J, LOCK = ".solaris-activation.json", ".solaris-activation.lock"
REC = []


class Fail(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Fail(msg)


def run(*args, kill_at=0, timeout=60, raw=False):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if kill_at:
        env["PYTHONPATH"] = str(INJECT)
        env["M02R2_KILL_AT"] = str(kill_at)
    argv = CMD + [a if isinstance(a, bytes) else str(a) for a in args]
    p = subprocess.run(argv, capture_output=True, env=env, timeout=timeout)
    out, err = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    js = None
    if "--json" in args:
        try:
            js = json.loads(out)
        except ValueError:
            js = None
    return p.returncode, out, err, js


def act(root, *extra, **kw):
    return run("activate", root, *extra, "--json", **kw)


def resume(root, **kw):
    return run("resume", root, "--json", **kw)


def st(js):
    return (js or {}).get("status")


def tree(path):
    out = {}
    path = Path(path)
    if not os.path.lexists(path):
        return out
    for dp, dns, fns in os.walk(path):
        for n in dns + fns:
            p = Path(dp) / n
            rel = str(p.relative_to(path))
            s = os.lstat(p)
            if os.path.islink(p):
                out[rel] = ("L", os.readlink(p))
            elif os.path.isdir(p):
                out[rel] = ("D", oct(s.st_mode & 0o777))
            else:
                out[rel] = ("F", hashlib.sha256(p.read_bytes()).hexdigest() if s.st_mode & 0o400 else "unreadable")
    return out


def text(root, rel):
    p = Path(root) / rel
    return p.read_text(encoding="utf-8") if p.is_file() and not p.is_symlink() else None


def entry_present(root):
    need(all((Path(root) / f).is_file() for f in FILES), "ENTRY_ABSENT: generated files missing after activation")


def deploy_lines(root):
    t = text(root, "STATUS.md") or ""
    return [l for l in t.splitlines() if l.startswith("DEPLOY-MODEL:")]


def first_marker(root):
    t = text(root, "STATUS.md") or ""
    i = t.find("DEPLOY-MODEL:")
    return t[i:].splitlines()[0] if i >= 0 else None


def temps(root):
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*.activation-tmp"))


def sentinel(base):
    o = Path(base) / "outside"
    (o / "sub").mkdir(parents=True)
    (o / "keep.txt").write_text("outside sentinel\n")
    (o / "sub" / "STATUS.md").write_text("outside status\n")
    return o


def names_in(root, names):
    found = set()
    for f in FILES:
        t = text(root, f) or ""
        found |= {n for n in names if n in t}
    return found


def unresolved(root, js):
    dl = deploy_lines(root)
    return (st(js) != "complete" and len(dl) == 1 and dl[0].startswith("DEPLOY-MODEL: UNRESOLVED")
            and not (js.get("intake") or {}).get("deploy_model"))


# ---------------------------------------------------------------- checks
def c01_clean(T):
    o = sentinel(T); before = tree(o)
    r = T / "p"
    args = ("--name", "Northwind Portal", "--type", "web app", "--deploy-model", "staging on PR merge; prod by owner click",
            "--brief", "Customer portal rebuild", "--credential", "system=github;username=nw-bot;location=1Password/Eng/GitHub")
    rc, out, err, js = act(r, *args)
    need(js is not None, f"no JSON result (rc={rc})")
    entry_present(r)
    need(rc == 0 and st(js) == "complete", f"first run rc={rc} status={st(js)}")
    need(deploy_lines(r) == ["DEPLOY-MODEL: staging on PR merge; prod by owner click"], f"deploy lines {deploy_lines(r)}")
    for f in FILES:
        need("Northwind Portal" in text(r, f), f"{f} does not name the project")
    need("1Password/Eng/GitHub" in text(r, "Delivery/CREDENTIALS.md"), "credential location missing")
    for d in ("Scope", "Development", "Delivery", "Assets"):
        need((r / d).is_dir() and not (r / d).is_symlink(), f"{d}/ not a real dir")
    t1 = tree(r)
    rc2, _, _, js2 = act(r, *args)
    need(rc2 == 0 and st(js2) == "complete" and tree(r) == t1, "rerun not byte-identical/complete")
    rc3, _, _, js3 = resume(r)
    need(rc3 == 0 and st(js3) == "complete" and tree(r) == t1, "resume not byte-identical/complete")
    need(not os.path.exists(r / LOCK) and temps(r) == [], "lock or temp left")
    need(tree(o) == before, "outside changed")
    return "2 activations + resume byte-identical, 1 verbatim DEPLOY-MODEL line, 3 docs name project"


def c02_owner_docs(T):
    r = T / "p"; (r / "Scope").mkdir(parents=True)
    (r / "STATUS.md").write_text("# owner status\nDEPLOY-MODEL: owner wrote this\n")
    (r / "Scope/ROUND-PLAN.md").write_text("owner plan\n")
    (r / "Assets").mkdir(); (r / "Assets/logo.svg").write_text("<svg/>")
    keep = {k: v for k, v in tree(r).items()}
    for i in range(2):
        rc, out, err, js = act(r, "--name", "Owner Co", "--type", "website", "--deploy-model", "main")
        need(js is not None, "no JSON")
        need(st(js) not in ("complete", None), f"run {i}: status {st(js)} despite owner conflicts")
        now = tree(r)
        for k, v in keep.items():
            need(now.get(k) == v, f"owner path {k} changed")
    need((r / "Delivery/CREDENTIALS.md").is_file(), "ENTRY_ABSENT: missing doc not created")
    need("conflict_preserved" in json.dumps(js.get("artifacts")), "conflict not reported")
    return "owner STATUS/plan/asset byte-identical over 2 runs, conflict reported, not complete"


def _git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd)] + list(a), capture_output=True, text=True,
                          env=dict(os.environ, GIT_AUTHOR_NAME="o", GIT_AUTHOR_EMAIL="o@localhost",
                                   GIT_COMMITTER_NAME="o", GIT_COMMITTER_EMAIL="o@localhost"))


def gitstate(r):
    g = Path(r) / ".git"
    objs = sorted(str(p.relative_to(g)) for p in (g / "objects").rglob("*") if p.is_file())
    return (_git(r, "for-each-ref").stdout, (g / "HEAD").read_bytes(), (g / "index").read_bytes() if (g / "index").exists() else b"",
            objs, (g / "config").read_bytes(), _git(r, "status", "--porcelain=v1", "--untracked-files=all").stdout)


def c03_git(T):
    o = sentinel(T); before = tree(o)
    r = T / "repo"; r.mkdir()
    _git(r, "init", "-q", "-b", "trunk")
    (r / "a.txt").write_text("1\n"); _git(r, "add", "a.txt"); _git(r, "commit", "-qm", "c1")
    (r / "a.txt").write_text("2\n"); _git(r, "commit", "-qam", "c2"); _git(r, "branch", "feature")
    (r / "b.txt").write_text("staged\n"); _git(r, "add", "b.txt")
    (r / "a.txt").write_text("unstaged\n"); (r / "u.txt").write_text("untracked\n")
    g0 = gitstate(r)
    for extra in (("--code",), ("--code",), ("--code", "--init-git")):
        rc, _, _, js = act(r, "--name", "Repo Co", "--type", "web app", "--deploy-model", "main", *extra)
        need(js is not None and st(js) in ("complete", "partial"), f"git run status {st(js)}")
        g1 = gitstate(r)
        need(g1[:5] == g0[:5], "Git refs/HEAD/index/objects/config changed")
    entry_present(r)
    need(g1[5].count("\n") >= g0[5].count("\n"), "status lost entries")
    u = T / "unborn"; u.mkdir(); _git(u, "init", "-q"); (u / "s.txt").write_text("s\n"); _git(u, "add", "s.txt")
    gu = gitstate(u)
    rc, _, _, js = act(u, "--name", "Unborn", "--type", "web app", "--deploy-model", "main", "--code", "--init-git")
    need(js is not None and st(js) != "complete", f"unborn status {st(js)} (first commit is owner step)")
    need(gitstate(u)[:5] == gu[:5] and _git(u, "rev-parse", "--verify", "HEAD").returncode != 0, "unborn repo changed/committed")
    need(tree(o) == before, "outside changed")
    return "existing repo x3 runs and unborn staged repo: refs/HEAD/index/objects/config identical, no commit"


def _alpha(T, name="alpha"):
    a = T / name
    rc, _, _, js = act(a, "--name", "Alpha Corp", "--type", "web app", "--deploy-model", "production: main=live",
                       "--brief", "alpha brief", "--credential", "system=aws;username=alpha;location=Vault/alpha")
    need(js is not None and st(js) == "complete", f"alpha setup status {st(js)}")
    entry_present(a)
    return a


def c04_binding(T):
    a = _alpha(T)
    notes = []
    # copied folder, omitted deploy
    g = T / "gamma"; shutil.copytree(a, g, symlinks=True)
    rc, out, err, js = act(g, "--name", "Gamma Inc", "--type", "website")
    need(js is not None, "no JSON")
    need(unresolved(g, js), f"copied folder: status {st(js)} deploy {deploy_lines(g)}")
    need("main=live" not in (text(g, "STATUS.md") + text(g, "Scope/ROUND-PLAN.md")), "live intent leaked to copied project")
    need("alpha" not in (text(g, "Delivery/CREDENTIALS.md") or "").lower(), "credentials inherited by copied project")
    need("deploy_model" not in (js.get("inherited") or []), "inherited lists deploy_model")
    rc, _, _, js = act(g, "--name", "Gamma Inc", "--type", "website")
    need(unresolved(g, js), f"second run after rebind: {st(js)} {deploy_lines(g)}")
    notes.append("copy x2 UNRESOLVED")
    # copied folder, human report
    d = T / "delta"; shutil.copytree(a, d, symlinks=True)
    rc, out, err, _ = run("activate", d, "--name", "Delta", "--type", "website")
    need("main=live" not in out and "(complete)" not in out, f"report: {out.splitlines()[:2]}")
    # copied folder, resume refused, nothing changed
    e = T / "eps"; shutil.copytree(a, e, symlinks=True); te = tree(e)
    rc, _, _, js = resume(e)
    need(rc != 0 and st(js) == "blocked" and tree(e) == te, f"resume in copy: rc={rc} {st(js)}")
    # journal only
    z = T / "zeta"; z.mkdir(); shutil.copy2(a / J, z / J)
    rc, _, _, js = act(z, "--name", "Zeta", "--type", "game")
    need(js is not None and unresolved(z, js), f"journal-only copy: {st(js)} {deploy_lines(z)}")
    # older journal without project_root, in a copy
    h = T / "eta"; shutil.copytree(a, h, symlinks=True)
    jj = json.loads((h / J).read_text()); jj.pop("project_root", None); (h / J).write_text(json.dumps(jj))
    rc, _, _, js = act(h, "--name", "Eta", "--type", "game")
    need(js is not None and unresolved(h, js), f"journal without project_root: {st(js)}")
    # positive control: same folder carries over and says so
    rc, out, err, _ = run("activate", a, "--name", "Alpha Corp Renamed")
    need(rc == 0 and "main=live" in out and "carried over" in out, f"same-folder carry-over control: {out.splitlines()[:2]}")
    # recorded: moved folder
    m = T / "alpha-moved"; os.rename(a, m)
    rc, _, _, js = resume(m)
    REC.append(f"REC c04 moved-folder resume: rc={rc} status={st(js)}")
    return "copied folder x2, report, resume refused, journal-only, rootless journal: UNRESOLVED; same-folder control carried over"


INVIS = ["", "   ", "\t", "\u200b", "\ufeff", "\u2060", "\u200b\ufeff \u00a0", "\u180e", "\u00ad", "\u3000\u200d",
         "UNRESOLVED", "unresolved", "Unresolved, ask owner", "  UNRESOLVED  ", "UNRESOLVED: main=live"]
REC_INVIS = {"hangul_filler": "\u3164", "braille_blank": "\u2800", "combining_acute": "\u0301", "zw_then_UNRESOLVED": "\u200bUNRESOLVED",
             "fullwidth_UNRESOLVED": "\uff35\uff2e\uff32\uff25\uff33\uff2f\uff2c\uff36\uff25\uff24", "quoted_UNRESOLVED": "'UNRESOLVED'", "TBD": "TBD"}


def c05_deploy_blank(T):
    for i, v in enumerate(INVIS):
        r = T / f"b{i}"
        rc, _, _, js = act(r, "--name", "Blank Co", "--type", "web app", "--deploy-model", v)
        need(js is not None, f"{v!r}: no JSON")
        entry_present(r)
        need(unresolved(r, js), f"deploy {v!r}: status {st(js)} lines {deploy_lines(r)}")
    for k, v in REC_INVIS.items():
        r = T / f"rec-{k}"
        rc, _, _, js = act(r, "--name", "Rec Co", "--type", "web app", "--deploy-model", v)
        REC.append(f"REC c05 {k}: status={st(js)} deploy_recorded={(js or {}).get('intake', {}).get('deploy_model')!r}")
    for v in ("main is live after owner sign-off; unresolved: staging", "Vercel preview only"):
        r = T / f"pos{len(v)}"
        rc, _, _, js = act(r, "--name", "Pos Co", "--type", "web app", "--deploy-model", v)
        need(js is not None and st(js) == "complete" and deploy_lines(r) == [f"DEPLOY-MODEL: {v}"], f"positive {v!r}: {st(js)}")
    r = T / "zwname"
    rc, _, _, js = act(r, "--name", "\u200b\u2060", "--type", "web app")
    need(rc != 0 and not r.exists(), "invisible-only name accepted")
    return f"{len(INVIS)} blank/invisible/UNRESOLVED answers -> UNRESOLVED not complete; 2 positive controls verbatim; invisible name refused"


C06_FAILS = []


def _no_tb(rc, out, err, js, label):
    if "Traceback" in err:
        C06_FAILS.append(f"{label}: traceback {err.strip().splitlines()[-1][:90]}")
    elif not (js is not None and st(js) in ("blocked", "invalid", "failed") and rc != 0):
        C06_FAILS.append(f"{label}: rc={rc} status={st(js)}")


def c06_malformed(T):
    C06_FAILS.clear()
    a = _alpha(T)
    good = (a / J).read_bytes()
    bad = {"files_list": None, "pending_list": None, "root_int": None, "top_list": b"[1,2]", "files_null": None, "intake_list": None,
           "deep": b"[" * 200000 + b"]" * 200000, "deep_obj": b'{"a":' * 100000 + b"1" + b"}" * 100000,
           "non_utf8": b"\xff\xfe{\x00", "empty": b"", "nul": b"\x00" * 64}
    base = json.loads(good)
    def mod(fn):
        d = json.loads(good); fn(d); return json.dumps(d).encode()
    bad["files_list"] = mod(lambda d: d["files"].__setitem__("STATUS.md", ["a"]))
    bad["pending_list"] = mod(lambda d: d["files"]["STATUS.md"].__setitem__("pending", ["x"]))
    bad["root_int"] = mod(lambda d: d.__setitem__("project_root", 7))
    bad["files_null"] = mod(lambda d: d["files"].__setitem__("STATUS.md", None))
    bad["intake_list"] = mod(lambda d: d.__setitem__("intake", ["x"]))
    docs = {f: (a / f).read_bytes() for f in FILES}
    for k, b in bad.items():
        (a / J).write_bytes(b)
        for label, res in ((f"{k}/activate", act(a, "--name", "Alpha Corp")), (f"{k}/resume", resume(a))):
            _no_tb(*res, label)
            need((a / J).read_bytes() == b and all((a / f).read_bytes() == v for f, v in docs.items()) and not os.path.lexists(a / LOCK), f"{label}: files changed or lock left")
    (a / J).write_bytes(good)
    # lock contents
    for k, b in {"deep_lock": b"[" * 200000, "garbage_lock": b"xyz", "nonutf8_lock": b"\xff\xff"}.items():
        (a / LOCK).write_bytes(b)
        _no_tb(*act(a, "--name", "Alpha Corp"), k)
        (a / LOCK).unlink()
    # read-only root
    ro = T / "ro"; ro.mkdir(); os.chmod(ro, 0o555)
    try:
        _no_tb(*act(ro, "--name", "RO", "--type", "web app"), "read-only root")
    finally:
        os.chmod(ro, 0o755)
    need(list(ro.iterdir()) == [], "read-only root got files")
    _no_tb(*act(T / ("x" * 300), "--name", "Long"), "300-byte component")
    deep = T
    for i in range(4):
        deep = deep / (chr(97 + i) * 230)
    deep.mkdir(parents=True)
    _no_tb(*act(deep / "p", "--name", "Long"), "root over 900 bytes")
    # non UTF-8 bytes in argv (surrogateescape)
    r = T / "badbytes"
    rc, out, err, js = act(r, "--name", b"Bad\xffName", "--type", "web app")
    if "Traceback" in err or js is None:
        C06_FAILS.append(f"non-UTF-8 name: rc={rc} traceback {err.strip().splitlines()[-1:]}")
    REC.append(f"REC c06 non-utf8 name: rc={rc} status={st(js)} exists={r.exists()}")
    need(not C06_FAILS, f"{len(C06_FAILS)} unbounded: " + " | ".join(C06_FAILS))
    return f"{len(bad)} malformed journals x2 cmds, 3 lock contents, RO root, 2 long paths, non-UTF-8 name: bounded JSON, no traceback, nothing changed"


def _recover(r, label):
    """Documented recovery: if a lock is left, the message must call it stale; delete it; resume."""
    if os.path.lexists(r / LOCK):
        rc, out, err, js = resume(r)
        need(js is not None and st(js) == "blocked" and "stale" in json.dumps(js.get("errors")), f"{label}: left lock not reported stale: {js and js.get('errors')}")
        os.unlink(r / LOCK)
    rc, out, err, js = resume(r)
    return rc, js


def c07_sigkill(T):
    o = sentinel(T); before = tree(o)
    detail = []
    for n in range(1, 10):
        r = _alpha(T, f"k{n}")
        (r / "Development").mkdir(exist_ok=True); (r / "Development/owner.txt").write_text("owner\n")
        rc, out, err, js = act(r, "--name", "Beta LLC", "--type", "web app", "--deploy-model", "beta: tags deploy", kill_at=n)
        killed = rc == -signal.SIGKILL
        rc, js = _recover(r, f"kill@{n}")
        need(rc == 0 and st(js) == "complete", f"kill@{n}: recovery status {st(js)} rc={rc}")
        nm = names_in(r, ["Alpha Corp", "Beta LLC"])
        need(len(nm) == 1, f"kill@{n}: mixed docs after recovery {nm}")
        need(temps(r) == [], f"kill@{n}: temp files survive recovery {temps(r)}")
        need(text(r, "Development/owner.txt") == "owner\n", "owner file changed")
        t1 = tree(r); rc, js = resume(r)[0], resume(r)[3]
        need(tree(r) == t1 and st(js) == "complete", f"kill@{n}: second resume not stable")
        detail.append(f"{n}:{'K' if killed else '-'}{list(nm)[0][0]}")
    # decoys vs real leftover
    r = _alpha(T, "decoy")
    real = r / ".STATUS.md.fedcba9876543210.activation-tmp"; real.write_text("leftover")
    decoys = [r / "Development/.STATUS.md.0123456789abcdef.activation-tmp", r / ".STATUS.md.notes.activation-tmp",
              r / "Scope/.STATUS.md.0123456789abcdef.activation-tmp", r / ".owner.md.0123456789abcdef.activation-tmp"]
    for p in decoys:
        p.write_text("owner decoy\n")
    (r / "Scope/.ROUND-PLAN.md.0123456789abcdef.activation-tmp").mkdir()
    os.symlink(o / "keep.txt", r / "Delivery/.CREDENTIALS.md.0123456789abcdef.activation-tmp")
    rc, _, _, js = act(r, "--name", "Alpha Corp")
    need(st(js) == "complete", f"decoy run {st(js)}")
    need(not real.exists(), "real leftover temp not removed")
    need(all(p.read_text() == "owner decoy\n" for p in decoys), "a decoy was removed or changed")
    need((r / "Scope/.ROUND-PLAN.md.0123456789abcdef.activation-tmp").is_dir() and
         os.path.islink(r / "Delivery/.CREDENTIALS.md.0123456789abcdef.activation-tmp"), "temp-named dir/symlink removed")
    need(tree(o) == before, "outside changed")
    # owner edits plan during outage
    r = _alpha(T, "edit")
    act(r, "--name", "Beta LLC", "--type", "web app", "--deploy-model", "beta", kill_at=2)
    (r / "Scope/ROUND-PLAN.md").write_text("owner edited during outage\n")
    rc, js = _recover(r, "edit")
    need(text(r, "Scope/ROUND-PLAN.md") == "owner edited during outage\n" and st(js) != "complete", f"owner mid-outage edit: {st(js)}")
    return "changed-intake SIGKILL before os.replace 1..9: " + " ".join(detail) + "; no temp left; decoys kept; mid-outage owner edit kept"


def c08_locks(T):
    a = _alpha(T)
    def lock(b):
        (a / LOCK).write_bytes(b)
    lock(b"")
    rc, _, _, js = act(a, "--name", "Alpha Corp")
    need(st(js) == "blocked" and "stale" in json.dumps(js.get("errors")), f"empty lock: {js and js.get('errors')}")
    sl = subprocess.Popen(["sleep", "30"])
    try:
        lock(json.dumps({"pid": sl.pid, "host": socket.gethostname(), "started": "x"}).encode())
        rc, _, _, js = act(a, "--name", "Alpha Corp")
        need(st(js) == "blocked" and "stale" not in json.dumps(js.get("errors")), "live holder called stale")
        for pid in (0, -1, True):
            lock(json.dumps({"pid": pid, "host": socket.gethostname(), "started": "x"}).encode())
            rc, _, _, js = act(a, "--name", "Alpha Corp")
            need(st(js) == "blocked" and sl.poll() is None, f"pid {pid}: {st(js)} / sleeper killed")
    finally:
        sl.kill(); sl.wait()
    lock(json.dumps({"pid": sl.pid, "host": socket.gethostname(), "started": "x"}).encode())
    rc, _, _, js = act(a, "--name", "Alpha Corp")
    need(st(js) == "blocked" and "stale" in json.dumps(js.get("errors")), "dead pid not stale")
    os.unlink(a / LOCK)
    rc, _, _, js = resume(a)
    need(st(js) == "complete", "recovery after deleting lock")
    return "empty and dead-pid locks stale; live holder not stale; pid 0/-1/true never signalled; recovery complete"


MARKERS = [("--name", "Acme DEPLOY-MODEL: main=live"), ("--brief", "note deploy_model: main=live"),
           ("--brief", "Deploy-Model : main=live"), ("--credential", "system=x;username=DEPLOYMODEL:live;location=v"),
           ("--credential", "system=x;location=vault DEPLOY MODEL: main=live")]


def c09_marker(T):
    for i, (flag, v) in enumerate(MARKERS):
        r = T / f"m{i}"
        rc, _, _, js = act(r, "--name", "Acme", "--type", "web app", flag, v) if flag != "--name" else act(r, "--name", v, "--type", "web app")
        need(rc == 2 and st(js) == "invalid" and not r.exists(), f"marker in {flag} {v!r}: rc={rc} {st(js)}")
    par = T / "DEPLOY-MODEL: main=live"; par.mkdir()
    accepted = [(par / "proj", ("--name", "Folder Co")), (T / "bidi", ("--name", "Acme \u202eevil\u202c")),
                (T / "colon", ("--name", "Acme DEPLOY-MODEL\uff1a main=live"))]
    for r, args in accepted:
        rc, _, _, js = act(r, *args, "--type", "web app")
        if r.exists() and (r / "STATUS.md").exists():
            need(first_marker(r) == deploy_lines(r)[0] and first_marker(r).startswith("DEPLOY-MODEL: UNRESOLVED"),
                 f"{r.name}: first marker {first_marker(r)!r}")
        REC.append(f"REC c09 {r.name}: rc={rc} status={st(js)}")
    return f"{len(MARKERS)} marker injections refused (rc 2, nothing written); first DEPLOY-MODEL: match is the anchored line in 3 accepted runs"


H40, H64 = "4113204" + "a" * 33, "62614bb3a1e36aa009a623e9b40600349c0e6b8fc2b3a8b506a941f43db3cd74"


def c10_commit_ids(T):
    ok = [f"fork of {H40}", f"commit {H40}", f"sha {H64}", f"rev: {H40.upper()}", f"revision #{H40}"]
    no = [f"{H40}", f"commit ghp_{'A1' * 18}", f"commit {H40} token=abc", f"see {H40}"]
    for i, b in enumerate(ok):
        r = T / f"ok{i}"
        rc, _, _, js = act(r, "--name", "C", "--type", "web app", "--deploy-model", "main", "--brief", b)
        need(rc == 0 and st(js) == "complete" and b in (text(r, "STATUS.md") or ""), f"commit id brief {b!r}: rc={rc} {st(js)}")
    for i, b in enumerate(no):
        r = T / f"no{i}"
        rc, out, err, js = act(r, "--name", "C", "--type", "web app", "--brief", b)
        need(rc == 2 and not r.exists() and "ghp_" not in out + err, f"secret-shaped brief {b[:20]!r}: rc={rc}")
    r = T / "loc"
    rc, _, _, js = act(r, "--name", "C", "--credential", f"system=git;location=commit {H40}")
    need(rc == 2 and not r.exists(), "commit id allowed outside the brief")
    for k, b in {"sha256_word": f"sha256 {H64}", "sha256_colon": f"sha256: {H64}", "short_sha": "commit 4113204"}.items():
        r = T / f"rec-{k}"
        rc, _, _, js = act(r, "--name", "C", "--type", "web app", "--deploy-model", "main", "--brief", b)
        REC.append(f"REC c10 {k}: rc={rc} status={st(js)}")
    return "5 commit-id briefs accepted verbatim; bare hex, token after commit, assignment, credential field refused"


def c11_escape(T):
    o = sentinel(T); before = tree(o)
    cases = {"delivery-dirlink": lambda r: os.symlink(o, r / "Delivery"),
             "status-dangling": lambda r: os.symlink(o / "new-status.md", r / "STATUS.md"),
             "journal-link": lambda r: os.symlink(o / "keep.txt", r / J),
             "scope-file": lambda r: (r / "Scope").write_text("owner file named Scope\n"),
             "plan-link": lambda r: ((r / "Scope").mkdir(), os.symlink(o / "sub/STATUS.md", r / "Scope/ROUND-PLAN.md"))}
    for k, mk in cases.items():
        r = T / k; r.mkdir(); mk(r); t0 = tree(r)
        rc, _, _, js = act(r, "--name", "Esc", "--type", "web app", "--deploy-model", "main")
        need(js is not None and st(js) == "blocked" and rc != 0, f"{k}: {st(js)}")
        need(tree(r) == t0 and tree(o) == before, f"{k}: tree or outside changed")
    w = T / "inside"; w.mkdir()
    rc, _, _, js = act(w / ".." / "esc", "--name", "Esc", "--within", w)
    need(rc == 2 and not (T / "esc").exists(), "--within escape")
    return "5 link/type escapes blocked with trees unchanged; --within escape refused"


def c12_eacces(T):
    r = T / "p"; (r / "Scope").mkdir(parents=True); os.chmod(r / "Scope", 0o555)
    try:
        rc, _, _, js = act(r, "--name", "Perm Co", "--type", "web app", "--deploy-model", "main")
        need(js is not None and rc != 0 and st(js) == "failed" and not (r / "Scope/ROUND-PLAN.md").exists(), f"EACCES run rc={rc} {st(js)}")
    finally:
        os.chmod(r / "Scope", 0o755)
    rc, _, _, js = resume(r)
    need(rc == 0 and st(js) == "complete", f"resume after fix {st(js)}")
    entry_present(r)
    t = tree(r); rc, _, _, js = resume(r)
    need(tree(r) == t and temps(r) == [], "second resume changed tree / temp left")
    return "EACCES between writes -> failed, plan absent; resume complete; stable"


def c13_concurrency(T):
    rounds = []
    for rd in range(5):
        r = T / f"race{rd}"
        names = [f"Racer{rd}{i:02d}" for i in range(16)]
        res = [None] * 16
        def go(i):
            res[i] = act(r, "--name", names[i], "--type", "web app", "--deploy-model", "main")
        th = [threading.Thread(target=go, args=(i,)) for i in range(16)]
        [t.start() for t in th]; [t.join() for t in th]
        ok = sum(1 for x in res if st(x[3]) == "complete")
        need(ok >= 1, f"round {rd}: no run succeeded")
        need(all(st(x[3]) in ("complete", "blocked") for x in res), f"round {rd}: statuses {[st(x[3]) for x in res]}")
        found = names_in(r, names)
        need(len(found) == 1, f"round {rd}: docs name {found}")
        need(not os.path.lexists(r / LOCK) and temps(r) == [], f"round {rd}: lock/temp left")
        rounds.append(ok)
    many = [T / f"proj{i:02d}" for i in range(40)]
    out = [None] * 40
    def go2(i):
        out[i] = act(many[i], "--name", f"Project {i:02d}", "--type", "website", "--deploy-model", "tags")
    th = [threading.Thread(target=go2, args=(i,)) for i in range(40)]
    [t.start() for t in th]; [t.join() for t in th]
    need(all(st(x[3]) == "complete" for x in out), "parallel distinct projects not all complete")
    need(all(names_in(many[i], [f"Project {i:02d}"]) for i in range(40)), "parallel project docs wrong")
    return f"5 rounds x 16 racers on one root (winners {rounds}) one consistent project, no lock; 40 parallel projects complete"


def c14_scale(T):
    r = T / "p"
    for i in range(4000):
        p = r / ("Development" if i % 2 else "Assets") / f"d{i % 40}" / f"f{i}.txt"
        p.parent.mkdir(parents=True, exist_ok=True); p.write_text(str(i))
    t0 = {k: v for k, v in tree(r).items()}
    s = time.time()
    rc, _, _, js = act(r, "--name", "Big Co", "--type", "web app", "--deploy-model", "main")
    dt = time.time() - s
    need(st(js) == "complete", f"scale status {st(js)}")
    entry_present(r)
    now = tree(r)
    need(all(now.get(k) == v for k, v in t0.items()), "owner tree changed")
    return f"4000 owner files kept byte-identical; activation {dt:.2f}s"


def c15_secrets(T):
    tok = "ghp_" + "Z9" * 18
    for i, args in enumerate([("--credential", f"system=gh;location={tok}"), ("--brief", "password=hunter2xx"),
                               ("--credential", "system=aws;username=" + "AKIA" + "ABCDEFGHIJKLMNOP" + ";location=v")]):
        r = T / f"s{i}"
        rc, out, err, js = act(r, "--name", "Sec", *args)
        need(rc == 2 and not r.exists() and tok not in out + err and "hunter2xx" not in out + err and "AKIAABCD" not in out + err,
             f"secret case {i}: rc={rc}")
    return "3 secret shapes refused, not echoed, nothing written"


CHECKS = [("C01_clean_twice", c01_clean), ("C02_owner_docs", c02_owner_docs), ("C03_git_unchanged", c03_git),
          ("C04_journal_binding_F1", c04_binding), ("C05_blank_deploy_F2_F3", c05_deploy_blank), ("C06_bounded_errors_F4", c06_malformed),
          ("C07_sigkill_temps_F5", c07_sigkill), ("C08_locks_F6", c08_locks), ("C09_marker_F7", c09_marker),
          ("C10_commit_ids_F8", c10_commit_ids), ("C11_escape", c11_escape), ("C12_failure_resume", c12_eacces),
          ("C13_concurrency", c13_concurrency), ("C14_scale", c14_scale), ("C15_secrets", c15_secrets)]


def main():
    global CMD
    argv = sys.argv[1:]
    only = None
    if argv and argv[0] == "--only":
        only = set(argv[1].split(",")); argv = argv[2:]
    if argv and argv[0] == "--":
        argv = argv[1:]
    CMD = argv
    print(f"# m02r2_oracle candidate: {' '.join(CMD)}")
    passed = 0; total = 0
    for name, fn in CHECKS:
        if only and name.split("_")[0] not in only:
            continue
        total += 1
        T = Path(tempfile.mkdtemp(prefix="m02r2-o-")).resolve()
        s = time.time()
        try:
            msg = fn(T); res = "PASS"; passed += 1
        except Fail as e:
            msg, res = str(e), "FAIL"
        except subprocess.TimeoutExpired as e:
            msg, res = f"timeout {e}", "FAIL"
        except Exception as e:  # harness error is still a FAIL, never a SKIP
            msg, res = f"harness error {type(e).__name__}: {e}", "FAIL"
        finally:
            for dp, dns, fns in os.walk(T):
                for d in dns:
                    try:
                        os.chmod(os.path.join(dp, d), 0o755, follow_symlinks=False)
                    except (OSError, NotImplementedError):
                        pass
            shutil.rmtree(T, ignore_errors=True)
        print(f"{res} {name} ({time.time() - s:.1f}s): {msg}", flush=True)
    for line in REC:
        print(line)
    verdict = "ACCEPTS" if passed == total and total else "REJECTS"
    print(f"SUMMARY {passed}/{total} pass; oracle {verdict} candidate")
    return 0 if verdict == "ACCEPTS" else 1


if __name__ == "__main__":
    sys.exit(main())
