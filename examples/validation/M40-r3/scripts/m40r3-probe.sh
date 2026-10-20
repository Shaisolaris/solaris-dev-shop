# M40 r3 probe W3: an existing --outside folder that the user owns (Grok self-validation)
. $TMP/scripts/pys.sh; W=$CANDIDATE; T=$(mktemp -d $TMP)
mkdir -p $T/mine/src $T/mine/wheels; echo "user data" > $T/mine/src/keep.txt; echo "old" > $T/mine/wheels/other-1.0-py3-none-any.whl; echo "notes" > $T/mine/notes.txt
echo "# before"; (cd $T/mine && find . -type f | sort)
cd $W; PIP_NO_INDEX=1 PYTHONDONTWRITEBYTECODE=1 $P311 employees/quality-security/qa-engineer/host_portability.py wheel-smoke . --outside $T/mine --json > $T/out.json 2> $T/err.txt; echo "rc=$?"
echo "stderr: $(tail -c 300 $T/err.txt)"
echo "# after"; (cd $T/mine && find . -type f -not -path "./src/*" -not -path "./venv/*" | sort; echo "src/keep.txt present: $(test -f src/keep.txt && echo yes || echo no)")
echo "checkout clean lines: $(git -C $W status --porcelain | wc -l)"
rm -rf $T
