#!/usr/bin/env python3
"""M02 unseen and adversarial cases for the G02 activation CLI (none taken from the builder's tests).

Usage: python m02_adversarial.py -- <candidate command prefix...>
Each case prints SAFE (expected safe behaviour observed), FINDING (defect, with the observation)
or NOTE (behaviour worth recording, not a defect). Synthetic data and temp dirs only.
"""
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

GITX = ["git", "-c", "user.name=M02", "-c", "user.email=m02@example.invalid", "-c", "core.hooksPath=/dev/null",
        "-c", "init.defaultBranch=main", "-c", "protocol.file.allow=always"]
CMD = []
TMP = None
results = []


def env():
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def run(*args, timeout=60):
    try:
        p = subprocess.run(CMD + [str(a) for a in args], capture_output=True, text=True, env=env(), timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return "timeout", "", ""


def jrun(*args):
    rc, out, err = run(*args, "--json")
    try:
        return rc, json.loads(out), err
    except ValueError:
        return rc, None, out + err


def git(cwd, *a):
    p = subprocess.run(GITX + ["-C", str(cwd), *a], capture_output=True, text=True, env=env())
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout.strip()


def gstate(repo):
    gd = Path(git(repo, "rev-parse", "--absolute-git-dir"))
    return (git(repo, "for-each-ref"), (gd / "index").read_bytes() if (gd / "index").exists() else b"",
            git(repo, "count-objects", "-v"), subprocess.run(GITX + ["-C", str(repo), "rev-parse", "-q", "--verify", "HEAD"],
                                                             capture_output=True, text=True).stdout)


def tree(base, exclude=None):
    out = {}
    for dp, dn, fn in os.walk(base):
        for n in dn + fn:
            p = Path(dp) / n
            rel = p.relative_to(base).as_posix()
            if exclude and (rel == exclude or rel.startswith(exclude + "/")):
                continue
            out[rel] = ("L:" + os.readlink(p)) if p.is_symlink() else (
                hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "d")
    return out


def new(label):
    b = Path(tempfile.mkdtemp(prefix=label + "-", dir=TMP)).resolve()
    (b / "outside").mkdir()
    (b / "outside" / "keep.txt").write_text("KEEP\n")
    return b


def rec(kind, case, msg):
    results.append((kind, case, msg))
    print(f"{kind:8} {case}: {msg}")
    sys.stdout.flush()


def crashed(err):
    return "Traceback (most recent call last)" in (err or "")


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


# --------------------------------------------------------------------------------------------

@case
def a01_unicode_names():
    for label, name in (("cjk", "\u9879\u76ee \u53f0\u5317"), ("emoji", "\U0001F680 Launch"), ("rtl-override", "safe\u202egnp.exe"),
                        ("combining", "Cafe\u0301"), ("zero-width-only", "\u200b")):
        b = new("a01")
        rc, r, err = jrun("activate", b / "proj", "--name", name, "--deploy-model", "none")
        st = r and r["status"]
        ok = rc == 0 and name in (b / "proj" / "STATUS.md").read_text(encoding="utf-8")
        if label == "zero-width-only":
            rec("FINDING" if rc == 0 else "SAFE", "a01_unicode_name_" + label,
                f"invisible-only required name accepted rc={rc} status={st}" if rc == 0 else f"refused rc={rc}")
        elif label == "rtl-override":
            rec("NOTE", "a01_unicode_name_" + label, f"bidi override char accepted rc={rc}; recorded verbatim={ok}")
        else:
            rec("SAFE" if ok else "FINDING", "a01_unicode_name_" + label, f"rc={rc} status={st} recorded={ok}")


@case
def a02_long_names():
    b = new("a02")
    rc, r, _ = jrun("activate", b / "p120", "--name", "\U0001F680" * 120, "--deploy-model", "none")
    rc2, r2, _ = jrun("activate", b / "p121", "--name", "\U0001F680" * 121, "--deploy-model", "none")
    rec("SAFE" if rc == 0 and rc2 == 2 and not (b / "p121").exists() else "FINDING", "a02_name_length_limit",
        f"120 x 4-byte emoji rc={rc}; 121 rc={rc2}, p121 created={(b / 'p121').exists()}")
    for n in (255, 300):
        root = b / ("x" * n)
        rc, out, err = run("activate", root, "--name", "Long path", "--deploy-model", "none")
        rec("FINDING" if crashed(err) else "SAFE", f"a02_root_component_{n}_bytes",
            f"rc={rc} traceback={crashed(err)} out={out.splitlines()[0] if out else err.strip()[-120:]!r}")


@case
def a03_readonly_parent_and_root():
    b = new("a03")
    par = b / "ro-parent"; par.mkdir(); os.chmod(par, 0o555)
    rc, out, err = run("activate", par / "proj", "--name", "RO parent", "--deploy-model", "none")
    os.chmod(par, 0o755)
    rec("FINDING" if crashed(err) or rc == 0 else "SAFE", "a03_readonly_parent",
        f"rc={rc} traceback={crashed(err)} first={out.splitlines()[0] if out else ''!r}")
    root = b / "ro-root"; root.mkdir(); (root / "owner.txt").write_text("owner\n"); os.chmod(root, 0o555)
    rc, out, err = run("activate", root, "--name", "RO root", "--deploy-model", "none")
    os.chmod(root, 0o755)
    rec("FINDING" if crashed(err) else "SAFE", "a03_readonly_existing_root",
        f"rc={rc} traceback={crashed(err)} last_err={err.strip().splitlines()[-1] if err.strip() else ''!r}; "
        f"owner file kept={(root / 'owner.txt').read_text() == 'owner' + chr(10)}")


@case
def a04_foreign_journal():
    b = new("a04")
    a = b / "alpha"
    run("activate", a, "--name", "Alpha Corp", "--type", "web app", "--deploy-model", "production: main=live")
    # (i) only the journal copied into a new project that already has owner material
    p = b / "beta"; p.mkdir(); shutil.copy(a / ".solaris-activation.json", p); (p / "README.md").write_text("beta owner\n")
    rc, r, _ = jrun("activate", p, "--name", "Beta Ltd", "--type", "website")
    dl = [l for l in (p / "STATUS.md").read_text().splitlines() if l.startswith("DEPLOY-MODEL:")]
    _, out, _ = run("activate", p, "--name", "Beta Ltd", "--type", "website")
    rec("FINDING" if r and "main=live" in "".join(dl) else "SAFE", "a04_foreign_journal_only",
        f"rc={rc} status={r and r['status']} inherited={r and r['inherited']} STATUS {dl}; "
        f"text report deploy line={[l for l in out.splitlines() if l.startswith('Deploy model')]}, mentions inherit="
        f"{'inherit' in out.lower()}")
    # (ii) template folder copied (cp -R) and reused for a new client
    c = b / "gamma"; shutil.copytree(a, c)
    rc, r, _ = jrun("activate", c, "--name", "Gamma Inc", "--type", "website")
    dl = [l for l in (c / "STATUS.md").read_text().splitlines() if l.startswith("DEPLOY-MODEL:")]
    rec("FINDING" if r and r["status"] == "complete" and "main=live" in "".join(dl) else "SAFE",
        "a04_template_copy_new_client", f"rc={rc} status={r and r['status']} STATUS {dl} (Gamma owner never answered)")


@case
def a05_corrupt_journal():
    variants = {
        "files-entry-list": {"schema": "solaris.project-activation/1", "intake": {"name": "X"}, "files": {"STATUS.md": ["a"]}},
        "pending-unhashable": {"schema": "solaris.project-activation/1", "intake": {"name": "X"},
                               "files": {"STATUS.md": {"pending": ["x"]}}},
        "intake-name-number": {"schema": "solaris.project-activation/1", "intake": {"name": 5}, "files": {}},
        "truncated": None,
    }
    for label, body in variants.items():
        b = new("a05"); p = b / "proj"; p.mkdir()
        (p / ".solaris-activation.json").write_text("{\"schema\": \"solaris.pro" if body is None else json.dumps(body))
        before = tree(p)
        rc, out, err = run("resume", p)
        rc2, out2, err2 = run("activate", p, "--name", "X")
        bad = crashed(err) or crashed(err2)
        rec("FINDING" if bad else "SAFE", "a05_journal_" + label,
            f"resume rc={rc} tb={crashed(err)}; activate rc={rc2} tb={crashed(err2)}; "
            f"{(err2.strip().splitlines() or [''])[-1][:110] if bad else (out2.splitlines() or [''])[0]}; unchanged={tree(p) == before}")


@case
def a06_lock_files():
    b = new("a06")
    dead = subprocess.Popen(["sleep", "30"]); dead.kill(); dead.wait()
    import socket
    for label, content in (("dead-pid", {"pid": dead.pid, "host": socket.gethostname(), "started": "x"}),
                           ("live-pid-1", {"pid": 1, "host": socket.gethostname(), "started": "x"}),
                           ("garbage", "not json"), ("other-host", {"pid": 4242, "host": "elsewhere", "started": "x"})):
        p = b / label; p.mkdir()
        (p / ".solaris-activation.lock").write_text(json.dumps(content) if isinstance(content, dict) else content)
        rc, out, err = run("activate", p, "--name", "Locked", "--deploy-model", "none")
        wrote = sorted(x.name for x in p.iterdir())
        stale = "stale" in out.lower()
        rec("SAFE" if rc != 0 and wrote == [".solaris-activation.lock"] and not crashed(err) else "FINDING",
            "a06_lock_" + label, f"rc={rc} nothing_written={wrote == ['.solaris-activation.lock']} says_stale={stale}")
    p = b / "lock-link"; p.mkdir(); (p / ".solaris-activation.lock").symlink_to(b / "outside" / "keep.txt")
    rc, out, err = run("activate", p, "--name", "Locked", "--deploy-model", "none")
    rec("SAFE" if rc != 0 and (b / "outside" / "keep.txt").read_text() == "KEEP\n" and (p / ".solaris-activation.lock").is_symlink()
        else "FINDING", "a06_lock_symlink", f"rc={rc}; outside kept; link kept")


@case
def a07_submodule_and_outer_repo():
    b = new("a07")
    sub_src = b / "outside" / "libsrc"; sub_src.mkdir(); git(sub_src, "init", "-q")
    (sub_src / "lib.txt").write_text("lib\n"); git(sub_src, "add", "."); git(sub_src, "commit", "-qm", "lib")
    sup = b / "super"; sup.mkdir(); git(sup, "init", "-q"); (sup / "a.txt").write_text("a\n"); git(sup, "add", ".")
    git(sup, "commit", "-qm", "a"); git(sup, "submodule", "add", "-q", str(sub_src), "vendor/lib"); git(sup, "commit", "-qm", "sub")
    sm = sup / "vendor" / "lib"
    s0, m0, src0 = gstate(sup), gstate(sm), gstate(sub_src)
    rc, r, err = jrun("activate", sm, "--name", "Submodule proj", "--code", "--init-git", "--deploy-model", "none")
    same = gstate(sup) == s0 and gstate(sm) == m0 and gstate(sub_src) == src0
    rec("SAFE" if rc == 0 and same else "FINDING", "a07_submodule_root",
        f"rc={rc} status={r and r['status']} git={r and r['git'] and r['git'].get('state')} linked={r and r['git'] and r['git'].get('linked_metadata')} git_unchanged={same}")
    inner = sup / "newproj"
    s0 = gstate(sup)
    rc, r, err = jrun("activate", inner, "--name", "Nested", "--code", "--init-git", "--deploy-model", "none")
    rec("SAFE" if rc == 0 and not (inner / ".git").exists() and gstate(sup) == s0 else "FINDING", "a07_inside_outer_repo_init",
        f"rc={rc} git={r and r['git'] and r['git'].get('state')} nested_git_created={(inner / '.git').exists()} outer_unchanged={gstate(sup) == s0}")


@case
def a08_deploy_values():
    for label, val in (("nbsp", "\u00a0"), ("ideographic-space", "\u3000"), ("zero-width-space", "\u200b"),
                       ("bom", "\ufeff"), ("newline", "\n"), ("literal-UNRESOLVED", "UNRESOLVED"), ("main", "main"),
                       ("main=live", "main=live"), ("None", "None"), ("dash", "-")):
        b = new("a08")
        rc, r, err = jrun("activate", b / "p", "--name", "Deploy " + label, "--type", "web app", "--deploy-model", val)
        st = r and r["status"]
        line = ""
        if (b / "p" / "STATUS.md").exists():
            line = [l for l in (b / "p" / "STATUS.md").read_text().splitlines() if l.startswith("DEPLOY-MODEL:")][0]
        if label in ("nbsp", "ideographic-space", "newline"):
            ok = (rc == 0 and "UNRESOLVED" in line and st != "complete") or rc == 2
            rec("SAFE" if ok else "FINDING", "a08_deploy_" + label, f"rc={rc} status={st} line={line!r}")
        elif label in ("zero-width-space", "bom"):
            rec("FINDING" if st == "complete" else "SAFE", "a08_deploy_" + label,
                f"invisible-only answer: rc={rc} status={st} line={line!r}")
        elif label == "literal-UNRESOLVED":
            rec("FINDING" if st == "complete" else "SAFE", "a08_deploy_" + label,
                f"rc={rc} status={st} line={line!r} (line says UNRESOLVED, status says resolved)")
        else:
            rec("NOTE", "a08_deploy_" + label, f"owner answer recorded verbatim: rc={rc} status={st} line={line!r}")


@case
def a09_path_traversal_intake():
    b = new("a09")
    allowed = b / "clients"; allowed.mkdir()
    (b / "linkout").symlink_to(b / "outside", target_is_directory=True)
    before = tree(b / "outside")
    attempts = [
        ("name-dotdot", ["activate", allowed / "p1", "--name", "../../outside/pwned", "--within", allowed]),
        ("cred-location-dotdot", ["activate", allowed / "p2", "--name", "P2", "--within", allowed,
                                  "--credential", "system=x;username=y;location=../../outside/keep.txt"]),
        ("root-dotdot", ["activate", str(allowed) + "/../outside/p3", "--name", "P3", "--within", allowed]),
        ("root-via-symlinked-ancestor", ["activate", b / "linkout" / "p4", "--name", "P4", "--within", allowed]),
        ("within-is-root", ["activate", allowed, "--name", "P5", "--within", allowed]),
        ("cred-pipe-injection", ["activate", allowed / "p6", "--name", "P6", "--credential",
                                 "system=x|y;username=z;location=Vault/a"]),
        ("cred-key-injection", ["activate", allowed / "p7", "--name", "P7", "--credential",
                                "system=x;location=Vault/a;deploy_model=main=live"]),
    ]
    for label, args in attempts:
        rc, out, err = run(*args)
        rec("SAFE" if tree(b / "outside") == before and not crashed(err) else "FINDING", "a09_" + label,
            f"rc={rc} outside_unchanged={tree(b / 'outside') == before} first={out.splitlines()[0] if out else err[-80:]!r}")
    p = allowed / "p8"
    run("activate", p, "--name", "Acme DEPLOY-MODEL: main=live", "--brief", "DEPLOY-MODEL: main=live")
    lines = [l for l in (p / "STATUS.md").read_text().splitlines() if "DEPLOY-MODEL:" in l]
    first = lines[0]
    rec("FINDING" if "main=live" in first else "SAFE", "a09_deploy_marker_injection_via_name",
        f"deploy omitted; first line containing 'DEPLOY-MODEL:' is {first!r}; anchored line is "
        f"{[l for l in lines if l.startswith('DEPLOY-MODEL:')]}")


@case
def a10_links_and_special_files():
    b = new("a10")
    p = b / "hard"; p.mkdir(); os.link(b / "outside" / "keep.txt", p / "STATUS.md")
    rc, out, err = run("activate", p, "--name", "Hard", "--deploy-model", "none")
    rec("SAFE" if (b / "outside" / "keep.txt").read_text() == "KEEP\n" else "FINDING", "a10_hardlinked_status",
        f"rc={rc} outside_kept={(b / 'outside' / 'keep.txt').read_text() == 'KEEP' + chr(10)} first={out.splitlines()[0]!r}")
    p = b / "fifo"; p.mkdir(); os.mkfifo(p / "STATUS.md")
    rc, out, err = run("activate", p, "--name", "Fifo", "--deploy-model", "none", timeout=20)
    rec("SAFE" if rc not in (0, "timeout") and not crashed(err) else "FINDING", "a10_fifo_status", f"rc={rc}")
    real = b / "realroot"; real.mkdir(); (b / "aliasroot").symlink_to(real, target_is_directory=True)
    rc, r, _ = jrun("activate", b / "aliasroot", "--name", "Alias", "--deploy-model", "none")
    rec("NOTE", "a10_symlinked_root", f"rc={rc} status={r and r['status']} project_root={r and Path(r['project_root']).name}; "
        "an explicitly named symlinked root is allowed by design and its real path is reported")
    p = b / "case"; p.mkdir(); (p / "status.md").write_text("owner lowercase status\n"); (p / "scope").mkdir()
    h = (p / "status.md").read_text()
    rc, r, _ = jrun("activate", p, "--name", "Case", "--deploy-model", "none")
    rec("SAFE" if (p / "status.md").read_text() == h else "FINDING", "a10_case_insensitive_collision",
        f"rc={rc} status={r and r['status']} owner lowercase file kept; artifacts={r and r['artifacts'].get('STATUS.md')}")
    p = b / "dry"
    rc, r, _ = jrun("activate", p, "--name", "Dry", "--dry-run")
    rec("SAFE" if rc == 0 and not p.exists() else "FINDING", "a10_dry_run_writes_nothing", f"rc={rc} root_created={p.exists()}")


@case
def a11_secret_false_positive():
    b = new("a11")
    rc, out, err = run("activate", b / "p", "--name", "SHA", "--brief", "fork of 41132041afeb2cce63a68554caf18cf6992a11ae")
    rec("NOTE" if rc == 2 else "SAFE", "a11_commit_sha_in_brief", f"rc={rc}: a 40-hex commit id is refused as a 'long opaque string'")


@case
def a12_sigkill_leftovers_not_cleaned():
    b = new("a12")
    inject = Path(__file__).resolve().parent / "inject"
    e = dict(env(), M02_KILL_ROOT=str(b), M02_KILL_AT="4", PYTHONPATH=str(inject))
    subprocess.run(CMD + ["activate", str(b / "p"), "--name", "K", "--deploy-model", "none"], env=e, capture_output=True)
    lock = b / "p" / ".solaris-activation.lock"
    rc1, out1, _ = run("resume", b / "p")
    if lock.exists():
        lock.unlink()
    rc2, out2, _ = run("resume", b / "p")
    left = [x for x in tree(b / "p") if x.endswith(".activation-tmp")]
    rec("FINDING" if left else "SAFE", "a12_sigkill_temp_leftover_after_documented_recovery",
        f"first resume rc={rc1} (stale lock); after deleting lock resume rc={rc2}; leftover temp files={left}")


def main(argv):
    global CMD, TMP
    CMD = argv[argv.index("--") + 1:]
    TMP = Path(tempfile.mkdtemp(prefix="m02-adv-")).resolve()
    print(f"# m02_adversarial candidate: {' '.join(CMD)}")
    try:
        for fn in CASES:
            try:
                fn()
            except Exception as exc:
                rec("ERROR", fn.__name__, f"harness error {type(exc).__name__}: {str(exc)[:200]}")
    finally:
        for dp, dn, _ in os.walk(TMP):
            for d in dn:
                try:
                    os.chmod(os.path.join(dp, d), 0o755)
                except OSError:
                    pass
        shutil.rmtree(TMP, ignore_errors=True)
    kinds = [k for k, _, _ in results]
    print(f"SUMMARY SAFE={kinds.count('SAFE')} FINDING={kinds.count('FINDING')} NOTE={kinds.count('NOTE')} ERROR={kinds.count('ERROR')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
