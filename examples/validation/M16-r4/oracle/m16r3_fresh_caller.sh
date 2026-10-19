#!/bin/zsh
# Fresh caller: a copy of the candidate tree (no .git), env -i with a new HOME, a PATH shim mapping python3 to
# the given Python, and only the commands printed in grounded-answer-evals.md, on the unseen allotment
# snapshot (v1, then v2) written by m16_world.py. Usage: m16_fresh_caller.sh PYTHON CANDIDATE_TREE ORACLE_DIR
P=$1; C=$2; O=$3
F=/tmp/m16r3-fresh; rm -rf $F; mkdir -p $F/home $F/bin $F/work; rsync -a --exclude .git $C/ $F/repo/; ln -s $P $F/bin/python3
$P - $O $F/work <<'PY'
import sys; sys.path.insert(0, sys.argv[1]); import m16_world as W; from pathlib import Path
w = Path(sys.argv[2]); W.write_snapshot(w / "snapshot-v1", W.V1); W.write_snapshot(w / "snapshot-v2", W.V2)
W.write_questions(w / "questions-v1.jsonl", W.QV1); W.write_questions(w / "questions-v2.jsonl", W.QV2)
(w / "fault.json").write_text('{"retrieve": {"b05": 1}}')
PY
cat > $F/caller.sh <<'IN'
set -u
cd "$HOME/../work"
T=../repo/employees/engineering/llm-agent-designer/grounded_eval.py
echo "python3 = $(python3 -c 'import sys; print(sys.version.split()[0])'); env vars: $(env | wc -l | tr -d ' ')"
x() { echo "\$ $*"; "$@"; echo "[exit $?]"; }
echo "-- 1 answer on v1 (doc command 1)"
x python3 $T answer --corpus snapshot-v1 --questions questions-v1.jsonl --out answers-v1.jsonl --journal journal-v1.jsonl
echo "-- 2 evaluate on v1 (doc command 2)"
x python3 $T evaluate --corpus snapshot-v1 --questions questions-v1.jsonl --answers answers-v1.jsonl --json --out report-v1.json > /dev/null
python3 -c "import json; r=json.load(open('report-v1.json')); print('status', r['status'], r['metrics'], '|', r['provenance']['evidence'])"
echo "-- 3 source change: old answers against v2 (doc 'Source change'), then re-answer"
x python3 $T evaluate --corpus snapshot-v2 --questions questions-v2.jsonl --answers answers-v1.jsonl
x python3 $T answer --corpus snapshot-v2 --questions questions-v2.jsonl --out answers-v2.jsonl --journal journal-v2.jsonl
x python3 $T evaluate --corpus snapshot-v2 --questions questions-v2.jsonl --answers answers-v2.jsonl
echo "-- 4 fault drill (doc 'Recoverable tool failure'), then --resume (doc command 3)"
x python3 $T answer --corpus snapshot-v1 --questions questions-v1.jsonl --out answers-drill.jsonl --journal journal-drill.jsonl --fault-plan fault.json
ls answers-drill.jsonl 2>/dev/null || echo "no answers file after the failure (as documented)"
x python3 $T answer --corpus snapshot-v1 --questions questions-v1.jsonl --out answers-drill.jsonl --journal journal-drill.jsonl --resume
cmp answers-drill.jsonl answers-v1.jsonl && echo "resume output byte-identical to the unbroken run"
echo "-- 5 hand answer: q b07 worked out from waiting.md by the caller"
python3 -c "import json; [print(r['id'], r['answer'], r['citations'][0]['doc'], r['citations'][0]['start'], r['citations'][0]['end']) for r in map(json.loads, open('answers-v1.jsonl')) if r.get('id')=='b07']"
python3 -c "t=open('snapshot-v1/waiting.md', encoding='utf-8').read(); s=t.index('Applicants'); e=t.index('for.')+4; print('hand span', s, e, t[s:e])"
IN
env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin zsh $F/caller.sh
