# SPDX-License-Identifier: GPL-3.0-only
"""
zorkmapper.lattice: the hand-drawn graph-paper method, as an algorithm.

One sheet of graph paper.  A room is one square and owns a 3 x 3 block: the eight squares around it are reserved for pathways, so rooms sit
on every second square (a sub-grid lattice) and two neighbouring rooms are always separated by exactly one pathway square.
  * N, S, E, W: a line runs through the whole next square to the next room.  The four diagonals run corner to corner through the square.
  * UP and DOWN are drawn as diagonals too (up leans up-right or up-left, down leans down-left or down-right), labelled U and D.
  * A long run may skip lattice spots (the line passes straight over them) as long as no room sits in the way.
  * A link that cannot be drawn straight is a CONNECTOR: a stub out of the room labelled with the square number it reaches.
  * Rooms that are mazes or puzzles are left out: the exit points off into blank space with the word on it.
IN / OUT / LAND have no geometry and are always connectors.
"""
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from .model import Room

VEC = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "NE": (1, -1), "NW": (-1, -1), "SE": (1, 1), "SW": (-1, 1)}
UP_OPTS = [(1, -1), (-1, -1)]       # up leans up-right, then up-left
DOWN_OPTS = [(-1, 1), (1, 1)]       # down leans down-left, then down-right


@dataclass
class Link:
    a: str; b: str; direction: str; kind: str                       # kind: to / cond
    mode: str = "straight"                                          # straight | connector
    vec: Tuple[int, int] = (0, 0)                                   # unit step used on the sheet
    steps: int = 1
    one_way: bool = False; label: str = ""; vertical: str = ""      # vertical: 'U' / 'D' / ''


@dataclass
class Sheet:
    pos: Dict[str, Tuple[int, int]]                                  # lattice coordinates (a room cell is (2a, 2b))
    order: List[str]
    links: List[Link]
    stubs: List[Tuple[str, Tuple[int, int], str]]                   # (room, step vector, word) for excluded maze/puzzle exits
    loops: List[str] = field(default_factory=list)                   # rooms with an exit back to themselves
    per: List[Tuple[str, str]] = field(default_factory=list)         # (room, direction) decided by a routine
    redundant: int = 0
    far: List[str] = field(default_factory=list)                     # rooms that had to be set down away from their neighbours

    def cell(self, name):
        a, b = self.pos[name]; return 2*a, 2*b


def _spiral(occ, near, maxr=40):
    x, y = near
    for r in range(0, maxr):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) == r and (x + dx, y + dy) not in occ: return (x + dx, y + dy)
    return (x + maxr, y)


def _options(direction):
    if direction in VEC: return [(VEC[direction], "")]
    if direction == "UP": return [(v, "U") for v in UP_OPTS]
    if direction == "DOWN": return [(v, "D") for v in DOWN_OPTS]
    return []


def _clear(pos_set, p, v, k):
    return all((p[0] + j*v[0], p[1] + j*v[1]) not in pos_set for j in range(1, k))


def build(rooms: Dict[str, Room], start: str, excluded=None, word=lambda n: "Maze") -> Sheet:
    excluded = set(excluded or ()); keep = {n: r for n, r in rooms.items() if n not in excluded}
    if start not in keep: start = next(iter(keep))
    pos: Dict[str, Tuple[int, int]] = {start: (0, 0)}; occ = {(0, 0)}; order = [start]; far: List[str] = []
    out = {n: [] for n in keep}; inc = {n: [] for n in keep}
    for r in keep.values():
        for d, e in r.exits.items():
            if e.dest in keep and e.kind in ("to", "cond"): out[r.name].append((d, e.dest, e)); inc[e.dest].append((d, r.name, e))
    def place(n, p): pos[n] = p; occ.add(p); order.append(n)
    q = deque([start])
    while q:
        cur = q.popleft(); cp = pos[cur]
        cands = [(d, n, +1) for d, n, e in sorted(out[cur], key=lambda t: (t[2].kind != "to", t[0]))] + [(d, n, -1) for d, n, e in inc[cur]]
        for d, n, sgn in cands:
            if n in pos or not _options(d): continue
            done = False
            for k in range(1, 7):                                    # nearest straight spot first, then longer runs
                for v, _ in _options(d):
                    t = (cp[0] + sgn*k*v[0], cp[1] + sgn*k*v[1])
                    if t not in occ and _clear(occ, cp, (sgn*v[0], sgn*v[1]), k): place(n, t); done = True; break
                if done: break
            if done: q.append(n)
    for n in keep:                                                  # rooms the walk could not seat straight
        if n in pos: continue
        nb = next((pos[m] for d, m, e in out[n] + [(d, m, e) for d, m, e in inc[n]] if m in pos), None) if False else None
        anchor = next((pos[m] for _, m, _ in out[n] if m in pos), None) or next((pos[m] for _, m, _ in inc[n] if m in pos), (0, 0))
        place(n, _spiral(occ, anchor)); far.append(n); q.append(n)
        while q:                                                    # seat this room's own unplaced neighbours around it
            cur = q.popleft(); cp = pos[cur]
            for d, m, e in [(d, m, e) for d, m, e in out[cur]] + [(d, m, e) for d, m, e in inc[cur]]:
                if m in pos or not _options(d): continue
                placed = False
                for k in range(1, 5):
                    for v, _ in _options(d):
                        t = (cp[0] + k*v[0], cp[1] + k*v[1])
                        if t not in occ and _clear(occ, cp, v, k): place(m, t); q.append(m); placed = True; break
                    if placed: break
    links: List[Link] = []; drawn = {}; stubs = []; loops = []; per = []; redundant = 0; pending: List[Link] = []
    for r in keep.values():
        for d, e in r.exits.items():
            if e.kind == "per": per.append((r.name, d)); continue
            if e.kind not in ("to", "cond") or not e.dest: continue
            if e.dest in excluded:                                    # an exit into a maze or puzzle: a stub pointing off into the blank space
                opts = _options(d); stubs.append((r.name, opts[0][0] if opts else (0, -1), word(e.dest))); continue
            if e.dest not in keep: continue
            if e.dest == r.name: loops.append(r.name); continue
            a, b = pos[r.name], pos[e.dest]; dx, dy = b[0] - a[0], b[1] - a[1]
            key = frozenset((r.name, e.dest))
            if key in drawn and drawn[key].mode == "straight": redundant += 1; continue
            fit = None
            for v, tag in _options(d):
                for k in range(1, 12):
                    if (k*v[0], k*v[1]) == (dx, dy) and _clear(set(pos.values()), a, v, k): fit = (v, k, tag)
                    if (-k*v[0], -k*v[1]) == (dx, dy) and _clear(set(pos.values()), a, (-v[0], -v[1]), k): fit = ((-v[0], -v[1]), k, tag)
            back = [bd for bd, be in rooms[e.dest].exits.items() if be.dest == r.name]
            one_way = not back
            if fit: l = Link(r.name, e.dest, d, e.kind, "straight", fit[0], fit[1], one_way, e.condition or "", fit[2])
            else: l = Link(r.name, e.dest, d, e.kind, "connector", (0, 0), 0, one_way, e.condition or "", "U" if d == "UP" else "D" if d == "DOWN" else "")
            if fit:
                if key in drawn: links.remove(drawn[key]); redundant += 1       # a straight link replaces an earlier connector for the same pair
                links.append(l); drawn[key] = l
            elif key in drawn: redundant += 1
            else: links.append(l); drawn[key] = l
    return Sheet(pos=pos, order=order, links=links, stubs=stubs, loops=loops, per=per, redundant=redundant, far=far)
