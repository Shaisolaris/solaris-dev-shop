# echo stub: echoes the intake back as a "complete" result, writes nothing
import json, sys
a = sys.argv[1:]
res = {"status": "complete", "exit_code": 0, "project_root": a[1] if len(a) > 1 else None,
       "intake": {"name": None, "deploy_model": None}, "inherited": [], "argv": a}
for i, t in enumerate(a):
    if t == "--name" and i + 1 < len(a): res["intake"]["name"] = a[i + 1]
    if t == "--deploy-model" and i + 1 < len(a): res["intake"]["deploy_model"] = a[i + 1]
print(json.dumps(res) if "--json" in a else "Folder: %s (complete)\nDeploy model: %s" % (res["project_root"], res["intake"]["deploy_model"] or "UNRESOLVED"))
