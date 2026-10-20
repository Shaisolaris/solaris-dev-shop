"""M09 h1 probe (Grok self-validation, not independent review). Anchors, aliases and tags in sequence-item positions the
G09 h1 test does not use, each in a full Deployment, plus controls that must stay clean. Usage: PY m09h1_probe.py REPO OUT.json"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(sys.argv[1]); OUT = sys.argv[2]
TOOL = REPO / "employees/infrastructure/kubernetes-specialist/k8s_manifest_check.py"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
BASE = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: shop
spec:
  replicas: 1
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      {C}
"""
GOOD = """- name: web
        image: web:1
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /
            port: 8080
        resources:
          requests: {cpu: 100m, memory: 64Mi}
          limits: {memory: 128Mi}"""
CASES = {  # name: (container block, expected line of the refusal or None for clean)
    "anchor on container item": (GOOD.replace("- name: web", "- &c name: web", 1), 17),
    "tag on container item": (GOOD.replace("- name: web", "- !Container name: web", 1), 17),
    "anchor on port item": (GOOD.replace("- containerPort: 8080", "- &p containerPort: 8080"), 20),
    "alias as port item": (GOOD.replace("- containerPort: 8080", "- *p"), 20),
    "tag on port item": (GOOD.replace("- containerPort: 8080", "- !!map containerPort: 8080"), 20),
    "anchor on a bare item, mapping below": (GOOD.replace("- name: web", "- &c\n        name: web", 1), 17),
    "clean control": (GOOD, None),
    "ampersand inside a value stays a value": (GOOD.replace("image: web:1", "image: 'web:1&x'"), None),
    "item key starting with a letter then &": (GOOD.replace("path: /", "path: /a&b"), None),
}
rows = []
for name, (c, line) in CASES.items():
    d = Path(tempfile.mkdtemp(prefix="m09h1-")); f = d / "m.yaml"; f.write_text(BASE.replace("{C}", c))
    p = subprocess.run([sys.executable, str(TOOL), "check", str(f), "--json"], capture_output=True, text=True, env=ENV, timeout=60)
    try: js = json.loads(p.stdout)
    except ValueError: js = {}
    u = js.get("unusable") or {}
    if line is None:
        ok = p.returncode == 0 and not u
        got = {"rc": p.returncode, "unusable": u or None}
    else:
        ok = p.returncode == 2 and u.get("line") == line and "anchors, aliases and tags are not read" in u.get("reason", "") and "summary" not in js
        got = {"rc": p.returncode, "line": u.get("line"), "reason": u.get("reason")}
    rows.append({"id": name, "pass": ok, "expected_line": line, "got": got})
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, json.dumps(got)))
    f.unlink(); d.rmdir()
json.dump({"python": sys.version.split()[0], "rows": rows}, open(OUT, "w"), indent=1)
print("M09H1 PROBE %d/%d" % (sum(r["pass"] for r in rows), len(rows)))
