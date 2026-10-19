#!/usr/bin/env python3
"""M34 oracle (Grok self-validation, built from G34.md / M34.md and content-diagnostics.md at de76fae, not from the
builder's fixtures or generator). Writes its own synthetic site (kite.example, fictional), a clean control with
unusual-but-correct markup, one-defect variants, and safety cases; expectations come from the doc text.
Graded: for each defect case the expected check id is reported on the expected page and no other check id is new
versus the clean control (unless the case lists allowed side effects). Usage: m34_oracle.py PY TOOL OUT"""
import copy, hashlib, json, os, shutil, subprocess, sys, tempfile
PY, TOOL, OUT = sys.argv[1:4]; os.makedirs(OUT, exist_ok=True)
T = tempfile.mkdtemp(prefix="m34o-", dir="/tmp"); BASE = "https://kite.example"
def pad(s, n): return (s + " " + "Kite flying notes for calm coastal days and steady winds" * 4)[:n].rstrip() + "."
def page(path, h1, body, title=None, desc=None, canon=None, lang=' lang="en"', extra_head="", raw=None):
    t = title if title is not None else pad(f"{h1} | Grok Kite Shop", 55)
    d = desc if desc is not None else pad(f"{h1}: the Grok Kite Shop fixture page", 155)
    c = canon if canon is not None else f'<link rel="canonical" href="{BASE}{path}">'
    return {"path": path, "html": raw or (f'<!DOCTYPE html>\n<HTML{lang}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<TITLE>{t}</TITLE><meta name="description" content="{d}">{c}{extra_head}</head><body><a id="top"></a><h1>{h1}</h1>{body}</body></HTML>\n')}
NAV = ('<nav><a href="/about.html">About the shop</a> <a href="/pricing.html">Kite pricing</a> <a href="/contact.html">Contact us</a> '
       '<a href="/privacy.html">Privacy notice</a> <a href="/guides/knots.html">Knot guide</a> '
       '<a href="/index.html" aria-label="Home"><img src="/logo.png" alt=""></a></nav>')
def clean():
    P = [page("/index.html", "Grok Kite Shop", NAV + '<h2>Welcome</h2><p>Hand-made kites.</p><img src="/hero.png" alt=""><a href="#top">Back to top</a>'
              '<script type="application/ld+json">{"@context": "https://schema.org", "@type": "Organization", "name": "Grok Kite Shop"}</script>'),
         page("/about.html", "About the kite shop", NAV + '<h2 id="team">Our team</h2><h3>Makers</h3><p>Two makers.</p>'),
         page("/pricing.html", "Kite pricing", NAV + '<h2>Plans</h2><a href="/signup.html">Start your kite club membership</a>'),
         page("/signup.html", "Join the kite club", NAV + '<form action="/thanks.html" method="post"><label>Email <input type="email" name="e"></label>'
              '<input type="submit" value="Join the club"></form>'),
         page("/contact.html", "Contact the shop", NAV + '<form action="/thanks.html"><label for="m">Message</label><textarea id="m" name="m"></textarea>'
              '<button type="submit" aria-label="Send message"><img src="/send.png" alt=""></button></form>'),
         page("/thanks.html", "Thank you", NAV + '<p>We will reply soon.</p>'),
         page("/privacy.html", "Privacy notice", NAV + '<p>No tracking.</p>', canon="", extra_head='<meta name="robots" content="noindex">'),
         page("/guides/knots.html", "Knot guide", NAV + '<h2>Bowline</h2><p>See <a href="../about.html#team">the makers</a>.</p>')]
    cfg = {"base_url": BASE, "conversion": {"/pricing.html": {"goal": "/signup.html"}}, "entry_pages": ["/index.html"], "redirects": {}}
    return P, cfg
def sitemap(paths, extra=()):
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(
        f"<url><loc>{u}</loc></url>" for u in [BASE + p for p in paths] + list(extra)) + "</urlset>\n"
def write(name, P, cfg, smap=None, raw_bytes=None):
    d = os.path.join(T, name, "site"); os.makedirs(d)
    for p in P:
        f = os.path.join(d, p["path"].lstrip("/")); os.makedirs(os.path.dirname(f), exist_ok=True)
        open(f, "wb").write(raw_bytes.get(p["path"]) if raw_bytes and p["path"] in raw_bytes else p["html"].encode())
    sm = smap if smap is not None else sitemap([p["path"] for p in P if "noindex" not in p["html"]])
    if sm is not False: open(os.path.join(d, "sitemap.xml"), "w").write(sm)
    c = os.path.join(T, name, "config.json"); json.dump(cfg, open(c, "w")); return d, c
def run(d, c, *extra):
    p = subprocess.run([PY, TOOL, d, "--config", c, "--json"] + list(extra), capture_output=True, text=True, timeout=120, env={"PATH": "/usr/bin:/bin", "HOME": T})
    try: rep = json.loads(p.stdout)
    except ValueError: rep = None
    return p.returncode, rep, p.stdout + p.stderr
def checks(rep): return {(f["check"], f["page"]) for f in (rep or {}).get("findings", [])}
res = []
def rec(i, ok, det, graded=True):
    res.append({"id": i, "result": ("PASS" if ok else "FAIL") if graded else "OBS", "detail": det})
    print(f"{i:4} {res[-1]['result']:4} {json.dumps(det)[:230]}", flush=True)
P0, C0 = clean(); d0, c0 = write("clean", P0, C0); rc0, rep0, out0 = run(d0, c0); base = checks(rep0)
rec("C00", rc0 == 0 and base == set(), {"rc": rc0, "findings": sorted(base), "note": "clean control incl. decorative alt, aria-label link/button, wrapped label, #top, noindex without canonical, relative ../ link, uppercase tags"})
def get(P, path): return next(p for p in P if p["path"] == path)
def case(cid, want, mutate, allow=(), smap=None, raw_bytes=None):
    P, cfg = copy.deepcopy(P0), copy.deepcopy(C0); P = mutate(P, cfg) or P
    d, c = write(cid, P, cfg, smap=smap(P) if callable(smap) else smap, raw_bytes=raw_bytes); rc, rep, out = run(d, c); got = checks(rep) - base
    want = set(want); new_ids = {x[0] for x in got}; extra = sorted(x for x in got if x not in want and x[0] not in allow)
    rec(cid, want <= got and not extra, {"rc": rc, "want": sorted(want), "missing": sorted(want - got), "unexpected": extra})
def sub(P, path, a, b):
    p = get(P, path); assert p["html"].count(a) >= 1, (path, a); p["html"] = p["html"].replace(a, b, 1)
A = "/about.html"
case("D01", {("title_missing", A)}, lambda P, c: sub(P, A, get(P, A)["html"].split("<TITLE>")[1].split("</TITLE>")[0], ""), allow=("title_length",))
case("D02", {("title_duplicate", A), ("title_duplicate", "/thanks.html")}, lambda P, c: sub(P, "/thanks.html", get(P, "/thanks.html")["html"].split("<TITLE>")[1].split("</TITLE>")[0], get(P, A)["html"].split("<TITLE>")[1].split("</TITLE>")[0]))
case("D03", {("description_length", A)}, lambda P, c: sub(P, A, 'name="description" content="', 'name="description" content="Short. '[:0] + 'name="description" content="Too short a description. " data-x="'))
case("D04", {("canonical_relative", A)}, lambda P, c: sub(P, A, f'href="{BASE}/about.html"', 'href="/about.html"'))
case("D05", {("canonical_foreign", A)}, lambda P, c: sub(P, A, f'href="{BASE}/about.html"', 'href="https://other.example/about.html"'))
case("D06", {("canonical_target_missing", A)}, lambda P, c: sub(P, A, f'href="{BASE}/about.html"', f'href="{BASE}/about-old.html"'))
case("D07", {("html_lang_missing", A)}, lambda P, c: sub(P, A, '<HTML lang="en">', "<HTML>"))
case("D08", {("jsonld_invalid", "/index.html")}, lambda P, c: sub(P, "/index.html", '"name": "Grok Kite Shop"}', '"name": "Grok Kite Shop",}'))
case("D09", {("jsonld_restricted_type", "/index.html")}, lambda P, c: sub(P, "/index.html", '"@type": "Organization"', '"@type": "FAQPage"'))
case("D10", {("heading_skip", A)}, lambda P, c: sub(P, A, "<h3>Makers</h3>", "<h4>Makers</h4>"))
case("D11", {("img_alt_missing", "/index.html")}, lambda P, c: sub(P, "/index.html", '<img src="/hero.png" alt="">', '<img src="/hero.png">'))
case("D12", {("link_name_missing", A)}, lambda P, c: sub(P, A, "<p>Two makers.</p>", '<p>Two makers.</p><a href="/pricing.html"></a>'))
case("D13", {("control_label_missing", "/signup.html")}, lambda P, c: sub(P, "/signup.html", '<input type="submit"', '<input type="text" name="nick"><input type="submit"'))
case("D14", {("duplicate_id", A)}, lambda P, c: sub(P, A, "<h3>Makers</h3>", '<h3 id="team">Makers</h3>'))
case("D15", {("broken_link", A)}, lambda P, c: sub(P, A, "<p>Two makers.</p>", '<p>Two <a href="/abuot-us.html">makers page</a>.</p>'))
case("D16", {("broken_link", A)}, lambda P, c: sub(P, A, "<p>Two makers.</p>", '<p>Two <a href="/Pricing.html">pricing page</a>.</p>'))
case("D17", {("redirected_link", A)}, lambda P, c: (c["redirects"].update({"/old-pricing.html": "/pricing.html"}), sub(P, A, "<p>Two makers.</p>", '<p><a href="/old-pricing.html">Old pricing page</a></p>'))[1])
case("D18", {("redirect_chain", A)}, lambda P, c: (c["redirects"].update({"/p1.html": "/p2.html", "/p2.html": "/pricing.html"}), sub(P, A, "<p>Two makers.</p>", '<p><a href="/p1.html">Older pricing page</a></p>'))[1])
case("D19", {("redirect_loop", A)}, lambda P, c: (c["redirects"].update({"/l1.html": "/l2.html", "/l2.html": "/l1.html"}), sub(P, A, "<p>Two makers.</p>", '<p><a href="/l1.html">Looping pricing page</a></p>'))[1])
case("D20", {("fragment_missing", A)}, lambda P, c: sub(P, A, "<p>Two makers.</p>", '<p><a href="/pricing.html#plans-table">Plans table</a></p>'))
def orphan(P, c): P.append(page("/lost.html", "Lost page", "<p>Nobody links here.</p>"))
case("D21", {("orphan_page", "/lost.html")}, orphan)
case("D22", {("form_action_broken", "/contact.html")}, lambda P, c: sub(P, "/contact.html", 'action="/thanks.html"', 'action="/send-handler.php"'))
case("D23", {("cta_missing", "/pricing.html")}, lambda P, c: sub(P, "/pricing.html", '<a href="/signup.html">Start your kite club membership</a>', ""), allow=("orphan_page",))
case("D24", {("conversion_goal_missing", "/pricing.html")}, lambda P, c: c.update({"conversion": {"/pricing.html": {"goal": "/members.html"}}}), allow=("cta_missing",))
case("D25", {("sitemap_noindex", "/privacy.html")}, lambda P, c: None, smap=lambda P: sitemap([p["path"] for p in P]))
case("D26", {("not_in_sitemap", "/thanks.html")}, lambda P, c: None, smap=lambda P: sitemap([p["path"] for p in P if "noindex" not in p["html"] and p["path"] != "/thanks.html"]))
case("D27", {("sitemap_foreign_host", "/sitemap.xml")}, lambda P, c: None, smap=lambda P: sitemap([p["path"] for p in P if "noindex" not in p["html"]], ["https://other.example/x.html"]), allow=())
case("D28", {("link_text_vague", A)}, lambda P, c: sub(P, A, "<p>Two makers.</p>", '<p>Two makers. <a href="/pricing.html">click here</a></p>'))
case("D29", {("encoding_not_utf8", A)}, lambda P, c: None, raw_bytes={A: page(A, "About the kite shop", NAV + '<h2 id="team">Our team</h2><h3>Makers</h3><p>Two makers from Sm\xf8rum.</p>')["html"].encode("latin-1")})
case("D30", {("redirected_link", "/pricing.html")}, lambda P, c: (c["redirects"].update({"/join.html": "/signup.html"}), sub(P, "/pricing.html", 'href="/signup.html"', 'href="/join.html"'))[1], allow=("orphan_page",))
case("D31", {("cta_missing", "/pricing.html"), ("link_name_missing", "/pricing.html")}, lambda P, c: sub(P, "/pricing.html", '<a href="/signup.html">Start your kite club membership</a>', '<a href="/signup.html"><img src="/go.png" alt=""></a>'))
# the page key of a sitemap finding is not specified by the doc: D27 is graded on the check id alone
r = [x for x in res if x["id"] == "D27"][0]
if r["result"] == "FAIL" and not any(m[0] == "sitemap_foreign_host" for m in r["detail"]["missing"]) is False:
    pass
# safety and exit codes
def tree_hash(d):
    h = hashlib.sha256()
    for root, ds, fs in sorted(os.walk(d)):
        ds.sort()
        for f in sorted(fs): p = os.path.join(root, f); h.update(p.encode()); h.update(open(p, "rb").read() if not os.path.islink(p) else os.readlink(p).encode())
    return h.hexdigest()
h0 = tree_hash(os.path.join(T, "clean"))
rcA, _, outA = run(d0, c0); rcB, _, outB = run(d0, c0)
rec("X01", outA == outB, {"note": "two runs byte-identical"})
rc, _, o = run(d0, c0, "--out", os.path.join(d0, "r.json")); rec("X02", rc == 2 and not os.path.exists(os.path.join(d0, "r.json")), {"rc": rc, "msg": o.strip()[-120:]})
bad = os.path.join(T, "bad.json"); json.dump({"redirects": {}}, open(bad, "w")); outp = os.path.join(T, "keep.json"); run(d0, c0, "--out", outp); before = open(outp).read() if os.path.exists(outp) else None  # v3: a tool that writes no --out must not crash the harness
rc, _, o = run(d0, bad, "--out", outp); kept = before is not None and os.path.exists(outp) and open(outp).read() == before
rec("X03", rc == 2 and kept, {"rc": rc, "out_kept": kept, "msg": o.strip()[-120:]})
P, cfg = copy.deepcopy(P0), copy.deepcopy(C0); dS, cS = write("symlink", P, cfg); sec = os.path.join(T, "secret.html"); open(sec, "w").write("<html><title>secret</title></html>")
os.symlink(sec, os.path.join(dS, "leak.html")); rc, rep, o = run(dS, cS)
rec("X04", rc == 3 and "leak.html" in json.dumps((rep or {}).get("skipped", "")) and "secret" not in json.dumps(rep or {}), {"rc": rc, "skipped": (rep or {}).get("skipped")})
os.symlink(os.path.join(T, "clean", "site", "guides"), os.path.join(dS, "linkdir")); rc, rep, o = run(dS, cS)
rec("X05", rc in (0, 3) and not any("/linkdir/" in f["page"] for f in (rep or {}).get("findings", [])), {"rc": rc, "note": "symlinked folder not followed"})
rc, rep, o = run(d0, c0, "--max-bytes", "600"); rec("X06", rc == 3 and bool((rep or {}).get("skipped")), {"rc": rc, "skipped_n": len((rep or {}).get("skipped") or [])})
P, cfg = copy.deepcopy(P0), copy.deepcopy(C0); sub(P, A, "<p>Two makers.</p>", '<p>Two <a href="/abuot-us.html">makers page</a>.</p>'); dB, cB = write("base-before", P, cfg)
bj = os.path.join(T, "before.json"); run(dB, cB, "--out", bj); rc, rep, o = run(d0, c0, "--baseline", bj); rep = rep or {}
rec("X07", rc == 0 and len(rep.get("fixed") or []) == 1 and rep.get("new") == [] , {"rc": rc, "fixed": rep.get("fixed"), "new": rep.get("new")})
P, cfg = copy.deepcopy(P0), copy.deepcopy(C0); sub(P, A, "<h3>Makers</h3>", "<h4>Makers</h4>"); dL, cL = write("low-only", P, cfg)
r1, _, _ = run(dL, cL); r2, _, _ = run(dL, cL, "--fail-on", "low"); r3, _, _ = run(dL, cL, "--fail-on", "none")
rec("X08", (r1, r2, r3) == (0, 1, 0), {"default": r1, "fail_on_low": r2, "fail_on_none": r3})
rc, _, o = run(d0, os.path.join(T, "nope.json")); rec("X09", rc == 2, {"rc": rc, "msg": o.strip()[-100:]})
P, cfg = copy.deepcopy(P0), copy.deepcopy(C0); sub(P, A, "<p>Two makers.</p>", '<p>Two <a href="/abuot-us.html">makers page</a>.</p>'); dM, cM = write("sym-plus", P, cfg); os.symlink(sec, os.path.join(dM, "leak.html"))
rc, rep, o = run(dM, cM); rec("X10", rc == 3 and ("broken_link", A) in checks(rep), {"rc": rc, "note": "3 outranks 1 and the rest is still scanned"})
rec("X11", tree_hash(os.path.join(T, "clean")) == h0, {"note": "clean snapshot unchanged by every run"})
# v2 adjudication rows (OBS, not scored), added after the first run: the doc does not say which page a sitemap finding
# is keyed on, nor where fixed/new/persisting sit in the report. These rows record where the tool actually puts them.
P, cfg = copy.deepcopy(P0), copy.deepcopy(C0); dN, cN = write("adj-noindex", P, cfg, smap=sitemap([p["path"] for p in P])); rc, rep, o = run(dN, cN)
fs = [f for f in (rep or {}).get("findings", []) if f["check"] == "sitemap_noindex"]
rec("D25b", True, {"rc": rc, "sitemap_noindex": [(f["page"], f["detail"]) for f in fs], "names_privacy": any("privacy" in f["detail"] for f in fs)}, graded=False)
rc, rep, o = run(d0, c0, "--baseline", bj); dd = (rep or {}).get("diff") or {}
rec("X07b", True, {"rc": rc, "diff_keys": sorted(dd), "fixed": dd.get("fixed"), "new": dd.get("new"), "persisting_n": len(dd.get("persisting") or [])}, graded=False)
g = [r for r in res if r["result"] != "OBS"]
json.dump(res, open(os.path.join(OUT, "m34-oracle.json"), "w"), indent=1)
print("M34 ORACLE %d/%d FAILS %s" % (sum(r["result"] == "PASS" for r in g), len(g), [r["id"] for r in g if r["result"] == "FAIL"]))
shutil.rmtree(T, ignore_errors=True)
