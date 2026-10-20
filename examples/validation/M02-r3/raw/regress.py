import sys, os, tempfile, shutil, importlib.util, io, contextlib
spec = importlib.util.spec_from_file_location("act", os.path.join(sys.argv[1], "employees/product-project/project-onboarding/activate.py")); a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
for v in ["UNRESOLVED", "UNRESOLVED ask the owner", "Unresolved until the owner decides", "unresolved pending call", "UNRESOLVED: main=live", "Unresolved, ask owner", "U\u0301NRESOLVED"]:
    t = tempfile.mkdtemp()
    with contextlib.redirect_stderr(io.StringIO()):
        r = a.activate(os.path.join(t, "p"), {"name": "P", "project_type": "website", "deploy_model": v})
    print("%-40r %s %r" % (v, r["status"], (r.get("intake") or {}).get("deploy_model")))
    shutil.rmtree(t)
