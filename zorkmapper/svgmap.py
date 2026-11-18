# SPDX-License-Identifier: GPL-3.0-only
"""zorkmapper.svgmap: draw a Layout as an SVG sheet of graph paper: numbered squares, straight lines, arrows for one-way exits, a legend."""
import html
import math
from typing import Dict
from .model import Room
from .layout import Layout

CELL, SQ = 80.0, 34.0
LEVEL = ["#1c2438", "#233152", "#2c3f6b", "#35508a"]        # square fill by level, up is lighter


def _fill(z):
    return LEVEL[max(0, min(len(LEVEL) - 1, z + 1))] if z >= -1 else "#141a2b"


def render(rooms: Dict[str, Room], lay: Layout, title: str = "Zork") -> str:
    pts = {n: lay.flat(n, CELL) for n in lay.pos}
    xs = [p[0] for p in pts.values()]; ys = [p[1] for p in pts.values()]
    x0, y0 = min(xs) - 1.2*CELL, min(ys) - 1.4*CELL; w, h = max(xs) - x0 + 1.2*CELL, max(ys) - y0 + 1.2*CELL
    leg_rows = 58; cols = math.ceil(len(lay.order)/leg_rows); leg_w = cols*270 + 40
    W, H = w + leg_w, max(h, leg_rows*15 + 52 + 7*15 + 60)
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="DejaVu Sans, sans-serif">' % (W, H, W, H)]
    o.append('<defs><pattern id="g" width="%g" height="%g" patternUnits="userSpaceOnUse" x="%g" y="%g"><path d="M %g 0 L 0 0 0 %g" fill="none" stroke="#2a3350" stroke-width="0.6"/></pattern>'
             '<marker id="arr" markerWidth="9" markerHeight="9" refX="6" refY="4.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L9,4.5 L0,9 z" fill="#ffd36b"/></marker></defs>' % (CELL, CELL, x0 % CELL, y0 % CELL, CELL, CELL))
    o.append('<rect width="%d" height="%d" fill="#0e1220"/><rect x="0" y="0" width="%g" height="%g" fill="url(#g)"/>' % (W, H, w, H))
    o.append('<text x="14" y="24" fill="#e6e9f5" font-size="17" font-weight="600">%s: %d rooms on a 3-D grid, flattened (up = diagonal up)</text>' % (html.escape(title), len(lay.order)))
    def P(n): return pts[n][0] - x0, pts[n][1] - y0
    for e in lay.edges:                                                 # lines first, squares on top
        (ax, ay), (bx, by) = P(e.a), P(e.b)
        up, down = e.direction == "UP", e.direction == "DOWN"
        col = "#ff9f43" if up else "#5ec2ff" if down else "#c39bff" if e.portal else "#7a86b8" if not e.irregular else "#5b6590"
        dash = ' stroke-dasharray="6 4"' if e.kind == "cond" else ' stroke-dasharray="2 4"' if e.portal else ""
        if e.a == e.b:
            o.append('<circle cx="%g" cy="%g" r="9" fill="none" stroke="%s" stroke-width="1.4"/>' % (ax + SQ/2, ay - SQ/2, col)); continue
        o.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="1.6"%s/>' % (ax, ay, bx, by, col, dash))
        if e.one_way:                                                  # arrow head in the middle of the line, pointing to the destination
            mx, my = (ax + bx)/2, (ay + by)/2; dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1
            o.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="none" marker-end="url(#arr)"/>' % (mx - dx/L*4, my - dy/L*4, mx + dx/L*4, my + dy/L*4))
    for i, n in enumerate(lay.order, 1):
        x, y = P(n); z = lay.pos[n][2]; nud = n in lay.nudged
        o.append('<rect x="%g" y="%g" width="%g" height="%g" rx="4" fill="%s" stroke="%s" stroke-width="%g"%s/>' % (x - SQ/2, y - SQ/2, SQ, SQ, _fill(z), "#e8b84a" if n == lay.order[0] else "#8da2d8", 2.2 if n == lay.order[0] else 1.2, ' stroke-dasharray="3 3"' if nud else ""))
        o.append('<text x="%g" y="%g" fill="#f2f4fb" font-size="13" text-anchor="middle" font-weight="600">%d</text>' % (x, y + 4.5, i))
        pers = [d for d, e in rooms[n].exits.items() if e.kind == "per"]
        for k, d in enumerate(pers):                                   # a routine decides this exit: a small marker, no line
            o.append('<circle cx="%g" cy="%g" r="6" fill="#ff6f91"/><text x="%g" y="%g" font-size="7.5" text-anchor="middle" fill="#0e1220">%s</text>' % (x + SQ/2 - 2 - k*13, y + SQ/2 - 2, x + SQ/2 - 2 - k*13, y + SQ/2 + 0.5, d[:2]))
    lx, ly = w + 20, 52
    o.append('<text x="%g" y="%g" fill="#e8b84a" font-size="13" font-weight="600">Legend: square number, room</text>' % (lx, ly - 14))
    for i, n in enumerate(lay.order, 1):
        c, r = divmod(i - 1, leg_rows); r_ = rooms[n]; name = r_.desc or n.title()
        o.append('<text x="%g" y="%g" fill="#d9dff2" font-size="10.5"><tspan fill="#e8b84a" font-weight="600">%d</tspan>  %s</text>' % (lx + c*270, ly + r*15, i, html.escape(name[:38])))
    ky = ly + leg_rows*15 + 14
    keys = [("#7a86b8", "", "two-way line"), ("#7a86b8", "arrow", "one-way: arrow in the middle points to the destination"), ("#ff9f43", "", "UP (diagonal up on the sheet)"),
            ("#5ec2ff", "", "DOWN"), ("#7a86b8", "dash", "conditional exit (door, window, flag)"), ("#c39bff", "dot", "IN / OUT / LAND portal"), ("#ff6f91", "pill", "a routine decides this exit (letters = direction)")]
    for k, (c, st, t) in enumerate(keys):
        yy = ky + k*15; o.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="1.8"%s/><text x="%g" y="%g" fill="#d9dff2" font-size="10">%s</text>' % (lx, yy - 3, lx + 26, yy - 3, c, ' stroke-dasharray="6 4"' if st == "dash" else ' stroke-dasharray="2 4"' if st == "dot" else "", lx + 34, yy, html.escape(t)))
    o.append('<text x="%g" y="%g" fill="#98a2c3" font-size="9.5">dashed square: nudged to a free cell (the map is not planar). Gold outline: start.</text></svg>' % (lx, ky + len(keys)*15 + 6))
    return "\n".join(o)
