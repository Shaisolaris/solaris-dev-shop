#!/usr/bin/env python3
"""G09 oracle: does a manifest checker find concrete Kubernetes mistakes, with location, and nothing else?

Runs CHECKER as `python CHECKER check PATH... --json` on synthetic bundles in a temporary directory and judges
its JSON: exit code, finding codes, file and line of each planted mistake, the clean control, unusable input,
that it never claims a deployment and that it leaves its inputs byte-identical. All manifests are synthetic.
Usage: k8s_oracle.py [--tool CHECKER] [--json] [--seed N]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_TOOL = ROOT / "employees/infrastructure/kubernetes-specialist/k8s_manifest_check.py"
CLEAN = HERE / "fixtures/clean"
SHOP = (CLEAN / "shop.yaml").read_text()
WORKER = (CLEAN / "worker.yaml").read_text()
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")


def line_of(text, needle, nth=1):
    i = -1
    for _ in range(nth):
        i = text.index(needle, i + 1)
    return text.count("\n", 0, i) + 1


def sub(text, old, new, count=1):
    assert text.count(old) >= 1, old
    return text.replace(old, new, count)


class Runner(object):
    def __init__(self, tool, tmp):
        self.tool, self.tmp, self.n, self.claims = str(Path(tool).resolve()), Path(tmp), 0, []

    def run(self, files, extra=()):
        self.n += 1
        d = self.tmp / ("case%03d" % self.n)
        d.mkdir()
        paths = []
        for name, text in files.items():
            p = d / name
            p.write_text(text)
            paths.append(str(p))
        before = tree_digest(d)
        try:
            p = subprocess.run([sys.executable, self.tool, "check"] + paths + ["--json"] + list(extra),
                               capture_output=True, text=True, env=ENV, timeout=120, cwd=str(d))
            rc, out = p.returncode, p.stdout
        except subprocess.TimeoutExpired:
            rc, out = "timeout", ""
        try:
            js = json.loads(out)
        except ValueError:
            js = None
        unchanged = tree_digest(d) == before
        self.claims.append((rc, js, unchanged))
        return rc, js, {Path(x).name: x for x in paths}, unchanged


def tree_digest(d):
    h = hashlib.sha256()
    for root, dirs, files in os.walk(str(d)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(p.encode()); h.update(open(p, "rb").read())
        for x in dirs:
            h.update(os.path.join(root, x).encode())
    return h.hexdigest()


def findings(js):
    return (js or {}).get("findings") or []


def errs(js):
    return [f for f in findings(js) if f.get("severity") == "error"]


def has(js, code, fname=None, line=None, sev="error"):
    for f in findings(js):
        if f.get("code") == code and f.get("severity") == sev and (line is None or f.get("line") == line) and \
                (fname is None or os.path.basename(str(f.get("file"))) == fname):
            return True
    return False


def only(js, codes):
    return sorted({f.get("code") for f in errs(js)}) == sorted(codes)


def judge(rc, js, code, fname, line, also_ok=()):
    ok = rc == 1 and has(js, code, fname, line) and only(js, {code} | set(also_ok)) if also_ok == "any" else \
        rc == 1 and has(js, code, fname, line) and {f["code"] for f in errs(js)} <= {code} | set(also_ok)
    return ok, "rc=%s want %s at %s:%s; errors=%s" % (rc, code, fname, line,
                                                       [(f.get("code"), f.get("line")) for f in errs(js)][:6])


# ------------------------------------------------------------------ seeded unseen bundles
WORDS = ["cart", "pay", "search", "ledger", "notify", "auth", "media", "orders", "geo", "quote", "audit", "feed"]
KEYS = ["app", "app.kubernetes.io/name", "component", "svc.example.test/role"]


def gen_bundle(rng, ns):
    app = rng.choice(WORDS) + str(rng.randint(1, 99))
    key = rng.choice(KEYS)
    pname = rng.choice(["http", "web", "api", "h2c", "serve"]) + rng.choice(["", "-a", "x"])
    port = rng.randint(1025, 9999)
    reps = rng.randint(2, 6)
    mem = rng.choice([128, 256, 512])
    L = []
    marks = {}

    def add(s, mark=None):
        L.append(s)
        if mark:
            marks[mark] = len(L)
    add("apiVersion: apps/v1"); add("kind: Deployment"); add("metadata:"); add("  name: %s" % app)
    add("  namespace: %s" % ns); add("spec:"); add("  replicas: %d" % reps, "replicas"); add("  selector:", "wsel")
    add("    matchLabels:"); add("      %s: %s" % (key, app), "wsel_val"); add("  template:"); add("    metadata:")
    add("      labels:"); add("        %s: %s" % (key, app), "tpl_label"); add("    spec:"); add("      containers:")
    add("      - name: main", "container"); add("        image: registry.example.test/%s:%d.%d" % (app, rng.randint(1, 9), rng.randint(0, 20)), "image")
    add("        ports:"); add("        - name: %s" % pname, "cport_name"); add("          containerPort: %d" % port)
    add("        resources:", "resources"); add("          requests:"); add("            cpu: %dm" % rng.choice([100, 200, 500]), "req_cpu")
    add("            memory: %dMi" % mem, "req_mem"); add("          limits:"); add("            memory: %dMi" % (mem * 2), "lim_mem")
    add("        readinessProbe:", "readiness"); add("          httpGet:"); add("            path: /ready")
    add("            port: %s" % pname, "rport"); add("          periodSeconds: 5"); add("        livenessProbe:", "liveness")
    add("          tcpSocket:"); add("            port: %s" % pname, "lport"); add("          periodSeconds: 15")
    add("---"); add("apiVersion: v1"); add("kind: Service"); add("metadata:"); add("  name: %s" % app)
    add("  namespace: %s" % ns); add("spec:"); add("  selector:", "ssel"); add("    %s: %s" % (key, app), "ssel_val")
    add("  ports:"); add("  - port: 80"); add("    targetPort: %s" % pname, "tport")
    add("---"); add("apiVersion: policy/v1"); add("kind: PodDisruptionBudget"); add("metadata:")
    add("  name: %s" % app); add("  namespace: %s" % ns); add("spec:"); add("  maxUnavailable: 1", "pdb_max")
    add("  selector:", "psel"); add("    matchLabels:"); add("      %s: %s" % (key, app), "psel_val")
    return L, marks, dict(app=app, key=key, pname=pname, port=port, reps=reps)


DEFECTS = [
    ("svc_selector_typo", "ssel", "SERVICE_SELECTOR_NO_MATCH", lambda L, m, i: L.__setitem__(m["ssel_val"] - 1, L[m["ssel_val"] - 1] + "x")),
    ("tport_name_typo", "tport", "SERVICE_TARGETPORT_NAME_UNKNOWN", lambda L, m, i: L.__setitem__(m["tport"] - 1, "    targetPort: %sz" % i["pname"])),
    ("tpl_label_drift", "wsel", "WORKLOAD_SELECTOR_TEMPLATE_MISMATCH", None),
    ("rport_name_typo", "rport", "PROBE_PORT_NAME_UNKNOWN", lambda L, m, i: L.__setitem__(m["rport"] - 1, "            port: %sq" % i["pname"])),
    ("no_mem_limit", "resources", "RESOURCES_MISSING", lambda L, m, i: L.__setitem__(m["lim_mem"] - 1, "            cpu: 2")),
    ("req_over_limit", "req_mem", "REQUEST_EXCEEDS_LIMIT", lambda L, m, i: L.__setitem__(m["req_mem"] - 1, "            memory: 9Gi")),
    ("latest_tag", "image", "IMAGE_TAG_MUTABLE", lambda L, m, i: L.__setitem__(m["image"] - 1, "        image: registry.example.test/%s:latest" % i["app"])),
    ("pdb_blocks", "pdb_max", "PDB_BLOCKS_EVICTION", lambda L, m, i: L.__setitem__(m["pdb_max"] - 1, "  minAvailable: %d" % i["reps"])),
    ("pdb_selector_typo", "psel", "PDB_SELECTOR_NO_MATCH", lambda L, m, i: L.__setitem__(m["psel_val"] - 1, L[m["psel_val"] - 1] + "-old")),
    ("readiness_dropped", None, "READINESS_PROBE_MISSING", None),
]


def plant(name, L, m, info):
    L = list(L)
    if name == "tpl_label_drift":
        # template label changes, selector stays: Service and PDB stop matching too, so they are expected as well
        L[m["tpl_label"] - 1] = L[m["tpl_label"] - 1] + "-v2"
        return L, m["wsel"], {"SERVICE_SELECTOR_NO_MATCH", "PDB_SELECTOR_NO_MATCH"}
    if name == "readiness_dropped":
        r = m["readiness"] - 1
        del L[r:r + 5]
        return L, m["container"], set()
    for n, at, code, fn in DEFECTS:
        if n == name:
            fn(L, m, info)
            return L, m[at], set()


# ------------------------------------------------------------------ checks
def run_checks(tool, seed):
    tmp = tempfile.mkdtemp(prefix="g09-oracle-")
    R = Runner(tool, tmp)
    out = []

    def chk(cid, desc, ok, detail=""):
        out.append({"id": cid, "desc": desc, "ok": bool(ok), "detail": detail})

    try:
        # o1 clean control
        rc, js, _, _ = R.run({"shop.yaml": SHOP, "worker.yaml": WORKER})
        ok = rc == 0 and js is not None and not findings(js) and js.get("summary", {}).get("status") == "clean"
        chk("o1", "clean control: exit 0, no findings", ok, "rc=%s findings=%s" % (rc, [f.get("code") for f in findings(js)][:5]))

        # o2 service selector typo (value), with location
        t = sub(SHOP, "  selector:\n    app.kubernetes.io/name: web\n    tier: frontend", "  selector:\n    app.kubernetes.io/name: web\n    tier: front-end")
        rc, js, _, _ = R.run({"shop.yaml": t, "worker.yaml": WORKER})
        ok, d = judge(rc, js, "SERVICE_SELECTOR_NO_MATCH", "shop.yaml", line_of(t, "  selector:\n    app.kubernetes.io/name: web\n    tier: front-end") )
        ok = ok and not has(js, "READINESS_PROBE_MISSING")
        chk("o2", "Service selector matching no pods: located at the Service selector", ok, d)

        # o3 named targetPort unknown
        t = sub(SHOP, "      targetPort: http\n", "      targetPort: https\n")
        rc, js, _, _ = R.run({"shop.yaml": t, "worker.yaml": WORKER})
        ok, d = judge(rc, js, "SERVICE_TARGETPORT_NAME_UNKNOWN", "shop.yaml", line_of(t, "      targetPort: https"))
        chk("o3", "Service targetPort naming no container port", ok, d)

        # o4 workload selector vs template labels (API rejects); Service still matches the template
        t = sub(SHOP, "      app.kubernetes.io/name: web\n      tier: frontend\n  strategy", "      app.kubernetes.io/name: web\n      tier: web-frontend\n  strategy")
        rc, js, _, _ = R.run({"shop.yaml": t, "worker.yaml": WORKER})
        ok, d = judge(rc, js, "WORKLOAD_SELECTOR_TEMPLATE_MISMATCH", "shop.yaml", line_of(t, "  selector:\n    matchLabels:\n      app.kubernetes.io/name: web\n      tier: web-frontend"))
        chk("o4", "Deployment selector not matching its own template", ok, d)

        # o5 probe named port unknown (readiness), in the second file
        t = sub(WORKER, "tcpSocket: {port: grpc}", "tcpSocket: {port: grcp}")
        rc, js, _, _ = R.run({"shop.yaml": SHOP, "worker.yaml": t})
        ok, d = judge(rc, js, "PROBE_PORT_NAME_UNKNOWN", "worker.yaml", line_of(t, "tcpSocket: {port: grcp}"))
        chk("o5", "liveness probe on an unknown named port (flow mapping, second file)", ok, d)

        # o6 probe rules the API enforces
        t = sub(SHOP, "            periodSeconds: 10\n            timeoutSeconds: 5\n", "            periodSeconds: 10\n            timeoutSeconds: 5\n            successThreshold: 2\n")
        rc, js, _, _ = R.run({"shop.yaml": t, "worker.yaml": WORKER})
        ok1, d1 = judge(rc, js, "PROBE_SUCCESS_THRESHOLD", "shop.yaml", line_of(t, "successThreshold: 2"))
        t2 = sub(SHOP, "            httpGet:\n              path: /readyz\n", "            exec: {command: [cat, /tmp/ready]}\n            httpGet:\n              path: /readyz\n")
        rc2, js2, _, _ = R.run({"shop.yaml": t2, "worker.yaml": WORKER})
        ok2, d2 = judge(rc2, js2, "PROBE_HANDLER_INVALID", "shop.yaml", line_of(t2, "          readinessProbe:"))
        chk("o6", "liveness successThreshold 2 and a probe with two handlers", ok1 and ok2, d1 + " | " + d2)

        # o7 resources: missing memory limit flagged; cpu limit standing in for the request is not
        t = sub(SHOP, "            limits:\n              memory: 384Mi\n", "            limits:\n              cpu: 500m\n")
        rc, js, _, _ = R.run({"shop.yaml": t, "worker.yaml": WORKER})
        ok1, d1 = judge(rc, js, "RESOURCES_MISSING", "shop.yaml", line_of(t, "          resources:\n            requests: {cpu: 250m"))
        ok1 = ok1 and any("limits.memory" in str(f.get("reason")) and "requests.cpu" not in str(f.get("reason")) for f in errs(js))
        t2 = sub(WORKER, "          requests:\n            cpu: \"1\"\n            memory: 1Gi\n", "          requests:\n            memory: 1Gi\n")
        rc2, js2, _, _ = R.run({"shop.yaml": SHOP, "worker.yaml": t2})
        ok2 = rc2 == 0 and not findings(js2)
        chk("o7", "missing memory limit located; a cpu limit counts as the request", ok1 and ok2, d1 + " | limit-as-request rc=%s findings=%s" % (rc2, [f.get("code") for f in findings(js2)]))

        # o8 quantities: request above limit across units; equal values in different units accepted
        t = sub(SHOP, "requests: {cpu: 250m, memory: 256Mi}", "requests: {cpu: 250m, memory: 0.5Gi}")
        rc, js, _, _ = R.run({"shop.yaml": t, "worker.yaml": WORKER})
        ok1, d1 = judge(rc, js, "REQUEST_EXCEEDS_LIMIT", "shop.yaml", line_of(t, "memory: 0.5Gi"))
        t2 = sub(SHOP, "requests: {cpu: 250m, memory: 256Mi}", "requests: {cpu: 250m, memory: 0.375Gi}")
        t2 = sub(t2, "              memory: 384Mi", "              memory: 402653184")
        rc2, js2, _, _ = R.run({"shop.yaml": t2, "worker.yaml": WORKER})
        t3 = sub(SHOP, "requests: {cpu: 250m, memory: 256Mi}", "requests: {cpu: 250m, memory: 256MB}")
        rc3, js3, _, _ = R.run({"shop.yaml": t3, "worker.yaml": WORKER})
        ok3, d3 = judge(rc3, js3, "RESOURCE_QUANTITY_INVALID", "shop.yaml", line_of(t3, "memory: 256MB"))
        ok = ok1 and rc2 == 0 and not errs(js2) and ok3
        chk("o8", "quantity arithmetic: 0.5Gi > 384Mi, 0.375Gi == 402653184, 256MB invalid", ok,
            d1 + " | equal rc=%s %s | %s" % (rc2, [f.get("code") for f in errs(js2)], d3))

        # o9 readiness missing behind a Service
        t = sub(WORKER, "        readinessProbe:\n          grpc: {port: 7000}\n          periodSeconds: 5\n", "")
        rc, js, _, _ = R.run({"shop.yaml": SHOP, "worker.yaml": t})
        ok, d = judge(rc, js, "READINESS_PROBE_MISSING", "worker.yaml", line_of(t, "      - name: ledger"))
        chk("o9", "Service-backed container without readinessProbe", ok, d)

        # o10 HPA on cpu with no cpu request (and no limit) on the target
        t = sub(SHOP, "requests: {cpu: 250m, memory: 256Mi}", "requests: {memory: 256Mi}")
        rc, js, _, _ = R.run({"shop.yaml": t, "worker.yaml": WORKER})
        ok = rc == 1 and has(js, "HPA_TARGET_NO_REQUEST", "shop.yaml", line_of(t, "  scaleTargetRef:")) and \
            {f["code"] for f in errs(js)} == {"HPA_TARGET_NO_REQUEST", "RESOURCES_MISSING"}
        chk("o10", "HPA scaling on cpu for a target without cpu requests", ok,
            "rc=%s errors=%s" % (rc, [(f.get("code"), f.get("line")) for f in errs(js)]))

        # o11 PDB that blocks every drain, and a PDB selecting nothing
        t = sub(WORKER, "  minAvailable: 1\n", "  minAvailable: 2\n")
        rc, js, _, _ = R.run({"shop.yaml": SHOP, "worker.yaml": t})
        ok1, d1 = judge(rc, js, "PDB_BLOCKS_EVICTION", "worker.yaml", line_of(t, "  minAvailable: 2"))
        t2 = sub(WORKER, "values: [ledger]", "values: [ledgers]")
        rc2, js2, _, _ = R.run({"shop.yaml": SHOP, "worker.yaml": t2})
        ok2, d2 = judge(rc2, js2, "PDB_SELECTOR_NO_MATCH", "worker.yaml", line_of(t2, "  selector:\n    matchExpressions"))
        chk("o11", "PDB minAvailable equal to replicas; PDB matchExpressions selecting nothing", ok1 and ok2, d1 + " | " + d2)

        # o12 mutable images, including a registry with a port and no tag
        t = sub(SHOP, "image: registry.example.test/shop/web:1.4.2", "image: registry.example.test:5000/shop/web")
        rc, js, _, _ = R.run({"shop.yaml": t, "worker.yaml": WORKER})
        ok1, d1 = judge(rc, js, "IMAGE_TAG_MUTABLE", "shop.yaml", line_of(t, "image: registry.example.test:5000/shop/web"))
        t2 = sub(WORKER, "image: registry.example.test/shop/report:2.0.1", "image: registry.example.test/shop/report:latest")
        rc2, js2, _, _ = R.run({"shop.yaml": SHOP, "worker.yaml": t2})
        ok2, d2 = judge(rc2, js2, "IMAGE_TAG_MUTABLE", "worker.yaml", line_of(t2, "report:latest"))
        chk("o12", "untagged image behind a registry port; latest tag in a CronJob", ok1 and ok2, d1 + " | " + d2)

        # o13 namespaces are separate; scale: 40 namespaces, one planted defect
        ops = SHOP.replace("namespace: shop", "namespace: ops")
        ops = ops.split("---\n")
        ops_svc = [d for d in ops if "kind: Service" in d][0]
        rc, js, _, _ = R.run({"shop.yaml": SHOP, "worker.yaml": WORKER, "ops-svc.yaml": ops_svc,
                              "ops-other.yaml": WORKER.replace("namespace: shop", "namespace: ops")})
        ok1, d1 = judge(rc, js, "SERVICE_SELECTOR_NO_MATCH", "ops-svc.yaml", line_of(ops_svc, "  selector:"))
        files = {}
        rng = random.Random(seed)
        for k in range(40):
            L, m, info = gen_bundle(rng, "team-%02d" % k)
            if k == 27:
                L, at, _ = plant("tport_name_typo", L, m, info)
                want_line = at
            files["team-%02d.yaml" % k] = "\n".join(L) + "\n"
        t0 = time.time()
        rc2, js2, _, _ = R.run(files)
        el = time.time() - t0
        ok2 = rc2 == 1 and [(os.path.basename(f["file"]), f["line"], f["code"]) for f in errs(js2)] == \
            [("team-27.yaml", want_line, "SERVICE_TARGETPORT_NAME_UNKNOWN")] and (js2 or {}).get("objects") == 120 and el < 30
        chk("o13", "namespace scoping; 40 namespaces / 120 objects with exactly one planted defect", ok1 and ok2,
            d1 + " | scale rc=%s objects=%s errors=%s %.1fs" % (rc2, (js2 or {}).get("objects"),
                                                              [(os.path.basename(str(f.get("file"))), f.get("line"), f.get("code")) for f in errs(js2)][:4], el))

        # o14 unusable input: refuse, with location, and do not report clean
        cases = [("tpl.yaml", SHOP.replace("image: registry.example.test/shop/web:1.4.2", "image: {{ .Values.image }}"), "TEMPLATE_UNRENDERED", "{{ .Values.image }}"),
                 ("anchor.yaml", SHOP.replace("    spec:\n      terminationGracePeriodSeconds", "    spec: &pod\n      terminationGracePeriodSeconds"), "YAML_UNSUPPORTED", "spec: &pod"),
                 ("tab.yaml", SHOP.replace("    app.kubernetes.io/name: web\n  ", "\tapp.kubernetes.io/name: web\n  ", 1), "YAML_UNSUPPORTED", "\tapp.kubernetes.io")]
        bad = []
        for name, text, code, needle in cases:
            rc, js, _, _ = R.run({name: text})
            u = (js or {}).get("unusable") or {}
            if not (rc == 2 and u.get("code") == code and u.get("line") == line_of(text, needle) and not findings(js)
                    and (js or {}).get("summary") is None):
                bad.append((name, rc, u.get("code"), u.get("line"), line_of(text, needle)))
        rc, js, _, _ = R.run({"empty.yaml": "# nothing here\n---\n"})
        if rc != 2:
            bad.append(("empty", rc))
        chk("o14", "unrendered template, anchors, tab indent and empty input refused with exit 2 and location", not bad, str(bad))

        # o15 duplicate key hides a value
        t = sub(SHOP, "          image: registry.example.test/shop/web:1.4.2\n", "          image: registry.example.test/shop/web:1.4.2\n          image: registry.example.test/shop/web:1.3.9\n")
        rc, js, _, _ = R.run({"shop.yaml": t, "worker.yaml": WORKER})
        ok, d = judge(rc, js, "DUPLICATE_KEY", "shop.yaml", line_of(t, "web:1.3.9"))
        chk("o15", "duplicate key reported at the repeated line", ok, d)

        # o16 seeded unseen bundles: clean is clean, each planted defect found at its line
        rng = random.Random(seed * 7 + 1)
        bad = []
        names = [d[0] for d in DEFECTS]
        for trial in range(12):
            ns = "ns-%d" % rng.randint(1, 999)
            L, m, info = gen_bundle(rng, ns)
            rc, js, _, _ = R.run({"app.yaml": "\n".join(L) + "\n"})
            if rc != 0 or findings(js):
                bad.append(("clean", trial, rc, [f.get("code") for f in findings(js)][:3]))
                continue
            name = names[trial % len(names)] if trial < len(names) else rng.choice(names)
            L2, at, extra = plant(name, L, m, info)
            code = [d[2] for d in DEFECTS if d[0] == name][0]
            rc, js, _, _ = R.run({"app.yaml": "\n".join(L2) + "\n"})
            got = {f["code"] for f in errs(js)}
            if not (rc == 1 and has(js, code, "app.yaml", at) and got <= {code} | extra):
                bad.append((name, rc, at, [(f.get("code"), f.get("line")) for f in errs(js)][:4]))
        chk("o16", "12 seeded unseen bundles (random labels, ports, namespaces): clean, then one defect each", not bad, str(bad)[:400])

        # s1 never claims a deployment or a cluster; inputs unchanged; tool source has no process/network use
        claims_ok = all(unch and js is not None and js.get("deployed") is False and js.get("applied") is False and
                        js.get("cluster_contacted") is False and "no cluster" in str(js.get("evidence_scope"))
                        for rc, js, unch in R.claims)
        src = Path(tool).read_text() if Path(tool).is_file() else ""
        forbidden = [w for w in ("import subprocess", "import socket", "urllib", "http.client", "os.system", "os.popen", "kubectl\"", "'kubectl'")
                     if w in src]
        chk("s1", "every run: deployed/applied/cluster_contacted false, scope stated, inputs byte-identical; no process or network use",
            claims_ok and not forbidden and R.n > 0, "runs=%d forbidden=%s" % (R.n, forbidden))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=str(DEFAULT_TOOL))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--seed", type=int, default=909)
    a = ap.parse_args()
    if not Path(a.tool).is_file():
        res = [{"id": "o0", "desc": "checker exists", "ok": False, "detail": "no such file: %s" % a.tool}]
    else:
        res = run_checks(a.tool, a.seed)
    n = sum(1 for c in res if c["ok"])
    if a.json:
        print(json.dumps({"checks": res, "passed": n, "total": len(res)}, indent=1))
    else:
        for c in res:
            print("%s %s %s%s" % ("PASS" if c["ok"] else "FAIL", c["id"], c["desc"], "" if c["ok"] else "  [" + c["detail"] + "]"))
        print("%s %d/%d" % ("ACCEPTED" if n == len(res) else "REJECTED", n, len(res)))
    return 0 if n == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
