# SPDX-License-Identifier: GPL-3.0-only
"""zorkmapper.sheetsvg: draw a lattice Sheet as one sheet of graph paper, in the manner of the Infocom map (boxes, plain lines, arrows for one-way,
dashed for special exits, U/D on vertical passages, 'to N' notes for connectors, a circle for a passage returning to its own room)."""
import html
import math
from typing import Dict
from .model import Room
from .lattice import Sheet

C = 30.0            # one graph-paper square
SQ = 22.0           # a room square


def render(rooms: Dict[str, Room], sh: Sheet, title: str) -> str:
    cells = {n: sh.cell(n) for n in sh.pos}
    x0 = min(c[0] for c in cells.values()) - 3; y0 = min(c[1] for c in cells.values()) - 3
    x1 = max(c[0] for c in cells.values()) + 3; y1 = max(c[1] for c in cells.values()) + 3
    w, h = (x1 - x0 + 1)*C, (y1 - y0 + 1)*C
    leg_rows = 50; cols = math.ceil(len(sh.order)/leg_rows); legw = cols*250 + 30
    W, H = w + legw, max(h, leg_rows*15 + 190)
    def P(n):
        cx, cy = cells[n]; return (cx - x0 + 0.5)*C, (cy - y0 + 0.5)*C
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="DejaVu Sans, sans-serif">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="#fbfaf4"/>' % (W, H),
         '<defs><pattern id="g" width="%g" height="%g" patternUnits="userSpaceOnUse"><path d="M %g 0 L 0 0 0 %g" fill="none" stroke="#b9d3c4" stroke-width="0.8"/></pattern></defs>' % (C, C, C, C),
         '<rect width="%g" height="%g" fill="url(#g)"/>' % (w, h),
         '<text x="12" y="22" font-size="16" font-weight="700" fill="#1d1d1d">%s</text>' % html.escape(title)]
    ink = "#1d1d1d"
    for l in sh.links:
        ax, ay = P(l.a); bx, by = P(l.b); dash = ' stroke-dasharray="5 4"' if l.kind == "cond" else ""
        if l.mode == "straight":
            o.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="2"%s/>' % (ax, ay, bx, by, ink, dash))
            mx, my = (ax + bx)/2, (ay + by)/2
            if l.one_way:
                dx, dy = bx - ax, by - ay; L_ = math.hypot(dx, dy) or 1; ux, uy = dx/L_, dy/L_
                o.append('<polygon points="%g,%g %g,%g %g,%g" fill="%s"/>' % (mx + ux*7, my + uy*7, mx - ux*5 - uy*5, my - uy*5 + ux*5, mx - ux*5 + uy*5, my - uy*5 - ux*5, ink))
            if l.vertical:
                o.append('<text x="%g" y="%g" font-size="9" font-style="italic" fill="#b3360b">%s</text>' % (mx + 3, my - 3, l.vertical))
        else:                                                           # connector: a short stub from each end labelled with the other end's number
            for n, m in ((l.a, l.b), (l.b, l.a)):
                if n == l.b and l.one_way: continue
                px, py = P(n); mx, my = P(m); dx, dy = mx - px, my - py; L_ = math.hypot(dx, dy) or 1
                ex, ey = px + dx/L_*C*0.95, py + dy/L_*C*0.95
                o.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="1.6" stroke-dasharray="2 3"/>' % (px, py, ex, ey, ink))
                lab = "%s%s%d" % (l.vertical + " " if l.vertical else "", "to " if n == l.a else "from ", sh.order.index(m) + 1)
                if n == l.a and l.one_way: o.append('<circle cx="%g" cy="%g" r="2.2" fill="%s"/>' % (ex, ey, ink))
                o.append('<text x="%g" y="%g" font-size="8.5" fill="#2a4a8a" text-anchor="middle">%s</text>' % (ex, ey + (11 if ey >= py else -4), html.escape(lab)))
    for n, v, word in sh.stubs:                                         # an excluded maze / puzzle: point off into the blank space and say so
        px, py = P(n); ex, ey = px + v[0]*C*1.1, py + v[1]*C*1.1
        o.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="1.6" stroke-dasharray="1 4"/><text x="%g" y="%g" font-size="9.5" font-style="italic" fill="#7a2a2a" text-anchor="middle">%s</text>' % (px, py, ex, ey, ink, ex + v[0]*10, ey + v[1]*4 + 3, html.escape(word)))
    for n in sh.loops:
        px, py = P(n); o.append('<circle cx="%g" cy="%g" r="9" fill="none" stroke="%s" stroke-width="1.5"/>' % (px + SQ/2 + 2, py - SQ/2 - 2, ink))
    for n, d in sh.per:
        px, py = P(n); o.append('<text x="%g" y="%g" font-size="8" fill="#a0306a" font-weight="700">%s?</text>' % (px - SQ/2, py + SQ/2 + 9, html.escape(d[:2])))
    for i, n in enumerate(sh.order, 1):
        px, py = P(n); far = n in sh.far
        o.append('<rect x="%g" y="%g" width="%g" height="%g" fill="#fffdf5" stroke="%s" stroke-width="%g"%s/>' % (px - SQ/2, py - SQ/2, SQ, SQ, "#b3360b" if i == 1 else ink, 2.4 if i == 1 else 1.6, ' stroke-dasharray="3 2"' if far else ""))
        o.append('<text x="%g" y="%g" font-size="11" font-weight="700" text-anchor="middle" fill="%s">%d</text>' % (px, py + 4, ink, i))
    lx, ly = w + 16, 44
    o.append('<text x="%g" y="%g" font-size="13" font-weight="700" fill="#b3360b">Rooms</text>' % (lx, ly - 14))
    for i, n in enumerate(sh.order, 1):
        c, r = divmod(i - 1, leg_rows); nm = rooms[n].desc or n.title()
        o.append('<text x="%g" y="%g" font-size="10.5" fill="#1d1d1d"><tspan font-weight="700" fill="#b3360b">%d</tspan>  %s</text>' % (lx + c*250, ly + r*15, i, html.escape(nm[:36])))
    ky = ly + leg_rows*15 + 18
    keys = [("normal passage", "", ""), ("one-way passage (arrow in the middle)", "", "arrow"), ("special exit: door, window, flag", "dash", ""),
            ("U / D: up or down, drawn diagonally", "", "ud"), ("dotted stub 'to N': links that cannot be drawn straight", "dot", ""),
            ("dotted stub into blank space: maze / puzzle (left out)", "dot", "word"), ("circle: exit back to its own room", "", "loop"), ("pink 'NO?': a routine decides this exit", "", "per"),
            ("dashed square: set down away from its neighbours", "", "far"), ("red square: start (West of House)", "", "")]
    for k, (t, st, _) in enumerate(keys):
        yy = ky + k*15
        o.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="1.8"%s/><text x="%g" y="%g" font-size="10" fill="#1d1d1d">%s</text>' % (lx, yy - 3, lx + 24, yy - 3, ink, ' stroke-dasharray="5 4"' if st == "dash" else ' stroke-dasharray="2 3"' if st == "dot" else "", lx + 32, yy, html.escape(t)))
    o.append('<text x="%g" y="%g" font-size="9" fill="#555">each room owns a 3x3 block; its 8 neighbours are pathway squares</text></svg>' % (lx, ky + len(keys)*15 + 8))
    return "\n".join(o)
