#!/usr/bin/env python3
"""M09 oracle (Grok self-validation, not independent review; black box). Written from M09.md (mismatched selectors,
missing ports, bad readiness, misleading availability; static diagnostics vs cluster execution) and
k8s-manifest-check.md (codes, severities, exits, limits). Bundles are generated here by my own YAML emitter, which
records the line of every field path, so each planted mistake has a known file, line and path. A core row passes
only if the planted code appears on the right object, path and line, and no other error appears.
Usage: PY m09_oracle.py REPO OUT.json [--tool TOOL.py]. Core rows score; OBS rows record only.
v2 (disclosed): R01 to R12 added after the v1 teeth run (27/43) showed doc rules v1 never exercised (default
targetPort, missing workload selector, matchExpressions, zero-handler probe, StatefulSet readiness, missing
resources, limit standing in for request, memory limit, binary quantities, refused YAML, LimitRange defaults).
Harness error fixed before scoring: the first R09b used 1000M vs 954Mi, which is not an excess (954Mi = 1000341504); now 1001M.
v3 (disclosed): the v2 teeth run (37/43 on 3.13.15) left res_limit_not_request, anchor_ok and tab_ok alive although
the builder's tests kill them. Added R07b (a limit standing in, with no LimitRange in the files, must not be called
RESOURCES_DEFAULTED, which the doc ties to a LimitRange in these files), R10b (each refusal names the planted line),
and OBS O34 (refusal code and reason, plus anchors in a sequence item and a key). v1 and v2 results are kept.
Expectations still come from the doc only."""
import copy, hashlib, json, os, random, shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
TOOL = Path(sys.argv[sys.argv.index("--tool") + 1]).resolve() if "--tool" in sys.argv else REPO / "employees/infrastructure/kubernetes-specialist/k8s_manifest_check.py"
TOP = Path(tempfile.mkdtemp(prefix="m09o-", dir="/tmp")).resolve(); ROWS = []; K = [0]
ENV = {"PATH": "/usr/bin:/bin", "HOME": str(TOP), "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
def row(rid, ok, det, obs=False): ROWS.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": det})
def scal(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    s = str(v)
    return json.dumps(s) if (s == "" or s[0] in "-?:,[]{}#&*!|>'\"%@`0123456789" or ": " in s or s.lower() in ("yes", "no", "on", "off", "true", "false", "null", "~") or s != s.strip()) else s
def emit(objs):
    """Block YAML; returns text and {doc_index: {path: line}} (1-based lines)."""
    L, P = [], []
    def put(node, ind, path, d):
        if isinstance(node, dict):
            for k, v in node.items():
                p = path + ("." if path else "") + k
                if isinstance(v, (dict, list)) and v:
                    L.append(" " * ind + "%s:" % k); d[p] = len(L); put(v, ind + 2, p, d)
                else:
                    L.append(" " * ind + "%s: %s" % (k, "{}" if v == {} else "[]" if v == [] else scal(v))); d[p] = len(L)
        else:
            for i, v in enumerate(node):
                p = "%s[%d]" % (path, i)
                if isinstance(v, dict) and v:
                    first = True
                    for k, x in v.items():
                        pre = " " * ind + ("- " if first else "  "); q = p + "." + k
                        if isinstance(x, (dict, list)) and x: L.append(pre + "%s:" % k); d[q] = len(L); put(x, ind + 4, q, d)
                        else: L.append(pre + "%s: %s" % (k, scal(x))); d[q] = len(L)
                        if first: d[p] = len(L)
                        first = False
                else: L.append(" " * ind + "- " + scal(v)); d[p] = len(L)
    for o in objs:
        if L: L.append("---")
        d = {}; start = len(L) + 1; put(o, 0, "", d); d[""] = start; d["__end"] = len(L); P.append(d)
    return "\n".join(L) + "\n", P
def ns(name): return {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": name}}
def probe(port, path="/readyz"): return {"httpGet": {"path": path, "port": port}, "periodSeconds": 5, "timeoutSeconds": 2, "failureThreshold": 3}
def deploy(name, n, labels, replicas=3, ports=(("http", 8080), ("metrics", 9090)), img=None):
    c = {"name": name, "image": img or "registry.example.test/%s/%s:1.4.2" % (n, name), "ports": [{"name": a, "containerPort": b} for a, b in ports],
         "resources": {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}},
         "readinessProbe": probe(ports[0][0] if ports else 8080), "livenessProbe": probe(ports[0][0] if ports else 8080, "/livez")}
    return {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": name, "namespace": n, "labels": dict(labels)},
            "spec": {"replicas": replicas, "selector": {"matchLabels": dict(labels)}, "template": {"metadata": {"labels": dict(labels)}, "spec": {"containers": [c]}}}}
def svc(name, n, sel, tp="http"): return {"apiVersion": "v1", "kind": "Service", "metadata": {"name": name, "namespace": n}, "spec": {"selector": dict(sel), "ports": [{"name": "http", "port": 80, "targetPort": tp}]}}
def pdb(name, n, sel, **kw):
    s = {"selector": {"matchLabels": dict(sel)}}; s.update(kw or {"minAvailable": 1})
    return {"apiVersion": "policy/v1", "kind": "PodDisruptionBudget", "metadata": {"name": name, "namespace": n}, "spec": s}
def hpa(name, n, lo=3, hi=6, res="cpu"): return {"apiVersion": "autoscaling/v2", "kind": "HorizontalPodAutoscaler", "metadata": {"name": name, "namespace": n},
    "spec": {"scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": name}, "minReplicas": lo, "maxReplicas": hi,
             "metrics": [{"type": "Resource", "resource": {"name": res, "target": {"type": "Utilization", "averageUtilization": 70}}}]}}
def bundle(n="shop", name="web", labels=None):
    labels = labels or {"app.kubernetes.io/name": name, "tier": "frontend"}
    return [ns(n), deploy(name, n, labels), svc(name, n, labels), pdb(name, n, labels), hpa(name, n)]
C = "spec.template.spec.containers[0]"
def run(files, *extra):
    K[0] += 1; d = TOP / ("b%03d" % K[0]); d.mkdir(); paths = []; lines = {}
    for fname, objs in files:
        text, P = emit(objs) if isinstance(objs, list) else (objs, [])
        (d / fname).write_text(text); paths.append(d / fname); lines[fname] = P
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir()}
    cp = subprocess.run([sys.executable, str(TOOL), "check", str(d)] + list(extra) + ["--json"], cwd=str(TOP), env=ENV, capture_output=True, text=True, timeout=120)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir()}
    try: rep = json.loads(cp.stdout)
    except Exception: rep = None
    return cp.returncode, rep, lines, before == after, cp, d
def errs(rep): return [f for f in (rep or {}).get("findings", []) if f.get("severity") == "error"]
def warns(rep): return [f for f in (rep or {}).get("findings", []) if f.get("severity") == "warning"]
def planted(rid, objs, code, doc, path, want_rc=1, sev="error", also=(), exact_line=True, fname="m.yaml"):
    """objs[doc] has the mistake at `path` (relative to the object); exactly that error (plus `also`) and no other."""
    rc, rep, lines, same, cp, _ = run([(fname, objs)]); P = lines[fname][doc]
    want_line = P.get(path); kinds = {f.get("code") for f in (errs(rep) if sev == "error" else warns(rep))}
    hit = [f for f in (rep or {}).get("findings", []) if f.get("code") == code and f.get("severity") == sev and (f.get("file") or "").endswith(fname) and f.get("name") == objs[doc]["metadata"]["name"]]
    line_ok = any((f.get("line") == want_line) if exact_line else (P[""] <= (f.get("line") or 0) <= P["__end"]) for f in hit)
    other = sorted({f["code"] for f in errs(rep)} - {code} - set(also))
    ok = rc == want_rc and bool(hit) and line_ok and not other and same
    row(rid, ok, {"rc": rc, "want_rc": want_rc, "code": code, "hit": [(f.get("line"), f.get("path")) for f in hit], "want_line": want_line, "other_errors": other, "inputs_unchanged": same, "stderr": cp.stderr[-200:]})
    return rep
# P01 clean control: two files, two namespaces, StatefulSet-free shop; exit 0, no errors, claims all false
rc, rep, _, same, cp, _ = run([("a.yaml", bundle()), ("b.yaml", bundle("pay", "api", {"app": "api", "track": "stable"}))])
claims = rep is not None and rep.get("cluster_contacted") is False and rep.get("applied") is False and rep.get("deployed") is False
row("P01_clean_control", rc == 0 and not errs(rep) and claims and same, {"rc": rc, "errors": [f["code"] for f in errs(rep)], "warnings": [f["code"] for f in warns(rep)], "claims_false": claims})
# Mismatched selectors
b = bundle(); b[2]["spec"]["selector"]["tier"] = "front-end"
planted("P02_service_selector_value_typo", b, "SERVICE_SELECTOR_NO_MATCH", 2, "spec.selector")
b = bundle(); b[2]["spec"]["selector"]["track"] = "canary"
planted("P03_service_selector_extra_key", b, "SERVICE_SELECTOR_NO_MATCH", 2, "spec.selector")
b = bundle() + [ns("other")]; b[2]["metadata"]["namespace"] = "other"
rc, rep, lines, same, cp, _ = run([("m.yaml", b[:2] + b[3:] + [b[2]])])
hit = [f for f in errs(rep) if f.get("code") == "SERVICE_SELECTOR_NO_MATCH" and f.get("namespace") == "other"]
unres = [f for f in warns(rep) if f.get("code") == "SERVICE_SELECTOR_UNRESOLVED" and f.get("namespace") == "other"]
row("P04_selector_matches_only_other_namespace", rc in (0, 1) and (bool(hit) or bool(unres)) and not [f for f in errs(rep) if f["code"] != "SERVICE_SELECTOR_NO_MATCH"],
    {"rc": rc, "no_match_error": bool(hit), "unresolved_warning": bool(unres), "note": "doc: a Service whose namespace has no workload in the files is UNRESOLVED (warning); pods elsewhere are never matched"})
# P04b other namespace has its own workload, the Service there selects the shop pods: no endpoints in its namespace
o = deploy("db", "other", {"app": "db"}); s2 = svc("web", "other", {"app.kubernetes.io/name": "web", "tier": "frontend"}); s2["spec"]["ports"][0]["targetPort"] = 8080
rc, rep, lines, same, cp, _ = run([("m.yaml", bundle() + [ns("other"), o, s2])])
hit = [f for f in errs(rep) if f.get("code") == "SERVICE_SELECTOR_NO_MATCH" and f.get("namespace") == "other"]
row("P04b_selector_crosses_namespace_with_local_workload", rc == 1 and bool(hit) and sorted({f["code"] for f in errs(rep)}) == ["SERVICE_SELECTOR_NO_MATCH"], {"rc": rc, "errors": [(f["code"], f.get("namespace")) for f in errs(rep)], "warnings": [f["code"] for f in warns(rep)]})
# P04c omitted namespace is "default": Service without namespace selects a Deployment with namespace: default
d0 = deploy("web", "default", {"app": "web"}); s0 = svc("web", "default", {"app": "web"}); del s0["metadata"]["namespace"]
rc, rep, _, _, _, _ = run([("m.yaml", [d0, s0, pdb("web", "default", {"app": "web"})])])
row("P04c_omitted_namespace_is_default", rc == 0 and not errs(rep) and not [f for f in warns(rep) if f["code"].startswith("SERVICE_SELECTOR")], {"rc": rc, "errors": [f["code"] for f in errs(rep)], "warnings": [f["code"] for f in warns(rep)]})
# P04d Service and Deployment in different files; the finding names the Service's file and line
b = bundle(); b[2]["spec"]["selector"]["tier"] = "fe"; rc, rep, lines, _, _, _ = run([("deploy.yaml", [b[0], b[1], b[3], b[4]]), ("service.yaml", [b[2]])])
hit = [f for f in errs(rep) if f.get("code") == "SERVICE_SELECTOR_NO_MATCH" and (f.get("file") or "").endswith("service.yaml") and f.get("line") == lines["service.yaml"][0]["spec.selector"]]
row("P04d_cross_file_selector", rc == 1 and bool(hit) and len(errs(rep)) == 1, {"rc": rc, "errors": [(f["code"], (f.get("file") or "")[-12:], f.get("line")) for f in errs(rep)]})
b = bundle(); b[1]["spec"]["selector"]["matchLabels"]["tier"] = "backend"
planted("P05_workload_selector_vs_template", b, "WORKLOAD_SELECTOR_TEMPLATE_MISMATCH", 1, "spec.selector", also=("SERVICE_SELECTOR_NO_MATCH", "PDB_SELECTOR_NO_MATCH"), exact_line=False)
# Missing ports
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["ports"][0]["name"] = "web"; b[1]["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]["httpGet"]["port"] = "web"; b[1]["spec"]["template"]["spec"]["containers"][0]["livenessProbe"]["httpGet"]["port"] = "web"
planted("P06_service_targetport_name_missing", b, "SERVICE_TARGETPORT_NAME_UNKNOWN", 2, "spec.ports[0].targetPort")
b = bundle(); c = b[1]["spec"]["template"]["spec"]["containers"][0]; del c["ports"]; c["readinessProbe"]["httpGet"]["port"] = 8080; c["livenessProbe"]["httpGet"]["port"] = 8080
planted("P07_container_has_no_ports_named_target", b, "SERVICE_TARGETPORT_NAME_UNKNOWN", 2, "spec.ports[0].targetPort", also=())
b = bundle(); b[2]["spec"]["ports"][0]["targetPort"] = 7070
planted("P08_numeric_targetport_undeclared_is_warning", b, "SERVICE_TARGETPORT_UNDECLARED", 2, "spec.ports[0].targetPort", want_rc=0, sev="warning")
b = bundle(); b[2]["spec"]["ports"].append({"port": 9090, "targetPort": "metrics"})
planted("P09_multiport_unnamed", b, "SERVICE_PORT_NAME_REQUIRED", 2, "spec.ports[1]", exact_line=False)
# Bad readiness
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]["httpGet"]["port"] = "htp"
planted("P10_readiness_port_name_typo", b, "PROBE_PORT_NAME_UNKNOWN", 1, C + ".readinessProbe.httpGet.port")
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]["tcpSocket"] = {"port": "http"}
planted("P11_readiness_two_handlers", b, "PROBE_HANDLER_INVALID", 1, C + ".readinessProbe", exact_line=False)
b = bundle(); del b[1]["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]
planted("P12_readiness_missing_behind_service", b, "READINESS_PROBE_MISSING", 1, C, exact_line=False)
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["livenessProbe"]["successThreshold"] = 2
planted("P13_liveness_success_threshold", b, "PROBE_SUCCESS_THRESHOLD", 1, C + ".livenessProbe.successThreshold", exact_line=False)
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]["successThreshold"] = 2
rc, rep, _, _, _, _ = run([("m.yaml", b)]); row("P14_readiness_success_threshold_allowed", rc == 0 and not errs(rep), {"rc": rc, "errors": [f["code"] for f in errs(rep)]})
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]["httpGet"]["port"] = 70000
planted("P15_readiness_port_out_of_range", b, "PROBE_PORT_INVALID", 1, C + ".readinessProbe.httpGet.port", exact_line=False)
# Misleading availability
for k, (kw, rep_) in enumerate((({"minAvailable": 3}, 3), ({"minAvailable": "100%"}, 3), ({"maxUnavailable": 0}, 3), ({"minAvailable": 1}, 1))):
    b = bundle(); b[3]["spec"] = {"selector": b[3]["spec"]["selector"], **kw}; b[1]["spec"]["replicas"] = rep_
    if rep_ == 1: b[4]["spec"]["minReplicas"] = 1
    planted("P16%s_pdb_blocks_eviction" % "abcd"[k], b, "PDB_BLOCKS_EVICTION", 3, "spec", exact_line=False)
b = bundle(); b[3]["spec"]["selector"]["matchLabels"]["tier"] = "fronted"
planted("P17_pdb_selects_nothing", b, "PDB_SELECTOR_NO_MATCH", 3, "spec.selector", exact_line=False)
b = bundle(); del b[3]
rc, rep, _, _, _, _ = run([("m.yaml", b)]); row("P18_no_pdb_is_warning", rc == 0 and "PDB_MISSING" in [f["code"] for f in warns(rep)] and not errs(rep), {"rc": rc, "warnings": [f["code"] for f in warns(rep)]})
b = bundle(); b[4]["spec"]["minReplicas"] = 7
planted("P19_hpa_min_gt_max", b, "HPA_MIN_GT_MAX", 4, "spec", exact_line=False)
b = bundle(); del b[1]["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"]["cpu"]; del b[1]["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]["cpu"]
planted("P20_hpa_cpu_without_request", b, "HPA_TARGET_NO_REQUEST", 4, "spec", also=("RESOURCES_MISSING",), exact_line=False)
# resources and quantity arithmetic
def res(req, lim):
    b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["resources"] = {"requests": req, "limits": lim}; return b
planted("P21a_request_exceeds_limit_mem", res({"cpu": "250m", "memory": "1Gi"}, {"cpu": "500m", "memory": "1000Mi"}), "REQUEST_EXCEEDS_LIMIT", 1, C + ".resources", exact_line=False)
planted("P21b_request_exceeds_limit_cpu", res({"cpu": "0.6", "memory": "256Mi"}, {"cpu": "500m", "memory": "512Mi"}), "REQUEST_EXCEEDS_LIMIT", 1, C + ".resources", exact_line=False)
rc, rep, _, _, _, _ = run([("m.yaml", res({"cpu": "500m", "memory": "1G"}, {"cpu": "0.5", "memory": "1Gi"}))])
row("P21c_equal_and_decimal_vs_binary_ok", rc == 0 and not errs(rep), {"rc": rc, "errors": [f["code"] for f in errs(rep)], "note": "500m == 0.5; 1G = 1e9 < 1Gi"})
planted("P21d_quantity_invalid", res({"cpu": "250m", "memory": "256MB"}, {"cpu": "500m", "memory": "512Mi"}), "RESOURCE_QUANTITY_INVALID", 1, C + ".resources.requests.memory", exact_line=False)
# images
for k, (img, bad) in enumerate((("registry.example.test:5000/shop/web", True), ("registry.example.test:5000/shop/web:2.0.1", False), ("registry.example.test/shop/web@sha256:" + "a" * 64, False), ("web:latest", True))):
    b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["image"] = img
    if bad: planted("P22%s_image_tag" % "abcd"[k], b, "IMAGE_TAG_MUTABLE", 1, C + ".image")
    else:
        rc, rep, _, _, _, _ = run([("m.yaml", b)]); row("P22%s_image_pinned_ok" % "abcd"[k], rc == 0 and not errs(rep), {"rc": rc, "image": img, "errors": [f["code"] for f in errs(rep)]})
# duplicate key / object, unusable input
text, _ = emit(bundle()); dup = text.replace("  replicas: 3\n", "  replicas: 3\n  replicas: 1\n", 1)
rc, rep, _, _, _, _ = run([("m.yaml", dup)]); row("P23_duplicate_key", rc == 1 and "DUPLICATE_KEY" in [f["code"] for f in errs(rep)], {"rc": rc, "errors": [f["code"] for f in errs(rep)]})
rc, rep, _, _, _, _ = run([("a.yaml", bundle()), ("b.yaml", [bundle()[1]])]); row("P24_duplicate_object_across_files", rc == 1 and "OBJECT_DUPLICATE" in [f["code"] for f in errs(rep)], {"rc": rc, "errors": [f["code"] for f in errs(rep)]})
bad = {"template": text.replace("1.4.2", "{{ .Values.tag }}"), "anchor": text.replace("  labels:\n", "  labels: &l\n", 1), "tab": text.replace("  replicas: 3", "\treplicas: 3", 1), "not_yaml": "just: [unclosed\n", "empty": ""}
res2 = {}
for k, t in bad.items():
    rc, rep, _, same, cp, _ = run([("m.yaml", t)]); res2[k] = {"rc": rc, "clean_claim": bool(rep and rep.get("findings") == [] and rc == 0), "unchanged": same}
row("P25_unusable_input_exit2_never_clean", all(v["rc"] == 2 and not v["clean_claim"] and v["unchanged"] for v in res2.values()), res2)
# static vs cluster execution: every output disclaims deployment; text mode too; no file written anywhere in the dir
b = bundle(); b[2]["spec"]["selector"]["tier"] = "x"; rc, rep, _, same, _, d = run([("m.yaml", b)])
cp2 = subprocess.run([sys.executable, str(TOOL), "check", str(d)], cwd=str(TOP), env=ENV, capture_output=True, text=True)
txt = cp2.stdout.lower(); files = sorted(p.name for p in d.iterdir())
row("P26_static_only_claims", rep is not None and rep.get("cluster_contacted") is False and rep.get("applied") is False and rep.get("deployed") is False and "not applied" in txt and ("no cluster" in txt or "cluster_contacted: false" in txt or "not contacted" in txt) and same and files == ["m.yaml"],
    {"json_claims": {k: (rep or {}).get(k) for k in ("cluster_contacted", "applied", "deployed")}, "evidence_scope": (rep or {}).get("evidence_scope"), "text_tail": cp2.stdout[-300:], "files": files})
# recovery: apply the tool's suggested labels by a reviewed edit (here: by hand from the suggestion), rerun clean
b = bundle(); b[2]["spec"]["selector"]["tier"] = "front-end"; rc1, rep1, _, _, _, _ = run([("m.yaml", b)])
sug = " ".join(f.get("suggestion", "") for f in errs(rep1)); b[2]["spec"]["selector"]["tier"] = "frontend"; rc2, rep2, _, _, _, _ = run([("m.yaml", b)])
row("P27_recovery_edit_then_rerun", rc1 == 1 and "tier=frontend" in sug and rc2 == 0 and not errs(rep2), {"rc_before": rc1, "suggestion": sug, "rc_after": rc2})
# P28 property: 30 random bundles (label keys/values, port names, namespaces), each clean, then one random planted defect
rng = random.Random(909); fails = []
DEF = ["svc_sel", "tp_name", "ready_port", "ready_missing", "pdb_block", "pdb_none", "req_gt_lim", "latest"]
for k in range(30):
    n = "ns%d" % rng.randint(1, 999); name = "app%d" % k; lab = {"k%d.example.test/x" % rng.randint(1, 9): "v%d" % rng.randint(1, 99), "role": rng.choice(["a", "b-c", "d.e"])}
    pn = rng.choice(["http", "web", "api-port", "p8080"]); b = bundle(n, name, lab); c = b[1]["spec"]["template"]["spec"]["containers"][0]
    c["ports"][0]["name"] = pn; c["readinessProbe"]["httpGet"]["port"] = pn; c["livenessProbe"]["httpGet"]["port"] = pn; b[2]["spec"]["ports"][0]["targetPort"] = pn
    rc, rep, _, _, _, _ = run([("m.yaml", b)])
    if rc != 0 or errs(rep): fails.append({"case": k, "clean_rc": rc, "errors": [f["code"] for f in errs(rep)]}); continue
    dfx = rng.choice(DEF); want = {"svc_sel": ("SERVICE_SELECTOR_NO_MATCH", 2), "tp_name": ("SERVICE_TARGETPORT_NAME_UNKNOWN", 2), "ready_port": ("PROBE_PORT_NAME_UNKNOWN", 1), "ready_missing": ("READINESS_PROBE_MISSING", 1),
                                   "pdb_block": ("PDB_BLOCKS_EVICTION", 3), "pdb_none": ("PDB_SELECTOR_NO_MATCH", 3), "req_gt_lim": ("REQUEST_EXCEEDS_LIMIT", 1), "latest": ("IMAGE_TAG_MUTABLE", 1)}[dfx]
    if dfx == "svc_sel": b[2]["spec"]["selector"]["role"] += "x"
    elif dfx == "tp_name": b[2]["spec"]["ports"][0]["targetPort"] = pn + "x"
    elif dfx == "ready_port": c["readinessProbe"]["httpGet"]["port"] = pn + "x"
    elif dfx == "ready_missing": del c["readinessProbe"]
    elif dfx == "pdb_block": b[3]["spec"] = {"selector": b[3]["spec"]["selector"], "minAvailable": 3}
    elif dfx == "pdb_none": b[3]["spec"]["selector"]["matchLabels"]["role"] += "x"
    elif dfx == "req_gt_lim": c["resources"]["requests"]["memory"] = "600Mi"
    else: c["image"] = c["image"].rsplit(":", 1)[0] + ":latest"
    rc, rep, _, _, _, _ = run([("m.yaml", b)]); codes = sorted({f["code"] for f in errs(rep)}); hit = [f for f in errs(rep) if f["code"] == want[0] and f.get("kind") == b[want[1]]["kind"]]
    if rc != 1 or codes != [want[0]] or not hit: fails.append({"case": k, "defect": dfx, "rc": rc, "codes": codes})
row("P28_random_bundles_property", not fails, {"cases": 30, "fails": fails[:3]})
# P29 scale: 60 namespaces x 4 objects, one planted defect in namespace 37 only
files = []
for i in range(60):
    b = bundle("n%02d" % i, "s%02d" % i)
    if i == 37: b[2]["spec"]["selector"]["tier"] = "frontendx"
    files.append(("f%02d.yaml" % i, b))
rc, rep, _, _, _, _ = run(files); e = errs(rep)
row("P29_scale_one_defect_in_60_namespaces", rc == 1 and len(e) == 1 and e[0]["code"] == "SERVICE_SELECTOR_NO_MATCH" and e[0].get("namespace") == "n37" and (e[0].get("file") or "").endswith("f37.yaml"), {"rc": rc, "errors": [(f["code"], f.get("namespace")) for f in e][:5], "objects": (rep or {}).get("objects")})
# OBS
b = bundle(); c = b[1]["spec"]["template"]["spec"]["containers"][0]; c["livenessProbe"] = copy.deepcopy(c["readinessProbe"])
rc, rep, _, _, _, _ = run([("m.yaml", b)]); row("O30_identical_probes", True, {"rc": rc, "warnings": [f["code"] for f in warns(rep)]}, obs=True)
b = bundle(); b[1]["spec"]["replicas"] = 1; b[4]["spec"]["minReplicas"] = 1; del b[3]
rc, rep, _, _, _, _ = run([("m.yaml", b)]); row("O31_single_replica_no_pdb", True, {"rc": rc, "warnings": [f["code"] for f in warns(rep)], "errors": [f["code"] for f in errs(rep)]}, obs=True)
b = bundle(); b[1]["spec"]["replicas"] = 2; b[4]["spec"]["minReplicas"] = 2
b[3]["spec"] = {"selector": b[3]["spec"]["selector"], "minAvailable": "50%"}
rc, rep, _, _, _, _ = run([("m.yaml", b)]); row("O32_pdb_50pct_of_2", True, {"rc": rc, "errors": [f["code"] for f in errs(rep)]}, obs=True)
b = bundle(); b[2]["spec"]["selector"] = {}
rc, rep, _, _, _, _ = run([("m.yaml", b)]); row("O33_service_without_selector", True, {"rc": rc, "findings": [(f["severity"], f["code"]) for f in (rep or {}).get("findings", [])]}, obs=True)
# ---- v2 rows ----
def codes(rep, sev="error"): return sorted({f["code"] for f in (rep or {}).get("findings", []) if f.get("severity") == sev})
def simple(rid, objs, want_rc, want_err, want_warn_has=(), fname="m.yaml"):
    rc, rep, _, same, cp, _ = run([(fname, objs)]); e = codes(rep); w = codes(rep, "warning")
    ok = rc == want_rc and e == sorted(want_err) and all(x in w for x in want_warn_has) and same and "Traceback" not in cp.stderr
    row(rid, ok, {"rc": rc, "want_rc": want_rc, "errors": e, "want_errors": sorted(want_err), "warnings": w, "want_warnings": list(want_warn_has)}); return rep
b = bundle(); b[2]["spec"]["ports"] = [{"name": "http", "port": 8080}]; simple("R01a_targetport_defaults_to_port_declared", b, 0, [])
b = bundle(); b[2]["spec"]["ports"] = [{"name": "http", "port": 81}]; rep = simple("R01b_targetport_defaults_to_port_undeclared", b, 0, [], ("SERVICE_TARGETPORT_UNDECLARED",))
b = bundle(); del b[1]["spec"]["selector"]; simple("R02_workload_selector_missing", b, 1, ["WORKLOAD_SELECTOR_MISSING"])
b = bundle(); b[3]["spec"]["selector"] = {"matchExpressions": [{"key": "tier", "operator": "In", "values": ["backend", "batch"]}]}; simple("R03a_pdb_matchexpressions_in_nomatch", b, 1, ["PDB_SELECTOR_NO_MATCH"])
b = bundle(); b[3]["spec"]["selector"] = {"matchExpressions": [{"key": "tier", "operator": "In", "values": ["frontend"]}, {"key": "app.kubernetes.io/name", "operator": "Exists"}]}; simple("R03b_pdb_matchexpressions_match", b, 0, [])
b = bundle(); b[3]["spec"]["selector"] = {"matchExpressions": [{"key": "tier", "operator": "NotIn", "values": ["frontend"]}]}; simple("R03c_pdb_notin_excludes", b, 1, ["PDB_SELECTOR_NO_MATCH"])
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["readinessProbe"] = {"periodSeconds": 5}; simple("R04_probe_zero_handlers", b, 1, ["PROBE_HANDLER_INVALID"])
ss = deploy("db", "shop", {"app": "db"}); ss["kind"] = "StatefulSet"; ss["spec"]["serviceName"] = "db"; del ss["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]
simple("R05_statefulset_behind_service_no_readiness", bundle() + [ss, svc("db", "shop", {"app": "db"}), pdb("db", "shop", {"app": "db"})], 1, ["READINESS_PROBE_MISSING"])
b = bundle(); del b[1]["spec"]["template"]["spec"]["containers"][0]["resources"]; del b[4]; simple("R06_no_resources", b, 1, ["RESOURCES_MISSING"])
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["resources"] = {"limits": {"cpu": "500m", "memory": "512Mi"}}; simple("R07_limits_stand_in_for_requests", b, 0, [])
rc, rep, _, same, cp, _ = run([("m.yaml", emit(b)[0])]); ws = [f["code"] for f in (rep or {}).get("findings", []) if f.get("code", "").startswith("RESOURCES")]
row("R07b_no_limitrange_no_defaulted_claim", rc == 0 and not ws, {"rc": rc, "resource_codes": ws})
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["resources"] = {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "500m"}}; simple("R08_memory_limit_missing", b, 1, ["RESOURCES_MISSING"])
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["resources"] = {"requests": {"cpu": "250m", "memory": "1025Mi"}, "limits": {"cpu": "500m", "memory": "1Gi"}}; simple("R09a_binary_mi_vs_gi", b, 1, ["REQUEST_EXCEEDS_LIMIT"])
b = bundle(); b[1]["spec"]["template"]["spec"]["containers"][0]["resources"] = {"requests": {"cpu": "250m", "memory": "1001M"}, "limits": {"cpu": "500m", "memory": "954Mi"}}; simple("R09b_decimal_m_vs_mi", b, 1, ["REQUEST_EXCEEDS_LIMIT"])
text, _ = emit(bundle())
bad = {"anchor_alias": text.replace("  name: web\n  namespace: shop\n  labels:", "  name: &n web\n  namespace: shop\n  labels:", 1).replace("kind: Service\nmetadata:\n  name: web", "kind: Service\nmetadata:\n  name: *n", 1),
       "tab_nested": text.replace("    app.kubernetes.io/name: web\n", "\tapp.kubernetes.io/name: web\n", 1),
       "deep_nesting": "apiVersion: v1\nkind: ConfigMap\nmetadata: {name: x}\ndata: " + "[" * 3000 + "]" * 3000 + "\n"}
bad["anchor_seq_item"] = text.replace("      - name: web\n", "      - &c name: web\n", 1)
bad["anchor_key"] = text.replace("  replicas: 3\n", "  &r replicas: 3\n", 1)
def first_line(t, m):
    for i, l in enumerate(t.split("\n"), 1):
        if m(l): return i
want_line = {"anchor_alias": first_line(bad["anchor_alias"], lambda l: "&n" in l), "tab_nested": first_line(bad["tab_nested"], lambda l: l.startswith("\t")),
             "anchor_seq_item": first_line(bad["anchor_seq_item"], lambda l: "&c" in l), "anchor_key": first_line(bad["anchor_key"], lambda l: "&r" in l)}
res3 = {}; o34 = {}
for k, t in bad.items():
    rc, rep, _, same, cp, _ = run([("m.yaml", t)]); u = (rep or {}).get("unusable") or {}
    res3[k] = {"rc": rc, "traceback": "Traceback" in cp.stderr, "has_line": any(ch.isdigit() for ch in (cp.stdout + cp.stderr)), "line": u.get("line"), "want_line": want_line.get(k)}
    o34[k] = {"code": u.get("code"), "reason": u.get("reason"), "line": u.get("line")}
row("R10_refused_yaml_exit2_with_line", all(v["rc"] == 2 and not v["traceback"] for v in res3.values()), res3)
row("R10b_refusal_names_planted_line", all(v["line"] == v["want_line"] for k, v in res3.items() if k in want_line), {k: (v["line"], v["want_line"]) for k, v in res3.items() if k in want_line})
row("O34_refusal_codes_and_reasons", True, o34, obs=True)
lr = lambda d: {"apiVersion": "v1", "kind": "LimitRange", "metadata": {"name": "defaults", "namespace": "shop"}, "spec": {"limits": [{"type": "Container", "default": d, "defaultRequest": d}]}}
b = bundle(); del b[1]["spec"]["template"]["spec"]["containers"][0]["resources"]; b.append(lr({"cpu": "500m", "memory": "512Mi"}))
simple("R11a_limitrange_defaults_warning", b, 0, [], ("RESOURCES_DEFAULTED",))
b = bundle(); del b[1]["spec"]["template"]["spec"]["containers"][0]["resources"]; del b[4]; b.append(lr({"cpu": "500m"}))
simple("R11b_limitrange_partial_still_error", b, 1, ["RESOURCES_MISSING"])
b = bundle(); b[2]["spec"]["selector"] = {"app.kubernetes.io/name": "web"}; b[2]["spec"]["ports"][0]["targetPort"] = "web-http"
simple("R12_targetport_name_missing_subset_selector", b, 1, ["SERVICE_TARGETPORT_NAME_UNKNOWN"])
shutil.rmtree(TOP, ignore_errors=True)
json.dump(ROWS, open(OUT, "w"), indent=1, sort_keys=True, default=str)
for x in ROWS: print(x["id"], x["result"], json.dumps(x["detail"], sort_keys=True, default=str)[:240])
c = [x for x in ROWS if x["kind"] == "core"]; print("M09 ORACLE %d/%d core PASS" % (sum(x["result"] == "PASS" for x in c), len(c)))
