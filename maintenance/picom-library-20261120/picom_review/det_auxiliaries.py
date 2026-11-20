#!/usr/bin/env python3
"""det_auxiliaries — be/have/do auxiliary verbs as a consistent SCHEMATIC family
(task #270), grounded in the library's existing conventions and Paul's 2026-07-21
decisions (have = open hand + green tick; am/is/are/be share one "=").

Cores:
  be / am / is / are = bold green "=" (state of being)   [from Core Words/is.svg]
  do / does          = red action arrow (perform)        [from Modals/do.svg]
  have / has         = open hand + green tick (possess/got)

Tense badges (bottom-right corner, uniform size):
  past       = clock + red anticlockwise rewind ring      (was, were, did, had)
  progressive= green circular loop arrow (ongoing = -ing)  (being, doing, having)
  perfect    = clock + green tick (completed-in-past)      (been, done)

Schematic (no figure) -> propagates to the pilots via the qword_pilots pipeline
(identity / soft3d / linify).

Usage: det_auxiliaries.py OUTDIR
"""
import os, sys, math

_CR = ('<!--SAH-COPYRIGHT © 2026 Sensory App House. All rights reserved.-->'
       '<metadata id="sah-copyright"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
       'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:cc="http://creativecommons.org/ns#">'
       '<cc:Work rdf:about=""><dc:rights><cc:Agent><dc:title>© 2026 Sensory App House. All rights reserved.'
       '</dc:title></cc:Agent></dc:rights><dc:creator><cc:Agent><dc:title>Sensory App House (PiCom)</dc:title>'
       '</cc:Agent></dc:creator><dc:date>2026</dc:date></cc:Work></rdf:RDF></metadata>')
HdG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
       'data-copyright="© 2026 Sensory App House">' + _CR +
       '<g data-fit="1" transform="translate(256 256) scale(1.0) translate(-256 -256)">')
FT = "</g></svg>"
INK = "#1a1a1a"; GRN = "#3fae5a"; TICK = "#2f9e4a"; RED = "#e0473c"; BLU = "#4a90d9"; SKIN = "#f5d6b0"

# ---------------- cores ----------------
def be_eq():
    return ['<rect x="96" y="206" width="320" height="42" rx="16" fill="%s" stroke="%s" stroke-width="7"/>' % (GRN, INK),
            '<rect x="96" y="286" width="320" height="42" rx="16" fill="%s" stroke="%s" stroke-width="7"/>' % (GRN, INK)]

def do_arrow():
    return ['<path d="M 96 232 L 300 232 L 300 202 L 404 256 L 300 310 L 300 280 L 96 280 Z" '
            'fill="%s" stroke="%s" stroke-width="7" stroke-linejoin="round"/>' % (RED, INK)]

def have_hand():
    fingers = [(196,176,30,92),(232,164,30,104),(268,168,30,100),(304,182,30,86)]
    out = ['<rect x="180" y="248" width="164" height="92" rx="30" fill="%s" stroke="%s" stroke-width="7"/>' % (SKIN, INK)]
    for x,y,w,h in fingers:
        out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="15" fill="%s" stroke="%s" stroke-width="7"/>' % (x,y,w,h,SKIN,INK))
    out.append('<g transform="rotate(-38 172 300)"><rect x="150" y="262" width="30" height="86" rx="15" fill="%s" stroke="%s" stroke-width="7"/></g>' % (SKIN, INK))
    # green tick sitting on the palm (duo like the `which` tick)
    out.append('<polyline points="222,300 250,332 312,268" fill="none" stroke="%s" stroke-width="20" stroke-linecap="round" stroke-linejoin="round"/>' % INK)
    out.append('<polyline points="222,300 250,332 312,268" fill="none" stroke="%s" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>' % TICK)
    return out

# ---------------- tense badges ----------------
_CX, _CY, _R = 400, 402, 60
def _clock(hands=True):
    o = ['<circle cx="%d" cy="%d" r="%d" fill="#fff" stroke="%s" stroke-width="7"/>' % (_CX,_CY,_R,INK)]
    if hands:
        o += ['<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="8" stroke-linecap="round"/>' % (_CX,_CY,_CX,_CY-38,INK),
              '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="8" stroke-linecap="round"/>' % (_CX,_CY,_CX+26,_CY+10,INK)]
    return o

def past_badge():
    return _clock() + [
        '<path d="M %d %d A 46 46 0 1 1 %d %d" fill="none" stroke="%s" stroke-width="8"/>' % (_CX-1,_CY-46,_CX-46,_CY+6,RED),
        '<polygon points="%d,%d %d,%d %d,%d" fill="%s" stroke="%s" stroke-width="2" stroke-linejoin="round"/>'
        % (_CX-60,_CY+4,_CX-40,_CY-8,_CX-36,_CY+18,RED,INK)]

def perfect_badge():
    return _clock() + [
        '<polyline points="%d,%d %d,%d %d,%d" fill="none" stroke="%s" stroke-width="15" stroke-linecap="round" stroke-linejoin="round"/>' % (_CX-30,_CY+30,_CX-8,_CY+52,_CX+38,_CY-2,INK),
        '<polyline points="%d,%d %d,%d %d,%d" fill="none" stroke="%s" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>' % (_CX-30,_CY+30,_CX-8,_CY+52,_CX+38,_CY-2,TICK)]

def ing_badge():
    # ~300deg green loop arrow = ongoing
    pts = []
    seg = []
    r = 44
    a0, a1 = -60, 250
    x0 = _CX + r*math.cos(math.radians(a0)); y0 = _CY + r*math.sin(math.radians(a0))
    x1 = _CX + r*math.cos(math.radians(a1)); y1 = _CY + r*math.sin(math.radians(a1))
    o = ['<circle cx="%d" cy="%d" r="%d" fill="#fff" stroke="%s" stroke-width="7"/>' % (_CX,_CY,_R,INK),
         '<path d="M %.1f %.1f A %d %d 0 1 1 %.1f %.1f" fill="none" stroke="%s" stroke-width="10" stroke-linecap="round"/>' % (x1,y1,r,r,x0,y0,TICK)]
    # arrowhead at (x0,y0) tangent
    ta = math.radians(a0+90)
    hx, hy = math.cos(ta), math.sin(ta)
    px, py = -hy, hx
    o.append('<polygon points="%.0f,%.0f %.0f,%.0f %.0f,%.0f" fill="%s" stroke="%s" stroke-width="2" stroke-linejoin="round"/>'
             % (x0+hx*16, y0+hy*16, x0-px*13, y0-py*13, x0+px*13, y0+py*13, TICK, INK))
    return o

# ---------------- paradigm ----------------
def _c(core, badge=None):
    return lambda: core() + (badge() if badge else [])

FORMS = {
    "be": _c(be_eq), "am": _c(be_eq), "is": _c(be_eq), "are": _c(be_eq),
    "was": _c(be_eq, past_badge), "were": _c(be_eq, past_badge),
    "being": _c(be_eq, ing_badge), "been": _c(be_eq, perfect_badge),
    "do": _c(do_arrow), "does": _c(do_arrow),
    "did": _c(do_arrow, past_badge), "doing": _c(do_arrow, ing_badge), "done": _c(do_arrow, perfect_badge),
    "have": _c(have_hand), "has": _c(have_hand),
    "had": _c(have_hand, past_badge), "having": _c(have_hand, ing_badge),
}

def build(fn): return HdG + "".join(fn()) + FT

def masters(): return {name: build(fn) for name, fn in FORMS.items()}

# pilot schematic style transfer (same proven transforms as qword_pilots)
def _pilot_tx():
    sys.path.insert(0, "/Users/paulblenkhorn/Desktop/picom_review")
    from kawaii_soft3d import soft3d
    from lineart_from_toon import linify
    ident = lambda s: s
    return {"Toon": ident, "Anime": ident, "Simplified": ident, "CP": ident,
            "Kawaii": lambda s: soft3d(s, "strong"), "3D": lambda s: soft3d(s, "strong"),
            "Lineart": linify}

def deploy():
    H = os.path.expanduser("~"); FLEX = f"{H}/Desktop/Fleximbols"
    m = masters(); n = 0
    gt = f"{FLEX}/Grammar/Tenses"; os.makedirs(gt, exist_ok=True)
    for name, s in m.items():
        open(f"{gt}/{name}.svg", "w").write(s); n += 1
    open(f"{FLEX}/Core Words/is.svg", "w").write(m["is"]); n += 1     # refresh the core-word copy
    for pilot, tx in _pilot_tx().items():
        d = f"{H}/Desktop/People Beta/{pilot} Library Pilot/Grammar/Tenses"
        os.makedirs(d, exist_ok=True)
        for name, s in m.items():
            open(f"{d}/{name}.svg", "w").write(tx(s)); n += 1
    print(f"deployed {n} files (Fleximbols Grammar/Tenses + Core Words/is + 7 pilots)")

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--help"
    if mode == "--deploy":
        deploy()
    else:
        out = mode; os.makedirs(out, exist_ok=True)
        for name, s in masters().items():
            open(os.path.join(out, f"{name}.svg"), "w").write(s)
        print(f"{len(FORMS)} forms -> {out}:", ", ".join(FORMS))

if __name__ == "__main__":
    main()
