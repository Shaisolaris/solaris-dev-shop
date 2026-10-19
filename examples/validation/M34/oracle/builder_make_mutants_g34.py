#!/usr/bin/env python3
"""G34 mutants of page_diagnostics.py. Usage: make_mutants_g34.py --list | TREE NAME OUTTREE"""
import sys
from pathlib import Path
T = "employees/marketing/seo-aso-specialist/page_diagnostics.py"
M = {
 "symlink_escape_followed": ('if os.path.islink(full) and not within(os.path.realpath(full), root):', 'if False:'),
 "dir_symlink_filter_off_EQUIV": ('dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))', 'dirnames[:] = sorted(dirnames)'),
 "size_cap_off": ('if size > max_bytes:', 'if False:'),
 "skipped_not_incomplete": ('"pages_scanned": len(parsed), "complete": not skipped,', '"pages_scanned": len(parsed), "complete": True,'),
 "exit3_after_1": ('''    if not rep["complete"]:
        return 3
    if args.fail_on != "none" and any(SEV[f["severity"]] >= SEV[args.fail_on] for f in rep["findings"]):
        return 1''', '''    if args.fail_on != "none" and any(SEV[f["severity"]] >= SEV[args.fail_on] for f in rep["findings"]):
        return 1
    if not rep["complete"]:
        return 3'''),
 "threshold_gt": ('any(SEV[f["severity"]] >= SEV[args.fail_on]', 'any(SEV[f["severity"]] > SEV[args.fail_on]'),
 "out_inside_allowed": ('                raise UsageError("--out must not be inside the snapshot")', '                pass'),
 "write_not_atomic": ('''    d = os.path.dirname(os.path.abspath(path))
    fd, tmp''', '''    open(path, "w").close()
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp'''),
 "temp_not_cleaned": ('''        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise''', '''        raise'''),
 "replace_error_uncaught": ('            except OSError as e:\n                raise UsageError("could not write --out', '            except ValueError as e:\n                raise UsageError("could not write --out'),
 "baseline_schema_unchecked": ('if not isinstance(rep, dict) or rep.get("schema") != SCHEMA or', 'if not isinstance(rep, dict) or'),
 "base_url_scheme_unchecked": ('if sp.scheme not in ("http", "https") or not sp.hostname:', 'if not sp.hostname:'),
 "redirects_ignored": ('        red, seen, hops = self.cfg["redirects"], [path], 0', '        red, seen, hops = {}, [path], 0'),
 "loop_by_hop_limit_EQUIV": ('            if path in seen:\n                return path, hops, True', '            if hops > 50:\n                return path, hops, True'),
 "chain_as_single": ('        if hops > 1:\n            add("redirect_chain"', '        if hops > 99:\n            add("redirect_chain"'),
 "case_hint_off": ('            hint = site.lower.get(final.lower()) or', '            hint = None and'),
 "fragment_check_off": ('if frag and frag != "top" and target in parsed', 'if False and target in parsed'),
 "fragment_top_flagged": ('if frag and frag != "top" and target in parsed', 'if frag and target in parsed'),
 "a_name_not_anchor": ('        if tag == "a" and "name" in a and "id" not in a:\n            self.ids.append(a["name"])', ''),
 "dir_index_off": ('        if path + "/index.html" in self.existing:\n            return path + "/index.html"', ''),
 "unquote_off": ('        path = unquote(path)\n', ''),
 "host_case_sensitive": ('if (sp.hostname or "").lower() != self.cfg["host"]:', 'if sp.netloc != self.cfg["host"]:'),
 "empty_alt_flagged": ('            if "alt" not in a:\n                self.imgs_no_alt += 1', '            if not a.get("alt"):\n                self.imgs_no_alt += 1'),
 "img_alt_not_name": ('            for rec in self._a + self._button:\n                rec["text"].append(alt)', ''),
 "labelledby_ignored": ('            self.buttons.append("x" if rec["labelled"] else', '            self.buttons.append("" if rec["labelled"] else'),
 "wrapped_label_ignored": ('self.controls.append((a.get("id"), own, self._label_depth > 0))', 'self.controls.append((a.get("id"), own, False))'),
 "hidden_needs_label": ('NO_LABEL_TYPES = {"hidden", "submit", "button", "reset", "image"}', 'NO_LABEL_TYPES = {"submit", "button", "reset", "image"}'),
 "vague_off": ('            elif link["name"].lower().strip(" .!:>\\u00bb\\u2192") in VAGUE:', '            elif False:'),
 "cta_unnamed_counts": ('            if path is None or not named:', '            if path is None:'),
 "cta_redirect_not_followed": ('            final, _, lp = site.follow(path)\n            if not lp and site.to_key(final) == goal:', '            final, lp = path, False\n            if not lp and site.to_key(final) == goal:'),
 "orphan_counts_self": ('                if target != key:\n                    inbound.setdefault(target, set()).add(key)', '                inbound.setdefault(target, set()).add(key)'),
 "noindex_needs_canonical": ('        if not p.noindex:\n            if not p.canonicals:', '        if True:\n            if not p.canonicals:'),
 "foreign_canonical_ok": ('                elif (sp.hostname or "").lower() != cfg["host"]:\n                    add("canonical_foreign"', '                elif False:\n                    add("canonical_foreign"'),
 "graph_types_missed": ('        for v in obj.values():\n            ld_types(v, out)', ''),
 "faq_not_restricted": ('RESTRICTED_LD = {"FAQPage"}', 'RESTRICTED_LD = set()'),
 "encoding_flag_off": ('                flags[key] = "encoding"', '                pass'),
 "sitemap_noindex_off": ('            if target in parsed and parsed[target].noindex:', '            if False:'),
 "title_range_wide": ('TITLE_RANGE = (50, 60)', 'TITLE_RANGE = (1, 90)'),
 "dup_titles_include_noindex": ('            if not p.noindex:\n                titles.setdefault', '            if True:\n                titles.setdefault'),
 "findings_unsorted": ('    findings = sorted(uniq.values(), key=lambda f: (-SEV[f["severity"]], f["page"], f["check"], f["detail"]))', '    findings = list(uniq.values())'),
}
if sys.argv[1] == "--list":
    print(" ".join(M)); sys.exit(0)
tree, name, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
old, new = M[name]
src = (tree / T).read_text(); n = src.count(old)
if n != 1:
    sys.stderr.write("%s anchor count %d\n" % (name, n)); sys.exit(1)
(out / T).write_text(src.replace(old, new))
# dir_symlink_filter_off_EQUIV: os.walk(followlinks=False) never descends into a symlinked folder; the filter is belt-and-braces.
# loop_by_hop_limit_EQUIV: a loop is still reported, after 51 hops instead of on the first repeat; the output is the same.
