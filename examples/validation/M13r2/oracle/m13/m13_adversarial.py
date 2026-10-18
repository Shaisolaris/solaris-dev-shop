#!/usr/bin/env python3
"""M13 adversarial cases for csv_reconcile.py, focused on what the prior review could not run
(scale, concurrency, as_of with missing loaded_at) and on concrete gaps. Synthetic data only.
Usage: python m13_adversarial.py [--pythons P1,P2,...] [--rows N] -- <candidate prefix...>
Each case prints OK, NOTE or FINDING with the observed output."""
import concurrent.futures as cf, json, os, subprocess, sys, tempfile, threading, time
from decimal import Decimal as D
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import m13_oracle as M
from m13_oracle import o, BASE, CUST, contract, rev, scalar, cov, dec

CASES = []
PYS = []
ROWS = 1_000_000


def case(f):
    CASES.append(f)
    return f


@case
def b01_cross_interpreter_bytes(w):
    rows, custs, exp, orders = M.gen(77, 2000)
    d = w.case(rows, custs)
    outs = {}
    for py in [M.CMD[0]] + PYS:
        p = subprocess.run([py] + M.CMD[1:] + ["reconcile", str(d / "contract.json"), "--json"], capture_output=True, text=True, env=M.env())
        outs[Path(py).parent.parent.name if "uv" in py else py] = (p.returncode, p.stdout)
    same = len({v for v in outs.values()}) == 1
    return ("OK" if same else "FINDING"), f"same dataset on {len(outs)} interpreters: identical exit and bytes={same}"


@case
def b02_timestamp_forms_by_interpreter(w):
    forms = ["2026-09-10T12:00:00Z", "2026-09-10T12:00:00+00:00", "2026-09-10T12:00:00.5Z", "2026-09-10T12:00:00+0000",
             "2026-09-10T12:00:00+00", "20260910T120000Z", "2026-W37-4T12:00:00Z", "2026-09-10T12:00Z", "2026-09-10 12:00:00",
             "2026-09-10", "2026-09-10T12:00:00.1234567Z"]
    res, div = [], []
    for f in forms:
        d = w.case(BASE + [o("O4", amt="4.00", ev=f)])
        got = []
        for py in [M.CMD[0]] + PYS:
            p = subprocess.run([py] + M.CMD[1:] + ["reconcile", str(d / "contract.json"), "--json"], capture_output=True, text=True, env=M.env())
            rep = json.loads(p.stdout) if p.stdout.startswith("{") else {}
            got.append(f"{p.returncode}:{rev(rep).get('USD')}")
        res.append(f"{f}: " + "/".join(got))
        if len(set(got)) > 1:
            div.append(f)
    return ("FINDING" if div else "OK"), f"event_time forms where interpreters disagree on the metric ({len(div)}): {div}; exit:USD per main/" + "/".join(Path(p).parent.parent.name for p in PYS) + ": " + "; ".join(res)


@case
def b03_dst_ambiguous_and_missing_local_times(w):
    c = contract(window={"column": "event_time", "start": "2026-10-25T00:00:00Z", "end": "2026-11-01T09:00:00Z"}, as_of="2026-11-05T00:00:00Z")
    # 01:30 local on 2026-11-01 happens twice: 08:30Z (PDT, inside) and 09:30Z (PST, outside the window end 09:00Z)
    d = w.case([o("O1", amt="10.00", ev="2026-11-01 01:30:00", la="2026-11-02T00:00:00Z", up="2026-11-01T10:00:00Z"),
                o("O2", amt="20.00", ev="2026-10-30T12:00:00Z", la="2026-11-02T00:00:00Z", up="2026-10-30T12:00:00Z")], c=c)
    rc, rep, _ = w.run(d)
    c2 = contract()
    d2 = w.case(BASE + [o("O4", amt="4.00", ev="2026-03-08 02:30:00")], c=c2)  # 02:30 does not exist on 2026-03-08 in Los Angeles
    rc2, rep2, _ = w.run(d2)
    amb = rev(rep).get("USD")
    flagged = any("ambig" in n.lower() or "dst" in n.lower() or "fold" in n.lower() for n in rep.get("notes", []))
    return ("FINDING" if not flagged else "OK"), (f"ambiguous local 2026-11-01 01:30 (window end 09:00Z): USD {amb}, exit {rc}, notes {rep.get('notes')} "
            f"(counted as the first occurrence, no ambiguity flagged); nonexistent local 2026-03-08 02:30 accepted: exit {rc2}, "
            f"outside_window {cov(rep2).get('outside_window')}, notes {rep2.get('notes')}")


@case
def b04_unicode_digits_in_int(w):
    c = contract()
    c["facts"]["columns"]["rev"] = "int"
    c["facts"]["duplicate_policy"] = "latest:rev"
    h = M.HEADER + ["rev"]
    rows = [r + ["1"] for r in BASE] + [o("O2", "C2", "70.00") + ["\u0663"]]  # ARABIC-INDIC DIGIT THREE
    d = w.case(rows, c=c, header=h)
    rc, rep, _ = w.run(d)
    usd = rev(rep).get("USD")
    return ("FINDING" if usd == D("170.00") else "OK"), f"int column value '\\u0663' (Arabic-Indic 3): USD {usd}, rejected {cov(rep).get('rejected')}; accepted as 3 and won the version" if usd == D("170.00") else f"USD {usd}, rejected {cov(rep).get('rejected')}"


@case
def b05_scale_memory(w):
    rows, custs, exp, orders = M.gen(31337, ROWS)
    d = w.case(rows, custs)
    size = (d / "orders.csv").stat().st_size
    t0 = time.time()
    p = subprocess.run(["/usr/bin/time", "-l"] + M.CMD + ["reconcile", str(d / "contract.json"), "--json", "--out", str(d / "r.json")],
                       capture_output=True, text=True, env=M.env(), timeout=1800)
    el = time.time() - t0
    rss = next((int(l.split()[0]) for l in p.stderr.splitlines() if "maximum resident set size" in l), 0)
    rep = json.loads(p.stdout)
    exact = rev(rep) == dec(exp) and scalar(rep, "orders") == orders and cov(rep).get("all_rows_accounted")
    mb = size / 1e6
    return ("OK" if exact else "FINDING"), (f"{len(rows)} rows ({mb:.0f} MB): exact={exact} in {el:.1f}s, peak RSS {rss/1e6:.0f} MB "
            f"({rss/size:.1f}x the file); at the documented 5,000,000-row / 512 MiB limit that ratio means about {rss/size*512*1.048576/1024:.1f} GB")


@case
def b06_concurrent_reader_sees_whole_reports(w):
    rows, custs, exp, orders = M.gen(5, 20000)
    d = w.case(rows, custs)
    d2 = w.case(BASE)
    out = d / "shared.json"
    M.CMD and w.run(d, "--out", str(out))
    stop = threading.Event()
    bad, reads = [], [0]

    def reader():
        while not stop.is_set():
            try:
                b = out.read_bytes()
            except FileNotFoundError:
                bad.append("missing")
                continue
            reads[0] += 1
            try:
                json.loads(b)
            except ValueError:
                bad.append(f"partial ({len(b)} bytes)")
    t = threading.Thread(target=reader)
    t.start()
    # writers with DIFFERENT inputs into the same --out
    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda i: subprocess.run(M.CMD + ["reconcile", str((d if i % 2 else d2) / "contract.json"), "--json", "--out", str(out)],
                                            capture_output=True, env=M.env()), range(16)))
    stop.set()
    t.join()
    final = json.loads(out.read_bytes())
    which = "big" if final["coverage"]["rows_read"] > 10 else "small"
    left = [x.name for x in d.iterdir() if x.name.endswith(".tmp")]
    return ("FINDING" if bad or left else "OK"), f"16 writers (2 different inputs) into one --out with a reader: {reads[0]} reads, partial/missing {len(bad)}, final is one whole report ({which}), temp files left {left}"


@case
def b07_as_of_missing_loaded_at(w):
    res = []
    for label, rows in (("one row blank loaded_at", BASE + [o("O4", amt="4.00", la="")]),
                        ("NULL token", BASE + [o("O4", amt="4.00", la="NULL")]),
                        ("every row blank", [r[:6] + [""] + r[7:] for r in BASE]),
                        ("newer version blank, older on time", BASE + [o("O2", "C2", "75.00", la="", up="2026-09-20T00:00:00Z")])):
        d = w.case(rows)
        rc, rep, _ = w.run(d)
        res.append(f"{label}: exit {rc} status {rep.get('status')} gaps {rep.get('gaps')} USD {rev(rep).get('USD')} "
                   f"loaded_at_missing_included {cov(rep).get('loaded_at_missing_included')}")
    clean = sum(1 for r in res if "exit 0" in r)
    return ("FINDING" if clean else "OK"), f"as_of 2026-10-02T00:00Z with loaded_at missing ({clean}/4 report exit 0 reconciled): " + "; ".join(res)


@case
def b08_naive_loaded_at_vs_as_of(w):
    d = w.case(BASE + [o("O4", amt="4.00", la="2026-10-01 18:00:00"), o("O5", amt="5.00", la="2026-10-01 16:00:00")])
    rc, rep, _ = w.run(d)
    ok = cov(rep).get("late_after_as_of") == 1 and rev(rep).get("USD") == D("155.00")
    return ("OK" if ok else "FINDING"), f"naive loaded_at read in contract zone (18:00 LA is after as_of, 16:00 is before): late {cov(rep).get('late_after_as_of')}, USD {rev(rep).get('USD')}"


@case
def b09_redelivered_identical_record(w):
    # the same business record delivered by two load batches (only loaded_at differs), same updated_at
    rows = BASE + [o("O2", "C2", "50.00", la="2026-09-12T00:00:00Z")]
    d = w.case(rows)
    rc, rep, _ = w.run(d)
    return ("FINDING" if rev(rep).get("USD") != D("150.00") else "OK"), (f"O2 re-delivered (identical except loaded_at): USD {rev(rep).get('USD')} (true 150.00), orders {scalar(rep, 'orders')}, "
            f"duplicates {cov(rep).get('duplicates')}, exit {rc}, gaps {rep.get('gaps')}")


@case
def b10_deep_json_contract(w):
    d = w.case(BASE)
    (d / "contract.json").write_text('{"schema": "solaris.csv-reconcile/1", "x": ' + "[" * 100000 + "]" * 100000 + "}")
    rc, rep, p = w.run(d)
    tb = "Traceback" in p.stderr
    return ("FINDING" if rc != 2 or tb else "OK"), f"100000-deep contract JSON: exit {rc}, traceback={tb} {p.stderr.strip().splitlines()[-1][:120] if p.stderr.strip() else ''}"


@case
def b11_write_failure_after_checks(w):
    d = w.case(BASE)
    ro = d / "ro"
    ro.mkdir()
    os.chmod(ro, 0o555)
    try:
        rc, rep, p = w.run(d, "--rejects", str(d / "rej.csv"), "--out", str(ro / "report.json"))
    finally:
        os.chmod(ro, 0o755)
    wrote = (d / "rej.csv").exists()
    return ("FINDING" if rc == 2 and wrote else "OK"), f"--rejects writable, --out in a read-only folder: exit {rc} {p.stdout.strip()[:100]!r}; rejects.csv written anyway={wrote} (doc: exit 2 means nothing written)"


@case
def b12_window_start_equals_naive_contract_time(w):
    c = contract(window={"column": "event_time", "start": "2026-09-01", "end": "2026-10-01"})
    d = w.case(BASE + [o("O4", amt="4.00", ev="2026-09-01T06:59:59Z"), o("O5", amt="5.00", ev="2026-09-30T23:00:00-07:00")], c=c)
    rc, rep, _ = w.run(d)
    ok = rev(rep).get("USD") == D("155.00") and cov(rep).get("outside_window") == 1
    return ("OK" if ok else "FINDING"), f"date-only window in the contract zone: USD {rev(rep).get('USD')}, outside {cov(rep).get('outside_window')}"


def main():
    global PYS, ROWS
    a = sys.argv[1:]
    i = a.index("--")
    opts, M.CMD = a[:i], a[i + 1:]
    if "--pythons" in opts:
        PYS = opts[opts.index("--pythons") + 1].split(",")
    if "--rows" in opts:
        ROWS = int(opts[opts.index("--rows") + 1])
    tmp = Path(tempfile.mkdtemp(prefix="m13a-"))
    tally = {}
    try:
        for f in CASES:
            w = M.Work(tmp / f.__name__)
            try:
                st, msg = f(w)
            except Exception as e:
                st, msg = "ERROR", f"{e.__class__.__name__}: {str(e)[:300]}"
            tally[st] = tally.get(st, 0) + 1
            print(f"{st} {f.__name__}: {msg}", flush=True)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print("SUMMARY " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))


if __name__ == "__main__":
    main()
