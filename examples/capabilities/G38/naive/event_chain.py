#!/usr/bin/env python3
"""G38 naive control: a log is fine when every line is JSON with an increasing seq; no hashes, no lock, no anchor."""
import json, sys
from pathlib import Path


def main(a):
    cmd, log = a[0], Path(a[1])
    if cmd == "append":
        n = len(log.read_text().splitlines()) if log.exists() else 0
        body = json.loads(a[a.index("--body") + 1])
        with open(log, "a") as f:
            f.write(json.dumps({"seq": n, "prev": "", "at": "", "claimed_by": a[a.index("--claimed-by") + 1], "body": body, "hash": ""}) + "\n")
        return 0
    good, F = [], []
    for i, l in enumerate(log.read_text().splitlines(), 1):
        try:
            e = json.loads(l)
        except ValueError:
            F.append({"code": "line_not_json", "at": "line %d" % i}); break
        if good and e.get("seq", -1) <= good[-1]["seq"]:
            F.append({"code": "seq_repeat", "at": "line %d" % i}); break
        good.append(e)
    if cmd == "recover":
        Path(a[a.index("--out") + 1]).write_text("".join(json.dumps(e) + "\n" for e in good)); return 0
    counts = {}
    for e in good:
        counts[e.get("claimed_by")] = counts.get(e.get("claimed_by"), 0) + 1
    print(json.dumps({"result": "findings" if F else "verified", "verified": len(good), "findings": F, "anchor": "none",
                      "head": {"seq": len(good) - 1, "hash": good[-1].get("hash") if good else None},
                      "claimed_by": {"counts": counts, "identity": "authenticated"}}))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
