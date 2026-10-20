#!/usr/bin/env python3
"""Content, metadata, link, accessibility and conversion-path diagnostics for a local HTML snapshot (G34).

Reads a folder of saved pages plus a small JSON config and reports findings with severity, evidence and a concrete
fix. Standard library only; Python 3.9 or newer. It never opens a network connection and never writes inside the
snapshot. External links, live pages, rendering, Core Web Vitals and search-engine indexing are NOT checked.

Exit codes: 0 no finding at or above --fail-on; 1 at least one such finding; 2 usage or input error (nothing
written); 3 incomplete scan (a page or folder was skipped; the report says which). 2 wins over 3, 3 over 1.
"""
import argparse
import json
import os
import posixpath
import re
import sys
import tempfile
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

TOOL = "g34-page-diagnostics"
VERSION = "1.0.0"
SCHEMA = "g34/1"
SEV = {"low": 1, "medium": 2, "high": 3}
UNRUN = ("No network: external links, live pages, rendering, Core Web Vitals and search-engine indexing are "
         "not checked. Findings describe the snapshot only.")
TITLE_RANGE = (50, 60)        # seo-aso-specialist SKILL.md, HARD NUMBERS
DESC_RANGE = (150, 160)       # same source
VAGUE = {"click here", "here", "read more", "learn more", "more", "this link", "link"}
DEPRECATED_LD = {"HowTo", "SpecialAnnouncement"}
RESTRICTED_LD = {"FAQPage"}
NO_LABEL_TYPES = {"hidden", "submit", "button", "reset", "image"}

CHECKS = {
    # check id: (area, severity, fix)
    "title_missing": ("metadata", "high", "Add one non-empty <title> naming the page and the site."),
    "title_multiple": ("metadata", "medium", "Keep a single <title> in <head>."),
    "title_length": ("metadata", "low", "Rewrite the title to 50-60 characters, keyword first."),
    "title_duplicate": ("metadata", "medium", "Give each indexable page its own title."),
    "description_missing": ("metadata", "medium", "Add a <meta name=\"description\"> summarising the page."),
    "description_length": ("metadata", "low", "Rewrite the description to 150-160 characters."),
    "description_duplicate": ("metadata", "low", "Write a page-specific description."),
    "canonical_missing": ("metadata", "medium", "Add <link rel=\"canonical\"> with the page's absolute URL."),
    "canonical_multiple": ("metadata", "high", "Keep exactly one canonical link."),
    "canonical_relative": ("metadata", "medium", "Make the canonical an absolute URL on the site's base URL."),
    "canonical_foreign": ("metadata", "high", "Point the canonical at this site, or confirm the cross-domain intent."),
    "canonical_target_missing": ("metadata", "high", "Point the canonical at a page that exists (after redirects)."),
    "html_lang_missing": ("accessibility", "medium", "Set lang on <html>, e.g. <html lang=\"en\">."),
    "viewport_missing": ("metadata", "medium", "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."),
    "jsonld_invalid": ("metadata", "high", "Fix the JSON-LD so it parses as JSON."),
    "jsonld_deprecated_type": ("metadata", "medium", "Remove the deprecated type; it no longer earns rich results."),
    "jsonld_restricted_type": ("metadata", "low", "FAQ rich results are limited to government and health sites; do not expect them."),
    "encoding_not_utf8": ("metadata", "medium", "Save the page as UTF-8 and declare <meta charset=\"utf-8\">."),
    "h1_missing": ("accessibility", "medium", "Add one <h1> stating the page topic."),
    "h1_multiple": ("accessibility", "medium", "Keep one <h1>; demote the others to <h2>."),
    "heading_skip": ("accessibility", "low", "Do not skip heading levels; use the next level down."),
    "img_alt_missing": ("accessibility", "high", "Add alt text, or alt=\"\" if the image is decorative."),
    "link_name_missing": ("accessibility", "high", "Give the link visible text or an aria-label."),
    "link_text_vague": ("content", "low", "Use link text that names the destination."),
    "button_name_missing": ("accessibility", "high", "Give the button text, an aria-label or a value."),
    "control_label_missing": ("accessibility", "high", "Associate a <label for=...> or add an aria-label."),
    "duplicate_id": ("accessibility", "medium", "Make every id unique on the page."),
    "broken_link": ("links", "high", "Point the link at an existing page or add a redirect."),
    "redirected_link": ("links", "low", "Link straight to the final URL."),
    "redirect_chain": ("links", "medium", "Collapse the chain to one redirect and update the link."),
    "redirect_loop": ("links", "high", "Break the redirect loop and point the link at a real page."),
    "fragment_missing": ("links", "medium", "Add the id on the target page or fix the #fragment."),
    "orphan_page": ("links", "medium", "Link to this page from at least one other page, or retire it."),
    "form_action_broken": ("conversion", "high", "Point the form action at an existing handler page."),
    "conversion_page_missing": ("conversion", "high", "Restore the configured conversion page or update the config."),
    "conversion_goal_missing": ("conversion", "high", "Restore the goal page the CTA should reach."),
    "cta_missing": ("conversion", "high", "Add a named link or form that reaches the configured goal."),
    "sitemap_missing": ("metadata", "low", "Add sitemap.xml listing the indexable pages."),
    "sitemap_invalid": ("metadata", "high", "Fix sitemap.xml so it parses as XML."),
    "sitemap_entry_missing": ("metadata", "high", "Remove the sitemap entry or restore the page."),
    "sitemap_foreign_host": ("metadata", "medium", "List only URLs on the site's base URL."),
    "sitemap_noindex": ("metadata", "high", "Remove noindex pages from the sitemap, or drop noindex."),
    "not_in_sitemap": ("metadata", "low", "Add the indexable page to sitemap.xml."),
}


class UsageError(Exception):
    pass


def norm_ws(s):
    return " ".join(s.split())


class PageParser(HTMLParser):
    """Collects what the checks need in one pass. Tolerant of malformed HTML (HTMLParser never raises on it)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.titles = []
        self.descriptions = []
        self.canonicals = []
        self.viewport = False
        self.noindex = False
        self.headings = []
        self.ids = []
        self.imgs_no_alt = 0
        self.links = []       # dicts: href, name, labelled
        self.buttons = []     # names
        self.controls = []    # (id, has_label_attr, wrapped)
        self.label_for = set()
        self.forms = []       # actions
        self.jsonld = []
        self._title = None
        self._script = None
        self._a = []
        self._button = []
        self._label_depth = 0
        self._head_text = None

    def handle_starttag(self, tag, attrs):
        a = {}
        for k, v in attrs:
            a.setdefault(k, "" if v is None else v)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "a" and "name" in a and "id" not in a:
            self.ids.append(a["name"])
        if tag == "html" and self.lang is None:
            self.lang = a.get("lang", "").strip()
        elif tag == "title":
            self._title = []
        elif tag == "meta":
            name = a.get("name", "").lower()
            if name == "description":
                self.descriptions.append(norm_ws(a.get("content", "")))
            elif name == "viewport":
                self.viewport = True
            elif name == "robots" and "noindex" in a.get("content", "").lower():
                self.noindex = True
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonicals.append(a.get("href", "").strip())
        elif tag == "script" and a.get("type", "").lower().strip() == "application/ld+json":
            self._script = []
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(int(tag[1]))
        elif tag == "img":
            if "alt" not in a:
                self.imgs_no_alt += 1
            alt = norm_ws(a.get("alt", ""))
            for rec in self._a + self._button:
                rec["text"].append(alt)
        elif tag == "a" and "href" in a:
            self._a.append({"href": a["href"].strip(), "text": [], "aria": norm_ws(a.get("aria-label", "")),
                            "labelled": bool(a.get("aria-labelledby", "").strip())})
        elif tag == "button":
            self._button.append({"text": [], "aria": norm_ws(a.get("aria-label", "") or a.get("title", "")),
                                 "labelled": bool(a.get("aria-labelledby", "").strip())})
        elif tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        elif tag in ("input", "select", "textarea"):
            typ = a.get("type", "text").lower() if tag == "input" else tag
            if tag == "input" and typ in ("button",):
                name = norm_ws(a.get("value", "") or a.get("aria-label", "") or a.get("title", ""))
                self.buttons.append(name)
            elif typ not in NO_LABEL_TYPES:
                own = bool(norm_ws(a.get("aria-label", "")) or a.get("aria-labelledby", "").strip()
                           or norm_ws(a.get("title", "")))
                self.controls.append((a.get("id"), own, self._label_depth > 0))
        elif tag == "form":
            self.forms.append(a.get("action", "").strip())

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in ("a", "button", "label", "title", "script"):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "title" and self._title is not None:
            self.titles.append(norm_ws("".join(self._title)))
            self._title = None
        elif tag == "script" and self._script is not None:
            self.jsonld.append("".join(self._script))
            self._script = None
        elif tag == "a" and self._a:
            rec = self._a.pop()
            name = rec["aria"] or norm_ws(" ".join(rec["text"]))
            self.links.append({"href": rec["href"], "name": name, "labelled": rec["labelled"]})
            for outer in self._a:
                outer["text"].extend(rec["text"])
        elif tag == "button" and self._button:
            rec = self._button.pop()
            self.buttons.append("x" if rec["labelled"] else (rec["aria"] or norm_ws(" ".join(rec["text"]))))
        elif tag == "label" and self._label_depth:
            self._label_depth -= 1

    def handle_data(self, data):
        if self._title is not None:
            self._title.append(data)
        if self._script is not None:
            self._script.append(data)
        for rec in self._a + self._button:
            rec["text"].append(data)

    def close(self):
        super().close()
        while self._a:
            self.handle_endtag("a")
        while self._button:
            self.handle_endtag("button")
        if self._title is not None:
            self.handle_endtag("title")
        if self._script is not None:
            self.handle_endtag("script")


def ld_types(obj, out):
    if isinstance(obj, dict):
        t = obj.get("@type")
        for x in (t if isinstance(t, list) else [t]):
            if isinstance(x, str):
                out.add(x.rsplit("/", 1)[-1])
        for v in obj.values():
            ld_types(v, out)
    elif isinstance(obj, list):
        for v in obj:
            ld_types(v, out)
    return out


def load_config(path):
    try:
        with open(path, "rb") as f:
            cfg = json.loads(f.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise UsageError("config %s unreadable: %s" % (path, e.__class__.__name__))
    if not isinstance(cfg, dict):
        raise UsageError("config must be a JSON object")
    base = cfg.get("base_url")
    if not isinstance(base, str):
        raise UsageError("config base_url must be a string")
    sp = urlsplit(base)
    if sp.scheme not in ("http", "https") or not sp.hostname:
        raise UsageError("config base_url must be an http(s) URL with a host")
    red = cfg.get("redirects", {})
    if not isinstance(red, dict) or not all(isinstance(k, str) and isinstance(v, str) and k.startswith("/")
                                            and v.startswith("/") for k, v in red.items()):
        raise UsageError("config redirects must map site paths ('/...') to site paths")
    conv = cfg.get("conversion", {})
    if not isinstance(conv, dict) or not all(isinstance(k, str) and k.startswith("/") and isinstance(v, dict)
                                             and isinstance(v.get("goal"), str) and v["goal"].startswith("/")
                                             for k, v in conv.items()):
        raise UsageError("config conversion must map site paths to {\"goal\": \"/...\"}")
    entry = cfg.get("entry_pages", ["/index.html"])
    if not isinstance(entry, list) or not all(isinstance(x, str) and x.startswith("/") for x in entry):
        raise UsageError("config entry_pages must be a list of site paths")
    return {"base_url": base, "host": sp.hostname.lower(), "redirects": red, "conversion": conv, "entry": entry}


def load_baseline(path):
    try:
        with open(path, "rb") as f:
            rep = json.loads(f.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise UsageError("baseline %s unreadable: %s" % (path, e.__class__.__name__))
    if not isinstance(rep, dict) or rep.get("schema") != SCHEMA or not isinstance(rep.get("findings"), list) \
            or not all(isinstance(f, dict) and isinstance(f.get("key"), str) for f in rep["findings"]):
        raise UsageError("baseline is not a %s report" % SCHEMA)
    return {f["key"]: f for f in rep["findings"]}


def within(path, root):
    return path == root or path.startswith(root + os.sep)


def scan(root, cfg, max_bytes):
    """Walk the snapshot without following links out of it. Returns pages {key: text}, flags, skipped, sitemap."""
    pages, flags, skipped, existing = {}, {}, [], set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for d in sorted(dirnames):
            full = os.path.join(dirpath, d)
            if os.path.islink(full):
                rel = "/" + os.path.relpath(full, root).replace(os.sep, "/")
                skipped.append({"path": rel, "reason": "symlinked directory not followed",
                                "outside_root": not within(os.path.realpath(full), root)})
        dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))
        for fn in sorted(filenames):
            if not fn.lower().endswith((".html", ".htm")):
                continue
            full = os.path.join(dirpath, fn)
            key = "/" + os.path.relpath(full, root).replace(os.sep, "/")
            existing.add(key)
            if os.path.islink(full) and not within(os.path.realpath(full), root):
                skipped.append({"path": key, "reason": "symlink points outside the snapshot", "outside_root": True})
                continue
            try:
                size = os.path.getsize(full)
                if size > max_bytes:
                    skipped.append({"path": key, "reason": "larger than --max-bytes (%d > %d)" % (size, max_bytes),
                                    "outside_root": False})
                    continue
                with open(full, "rb") as f:
                    raw = f.read(max_bytes + 1)
            except OSError as e:
                skipped.append({"path": key, "reason": "unreadable (%s)" % e.__class__.__name__, "outside_root": False})
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
                flags[key] = "encoding"
            pages[key] = text
    sitemap = None
    sm = os.path.join(root, "sitemap.xml")
    if os.path.isfile(sm) and not os.path.islink(sm):
        try:
            if os.path.getsize(sm) > max_bytes:
                sitemap = "invalid"
            else:
                with open(sm, "rb") as f:
                    tree = ET.fromstring(f.read())
                sitemap = [norm_ws(el.text or "") for el in tree.iter() if el.tag.rsplit("}", 1)[-1] == "loc"]
        except (OSError, ET.ParseError):
            sitemap = "invalid"
    return pages, flags, skipped, existing, sitemap


class Site:
    def __init__(self, cfg, existing):
        self.cfg = cfg
        self.existing = existing
        self.lower = {}
        for k in existing:
            self.lower.setdefault(k.lower(), k)

    def to_key(self, path):
        """Site path -> page key, or None. '/' and '/dir/' map to index.html; '/dir' to /dir/index.html."""
        if path.endswith("/"):
            path += "index.html"
        if path in self.existing:
            return path
        if path + "/index.html" in self.existing:
            return path + "/index.html"
        return None

    def internal_path(self, page, href):
        """Return the site path an href points to, or None for external / non-http links."""
        if not href or href.startswith("#"):
            return page if href else None
        sp = urlsplit(href)
        if sp.scheme and sp.scheme.lower() not in ("http", "https"):
            return None
        if sp.netloc:
            if (sp.hostname or "").lower() != self.cfg["host"]:
                return None
            path = sp.path or "/"
        else:
            path = urlsplit(urljoin(page, href)).path
        path = unquote(path)
        trail = path.endswith("/")
        path = "/" + posixpath.normpath("/" + path).lstrip("/")
        if trail and not path.endswith("/"):
            path += "/"
        return path

    def follow(self, path):
        """Follow configured redirects. Returns (final_path, hops, loop)."""
        red, seen, hops = self.cfg["redirects"], [path], 0
        while path in red:
            path = red[path]
            hops += 1
            if path in seen:
                return path, hops, True
            seen.append(path)
        return path, hops, False


def diagnose(root, cfg, max_bytes):
    pages, flags, skipped, existing, sitemap = scan(root, cfg, max_bytes)
    site = Site(cfg, existing)
    findings = []
    external = 0

    def add(check, page, detail):
        area, sev, fix = CHECKS[check]
        findings.append({"key": "%s|%s|%s" % (check, page, detail), "check": check, "area": area,
                         "severity": sev, "page": page, "detail": detail, "fix": fix})

    parsed = {}
    for key in sorted(pages):
        p = PageParser()
        p.feed(pages[key])
        p.close()
        parsed[key] = p
    inbound = {k: set() for k in parsed}
    titles, descs = {}, {}

    def resolve(page, path, kind):
        """Report redirect/broken problems for a site path; return the final page key or None."""
        final, hops, loop = site.follow(path)
        shown = path
        if loop:
            add("redirect_loop", page, "%s %s" % (kind, shown))
            return None
        if hops > 1:
            add("redirect_chain", page, "%s %s -> %s (%d hops)" % (kind, shown, final, hops))
        elif hops == 1:
            add("redirected_link", page, "%s %s -> %s" % (kind, shown, final))
        target = site.to_key(final)
        if target is None:
            hint = site.lower.get(final.lower()) or site.lower.get((final.rstrip("/") + "/index.html").lower())
            detail = "%s %s" % (kind, shown) + (" (differs only in case from %s)" % hint if hint else "")
            add("form_action_broken" if kind == "form" else "broken_link", page, detail)
        return target

    for key in sorted(parsed):
        p = parsed[key]
        if key in flags:
            add("encoding_not_utf8", key, "bytes are not valid UTF-8")
        if not p.titles or not p.titles[0]:
            add("title_missing", key, "no non-empty <title>")
        else:
            if len(p.titles) > 1:
                add("title_multiple", key, "%d titles" % len(p.titles))
            n = len(p.titles[0])
            if not TITLE_RANGE[0] <= n <= TITLE_RANGE[1]:
                add("title_length", key, "%d characters" % n)
            if not p.noindex:
                titles.setdefault(p.titles[0], []).append(key)
        if not p.descriptions or not p.descriptions[0]:
            add("description_missing", key, "no non-empty meta description")
        else:
            n = len(p.descriptions[0])
            if not DESC_RANGE[0] <= n <= DESC_RANGE[1]:
                add("description_length", key, "%d characters" % n)
            if not p.noindex:
                descs.setdefault(p.descriptions[0], []).append(key)
        if not p.lang:
            add("html_lang_missing", key, "<html> has no lang")
        if not p.viewport:
            add("viewport_missing", key, "no viewport meta")
        if not p.noindex:
            if not p.canonicals:
                add("canonical_missing", key, "no canonical link")
            elif len(p.canonicals) > 1:
                add("canonical_multiple", key, "%d canonical links" % len(p.canonicals))
            else:
                c = p.canonicals[0]
                sp = urlsplit(c)
                if not sp.scheme or not sp.netloc:
                    add("canonical_relative", key, "canonical %s" % (c or '""'))
                elif (sp.hostname or "").lower() != cfg["host"]:
                    add("canonical_foreign", key, "canonical %s" % c)
                else:
                    path = site.internal_path(key, c)
                    final, hops, loop = site.follow(path)
                    if loop or hops or site.to_key(final) is None:
                        add("canonical_target_missing", key, "canonical %s" % c)
        for i, blob in enumerate(p.jsonld):
            try:
                data = json.loads(blob)
            except ValueError:
                add("jsonld_invalid", key, "block %d" % (i + 1))
                continue
            types = ld_types(data, set())
            for t in sorted(types & DEPRECATED_LD):
                add("jsonld_deprecated_type", key, t)
            for t in sorted(types & RESTRICTED_LD):
                add("jsonld_restricted_type", key, t)
        h1 = p.headings.count(1)
        if h1 == 0:
            add("h1_missing", key, "no <h1>")
        elif h1 > 1:
            add("h1_multiple", key, "%d <h1>" % h1)
        for prev, cur in zip(p.headings, p.headings[1:]):
            if cur > prev + 1:
                add("heading_skip", key, "h%d -> h%d" % (prev, cur))
        if p.imgs_no_alt:
            add("img_alt_missing", key, "%d image(s) without alt" % p.imgs_no_alt)
        seen_ids, dups = set(), set()
        for i in p.ids:
            (dups if i in seen_ids else seen_ids).add(i)
        for i in sorted(dups):
            add("duplicate_id", key, "id %s" % i)
        unnamed = sum(1 for b in p.buttons if not b)
        if unnamed:
            add("button_name_missing", key, "%d button(s) without a name" % unnamed)
        bad = sum(1 for cid, own, wrapped in p.controls if not (own or wrapped or (cid and cid in p.label_for)))
        if bad:
            add("control_label_missing", key, "%d control(s) without a label" % bad)
        for link in p.links:
            href = link["href"]
            if not link["name"] and not link["labelled"]:
                add("link_name_missing", key, "href %s" % (href or '""'))
            elif link["name"].lower().strip(" .!:>\u00bb\u2192") in VAGUE:
                add("link_text_vague", key, "\"%s\" -> %s" % (link["name"], href))
            path = site.internal_path(key, href)
            if path is None:
                if href and not href.startswith("#") and urlsplit(href).scheme.lower() in ("http", "https", ""):
                    external += 1
                continue
            target = resolve(key, path, "link")
            frag = urlsplit(href).fragment
            if target is not None:
                if target != key:
                    inbound.setdefault(target, set()).add(key)
                if frag and frag != "top" and target in parsed and unquote(frag) not in parsed[target].ids:
                    add("fragment_missing", key, "%s -> #%s on %s" % (href, frag, target))
        for action in p.forms:
            if action:
                path = site.internal_path(key, action)
                if path is not None:
                    target = resolve(key, path, "form")
                    if target is not None and target != key:
                        inbound.setdefault(target, set()).add(key)
    for group, check in ((titles, "title_duplicate"), (descs, "description_duplicate")):
        for _, keys in sorted(group.items()):
            if len(keys) > 1:
                for k in keys:
                    add(check, k, "shared with %s" % ", ".join(x for x in keys if x != k))
    for key in sorted(parsed):
        if key not in cfg["entry"] and not inbound.get(key):
            add("orphan_page", key, "no internal link from another page")
    for page, spec in sorted(cfg["conversion"].items()):
        pk = site.to_key(page)
        goal_final, _, loop = site.follow(spec["goal"])
        goal = None if loop else site.to_key(goal_final)
        if pk is None:
            add("conversion_page_missing", page, "configured conversion page not in snapshot")
            continue
        if goal is None:
            add("conversion_goal_missing", page, "goal %s" % spec["goal"])
            continue
        if pk not in parsed:
            continue
        p = parsed[pk]
        hrefs = [(l["href"], bool(l["name"] or l["labelled"])) for l in p.links] + [(a, True) for a in p.forms if a]
        ok = False
        for href, named in hrefs:
            path = site.internal_path(pk, href)
            if path is None or not named:
                continue
            final, _, lp = site.follow(path)
            if not lp and site.to_key(final) == goal:
                ok = True
                break
        if not ok:
            add("cta_missing", page, "no named link or form reaching %s" % goal)
    if sitemap is None:
        add("sitemap_missing", "/sitemap.xml", "no sitemap.xml at the snapshot root")
    elif sitemap == "invalid":
        add("sitemap_invalid", "/sitemap.xml", "sitemap.xml does not parse")
    else:
        listed = set()
        for loc in sitemap:
            sp = urlsplit(loc)
            if (sp.hostname or "").lower() != cfg["host"]:
                add("sitemap_foreign_host", "/sitemap.xml", loc or '""')
                continue
            final, hops, loop = site.follow(site.internal_path("/", loc))
            target = None if (loop or hops) else site.to_key(final)
            if target is None:
                add("sitemap_entry_missing", "/sitemap.xml", loc)
                continue
            listed.add(target)
            if target in parsed and parsed[target].noindex:
                add("sitemap_noindex", "/sitemap.xml", loc)
        for key in sorted(parsed):
            if key not in listed and not parsed[key].noindex:
                add("not_in_sitemap", key, "indexable page not in sitemap.xml")
    uniq = {}
    for f in findings:
        uniq.setdefault(f["key"], f)
    findings = sorted(uniq.values(), key=lambda f: (-SEV[f["severity"]], f["page"], f["check"], f["detail"]))
    return parsed, findings, skipped, external


def build_report(root, cfg, max_bytes, baseline):
    parsed, findings, skipped, external = diagnose(root, cfg, max_bytes)
    summary = {s: sum(1 for f in findings if f["severity"] == s) for s in ("high", "medium", "low")}
    areas = {}
    for f in findings:
        areas[f["area"]] = areas.get(f["area"], 0) + 1
    rep = {"tool": TOOL, "version": VERSION, "schema": SCHEMA, "base_url": cfg["base_url"],
           "pages_scanned": len(parsed), "complete": not skipped, "skipped": skipped,
           "summary": {"by_severity": summary, "by_area": dict(sorted(areas.items())), "total": len(findings)},
           "external_links_not_checked": external, "findings": findings, "unrun": UNRUN}
    if baseline is not None:
        now = {f["key"] for f in findings}
        rep["diff"] = {"fixed": sorted(set(baseline) - now), "new": sorted(now - set(baseline)),
                       "persisting": sorted(now & set(baseline))}
    return rep


def render_text(rep):
    lines = ["%s %s: %d pages, %d findings (high %d, medium %d, low %d)%s" % (
        TOOL, VERSION, rep["pages_scanned"], rep["summary"]["total"], rep["summary"]["by_severity"]["high"],
        rep["summary"]["by_severity"]["medium"], rep["summary"]["by_severity"]["low"],
        "" if rep["complete"] else ", INCOMPLETE")]
    for s in rep["skipped"]:
        lines.append("skipped %s: %s" % (s["path"], s["reason"]))
    for f in rep["findings"]:
        lines.append("%s | %s | %s | %s | fix: %s" % (f["severity"], f["check"], f["page"], f["detail"], f["fix"]))
    if "diff" in rep:
        d = rep["diff"]
        lines.append("versus baseline: fixed %d, new %d, persisting %d" % (len(d["fixed"]), len(d["new"]),
                                                                          len(d["persisting"])))
    lines.append("external links not checked: %d" % rep["external_links_not_checked"])
    lines.append("not run: " + rep["unrun"])
    return "\n".join(lines) + "\n"


def write_atomic(path, data):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".g34-", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("site", help="folder holding the saved pages (and optional sitemap.xml)")
    ap.add_argument("--config", required=True, help="JSON: base_url, optional redirects, conversion, entry_pages")
    ap.add_argument("--baseline", help="an earlier JSON report; adds fixed / new / persisting")
    ap.add_argument("--out", help="write the JSON report here (atomically; never inside the snapshot)")
    ap.add_argument("--json", action="store_true", help="print the JSON report instead of text")
    ap.add_argument("--fail-on", choices=("high", "medium", "low", "none"), default="high")
    ap.add_argument("--max-bytes", type=int, default=2000000, help="skip pages larger than this (default 2 MB)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        root = os.path.realpath(args.site)
        if not os.path.isdir(root):
            raise UsageError("site folder %s not found" % args.site)
        if args.max_bytes < 1:
            raise UsageError("--max-bytes must be positive")
        cfg = load_config(args.config)
        baseline = load_baseline(args.baseline) if args.baseline else None
        if args.out:
            out_dir = os.path.realpath(os.path.dirname(os.path.abspath(args.out)))
            if not os.path.isdir(out_dir):
                raise UsageError("--out folder does not exist")
            if within(os.path.join(out_dir, os.path.basename(args.out)), root):
                raise UsageError("--out must not be inside the snapshot")
            if os.path.isdir(args.out):
                raise UsageError("--out is a folder")
        rep = build_report(root, cfg, args.max_bytes, baseline)
        body = json.dumps(rep, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.out:
            try:
                write_atomic(args.out, body)
            except OSError as e:
                raise UsageError("could not write --out (%s)" % e.__class__.__name__)
    except UsageError as e:
        sys.stderr.write("error: %s\n" % e)
        return 2
    sys.stdout.write(body if args.json else render_text(rep))
    if not rep["complete"]:
        return 3
    if args.fail_on != "none" and any(SEV[f["severity"]] >= SEV[args.fail_on] for f in rep["findings"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
