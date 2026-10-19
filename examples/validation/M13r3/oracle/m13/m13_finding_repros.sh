#!/bin/zsh
# Usage: zsh m13_finding_repros.sh PY_MAIN PY39 CANDIDATE_TREE   (run against the 7da20d4 worktree)
export PYTHONDONTWRITEBYTECODE=1
exec "$1" "${0:A:h}/m13_finding_repros.py" "$1" "$2" "$3/employees/data/data-engineer/csv_reconcile.py"
