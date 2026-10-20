#!/bin/bash
# o13_teeth.sh: run the G05 oracle, then again with the stale-revision check in can_close_finding disabled
# on a scratch copy; o13 must pass on the real tool and fail on the broken one.
set -e; W=$(mktemp -d); git -C "$1" archive HEAD | tar -x -C "$W"; cd "$W"
export PYTHONDONTWRITEBYTECODE=1
python3 examples/capabilities/G05/binding_oracle.py | grep -E "o13|checks"
python3 - <<'PY'
p="employees/quality-security/assurance/quality_os.py"; s=open(p).read()
k="if not same_revision(verified_revision, subject_revision):"
assert k in s; open(p,"w").write(s.replace(k,"if False and not same_revision(verified_revision, subject_revision):",1))
PY
python3 examples/capabilities/G05/binding_oracle.py | grep -E "o13|checks" || true
rm -rf "$W"
