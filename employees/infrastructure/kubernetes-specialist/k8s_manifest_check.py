#!/usr/bin/env python3
"""Offline Kubernetes manifest check (G09): service/selector, probe, resource and rollout mistakes.

Reads YAML or JSON manifest files and reports concrete mistakes with file, line and field path. It never
contacts a cluster, never runs kubectl, helm or a container runtime and never writes to its inputs. A clean
result means only that these files passed these checks; it is not evidence that anything was applied,
deployed or is healthy.

Usage:
  k8s_manifest_check.py check PATH [PATH ...] [--json] [--namespace NS]
Exit codes: 0 no errors (warnings allowed), 1 errors found, 2 input unusable (unreadable, unsupported YAML,
unrendered template, no objects).
Python 3.9+, standard library only.
"""
import argparse
import json
import os
import re
import sys
from fractions import Fraction

SCHEMA = "g09-k8s-check-v1"
SCOPE = ("static manifest files only; no cluster was contacted, nothing was applied or deployed, and no "
         "rollout behaviour was observed")


class Unusable(Exception):
    def __init__(self, code, where, reason):
        Exception.__init__(self, "%s %s: %s" % (code, where, reason))
        self.code, self.where, self.reason = code, where, reason


# ---------------------------------------------------------------- YAML subset reader with line numbers
class Map(dict):
    """dict that remembers the line of each key."""
    def __init__(self, line):
        dict.__init__(self)
        self.line, self.lines = line, {}


class Seq(list):
    def __init__(self, line):
        list.__init__(self)
        self.line, self.lines = line, []


_KEY = re.compile(r'''^(?:"((?:[^"\\]|\\.)*)"|'((?:[^']|'')*)'|([^\s#'"\[\]{},&*!|>%@`?][^#]*?|\?[^\s][^#]*?))\s*:(?:\s+|$)(.*)$''')
_BOOL = {"true": True, "True": True, "TRUE": True, "false": False, "False": False, "FALSE": False,
         "yes": True, "Yes": True, "YES": True, "no": False, "No": False, "NO": False,
         "on": True, "On": True, "ON": True, "off": False, "Off": False, "OFF": False}
_NULL = {"", "~", "null", "Null", "NULL"}
_INT = re.compile(r'^[-+]?(0|[1-9][0-9_]*)$')
_FLOAT = re.compile(r'^[-+]?(\.[0-9]+|[0-9][0-9_]*(\.[0-9]*)?)([eE][-+]?[0-9]+)?$')


def _fc(s, chars):
    """first character of s is one of chars (False for an empty s)."""
    return s[:1] != '' and s[:1] in chars


def _strip_comment(s):
    q, i = None, 0
    while i < len(s):
        c = s[i]
        if q:
            if c == '\\' and q == '"':
                i += 2
                continue
            if c == q:
                if q == "'" and i + 1 < len(s) and s[i + 1] == "'":
                    i += 2
                    continue
                q = None
        elif c in "'\"" and (i == 0 or s[i - 1] in " \t:-[{,"):
            q = c
        elif c == '#' and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
        i += 1
    return s.rstrip()


def _unquote_double(body, where):
    out, i = [], 0
    esc = {'"': '"', '\\': '\\', '/': '/', 'n': '\n', 't': '\t', 'r': '\r', '0': '\0', ' ': ' '}
    while i < len(body):
        c = body[i]
        if c == '\\':
            n = body[i + 1:i + 2]
            if n in esc:
                out.append(esc[n]); i += 2; continue
            if n == 'u' and re.match(r'[0-9a-fA-F]{4}$', body[i + 2:i + 6]):
                out.append(chr(int(body[i + 2:i + 6], 16))); i += 6; continue
            raise Unusable("YAML_UNSUPPORTED", where, "escape \\%s in a double-quoted string" % n)
        out.append(c); i += 1
    return ''.join(out)


def _scalar(text, where):
    t = text.strip()
    if t[:1] in ('&', '*', '!'):
        raise Unusable("YAML_UNSUPPORTED", where, "anchors, aliases and tags are not read; expand them first")
    if t[:1] == '"':
        if len(t) < 2 or not t.endswith('"'):
            raise Unusable("YAML_UNSUPPORTED", where, "multi-line or unterminated double-quoted string")
        return _unquote_double(t[1:-1], where)
    if t[:1] == "'":
        if len(t) < 2 or not t.endswith("'"):
            raise Unusable("YAML_UNSUPPORTED", where, "multi-line or unterminated single-quoted string")
        return t[1:-1].replace("''", "'")
    if t in _NULL:
        return None
    if t in _BOOL:
        return _BOOL[t]
    if _INT.match(t):
        return int(t.replace('_', ''))
    if _FLOAT.match(t) and any(ch in t for ch in '.eE'):
        return float(t.replace('_', ''))
    if _fc(t, '[{'):
        return _flow(t, where)
    if _fc(t, '|>'):
        raise Unusable("YAML_UNSUPPORTED", where, "block scalar in this position")
    return t


def _flow(t, where):
    pos = [0]

    def ws():
        while pos[0] < len(t) and t[pos[0]] in ' \t':
            pos[0] += 1

    def item(stop):
        ws()
        c = t[pos[0]:pos[0] + 1]
        if c == '[':
            pos[0] += 1; out = Seq(where[1]); ws()
            if t[pos[0]:pos[0] + 1] == ']':
                pos[0] += 1; return out
            while True:
                out.append(item(',]')); out.lines.append(where[1]); ws()
                c2 = t[pos[0]:pos[0] + 1]; pos[0] += 1
                if c2 == ']':
                    return out
                if c2 != ',':
                    raise Unusable("YAML_UNSUPPORTED", where, "unterminated flow sequence")
        if c == '{':
            pos[0] += 1; out = Map(where[1]); ws()
            if t[pos[0]:pos[0] + 1] == '}':
                pos[0] += 1; return out
            while True:
                k = item(':,}'); ws()
                if t[pos[0]:pos[0] + 1] != ':':
                    raise Unusable("YAML_UNSUPPORTED", where, "flow mapping entry without a value")
                pos[0] += 1
                v = item(',}')
                out[str(k)] = v; out.lines[str(k)] = where[1]; ws()
                c2 = t[pos[0]:pos[0] + 1]; pos[0] += 1
                if c2 == '}':
                    return out
                if c2 != ',':
                    raise Unusable("YAML_UNSUPPORTED", where, "unterminated flow mapping")
        if c in ('"', "'"):
            j = pos[0] + 1
            while j < len(t):
                if t[j] == '\\' and c == '"':
                    j += 2; continue
                if t[j] == c:
                    if c == "'" and t[j + 1:j + 2] == "'":
                        j += 2; continue
                    break
                j += 1
            s = t[pos[0]:j + 1]; pos[0] = j + 1
            return _scalar(s, where)
        j = pos[0]
        while j < len(t) and t[j] not in stop and not (t[j] == ':' and ':' in stop and t[j + 1:j + 2] in (' ', ',', '}', '')):
            if t[j] in '[]{}' :
                break
            j += 1
        s = t[pos[0]:j]; pos[0] = j
        return _scalar(s, where)

    v = item('')
    ws()
    if pos[0] != len(t):
        raise Unusable("YAML_UNSUPPORTED", where, "text after a flow collection")
    return v


class _Doc(object):
    def __init__(self, fname, lines, dups):
        self.f, self.toks, self.dups = fname, lines, dups  # toks: [lineno, indent, text, rawline]

    def where(self, i):
        return (self.f, self.toks[i][0] if i < len(self.toks) else (self.toks[-1][0] if self.toks else 1))

    def node(self, i, ind):
        ln, ti, tx = self.toks[i][0], self.toks[i][1], self.toks[i][2]
        if tx == '-' or tx.startswith('- '):
            return self.seq(i, ti)
        if _KEY.match(tx) and not _fc(tx, '[{"\'') or (_fc(tx, '"\'') and _KEY.match(tx)):
            return self.mapping(i, ti)
        if i + 1 < len(self.toks) and self.toks[i + 1][1] > ti:
            raise Unusable("YAML_UNSUPPORTED", self.where(i + 1), "multi-line plain scalar")
        return _scalar(tx, (self.f, ln)), i + 1

    def block(self, i, ind, indicator):
        """literal (|) or folded (>) block scalar with clip, strip (-) or keep (+) chomping."""
        raw, j = [], i + 1
        while j < len(self.toks) and self.toks[j][1] > ind:
            raw.append(self.toks[j][3]); j += 1
        digits = re.sub(r'[^0-9]', '', indicator)
        filled = [r for r in raw if r.strip()]
        ci = (ind + int(digits)) if digits else (min(len(r) - len(r.lstrip(' ')) for r in filled) if filled else 0)
        lines = [(r[ci:] if r.strip() else '') for r in raw]
        trailing = 0
        while lines and lines[-1] == '':
            lines.pop(); trailing += 1
        if indicator[0] == '|':
            body = "\n".join(lines)
        else:
            body = ''
            for n, ln in enumerate(lines):
                if n == 0:
                    body = ln
                elif ln == '':
                    body += "\n"
                elif lines[n - 1] == '':
                    body += ln
                elif ln[:1] == ' ' or lines[n - 1][:1] == ' ':
                    body += "\n" + ln
                else:
                    body += ' ' + ln
        if not lines:
            return '', j
        if '-' in indicator:
            return body, j
        if '+' in indicator:
            return body + "\n" * (1 + trailing), j
        return body + "\n", j

    def value(self, i, ind, rest):
        """value after 'key:' on token i, at mapping indent ind; returns (value, next)."""
        if rest == '':
            if i + 1 < len(self.toks):
                nt = self.toks[i + 1]
                if nt[1] > ind or (nt[1] == ind and (nt[2] == '-' or nt[2].startswith('- '))):
                    return self.node(i + 1, nt[1])
            return None, i + 1
        if _fc(rest, '|>') and re.match(r'^[|>][-+0-9]*$', rest):
            return self.block(i, ind, rest)
        if i + 1 < len(self.toks) and self.toks[i + 1][1] > ind and not _fc(rest, '[{') :
            raise Unusable("YAML_UNSUPPORTED", self.where(i + 1), "multi-line plain scalar or unexpected indentation")
        return _scalar(rest, (self.f, self.toks[i][0])), i + 1

    def mapping(self, i, ind):
        m = Map(self.toks[i][0])
        while i < len(self.toks) and self.toks[i][1] == ind:
            tx, ln = self.toks[i][2], self.toks[i][0]
            mt = _KEY.match(tx)
            if not mt or tx == '-' or tx.startswith('- '):
                raise Unusable("YAML_UNSUPPORTED", self.where(i), "expected 'key: value'")
            key = mt.group(1) if mt.group(1) is not None else (mt.group(2).replace("''", "'") if mt.group(2) is not None else mt.group(3).strip())
            if key.startswith('?') or key == '<<' or _fc(key, '&*!'):
                raise Unusable("YAML_UNSUPPORTED", self.where(i), "complex keys, merge keys, anchors and tags are not read")
            rest = mt.group(4).strip()
            if _fc(rest, '&*!'):
                raise Unusable("YAML_UNSUPPORTED", self.where(i), "anchors, aliases and tags are not read; expand them first")
            v, i = self.value(i, ind, rest)
            if key in m:
                self.dups.append((self.f, ln, key, m.lines[key]))
            m[key] = v; m.lines[key] = ln
        if i < len(self.toks) and self.toks[i][1] > ind:
            raise Unusable("YAML_UNSUPPORTED", self.where(i), "unexpected indentation")
        return m, i

    def seq(self, i, ind):
        s = Seq(self.toks[i][0])
        while i < len(self.toks) and self.toks[i][1] == ind and (self.toks[i][2] == '-' or self.toks[i][2].startswith('- ')):
            ln, tx = self.toks[i][0], self.toks[i][2]
            rest = tx[1:].lstrip()
            if rest == '':
                if i + 1 < len(self.toks) and self.toks[i + 1][1] > ind:
                    v, i = self.node(i + 1, self.toks[i + 1][1])
                else:
                    v, i = None, i + 1
            else:
                newind = ind + (len(tx) - len(rest))
                if rest == '-' or rest.startswith('- ') or (_KEY.match(rest) and not _fc(rest, '[{')):
                    self.toks[i] = [ln, newind, rest, self.toks[i][3]]
                    v, i = self.node(i, newind)
                elif _fc(rest, '|>'):
                    v, i = self.block(i, ind, rest)
                else:
                    if i + 1 < len(self.toks) and self.toks[i + 1][1] > ind:
                        raise Unusable("YAML_UNSUPPORTED", self.where(i + 1), "multi-line plain scalar")
                    v, i = _scalar(rest, (self.f, ln)), i + 1
            s.append(v); s.lines.append(ln)
        return s, i


def load_yaml(text, fname):
    """Return [(doc_value, first_line)], duplicate-key list."""
    docs, cur, dups = [], [], []
    start = 1
    for n, raw in enumerate(text.split('\n'), 1):
        if raw.startswith('%'):
            raise Unusable("YAML_UNSUPPORTED", (fname, n), "YAML directives are not read")
        if re.match(r'^(---|\.\.\.)(\s.*)?$', raw):
            docs.append((cur, start)); cur, start = [], n + 1
            rest = raw[3:].strip()
            if rest and not rest.startswith('#'):
                raise Unusable("YAML_UNSUPPORTED", (fname, n), "content on a document marker line")
            continue
        cur.append((n, raw))
    docs.append((cur, start))
    out = []
    for lines, first in docs:
        toks, k = [], 0
        while k < len(lines):
            n, raw = lines[k]
            body = raw.lstrip(' ')
            if body.startswith('\t'):
                raise Unusable("YAML_UNSUPPORTED", (fname, n), "tab used for indentation")
            s = _strip_comment(body)
            if s.strip():
                toks.append([n, len(raw) - len(body), s, raw])
                m = _KEY.match(s)
                tail = (m.group(4).strip() if m else (s[1:].strip() if s.startswith('-') else ''))
                if re.match(r'^[|>][-+0-9]*$', tail):
                    ind = len(raw) - len(body)
                    k += 1
                    while k < len(lines) and (not lines[k][1].strip() or len(lines[k][1]) - len(lines[k][1].lstrip(' ')) > ind):
                        toks.append([lines[k][0], 10 ** 6, lines[k][1].strip() or ' ', lines[k][1].rstrip('\r')])
                        k += 1
                    continue
            k += 1
        if not toks:
            continue
        d = _Doc(fname, toks, dups)
        if toks[0][1] != 0:
            raise Unusable("YAML_UNSUPPORTED", (fname, toks[0][0]), "document does not start at column 1")
        v, i = d.node(0, 0)
        if i != len(toks):
            raise Unusable("YAML_UNSUPPORTED", d.where(i), "content after the end of the document")
        out.append((v, toks[0][0]))
    return out, dups


def _json_lines(obj, line=1):
    """Wrap parsed JSON in Map/Seq without line data (line 1 = the file)."""
    if isinstance(obj, dict):
        m = Map(line)
        for k, v in obj.items():
            m[k] = _json_lines(v, line); m.lines[k] = line
        return m
    if isinstance(obj, list):
        s = Seq(line)
        for v in obj:
            s.append(_json_lines(v, line)); s.lines.append(line)
        return s
    return obj


# ---------------------------------------------------------------- quantities
_QSUF = {'n': Fraction(1, 10 ** 9), 'u': Fraction(1, 10 ** 6), 'm': Fraction(1, 1000), '': Fraction(1),
         'k': Fraction(10 ** 3), 'M': Fraction(10 ** 6), 'G': Fraction(10 ** 9), 'T': Fraction(10 ** 12),
         'P': Fraction(10 ** 15), 'E': Fraction(10 ** 18), 'Ki': Fraction(2 ** 10), 'Mi': Fraction(2 ** 20),
         'Gi': Fraction(2 ** 30), 'Ti': Fraction(2 ** 40), 'Pi': Fraction(2 ** 50), 'Ei': Fraction(2 ** 60)}
_QRE = re.compile(r'^([+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))(?:([eE][-+]?[0-9]+)|(Ki|Mi|Gi|Ti|Pi|Ei|n|u|m|k|M|G|T|P|E))?$')


def quantity(v):
    """Kubernetes resource quantity -> Fraction, or None when invalid."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int):
        return Fraction(v) if v >= 0 else None
    if isinstance(v, float):
        return Fraction(str(v)) if v >= 0 else None
    m = _QRE.match(str(v).strip()) if isinstance(v, str) else None
    if not m:
        return None
    num = Fraction(m.group(1).lstrip('+'))
    if m.group(2):
        return num * Fraction(10) ** int(m.group(2)[1:])
    return num * _QSUF[m.group(3) or '']


# ---------------------------------------------------------------- object model
POD_TEMPLATE_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "ReplicationController", "Job",
                      "CronJob", "Pod"}
SELECTOR_REQUIRED = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet"}
LONG_RUNNING = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "ReplicationController", "Pod"}
_PORTNAME = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')


def _get(m, *path):
    for p in path:
        if not isinstance(m, dict) or p not in m:
            return None
        m = m[p]
    return m


def _line(m, key=None, default=None):
    if isinstance(m, Map):
        if key is not None and key in m.lines:
            return m.lines[key]
        return m.line
    if isinstance(m, Seq):
        return m.line
    return default


class Obj(object):
    def __init__(self, f, line, body, default_ns):
        self.f, self.line, self.body = f, line, body
        self.kind = body.get("kind") if isinstance(body.get("kind"), str) else None
        self.api = body.get("apiVersion")
        md = body.get("metadata") if isinstance(body.get("metadata"), dict) else Map(line)
        self.md = md
        self.name = md.get("name") if isinstance(md.get("name"), str) else None
        ns = md.get("namespace")
        self.ns = ns if isinstance(ns, str) and ns else default_ns
        self.labels = md.get("labels") if isinstance(md.get("labels"), dict) else {}
        self.pod_spec, self.pod_labels, self.pod_path, self.pod_meta = None, None, None, None
        if self.kind in POD_TEMPLATE_KINDS:
            if self.kind == "Pod":
                self.pod_spec, self.pod_labels, self.pod_path = body.get("spec"), self.labels, "spec"
                self.pod_meta = md
            else:
                base = ("spec", "jobTemplate", "spec", "template") if self.kind == "CronJob" else ("spec", "template")
                tpl = _get(body, *base)
                if isinstance(tpl, dict):
                    self.pod_spec = tpl.get("spec")
                    self.pod_meta = tpl.get("metadata") if isinstance(tpl.get("metadata"), dict) else None
                    lb = _get(tpl, "metadata", "labels")
                    self.pod_labels = lb if isinstance(lb, dict) else {}
                self.pod_path = ".".join(base) + ".spec"
            if not isinstance(self.pod_spec, dict):
                self.pod_spec = None

    def ident(self):
        return "%s/%s" % (self.kind, self.name)

    def containers(self):
        """[(path, container_map, is_init)]"""
        out = []
        if not self.pod_spec:
            return out
        for key, init in (("initContainers", True), ("containers", False)):
            cs = self.pod_spec.get(key)
            if isinstance(cs, list):
                for i, c in enumerate(cs):
                    if isinstance(c, dict):
                        out.append(("%s.%s[%d]" % (self.pod_path, key, i), c, init))
        return out

    def replicas(self):
        r = _get(self.body, "spec", "replicas")
        if self.kind in ("Deployment", "StatefulSet", "ReplicaSet", "ReplicationController"):
            return r if isinstance(r, int) and not isinstance(r, bool) else 1
        return None


def selector_matches(sel, labels):
    """sel: matchLabels/matchExpressions mapping (LabelSelector) or plain map. labels: dict."""
    if not isinstance(sel, dict):
        return False
    labels = {str(k): str(v) for k, v in (labels or {}).items()}
    if "matchLabels" in sel or "matchExpressions" in sel:
        ml = sel.get("matchLabels") or {}
        me = sel.get("matchExpressions") or []
        if not ml and not me:
            return True
        if not isinstance(ml, dict) or not isinstance(me, list):
            return False
        for k, v in ml.items():
            if labels.get(str(k)) != str(v):
                return False
        for e in me:
            if not isinstance(e, dict):
                return False
            k, op, vals = str(e.get("key")), e.get("operator"), [str(x) for x in (e.get("values") or [])]
            if op == "In" and labels.get(k) not in vals:
                return False
            if op == "NotIn" and k in labels and labels[k] in vals:
                return False
            if op == "Exists" and k not in labels:
                return False
            if op == "DoesNotExist" and k in labels:
                return False
            if op not in ("In", "NotIn", "Exists", "DoesNotExist"):
                return False
        return True
    for k, v in sel.items():
        if labels.get(str(k)) != str(v):
            return False
    return True


def _fmt_sel(sel):
    if isinstance(sel, dict) and ("matchLabels" in sel or "matchExpressions" in sel):
        parts = ["%s=%s" % (k, v) for k, v in (sel.get("matchLabels") or {}).items()]
        for e in sel.get("matchExpressions") or []:
            if isinstance(e, dict):
                parts.append("%s %s %s" % (e.get("key"), e.get("operator"), list(e.get("values") or [])))
        return ",".join(parts)
    return ",".join("%s=%s" % (k, v) for k, v in (sel or {}).items())


# ---------------------------------------------------------------- checks
class Report(object):
    def __init__(self):
        self.findings = []

    def add(self, sev, code, o, line, path, reason, suggestion=None):
        self.findings.append({"severity": sev, "code": code, "file": o.f if o else None, "line": line,
                              "kind": o.kind if o else None, "name": o.name if o else None,
                              "namespace": o.ns if o else None, "path": path, "reason": reason,
                              "suggestion": suggestion})


def _ports_of(c):
    out = []
    ps = c.get("ports")
    if isinstance(ps, list):
        for p in ps:
            if isinstance(p, dict):
                out.append(p)
    return out


def check_objects(objs, rep):
    by_ns = {}
    for o in objs:
        by_ns.setdefault(o.ns, []).append(o)
    workloads = [o for o in objs if o.kind in POD_TEMPLATE_KINDS and o.pod_spec is not None]
    limitranges = {}
    for o in objs:
        if o.kind == "LimitRange":
            for lim in _get(o.body, "spec", "limits") or []:
                if isinstance(lim, dict) and lim.get("type") == "Container":
                    d = {}
                    for k in ("default", "defaultRequest"):
                        if isinstance(lim.get(k), dict):
                            d[k] = lim[k]
                    limitranges.setdefault(o.ns, []).append((o, d))

    served = {}  # id(workload) -> list of Service objs selecting it
    # ---- workload checks
    for o in objs:
        if o.kind in POD_TEMPLATE_KINDS and o.pod_spec is None:
            rep.add("error", "POD_TEMPLATE_MISSING", o, o.line, o.pod_path or "spec",
                    "%s has no pod spec at %s" % (o.kind, o.pod_path or "spec.template.spec"))
            continue
        if o.kind in SELECTOR_REQUIRED or o.kind == "ReplicationController":
            sel = _get(o.body, "spec", "selector")
            sl = _line(o.body.get("spec"), "selector", o.line)
            if sel is None and o.kind in SELECTOR_REQUIRED:
                rep.add("error", "WORKLOAD_SELECTOR_MISSING", o, sl, "spec.selector",
                        "apps/v1 %s requires spec.selector; the API server rejects it without one" % o.kind,
                        "spec.selector.matchLabels: %s" % json.dumps(dict(o.pod_labels or {}), sort_keys=True))
            elif sel is not None and not selector_matches(sel, o.pod_labels):
                rep.add("error", "WORKLOAD_SELECTOR_TEMPLATE_MISMATCH", o, sl, "spec.selector",
                        "selector %s does not match the pod template labels %s; the API server rejects this "
                        "(selector does not match template labels)" % (_fmt_sel(sel), _fmt_sel(o.pod_labels or {})),
                        "make the template labels include %s" % _fmt_sel(sel))
        _check_pod(o, rep, limitranges.get(o.ns, []))

    # ---- services
    for o in objs:
        if o.kind != "Service":
            continue
        spec = o.body.get("spec") if isinstance(o.body.get("spec"), dict) else Map(o.line)
        ports = spec.get("ports") if isinstance(spec.get("ports"), list) else []
        if len(ports) > 1:
            for i, p in enumerate(ports):
                if isinstance(p, dict) and not p.get("name"):
                    rep.add("error", "SERVICE_PORT_NAME_REQUIRED", o, _line(p, None, o.line), "spec.ports[%d].name" % i,
                            "a Service with more than one port must name every port; the API server rejects it")
        if spec.get("type") == "ExternalName":
            continue
        sel = spec.get("selector")
        if not isinstance(sel, dict) or not sel:
            continue
        sline = _line(spec, "selector", o.line)
        peers = [w for w in workloads if w.ns == o.ns]
        matched = [w for w in peers if selector_matches(sel, w.pod_labels)]
        if not peers:
            rep.add("warning", "SERVICE_SELECTOR_UNRESOLVED", o, sline, "spec.selector",
                    "no workload in namespace %s is in these files, so selector %s cannot be confirmed" % (o.ns, _fmt_sel(sel)))
            continue
        if not matched:
            near = []
            for w in peers:
                lb = {str(k): str(v) for k, v in (w.pod_labels or {}).items()}
                shared = [k for k in sel if str(k) in lb]
                if shared:
                    near.append("%s has %s" % (w.ident(), ",".join("%s=%s" % (k, lb[str(k)]) for k in shared)))
            rep.add("error", "SERVICE_SELECTOR_NO_MATCH", o, sline, "spec.selector",
                    "selector %s matches no pod template in namespace %s; the Service would have no endpoints"
                    % (_fmt_sel(sel), o.ns), "; ".join(near) or None)
            continue
        for w in matched:
            served.setdefault(id(w), []).append(o)
        for i, p in enumerate(ports):
            if not isinstance(p, dict):
                continue
            tp = p.get("targetPort", p.get("port"))
            pl = _line(p, "targetPort", _line(p, None, o.line))
            for w in matched:
                cports = [cp for _, c, init in w.containers() if not init for cp in _ports_of(c)]
                if isinstance(tp, str) and not tp.isdigit():
                    names = sorted({str(cp.get("name")) for cp in cports if cp.get("name")})
                    if tp not in names:
                        rep.add("error", "SERVICE_TARGETPORT_NAME_UNKNOWN", o, pl, "spec.ports[%d].targetPort" % i,
                                "targetPort %r is not a container port name in %s (names: %s); endpoints get no port"
                                % (tp, w.ident(), ", ".join(names) or "none"),
                                ("use one of: %s" % ", ".join(names)) if names else "name the container port")
                elif isinstance(tp, (int, str)) and not isinstance(tp, bool):
                    num = int(tp)
                    nums = sorted({cp.get("containerPort") for cp in cports if isinstance(cp.get("containerPort"), int)})
                    if nums and num not in nums:
                        rep.add("warning", "SERVICE_TARGETPORT_UNDECLARED", o, pl, "spec.ports[%d].targetPort" % i,
                                "targetPort %d is not declared by %s (declared: %s); traffic reaches it only if the "
                                "process listens there" % (num, w.ident(), ", ".join(str(n) for n in nums)))

    # ---- readiness behind a service
    for w in workloads:
        if id(w) not in served:
            continue
        for path, c, init in w.containers():
            if init:
                continue
            if c.get("readinessProbe") is None:
                rep.add("error", "READINESS_PROBE_MISSING", w, _line(c, None, w.line), path + ".readinessProbe",
                        "container %r receives Service traffic (%s) but has no readinessProbe, so it is sent "
                        "traffic before it can serve" % (c.get("name"), ", ".join(s.ident() for s in served[id(w)])))

    # ---- HPA
    for o in objs:
        if o.kind != "HorizontalPodAutoscaler":
            continue
        spec = o.body.get("spec") if isinstance(o.body.get("spec"), dict) else Map(o.line)
        mn, mx = spec.get("minReplicas", 1), spec.get("maxReplicas")
        if isinstance(mn, int) and isinstance(mx, int) and mn > mx:
            rep.add("error", "HPA_MIN_GT_MAX", o, _line(spec, "minReplicas", o.line), "spec.minReplicas",
                    "minReplicas %d is greater than maxReplicas %d" % (mn, mx))
        ref = spec.get("scaleTargetRef") if isinstance(spec.get("scaleTargetRef"), dict) else {}
        tgt = [w for w in workloads if w.ns == o.ns and w.kind == ref.get("kind") and w.name == ref.get("name")]
        rl = _line(spec, "scaleTargetRef", o.line)
        if not tgt:
            rep.add("warning", "HPA_TARGET_UNRESOLVED", o, rl, "spec.scaleTargetRef",
                    "%s/%s is not in these files; its requests cannot be checked" % (ref.get("kind"), ref.get("name")))
            continue
        res = set()
        if spec.get("targetCPUUtilizationPercentage") is not None:
            res.add("cpu")
        for mt in spec.get("metrics") or []:
            if isinstance(mt, dict) and mt.get("type") in ("Resource", "ContainerResource"):
                r = _get(mt, "resource", "name") or _get(mt, "containerResource", "name")
                t = _get(mt, "resource", "target", "type") or _get(mt, "containerResource", "target", "type")
                if r and t == "Utilization":
                    res.add(str(r))
        if not spec.get("metrics") and spec.get("targetCPUUtilizationPercentage") is None and str(o.api).startswith("autoscaling/v1"):
            res.add("cpu")
        for r in sorted(res):
            for path, c, init in tgt[0].containers():
                if init:
                    continue
                if _effective(c, "requests", r, limitranges.get(tgt[0].ns, [])) is None:
                    rep.add("error", "HPA_TARGET_NO_REQUEST", o, rl, "spec.scaleTargetRef",
                            "scales on %s utilization but container %r of %s has no %s request, so the HPA cannot "
                            "compute utilization and does nothing" % (r, c.get("name"), tgt[0].ident(), r))

    # ---- PDB
    pdbs = [o for o in objs if o.kind == "PodDisruptionBudget"]
    covered = set()
    for o in pdbs:
        spec = o.body.get("spec") if isinstance(o.body.get("spec"), dict) else Map(o.line)
        sel = spec.get("selector")
        peers = [w for w in workloads if w.ns == o.ns and w.kind in LONG_RUNNING]
        matched = [w for w in peers if isinstance(sel, dict) and selector_matches(sel, w.pod_labels)]
        sl = _line(spec, "selector", o.line)
        if peers and not matched:
            rep.add("error", "PDB_SELECTOR_NO_MATCH", o, sl, "spec.selector",
                    "selector %s matches no pod template in namespace %s; the budget protects nothing" % (_fmt_sel(sel), o.ns))
        for w in matched:
            covered.add(id(w))
        total = sum((w.replicas() or 0) for w in matched if w.replicas() is not None)
        if matched and all(w.replicas() is not None for w in matched):
            mina, maxu = spec.get("minAvailable"), spec.get("maxUnavailable")
            if isinstance(mina, int) and not isinstance(mina, bool) and mina >= total:
                rep.add("error", "PDB_BLOCKS_EVICTION", o, _line(spec, "minAvailable", o.line), "spec.minAvailable",
                        "minAvailable %d with %d replica(s) allows no voluntary eviction; node drains hang" % (mina, total),
                        "minAvailable: %d or maxUnavailable: 1" % max(total - 1, 0))
            if mina == "100%" or maxu == 0 or maxu == "0%":
                k = "minAvailable" if mina == "100%" else "maxUnavailable"
                rep.add("error", "PDB_BLOCKS_EVICTION", o, _line(spec, k, o.line), "spec." + k,
                        "%s %r allows no voluntary eviction; node drains hang" % (k, spec.get(k)), "maxUnavailable: 1")
    for w in workloads:
        r = w.replicas()
        if w.kind in ("Deployment", "StatefulSet") and r is not None and r > 1 and id(w) not in covered:
            rep.add("warning", "PDB_MISSING", w, _line(w.body.get("spec"), "replicas", w.line), "spec.replicas",
                    "%d replicas and no PodDisruptionBudget in these files selects them" % r)


def _effective(c, kind, res, lrs):
    """effective requests/limits value for resource res (limit defaults request; LimitRange defaults)."""
    r = c.get("resources") if isinstance(c.get("resources"), dict) else {}
    v = _get(r, kind, res)
    if v is not None:
        return v
    if kind == "requests":
        lv = _get(r, "limits", res)
        if lv is not None:
            return lv
    for _o, d in lrs:
        key = "defaultRequest" if kind == "requests" else "default"
        if res in d.get(key, {}):
            return d[key][res]
        if kind == "requests" and res in d.get("default", {}):
            return d["default"][res]
    return None


def _check_probe(o, rep, path, c, pname, probe, cports):
    pl = _line(c, pname, o.line)
    if not isinstance(probe, dict):
        rep.add("error", "PROBE_HANDLER_INVALID", o, pl, path, "%s is not a mapping" % pname)
        return
    handlers = [h for h in ("exec", "httpGet", "tcpSocket", "grpc") if probe.get(h) is not None]
    if len(handlers) != 1:
        rep.add("error", "PROBE_HANDLER_INVALID", o, pl, path,
                "%s must have exactly one of exec, httpGet, tcpSocket, grpc (has %s)" % (pname, ", ".join(handlers) or "none"))
    for f, lo in (("periodSeconds", 1), ("timeoutSeconds", 1), ("failureThreshold", 1), ("successThreshold", 1),
                  ("initialDelaySeconds", 0)):
        v = probe.get(f)
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < lo):
            rep.add("error", "PROBE_VALUE_INVALID", o, _line(probe, f, pl), "%s.%s" % (path, f),
                    "%s.%s must be an integer >= %d (got %r)" % (pname, f, lo, v))
    st = probe.get("successThreshold")
    if pname in ("livenessProbe", "startupProbe") and isinstance(st, int) and st != 1:
        rep.add("error", "PROBE_SUCCESS_THRESHOLD", o, _line(probe, "successThreshold", pl), path + ".successThreshold",
                "%s.successThreshold must be 1; the API server rejects %r" % (pname, st))
    to, pe = probe.get("timeoutSeconds", 1), probe.get("periodSeconds", 10)
    if isinstance(to, int) and isinstance(pe, int) and to > pe:
        rep.add("warning", "PROBE_TIMEOUT_GT_PERIOD", o, _line(probe, "timeoutSeconds", pl), path + ".timeoutSeconds",
                "%s timeoutSeconds %d is longer than periodSeconds %d" % (pname, to, pe))
    for h in ("httpGet", "tcpSocket", "grpc"):
        hb = probe.get(h)
        if not isinstance(hb, dict):
            continue
        port = hb.get("port")
        hl = _line(hb, "port", pl)
        names = sorted({str(cp.get("name")) for cp in cports if cp.get("name")})
        nums = sorted({cp.get("containerPort") for cp in cports if isinstance(cp.get("containerPort"), int)})
        if port is None:
            rep.add("error", "PROBE_PORT_MISSING", o, hl, "%s.%s.port" % (path, h), "%s.%s has no port" % (pname, h))
        elif isinstance(port, str) and not port.isdigit():
            if h == "grpc":
                rep.add("error", "PROBE_PORT_INVALID", o, hl, "%s.%s.port" % (path, h), "grpc probes take a port number")
            elif port not in names:
                rep.add("error", "PROBE_PORT_NAME_UNKNOWN", o, hl, "%s.%s.port" % (path, h),
                        "%s port %r is not a port name of container %r (names: %s); the probe always fails"
                        % (pname, port, c.get("name"), ", ".join(names) or "none"),
                        ("use one of: %s" % ", ".join(names)) if names else None)
        elif isinstance(port, (int, str)) and not isinstance(port, bool):
            n = int(port)
            if not 1 <= n <= 65535:
                rep.add("error", "PROBE_PORT_INVALID", o, hl, "%s.%s.port" % (path, h), "port %d out of range" % n)
            elif nums and n not in nums:
                rep.add("warning", "PROBE_PORT_UNDECLARED", o, hl, "%s.%s.port" % (path, h),
                        "%s port %d is not declared by container %r (declared: %s)"
                        % (pname, n, c.get("name"), ", ".join(str(x) for x in nums)))


def _probe_key(p):
    if not isinstance(p, dict):
        return None
    return json.dumps({k: p.get(k) for k in ("exec", "httpGet", "tcpSocket", "grpc", "periodSeconds",
                                              "failureThreshold", "initialDelaySeconds", "timeoutSeconds")},
                      sort_keys=True, default=str)


def _check_pod(o, rep, lrs):
    if o.pod_spec is None:
        return
    names = {}
    qos_parts = []
    for path, c, init in o.containers():
        nm = c.get("name")
        cl = _line(c, None, o.line)
        if nm in names:
            rep.add("error", "CONTAINER_NAME_DUPLICATE", o, cl, path + ".name",
                    "container name %r is also used at %s" % (nm, names[nm]))
        names[nm] = path
        img = c.get("image")
        il = _line(c, "image", cl)
        if not isinstance(img, str) or not img:
            rep.add("error", "IMAGE_MISSING", o, il, path + ".image", "container %r has no image" % nm)
        else:
            last = img.rsplit("/", 1)[-1]
            if "@sha256:" not in img and (":" not in last or last.endswith(":latest")):
                rep.add("error", "IMAGE_TAG_MUTABLE", o, il, path + ".image",
                        "image %r uses %s; rollouts and rollbacks are not reproducible"
                        % (img, "the latest tag" if last.endswith(":latest") else "no tag (implies latest)"),
                        "pin a version tag or a digest")
        cports = _ports_of(c)
        seen = {}
        for i, p in enumerate(cports):
            pn, cp = p.get("name"), p.get("containerPort")
            pl = _line(p, None, cl)
            if not isinstance(cp, int) or isinstance(cp, bool) or not 1 <= cp <= 65535:
                rep.add("error", "CONTAINER_PORT_INVALID", o, pl, "%s.ports[%d].containerPort" % (path, i),
                        "containerPort %r is not an integer from 1 to 65535" % (cp,))
            if pn is not None:
                pn = str(pn)
                if len(pn) > 15 or not _PORTNAME.match(pn) or "--" in pn or not re.search('[a-z]', pn):
                    rep.add("error", "PORT_NAME_INVALID", o, pl, "%s.ports[%d].name" % (path, i),
                            "port name %r must be at most 15 lowercase letters, digits and single dashes with "
                            "at least one letter; the API server rejects it" % pn)
                if pn in seen:
                    rep.add("error", "CONTAINER_PORT_NAME_DUPLICATE", o, pl, "%s.ports[%d].name" % (path, i),
                            "port name %r is already used in this container" % pn)
                seen[pn] = i
        # resources
        res = c.get("resources") if isinstance(c.get("resources"), dict) else None
        rl = _line(c, "resources", cl)
        missing, defaulted = [], []
        for kind, r in (("requests", "cpu"), ("requests", "memory"), ("limits", "memory")):
            direct = _get(res or {}, kind, r)
            if direct is None and kind == "requests" and _get(res or {}, "limits", r) is not None:
                continue
            if direct is None:
                if _effective(c, kind, r, lrs) is not None:
                    defaulted.append("%s.%s" % (kind, r))
                else:
                    missing.append("%s.%s" % (kind, r))
        if missing:
            rep.add("error", "RESOURCES_MISSING", o, rl, path + ".resources",
                    "container %r has no %s; it can be BestEffort, starve neighbours or be OOM-killed first"
                    % (nm, ", ".join(missing)), "set requests from measured peak and a memory limit")
        if defaulted:
            rep.add("warning", "RESOURCES_DEFAULTED", o, rl, path + ".resources",
                    "container %r relies on a LimitRange default for %s" % (nm, ", ".join(defaulted)))
        for kind in ("requests", "limits"):
            for r, v in ((_get(res or {}, kind) or {}).items() if isinstance(_get(res or {}, kind), dict) else []):
                if quantity(v) is None:
                    rep.add("error", "RESOURCE_QUANTITY_INVALID", o, _line(res.get(kind), r, rl),
                            "%s.resources.%s.%s" % (path, kind, r), "%r is not a valid quantity" % (v,))
        if res and isinstance(res.get("requests"), dict) and isinstance(res.get("limits"), dict):
            for r, v in res["requests"].items():
                lv = res["limits"].get(r)
                qv, ql = quantity(v), quantity(lv)
                if qv is not None and ql is not None and qv > ql:
                    rep.add("error", "REQUEST_EXCEEDS_LIMIT", o, _line(res["requests"], r, rl),
                            "%s.resources.requests.%s" % (path, r),
                            "request %s %s is above its limit %s; the API server rejects it" % (r, v, lv))
        if not init:
            qos_parts.append(_qos_part(c, lrs))
        # probes
        if not init:
            for pname in ("startupProbe", "livenessProbe", "readinessProbe"):
                if c.get(pname) is not None:
                    _check_probe(o, rep, "%s.%s" % (path, pname), c, pname, c.get(pname), cports)
            if o.kind in LONG_RUNNING and c.get("livenessProbe") is None:
                rep.add("warning", "LIVENESS_PROBE_MISSING", o, cl, path + ".livenessProbe",
                        "container %r has no livenessProbe; a hung process is never restarted" % nm)
            lk, rk = _probe_key(c.get("livenessProbe")), _probe_key(c.get("readinessProbe"))
            if lk and lk == rk:
                rep.add("warning", "PROBES_IDENTICAL", o, _line(c, "livenessProbe", cl), path + ".livenessProbe",
                        "liveness and readiness probes are identical; a dependency outage restarts every pod "
                        "instead of only taking it out of rotation")
    if qos_parts:
        o.qos = ("BestEffort" if all(p == "none" for p in qos_parts) else
                 "Guaranteed" if all(p == "guaranteed" for p in qos_parts) else "Burstable")


def _qos_part(c, lrs):
    res = c.get("resources") if isinstance(c.get("resources"), dict) else {}
    req = {r: _effective(c, "requests", r, lrs) for r in ("cpu", "memory")}
    lim = {r: _get(res, "limits", r) for r in ("cpu", "memory")}
    for r in ("cpu", "memory"):
        if lim[r] is None:
            for _o, d in lrs:
                if r in d.get("default", {}):
                    lim[r] = d["default"][r]
    if all(v is None for v in list(req.values()) + list(lim.values())):
        return "none"
    if all(lim[r] is not None and req[r] is not None and quantity(lim[r]) == quantity(req[r]) for r in ("cpu", "memory")):
        return "guaranteed"
    return "some"


# ---------------------------------------------------------------- loading
def collect_files(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs.sort()
                for f in sorted(files):
                    if f.endswith((".yaml", ".yml", ".json")):
                        out.append(os.path.join(root, f))
        elif os.path.isfile(p):
            out.append(p)
        else:
            raise Unusable("INPUT_UNREADABLE", (p, 0), "no such file or directory")
    return out


def load(paths, default_ns="default"):
    objs, dups = [], []
    files = collect_files(paths)
    for f in files:
        try:
            with open(f, "rb") as fh:
                raw = fh.read()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise Unusable("INPUT_UNREADABLE", (f, 0), str(e))
        if text.startswith("\ufeff"):
            text = text[1:]
        for n, ln in enumerate(text.split("\n"), 1):
            if "{{" in ln and "}}" in ln:
                raise Unusable("TEMPLATE_UNRENDERED", (f, n),
                               "template expression found; render it first (helm template / kustomize build) and check the output")
        if f.endswith(".json"):
            try:
                docs = [(_json_lines(json.loads(text)), 1)]
            except ValueError as e:
                raise Unusable("JSON_INVALID", (f, 0), str(e))
        else:
            docs, d2 = load_yaml(text, f)
            dups.extend(d2)
        for body, line in docs:
            if body is None:
                continue
            if not isinstance(body, dict):
                raise Unusable("OBJECT_INVALID", (f, line), "document is not a mapping")
            items = body.get("items") if isinstance(body.get("kind"), str) and body["kind"].endswith("List") else None
            if isinstance(items, list):
                for i, it in enumerate(items):
                    if isinstance(it, dict):
                        objs.append(Obj(f, _line(it, None, line), it, default_ns))
                continue
            objs.append(Obj(f, line, body, default_ns))
    if not objs:
        raise Unusable("NO_OBJECTS", (",".join(paths), 0), "no Kubernetes objects found")
    return files, objs, dups


def run(paths, default_ns="default"):
    files, objs, dups = load(paths, default_ns)
    rep = Report()
    for f, ln, key, first in dups:
        rep.add("error", "DUPLICATE_KEY", None, ln, key,
                "key %r repeats line %d; Kubernetes keeps only one of the two values" % (key, first))
        rep.findings[-1]["file"] = f
    seen = {}
    for o in objs:
        if not o.kind or not o.api or not o.name:
            rep.add("error", "OBJECT_INVALID", o, o.line, "metadata",
                    "object needs apiVersion, kind and metadata.name")
            continue
        k = (o.kind, o.ns, o.name)
        if k in seen:
            rep.add("error", "OBJECT_DUPLICATE", o, o.line, "metadata.name",
                    "%s %s/%s is also defined at %s:%d; the later apply silently wins" % (o.kind, o.ns, o.name, seen[k][0], seen[k][1]))
        seen[k] = (o.f, o.line)
    check_objects([o for o in objs if o.kind and o.name], rep)
    order = {"error": 0, "warning": 1}
    rep.findings.sort(key=lambda x: (x["file"] or "", x["line"] or 0, order.get(x["severity"], 2), x["code"], x["path"] or ""))
    qos = [{"kind": o.kind, "name": o.name, "namespace": o.ns, "qos": getattr(o, "qos", None)}
           for o in objs if o.kind in POD_TEMPLATE_KINDS and o.pod_spec is not None]
    errors = sum(1 for x in rep.findings if x["severity"] == "error")
    warns = sum(1 for x in rep.findings if x["severity"] == "warning")
    return {"schema": SCHEMA, "evidence_scope": SCOPE, "cluster_contacted": False, "applied": False,
            "deployed": False, "files": files, "objects": len(objs), "findings": rep.findings, "qos": qos,
            "summary": {"errors": errors, "warnings": warns,
                        "status": "errors" if errors else ("warnings" if warns else "clean")}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Offline Kubernetes manifest check (no cluster contact).")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check")
    c.add_argument("paths", nargs="+")
    c.add_argument("--json", action="store_true")
    c.add_argument("--namespace", default="default", help="namespace for objects that name none")
    a = ap.parse_args(argv)
    if a.cmd != "check":
        ap.print_help()
        return 2
    try:
        res = run(a.paths, a.namespace)
    except Unusable as e:
        out = {"schema": SCHEMA, "evidence_scope": SCOPE, "cluster_contacted": False, "applied": False,
               "deployed": False, "unusable": {"code": e.code, "file": e.where[0], "line": e.where[1], "reason": e.reason}}
        if a.json:
            print(json.dumps(out, indent=2))
        else:
            print("%s:%s: UNUSABLE %s: %s" % (e.where[0], e.where[1], e.code, e.reason))
            print("Nothing was checked. " + SCOPE + ".")
        return 2
    except RecursionError:
        print("UNUSABLE NESTING_TOO_DEEP: input nests too deeply to read", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(res, indent=2, sort_keys=False))
    else:
        for x in res["findings"]:
            loc = "%s:%s" % (x["file"], x["line"])
            who = ("%s/%s (%s)" % (x["kind"], x["name"], x["namespace"])) if x["kind"] else "-"
            print("%s: %s %s %s %s: %s" % (loc, x["severity"], x["code"], who, x["path"], x["reason"]))
            if x["suggestion"]:
                print("    suggestion (not applied): %s" % x["suggestion"])
        for q in res["qos"]:
            print("qos %s/%s (%s): %s" % (q["kind"], q["name"], q["namespace"], q["qos"]))
        s = res["summary"]
        print("%d error(s), %d warning(s) in %d object(s) from %d file(s)." % (s["errors"], s["warnings"], res["objects"], len(res["files"])))
        print("Scope: " + SCOPE + ".")
    return 1 if res["summary"]["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
