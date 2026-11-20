#!/usr/bin/env python3
"""Tense annotations for verbs, reusing the PiCom Modal clock (did=past / will=future) + a new
present-continuous clock (straight arrow right, under the face). Collision-aware: if the verb
intrudes into the top-right clock zone it is shifted down-left and shrunk a little to clear it."""
import re, subprocess, os

# ---- clock pieces lifted verbatim from Core symbols/Base/Modal/did.svg (group coord space) ----
_FACE = ('<polygon points="82,149 83,157 84,166 86,174 89,182 92,189 97,196 101,202 107,208 113,214 119,219 126,223 134,226 141,229 149,231 158,232 166,233 175,232 183,231 191,229 199,226 206,223 213,219 220,214 226,208 231,202 236,196 240,189 244,182 246,174 249,166 250,157 250,149 250,140 249,132 246,124 244,116 240,109 236,102 231,95 226,89 220,84 213,79 206,75 199,71 191,69 183,67 175,65 166,65 158,65 149,67 141,69 134,71 126,75 119,79 113,84 107,89 101,95 97,102 92,109 89,116 86,124 84,132 83,140 82,149" fill="#ffffff" stroke="#000000" stroke-width="8" fill-rule="evenodd"/>'
 '<polyline points="166,209 166,225" fill="none" stroke="#000000" stroke-width="8"/><polyline points="106,149 90,149"  fill="none" stroke="#000000" stroke-width="8"/><polyline points="243,149 226,149" fill="none" stroke="#000000" stroke-width="8"/><polyline points="124,191 112,203" fill="none" stroke="#000000" stroke-width="8"/><polyline points="220,95 209,106"  fill="none" stroke="#000000" stroke-width="8"/><polyline points="220,203 209,191" fill="none" stroke="#000000" stroke-width="8"/><polyline points="112,95 123,106"  fill="none" stroke="#000000" stroke-width="8"/>'
 '<polygon points="158,81 159,84 161,87 164,89 167,90 171,89 173,87 175,84 176,81 175,77 173,74 171,72 167,72 164,72 161,74 159,77 158,81" fill="#000000" stroke="#000000" stroke-width="5"/><polygon points="168,98 174,153 159,151 168,98" fill="#000000" stroke="#000000" stroke-width="5"/><polygon points="157,149 158,152 160,155 163,157 166,158 170,157 173,155 175,152 175,149 175,145 173,142 170,141 166,140 163,141 160,142 158,145 157,149" fill="#000000" stroke="#000000" stroke-width="5"/>')
_ARROW_TOP  = '<polygon points="135,33 170,5 180,17 145,45 153,55 104,66 127,23 135,33" fill="#e03734" stroke="#000000" stroke-width="6"/>'   # curved arrow, top (past)
_ARROW_CONT = '<polygon points="112,256 205,256 205,243 251,272 205,301 205,288 112,288" fill="#e03734" stroke="#000000" stroke-width="6"/>'  # straight arrow right, under the face (continuous)

def clock(kind):
    if kind=="past":   return f'<g transform="translate(460,5) scale(0.4825) translate(-166,-5)">{_FACE}{_ARROW_TOP}</g>'
    if kind=="future": return f'<g transform="translate(425,5) scale(0.4825) translate(-166,-5) scale(-1,1) translate(-332,0)">{_FACE}{_ARROW_TOP}</g>'
    if kind=="cont":   return f'<g transform="translate(460,5) scale(0.4825) translate(-166,-5)">{_FACE}{_ARROW_CONT}</g>'
    raise ValueError(kind)

_VB = re.compile(r'viewBox="\s*([-\d.]+)[ ,]+([-\d.]+)[ ,]+([-\d.]+)[ ,]+([-\d.]+)')
def _num(x):
    t = f"{x:.4f}".rstrip("0").rstrip("."); return t if t not in ("", "-0") else "0"
def anchored_clock(kind, head):
    """The clock is DESIGNED in 0..512 space (top-right). For any other viewBox, prefix the clock
    group's transform with translate(minX,minY) scale(w/512[,h/512]) so it sits proportionally in the
    top-right corner of THIS symbol's own viewBox. 512 (or missing) viewBox -> returned unchanged."""
    c = clock(kind)
    m = _VB.search(head or "")
    if not m: return c
    minx, miny, w, h = map(float, m.groups())
    if abs(minx) < 1e-6 and abs(miny) < 1e-6 and abs(w-512) < 1e-6 and abs(h-512) < 1e-6:
        return c
    sx, sy = w/512.0, h/512.0
    scale = f"scale({_num(sx)})" if abs(sx-sy) < 1e-6 else f"scale({_num(sx)},{_num(sy)})"
    return c.replace('<g transform="', f'<g transform="translate({_num(minx)},{_num(miny)}) {scale} ', 1)

def _zone_inked(path, x, y, w, h):
    """True iff the base symbol has ink inside the clock rectangle (top-right corner)."""
    png="/tmp/_bb.png"
    subprocess.run(["/opt/homebrew/bin/rsvg-convert","-w","512","-h","512","-b","#fff",path,"-o",png],
                   capture_output=True)
    r=subprocess.run(["/opt/homebrew/bin/magick",png,"-crop",f"{w}x{h}+{x}+{y}","+repage",
                      "-format","%[fx:mean]","info:"],capture_output=True,text=True)
    try: return float(r.stdout.strip()) < 0.997      # anything darker than ~white => overlap
    except ValueError: return False

def annotate(verb_path, kind):
    s=open(verb_path,encoding="utf-8").read()
    mo=re.search(r'(<svg[^>]*>)(.*)(</svg>\s*)$', s, re.S)
    if mo:
        head,body,tail=mo.group(1),mo.group(2),mo.group(3)
    else:                                    # robust fallback: opening <svg...> .. last </svg>
        om=re.search(r'<svg[^>]*>', s, re.S); ci=s.rfind("</svg>")
        if not om or ci<0: return s          # unparseable -> return unchanged (caller skips)
        head, body, tail = s[:om.end()], s[om.end():ci], s[ci:]
    # the clock rectangle (top-right); continuous reaches ~30px lower for the straight arrow
    zx, zy, zw = 400, 20, 112
    zh = 128 if kind=="cont" else 104
    wrap_open, wrap_close = "", ""
    if _zone_inked(verb_path, zx, zy, zw, zh):           # ONLY shift if the verb actually enters the clock rectangle
        # shrink a little + nudge down-left to clear the clock. The (8,92) offset is DESIGNED in
        # 0..512 space; it MUST be scaled into THIS file's own viewBox (same lesson as the clock
        # anchoring) or a small canvas (e.g. viewBox 100) gets the drawing shoved off-screen —
        # 92 units is 92% of a 100px canvas. Scale by w/512, h/512 and anchor at the viewBox corner.
        k = 0.82
        m = _VB.search(head or "")
        if m:
            minx, miny, w, h = map(float, m.groups())
            sx, sy = w / 512.0, h / 512.0
            tx, ty = minx + 8 * sx, miny + 92 * sy
            wrap_open = f'<g transform="translate({tx:.3f},{ty:.3f}) scale({k}) translate({-minx:.3f},{-miny:.3f})">'
        else:
            wrap_open = f'<g transform="translate(8,92) scale({k})">'
        wrap_close = '</g>'
    return f'{head}{wrap_open}{body}{wrap_close}{anchored_clock(kind, head)}{tail}'

if __name__=="__main__":
    FLEX="/Users/paulblenkhorn/Desktop/Fleximbols/Verbs"
    OUT="/tmp/tense"; os.makedirs(OUT,exist_ok=True)
    bases=["walk (M)","run (M)","eat (M)","cheer (M)","reach (M)","jump (M)"]
    for base in bases:
        for kind in ("past","cont","future"):
            src=f"{FLEX}/{base}.svg"
            if not os.path.exists(src): continue
            open(f"{OUT}/{base}-{kind}.svg","w").write(annotate(src,kind))
        # report whether the shift fired (top-right inked)
        if os.path.exists(f"{FLEX}/{base}.svg"):
            print(base, "-> shift" if _zone_inked(f"{FLEX}/{base}.svg",400,20,112,104) else "-> no shift (clock zone clear)")
    print("done")
