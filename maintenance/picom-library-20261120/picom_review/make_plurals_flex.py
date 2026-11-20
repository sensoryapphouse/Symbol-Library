#!/usr/bin/env python3
"""Fleximbols-scoped, viewBox-SAFE plural generator. Adds the green 12-point asterisk badge to a
singular noun's drawing, anchored to the file's OWN viewBox top-right (the tense-clock lesson), with a
per-file UNIQUE gradient id. Collision-aware: only shrink+nudge the drawing if it actually has ink in
the badge zone (else leave full size). Returns the new SVG string; writes nothing itself.
Reuses tense_annotate._VB/_num/_zone_inked."""
import re, importlib
import tense_annotate as TA
importlib.reload(TA)

_BADGE = (
    '<g transform="translate(360 8) scale(0.2812)">'
    '<defs><radialGradient id="{gid}" cx="40%" cy="35%" r="65%">'
    '<stop offset="0%" stop-color="#7ed957"/><stop offset="100%" stop-color="#3aa324"/>'
    '</radialGradient></defs>'
    '<path d="M 256.0,56.0 L 281.0,212.7 L 429.2,156.0 L 306.0,256.0 L 429.2,356.0 '
    'L 281.0,299.3 L 256.0,456.0 L 231.0,299.3 L 82.8,356.0 L 206.0,256.0 '
    'L 82.8,156.0 L 231.0,212.7 Z" fill="url(#{gid})" stroke="#1a1a1a" '
    'stroke-width="14" stroke-linejoin="round"/></g>'
)

def anchored_badge(head, gid):
    badge = _BADGE.format(gid=gid)
    m = TA._VB.search(head or "")
    if not m: return badge
    minx, miny, w, h = map(float, m.groups())
    if abs(minx) < 1e-6 and abs(miny) < 1e-6 and abs(w-512) < 1e-6 and abs(h-512) < 1e-6:
        return badge
    sx, sy = w/512.0, h/512.0
    scale = f"scale({TA._num(sx)})" if abs(sx-sy) < 1e-6 else f"scale({TA._num(sx)},{TA._num(sy)})"
    return badge.replace('<g transform="', f'<g transform="translate({TA._num(minx)},{TA._num(miny)}) {scale} ', 1)

def make_plural(src_path, gid):
    s = open(src_path, encoding="utf-8", errors="ignore").read()
    mo = re.search(r'(<svg[^>]*>)(.*)(</svg>\s*)$', s, re.S)
    if mo:
        head, body, tail = mo.group(1), mo.group(2), mo.group(3)
    else:
        om = re.search(r'<svg[^>]*>', s, re.S); ci = s.rfind("</svg>")
        if not om or ci < 0: return None
        head, body, tail = s[:om.end()], s[om.end():ci], s[ci:]
    # Build full-size (badge overlaid top-right), then apply the CONTENT-AWARE MINIMAL shrink:
    # smart_shrink only shrinks — by the least amount, toward the viewBox bottom-left — when content
    # actually sits under the asterisk's real footprint (else full size). Fixes both failure modes:
    # blanket 0.72 shrink (streets, unnecessary) and no-shrink overlay (sardines, obscured).
    full = f'{head}{body}{anchored_badge(head, gid)}{tail}'
    try:
        import smart_shrink_plurals as _SS
        return _SS.process(full)[0]
    except Exception:
        return full
