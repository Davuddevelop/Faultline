#!/usr/bin/env python3
"""Draw Teeter's mark and wordmark from their geometry.

Nothing in the identity is drawn by eye. Everything is computed here and
written to teeter/brand/ as SVG, so the files can be regenerated and checked:

    python3 tools/build_brand.py

THE MARK is a 7 x 10 block standing on one corner. A rectangle pivoting on a
corner tips over when its centre of mass passes outside that corner, which
happens at theta_c = arctan(width / height). For 7 x 10 that is
arctan(0.7) = 34.99 degrees, and at exactly that angle the diagonal through
the pivot is vertical: the centre of mass sits directly above the corner, and
any further rotation lets it fall. 35 degrees is also the harness's real
failure threshold, `tilt_deg > 35.0`. The mark is a picture of the condition
the product exists to find.

THE WORDMARK is built on the same 10-unit height as the block, so the block's
long side and the cap height are the same length. The leg of the R leans at
the same 35 degrees.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "teeter" / "brand"

# ── the block ────────────────────────────────────────────────────────────
W_BLOCK, H_BLOCK = 7.0, 10.0
THETA = math.atan2(W_BLOCK, H_BLOCK)          # critical tipping angle
C, S = math.cos(THETA), math.sin(THETA)
DIAG = math.hypot(W_BLOCK, H_BLOCK)           # sqrt(149)


def block_corners():
    """Corners in maths coordinates (y up), pivot at the origin.

    Upright, the block's bottom-right corner is the pivot and the block
    extends to the left. Rotating clockwise by THETA puts the far corner
    directly above the pivot."""
    def rot(x, y):
        return (x * C + y * S, -x * S + y * C)
    pivot = (0.0, 0.0)
    left = rot(-W_BLOCK, 0.0)
    top = rot(-W_BLOCK, H_BLOCK)
    right = rot(0.0, H_BLOCK)
    return pivot, left, top, right


PIVOT, LEFT, TOP, RIGHT = block_corners()
CENTROID = (0.0, DIAG / 2.0)

assert abs(TOP[0]) < 1e-12, "far corner must be directly above the pivot"
assert abs(math.degrees(THETA) - 34.992) < 0.001


def f(v: float) -> str:
    """Compact, stable number formatting for SVG."""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def to_svg(pt, ox, oy):
    """Maths coordinates to SVG coordinates (y down) about an origin."""
    return (ox + pt[0], oy - pt[1])


def poly(points) -> str:
    return "M" + " L".join(f"{f(x)},{f(y)}" for x, y in points) + " Z"


# ── the wordmark ─────────────────────────────────────────────────────────
CAP = 10.0       # cap height, equal to the block's long side
V = 1.5          # vertical stem
HZ = 1.28        # horizontal stroke, thinner so it reads as the same weight
MID_TOP = 4.08   # middle arm of E and bowl floor of R, optically above centre
MID_BOT = MID_TOP + HZ
LEG = math.radians(35.0)


def glyph_T(x0):
    w = 10.2
    sx = x0 + (w - V) / 2
    shapes = [
        poly([(x0, 0), (x0 + w, 0), (x0 + w, HZ), (x0, HZ)]),
        poly([(sx, 0), (sx + V, 0), (sx + V, CAP), (sx, CAP)]),
    ]
    return shapes, w


def glyph_E(x0):
    w = 8.3
    shapes = [
        poly([(x0, 0), (x0 + V, 0), (x0 + V, CAP), (x0, CAP)]),
        poly([(x0, 0), (x0 + w, 0), (x0 + w, HZ), (x0, HZ)]),
        poly([(x0, MID_TOP), (x0 + w - 0.75, MID_TOP), (x0 + w - 0.75, MID_BOT), (x0, MID_BOT)]),
        poly([(x0, CAP - HZ), (x0 + w + 0.1, CAP - HZ), (x0 + w + 0.1, CAP), (x0, CAP)]),
    ]
    return shapes, w + 0.1


def glyph_R(x0):
    w = 9.3
    ro = 2.55                      # outer bowl radius
    ri = max(ro - V, 0.45)         # counter radius
    yb = MID_BOT                   # bowl floor, outer edge
    k = 0.5523                     # cubic approximation of a quarter circle
    # bowl: outer contour clockwise, counter anticlockwise, filled evenodd
    ox, oy = x0, 0.0
    outer = (
        f"M{f(ox)},{f(oy)} L{f(x0 + w - ro)},{f(oy)} "
        f"C{f(x0 + w - ro + ro * k)},{f(oy)} {f(x0 + w)},{f(ro - ro * k)} {f(x0 + w)},{f(ro)} "
        f"L{f(x0 + w)},{f(yb - ro)} "
        f"C{f(x0 + w)},{f(yb - ro + ro * k)} {f(x0 + w - ro + ro * k)},{f(yb)} {f(x0 + w - ro)},{f(yb)} "
        f"L{f(x0)},{f(yb)} Z"
    )
    ix0, iy0, ix1, iy1 = x0 + V, HZ, x0 + w - V, yb - HZ
    inner = (
        f"M{f(ix0)},{f(iy0)} L{f(ix0)},{f(iy1)} L{f(ix1 - ri)},{f(iy1)} "
        f"C{f(ix1 - ri + ri * k)},{f(iy1)} {f(ix1)},{f(iy1 - ri * k)} {f(ix1)},{f(iy1 - ri)} "
        f"L{f(ix1)},{f(iy0 + ri)} "
        f"C{f(ix1)},{f(iy0 + ri - ri * k)} {f(ix1 - ri + ri * k)},{f(iy0)} {f(ix1 - ri)},{f(iy0)} Z"
    )
    stem = poly([(x0, 0), (x0 + V, 0), (x0 + V, CAP), (x0, CAP)])
    # leg: right edge runs from the baseline at the bowl's outer edge up at
    # 35 degrees from vertical; thickness measured perpendicular equals V
    hw = V / math.cos(LEG)
    run = (CAP - MID_TOP) * math.tan(LEG)
    xr_base = x0 + w + 0.15
    leg = poly([
        (xr_base - run - hw, MID_TOP), (xr_base - run, MID_TOP),
        (xr_base, CAP), (xr_base - hw, CAP),
    ])
    return [outer + " " + inner, stem, leg], w + 0.15


GLYPHS = {"T": glyph_T, "E": glyph_E, "R": glyph_R}
# Spacing between glyph boxes. Set by eye once against a rendered sheet,
# then fixed: wide on purpose, so the name reads as a label on a drawing.
KERN = {("T", "E"): 2.79, ("E", "E"): 3.69, ("E", "T"): 2.25, ("E", "R"): 3.69}


def wordmark(x0=0.0, y0=0.0, word="TEETER", boxes=None):
    shapes, x = [], x0
    for i, ch in enumerate(word):
        s, w = GLYPHS[ch](x)
        shapes += [(p, ch == "R" and j == 0) for j, p in enumerate(s)]
        if boxes is not None:
            boxes.append((ch, x, w))
        x += w
        if i + 1 < len(word):
            x += KERN[(ch, word[i + 1])]
    return shapes, x - x0


# ── the construction drawing (sheet TT-001) ─────────────────────────────
def construction(u=26.0, px=252.0, py=362.0):
    """The mark drawn as an engineering drawing, line types after ISO 128:

      thick continuous            the block, and the ground
      thin continuous             dimensions, extension lines, hatching
      long-dashed double-dotted   the centroidal line, and the block's
                                  upright position: ISO 128 uses this one
                                  line type for both centroids and for the
                                  alternative positions of a movable part

    Returns SVG markup (no wrapper) using classes the page styles."""
    def P(x, y):                       # module coordinates, y up -> px
        return (px + x * u, py - y * u)

    def pt(q):
        return f"{f(q[0])},{f(q[1])}"

    out = []
    # ground, and the fixed-support hatching under it at the brand angle
    g0, g1 = P(-9.2, 0), P(8.2, 0)
    out.append(f'<line class="k" x1="{f(g0[0])}" y1="{f(g0[1])}" x2="{f(g1[0])}" y2="{f(g1[1])}"/>')
    depth = 0.62 * u
    dx = depth / math.tan(math.radians(35))
    hs, x = [], g0[0] + dx + 4
    while x < g1[0]:
        hs.append(f"M{f(x)},{f(py)} L{f(x - dx)},{f(py + depth)}")
        x += 0.82 * u
    out.append(f'<path class="ht" d="{" ".join(hs)}"/>')

    # upright position of the block, before it was tipped about P
    ghost = [P(0, 0), P(-W_BLOCK, 0), P(-W_BLOCK, H_BLOCK), P(0, H_BLOCK)]
    out.append(f'<path class="ph" d="M{" L".join(pt(q) for q in ghost)} Z"/>')

    # centroidal line: vertical through P, G and the far corner
    c0, c1 = P(0, -1.25), P(0, DIAG + 1.3)
    out.append(f'<line class="ph" x1="{f(c0[0])}" y1="{f(c0[1])}" x2="{f(c1[0])}" y2="{f(c1[1])}"/>')

    # path of the centre of mass while the block tips: an arc about P that
    # peaks exactly over P, which is the point of no return
    r = DIAG / 2
    a0, a1 = math.atan2(H_BLOCK / 2, -W_BLOCK / 2), math.radians(58)
    s0, s1 = P(r * math.cos(a0), r * math.sin(a0)), P(r * math.cos(a1), r * math.sin(a1))
    out.append(f'<path class="n arc" d="M{pt(s0)} A{f(r * u)},{f(r * u)} 0 0 1 {pt(s1)}" marker-end="url(#ah)"/>')

    # the tipped block itself, grouped with its centre of mass so a page can
    # rotate the group back to upright and replay the tip about P
    blk = [P(*PIVOT), P(*LEFT), P(*TOP), P(*RIGHT)]
    out.append(f'<g class="tip" style="transform-origin:{f(px)}px {f(py)}px">'
               f'<path class="k" d="M{" L".join(pt(q) for q in blk)} Z"/>')

    # centre-of-gravity symbols: tipped G (solid) and upright G0 (phantom)
    def cg(c, rad, solid):
        cx, cy = c
        k = "cg" if solid else "cg ph0"
        q = (f'<circle class="{k}" cx="{f(cx)}" cy="{f(cy)}" r="{f(rad)}"/>')
        if solid:
            q += (f'<path class="cgf" d="M{f(cx)},{f(cy)} L{f(cx + rad)},{f(cy)} '
                  f'A{f(rad)},{f(rad)} 0 0 0 {f(cx)},{f(cy - rad)} Z '
                  f'M{f(cx)},{f(cy)} L{f(cx - rad)},{f(cy)} '
                  f'A{f(rad)},{f(rad)} 0 0 0 {f(cx)},{f(cy + rad)} Z"/>')
        return q
    G = P(*CENTROID)
    G0 = P(-W_BLOCK / 2, H_BLOCK / 2)
    out.append(cg(G, 6.5, True) + "</g>")
    out.append(cg(G0, 4.5, False))

    # dimensions on the upright position, where they can be axis-aligned
    def dim(a, b, label, side, rot=0):
        (x1, y1), (x2, y2) = a, b
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        tx, ty = mx + side[0], my + side[1]
        tr = f' transform="rotate({rot} {f(tx)} {f(ty)})"' if rot else ""
        return (f'<line class="n" x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" '
                f'marker-start="url(#ah)" marker-end="url(#ah)"/>'
                f'<text class="dim" x="{f(tx)}" y="{f(ty)}" text-anchor="middle"{tr}>{label}</text>')

    yd = P(0, DIAG + 0.75)[1]
    for xx in (-W_BLOCK, 0):
        e0, e1 = P(xx, H_BLOCK + 0.25), P(xx, DIAG + 1.05)
        out.append(f'<line class="n" x1="{f(e0[0])}" y1="{f(e0[1])}" x2="{f(e1[0])}" y2="{f(e1[1])}"/>')
    out.append(dim((P(-W_BLOCK, 0)[0], yd), (P(0, 0)[0], yd), "7", (0, -6)))

    xd = P(-W_BLOCK - 1.25, 0)[0]
    for yy in (0, H_BLOCK):
        e0, e1 = P(-W_BLOCK - 0.25, yy), P(-W_BLOCK - 1.55, yy)
        out.append(f'<line class="n" x1="{f(e0[0])}" y1="{f(e0[1])}" x2="{f(e1[0])}" y2="{f(e1[1])}"/>')
    out.append(dim((xd, P(0, 0)[1]), (xd, P(0, H_BLOCK)[1]), "10", (-7, 0), rot=-90))

    # the angle: base edge off the ground, which is the tilt itself
    ra = 3.6
    e = P(ra * math.cos(math.pi - THETA), ra * math.sin(math.pi - THETA))
    g = P(-ra, 0)
    moving = []                      # hidden while a page replays the tip
    moving.append(f'<path class="n" d="M{pt(g)} A{f(ra * u)},{f(ra * u)} 0 0 1 {pt(e)}" '
                  f'marker-start="url(#ah)" marker-end="url(#ah)"/>')
    tpos = P(-(ra + 1.05) * math.cos(THETA / 2), (ra + 1.05) * math.sin(THETA / 2))
    moving.append(f'<text class="dim" x="{f(tpos[0])}" y="{f(tpos[1] + 4)}" text-anchor="end">34.99°</text>')

    # labels
    def lab(q, text, dx=0, dy=0, anchor="start", cls="lab"):
        return (f'<text class="{cls}" x="{f(q[0] + dx)}" y="{f(q[1] + dy)}" '
                f'text-anchor="{anchor}">{text}</text>')
    moving.append(lab(G, "G", 12, -9))
    out.append(f'<text class="lab" x="{f(G0[0] - 9)}" y="{f(G0[1] - 8)}" text-anchor="end">G<tspan class="sub" dy="3">0</tspan></text>')
    out.append(lab(P(0, 0), "P", 9, -8))
    under = P((r - 1.05) * math.cos(math.radians(70)), (r - 1.05) * math.sin(math.radians(70)))
    out.append(lab(under, "path of G", 0, 4, "middle"))
    moving.append(lab(P(*TOP), "T", 9, 2))
    out.append('<g class="dimA">' + "".join(moving) + "</g>")

    defs = ('<defs><marker id="ah" viewBox="0 0 10 6" refX="9.5" refY="3" '
            'markerWidth="9" markerHeight="5.4" orient="auto-start-reverse" '
            'markerUnits="userSpaceOnUse"><path d="M0,0 L10,3 L0,6 Z" class="ahf"/></marker></defs>')
    return defs + "".join(out)


CONSTRUCTION_CSS = """
.k{fill:none;stroke:#E9E6DE;stroke-width:2;stroke-linejoin:miter}
.n{fill:none;stroke:#B5B1A8;stroke-width:1}
.ht{fill:none;stroke:#8E8B83;stroke-width:1}
.ph{fill:none;stroke:#B5B1A8;stroke-width:1;stroke-dasharray:18 3 1.5 3 1.5 3}
.cg{fill:#0B0B0A;stroke:#E9E6DE;stroke-width:1.4}.cg.ph0{stroke:#B5B1A8;stroke-width:1;fill:#0B0B0A}
.cgf{fill:#E9E6DE}.ahf{fill:#B5B1A8}
.dim{font:500 12px "B612 Mono",ui-monospace,monospace;fill:#E9E6DE}
.lab{font:400 11px "B612 Mono",ui-monospace,monospace;fill:#B5B1A8}
"""


# ── sheet TT-003: the wordmark, dimensioned ──────────────────────────────
def wordmark_construction(k=12.0, mx=78.0, my=40.0):
    """The wordmark at k px per module with its guides and dimensions."""
    boxes = []
    shapes, ww = wordmark(boxes=boxes)
    W, H = mx + ww * k + 40, my + CAP * k + 96
    X = lambda u: mx + u * k
    Y = lambda u: my + u * k
    o = [f'<g transform="translate({f(mx)} {f(my)}) scale({f(k)})">{paths(shapes, "currentColor")}</g>']
    # horizontal guides across the whole word
    for y, name in ((0, "cap 10.00"), (MID_TOP, f"arm {CAP - MID_TOP:.2f}"), (MID_BOT, f"{CAP - MID_BOT:.2f}"), (CAP, "base 0.00")):
        o.append(f'<line class="gd" x1="{f(mx - 10)}" y1="{f(Y(y))}" x2="{f(W - 12)}" y2="{f(Y(y))}"/>')
        o.append(f'<text class="lab" x="{f(mx - 14)}" y="{f(Y(y) + 3.5)}" text-anchor="end">{name}</text>')
    # stem width on the first E
    _, ex, _ = boxes[1]
    yy = Y(CAP) + 24
    for xx in (ex, ex + V):
        o.append(f'<line class="n" x1="{f(X(xx))}" y1="{f(Y(CAP) + 6)}" x2="{f(X(xx))}" y2="{f(yy + 6)}"/>')
    o.append(f'<line class="n" x1="{f(X(ex) - 24)}" y1="{f(yy)}" x2="{f(X(ex))}" y2="{f(yy)}" marker-end="url(#ah2)"/>')
    o.append(f'<line class="n" x1="{f(X(ex + V) + 24)}" y1="{f(yy)}" x2="{f(X(ex + V))}" y2="{f(yy)}" marker-end="url(#ah2)"/>')
    o.append(f'<text class="dim sm" x="{f(X(ex + V) + 30)}" y="{f(yy + 4)}">stem {V:.2f}</text>')
    # spacing between glyphs, below the baseline
    ys = Y(CAP) + 62
    for (c1, x1, w1), (c2, x2, _w2) in zip(boxes, boxes[1:]):
        a, b2 = X(x1 + w1), X(x2)
        o.append(f'<line class="n" x1="{f(a)}" y1="{f(ys)}" x2="{f(b2)}" y2="{f(ys)}" marker-start="url(#ah2)" marker-end="url(#ah2)"/>')
        for xx in (a, b2):
            o.append(f'<line class="n" x1="{f(xx)}" y1="{f(ys - 9)}" x2="{f(xx)}" y2="{f(ys + 4)}"/>')
        o.append(f'<text class="dim sm" x="{f((a + b2) / 2)}" y="{f(ys + 19)}" text-anchor="middle">{KERN[(c1, c2)]:.2f}</text>')
    # the R's leg at the brand angle, measured from the vertical at its foot
    _, rx, rw = boxes[-1]
    base_x = X(rx + rw)
    o.append(f'<line class="gd" x1="{f(base_x)}" y1="{f(Y(CAP))}" x2="{f(base_x)}" y2="{f(Y(MID_TOP) - 8)}"/>')
    ra = 50
    ex_, ey_ = base_x - ra * math.sin(LEG), Y(CAP) - ra * math.cos(LEG)
    o.append(f'<path class="n" d="M{f(base_x)},{f(Y(CAP) - ra)} A{ra},{ra} 0 0 0 {f(ex_)},{f(ey_)}" marker-start="url(#ah2)" marker-end="url(#ah2)"/>')
    o.append(f'<text class="dim" x="{f(base_x + 9)}" y="{f(Y(CAP) - ra + 2)}">35°</text>')
    defs = ('<defs><marker id="ah2" viewBox="0 0 10 6" refX="9.5" refY="3" markerWidth="9" markerHeight="5.4" '
            'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,0 L10,3 L0,6 Z" class="ahf"/></marker></defs>')
    return (f'<svg class="draw" viewBox="0 0 {f(W)} {f(H)}" role="img" aria-label="The wordmark on its '
            f'construction grid: cap height 10 modules, stem {V}, the spacing between letters, and the R leg at 35 degrees.">'
            f'{defs}{"".join(o)}</svg>')


# ── figures from the real campaign, in Teeter's drawing style ───────────
def hatch_pattern(pid, spacing=6.0, cls="hp"):
    """Section hatching at 35 degrees: horizontal lines rotated -35."""
    return (f'<pattern id="{pid}" width="{spacing}" height="{spacing}" patternUnits="userSpaceOnUse" '
            f'patternTransform="rotate(-35)"><line class="{cls}" x1="0" y1="0.5" x2="{spacing}" y2="0.5"/></pattern>')


def trace_figure(sim, campaign, pid="hx-trace", w=760, h=300, small=False):
    hz = sim["hz"]
    nom, mini = sim["runs"]["nominal"]["tilt"], sim["runs"]["minimal"]["tilt"]
    thr = next(p for p in campaign["report"]["predicates"] if p["name"] == "tilt_limit")["threshold"]
    dur = (len(mini) - 1) / hz
    l, r, t, b = (6, w - 6, 6, h - 6) if small else (64, w - 16, 30, h - 40)
    X = lambda sec: l + sec / dur * (r - l)
    Y = lambda d: b - d / 180.0 * (b - t)
    pts = lambda series: " L".join(f"{f(X(i / hz))},{f(Y(v))}" for i, v in enumerate(series))
    i_b = next(i for i, v in enumerate(mini) if v > thr)
    tb = i_b / hz
    o = [f'<defs>{hatch_pattern(pid, 5.0 if small else 6.0)}</defs>']
    o.append(f'<rect class="fail-zone" x="{f(l)}" y="{f(t)}" width="{f(r - l)}" height="{f(Y(thr) - t)}" fill="url(#{pid})"/>')
    if not small:
        for d in (90, 135, 180):
            o.append(f'<line class="grid" x1="{f(l)}" y1="{f(Y(d))}" x2="{f(r)}" y2="{f(Y(d))}"/>')
        for d in (0, 35, 90, 135, 180):
            o.append(f'<text class="tick" x="{f(l - 9)}" y="{f(Y(d) + 3.5)}" text-anchor="end">{d}</text>')
        for sec in range(int(dur) + 1):
            o.append(f'<text class="tick" x="{f(X(sec))}" y="{f(b + 18)}" text-anchor="middle">{sec}</text>')
        o.append(f'<line class="axis" x1="{f(l)}" y1="{f(t)}" x2="{f(l)}" y2="{f(b)}"/>')
        o.append(f'<line class="axis" x1="{f(l)}" y1="{f(b)}" x2="{f(r)}" y2="{f(b)}"/>')
        o.append(f'<text class="unit" x="{f(r)}" y="{f(b + 34)}" text-anchor="end">time · s</text>')
        o.append(f'<text class="unit" x="{f(l)}" y="{f(t - 12)}">tilt_deg</text>')
    o.append(f'<line class="limit" x1="{f(l)}" y1="{f(Y(thr))}" x2="{f(r)}" y2="{f(Y(thr))}"/>')
    o.append(f'<path class="tr-calm" pathLength="1" d="M{pts(nom)}"/>')
    o.append(f'<path class="tr-fail" pathLength="1" d="M{pts(mini)}"/>')
    bx, by = X(tb), Y(thr)
    trail = [(X(i / hz), Y(v)) for i, v in enumerate(mini)]
    run_ = [math.dist(a, b) for a, b in zip(trail, trail[1:])]
    hit = sum(run_[:i_b]) / sum(run_)
    o.append(f'<rect class="breach" x="{f(bx - 4)}" y="{f(by - 4)}" width="8" height="8" transform="rotate(45 {f(bx)} {f(by)})"/>')
    if not small:
        o.append(f'<text class="lab" x="{f(r)}" y="{f(Y(thr) - 9)}" text-anchor="end">tilt_deg &gt; {thr:g} · failed</text>')
        o.append(f'<text class="lab hi" x="{f(bx + 12)}" y="{f(by + 17)}">breach {tb:.2f} s</text>')
        o.append(f'<text class="lab" x="{f(r)}" y="{f(Y(0) - 9)}" text-anchor="end">nominal · peak {max(nom):.2f}°</text>')
    label = (f"Measured body tilt over {dur:.0f} seconds. The undisturbed run peaks at {max(nom):.2f} degrees. "
             f"The smallest failing push crosses {thr:g} degrees at {tb:.2f} seconds and keeps going over.")
    return (f'<svg class="fig{" fig--small" if small else ""}" viewBox="0 0 {w} {h}" role="img" '
            f'style="--hit-frac:{hit:.4f}" aria-label="{label}">{"".join(o)}</svg>')


def reduction_figure(campaign, pid="hx-red", w=760, h=176):
    mode = campaign["report"]["modes"][0]
    axis = mode["required"][0]
    ax = campaign["report"]["coverage"]["per_axis"][axis]
    lo, hi = ax["declared_min"], ax["declared_max"]
    fails = [p["x"] for p in campaign["scatter"]["points"] if p["f"]]
    f_lo, f_hi, m = min(fails), max(fails), mode["minimal"][axis]
    l, r, yb = 26, w - 26, 118
    X = lambda v: l + (v - lo) / (hi - lo) * (r - l)
    o = [f'<defs>{hatch_pattern(pid, 5.0)}</defs>']
    o.append(f'<line class="axis" x1="{f(l)}" y1="{yb}" x2="{f(r)}" y2="{yb}"/>')
    for v in range(int(lo), int(hi) + 1):
        o.append(f'<line class="axis" x1="{f(X(v))}" y1="{yb}" x2="{f(X(v))}" y2="{yb + 7}"/>')
        o.append(f'<text class="tick" x="{f(X(v))}" y="{yb + 22}" text-anchor="middle">{v}</text>')
    o.append(f'<rect class="fail-band" x="{f(X(f_lo))}" y="{yb - 26}" width="{f(X(f_hi) - X(f_lo))}" height="26" fill="url(#{pid})"/>')
    o.append(f'<rect class="fail-edge" x="{f(X(f_lo))}" y="{yb - 26}" width="{f(X(f_hi) - X(f_lo))}" height="26"/>')
    o.append(f'<line class="minimal" x1="{f(X(m))}" y1="{yb - 44}" x2="{f(X(m))}" y2="{yb}"/>')
    o.append(f'<circle class="minimal-dot" cx="{f(X(m))}" cy="{yb - 44}" r="3.5"/>')
    o.append(f'<text class="lab hi" x="{f(X(m) - 10)}" y="{yb - 40}" text-anchor="end">reduced to {m:g}</text>')
    # the band's label sits a row higher, with a leader down to the band
    bx_ = (X(f_lo) + X(f_hi)) / 2
    o.append(f'<path d="M{f(bx_)},{yb - 27} L{f(bx_)},{yb - 70}" fill="none" stroke="var(--ink-3)" stroke-width="1"/>')
    o.append(f'<text class="lab" x="{f(bx_ + 2)}" y="{yb - 78}" text-anchor="end">sampled failures {f_lo:.3f}–{f_hi:.3f}</text>')
    o.append(f'<text class="unit" x="{f(r)}" y="{yb + 44}" text-anchor="end">push_impulse_ns · requested · N·s</text>')
    label = (f"Every sampled failure needed at least {f_lo:.3f} newton-seconds. Reduction then proved the policy "
             f"falls at a requested {m:g}, below anything the search had sampled.")
    return (f'<svg class="fig" viewBox="0 0 {w} {h}" role="img" style="--walk:{f(X(f_lo) - X(m))}px" '
            f'aria-label="{label}">{"".join(o)}</svg>')


# ── inject generated pieces into hand-written pages ─────────────────────
def inject(page: Path, pieces: dict) -> list:
    """Replace <!-- gen:name -->…<!-- /gen:name --> regions; returns names used."""
    import re as _re
    html, used = page.read_text(), []
    for name, markup in pieces.items():
        start, end = f"<!-- gen:{name} -->", f"<!-- /gen:{name} -->"
        if start not in html:
            continue
        html = _re.sub(_re.escape(start) + r".*?" + _re.escape(end),
                       lambda m: start + markup + end, html, flags=_re.S)
        used.append(name)
    page.write_text(html)
    return used


# ── pieces for the identity standard page ───────────────────────────────
def inline(viewbox, body, label=None, cls=""):
    """An SVG for inlining in a page: no ids that could collide."""
    c = f' class="{cls}"' if cls else ""
    a = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true" focusable="false"'
    return f'<svg{c} xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" {a}>{body}</svg>'


def block_at(angle_deg, ox, oy, fill="currentColor", outline=False, ground=True, hatch=True):
    """The block rotated to any angle about its pivot, for the misuse sheet."""
    a = math.radians(angle_deg)
    c_, s_ = math.cos(a), math.sin(a)
    rot = lambda x, y: (x * c_ + y * s_, -x * s_ + y * c_)
    pts = [rot(0, 0), rot(-W_BLOCK, 0), rot(-W_BLOCK, H_BLOCK), rot(0, H_BLOCK)]
    d = poly([to_svg(q, ox, oy) for q in pts])
    body = (f'<path d="{d}" fill="none" stroke="{fill}" stroke-width="0.45"/>' if outline
            else f'<path d="{d}" fill="{fill}"/>')
    if ground:
        g = mark_body(ox, oy, fill=fill, hatch=hatch)
        body += g[g.index("<rect"):]                    # keep the ground, drop the block
    return body


def clearspace_svg():
    k = 3.5                                              # half the short side
    x0, x1, y0, y1 = -6.4, 6.4, -1.65, DIAG              # mark bounds, maths coords
    pad = 1.6
    W = (x1 - x0) + 2 * (k + pad)
    H = (y1 - y0) + 2 * (k + pad)
    ox, oy = -x0 + k + pad, y1 + k + pad
    box = f'<rect x="{f(pad)}" y="{f(pad)}" width="{f(W - 2 * pad)}" height="{f(H - 2 * pad)}" fill="none" stroke="var(--ink-3)" stroke-width="0.08" stroke-dasharray="0.5 0.4"/>'
    bound = f'<rect x="{f(ox + x0)}" y="{f(oy - y1)}" width="{f(x1 - x0)}" height="{f(y1 - y0)}" fill="none" stroke="var(--rule)" stroke-width="0.06"/>'
    def dmv(xa, ya, xb, yb, tx, ty, label):
        return (f'<line x1="{f(xa)}" y1="{f(ya)}" x2="{f(xb)}" y2="{f(yb)}" stroke="var(--ink-2)" stroke-width="0.07"/>'
                f'<text x="{f(tx)}" y="{f(ty)}" font-size="1.05" font-family="B612 Mono, monospace" fill="var(--ink-2)" text-anchor="middle">{label}</text>')
    dims = dmv(pad, oy - 5, ox + x0, oy - 5, (pad + ox + x0) / 2, oy - 5.45, "3.5")
    dims += dmv(ox, pad, ox, oy - y1, ox + 1.6, (pad + oy - y1) / 2 + 0.35, "3.5")
    return inline(f"0 0 {f(W)} {f(H)}", box + bound + mark_body(ox, oy) + dims,
                  "The mark with its clear space: 3.5 modules on every side.", "draw cs")


def hatch_spec_svg():
    """Hatching at 1:1 beside a 4:1 detail with its three dimensions."""
    W, H = 560, 214
    o = ['<defs><pattern id="hx-spec" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(-35)">'
         '<line x1="0" y1="0.5" x2="6" y2="0.5" stroke="var(--ink-2)" stroke-width="1"/></pattern>'
         '<clipPath id="cp-det"><circle cx="390" cy="105" r="86"/></clipPath></defs>']
    o.append('<rect x="10" y="30" width="190" height="150" fill="url(#hx-spec)"/>')
    o.append('<rect x="10" y="30" width="190" height="150" fill="none" stroke="var(--ink)" stroke-width="2"/>')
    o.append('<circle cx="150" cy="80" r="22" fill="none" stroke="var(--ink-2)" stroke-width="1"/>')
    o.append('<line x1="170" y1="70" x2="300" y2="50" stroke="var(--ink-2)" stroke-width="1"/>')
    o.append('<text x="10" y="18" class="lab">1 : 1</text>')
    o.append('<text x="160" y="58" class="dim">A</text>')
    # detail at 4:1: pitch 24, line 4
    lines = []
    c, s_ = math.cos(math.radians(35)), math.sin(math.radians(35))
    for i in range(-8, 9):
        # lines rising to the right at 35 deg, perpendicular spacing 24
        nx, ny = -s_, -c                      # unit normal (screen coords, pointing up-left)
        cx, cy = 390 + nx * 24 * i, 105 + ny * 24 * i
        lines.append(f'<line x1="{f(cx - c * 200)}" y1="{f(cy + s_ * 200)}" x2="{f(cx + c * 200)}" y2="{f(cy - s_ * 200)}" stroke="var(--ink)" stroke-width="4"/>')
    o.append('<g clip-path="url(#cp-det)">' + "".join(lines) + '</g>')
    o.append('<circle cx="390" cy="105" r="86" fill="none" stroke="var(--ink-2)" stroke-width="1"/>')
    o.append('<text x="300" y="18" class="lab">detail A · 4 : 1</text>')
    # pitch dimension, perpendicular to the lines, between line 0 and line 1
    nx, ny = -s_, -c
    ax, ay = 390 + 2 * c * 20, 105 - 2 * s_ * 20
    bx, by = ax + nx * 24, ay + ny * 24
    o.append(f'<line x1="{f(ax)}" y1="{f(ay)}" x2="{f(bx)}" y2="{f(by)}" stroke="var(--well)" stroke-width="5"/>')
    o.append(f'<line x1="{f(ax)}" y1="{f(ay)}" x2="{f(bx)}" y2="{f(by)}" stroke="var(--ink)" stroke-width="1" marker-start="url(#ah3)" marker-end="url(#ah3)"/>')
    # leader out of the circle to the pitch value
    mx_, my_ = (ax + bx) / 2, (ay + by) / 2
    o.append(f'<path d="M{f(mx_)},{f(my_)} L486,40 L500,40" fill="none" stroke="var(--ink-3)" stroke-width="1"/>')
    o.append('<text x="504" y="44" class="dim">6 px</text>')
    o.append('<text x="504" y="62" class="lab">pitch</text>')
    o.append('<text x="504" y="160" class="dim">1 px</text>')
    o.append('<text x="504" y="178" class="lab">line</text>')
    o.append('<path d="M452,150 L486,156 L500,156" fill="none" stroke="var(--ink-3)" stroke-width="1"/>')
    o.append('<text x="300" y="206" class="lab">angle 35° · rising to the right</text>')
    defs = ('<defs><marker id="ah3" viewBox="0 0 10 6" refX="9.5" refY="3" markerWidth="8" markerHeight="4.8" '
            'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,0 L10,3 L0,6 Z" class="ahf"/></marker></defs>')
    return inline(f"0 0 {W} {H}", defs + "".join(o),
                  "Section hatching at 35 degrees, 6 pixels apart and 1 pixel thick, shown full size and in a 4 to 1 detail.", "draw")


def dim_anatomy_svg():
    """A dimension, with ISO-style balloons; the page lists what each one is."""
    W, H = 520, 170
    o = ['<rect x="60" y="96" width="320" height="44" fill="none" stroke="var(--ink)" stroke-width="2"/>']
    for x in (60, 380):
        o.append(f'<line x1="{x}" y1="90" x2="{x}" y2="40" stroke="var(--ink-2)" stroke-width="1"/>')
    o.append('<line x1="60" y1="50" x2="380" y2="50" stroke="var(--ink-2)" stroke-width="1" marker-start="url(#ah4)" marker-end="url(#ah4)"/>')
    o.append('<text x="220" y="42" class="dim" text-anchor="middle">7.875 N·s</text>')
    balloons = [((248, 34), (300, 14), "1"), ((150, 50), (130, 18), "2"), ((372, 50), (430, 22), "3"), ((380, 74), (440, 84), "4")]
    for (x1, y1), (bx, by), n in balloons:
        o.append(f'<line x1="{x1}" y1="{y1}" x2="{bx}" y2="{by}" stroke="var(--ink-3)" stroke-width="1"/>')
        o.append(f'<circle cx="{x1}" cy="{y1}" r="1.8" fill="var(--ink-3)"/>')
        o.append(f'<circle cx="{bx}" cy="{by}" r="10" fill="var(--well)" stroke="var(--ink-2)" stroke-width="1"/>')
        o.append(f'<text x="{bx}" y="{by + 4}" class="dim sm" text-anchor="middle">{n}</text>')
    defs = ('<defs><marker id="ah4" viewBox="0 0 10 6" refX="9.5" refY="3" markerWidth="9" markerHeight="5.4" '
            'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,0 L10,3 L0,6 Z" class="ahf"/></marker></defs>')
    return inline(f"0 0 {W} {H}", defs + "".join(o), "Anatomy of a dimension, with numbered balloons.", "draw")


def _dim_anatomy_old():
    W, H = 520, 196
    o = ['<rect x="70" y="92" width="300" height="46" fill="none" stroke="var(--ink)" stroke-width="2"/>']
    for x in (70, 370):
        o.append(f'<line x1="{x}" y1="86" x2="{x}" y2="44" stroke="var(--ink-2)" stroke-width="1"/>')
    o.append('<line x1="70" y1="54" x2="370" y2="54" stroke="var(--ink-2)" stroke-width="1" marker-start="url(#ah4)" marker-end="url(#ah4)"/>')
    o.append('<text x="220" y="47" class="dim" text-anchor="middle">7.875 N·s</text>')
    calls = [((370, 70), (430, 30), "extension line"), ((300, 54), (430, 74), "dimension line"),
             ((366, 54), (430, 118), "arrowhead · filled"), ((248, 44), (430, 162), "value · B612 Mono")]
    for (x1, y1), (x2, y2), t in calls:
        o.append(f'<path d="M{x1},{y1} L{x2 - 14},{y2} L{x2 - 4},{y2}" fill="none" stroke="var(--ink-3)" stroke-width="1"/>')
        o.append(f'<circle cx="{x1}" cy="{y1}" r="2" fill="var(--ink-3)"/>')
        o.append(f'<text x="{x2}" y="{y2 + 4}" class="lab">{t}</text>')
    o.append('<text x="70" y="166" class="lab">Text sits above the line and reads from the bottom or the right.</text>')
    defs = ('<defs><marker id="ah4" viewBox="0 0 10 6" refX="9.5" refY="3" markerWidth="9" markerHeight="5.4" '
            'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,0 L10,3 L0,6 Z" class="ahf"/></marker></defs>')
    return inline(f"0 0 {W} {H}", defs + "".join(o), "Anatomy of a dimension.", "draw")


TONE = [
    ("Graphite 950", "#0B0B0A", "ground"), ("Graphite 900", "#111110", "sheet"),
    ("Graphite 850", "#171716", "well"), ("Graphite 800", "#21211F", "grid"),
    ("Graphite 700", "#34332F", "rule"), ("Graphite 500", "#5F5D57", "line, not text"),
    ("Graphite 400", "#8E8B83", "tertiary text"), ("Graphite 300", "#B5B1A8", "secondary text"),
    ("Vellum 100", "#E9E6DE", "text"), ("Vellum 50", "#F5F3EE", "emphasis"),
]


def _lum(h):
    h = h.lstrip("#")
    ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    ch = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def wedge_html():
    """The step wedge. Each swatch's own label colours are picked so the
    label clears 4.5:1 on that swatch, and the choice is measured, not guessed."""
    tones = [t[1] for t in TONE]
    out = ['<div class="wedge" role="list" aria-label="Tone scale">']
    for name, hx, role in TONE:
        fg = max(("#0B0B0A", "#F5F3EE"), key=lambda c: contrast(c, hx))
        # quietest step on the scale that still reads on this swatch
        quiet = [c for c in tones + ["#4A4843"] if c not in (hx, fg) and contrast(c, hx) >= 4.5]
        mu = min(quiet, key=lambda c: contrast(c, hx)) if quiet else fg
        out.append(
            f'<button class="step" type="button" role="listitem" '
            f'data-hex="{hx}" data-name="{name}" style="background:{hx};color:{fg}" '
            f'aria-label="{name}, {hx}, {contrast(hx, TONE[0][1]):.2f} to 1 on ground, {role}">'
            f'<span class="nm">{name}</span><span>{hx}</span>'
            f'<span style="color:{mu}">{contrast(hx, TONE[0][1]):.2f}&nbsp;:&nbsp;1</span>'
            f'<span style="color:{mu}">{role}</span></button>')
    out.append("</div>")
    return "".join(out)


def modes_rows(campaign):
    rows = []
    for m in campaign["report"]["modes"]:
        mins = " · ".join(f"{k} {v:g}" for k, v in m["minimal"].items())
        rows.append(f'<tr><td>{esc_(m["label"])}</td><td>{m["count"]}</td><td>{esc_(mins)}</td><td>{m["first_t"]:.2f} s</td></tr>')
    return "".join(rows)


def esc_(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def social_svg(lockup_body, lockup_vb_w, lockup_vb_h):
    W, H = 1200, 630
    o = [f'<rect width="{W}" height="{H}" fill="#0B0B0A"/>',
         f'<rect x="24" y="24" width="{W - 48}" height="{H - 48}" fill="none" stroke="#34332F" stroke-width="1"/>']
    # the construction drawing, faint, on the right
    o.append(f'<g transform="translate(610 100)" opacity=".5">{gyro_construction("soc")}</g>')
    lw = 330
    sc = lw / lockup_vb_w
    o.append(f'<g transform="translate(72 74) scale({f(sc)})" fill="#E9E6DE" color="#E9E6DE">{lockup_body}</g>')
    lines = ["We find the exact", "condition where", "your robot falls."]
    for i, ln in enumerate(lines):
        o.append(f'<text x="72" y="{300 + i * 66}" class="soc-h">{ln}</text>')
    o.append('<text x="72" y="560" class="soc-m">Adversarial testing for learned robot policies</text>')
    o.append('<text x="1128" y="560" class="soc-m" text-anchor="end">teeter, v.: to sway at the edge of falling</text>')
    css = ('<style>.soc-h{font-family:Archivo,sans-serif;font-stretch:125%;font-variation-settings:"wdth" 125;'
           'font-weight:500;font-size:56px;fill:#E9E6DE;letter-spacing:-.5px}'
           '.soc-m{font-family:"B612 Mono",monospace;font-size:17px;fill:#8E8B83}'
           '.k{fill:none;stroke:#E9E6DE;stroke-width:2}.n{fill:none;stroke:#B5B1A8;stroke-width:1}'
           '.ht{fill:none;stroke:#8E8B83;stroke-width:1}.ph{fill:none;stroke:#B5B1A8;stroke-width:1;stroke-dasharray:18 3 1.5 3 1.5 3}'
           '.cg{fill:#0B0B0A;stroke:#E9E6DE;stroke-width:1.4}.cg.ph0{stroke:#B5B1A8}.cgf{fill:#E9E6DE}.ahf{fill:#B5B1A8}'
           '.dim{font:400 12px "B612 Mono",monospace;fill:#E9E6DE}.lab{font:400 11px "B612 Mono",monospace;fill:#B5B1A8}.sub{font-size:8px}</style>')
    body = css + "".join(o)
    return body.replace('id="ah"', 'id="ah-soc"').replace("url(#ah)", "url(#ah-soc)")

# ── SVG writers ──────────────────────────────────────────────────────────
def svg(viewbox, body, title, desc=""):
    d = f"<desc>{desc}</desc>" if desc else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" '
            f'role="img" aria-labelledby="t"><title id="t">{title}</title>{d}{body}</svg>\n')


def mark_body(ox, oy, fill="currentColor", gap=0.0, ground=True, hatch=True):
    """The solid mark: the block at its tipping angle, standing on the
    free-body-diagram symbol for a fixed support. A split along the vertical
    diagonal was tried and dropped: it read as a sail on waves."""
    p, l, t, r = (to_svg(q, ox, oy) for q in (PIVOT, LEFT, TOP, RIGHT))
    g = gap / 2
    left_half = poly([(p[0] - g, p[1]), l, (t[0] - g, t[1])])
    right_half = poly([(p[0] + g, p[1]), (t[0] + g, t[1]), r])
    parts = [f'<path d="{left_half} {right_half}" fill="{fill}"/>']
    if ground:
        gw, gt = 6.4, 0.5
        parts.append(f'<rect x="{f(ox - gw)}" y="{f(oy)}" width="{f(2 * gw)}" height="{f(gt)}" fill="{fill}"/>')
        if hatch:
            # the free-body-diagram symbol for a fixed support: short strokes
            # under the ground line, here at the brand angle
            n, step, depth = 7, 1.75, 1.15
            dx = depth / math.tan(math.radians(35.0))
            strokes = []
            for i in range(n):
                x = ox - gw + 0.55 + i * step + dx
                strokes.append(f"M{f(x)},{f(oy + gt)} L{f(x - dx)},{f(oy + gt + depth)}")
            parts.append(f'<path d="{" ".join(strokes)}" stroke="{fill}" stroke-width="0.32" fill="none"/>')
    return "".join(parts)


def paths(shapes, fill="currentColor") -> str:
    """Wordmark shapes to SVG paths; the R's bowl needs evenodd for its counter."""
    out = []
    for d, evenodd in shapes:
        rule = ' fill-rule="evenodd"' if evenodd else ""
        out.append(f'<path d="{d}" fill="{fill}"{rule}/>')
    return "".join(out)


# the revision-A mark's box: the block spans x ±5.73 and y 0..12.21, ground and hatch below
MARK_W, MARK_H = 14.4, 15.6
MARK_OX, MARK_OY = MARK_W / 2, 13.0


# ── revision B: the gyroscope and the machined wordmark ──────────────────
# The symbol is a gyroscope, the sensor a robot balances by: a needle tipped off
# vertical, and a gimbal ring around it that the needle passes in front of at
# the bottom and behind at the top. The wordmark is drawn from rectangles with
# stencil cuts, as lettering is machined into a part. Both are pure geometry.
G_TIP = math.radians(12.0)       # the needle, off vertical
G_RING = math.radians(-24.0)     # the gimbal ring's tilt
G_BOX = 112.0                    # the symbol is drawn in a box centred on 0


def _turn(x, y, a):
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def _spindle(L, w, a, k=.2):
    """A ray tapering to a point at each end, its sides drawn in to the axis."""
    pts = [(0, -L), (w, 0), (0, L), (-w, 0)]
    ctl = [(w * k, -L * k), (w * k, L * k), (-w * k, L * k), (-w * k, -L * k)]
    P = lambda q: _turn(q[0], q[1], a)
    d = "M{},{}".format(*map(f, P(pts[0])))
    for n in range(4):
        c, q = P(ctl[n]), P(pts[(n + 1) % 4])
        d += f" Q{f(c[0])},{f(c[1])} {f(q[0])},{f(q[1])}"
    return d + " Z"


def _ring(rx, ry, tx, ty, a, n=120):
    """An elliptical band, thick at its sides and thin where it turns away."""
    o = [_turn(rx * math.cos(2 * math.pi * k / n), ry * math.sin(2 * math.pi * k / n), a) for k in range(n)]
    i = [_turn((rx - tx) * math.cos(2 * math.pi * k / n), (ry - ty) * math.sin(2 * math.pi * k / n), a) for k in range(n)]
    p = lambda pts: "M" + " L".join(f"{f(x)},{f(y)}" for x, y in pts) + " Z"
    return p(o) + " " + p(i[::-1])


NEEDLE = _spindle(47, 6.4, G_TIP)
RING = _ring(37, 13.5, 7.0, 2.4, G_RING)


def mark_b(uid="g", fill="currentColor", box=32.0, fit=1.0, tip=None, weave=True, outline=False, turn=0.0):
    """The gyroscope in a square box. uid keeps its two mask ids unique. The
    keyword arguments exist to draw what the mark must never be (TT-002)."""
    k = box / G_BOX * fit
    h = G_BOX / 2
    NEEDLE = _spindle(47, 6.4, G_TIP if tip is None else tip)
    if outline:
        sw = 1.4 / k
        return (f'<g transform="translate({f(box / 2)} {f(box / 2)}) scale({f(k)}) rotate({f(turn)})">'
                f'<path d="{RING}" fill="none" stroke="{fill}" stroke-width="{f(sw)}" fill-rule="evenodd"/>'
                f'<path d="{NEEDLE}" fill="none" stroke="{fill}" stroke-width="{f(sw)}"/></g>')
    if not weave:
        return (f'<g transform="translate({f(box / 2)} {f(box / 2)}) scale({f(k)}) rotate({f(turn)})">'
                f'<path d="{RING}" fill="{fill}" fill-rule="evenodd"/><path d="{NEEDLE}" fill="{fill}"/></g>')
    m = (f'<mask id="gr-{uid}" maskUnits="userSpaceOnUse" x="{-h}" y="{-h}" width="{G_BOX}" height="{G_BOX}">'
         f'<rect x="{-h}" y="{-h}" width="{G_BOX}" height="{G_BOX}" fill="#fff"/>'
         f'<path d="{NEEDLE}" fill="#000" stroke="#000" stroke-width="5.5"/>'
         f'<rect x="{-h}" y="{-h}" width="{G_BOX}" height="{h}" fill="#fff"/></mask>'
         f'<mask id="gn-{uid}" maskUnits="userSpaceOnUse" x="{-h}" y="{-h}" width="{G_BOX}" height="{G_BOX}">'
         f'<rect x="{-h}" y="{-h}" width="{G_BOX}" height="{G_BOX}" fill="#fff"/>'
         f'<path d="{RING}" fill="#000" stroke="#000" stroke-width="5.5" fill-rule="evenodd"/>'
         f'<rect x="{-h}" y="0" width="{G_BOX}" height="{h}" fill="#fff"/></mask>')
    return (f'<g transform="translate({f(box / 2)} {f(box / 2)}) scale({f(k)}) rotate({f(turn)})"><defs>{m}</defs>'
            f'<path d="{RING}" fill="{fill}" fill-rule="evenodd" mask="url(#gr-{uid})"/>'
            f'<path d="{NEEDLE}" fill="{fill}" mask="url(#gn-{uid})"/></g>')


# the wordmark, on a cap height of 100: stroke, stencil cut, tracking
W_S, W_G, W_TRACK = 16.0, 6.0, 26.0


def _rect(x, y, w, h):
    return f"M{f(x)},{f(y)} h{f(w)} v{f(h)} h{f(-w)} Z"


def _T(x):
    w = 124.0
    return _rect(x, 0, w, W_S) + _rect(x + w / 2 - W_S / 2 - 1, W_S + W_G, W_S + 2, 100 - W_S - W_G), w


def _E(x):
    w, st = 104.0, W_S + 2
    a = x + st + W_G
    return (_rect(x, 0, st, 100) + _rect(a, 0, w - st - W_G, W_S) +
            _rect(a, 50 - W_S / 2, w - st - W_G - 12, W_S) + _rect(a, 100 - W_S, w - st - W_G, W_S)), w


def _R(x):
    w, bh, st = 112.0, 58.0, W_S + 2
    bx, r = x + st + W_G, bh / 2
    ir = r - W_S
    outer = f"M{f(bx)},0 H{f(x + w - r)} A{f(r)},{f(r)} 0 0 1 {f(x + w - r)},{f(bh)} H{f(bx)} Z"
    inner = f"M{f(bx)},{f(W_S)} H{f(x + w - r)} A{f(ir)},{f(ir)} 0 0 1 {f(x + w - r)},{f(bh - W_S)} H{f(bx)} Z"
    leg = f"M{f(x + w - 56)},{f(bh + W_G)} L{f(x + w - 34)},{f(bh + W_G)} L{f(x + w)},100 L{f(x + w - 22)},100 Z"
    return _rect(x, 0, st, 100) + outer + " " + inner + " " + leg, w


def _word_d():
    d, x = [], 0.0
    for glyph in (_T, _E, _E, _T, _E, _R):
        p, w = glyph(x)
        d.append(p)
        x += w + W_TRACK
    return " ".join(d), x - W_TRACK


def word_b(fill="currentColor", cap=10.0):
    """The wordmark scaled to a cap height; returns (width, height, body)."""
    d, w = _word_d()
    k = cap / 100
    return w * k, cap, f'<path transform="scale({f(k)})" d="{d}" fill="{fill}" fill-rule="evenodd"/>'


LOCK_GAP = 5.0


def lockup(uid="lk", fill="currentColor"):
    """The gyroscope beside the wordmark, its centre on the cap line's middle.
    Returns (viewBox, body)."""
    ww, wh, word = word_b(fill)
    m = 17.0
    body = (f'<g transform="translate(0 {f((wh - m) / 2)})">{mark_b(uid, fill, box=m)}</g>'
            f'<g transform="translate({f(m + LOCK_GAP)} 0)">{word}</g>')
    return f"0 {f((wh - m) / 2)} {f(m + LOCK_GAP + ww)} {f(m)}", body


def stacked_b(uid="st", fill="currentColor"):
    ww, wh, word = word_b(fill)
    m = 40.0
    w = max(ww, m)
    body = (f'<g transform="translate({f((w - m) / 2)} 0)">{mark_b(uid, fill, box=m)}</g>'
            f'<g transform="translate({f((w - ww) / 2)} {f(m + 4)})">{word}</g>')
    return f"0 0 {f(w)} {f(m + 4 + wh)}", body


def clearspace_b():
    """The symbol with its clear space: a quarter of its box on every side."""
    b, q = 112.0, 28.0
    W = b + 2 * q + 40
    o = [f'<rect class="n" x="20" y="20" width="{f(b + 2 * q)}" height="{f(b + 2 * q)}" stroke-dasharray="3 3"/>',
         f'<rect class="ph" x="{f(20 + q)}" y="{f(20 + q)}" width="{f(b)}" height="{f(b)}"/>',
         f'<g transform="translate({f(20 + q)} {f(20 + q)})">{mark_b("cs", box=b)}</g>',
         f'<line class="n" x1="{f(20 + q)}" y1="12" x2="{f(20 + q)}" y2="{f(20 + q)}"/>',
         f'<text class="dim" x="{f(20 + q / 2)}" y="14" text-anchor="middle">¼</text>']
    return inline(f"0 0 {f(W)} {f(W)}", "".join(o), "The symbol inside a dashed square a quarter of its own size larger on every side.", "draw cs")


def wordmark_construction_b(k=1.25, mx=70.0, my=40.0):
    """The stencil wordmark on its grid: cap height, stroke, cut and tracking."""
    d, ww = _word_d()
    W, H = mx * 2 + ww * k, my + 100 * k + 80
    X = lambda u: mx + u * k
    Y = lambda u: my + u * k
    o = [f'<path transform="translate({f(mx)} {f(my)}) scale({f(k)})" d="{d}" fill="currentColor" fill-rule="evenodd"/>']
    for y, name in ((0, "cap 100"), (50, "mid 50"), (100, "base 0")):
        o.append(f'<line class="gd" x1="{f(mx - 10)}" y1="{f(Y(y))}" x2="{f(W - 10)}" y2="{f(Y(y))}"/>')
        o.append(f'<text class="lab" x="{f(W - 10)}" y="{f(Y(y) - 6)}" text-anchor="end">{name}</text>')
    # stroke, on the first T's bar
    o.append(f'<line class="n" x1="{f(X(-4))}" y1="{f(Y(0))}" x2="{f(X(-4))}" y2="{f(Y(W_S))}" marker-start="url(#ah2)" marker-end="url(#ah2)"/>')
    o.append(f'<text class="dim sm" x="{f(X(-6))}" y="{f(Y(W_S / 2) + 4)}" text-anchor="end">stroke {W_S:g}</text>')
    # the stencil cut, between the first T's bar and stem
    tx = X(62)
    o.append(f'<line class="n" x1="{f(tx + 24)}" y1="{f(Y(W_S))}" x2="{f(tx + 24)}" y2="{f(Y(W_S + W_G))}"/>')
    o.append(f'<text class="dim sm" x="{f(tx + 30)}" y="{f(Y(W_S + W_G / 2) + 4)}">cut {W_G:g}</text>')
    # tracking, between the letters, below the baseline
    x, ys = 0.0, Y(100) + 34
    for glyph in (_T, _E, _E, _T, _E):
        _, w = glyph(x)
        a, b = X(x + w), X(x + w + W_TRACK)
        o.append(f'<line class="n" x1="{f(a)}" y1="{f(ys)}" x2="{f(b)}" y2="{f(ys)}" marker-start="url(#ah2)" marker-end="url(#ah2)"/>')
        o.append(f'<text class="dim sm" x="{f((a + b) / 2)}" y="{f(ys + 18)}" text-anchor="middle">{W_TRACK:g}</text>')
        x += w + W_TRACK
    defs = ('<defs><marker id="ah2" viewBox="0 0 10 6" refX="9.5" refY="3" markerWidth="9" markerHeight="5.4" '
            'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,0 L10,3 L0,6 Z" class="ahf"/></marker></defs>')
    return (f'<svg class="draw" viewBox="0 0 {f(W)} {f(H)}" role="img" aria-label="The wordmark on its grid: cap height 100, '
            f'stroke {W_S:g}, a stencil cut of {W_G:g} between every bar and its stem, and {W_TRACK:g} between letters.">{defs}{"".join(o)}</svg>')


def gyro_construction(uid="gc", W=600, H=420):
    """The gyroscope drawn large and dimensioned: the vertical it has left, the
    angle it is tipped by, the ring's axes. The needle sits in a group a page
    can set precessing."""
    k = 3.3
    cx, cy = W / 2 - 20, H / 2
    T = lambda d: f'transform="translate({f(cx)} {f(cy)}) scale({f(k)})"'
    o = ['<defs><marker id="ah" viewBox="0 0 10 6" refX="9.5" refY="3" markerWidth="9" markerHeight="5.4" '
         'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,0 L10,3 L0,6 Z" class="ahf"/></marker></defs>']
    o.append(f'<line class="ph" x1="{f(cx)}" y1="{f(cy - 190)}" x2="{f(cx)}" y2="{f(cy + 190)}"/>')
    ra, rb = _turn(46, 0, G_RING), _turn(0, 17, G_RING)
    o.append(f'<line class="n" x1="{f(cx - ra[0] * k)}" y1="{f(cy - ra[1] * k)}" x2="{f(cx + ra[0] * k)}" y2="{f(cy + ra[1] * k)}" stroke-dasharray="2 4"/>')
    o.append(f'<path class="k" {T(0)} d="{RING}" fill-rule="evenodd" style="stroke-width:{f(1.6 / k)}"/>')
    o.append(f'<g class="tip" style="transform-origin:{f(cx)}px {f(cy)}px">'
             f'<path class="k gyro-needle" {T(0)} d="{NEEDLE}" style="stroke-width:{f(1.6 / k)}"/>'
             f'<line class="n" x1="{f(cx)}" y1="{f(cy)}" x2="{f(cx + _turn(0, -60, G_TIP)[0] * k)}" y2="{f(cy + _turn(0, -60, G_TIP)[1] * k)}"/></g>')
    o.append(f'<circle class="cg" cx="{f(cx)}" cy="{f(cy)}" r="5"/>')
    R = 172
    e = (cx + R * math.sin(G_TIP), cy - R * math.cos(G_TIP))
    dim = [f'<path class="n" d="M{f(cx)},{f(cy - R)} A{R},{R} 0 0 1 {f(e[0])},{f(e[1])}" marker-start="url(#ah)" marker-end="url(#ah)"/>',
           f'<text class="dim" x="{f(cx + 26)}" y="{f(cy - R - 8)}">{math.degrees(G_TIP):g}°</text>',
           f'<text class="lab" x="{f(cx + 14)}" y="{f(cy + 196)}" >vertical</text>',
           f'<text class="lab" x="{f(cx + ra[0] * k + 8)}" y="{f(cy + ra[1] * k + 4)}">gimbal ring</text>']
    o.append('<g class="dimA">' + "".join(dim) + "</g>")
    return "".join(o)


def write(name, text):
    (OUT / name).write_text(text)
    return name


def main():
    OUT.mkdir(exist_ok=True)
    files = []

    # revision B: the wordmark, with the teeter-totter T as the symbol
    mw, mh = MARK_W, MARK_H                      # the revision-A block, still drawn on TT-001..TT-003
    ox, oy = MARK_OX, MARK_OY
    desc = "A gyroscope: a needle tipped off vertical and a gimbal ring around it."
    files.append(write("teeter-mark.svg", svg("0 0 32 32", mark_b("f"), "Teeter", desc)))
    fb = '<rect width="32" height="32" rx="7" fill="#0B0B0A"/>' + mark_b("fav", "#E9E6DE", fit=.92)
    files.append(write("favicon.svg", svg("0 0 32 32", fb, "Teeter")))
    ww, wh, word = word_b()
    files.append(write("teeter-wordmark.svg", svg(f"0 0 {f(ww)} {f(wh)}", word, "Teeter")))
    lock_vb, lock_body = lockup("file")
    lw, lh = (float(v) for v in lock_vb.split()[2:])
    files.append(write("teeter-lockup.svg", svg(lock_vb, lock_body, "Teeter")))
    files.append(write("teeter-mark-plain.svg", svg("0 0 32 32", mark_b("pl"), "Teeter")))
    st_vb, st_body = stacked_b("file")
    files.append(write("teeter-lockup-stacked.svg", svg(st_vb, st_body, "Teeter")))
    cw, ch = 600, 420
    files.append(write("teeter-mark-construction.svg", svg(
        f"0 0 {cw} {ch}",
        f'<style>{CONSTRUCTION_CSS}</style><rect width="{cw}" height="{ch}" fill="#0B0B0A"/>' + gyro_construction("file"),
        "Teeter mark construction", desc)))
    old = OUT / "rev-a-block-construction.svg"
    old.write_text(svg("0 0 480 400", f'<style>{CONSTRUCTION_CSS}</style><rect width="480" height="400" fill="#0B0B0A"/>' + construction(),
                       "Revision A mark construction, withdrawn"))
    files.append(old.name)

    # the identity standard page
    campaign = json.loads((ROOT / "assets/data/campaign.json").read_text())
    sim = json.loads((ROOT / "media/sim.json").read_text())
    L = lambda uid, label=None: inline(lockup(uid)[0], lockup(uid)[1], label)
    Mk = lambda uid: inline("0 0 32 32", mark_b(uid))
    Fv = lambda uid: inline("0 0 32 32", fb.replace("-fav", "-" + uid))
    standard = {
        "lockup": L("bk1"), "lockup-cover": L("bk2", "Teeter"),
        "lockup-tb": L("bk3"), "lockup-big": L("bk4"), "lockup-card": L("bk5"),
        "lockup-report": L("bk6"),
        "lockup-stacked": inline(st_vb, stacked_b("bk7")[1]),
        "mark": Mk("bk8"), "mark-inv": Mk("bk9"), "mark-card": Mk("bk10"),
        "mark-plain": Mk("bk11"),
        "favicons": (f'<span style="width:64px">{Fv("fv1")}</span>'
                     f'<span style="width:32px">{Fv("fv2")}</span>'
                     f'<span style="width:16px">{Fv("fv3")}</span>'),
        "construction": f'<svg class="draw" viewBox="0 0 {cw} {ch}" role="img" aria-label="Construction of the symbol: a needle tipped 12 degrees off vertical inside a gimbal ring tilted the other way, with the vertical it has left.">{gyro_construction("bk")}</svg>',
        "clearspace": clearspace_b(),
        "dont-angle": inline("0 0 32 32", mark_b("d1", tip=0.0)),
        "dont-ground": inline("0 0 32 32", mark_b("d2", weave=False)),
        "dont-outline": inline("0 0 32 32", mark_b("d3", outline=True)),
        "dont-split": inline("0 0 32 32", mark_b("d4", turn=-30.0)),
        "wordmark-construction": wordmark_construction_b(),
        "wedge": wedge_html(),
        "hatch-spec": hatch_spec_svg(),
        "trace": trace_figure(sim, campaign),
        "trace-small": trace_figure(sim, campaign, pid="hx-mini", w=420, h=130, small=True),
        "reduction": reduction_figure(campaign),
        "dim-anatomy": dim_anatomy_svg(),
        "modes": modes_rows(campaign),
        "social": inline("0 0 1200 630", social_svg(lockup("soc")[1], lw, lh),
                         "Social preview: the Teeter lockup, the line 'We find the exact condition where your robot falls', and the mark drawn as an instrument behind it."),
    }
    used = inject(ROOT / "teeter" / "brand" / "index.html", standard)
    missing = sorted(set(standard) - set(used))
    print("identity standard:", len(used), "regions filled", ("· unused: " + ", ".join(missing)) if missing else "")

    # numbers anyone can check
    facts = {
        "block": {"width": W_BLOCK, "height": H_BLOCK},
        "theta_c_deg": round(math.degrees(THETA), 4),
        "diagonal": round(DIAG, 6),
        "corners": {k: [round(v, 6) for v in pt] for k, pt in
                    zip(("pivot", "left", "top", "right"), (PIVOT, LEFT, TOP, RIGHT))},
        "centroid": [0.0, round(DIAG / 2, 6)],
        "logo_rev_b": {"needle_off_vertical_deg": math.degrees(G_TIP), "ring_tilt_deg": math.degrees(G_RING),
                       "wordmark": {"stroke": W_S, "stencil_gap": W_G, "tracking": W_TRACK, "width_at_cap_10": round(ww, 4)}},
        "files": files,
    }
    (OUT / "geometry.json").write_text(json.dumps(facts, indent=2) + "\n")
    print(json.dumps({k: facts[k] for k in ("theta_c_deg", "corners", "centroid")}, indent=1))
    print("wrote", ", ".join(files))


if __name__ == "__main__":
    main()
