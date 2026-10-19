"""M16 r3 (Grok self-validation): the same 28 M16 mutants on G16 r3 6bd3695. All 28 anchors (r2 set: 22 original,
6 builder re-points read and hand-checked in r2) still match exactly once; none lies on a line changed by r3, and the
two in functions r3 changed (check_citation, _check_target) were re-read by hand and remove the same guard.
stale_reported_invalid uses the re-pointed anchor from r2 directly (the original anchor hits the always-invalid
fallback and is equivalent, as disclosed in r2). Usage: python make_mutants_r3.py SOURCE OUT_DIR M16_MAKE_MUTANTS BUILDER_MAKE_MUTANTS_R2"""
import sys
from pathlib import Path
src, out, mine, theirs = sys.argv[1:5]
ns = {}; exec(Path(mine).read_text().split("def main")[0], ns)
text = Path(theirs).read_text(); ms = text[text.index("MOVED = {"):]
d = 0
for i, ch in enumerate(ms):
    d += ch == "{"; d -= ch == "}"
    if d == 0 and ch == "}": ms = ms[:i + 1]; break
mv = {}; exec(ms, mv); MOVED = mv["MOVED"]
REPOINT = ("numbers_not_checked", "coverage_not_checked", "facts_not_in_quote_ok", "conflict_check_off", "overwrite_input_allowed", "order_dependent_output")
OWN = {"stale_reported_invalid": [('if recorded and recorded != doc["sha256"] and other_snapshot:', 'if False:')]}
code = Path(src).read_text()
for name, old, new in ns["MUTANTS"]:
    reps = OWN.get(name) or (MOVED[name] if name in REPOINT else [(old, new)])
    t = code
    for o, n in reps:
        assert t.count(o) == 1, (name, t.count(o)); t = t.replace(o, n)
    assert t != code, name
    dd = Path(out) / name; dd.mkdir(parents=True, exist_ok=True); (dd / "grounded_eval.py").write_text(t)
    print(name, "re-pointed (r2 M16)" if name in OWN else "re-pointed (builder r2, hand-checked)" if name in REPOINT else "original anchor")
