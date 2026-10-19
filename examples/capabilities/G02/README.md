# G02 activation oracle

`activation_oracle.py` drives an activation command against disposable directories and
checks real outcomes: files, bytes, hashes, Git refs/HEAD/log/index and outside sentinels.
Exit 0 or an echoed path proves nothing on its own, so a no-op fails.

```bash
PY=python3.12
$PY examples/capabilities/G02/activation_oracle.py -- $PY employees/product-project/project-onboarding/activate.py
$PY examples/capabilities/G02/activation_oracle.py -- $PY examples/capabilities/G02/noop_stub.py      # must be REJECTED
$PY examples/capabilities/G02/activation_oracle.py -- $PY examples/capabilities/G02/partial_stub.py   # must be REJECTED
```

Checks: O1 clean activation twice plus resume (byte-identical); O2 owner files kept; O3 real
permission failure between writes, then resume; O4 changed intake during an interruption; O5
blank or omitted deploy model stays UNRESOLVED; O6 symlinked folder and planted temp links
leave outside sentinels unchanged; O7 Git history, staged index and unborn repos unchanged, no
nested init; O8 token-shaped credential refused without echo or writes; O9 six concurrent runs
converge; O10 3000 owner files untouched. Synthetic data only; POSIX (uses chmod and symlinks).
