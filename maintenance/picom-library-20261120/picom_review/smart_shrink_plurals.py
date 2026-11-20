#!/usr/bin/env python3
"""Content-aware MINIMAL shrink so the plural asterisk never obscures the symbol, and symbols that
don't need it stay full size.

Per plural: render the drawing (badge stripped) -> content mask. If no content sits under the badge's
ACTUAL footprint -> leave full size (e.g. streets). Otherwise binary-search the LARGEST scale s (least
shrink) toward the viewBox bottom-left such that the content clears the badge box (with a small gap).
Apply that exact s. Badge itself is untouched (stays top-right).
  python3 smart_shrink_plurals.py --test    # sardines/streets/+ samples -> scratch renders
  python3 smart_shrink_plurals.py           # dry-run: distribution of needed shrink
  python3 smart_shrink_plurals.py --apply
"""
import glob, os, re, sys, subprocess, tempfile
import numpy as np
from PIL import Image
FLEX = "/Users/paulblenkhorn/Desktop/Fleximbols"; DEST = f"{FLEX}/Plurals and tenses"
RSVG = "/opt/homebrew/bin/rsvg-convert"; MAGICK = "/opt/homebrew/bin/magick"; R = 256
SC = ("/private/tmp/claude-501/-Users-paulblenkhorn-Documents-Development-PWAs-To-do-next-Music/"
      "73b341ae-9fc3-416e-8cc5-6df32ec6dd95/scratchpad/smartshrink")
BADGE_RE = re.compile(r'<g transform="[^"]*scale\(0\.2812\)[^"]*">.*?</g>', re.S)
VB = re.compile(r'viewBox="\s*([-\d.]+)[ ,]+([-\d.]+)[ ,]+([-\d.]+)[ ,]+([-\d.]+)')

def rmask(svg):
    with tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False) as f: f.write(svg); t = f.name
    p = t + ".png"; subprocess.run([RSVG,'-w',str(R),'-h',str(R),t,'-o',p], capture_output=True)
    try: a = np.array(Image.open(p).convert('RGBA').split()[3]) > 16
    except Exception: a = np.zeros((R, R), bool)
    for x in (t, p):
        try: os.remove(x)
        except OSError: pass
    return a

# badge box in render px (once), with small clearance margin
_badge = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><g transform="translate(360 8) '
 'scale(0.2812)"><path d="M 256,56 L 281,212.7 L 429.2,156 L 306,256 L 429.2,356 L 281,299.3 L 256,456 '
 'L 231,299.3 L 82.8,356 L 206,256 L 82.8,156 L 231,212.7 Z" fill="#000"/></g></svg>')
_ys, _xs = np.where(rmask(_badge)); MARG = 9
BX0, BY0, BX1, BY1 = _xs.min()-MARG, _ys.min()-MARG, _xs.max()+MARG, _ys.max()+MARG

def split(text):
    m = re.search(r'(<svg[^>]*>)(.*)(</svg>\s*)$', text, re.S)
    if not m: return None
    head, inner, tail = m.groups()
    bm = BADGE_RE.search(inner)
    if not bm: return None
    body = inner[:bm.start()] + inner[bm.end():]
    return head, body, bm.group(0), tail

def min_shrink(mask):
    ys, xs = np.where(mask)
    if len(xs) == 0: return 1.0
    def clears(sc):
        X = sc*xs; Y = R - sc*(R - ys)
        return not ((X >= BX0) & (X <= BX1) & (Y >= BY0) & (Y <= BY1)).any()
    if clears(1.0): return 1.0
    lo, hi = 0.62, 1.0
    if not clears(lo): return round(lo, 4)     # even the cap can't clear (extreme full-frame)
    for _ in range(22):
        mid = (lo + hi) / 2
        if clears(mid): lo = mid
        else: hi = mid
    return round(lo, 4)

def process(text):
    parts = split(text)
    if not parts: return text, None
    head, body, badge, tail = parts
    s = min_shrink(rmask(head + body + tail))
    if s >= 0.985:
        return f'{head}{body}{badge}{tail}', 1.0            # full size — badge over empty corner
    m = VB.search(head); minx, miny, w, h = (map(float, m.groups()) if m else (0, 0, 512, 512))
    minx, miny, w, h = (minx, miny, w, h) if m else (0.0, 0.0, 512.0, 512.0)
    ax, ay = minx, miny + h                                  # shrink toward viewBox bottom-left
    tx, ty = ax*(1-s), ay*(1-s)
    wrap = f'<g transform="translate({tx:.3f},{ty:.3f}) scale({s})">'
    return f'{head}{wrap}{body}</g>{badge}{tail}', s

def render(path, out):
    subprocess.run([RSVG,'-w','200','-h','200','-b','#fff',path,'-o',out], capture_output=True)

def main():
    badge_plurals = [p for p in glob.glob(f"{DEST}/**/*.svg", recursive=True)
                     if "scale(0.2812)" in open(p, encoding="utf-8", errors="ignore").read()]
    if "--test" in sys.argv:
        os.makedirs(SC, exist_ok=True)
        names = ["sardines","streets","froglets","baboons","extinguishers","fuji apples","tubes","bike sheds"]
        tiles = []
        for nm in names:
            g = [p for p in glob.glob(f"{DEST}/**/{nm}.svg", recursive=True)]
            if not g: continue
            p = g[0]; txt = open(p, encoding="utf-8").read()
            out, s = process(txt)
            cur = f"{SC}/{nm}_cur.png"; render(p, cur)
            fx = f"{SC}/{nm}_fix.svg"; open(fx, "w").write(out); fxp = f"{SC}/{nm}_fix.png"; render(fx, fxp)
            tiles += ["-label", f"{nm} NOW", cur, "-label", f"{nm} s={s}", fxp]
        subprocess.run([MAGICK,"montage",*tiles,"-tile","4x","-geometry","200x200+3+15","-pointsize","10",
                        "-title","Each pair: NOW (obscured/full) | FIXED (minimal shrink)", f"{SC}/test.png"], capture_output=True)
        print("test sheet:", f"{SC}/test.png")
        return
    apply = "--apply" in sys.argv
    import collections
    dist = collections.Counter(); changed = 0
    for p in badge_plurals:
        txt = open(p, encoding="utf-8", errors="ignore").read()
        out, s = process(txt)
        if s is None: continue
        bucket = "full(1.0)" if s >= 0.985 else (">=0.85" if s >= 0.85 else (">=0.72" if s >= 0.72 else "<0.72"))
        dist[bucket] += 1
        if out != txt:
            changed += 1
            if apply: open(p, "w").write(out)
    print(f"badge-plurals: {len(badge_plurals)} | changed: {changed}")
    print("shrink distribution:", dict(dist))
    print("APPLIED" if apply else "DRY-RUN")

if __name__ == "__main__":
    main()
