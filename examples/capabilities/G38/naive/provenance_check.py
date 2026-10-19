#!/usr/bin/env python3
"""G38 naive control: trusts the first line of LICENSE and pyproject only; a manifest file only has to exist."""
import json, re, sys
from pathlib import Path


def main(a):
    root = Path(a[1]); F = []
    first = (root / "LICENSE").read_text().splitlines()[0].split()[0] if (root / "LICENSE").exists() else "unknown"
    py = (root / "pyproject.toml").read_text() if (root / "pyproject.toml").exists() else ""
    m = re.search(r'license\s*=\s*\{?\s*(?:text\s*=\s*)?"([^"]+)"', py)
    if m and m.group(1) != first:
        F.append({"code": "license_mismatch", "path": "pyproject.toml"})
    integ = None
    if "--manifest" in a:
        rows = [l.split("  ", 1) for l in Path(a[a.index("--manifest") + 1]).read_text().splitlines() if "  " in l]
        miss = [p for _, p in rows if not (root / p).exists()]
        F += [{"code": "artifact_missing", "path": p} for p in miss]
        integ = {"listed": len(rows), "matching": len(rows) - len(miss), "subject": {"digests": {p: h for h, p in rows}}}
    r = {"result": "findings" if F else "consistent", "license": first, "declarations": 1, "findings": F, "integrity": integ, "excluded": {}}
    print(json.dumps(r))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
