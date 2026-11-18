# SPDX-License-Identifier: GPL-3.0-only
"""
zorkmapper.asciiart: the graph-paper Sheet as text.  A grid square is TWO characters wide and one row high.

Room squares:   two digits (07); 100 is '**', 101..109 are '*1'..'*9', 110 is '*0'.  The square's background colour is its level.
Passages:       horizontal '──', vertical '│' (left character of the square), diagonals '╱╱' and '╲╲' (two characters, so the diagonal fills the
                square), crossings '╳╳' / '─┼'.  One-way: an arrow replaces one character in the middle square.  U / D on vertical passages.
Connectors:     the target room number in superscript digits (²³) in the square next to the room.  Maze / puzzle: the word, pointing into blank space.
Colours (ANSI 256): the level of the start room (West of House, the surface) is white; up is light, underground is dark; unknown is grey.
"""
from collections import deque
from typing import Dict, List, Tuple
from .model import Room
from .lattice import Sheet, VEC

SUP = str.maketrans("0123456789*", "⁰¹²³⁴⁵⁶⁷⁸⁹⁎")
UP_BG = [231, 229, 195, 159, 123]                       # level 0 white, then light yellow, light cyan ...
DOWN_BG = [24, 54, 94, 22, 52, 58, 17]                  # level -1 downward: dark blue, purple, brown, green, red, olive, navy
UNK_BG = 240


def label(n: int) -> str:
    """the two-character room label: 01..99, '**' = 100, '*1'..'*9' = 101..109, '*0' = 110"""
    if n < 100: return "%02d" % n
    return "**" if n == 100 else "*%d" % (n % 10)


def levels(rooms: Dict[str, Room], sh: Sheet, start: str) -> Dict[str, int]:
    z = {start: 0}; q = deque([start])
    while q:
        c = q.popleft()
        for d, e in rooms[c].exits.items():
            if e.dest in sh.pos and e.dest not in z and e.kind in ("to", "cond"):
                z[e.dest] = z[c] + (1 if d == "UP" else -1 if d == "DOWN" else 0); q.append(e.dest)
        for n, r in rooms.items():                                       # entered backwards: the other end of an exit tells our level
            if n in sh.pos and n not in z:
                for d, e in r.exits.items():
                    if e.dest == c and r.name in z and e.kind in ("to", "cond"): z[n] = z[r.name] + (1 if d == "UP" else -1 if d == "DOWN" else 0); q.append(n); break
    return z


def bg(z):
    if z is None: return UNK_BG
    return UP_BG[min(z, len(UP_BG) - 1)] if z >= 0 else DOWN_BG[min(-z - 1, len(DOWN_BG) - 1)]


def render(rooms: Dict[str, Room], sh: Sheet, title: str, start: str, color: bool = False) -> str:
    cells = {n: sh.cell(n) for n in sh.pos}; zl = levels(rooms, sh, start)
    x0 = min(c[0] for c in cells.values()) - 3; y0 = min(c[1] for c in cells.values()) - 2
    x1 = max(c[0] for c in cells.values()) + 3; y1 = max(c[1] for c in cells.values()) + 2
    W, H = x1 - x0 + 1, y1 - y0 + 1
    grid: List[List[Tuple[str, int]]] = [[("  ", 0) for _ in range(W)] for _ in range(H)]      # (two characters, background colour or 0)
    def at(c): return c[0] - x0, c[1] - y0
    def put(c, s, b=0, force=False):
        x, y = at(c)
        if 0 <= x < W and 0 <= y < H and (force or grid[y][x][0] == "  "): grid[y][x] = (s, b)
    def free(c): x, y = at(c); return 0 <= x < W and 0 <= y < H and grid[y][x][0] == "  "
    glyph = {(1, 0): "==", (-1, 0): "==", (0, 1): "||", (0, -1): "||", (1, -1): "//", (-1, 1): "//", (1, 1): "\\\\", (-1, -1): "\\\\"}
    arrows = {(1, 0): "=>", (-1, 0): "<=", (0, -1): "^^", (0, 1): "vv", (1, -1): "↗/", (-1, 1): "↙/", (1, 1): "↘\\", (-1, -1): "↖\\"}
    def line_cell(c, v, s):
        x, y = at(c); cur = grid[y][x][0]
        if cur == "  ": grid[y][x] = (s, 0)
        elif cur != s and not cur.strip() == "": grid[y][x] = ("XX" if v[0] and v[1] else "++", 0)
    for l in sh.links:
        if l.mode != "straight": continue
        a = cells[l.a]; v = l.vec; n = 2*l.steps
        for j in range(1, n):
            c = (a[0] + j*v[0], a[1] + j*v[1]); line_cell(c, v, glyph[v])
        mid = (a[0] + l.steps*v[0], a[1] + l.steps*v[1])
        if l.one_way: x, y = at(mid); grid[y][x] = (arrows[v], 0)
        if l.vertical:
            c1 = (a[0] + v[0], a[1] + v[1]); x, y = at(c1); s = grid[y][x][0]; grid[y][x] = (l.vertical + s[1], 0)
    def neighbour_cells(c): return [(c[0] + dx, c[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, -1), (1, 1), (-1, 1))]
    for l in sh.links:
        if l.mode != "connector": continue
        for n, m, out_ in ((l.a, l.b, True), (l.b, l.a, False)):
            if not out_ and l.one_way: continue
            c = cells[n]; v = VEC.get(l.direction if out_ else {"NORTH": "SOUTH", "SOUTH": "NORTH", "EAST": "WEST", "WEST": "EAST", "NE": "SW", "SW": "NE", "NW": "SE", "SE": "NW"}.get(l.direction, ""), None)
            want = (c[0] + v[0], c[1] + v[1]) if v else None
            spot = want if want and free(want) else next((p for p in neighbour_cells(c) if free(p)), None)
            if spot: put(spot, label(sh.order.index(m) + 1).translate(SUP))
    for n, v, word in sh.stubs:
        c = cells[n]; p1 = (c[0] + v[0], c[1] + v[1]); p2 = (c[0] + 2*v[0], c[1] + 2*v[1]); w = word[:4]
        if free(p1): 
            if free(p2) and v[0] >= 0 and len(w) > 2: put(p1, w[:2]); put(p2, w[2:4].ljust(2))
            else: put(p1, w[:2])
    for n in sh.loops:
        c = cells[n]; p = next((q for q in neighbour_cells(c)[4:] if free(q)), None)
        if p: put(p, "⟲ ")
    for n, d in sh.per:
        c = cells[n]; v = VEC.get(d); p = (c[0] + v[0], c[1] + v[1]) if v else None
        if p and free(p): put(p, "?" + d[0])
    for i, n in enumerate(sh.order, 1):
        put(cells[n], label(i), bg(zl.get(n)), force=True)
    out = [title, ""]
    for row in grid:
        if not color: out.append("".join(s + " " for s, _ in row).rstrip())
        else: out.append("".join((("\x1b[48;5;%dm\x1b[%sm%s\x1b[0m" % (b, "30" if b in (231, 229, 195, 159, 123) else "97;1", s)) if b else s) + " " for s, b in row).rstrip())
    out += ["", "Rooms (number, name, level above the start room: + up, - down)"]
    names = ["%s  %s  [%+d]" % (label(i), (rooms[n].desc or n.title())[:34], zl.get(n, 0)) for i, n in enumerate(sh.order, 1)]
    half = (len(names) + 1)//2
    for i in range(half): out.append("%-48s%s" % (names[i], names[i + half] if i + half < len(names) else ""))
    out += ["", "Key: == east/west, || north/south, // \\\\ diagonals; => <= ^^ vv (or ↗ ↖ ↘ ↙) one-way arrows; U/D up/down (drawn diagonally); ²³ superscript = a link to that room number that cannot be drawn straight;",
            "     Ma ze / Pu zz le = a maze or puzzle (left out) off in that direction; ⟲ passage back to its own room; ?N = a routine decides that exit.",
            "     Background colour = level: white = start level (surface); lighter colours up, darker colours underground."]
    return "\n".join(out) + "\n"
