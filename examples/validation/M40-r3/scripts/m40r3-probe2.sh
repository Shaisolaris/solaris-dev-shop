. $TMP/scripts/pys.sh; W=$CANDIDATE; T=$(mktemp -d $TMP)
mkdir -p $T/mine/src; echo "user data" > $T/mine/src/keep.txt; echo "notes" > $T/mine/notes.txt
echo "# W3b: build isolation off (setuptools from the interpreter), existing folder with src/keep.txt"
cd $W; PIP_NO_INDEX=1 PIP_NO_BUILD_ISOLATION=0 PYTHONDONTWRITEBYTECODE=1 $P311 employees/quality-security/qa-engineer/host_portability.py wheel-smoke . --outside $T/mine --json > $T/out.json 2> $T/err.txt; echo "rc=$?"
python3 -c "import json;d=json.load(open('$T/out.json'));print('result',d['result'],'findings',d['findings'])"
echo "src/keep.txt present after: $(test -f $T/mine/src/keep.txt && echo yes || echo no); notes.txt present: $(test -f $T/mine/notes.txt && echo yes || echo no)"
echo "checkout clean lines: $(git -C $W status --porcelain --ignored | wc -l)"
rm -rf $T
