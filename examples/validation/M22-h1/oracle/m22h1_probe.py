#!/usr/bin/env python3
"""M22 h1 probe (Grok self-validation, not independent review). Black-box checks of the G22 h1 export-g14 refusal,
using the shipped september fixture lines only. Usage: PY m22h1_probe.py SRC OUT.json"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
SRC = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]; ROWS = []
TOOL = SRC / "employees/specialized/payments-specialist/payment_ledger.py"
G14 = SRC / "employees/leadership/cfo/cash_revenue_reconcile.py"
FIX = SRC / "examples/capabilities/G22/fixtures"
LINES = [l for l in (FIX / "september.jsonl").read_text().splitlines() if l.strip()]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
NOW = "1790000200"  # the fixture README and tests ingest with --now 1790000200
SEP = ("--period-start", "2026-09-01T00:00:00Z", "--period-end", "2026-10-01T00:00:00Z")
def eid(l): return json.loads(json.loads(l)["body"])["id"]
def run(*a, tool=TOOL):
    p = subprocess.run([sys.executable, str(tool)] + [str(x) for x in a], capture_output=True, text=True, env=ENV, timeout=300)
    return p.returncode, p.stdout, p.stderr
class L:
    def __init__(self):
        self.d = Path(tempfile.mkdtemp(prefix="m22h1-")); self.db = self.d / "l.db"; self.n = 0
        assert run("init", "--db", self.db, "--catalog", FIX / "catalog.json")[0] == 0
    def ingest(self, lines):
        self.n += 1; p = self.d / ("b%d.jsonl" % self.n); p.write_text("\n".join(lines) + "\n")
        return run("ingest", "--db", self.db, "--secret-file", FIX / "test-secret.txt", "--events", p, "--now", NOW)[0]
    def export(self, name="books", period=SEP):
        out = self.d / name; rc, o, e = run("export-g14", "--db", self.db, "--out", out, *period)
        js = None
        try: js = json.loads(o) if o.strip().startswith("{") else None
        except ValueError: pass
        return rc, out, js, e
    def close(self): shutil.rmtree(self.d, ignore_errors=True)
def row(rid, desc, ok, detail):
    ROWS.append({"id": rid, "desc": desc, "pass": bool(ok), "detail": detail})
    print("%s %s %s %s" % (rid, "PASS" if ok else "FAIL", desc, json.dumps(detail)[:260]))
CLEAN = [l for l in LINES if eid(l) not in ("evt_007", "evt_008")]
# Q1 full stream refused, nothing written
l = L(); l.ingest(LINES); rc, out, js, e = l.export()
ids = sorted(x["id"] for x in (js or {}).get("open", []))
money = (js or {}).get("unapplied_money", [])
row("Q1", "september stream: exit 1, --out not created, open evt_007 and evt_008 listed with the 40.00 refund",
    rc == 1 and not out.exists() and ids == ["evt_007", "evt_008"] and any(m.get("amount") == "40.00" for m in money) and "evt_007" in e,
    {"rc": rc, "out_exists": out.exists(), "open": ids, "money": money})
rc2 = run("check", "--db", l.db)[0]
row("Q2", "check on the same ledger still exit 0 (consistent): refusal is about open items, not corruption", rc2 == 0, {"rc": rc2})
l.close()
# Q3 clean stream exports and G14 reconciles
l = L(); l.ingest(CLEAN); rc, out, js, e = l.export()
g = run("reconcile", out / "package.json", "--json", tool=G14) if rc == 0 else (None, "", "")
c = json.loads(g[1])["currencies"]["USD"] if g[0] == 0 else {}
row("Q3", "september without evt_007/evt_008: exit 0 and G14 reconciles to net cash 32.69",
    rc == 0 and g[0] == 0 and c.get("net_cash") == "32.69" and c.get("recognized_revenue") == "32.69", {"rc": rc, "g14_rc": g[0], "net_cash": c.get("net_cash")})
l.close()
# Q4 a held event blocks export, and the block lifts when the missing events arrive
l = L(); first = [x for x in CLEAN if eid(x) == "evt_004"]; rest = [x for x in CLEAN if eid(x) != "evt_004"]
l.ingest(first); rc_a, out_a, js_a, _ = l.export("a")
held = [x["id"] for x in (js_a or {}).get("open", [])]
l.ingest(rest); rc_b, out_b, js_b, _ = l.export("b")
row("Q4", "refund before its order is held: export refused naming evt_004; after the order and capture arrive export exits 0",
    rc_a == 1 and not out_a.exists() and held == ["evt_004"] and rc_b == 0 and (out_b / "package.json").is_file(),
    {"rc_held": rc_a, "open": held, "rc_after": rc_b})
l.close()
# Q5 an exception can never be cleared, even for a later period with no events in it
l = L(); l.ingest([x for x in LINES if eid(x) != "evt_008"])
rc_a, out_a, js_a, _ = l.export("a")
rc_r = l.ingest([x for x in LINES if eid(x) == "evt_007"])  # re-deliver the same event
rc_b, out_b, js_b, _ = l.export("b", ("--period-start", "2026-11-01T00:00:00Z", "--period-end", "2026-12-01T00:00:00Z"))
cmds = run("--help")[1]
row("Q5", "OBSERVATION: an over-refund exception stays open after re-delivery and also blocks a later empty period (no resolve command)",
    True, {"rc_sep": rc_a, "redeliver_rc": rc_r, "rc_november": rc_b, "open_november": [x["id"] for x in (js_b or {}).get("open", [])],
           "commands": [c for c in ("init", "sign", "ingest", "report", "check", "export-g14", "resolve") if c in cmds]})
OBS_Q5 = {"blocked_forever": rc_b == 1}
l.close()
# Q6 existing non-empty --out is still invalid (exit 2) and untouched
l = L(); l.ingest(CLEAN); o = l.d / "full"; o.mkdir(); (o / "x.txt").write_text("keep")
rc, _, _, e = l.export("full")
row("Q6", "--out that is not empty: exit 2, file kept", rc == 2 and (o / "x.txt").read_text() == "keep", {"rc": rc})
l.close()
json.dump({"python": sys.version.split()[0], "rows": ROWS, "q5_blocked_forever": OBS_Q5["blocked_forever"]}, open(OUT, "w"), indent=1)
print("M22H1 PROBE %d/%d (Q5 observation: export blocked forever after an exception = %s)" % (sum(r["pass"] for r in ROWS), len(ROWS), OBS_Q5["blocked_forever"]))
