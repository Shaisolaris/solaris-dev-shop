#!/usr/bin/env python3
"""M42 union check (Grok self-validation). For each merge commit in the G42 chain, every file both parents changed
from the merge base: every line either parent added must still be in the merge result, and every base line both
parents kept must still be there (trailing commas ignored). Usage: python3 m42_union.py REPO MERGE_SHA..."""
import subprocess, sys
repo = sys.argv[1]
def g(*a): return subprocess.run(["git", "-C", repo] + list(a), capture_output=True, text=True).stdout
def lines(rev, f):
    r = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (rev, f)], capture_output=True, text=True)
    # trailing commas are dropped before comparing: a JSON list item gains or loses its comma when a neighbour is added
    return [l.rstrip().rstrip(",") for l in r.stdout.splitlines()] if r.returncode == 0 else None
bad = 0
for m in sys.argv[2:]:
    p1, p2 = g("log", "-1", "--format=%P", m).split()
    base = g("merge-base", p1, p2).strip()
    c1 = set(g("diff", "--name-only", base, p1).split()); c2 = set(g("diff", "--name-only", base, p2).split())
    both = sorted(c1 & c2)
    print("merge %s parents %s %s base %s: %d files changed on both sides" % (m[:7], p1[:7], p2[:7], base[:7], len(both)))
    for f in both:
        B, L, R, M = (lines(x, f) for x in (base, p1, p2, m))
        if M is None:
            print("  LOST FILE %s" % f); bad += 1; continue
        Bs = set(B or []); Ms = set(M)
        add = [l for l in (L or []) + (R or []) if l not in Bs and l.strip()]
        kept = [l for l in (B or []) if l.strip() and l in set(L or []) and l in set(R or [])]
        lost = sorted({l for l in add + kept if l not in Ms})
        print("  %s %s: added %d, kept-by-both %d, lost %d" % ("OK  " if not lost else "LOST", f, len(add), len(kept), len(lost)))
        for l in lost[:5]: print("     - " + l[:160])
        bad += bool(lost)
print("UNION %s (%d files with lost lines)" % ("OK" if not bad else "FAIL", bad))
sys.exit(1 if bad else 0)
