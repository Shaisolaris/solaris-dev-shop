"""M16 r2 (Grok self-validation): the same 28 M16 mutants on G16 r2. 22 original anchors still match
exactly once and are used unchanged. 6 anchors moved in r2; for those the builder's re-point (G16
scripts/rework-r2/make_mutants_r2.py MOVED) was read, checked by hand to remove the same guard, and is used.
Usage: python make_mutants_r2.py SOURCE OUT_DIR M16_MAKE_MUTANTS BUILDER_MAKE_MUTANTS_R2"""
import sys
from pathlib import Path
src, out, mine, theirs = sys.argv[1:5]
ns = {}; exec(Path(mine).read_text().split("def main")[0], ns)
tb = {}; exec(Path(theirs).read_text().split("def main")[0].split("R2 = {")[0] if "R2 = {" in Path(theirs).read_text() else "", tb)
text = Path(theirs).read_text(); moved_src = text[text.index("MOVED = {"):]
depth = 0
for i, ch in enumerate(moved_src):
    depth += ch == "{"; depth -= ch == "}"
    if depth == 0 and ch == "}":
        moved_src = moved_src[:i + 1]; break
mv = {}; exec(moved_src, mv); MOVED = mv["MOVED"]
# stale_reported_invalid: the original anchor still matches once in r2 but now hits the new N7 branch (equivalent); the
# correctly re-pointed mutant is scored separately as stale_reported_invalid_repointed (raw/teeth-repointed-3.12.14.tsv).
REPOINT = ("numbers_not_checked", "coverage_not_checked", "facts_not_in_quote_ok", "conflict_check_off",
           "overwrite_input_allowed", "order_dependent_output")
code = Path(src).read_text()
for name, old, new in ns["MUTANTS"]:
    reps = MOVED[name] if name in REPOINT else [(old, new)]
    t = code
    for o, n in reps:
        assert t.count(o) == 1, (name, t.count(o)); t = t.replace(o, n)
    assert t != code, name
    d = Path(out) / name; d.mkdir(parents=True, exist_ok=True); (d / "grounded_eval.py").write_text(t)
    print(name, "re-pointed" if name in REPOINT else "original anchor")
