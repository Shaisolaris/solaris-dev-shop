#!/usr/bin/env python3
"""Write the G34 synthetic fixtures (deterministic; no network; fictional sites on .example hosts).

clean/   a small site with no defects (the clean control: expected findings = none)
before/  a product site with seeded defects; every defect declares the finding key it must produce
after/   the same site with every seeded defect corrected (expected = none; versus before = all fixed)
unseen/  a different site built from traps: tricky correct markup that must NOT be flagged, plus defects the
         before/ site does not contain (case-only mismatch, redirect loop, non-UTF-8 bytes, malformed HTML, ...)

Each folder holds site/ (the pages), config.json and expected.json (the declared finding keys, sorted).
Run: python3 make_fixtures.py [OUTDIR]   (default: the fixtures/ folder next to this file)
"""
import html
import json
import os
import shutil
import sys

DESC_PAD = ("Built for small teams that plan in the open and keep every decision written down where "
            "everyone can find it later today, with owners, dates and the reasons behind each choice kept close "
            "at hand for the next meeting").split()
TITLE_PAD = "| Lantern Notes for calm small teams everywhere".split()


def fit(core, pad, lo, hi):
    """Append pad words to core until its length is within [lo, hi]; fail loudly if that is impossible."""
    s = core
    for w in pad:
        if lo <= len(html.unescape(s)) <= hi:
            return s
        s = s + " " + w
    if lo <= len(html.unescape(s)) <= hi:
        return s
    raise SystemExit("cannot fit %r into %d-%d characters" % (core, lo, hi))


def page(title, desc, h1, body, canonical, lang="en", viewport=True, head_extra="", raw_title=None):
    head = ['<meta charset="utf-8">']
    if viewport:
        head.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    if raw_title is not None:
        head.append(raw_title)
    elif title is not None:
        head.append("<title>%s</title>" % title)
    if desc is not None:
        head.append('<meta name="description" content="%s">' % desc)
    if canonical is not None:
        head.append('<link rel="canonical" href="%s">' % canonical)
    head.append(head_extra)
    lang_attr = ' lang="%s"' % lang if lang else ""
    h1_html = "<h1>%s</h1>\n" % h1 if h1 else ""
    return ("<!doctype html>\n<html%s>\n<head>\n%s\n</head>\n<body>\n<header><nav>%s</nav></header>\n<main>\n%s%s\n"
            "</main>\n</body>\n</html>\n") % (lang_attr, "\n".join(x for x in head if x), "{NAV}", h1_html, body)


def write_site(base, files, config, expected, sitemap):
    if os.path.exists(base):
        shutil.rmtree(base)
    site = os.path.join(base, "site")
    for rel, data in sorted(files.items()):
        path = os.path.join(site, *rel.strip("/").split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    if sitemap is not None:
        with open(os.path.join(site, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s</urlset>\n'
                    % "".join("  <url><loc>%s</loc></url>\n" % u for u in sitemap))
    with open(os.path.join(base, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")
    with open(os.path.join(base, "expected.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(set(expected)), f, indent=1, ensure_ascii=False)
        f.write("\n")


# ----------------------------------------------------------------------------------------------------- lantern
LBASE = "https://lantern.example"
LNAV = ('<a href="/">Home</a> <a href="/features.html">Features</a> <a href="/pricing.html">Pricing</a> '
        '<a href="/blog/">Blog</a> <a href="/about.html">About</a> <a href="/contact.html">Contact</a>')
LPAGES = {
    "/index.html": ("Lantern Notes, the shared team notebook", "Lantern Notes keeps meeting notes, decisions and "
                    "owners in one shared notebook.", "A shared notebook for team decisions"),
    "/features.html": ("Features of Lantern Notes", "See how Lantern Notes links decisions to owners, due dates "
                       "and the meeting where they were made.", "Features"),
    "/pricing.html": ("Lantern Notes pricing for teams", "Lantern Notes pricing: a free plan for small teams and "
                      "one paid plan with history and exports.", "Pricing"),
    "/signup.html": ("Create your Lantern Notes account", "Create a Lantern Notes account in a minute; no card "
                     "is needed for the free plan.", "Create your account"),
    "/about.html": ("About the Lantern Notes team", "Who builds Lantern Notes, why we started, and how we decide "
                    "what to build next.", "About us"),
    "/contact.html": ("Contact the Lantern Notes team", "Ask the Lantern Notes team a question about plans, "
                      "privacy or getting started.", "Contact"),
    "/blog/index.html": ("The Lantern Notes blog on team writing", "Short essays on writing decisions down, "
                         "running calmer meetings and keeping owners clear.", "Blog"),
    "/blog/decision-logs.html": ("Why every team needs a decision log", "A decision log answers who decided, "
                                 "when and why, so nobody has to ask twice in the next meeting.",
                                 "Why every team needs a decision log"),
    "/thanks.html": ("Thanks for writing to Lantern Notes", "Thanks for your message; the Lantern Notes team "
                     "replies within two working days.", "Thanks"),
}


def lantern(defects):
    """defects=False builds after/ (and is the corrected reference); True builds before/ with declared keys."""
    exp = []
    files = {}
    D = defects

    def meta(key):
        t, d, h = LPAGES[key]
        return fit(t, TITLE_PAD, 50, 60), fit(d, DESC_PAD, 150, 160), h

    bodies = {
        "/index.html": ('<p>Write it down once. <a href="/features.html">See what Lantern Notes does</a> or '
                        '<a href="/pricing.html">compare plans</a>.</p>\n<h2>Built for decisions</h2>\n'
                        '<p><img src="/img/notebook.png" alt="A notebook page listing three decisions"></p>\n'
                        '<p><a href="/blog/decision-logs.html">Read why decision logs matter</a></p>'),
        "/features.html": ('<h2>Owners</h2><p>Every decision names one owner.</p>\n<h3>Due dates</h3><p>Dates sit '
                           'next to the decision.</p>\n<h2>History</h2><p><a href="/pricing.html#history">History '
                           'is in the paid plan</a>.</p>'),
        "/pricing.html": ('<h2>Free</h2><p>Up to five people.</p>\n<h2 id="history">Team</h2><p>History and '
                          'exports.</p>\n<p><a class="cta" href="/signup.html">Start free with Lantern Notes</a></p>'),
        "/signup.html": ('<form action="/thanks.html" method="post">\n<label for="email">Work email</label>\n'
                         '<input id="email" name="email" type="email">\n<input type="hidden" name="plan" '
                         'value="free">\n<button type="submit">Create account</button>\n</form>'),
        "/about.html": '<h2>Why we started</h2><p>Too many meetings ended without an owner.</p>',
        "/contact.html": ('<form action="/thanks.html" method="post">\n<label>Your email <input name="email" '
                          'type="email"></label>\n<label for="msg">Message</label>\n<textarea id="msg" name="msg">'
                          '</textarea>\n<button type="submit">Send message</button>\n</form>'),
        "/blog/index.html": ('<h2>Latest</h2><p><a href="decision-logs.html">Why every team needs a decision '
                             'log</a></p>'),
        "/blog/decision-logs.html": ('<p>A decision log is a list of decisions with an owner and a date.</p>\n'
                                     '<h2>What to record</h2><p>Who, what, when, why.</p>\n'
                                     '<script type="application/ld+json">{"@context": "https://schema.org", '
                                     '"@type": "Article", "headline": "Why every team needs a decision log", '
                                     '"author": {"@type": "Person", "name": "Ada Example"}}</script>'),
        "/thanks.html": '<p>We will reply within two working days. <a href="/blog/">Read the blog</a>.</p>',
    }
    noindex = {"/thanks.html"}
    for key in LPAGES:
        title, desc, h1 = meta(key)
        canon = LBASE + ("/" if key == "/index.html" else key.replace("/index.html", "/"))
        extra = '<meta name="robots" content="noindex">' if key in noindex else ""
        files[key] = page(title, desc, h1, bodies[key], None if key in noindex else canon, head_extra=extra)
    sitemap = [LBASE + "/", LBASE + "/features.html", LBASE + "/pricing.html", LBASE + "/signup.html",
               LBASE + "/about.html", LBASE + "/contact.html", LBASE + "/blog/", LBASE + "/blog/decision-logs.html"]
    redirects = {}
    if D:
        def sub(key, old, new, *keys):
            assert files[key].count(old) == 1, (key, old)
            files[key] = files[key].replace(old, new)
            exp.extend(keys)
        t, d, _ = meta("/index.html")
        sub("/index.html", "<title>%s</title>" % t, "<title>Home</title>", "title_length|/index.html|4 characters")
        sub("/index.html", ' alt="A notebook page listing three decisions"', "",
            "img_alt_missing|/index.html|1 image(s) without alt")
        sub("/index.html", '<a href="/blog/decision-logs.html">Read why decision logs matter</a>',
            '<a href="/blog/decision-logs.html">Read more</a> <a href="/blog/decison-logs.html">Older post</a>',
            '"link_text_vague|/index.html|\\"Read more\\" -> /blog/decision-logs.html"'[1:-1].replace('\\"', '"'),
            "broken_link|/index.html|link /blog/decison-logs.html")
        t, d, _ = meta("/features.html")
        sub("/features.html", '<meta name="description" content="%s">' % d, "",
            "description_missing|/features.html|no non-empty meta description")
        sub("/features.html", "<h3>Due dates</h3>", "<h4>Due dates</h4>", "heading_skip|/features.html|h2 -> h4")
        sub("/features.html", "/pricing.html#history", "/pricing.html#histroy",
            "fragment_missing|/features.html|/pricing.html#histroy -> #histroy on /pricing.html")
        sub("/pricing.html", '<a class="cta" href="/signup.html">Start free with Lantern Notes</a>',
            '<a class="cta" href="/start"><svg viewBox="0 0 8 8"></svg></a>',
            "link_name_missing|/pricing.html|href /start", "redirected_link|/pricing.html|link /start -> /signup.html",
            "cta_missing|/pricing.html|no named link or form reaching /signup.html")
        redirects["/start"] = "/signup.html"
        sub("/pricing.html", '<link rel="canonical" href="%s/pricing.html">' % LBASE,
            '<link rel="canonical" href="/pricing.html">', "canonical_relative|/pricing.html|canonical /pricing.html")
        sub("/signup.html", '<label for="email">Work email</label>\n', "",
            "control_label_missing|/signup.html|1 control(s) without a label")
        sub("/signup.html", '<form action="/thanks.html"', '<form action="/thank-you.html"',
            "form_action_broken|/signup.html|form /thank-you.html")
        sub("/signup.html", '<button type="submit">Create account</button>',
            '<button type="submit"><span class="icon"></span></button>',
            "button_name_missing|/signup.html|1 button(s) without a name")
        t, d, _ = meta("/about.html")
        sub("/about.html", ' lang="en"', "", "html_lang_missing|/about.html|<html> has no lang")
        sub("/about.html", '<meta name="viewport" content="width=device-width, initial-scale=1">\n', "",
            "viewport_missing|/about.html|no viewport meta")
        sub("/about.html", "<h2>Why we started</h2>", "<h1>Why we started</h1>", "h1_multiple|/about.html|2 <h1>")
        tc, dc, _ = meta("/contact.html")
        sub("/contact.html", "<title>%s</title>" % tc, "<title>%s</title>" % meta("/about.html")[0],
            "title_duplicate|/contact.html|shared with /about.html",
            "title_duplicate|/about.html|shared with /contact.html")
        sub("/contact.html", '<label for="msg">Message</label>', '<label for="message">Message</label>',
            "control_label_missing|/contact.html|1 control(s) without a label")
        sub("/blog/decision-logs.html", '"@type": "Article"', '"@type": "HowTo"',
            "jsonld_deprecated_type|/blog/decision-logs.html|HowTo")
        sub("/blog/decision-logs.html", "</script>",
            '</script>\n<script type="application/ld+json">{"@type": "Person", "name": "Ada",}</script>',
            "jsonld_invalid|/blog/decision-logs.html|block 2")
        sub("/blog/decision-logs.html", '<h1>Why every team needs a decision log</h1>\n', "",
            "h1_missing|/blog/decision-logs.html|no <h1>")
        sub("/blog/index.html", '<p><a href="decision-logs.html">', '<p id="latest"><a id="latest" '
            'href="decision-logs.html">', "duplicate_id|/blog/index.html|id latest")
        # a stale campaign page nobody links to, still listed in the sitemap, with a long title
        ot = fit("Lantern Notes spring offer", TITLE_PAD, 50, 60) + " - limited time only, ends soon"
        files["/spring-offer.html"] = page(ot, fit("The spring offer for Lantern Notes has ended; see pricing "
                                                   "for current plans.", DESC_PAD, 150, 160), "Spring offer",
                                           '<p>This offer has ended. <a href="/pricing.html">See pricing</a>.</p>',
                                           LBASE + "/spring-offer.html")
        exp += ["title_length|/spring-offer.html|%d characters" % len(ot),
                "orphan_page|/spring-offer.html|no internal link from another page"]
        sitemap = sitemap + [LBASE + "/spring-offer.html", LBASE + "/thanks.html", LBASE + "/careers.html"]
        exp += ["sitemap_noindex|/sitemap.xml|%s/thanks.html" % LBASE,
                "sitemap_entry_missing|/sitemap.xml|%s/careers.html" % LBASE]
        sitemap.remove(LBASE + "/about.html")
        exp.append("not_in_sitemap|/about.html|indexable page not in sitemap.xml")
    for key in files:
        files[key] = files[key].replace("{NAV}", LNAV)
    config = {"base_url": LBASE, "redirects": redirects, "conversion": {"/pricing.html": {"goal": "/signup.html"}},
              "entry_pages": ["/index.html"]}
    return files, config, exp, sitemap


# ----------------------------------------------------------------------------------------------------- harbor
def harbor():
    base = "https://harbor.example"
    nav = '<a href="/">Home</a> <a href="/guide/">Reading guide</a> <a href="/visit.html">Visit</a>'
    pages = {
        "/index.html": ("Quiet Harbor Library, a reading room by the sea", "Quiet Harbor Library is a small "
                        "reading room open to everyone", "Quiet Harbor Library",
                        '<p><a href="/guide/">Find a book with the reading guide</a>.</p>'),
        "/guide/index.html": ("Reading guide for the Quiet Harbor Library", "How the shelves at Quiet Harbor "
                              "Library are arranged and how to ask for help", "Reading guide",
                              '<h2>Shelves</h2><p>Fiction is upstairs. <a href="/visit.html#hours">Check opening '
                              'hours</a>.</p>'),
        "/visit.html": ("Visit the Quiet Harbor Library reading room", "Opening hours, the address and step-free "
                        "access for the Quiet Harbor Library reading room", "Visit",
                        '<h2 id="hours">Opening hours</h2><p>Daily, nine to five.</p>\n<p><a href="/guide/">'
                        'Back to the reading guide</a></p>'),
    }
    pad_t = "| a calm room for slow reading".split()
    pad_d = ("for neighbours, visitors and students who want a quiet seat and a good book near the water every "
             "single day").split()
    files = {}
    for key, (t, d, h, body) in pages.items():
        canon = base + ("/" if key == "/index.html" else key.replace("/index.html", "/"))
        files[key] = page(fit(t, pad_t, 50, 60), fit(d, pad_d, 150, 160), h, body, canon).replace("{NAV}", nav)
    return files, {"base_url": base}, [], [base + "/", base + "/guide/", base + "/visit.html"]


# ----------------------------------------------------------------------------------------------------- unseen
def unseen():
    base = "https://tidewater.example"
    pad_t = "| Tidewater Tools for careful field crews".split()
    pad_d = ("for field crews: notes on tide tables, safety checks and the gear a small crew needs before the "
             "water turns again this season, written plainly by people who work on the shore every day").split()
    T = lambda s: fit(s, pad_t, 50, 60)
    Dd = lambda s: fit(s, pad_d, 150, 160)
    nav = ('<a href="/">Home</a> <a href="/Guides/">Guides</a> <a href="/shop.html">Shop</a> '
           '<a href="/caf%C3%A9.html">Caf\u00e9</a> <a href="/docs">Docs</a>')
    exp = []
    files = {}
    # traps that must not be flagged: decorative alt, image-only link named by alt, aria-labelledby button,
    # wrapped label, hidden input, #top, /docs -> docs/index.html, mailto/tel/javascript, external links,
    # upper-case tags with unquoted attributes, <a name> anchors, entity-decoded title, percent-encoded file name
    files["/index.html"] = page(T("Tidewater Tools &amp; tide tables"), Dd("Tide tables &amp; checklists"),
                                "Tidewater Tools",
                                '<P><IMG SRC=/img/wave.svg ALT=""><A HREF=/shop.html#kits><IMG SRC=/k.png '
                                'ALT="Shop field kits"></A></P>\n<p><a href="mailto:crew@tidewater.example">Email '
                                'the crew</a> <a href="tel:+10000000000">Call the crew</a> <a href="javascript:void(0)'
                                '">Open the tide widget</a> <a href="https://other.example/tides">Regional tide '
                                'service</a> <a href="#top">Back to top</a></p>\n'
                                '<span id="lbl">Search tides</span><button aria-labelledby="lbl"><svg></svg></button>'
                                '\n<p><a href="/docs/#safety">Safety checks</a> <a href="/blog/old-post.html">2019 '
                                'tide notes</a> <a href="/promo/">Spring promotion</a> <a href="/guides/knots.html">'
                                'Knot guide</a></p>',
                                base + "/")
    exp += ["redirect_chain|/index.html|link /blog/old-post.html -> /blog/tides-2019.html (2 hops)",
            "redirect_loop|/index.html|link /promo/",
            "broken_link|/index.html|link /guides/knots.html (differs only in case from /Guides/knots.html)"]
    files["/Guides/index.html"] = page(T("Field guides for tide crews"), Dd("Guides for reading tides"),
                                       "Field guides", '<p><a href="knots.html">Knots every crew should know</a>'
                                       '</p>', base + "/Guides/")
    files["/Guides/knots.html"] = page(T("Knots every tide crew should know"), Dd("Five knots for mooring lines"),
                                       "Knots", '<h2><a name="bowline"></a>Bowline</h2><p>The first knot.</p>\n'
                                       '<p><a href="/Guides/knots.html#bowline">Link to the bowline</a></p>',
                                       base + "/Guides/knots.html")
    files["/docs/index.html"] = page(T("Tidewater safety documentation"), Dd("Safety checks before launch"),
                                     "Documentation", '<h2 id="safety">Safety checks</h2><p>Check the tide.</p>',
                                     base + "/docs/")
    files["/blog/tides-2019.html"] = page(T("Tide notes from 2019"), Dd("Archived tide notes from 2019"),
                                          "Tide notes 2019", '<p><a href="/">Home</a></p>', base + "/blog/tides-2019.html")
    files["/caf\u00e9.html"] = page(T("The Tidewater crew caf\u00e9"), Dd("Coffee and tide tables at the dock"),
                                    "Caf\u00e9", "<p>Open at dawn.</p>", base + "/caf%C3%A9.html")
    # shop: CTA goal reached only through one redirect (allowed, but reported Low); a canonical with a query
    # string on this host (allowed); two canonicals on the kits page (defect); malformed, unclosed markup
    files["/shop.html"] = page(T("The Tidewater field kit shop"), Dd("Field kits for small crews"), "Shop",
                               '<h2 id="kits">Kits</h2>\n<p><a class=cta href=/buy>Buy the crew kit</a></p>\n'
                               '<p><a href="/kits.html">Compare kits</p>\n<div><span>unclosed',
                               base + "/shop.html?ref=nav")
    exp += ["redirected_link|/shop.html|link /buy -> /checkout.html"]
    files["/kits.html"] = page(T("Compare Tidewater field kits"), Dd("Compare the three field kits"), "Kits",
                               '<p><a href="/shop.html">Back to the shop</a></p>', base + "/kits.html",
                               head_extra='<link rel="canonical" href="%s/kits">' % base)
    exp += ["canonical_multiple|/kits.html|2 canonical links"]
    files["/checkout.html"] = page(T("Tidewater checkout"), Dd("Pay for your field kit"), "Checkout",
                                   '<form action="/order/submit.html"><label>Name <input name=n></label>'
                                   '<input type="submit" value="Pay"></form>', base + "/checkout.html")
    exp += ["form_action_broken|/checkout.html|form /order/submit.html"]
    # non-UTF-8 page (Latin-1 bytes) and a page whose canonical points at another site
    legacy = page(T("Legacy tide table"), Dd("The old tide table page"), "Legacy tide table",
                  '<p>Tide at 6 \u00b0C water. <a href="/legacy.html">Permanent address of this table</a></p>',
                  "https://mirror.example/legacy.html")
    files["/legacy.html"] = legacy.replace("{NAV}", nav).encode("latin-1")
    exp += ["encoding_not_utf8|/legacy.html|bytes are not valid UTF-8",
            "canonical_foreign|/legacy.html|canonical https://mirror.example/legacy.html",
            "orphan_page|/legacy.html|no internal link from another page",
            "not_in_sitemap|/legacy.html|indexable page not in sitemap.xml"]
    # noindex draft: no canonical needed, not in sitemap, and its title may repeat an indexable page's (all
    # fine); FAQPage nested in @graph (restricted, Low). legacy.html above links to itself and is still an orphan.
    files["/draft.html"] = page(T("Tidewater checkout"), Dd("A draft of the tide FAQ"), "Draft FAQ",
                                '<script type="application/ld+json">{"@context": "https://schema.org", "@graph": '
                                '[{"@type": "WebPage"}, {"@type": ["Thing", "FAQPage"]}]}</script>'
                                '<p><a href="/">Home</a></p>', None,
                                head_extra='<meta name="robots" content="noindex, follow">')
    exp += ["jsonld_restricted_type|/draft.html|FAQPage",
            "orphan_page|/draft.html|no internal link from another page"]
    for k in list(files):
        if isinstance(files[k], str):
            files[k] = files[k].replace("{NAV}", nav)
    redirects = {"/blog/old-post.html": "/blog/2019/old-post.html", "/blog/2019/old-post.html": "/blog/tides-2019.html",
                 "/promo/": "/promo/spring/", "/promo/spring/": "/promo/", "/buy": "/checkout.html"}
    sitemap = [base + "/", base + "/Guides/", base + "/Guides/knots.html", base + "/docs/",
               base + "/blog/tides-2019.html", base + "/caf%C3%A9.html", base + "/shop.html", base + "/kits.html",
               base + "/checkout.html", "https://other.example/tides.html"]
    exp += ["sitemap_foreign_host|/sitemap.xml|https://other.example/tides.html"]
    config = {"base_url": base, "redirects": redirects, "conversion": {"/shop.html": {"goal": "/checkout.html"},
                                                                       "/old-shop.html": {"goal": "/checkout.html"}}}
    exp += ["conversion_page_missing|/old-shop.html|configured conversion page not in snapshot"]
    return files, config, exp, sitemap


def main(argv):
    out = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
    os.makedirs(out, exist_ok=True)
    f, c, e, s = harbor()
    write_site(os.path.join(out, "clean"), f, c, e, s)
    f, c, e, s = lantern(False)
    write_site(os.path.join(out, "after"), f, c, e, s)
    f, c, e, s = lantern(True)
    write_site(os.path.join(out, "before"), f, c, e, s)
    f, c, e, s = unseen()
    write_site(os.path.join(out, "unseen"), f, c, e, s)
    print("wrote clean, before, after, unseen under %s" % out)


if __name__ == "__main__":
    main(sys.argv)
