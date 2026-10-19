#!/bin/zsh
# M38 findings probe (Grok self-validation): reproduces P2-1, P2-2, P3-1..P3-3 and P4-1 with the CLIs on a private copy.
C=$(mktemp -d /tmp/m38pr-XXXXXX); rsync -a --exclude .git /tmp/m38-eval/ $C/c/; cd $C/c; export PYTHONDONTWRITEBYTECODE=1
P=employees/quality-security/security-auditor/provenance_check.py; E=employees/engineering/blockchain-developer/event_chain.py; F=examples/capabilities/G38/fixtures
print "== P2-1 MIT text with an added commercial-use restriction"; cp -R $F/repo-clean $C/r1; print "\nThe Software may not be used for commercial purposes without written permission." >> $C/r1/LICENSE
tail -2 $C/r1/LICENSE; python3 $P check $C/r1; print "exit $?"
print "== P2-1b a three-line Apache header alone"; cp -R $F/repo-clean $C/r1b; printf 'Apache License\nVersion 2.0, January 2004\nTERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n' > $C/r1b/LICENSE; python3 $P check $C/r1b | head -1
print "== P2-2 append after a verified last event whose newline was lost"; head -c -1 $F/events.jsonl > $C/e.jsonl 2>/dev/null || python3 -c "import sys;d=open('$F/events.jsonl','rb').read().rstrip(b'\n');open('$C/e.jsonl','wb').write(d)"
python3 $E verify $C/e.jsonl | head -1; python3 $E append $C/e.jsonl --claimed-by "Ops (synthetic)" --body '{"step":"next"}'; print "append exit $?"; python3 $E verify $C/e.jsonl | head -3; print "verify exit ${pipestatus[1]}"
print "== P3-1 a plugin.json outside employees/ (chief-of-staff) is not checked"; cp chief-of-staff/plugin.json $C/cos.bak; sed -i '' 's/"license": "MIT"/"license": "Apache-2.0"/' chief-of-staff/plugin.json; python3 $P check . --exclude $F | head -1; print "exit ${pipestatus[1]}"; cp $C/cos.bak chief-of-staff/plugin.json
print "== P3-2 README '## License' then 'GPL, see LICENSE.' is not read"; cp -R $F/repo-clean $C/r2; sed -i '' 's/^MIT\. See LICENSE and NOTICE\.md\./GPL, see LICENSE./' $C/r2/README.md; grep -A2 "## License" $C/r2/README.md; python3 $P check $C/r2 | head -1; print "exit ${pipestatus[1]}"
print "== P3-3 integrity.subject carries the digest of a file that does not match the manifest"; cp -R $F/repo-clean $C/r3; print "x" >> $C/r3/src/app.py; python3 $P check $C/r3 --manifest $C/r3/MANIFEST.sha256 --json | python3 -c "import json,sys;d=json.load(sys.stdin);print('findings',[(f['code'],f['path']) for f in d['findings']]);print('subject has src/app.py:', 'src/app.py' in d['integrity']['subject']['digests'], d['integrity']['subject']['digests'].get('src/app.py'))"
print "== P4-1 --out into a missing folder"; python3 $P check $F/repo-clean --out $C/nodir/r.json 2>&1 | tail -1; print "exit ${pipestatus[1]}"; python3 $E recover $F/events.jsonl --out $C/nodir/e.jsonl 2>&1 | tail -1; print "exit ${pipestatus[1]}"
cd /tmp; rm -rf $C
