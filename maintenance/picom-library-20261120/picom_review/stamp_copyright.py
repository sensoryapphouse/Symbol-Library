#!/usr/bin/env python3
"""Insert an INVISIBLE copyright into our own symbol SVGs (Sensory App House / PiCom).

Recommended combo (all invisible, do not render):
  - a root attribute   <svg ... data-copyright="...">
  - a marker comment   <!--SAH-COPYRIGHT ...-->
  - a <metadata> RDF block (Dublin Core + Creative Commons) holding the rights line.

Idempotent (skips already-stamped files). REVERSIBLE:
  python3 stamp_copyright.py undo            # remove from all TARGETS
  python3 stamp_copyright.py insert /tmp/x   # operate on one folder (testing)

Stamps ONLY our own work. Excludes third-party / PD-sourced material:
  - Fleximbols: skips American Sign Language (PD chart) + British Sign Language (licensed 3rd-party chart) + Flags (external).
  - Mulberry: only the symbols WE created (filenames absent from the original Mulberry set); original/derivative Mulberry art left alone.
"""
import re, os, sys, glob
import det_meta as _M               # build the compact <metadata id="sah"> figure index alongside the copyright

TEXT  = "© 2026 Sensory App House. All rights reserved."
OWNER = "Sensory App House (PiCom)"
MARK  = "SAH-COPYRIGHT"
COMMENT = f"<!--{MARK} {TEXT}-->"
META = ('<metadata id="sah-copyright"><rdf:RDF '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:cc="http://creativecommons.org/ns#"><cc:Work rdf:about="">'
        f'<dc:rights><cc:Agent><dc:title>{TEXT}</dc:title></cc:Agent></dc:rights>'
        f'<dc:creator><cc:Agent><dc:title>{OWNER}</dc:title></cc:Agent></dc:creator>'
        '<dc:date>2026</dc:date></cc:Work></rdf:RDF></metadata>')
ATTR = ' data-copyright="© 2026 Sensory App House"'
SVGTAG = re.compile(r'<svg\b[^>]*?>', re.I | re.S)

def stamp(t):
    if MARK in t: return None
    m = SVGTAG.search(t)
    if not m: return None
    newtag = m.group(0)[:-1] + ATTR + '>'
    out = t[:m.start()] + newtag + COMMENT + META + t[m.end():]
    if t[m.end():] not in out or len(out) <= len(t): return None   # sanity
    return out

def unstamp(t):
    if MARK not in t: return None
    return t.replace(ATTR, '', 1).replace(COMMENT, '', 1).replace(META, '', 1)

def process(files, undo=False):
    done = skip = err = 0
    for f in files:
        try:
            t = open(f, encoding='utf-8', errors='surrogateescape').read()
            if undo:
                o = unstamp(t)
            else:
                o = stamp(t) or t                       # copyright (or keep as-is if already stamped)
                o = _M.meta_ize(o)                       # + build the <metadata id="sah"> index from data-fig head tags
            if o is None or o == t:
                skip += 1; continue
            open(f, 'w', encoding='utf-8', errors='surrogateescape').write(o); done += 1
        except Exception:
            err += 1
    return done, skip, err

def collect(root, exclude=frozenset()):
    out = []
    for f in glob.glob(root + "/**/*.svg", recursive=True):
        if any(seg in exclude for seg in os.path.relpath(f, root).split(os.sep)):
            continue
        out.append(f)
    return out

def mulberry_ours():
    ORIG = "/Users/paulblenkhorn/Downloads/mulberry-symbols"   # authoritative original Mulberry set
    WORK = "/Users/paulblenkhorn/Desktop/AAC_Simple_Symbols"
    orig = {os.path.basename(f).lower() for f in glob.glob(ORIG + "/**/*.svg", recursive=True)}
    return [f for f in glob.glob(WORK + "/**/*.svg", recursive=True)
            if os.path.basename(f).lower() not in orig]

TARGETS = {
    "Fleximbols":   lambda: collect("/Users/paulblenkhorn/Desktop/Fleximbols",
                                       exclude={"American Sign Language", "British Sign Language", "Flags"}),
    "PiCom Cartoon":   lambda: collect("/Users/paulblenkhorn/Desktop/PiCom Cartoon SVG"),
    "PiCom Cute":      lambda: collect("/Users/paulblenkhorn/Desktop/PiCom Cute SVG"),
    "PiCom Classic":   lambda: collect("/Users/paulblenkhorn/Desktop/PiCom_Classic SVG"),
    "PiCom Anime":     lambda: collect("/Users/paulblenkhorn/Desktop/PiCom Anime SVG"),
    "3D Symbols":      lambda: collect("/Users/paulblenkhorn/Desktop/3D Symbols"),
    "Mulberry (ours)": mulberry_ours,
}

if __name__ == "__main__":
    args = sys.argv[1:]
    undo = "undo" in args
    paths = [a for a in args if a not in ("insert", "undo")]
    if paths:  # test/one-folder mode
        files = glob.glob(paths[0] + "/**/*.svg", recursive=True)
        print(process(files, undo)); sys.exit()
    grand = 0
    for name, fn in TARGETS.items():
        files = fn()
        d, s, e = process(files, undo)
        grand += d
        print(f"{name:18}: {'removed' if undo else 'stamped'} {d:6}  skipped {s:6}  err {e}  (of {len(files)})")
    print("TOTAL", "removed" if undo else "stamped", ":", grand)
