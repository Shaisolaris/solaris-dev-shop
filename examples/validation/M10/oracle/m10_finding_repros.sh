#!/bin/zsh
# Usage: m10_finding_repros.sh PY_MAIN PY39 CANDIDATE_TREE   (run against the 6af7849 worktree)
export PYTHONDONTWRITEBYTECODE=1
exec "$1" "${0:A:h}/m10_finding_repros.py" "$1" "$2" "$3/employees/infrastructure/network-engineer/netdiag.py"
