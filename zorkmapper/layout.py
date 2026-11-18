# SPDX-License-Identifier: GPL-3.0-only
"""
zorkmapper.layout: place rooms on a 3-D integer grid from their exits, then flatten to graph paper.

Directions as grid vectors (x east, y south, z up): N, S, E, W, the four compass diagonals, UP, DOWN.  IN, OUT, LAND (and the other
verbs) have no geometry: they are portals, drawn as lines but never used to place a room.  The flat view puts each level z at a diagonal
offset (up is diagonal up, down is diagonal down), so the 3-D grid reads as one sheet of graph paper.
Placement is a breadth-first walk from the start room over exits, and over reverse exits for rooms only reachable backwards;
unplaced islands are set beside the main map.  A cell that is already taken pushes the room to the nearest free cell (recorded).
"""
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from .model import Room, OPPOSITE

VEC = {"NORTH": (0, -1, 0), "SOUTH": (0, 1, 0), "EAST": (1, 0, 0), "WEST": (-1, 0, 0), "NE": (1, -1, 0), "NW": (-1, -1, 0),
       "SE": (1, 1, 0), "SW": (-1, 1, 0), "UP": (0, 0, 1), "DOWN": (0, 0, -1)}
FLAT_Z = (0.5, -0.5)          # one level up shifts the room half a cell right and half a cell up on the flat sheet


@dataclass
class Edge:
    a: str; b: str; direction: str; kind: str                 # kind of the forward exit: to / cond / per
    one_way: bool = False; irregular: bool = False; label: str = ""; portal: bool = False; both: str = ""


@dataclass
class Layout:
    pos: Dict[str, Tuple[int, int, int]]
    order: List[str]                                          # square numbers = index + 1
    edges: List[Edge]
    nudged: List[str] = field(default_factory=list)
    islands: List[List[str]] = field(default_factory=list)
    unplaced_links: List[Tuple[str, str, str]] = field(default_factory=list)

    def flat(self, name: str, cell: float = 1.0) -> Tuple[float, float]:
        x, y, z = self.pos[name]; return (x + z*FLAT_Z[0])*cell, (y + z*FLAT_Z[1])*cell


def _adjacency(rooms: Dict[str, Room]):
    out, inc = {n: [] for n in rooms}, {n: [] for n in rooms}
    for r in rooms.values():
        for d, e in r.exits.items():
            if e.dest and e.dest in rooms and d in VEC:
                out[r.name].append((d, e.dest)); inc[e.dest].append((d, r.name))
    return out, inc


def _free(pos_set, cell):
    if cell not in pos_set: return cell
    x, y, z = cell
    for rad in range(1, 12):
        for dx in range(-rad, rad + 1):
            for dy in range(-rad, rad + 1):
                if max(abs(dx), abs(dy)) == rad and (x + dx, y + dy, z) not in pos_set: return (x + dx, y + dy, z)
    return (x + 20, y, z)


def build(rooms: Dict[str, Room], start: str) -> Layout:
    out, inc = _adjacency(rooms); pos: Dict[str, Tuple[int, int, int]] = {}; taken = set(); order: List[str] = []; nudged = []
    islands: List[List[str]] = []

    def put(name, want, base_note=""):
        cell = _free(taken, want)
        if cell != want: nudged.append(name)
        pos[name] = cell; taken.add(cell); order.append(name); return cell

    def walk(root, origin):
        put(root, origin); q = deque([root]); members = [root]
        while q:
            cur = q.popleft(); cx, cy, cz = pos[cur]
            nbrs = [(d, n, +1) for d, n in out[cur]] + [(d, n, -1) for d, n in inc[cur]]
            for d, n, sgn in nbrs:
                if n in pos: continue
                v = VEC[d]; put(n, (cx + sgn*v[0], cy + sgn*v[1], cz + sgn*v[2])); q.append(n); members.append(n)
        return members

    if start not in rooms: start = next(iter(rooms))
    walk(start, (0, 0, 0))
    xs = [p[0] for p in pos.values()] or [0]; right = max(xs) + 3
    for n in rooms:                                            # islands: rooms with no placed neighbour at all
        if n in pos: continue
        members = walk(n, (right, 0, 0)); islands.append(members); right = max(pos[m][0] for m in members) + 3
    edges, seen = [], set()
    for r in rooms.values():
        for d, e in r.exits.items():
            if not e.dest or e.dest not in rooms or e.kind == "blocked": continue
            key = (r.name, e.dest, d)
            if key in seen: continue
            seen.add(key); back = [(bd, be) for bd, be in rooms[e.dest].exits.items() if be.dest == r.name]
            opp = OPPOSITE.get(d); has_opp = any(bd == opp for bd, _ in back)
            ed = Edge(r.name, e.dest, d, e.kind, one_way=not back, irregular=bool(back) and not has_opp, portal=(d not in VEC),
                      label=(e.condition or ""), both=",".join(bd for bd, _ in back))
            edges.append(ed)
    for r in rooms.values():                                   # per-routine exits: destination unknown without running the routine
        pass
    return Layout(pos=pos, order=order, edges=edges, nudged=nudged, islands=islands)
