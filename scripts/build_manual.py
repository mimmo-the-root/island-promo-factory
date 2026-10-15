#!/usr/bin/env python3
"""build_manual.py - turns docs/manual/*.md into the HTML manual shipped with Island Promo Factory.

Sources: docs/manual/manual.json (parts and chapter order) and one <slug>.md per chapter.
Output : docs/manual-html/  (index.html, <slug>.html, whatsnew.html, manual.css, screenshots)
         The live console serves it at /manual/ and the update ships it (the folder is under docs/). The same files are what GitHub Pages publishes.
         whatsnew.html is generated from CHANGELOG.md; {{EPIC_TABLE}} in a chapter is replaced by the table made from scripts/epic_specs.json.

No dependencies, no JavaScript, no external fonts or scripts: the pages work offline and from file://.
Markdown subset: # title, ## / ### headings, paragraphs, - lists, 1. steps, > callouts
(first word in bold = Note, Tip, Warning or Checkpoint), | tables, ``` code ```, `code`, **bold**,
*italic*, [text](url), [text](ch:slug#anchor) for a link to another chapter, ![alt](name.png) for a screenshot kept in docs/manual/images/.
Raw HTML in the sources is escaped, never passed through.

    python scripts/build_manual.py            build
    python scripts/build_manual.py --check    exit 1 if the committed output is out of date (also checks links, anchors, no external resources)
"""
import base64, html, json, os, re, shutil, sys, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "docs", "manual")
OUT = os.path.join(ROOT, "docs", "manual-html")
REPO = "https://github.com/mimmo-the-root/island-promo-factory"
PAGES = "https://mimmo-the-root.github.io/island-promo-factory/"
X_URL = "https://x.com/mimmo_the_root"
SLUG_RE = re.compile(r"[a-z0-9-]+")


def esc(t):
    return html.escape(t, quote=True)


def slugify(t):
    s = re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", t).lower()).strip("-")
    return s or "section"


def link_target(url, chapters):
    if url.startswith("ch:"):
        slug, _, frag = url[3:].partition("#")
        if slug not in chapters and slug not in ("index", "whatsnew"):
            raise ValueError("link to unknown chapter: " + url)
        return slug + ".html" + ("#" + frag if frag else ""), False
    if re.match(r"https?://", url):
        return url, True
    if re.match(r"[A-Za-z0-9_./#-]+", url) and not url.lower().startswith(("javascript:", "data:")):
        return url, False
    raise ValueError("bad link: " + url)


def inline(t, chapters):
    parts = re.split(r"(`[^`]+`)", t)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append("<code>" + esc(p[1:-1]) + "</code>")
            continue
        p = esc(p)
        p = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: '<img src="%s" alt="%s" loading="lazy">' % (m.group(2), m.group(1)), p)

        def lk(m):
            href, ext = link_target(html.unescape(m.group(2)), chapters)
            return '<a href="%s"%s>%s</a>' % (esc(href), ' target="_blank" rel="noopener"' if ext else "", m.group(1))
        p = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lk, p)
        p = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"(?<![*\w])\*([^*\s][^*]*)\*(?!\w)", r"<em>\1</em>", p)
        out.append(p)
    return "".join(out)


CALLOUT = {"note": "Note", "tip": "Tip", "warning": "Warning", "checkpoint": "You should see"}


def convert(md, chapters):
    """Returns (title, lede_html, body_html, headings[(level, id, text)])."""
    lines = md.replace("\r\n", "\n").split("\n")
    title, i, blocks, heads, used = "", 0, [], [], set()
    n = len(lines)
    while i < n:
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("```"):
            j = i + 1
            code = []
            while j < n and not lines[j].startswith("```"):
                code.append(lines[j]); j += 1
            blocks.append("<pre><code>" + esc("\n".join(code)) + "</code></pre>")
            i = j + 1
            continue
        m = re.match(r"(#{1,3}) (.+)", ln)
        if m:
            lvl, text = len(m.group(1)), m.group(2).strip()
            if lvl == 1 and not title:
                title = text
            else:
                hid = slugify(text); k = 2
                while hid in used:
                    hid = "%s-%d" % (slugify(text), k); k += 1
                used.add(hid)
                heads.append((lvl, hid, text))
                blocks.append('<h%d id="%s">%s</h%d>' % (lvl, hid, inline(text, chapters), lvl))
            i += 1
            continue
        if ln.startswith("> "):
            q = []
            while i < n and lines[i].startswith(">"):
                q.append(lines[i][1:].strip()); i += 1
            text = " ".join(x for x in q if x)
            mm = re.match(r"\*\*([A-Za-z ]+)\*\*:?\s*(.*)", text)
            kind = mm.group(1).strip().lower() if mm else ""
            if kind in CALLOUT:
                blocks.append('<div class="callout %s"><div class="callout-label">%s</div><p>%s</p></div>' % (kind, CALLOUT[kind], inline(mm.group(2), chapters)))
            else:
                blocks.append('<div class="callout note"><p>%s</p></div>' % inline(text, chapters))
            continue
        if ln.startswith("|"):
            rows = []
            while i < n and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            head, body = rows[0], [r for r in rows[1:] if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            t = "<div class=\"tablewrap\"><table><thead><tr>" + "".join("<th>%s</th>" % inline(c, chapters) for c in head) + "</tr></thead><tbody>"
            t += "".join("<tr>" + "".join("<td>%s</td>" % inline(c, chapters) for c in r) + "</tr>" for r in body) + "</tbody></table></div>"
            blocks.append(t)
            continue
        if re.match(r"\d+\. ", ln):
            items = []
            while i < n and (re.match(r"\d+\. ", lines[i]) or (lines[i].startswith("   ") and items)):
                if re.match(r"\d+\. ", lines[i]):
                    items.append(re.sub(r"^\d+\. ", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            blocks.append('<ol class="steps">' + "".join("<li>%s</li>" % inline(x, chapters) for x in items) + "</ol>")
            continue
        if ln.startswith("- "):
            items = []
            while i < n and (lines[i].startswith("- ") or (lines[i].startswith("  ") and items and lines[i].strip())):
                if lines[i].startswith("- "):
                    items.append(lines[i][2:])
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            blocks.append("<ul>" + "".join("<li>%s</li>" % inline(x, chapters) for x in items) + "</ul>")
            continue
        if ln.strip() == "---":
            blocks.append("<hr>"); i += 1; continue
        para = []
        while i < n and lines[i].strip() and not re.match(r"(#{1,3} |> |\||- |\d+\. |```|---$)", lines[i]):
            para.append(lines[i].strip()); i += 1
        blocks.append("<p>%s</p>" % inline(" ".join(para), chapters))
    lede = ""
    if blocks and blocks[0].startswith("<p>"):
        lede = blocks.pop(0).replace("<p>", '<p class="lede">', 1)
    return title, lede, "\n".join(blocks), heads


def load():
    with open(os.path.join(SRC, "manual.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    order = []
    for part in cfg["parts"]:
        for slug in part["chapters"]:
            if not SLUG_RE.fullmatch(slug) or slug == "index":
                raise ValueError("bad chapter slug: " + slug)
            order.append(slug)
    chapters = {}
    for slug in order:
        with open(os.path.join(SRC, slug + ".md"), encoding="utf-8") as f:
            chapters[slug] = f.read()
    return cfg, order, chapters


def version():
    with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
        return f.read().strip()


def epic_table():
    """Markdown table from scripts/epic_specs.json (the single source of the Epic rules)."""
    with open(os.path.join(ROOT, "scripts", "epic_specs.json"), encoding="utf-8") as f:
        sp = json.load(f)
    im, vd = sp["images"], sp["video"]
    sz = lambda k: "%dx%d" % tuple(im[k]["size"])
    rows = [("Landscape thumbnail", "%s PNG/JPEG, up to %s MB; two versions: art + logo, art only" % (sz("landscape"), im["landscape"]["max_mb"])),
            ("Portrait thumbnail", "%s PNG/JPEG, up to %s MB; two versions: art + logo, art only" % (sz("portrait"), im["portrait"]["max_mb"])),
            ("Logo", "%s transparent PNG" % sz("logo")),
            ("Lobby background", "%s PNG/JPG, up to %s MB (optional)" % (sz("lobby"), im["lobby"]["max_mb"])),
            ("Video", "%d-%d s, MOV ProRes, 16:9, native frame rate, uncompressed stereo audio (the kit renders %dx%d)" % (vd["min_s"], vd["max_s"], vd["width"], vd["height"])),
            ("Safe area", "keep titles %d px away from the top and bottom edges" % im["safe_area_px"])]
    return "| Asset | Rule |\n|---|---|\n" + "\n".join("| %s | %s |" % r for r in rows) + "\n\nVerified on %s; mandatory from %s." % (sp["verified"], sp["mandatory_from"])


def rail(cfg, titles, current, ver):
    def links(cls):
        out = ['<a class="rail-home%s" href="index.html">Manual home</a>' % (" on" if current == "index" else ""),
               '<a class="rail-home%s" href="whatsnew.html">What\'s new</a>' % (" on" if current == "whatsnew" else "")]
        num = 0
        for part in cfg["parts"]:
            out.append('<div class="rail-part">%s</div>' % esc(part["title"]))
            for slug in part["chapters"]:
                num += 1
                out.append('<a class="rail-link%s" href="%s.html"><span class="rail-n">%02d</span>%s</a>' % (" on" if slug == current else "", slug, num, esc(titles[slug])))
        return "\n".join(out)
    brand = '<div class="rail-brand">Island Promo Factory<small>Manual &middot; kit v%s</small></div>' % esc(ver)
    return ('<nav class="rail rail-w" aria-label="Chapters">%s%s</nav>' % (brand, links("w")) +
            '<details class="rail rail-m"><summary>Chapters</summary>%s</details>' % links("m"))


def foot(ver):
    return ('<footer class="foot">Island Promo Factory v%s &middot; <a href="%s" target="_blank" rel="noopener">GitHub repo</a> &middot; '
            '<a href="%s" target="_blank" rel="noopener">Documentation</a> &middot; '
            '<a href="%s/blob/main/LICENSE" target="_blank" rel="noopener">MIT License</a> (free to use, copy and change, no warranty) &middot; '
            'by <a href="%s" target="_blank" rel="noopener">@mimmo_the_root</a> on X<br>Unofficial tool, not affiliated with Epic Games. Fortnite and Unreal Editor for Fortnite are trademarks of Epic Games, Inc. '
            '<a href="whatsnew.html">What\'s new</a></footer>') % (esc(ver), REPO, PAGES, REPO, X_URL)


def page(cfg, titles, current, ver, inner_title, inner):
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s &middot; Island Promo Factory Manual</title><link rel="stylesheet" href="manual.css"></head><body>'
            '<div class="shell">%s<main class="page">%s%s</main></div></body></html>\n') % (esc(inner_title), rail(cfg, titles, current, ver), inner, foot(ver))


def build(out_dir):
    cfg, order, sources = load()
    ver = version()
    conv, titles = {}, {}
    for slug in order:
        t, lede, body, heads = convert(sources[slug].replace("{{EPIC_TABLE}}", epic_table()), set(order))
        if not t:
            raise ValueError(slug + ": the chapter needs a # title")
        conv[slug] = (t, lede, body, heads)
        titles[slug] = t
    os.makedirs(out_dir, exist_ok=True)
    shots = sorted(f for f in os.listdir(os.path.join(SRC, "images"))) if os.path.isdir(os.path.join(SRC, "images")) else []
    for f in shots:
        if not re.fullmatch(r"[a-z0-9-]+\.png", f):
            raise ValueError("images/%s: use lowercase letters, digits and dashes, and .png" % f)
    keep = set(["index.html", "whatsnew.html", "manual.css"] + [slug + ".html" for slug in order] + shots)
    for f in os.listdir(out_dir):  # a chapter that was removed or renamed must not linger; files that stay are simply overwritten below
        if f.endswith((".html", ".css", ".png")) and f not in keep:
            os.remove(os.path.join(out_dir, f))
    # home
    home = ['<div class="crumb">Manual</div><h1>%s</h1><p class="lede">%s</p>' % (esc(cfg.get("title", "Manual")), esc(cfg.get("intro", "")))]
    num = 0
    for part in cfg["parts"]:
        home.append('<h2>%s</h2><div class="toc">' % esc(part["title"]))
        for slug in part["chapters"]:
            num += 1
            home.append('<a class="toc-card" href="%s.html"><span class="toc-n">%02d</span><span class="toc-t">%s</span><span class="toc-s">%s</span></a>' % (slug, num, esc(titles[slug]), esc(cfg.get("summaries", {}).get(slug, ""))))
        home.append("</div>")
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page(cfg, titles, "index", ver, "Home", "\n".join(home)))
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        cl = f.read().replace("\r\n", "\n")
    entries = re.findall(r"^## v?(\d+\.\d+\.\d+)\s*[-\u2014\u2013:]*\s*(.*?)\n(.*?)(?=^## v?\d+\.\d+\.\d+|\Z)", cl, re.S | re.M)
    wn = ['<div class="crumb"><a href="index.html">Manual</a> / What\'s new</div><h1>What\'s new</h1><p class="lede">Every release of Island Promo Factory, newest first. Generated from CHANGELOG.md.</p>']
    for v, title_, bodytxt in entries:
        _, _, b, _ = convert("# x\n\n" + bodytxt.strip(), set(order))
        wn.append('<h2 id="v%s">v%s &middot; %s</h2>%s' % (v.replace(".", "-"), esc(v), esc(title_.strip()), b))
    with open(os.path.join(out_dir, "whatsnew.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page(cfg, titles, "whatsnew", ver, "What's new", "\n".join(wn)))
    for idx, slug in enumerate(order):
        t, lede, body, heads = conv[slug]
        prev_ = order[idx - 1] if idx else None
        next_ = order[idx + 1] if idx + 1 < len(order) else None
        nav = '<nav class="pn">%s%s</nav>' % (
            ('<a class="pn-prev" href="%s.html"><small>Previous</small>%s</a>' % (prev_, esc(titles[prev_]))) if prev_ else "<span></span>",
            ('<a class="pn-next" href="%s.html"><small>Next</small>%s</a>' % (next_, esc(titles[next_]))) if next_ else "<span></span>")
        inner = '<div class="crumb"><a href="index.html">Manual</a> / Chapter %02d</div><div class="chapter-num">%02d</div><h1>%s</h1>%s\n%s\n%s' % (idx + 1, idx + 1, inline(t, set(order)), lede, body, nav)
        with open(os.path.join(out_dir, slug + ".html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(page(cfg, titles, slug, ver, t, inner))
    shutil.copyfile(os.path.join(SRC, "manual.css"), os.path.join(out_dir, "manual.css"))
    for f in shots:
        shutil.copyfile(os.path.join(SRC, "images", f), os.path.join(out_dir, f))
    return order


def tree(d):
    return {f: open(os.path.join(d, f), "rb").read() for f in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d, f))} if os.path.isdir(d) else {}


def lint(d):
    """Problems in a built manual: broken local links/anchors, external resources (src/href to http) other than clickable links, missing version."""
    bad, ids, pages = [], {}, [f for f in os.listdir(d) if f.endswith(".html")]
    for f in pages:
        t = open(os.path.join(d, f), encoding="utf-8").read()
        ids[f] = set(re.findall(r'id="([^"]+)"', t))
        if re.search(r'<(?:script|img|link|iframe)[^>]+(?:src|href)="https?://', t):
            bad.append("%s: external resource" % f)
        if "<script" in t:
            bad.append("%s: script" % f)
        if not re.search(r"Island Promo Factory v\d+\.\d+\.\d+", t):
            bad.append("%s: version missing in the footer" % f)
    for f in pages:
        t = open(os.path.join(d, f), encoding="utf-8").read()
        for href in re.findall(r'<a [^>]*href="([^"]+)"', t):
            if re.match(r"https?://", href):
                continue
            page_, _, frag = href.partition("#")
            if page_ and not os.path.exists(os.path.join(d, page_)):
                bad.append("%s: broken link %s" % (f, href))
            elif frag and frag not in ids.get(page_ or f, set()):
                bad.append("%s: broken anchor %s" % (f, href))
        for src_ in re.findall(r'<img [^>]*src="([^"]+)"', t):
            if not os.path.exists(os.path.join(d, src_)):
                bad.append("%s: missing image %s" % (f, src_))
    return bad


def main():
    if "--check" in sys.argv:
        tmp = tempfile.mkdtemp()
        try:
            build(tmp)
            same = tree(tmp) == tree(OUT)
            bad = lint(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        for b in bad:
            print("PROBLEM " + b)
        print("manual is up to date" if same else "manual is OUT OF DATE: run python scripts/build_manual.py")
        return 0 if same and not bad else 1
    order = build(OUT)
    print("manual built: %d chapters -> %s" % (len(order), os.path.relpath(OUT, ROOT)))
    bad = lint(OUT)
    for b in bad:
        print("PROBLEM " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
