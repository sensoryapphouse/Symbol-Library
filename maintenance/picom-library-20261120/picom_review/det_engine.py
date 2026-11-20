#!/usr/bin/env python3
"""
Deterministic figure generator (Stage A of the no-guessing rebuild).
Heads attached by construction; arms from shoulders, legs from hips.
Gender (dress/long-hair vs tee+trousers/short-hair), age (adult/child/toddler/
elderly/baby), and a pose set parsed from the filename. Groups share one floor.
Objects/costumes are Stage B. Renders figures-only for visual verification.
"""
import re
from pathlib import Path
G=455; CREAM="#f5d6b0"; BLACK="#1a1a1a"; SHOE="#33373d"
HBROWN="#5a3a1f"; HGREY="#b9b9bd"
def L(x1,y1,x2,y2,w,c=BLACK): return f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{c}" stroke-width="{w}" stroke-linecap="round"/>'
def _cls(cls): return f' class="{cls}"' if cls else ''
def C(cx,cy,r,fill,sw=6,c=BLACK,cls=""): return f'<circle{_cls(cls)} cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="{fill}" stroke="{c}" stroke-width="{sw}"/>'
def E(cx,cy,rx,ry,fill,cls=""): return f'<ellipse{_cls(cls)} cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{ry:.0f}" fill="{fill}"/>'
def Pa(d,fill,sw=5,c=BLACK): return f'<path d="{d}" fill="{fill}" stroke="{c}" stroke-width="{sw}" stroke-linejoin="round"/>'
def Poly(p,fill,sw=5,c=BLACK): return f'<polygon points="{p}" fill="{fill}" stroke="{c}" stroke-width="{sw}" stroke-linejoin="round"/>'

AD_TEE=["#4a90d9","#5a6e8c","#cc5544","#3d8a6b","#7a5230"]
KID_TEE=["#3fb24a","#e0473c","#f5a623","#3f6fb0","#8e44ad"]
DRESS=["#d6529e","#c0518f","#e0559e"]; KID_DRESS=["#f5a623","#e0473c","#3fb24a"]
FEMALE_TOP="#e8821e"   # female everyday top = orange (gender cue; male = blue tee). Uniforms pass their own colour.

HAIRCOL={"white":"#efefef","grey":"#b9b9bd","gray":"#b9b9bd","silver":"#cfcfd4",
 "red":"#bb4a23","ginger":"#c8612e","auburn":"#7a3b1f","redhead":"#bb4a23",
 "blond":"#e6c36a","blonde":"#e6c36a","golden":"#e6c36a","fair":"#e6c36a",
 "black":"#2a2a2a","dark":"#33291f","brown":"#5a3a1f","brunette":"#5a3a1f"}
def appearance(toks):
    """Parse visible-appearance attributes from the filename tokens."""
    a={}
    if "hair" in toks or (toks & {"blonde","brunette","ginger","redhead"}):
        for t in toks:
            if t in HAIRCOL: a["hair"]=HAIRCOL[t]; break
    if "bald" in toks: a["bald"]=True
    if "curly" in toks or "afro" in toks: a["curly"]=True
    if toks & {"beard","bearded","goatee"}: a["beard"]=True
    if toks & {"moustache","mustache","moustached"}: a["moustache"]=True
    if "pregnant" in toks or "pregnancy" in toks or "expecting" in toks: a["pregnant"]=True
    if toks & {"glasses","spectacles","bespectacled"}: a["glasses"]=True
    return a

def head(hx,hy,r,gender,hair,bald=False,curly=False,skin=CREAM):
    o=[]
    if bald:
        o.append(C(hx,hy,r,skin,cls="skin"))
        o.append(Pa(f"M {hx-r} {hy+2} Q {hx-r-2} {hy+r-6} {hx} {hy+r-2} Q {hx+r+2} {hy+r-6} {hx+r} {hy+2} "
                    f"Q {hx+r-3} {hy+r-12} {hx} {hy+r-8} Q {hx-r+3} {hy+r-12} {hx-r} {hy+2} Z",hair,2))   # low hair rim
        return o
    if curly:   # afro / curly: ring of hair puffs around the crown, face on top
        for dx,dy,rad in [(-r*0.92,r*0.06,14),(-r*0.78,-r*0.55,15),(-r*0.4,-r*0.94,15),(0,-r*1.04,16),
                          (r*0.4,-r*0.94,15),(r*0.78,-r*0.55,15),(r*0.92,r*0.06,14)]:
            o.append(C(hx+dx,hy+dy,rad,hair,2))
        o.append(C(hx,hy,r,skin,cls="skin"))
        return o
    if gender=="f":  # long hair behind, cream face on top, fringe
        o.append(Pa(f"M {hx-r-7} {hy+r+14} L {hx-r-7} {hy-2} Q {hx-r-7} {hy-r-14} {hx} {hy-r-14} Q {hx+r+7} {hy-r-14} {hx+r+7} {hy-2} L {hx+r+7} {hy+r+14} L {hx+r-6} {hy+r+14} L {hx+r-6} {hy} Q {hx+r-6} {hy-r+6} {hx} {hy-r+6} Q {hx-r+6} {hy-r+6} {hx-r+6} {hy} L {hx-r+6} {hy+r+14} Z",hair,3))
        o.append(C(hx,hy,r,skin,cls="skin"))
        o.append(Pa(f"M {hx-r+2} {hy-r+6} Q {hx} {hy-r-8} {hx+r-2} {hy-r+6} Q {hx} {hy-r+2} {hx-r+2} {hy-r+6} Z",hair,3))
    else:
        o.append(C(hx,hy,r,skin,cls="skin"))
        o.append(Pa(f"M {hx-r} {hy} Q {hx-r} {hy-r-10} {hx} {hy-r-10} Q {hx+r} {hy-r-10} {hx+r} {hy} Q {hx} {hy-r+13} {hx-r} {hy} Z",hair,3))
    return o

# ---- style pens: pluggable body-part inkers. 'stick' reproduces the original output
# byte-for-byte (default). A pen swaps only HOW parts are drawn; figure()'s pose/joint
# model is unchanged, so new styles (toon, kawaii, ...) are just another pen. ---------
class StickPen:
    name = "stick"
    def __init__(self, skin=CREAM, lw=13, s=1.0): self.skin, self.lw, self.s = skin, lw, s
    def limb(self, x1, y1, x2, y2, w, c=BLACK, kind="arm"): return L(x1, y1, x2, y2, w, c)
    def foot(self, cx, cy, rx, ry): return E(cx, cy + 2, rx, ry, SHOE)
    def torso(self, pts, color, **kw): return Poly(pts, color)
    def sleeves(self, shoulders, hands, color, s=1.0, drop=None): return ""   # stick: no sleeves
    def head(self, hx, hy, r, gender, hair, bald=False, curly=False, skin=CREAM):
        return head(hx, hy, r, gender, hair, bald=bald, curly=curly, skin=skin)

class ToonPen(StickPen):
    """Full cartoon-character kit: volumized limbs + mitten hands, chunky shoes, a shaped
    collared shirt (not a rectangle), and a rounded head with a real face. Same joints."""
    name = "toon"
    OUT = 6                                                        # bold shape outline

    def limb(self, x1, y1, x2, y2, w, c=BLACK, kind="arm"):
        fill = self.skin if kind in ("arm", "neck") else c        # arms/neck read as skin tubes
        fw = w * (1.15 if kind == "neck" else 1.95)               # give the bone volume
        seg = f'x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke-linecap="round"'
        out = (f'<line {seg} stroke="{BLACK}" stroke-width="{fw + 9:.1f}"/>'
               f'<line {seg} stroke="{fill}" stroke-width="{fw:.1f}"/>')
        if kind == "arm":                                          # rounded mitten hand
            out += (f'<circle cx="{x2:.0f}" cy="{y2:.0f}" r="{fw*0.85:.1f}" '
                    f'fill="{self.skin}" stroke="{BLACK}" stroke-width="{self.OUT}"/>')
        return out

    def foot(self, cx, cy, rx, ry):                                # chunky rounded shoe
        return (f'<ellipse cx="{cx:.0f}" cy="{cy + 5:.0f}" rx="{rx * 1.8:.0f}" ry="{ry * 1.9:.0f}" '
                f'fill="{SHOE}" stroke="{BLACK}" stroke-width="{self.OUT}"/>')

    def torso(self, pts, color, sh=None, hip=None, s=1.0, **kw):
        if sh is None:                                             # dress/fallback -> plain bolder
            return Poly(pts, color, sw=self.OUT)
        cx, ty, hy = sh[0], sh[1], hip[1]
        SW, HW, nk = 36 * s, 30 * s, 13 * s
        d = (f"M {cx-SW:.0f} {ty+10:.0f} "
             f"Q {cx-SW:.0f} {ty-7:.0f} {cx-SW+18*s:.0f} {ty-7:.0f} "     # left shoulder round
             f"Q {cx-nk:.0f} {ty-7:.0f} {cx-nk:.0f} {ty+1:.0f} "          # in toward collar
             f"Q {cx:.0f} {ty+17*s:.0f} {cx+nk:.0f} {ty+1:.0f} "          # collar dip
             f"Q {cx+nk:.0f} {ty-7:.0f} {cx+SW-18*s:.0f} {ty-7:.0f} "     # to right shoulder
             f"Q {cx+SW:.0f} {ty-7:.0f} {cx+SW:.0f} {ty+10:.0f} "         # right shoulder round
             f"L {cx+HW:.0f} {hy:.0f} L {cx-HW:.0f} {hy:.0f} Z")          # sides to hem
        return f'<path d="{d}" fill="{color}" stroke="{BLACK}" stroke-width="{self.OUT}" stroke-linejoin="round"/>'

    def sleeves(self, shoulders, hands, color, s=1.0, drop=None):
        import math
        out = []
        for i, ((sx, sy), (hx, hy)) in enumerate(zip(shoulders, hands)):   # short sleeve over each upper arm
            if i == drop:
                continue
            dx, dy = hx - sx, hy - sy
            ln = math.hypot(dx, dy) or 1
            ex, ey = sx + dx / ln * 30 * s, sy + dy / ln * 30 * s
            w = self.lw * 2.25
            seg = f'x1="{sx:.0f}" y1="{sy:.0f}" x2="{ex:.0f}" y2="{ey:.0f}" stroke-linecap="round"'
            out.append(f'<line {seg} stroke="{BLACK}" stroke-width="{w+9:.1f}"/>'
                       f'<line {seg} stroke="{color}" stroke-width="{w:.1f}"/>')
        return "".join(out)

    def head(self, hx, hy, r, gender, hair, bald=False, curly=False, skin=CREAM):
        if not (bald or curly):                       # transplant a REAL toon head (face+hair)
            try:
                import toon_heads
                g = toon_heads.head_group(gender, hx, hy, r)
                if g:
                    return [g]
            except Exception:
                pass
        o = head(hx, hy, r, gender, hair, bald=bald, curly=curly, skin=skin)   # fallback: parametric head + face
        bw = max(2.0, r * 0.05)
        ex, ey, er = 0.36 * r, hy - 0.02 * r, 0.12 * r
        for sgn in (-1, 1):                                        # eyes
            o.append(f'<ellipse cx="{hx+sgn*ex:.0f}" cy="{ey:.0f}" rx="{er:.1f}" ry="{er*1.25:.1f}" fill="{BLACK}"/>')
            o.append(f'<path d="M {hx+sgn*ex-er:.0f} {ey-er*1.7:.0f} Q {hx+sgn*ex:.0f} {ey-er*2.5:.0f} '
                     f'{hx+sgn*ex+er:.0f} {ey-er*1.7:.0f}" fill="none" stroke="{BLACK}" '
                     f'stroke-width="{max(3,r*0.06):.0f}" stroke-linecap="round"/>')   # brow
        o.append(f'<path d="M {hx:.0f} {hy+0.06*r:.0f} Q {hx+0.07*r:.0f} {hy+0.22*r:.0f} {hx-0.05*r:.0f} {hy+0.24*r:.0f}" '
                 f'fill="none" stroke="{BLACK}" stroke-width="{bw:.0f}" stroke-linecap="round"/>')   # nose
        my, mw = hy + 0.42 * r, 0.28 * r                          # open smile
        o.append(f'<path d="M {hx-mw:.0f} {my:.0f} Q {hx:.0f} {my+0.34*r:.0f} {hx+mw:.0f} {my:.0f} '
                 f'Q {hx:.0f} {my+0.13*r:.0f} {hx-mw:.0f} {my:.0f} Z" fill="#8a3324" '
                 f'stroke="{BLACK}" stroke-width="{bw:.0f}" stroke-linejoin="round"/>')
        return o

PENS = {"stick": StickPen, "toon": ToonPen}

def figure(cx, ground, age, gender, pose, color=None, hair=None, expr=None,
           bald=False, curly=False, beard=False, moustache=False, pregnant=False, glasses=False, skin=CREAM,
           skirt=True, drop_arm=None, style="stick"):
    """Verified construction. Returns (elements, joints).
    skirt=False renders a female (long hair) on the TROUSER body (no dress) — for jobs etc."""
    if age=="baby": return baby(cx,ground,skin=skin)
    s={"adult":1.0,"elderly":1.0,"child":0.72,"toddler":0.58}.get(age,1.0)
    old=age=="elderly"; female=gender=="f"; child=age in("child","toddler")
    wear_dress=female and skirt
    r=(40*s*1.34 if style=="toon" else 40*s); lw=max(8,13*s)
    pen=PENS.get(style,StickPen)(skin=skin,lw=lw,s=s)
    hair = HGREY if old else (hair or HBROWN)
    if color is None:
        if female:
            color=FEMALE_TOP                              # orange top — dress OR trousers
        else:
            color=(KID_TEE if child else AD_TEE)[0]       # blue tee (male)
            if old: color="#8a8f98"                       # elderly male grey
    # base joints (scaled), then pose overrides
    hip=(cx, ground-150*s); sh=(cx, ground-258*s); hx,hy=cx, ground-(325*s);
    hands=[(cx-62*s,ground-150*s),(cx+62*s,ground-150*s)]   # resting arms angle out a little at the lower end (was 50)
    feet=[(cx-24*s,ground),(cx+24*s,ground)]; knees=None; lean=0
    P=pose
    if P=="walk": feet=[(cx+30*s,ground),(cx-26*s,ground)]; hands=[(cx-44*s,ground-150*s),(cx+50*s,ground-168*s)]
    elif P=="run": lean=16*s; sh=(cx+lean,sh[1]); hx+=lean; hip=(cx+lean*0.5,hip[1]); hands=[(cx-40*s+lean,ground-200*s),(cx+62*s+lean,ground-205*s)]; feet=[(cx+64*s+lean,ground),(cx-52*s+lean,ground-40*s)]
    elif P=="jump": dy=26*s; sh=(cx,sh[1]-dy); hx=cx; hy-=dy; hip=(cx,hip[1]-dy); hands=[(cx-58*s,hy-6*s),(cx+58*s,hy-6*s)]; feet=[(cx-30*s,ground-50*s),(cx+30*s,ground-50*s)]
    elif P in("cheer","celebrate"): hands=[(cx-52*s,sh[1]-44*s),(cx+52*s,sh[1]-44*s)]
    elif P in("welcome","openarms","embrace"): hands=[(cx-104*s,sh[1]-30*s),(cx+104*s,sh[1]-30*s)]   # wide open arms, slightly raised, palms up
    elif P=="wave": hands=[(cx-46*s,ground-150*s),(cx+58*s,sh[1]-46*s)]
    elif P in("point","reach","carry","throw","hold","give","lend","take"): hands=[(cx-46*s,ground-150*s),(cx+78*s,sh[1]+24*s)]
    elif P=="shrug": hands=[(cx-58*s,sh[1]+14*s),(cx+58*s,sh[1]+14*s)]
    elif P=="facepalm": hands=[(cx-48*s,ground-150*s),(cx+6*s,hy+r-6*s)]
    elif P in("tip","tipping"): hands=[(cx-46*s,ground-150*s),(cx+72*s,sh[1]+34*s)]
    elif P in("gesture-no","pout"): hands=[(cx+26*s,sh[1]+34*s),(cx-26*s,sh[1]+34*s)]
    elif P=="gesture-ok": hands=[(cx-46*s,ground-150*s),(cx+38*s,sh[1]-14*s)]
    elif P=="salute": hands=[(cx-44*s,ground-150*s),(cx+8*s,hy-r+4*s)]
    elif P=="power": hands=[(cx-40*s,hip[1]-10*s),(cx+40*s,hip[1]-10*s)]; feet=[(cx-36*s,ground),(cx+36*s,ground)]
    elif P=="slump": sh=(cx,ground-248*s); hx=cx+16*s; hy=ground-296*s; hands=[(cx-22*s,hip[1]+8*s),(cx+24*s,hip[1]+8*s)]
    elif P=="leap": hx=cx+6*s; hands=[(cx-52*s,sh[1]-34*s),(cx+58*s,sh[1]-34*s)]; feet=[(cx+42*s,ground-34*s),(cx-30*s,ground-74*s)]
    elif P in("raise-hand","raising"): hands=[(cx-46*s,ground-150*s),(cx+64*s,sh[1]-54*s)]
    elif P=="sit": hip=(cx,ground-110*s); knees=[(cx-40*s,ground-110*s),(cx+40*s,ground-110*s)]; feet=[(cx-40*s,ground-40*s),(cx+40*s,ground-40*s)]
    elif P in("kneel","pray","propose"): hip=(cx,ground-98*s); knees=[(cx-28*s,ground),(cx+32*s,ground-76*s)]; feet=[(cx-54*s,ground),(cx+32*s,ground)]; hands=[(cx-30*s,ground-150*s),(cx+34*s,ground-150*s)]
    elif P in("exercise","starjump","jumping-jack","star"): hands=[(cx-56*s,ground-300*s),(cx+56*s,ground-300*s)]; feet=[(cx-46*s,ground),(cx+46*s,ground)]
    elif P=="balance": feet=[(cx-2*s,ground),(cx+34*s,ground-86*s)]; hands=[(cx-62*s,ground-204*s),(cx+62*s,ground-204*s)]
    elif P in("march","marching"): feet=[(cx-26*s,ground),(cx+22*s,ground-58*s)]; hands=[(cx-40*s,ground-186*s),(cx+44*s,ground-118*s)]
    elif P in("crouch","squat","duck"): hip=(cx,ground-78*s); knees=[(cx-40*s,ground-78*s),(cx+40*s,ground-78*s)]; feet=[(cx-38*s,ground),(cx+38*s,ground)]; hands=[(cx-30*s,ground-110*s),(cx+30*s,ground-110*s)]
    elif P=="kneel2":   # upright on BOTH knees: lowered torso, both knees on the ground, shins folded back
        hip=(cx,ground-92*s); sh=(cx,ground-200*s); hx,hy=cx,ground-267*s
        knees=[(cx-26*s,ground),(cx+26*s,ground)]; feet=[(cx-48*s,ground),(cx+48*s,ground)]
        hands=[(cx-46*s,ground-96*s),(cx+46*s,ground-96*s)]
    elif P=="climb": sh=(cx+8*s,ground-258*s); hx=cx+10*s; hands=[(cx-2*s,ground-300*s),(cx+44*s,ground-252*s)]; feet=[(cx-22*s,ground),(cx+30*s,ground-46*s)]
    elif P=="ride": hip=(cx,ground-132*s); sh=(cx,ground-240*s); hx=cx; hy=ground-307*s; knees=[(cx-46*s,ground-128*s),(cx+46*s,ground-128*s)]; feet=[(cx-28*s,ground-62*s),(cx+30*s,ground-62*s)]; hands=[(cx+46*s,ground-150*s),(cx+82*s,ground-148*s)]
    elif P=="bow": sh=(cx+44*s,ground-245*s); hx=cx+82*s; hy=ground-289*s; hands=[(cx+60*s,ground-150*s),(cx+74*s,ground-150*s)]
    elif P in("dance","dancing"): hands=[(cx-58*s,sh[1]-30*s),(cx+44*s,ground-160*s)]; feet=[(cx-34*s,ground),(cx+30*s,ground-18*s)]
    elif P in("lift","lifting","deadlift","weights"): hands=[(cx-44*s,ground-150*s),(cx+44*s,ground-150*s)]
    elif P in("eat","eating"): hands=[(cx-30*s,ground-208*s),(cx+14*s,ground-298*s)]
    elif P in("drink","drinking"): hands=[(cx-44*s,ground-150*s),(cx+14*s,ground-298*s)]
    elif P in("kick","kicking"): feet=[(cx-24*s,ground),(cx+72*s,ground-66*s)]; hands=[(cx-54*s,ground-160*s),(cx+44*s,ground-150*s)]
    elif P in("push","pushing"): sh=(cx+8*s,sh[1]); hx=cx+12*s; hands=[(cx+58*s,ground-236*s),(cx+62*s,ground-196*s)]; feet=[(cx-42*s,ground),(cx+2*s,ground)]
    elif P in("pull","pulling"): sh=(cx-8*s,sh[1]); hx=cx-10*s; hands=[(cx+54*s,ground-182*s),(cx+58*s,ground-150*s)]; feet=[(cx-24*s,ground),(cx+34*s,ground)]
    elif P in("catch","catching"): hands=[(cx-30*s,ground-298*s),(cx+46*s,ground-292*s)]
    elif P in("clap","clapping","applaud"): hands=[(cx-8*s,ground-234*s),(cx+8*s,ground-234*s)]
    elif P in("listen","listening"): hands=[(cx-44*s,ground-150*s),(cx+34*s,ground-316*s)]
    elif P in("look","looking","watch"): hands=[(cx-44*s,ground-150*s),(cx+30*s,ground-330*s)]
    elif P in("hop","hopping"): feet=[(cx-6*s,ground-42*s),(cx+26*s,ground-80*s)]; hands=[(cx-50*s,ground-178*s),(cx+50*s,ground-178*s)]
    elif P in("skip","skipping"): feet=[(cx+32*s,ground-34*s),(cx-26*s,ground)]; hands=[(cx-48*s,ground-186*s),(cx+50*s,ground-150*s)]
    elif P in("stretch","stretching","reach-up","wake"): hands=[(cx-34*s,ground-332*s),(cx+34*s,ground-332*s)]
    elif P in("fall","falling","trip","slip"): sh=(cx-28*s,ground-236*s); hx=cx-54*s; hy=ground-292*s; hands=[(cx-72*s,ground-292*s),(cx-18*s,ground-300*s)]; feet=[(cx+52*s,ground-18*s),(cx+22*s,ground-6*s)]
    elif P in("flex","strong"): hands=[(cx-24*s,ground-272*s),(cx+24*s,ground-272*s)]; feet=[(cx-34*s,ground),(cx+34*s,ground)]
    elif P=="wash": hands=[(cx-16*s,ground-150*s),(cx+16*s,ground-150*s)]
    elif P=="drive": hands=[(cx-26*s,ground-224*s),(cx+26*s,ground-224*s)]
    elif P=="read": hands=[(cx-28*s,ground-212*s),(cx+28*s,ground-212*s)]
    elif P=="type": hands=[(cx-24*s,ground-188*s),(cx+24*s,ground-188*s)]
    elif P in("pickup","pick-up"): sh=(cx+28*s,ground-236*s); hx=cx+60*s; hy=ground-282*s; hands=[(cx+38*s,ground-150*s),(cx+54*s,ground-26*s)]
    elif P=="think": hip=(cx,ground-110*s); knees=[(cx-40*s,ground-110*s),(cx+40*s,ground-110*s)]; feet=[(cx-40*s,ground-40*s),(cx+40*s,ground-40*s)]; hands=[(cx-28*s,ground-110*s),(cx+6*s,ground-296*s)]
    elif P in("want","reach-out","grab"): hands=[(cx+42*s,ground-208*s),(cx+64*s,ground-192*s)]
    elif P in("pledge","vow"): hands=[(cx-44*s,ground-150*s),(cx-8*s,ground-206*s)]
    elif P=="tummy": hands=[(cx-44*s,ground-150*s),(cx-6*s,ground-134*s)]
    elif P=="throat": hands=[(cx-44*s,ground-150*s),(cx-2*s,ground-288*s)]
    elif P in("cold","shiver"): hands=[(cx+30*s,ground-238*s),(cx-30*s,ground-238*s)]
    elif P in("fan","hot"): hands=[(cx-44*s,ground-150*s),(cx+34*s,ground-314*s)]
    elif P in("please","palms-up"): hands=[(cx-34*s,ground-184*s),(cx+34*s,ground-184*s)]
    elif P in("halt","stopgesture"): hands=[(cx-44*s,ground-150*s),(cx+58*s,ground-256*s)]
    elif P in("putdown","place"): hands=[(cx-28*s,ground-120*s),(cx+28*s,ground-120*s)]
    elif P in("alldone","finished"): hands=[(cx-42*s,ground-252*s),(cx+42*s,ground-252*s)]
    elif P in("wide","big"): hands=[(cx-82*s,ground-208*s),(cx+82*s,ground-208*s)]
    elif P in("narrow","small"): hands=[(cx-12*s,ground-198*s),(cx+12*s,ground-198*s)]
    elif P=="hit": hands=[(cx-44*s,ground-150*s),(cx+50*s,ground-300*s)]
    # superman dive: both arms extended straight past the head, legs together and
    # straight. Drawn UPRIGHT; the caller rotates the whole figure to horizontal so
    # the arms lead and the legs trail. Do NOT rotate a standing figure instead —
    # that reads as a person lying down, not flying.
    elif P in("fly","dive"): hands=[(cx-20*s,ground-406*s),(cx+24*s,ground-398*s)]; feet=[(cx-13*s,ground),(cx+13*s,ground)]
    # ---- draw: legs, torso, arms, neck, head ----
    o=[]
    SHW=30*s; HPW=15*s
    shoulders=[(sh[0]-SHW,sh[1]+2),(sh[0]+SHW,sh[1]+2)]
    hips=[(hip[0]-HPW,hip[1]-2),(hip[0]+HPW,hip[1]-2)]
    if wear_dress:
        hem=ground-66*s
        o.append(Pa(f"M {sh[0]-30*s} {sh[1]} L {sh[0]+30*s} {sh[1]} L {hip[0]+30*s} {hip[1]-18*s} L {hip[0]+56*s} {hem} L {hip[0]-56*s} {hem} L {hip[0]-30*s} {hip[1]-18*s} Z",color,5))
        leg_tops=[(hip[0]-18*s,hem),(hip[0]+18*s,hem)]
        if knees:   # respect the knee joint so kneel/sit/ride bend for women too
            for (hpx,hpy),(kx,ky),(fx,fy) in zip(leg_tops,knees,feet): o.append(pen.limb(hpx,hpy,kx,ky,lw,kind="leg")); o.append(pen.limb(kx,ky,fx,fy,lw,kind="leg"))
        else:
            for (hpx,hpy),(fx,fy) in zip(leg_tops,feet): o.append(pen.limb(hpx,hpy,fx,fy,lw,kind="leg"))
        for fx,fy in feet: o.append(pen.foot(fx,fy,13*s,7*s))
    else:
        # legs
        if knees:
            for (hpx,hpy),(kx,ky),(fx,fy) in zip(hips,knees,feet): o.append(pen.limb(hpx,hpy,kx,ky,lw+3,"#39425c",kind="leg")); o.append(pen.limb(kx,ky,fx,fy,lw+3,"#39425c",kind="leg"))
        else:
            for (hpx,hpy),(fx,fy) in zip(hips,feet): o.append(pen.limb(hpx,hpy,fx,fy,lw+3,"#39425c" if not child else BLACK,kind="leg"))
        for fx,fy in feet: o.append(pen.foot(fx,fy,13*s,7*s))
        o.append(pen.torso(f"{sh[0]-32*s:.0f},{sh[1]:.0f} {sh[0]+32*s:.0f},{sh[1]:.0f} {hip[0]+30*s:.0f},{hip[1]:.0f} {hip[0]-30*s:.0f},{hip[1]:.0f}",color))
        if child:
            hem_s=hip[1]+40*s   # short shorts: hem sits at the upper thigh, not down at the knee
            o.append(Poly(f"{hip[0]-30*s:.0f},{hip[1]:.0f} {hip[0]+30*s:.0f},{hip[1]:.0f} {hip[0]+30*s:.0f},{hem_s:.0f} {hip[0]-30*s:.0f},{hem_s:.0f}","#e0473c"))
    if pregnant:
        o.append(C(cx,ground-118*s,33*s,color))                  # rounded belly (clothing colour)
    # arms from shoulders (drop_arm=0 omits left, 1 omits right — for interaction scenes
    # where an action/reaching arm REPLACES the rest arm on that side, not adds a 3rd arm)
    for i,((shx,shy),(hxn,hyn)) in enumerate(zip(shoulders,hands)):
        if i==drop_arm: continue
        o.append(pen.limb(shx,shy,hxn,hyn,lw,kind="arm"))
    _sl=pen.sleeves(shoulders,hands,color,s,drop_arm)   # short sleeves over the upper arms (toon only)
    if _sl: o.append(_sl)
    # neck shoulder-centre -> head
    o.append(pen.limb(sh[0],sh[1],hx,hy+r-4,lw,kind="neck"))
    o+=pen.head(hx,hy,r,gender,hair,bald=bald,curly=curly,skin=skin)
    _fc=('f' if female else 'm')+('c' if child else 'a')   # data-fig code (gender+age) on the head -> <metadata id="sah">
    for _i,_el in enumerate(o):
        if _el.startswith('<circle class="skin"'):
            o[_i]=_el.replace('<circle class="skin"', f'<circle class="skin" data-fig="{_fc}"', 1); break
    if beard:
        o.append(Pa(f"M {hx-r+2} {hy+r-16} Q {hx-r-3} {hy+r+9} {hx} {hy+r+15} Q {hx+r+3} {hy+r+9} {hx+r-2} {hy+r-16} "
                    f"Q {hx} {hy+r-4} {hx-r+2} {hy+r-16} Z",hair,3))
    if moustache:
        o.append(Pa(f"M {hx-14*s} {hy+9*s} Q {hx} {hy+17*s} {hx+14*s} {hy+9*s} Q {hx} {hy+12*s} {hx-14*s} {hy+9*s} Z",hair,2))
    if glasses:
        o+=[C(hx-14*s,hy-4,9*s,"none",3),C(hx+14*s,hy-4,9*s,"none",3),L(hx-5*s,hy-4,hx+5*s,hy-4,2)]
    if old:
        o.append(C(hx-15*s,hy+2,9*s,"none",3,"#333")); o.append(C(hx+15*s,hy+2,9*s,"none",3,"#333")); o.append(L(hx-6*s,hy+2,hx+6*s,hy+2,3,"#333"))
        o.append(Pa(f"M {shoulders[1][0]+22} {sh[1]+20} L {shoulders[1][0]+30} {ground}","none",7,"#9a6a3a"))
    if expr:
        o.append(C(hx-13*s,hy-3,3.5*s,BLACK,0)); o.append(C(hx+13*s,hy-3,3.5*s,BLACK,0))
        my=hy+18*s
        if expr=="frown": o.append(Pa(f"M {hx-14*s} {my+4} Q {hx} {my-10} {hx+14*s} {my+4}","none",4))
        elif expr=="smile": o.append(Pa(f"M {hx-14*s} {my-4} Q {hx} {my+12} {hx+14*s} {my-4}","none",4))
        else: o.append(L(hx-12*s,my,hx+12*s,my,4))
    if pose=="facepalm":
        o.append(L(shoulders[1][0],shoulders[1][1],hx+2,hy+4,lw)); o.append(f'<ellipse class="skin" cx="{hx+2:.0f}" cy="{hy+6:.0f}" rx="{15*s:.0f}" ry="{19*s:.0f}" fill="{skin}" stroke="{BLACK}" stroke-width="5"/>')
    elif pose=="salute":
        o.append(L(shoulders[1][0],shoulders[1][1],hx+8,hy-r+6,lw)); o.append(f'<ellipse class="skin" cx="{hx+10:.0f}" cy="{hy-r+4:.0f}" rx="{13*s:.0f}" ry="{9*s:.0f}" fill="{skin}" stroke="{BLACK}" stroke-width="4"/>')
    elif pose=="shrug":
        for (hxx,hyy) in hands: o.append(Pa(f"M {hxx-10*s} {hyy} Q {hxx} {hyy+12*s} {hxx+10*s} {hyy}","none",4,skin))
    elif pose=="gesture-ok":   # large, clear OK hand: thumb+index ring + three fingers up
        x,y=hands[1]
        o.append(f'<ellipse class="skin" cx="{x:.0f}" cy="{y+4:.0f}" rx="{15*s:.0f}" ry="{13*s:.0f}" fill="{skin}" stroke="{BLACK}" stroke-width="4"/>')  # palm
        for dx in (-9,0,9): o.append(L(x+dx*s,y-6*s,x+dx*s,y-26*s,6*s,skin))   # three fingers up
        o.append(C(x+16*s,y-10*s,11*s,"none",6,BLACK))                          # thumb+index OK ring (bold)
    return o,dict(cx=cx,s=s,ground=ground,hx=hx,hy=hy,r=r,sh=sh,hip=hip,hands=hands,shoulders=shoulders,feet=feet,knees=knees,pose=pose)

def baby(cx,ground,skin=CREAM):
    hy=ground-150; r=42; o=[]
    o.append(L(cx-14,hy+92,cx-44,hy+130,14)); o.append(L(cx+14,hy+92,cx+44,hy+130,14))
    o+=[E(cx-48,hy+132,13,8,SHOE),E(cx+48,hy+132,13,8,SHOE)]
    o.append(L(cx-22,hy+52,cx-52,hy+86,14)); o.append(L(cx+22,hy+52,cx+52,hy+86,14))
    o.append(Pa(f"M {cx-30} {hy+42} Q {cx-36} {hy+100} {cx} {hy+104} Q {cx+36} {hy+100} {cx+30} {hy+42} Z","#ffcf33",5))
    o.append(C(cx,hy,r,skin,cls="skin"))
    o.append(Pa(f"M {cx} {hy-r+3} q -11 -15 5 -17 q 13 -1 6 13","none",4,HBROWN))
    o.append(C(cx-20,hy+10,6,"#f4a4a4",0)); o.append(C(cx+20,hy+10,6,"#f4a4a4",0))
    o.append(C(cx-13,hy-4,3.5,BLACK,0)); o.append(C(cx+13,hy-4,3.5,BLACK,0))
    return o,dict(cx=cx,s=0.5,ground=ground,hx=cx,hy=hy,r=r,sh=(cx,hy+40),hip=(cx,hy+90),hands=[(cx-52,hy+86),(cx+52,hy+86)],shoulders=[(cx-22,hy+44),(cx+22,hy+44)],pose="sit")

def svg(b): return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n'+"\n".join(b)+"\n</svg>\n"

MEMBER={"man":("adult","m"),"woman":("adult","f"),"boy":("child","m"),"girl":("child","f"),
 "kid":("child","n"),"child":("child","n"),"baby":("baby","n"),"infant":("baby","n"),"newborn":("baby","n"),
 "toddler":("toddler","n"),"adult":("adult","n"),"person":("adult","n"),"lady":("adult","f"),"guy":("adult","m"),
 "grandpa":("elderly","m"),"grandfather":("elderly","m"),"grandma":("elderly","f"),"grandmother":("elderly","f"),
 "granny":("elderly","f"),"elderly":("elderly","n"),"senior":("elderly","n"),"dad":("adult","m"),"father":("adult","m"),
 "mom":("adult","f"),"mum":("adult","f"),"mother":("adult","f"),"son":("child","m"),"daughter":("child","f"),
 "brother":("adult","m"),"sister":("adult","f"),"husband":("adult","m"),"wife":("adult","f"),
 "grandad":("elderly","m"),"old-man":("elderly","m"),"old-woman":("elderly","f")}
PLURAL={"men":("adult","m"),"women":("adult","f"),"boys":("child","m"),"girls":("child","f"),"kids":("child","n"),
 "children":("child","n"),"babies":("baby","n"),"people":("adult","n"),"friends":("adult","n")}
POSE_KW={"climb":"climb","climbing":"climb","shrug":"shrug","shrugging":"shrug","run":"run","running":"run",
 "jog":"run","walk":"walk","walking":"walk","jump":"jump","jumping":"jump","sit":"sit","sitting":"sit",
 "kneel":"kneel","kneeling":"kneel","pray":"kneel","bow":"bow","bowing":"bow","dance":"dance","dancing":"dance",
 "wave":"wave","waving":"wave","cheer":"cheer","celebrate":"cheer","point":"point","raising":"raise-hand",
 "lift":"lift","lifting":"lift","deadlift":"lift","weights":"lift","carry":"carry","throw":"throw","reach":"reach"}
GROUP={"family":[("adult","m"),("adult","f"),("child","n")],"couple":[("adult","m"),("adult","f")],
 "team":[("adult","n")]*3,"group":[("adult","n")]*3,"crowd":[("adult","n")]*3}

POSE_KW2={"shrug":"shrug","shrugging":"shrug","facepalm":"facepalm","facepalming":"facepalm",
 "tipping":"tip","raising":"raise-hand"}
def parse(name):
    s=re.sub(r"\s*\(\d+\)$","",name[:-4] if name.lower().endswith(".svg") else name).lower()
    toks=[t for t in re.split(r"[ \-_:]+",s) if t]; tset=set(toks)
    elderly = bool(tset & {"old","older","elderly","senior","aged"})
    mem=[]
    for t in toks:
        if t in MEMBER:
            a,g=MEMBER[t]; a="elderly" if (elderly and a=="adult") else a; mem.append((a,g))
        elif t in PLURAL:
            a,g=PLURAL[t]; a="elderly" if (elderly and a=="adult") else a; mem += [(a,g)]*2
    if not mem:
        for gw,gm in GROUP.items():
            if gw in tset: mem=list(gm); break
    _pk={**POSE_KW,**POSE_KW2}
    pose=next((_pk[t] for t in toks if t in _pk),"stand")
    if not mem:
        g='f' if tset&{"woman","girl","lady","mother","sister","she"} else ('m' if tset&{"man","boy","father","brother"} else 'n')
        mem=[("adult", g)]
    return mem,pose

# toon: poses that have a REAL posed template (drop in the whole figure — real trousers,
# arms, hands, correct layering) instead of synthesising a parametric body.
_TT={"stand":{"m":"man-standing.svg","f":"woman-standing.svg","n":"person-standing.svg"},
     "walk":{"m":"man-walking-facing-right.svg","f":"woman-walking-facing-right.svg","n":"person-walking-facing-right.svg"},
     "run":{"m":"man-running-facing-right.svg","f":"person-running-facing-right.svg","n":"person-running-facing-right.svg"},
     "kneel":{"m":"man-kneeling-facing-right.svg","f":"woman-kneeling-facing-right.svg","n":"person-kneeling-facing-right.svg"}}

def compose(name,style="stick"):
    mem,pose=parse(name)
    s=re.sub(r"\s*\(\d+\)$","",name[:-4] if name.lower().endswith(".svg") else name).lower()
    ap=appearance(set(re.split(r"[ \-_:]+",s)))
    n=len(mem);
    if style=="toon" and n==1 and mem[0][0]=="adult" and pose in _TT and not (ap.get("bald") or ap.get("curly") or ap.get("beard")):
        g=mem[0][1]; g=g if g in ("m","f") else ['m','f'][sum(map(ord,name))%2]
        try:
            import toon_heads
            fig=toon_heads.full_figure(_TT[pose].get(g) or _TT[pose]["n"])
            if fig: return fig
        except Exception: pass
    xs=[256] if n==1 else [int(86+340*i/(n-1)) for i in range(n)]
    body=[]
    for i,(age,gender) in enumerate(mem):
        g = gender if gender!='n' else (['m','f'][ (sum(map(ord,name))+i)%2 ])
        els,_=figure(xs[i],G,age,g,pose if n==1 else "stand",
                     hair=ap.get("hair"), bald=ap.get("bald",False), curly=ap.get("curly",False),
                     beard=ap.get("beard",False), moustache=ap.get("moustache",False),
                     pregnant=ap.get("pregnant",False), glasses=ap.get("glasses",False), style=style)
        body+=els
    return svg(body)

if __name__=="__main__":
    src=Path("/tmp/stick_unannotated_reduced.txt")
    names=[l.strip() for l in src.read_text().splitlines() if l.strip()] if src.exists() else []
    out=Path("/tmp/det_figs"); out.mkdir(exist_ok=True)
    for nme in names:
        try: (out/nme).write_text(compose(nme))
        except Exception as e: print("ERR",nme,e)
    print(f"rendered {len(names)} deterministic figures to {out}")
