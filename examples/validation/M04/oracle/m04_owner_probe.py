"""M04 owner-conflict probe (Grok self-validation, added after the oracle run; OBS evidence for finding F-owner).
Same order and revision re-issued with a different owner after the brief was written. Prints what the delivered brief,
the ledger record and status say about the owner. Usage: PY m04_owner_probe.py PY HANDOFF"""
import sys, os, json, shutil
sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2], "/tmp/m04o-ownerout"]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "m04_oracle.py")).read(); exec(src[:src.index("# C01 clean control")])
d = world(); print("stop-after brief:", run(d, "run", "order.json", "--worker", "ana", "--stop-after", "brief")[0])
world(owner="support: Someone Else", d=d); rc, o = run(d, "run", "order.json", "--worker", "ben"); print("rerun with new owner: rc", rc); print(o)
print("brief owner lines:", [l for l in rd(brief(d), "r").splitlines() if "wner" in l])
print("ledger record:", ledger(d)[-1][:400] if ledger(d) else None)
print("status:", run(d, "status", "order.json")[1])
shutil.rmtree(d); shutil.rmtree("/tmp/m04o-ownerout", ignore_errors=True)
