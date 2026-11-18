# SPDX-License-Identifier: GPL-3.0-only
"""zorkmapper.mapper: the mapping function.  Point it at a Z-machine story file (.dat, .z3, .z5) or a folder of ZIL source; it reads the rooms,
lays them on the graph-paper lattice, and writes NAME.map.json (for the explorer), NAME.txt, NAME.ans and NAME.svg into the output folder (ASCIIArt/)."""
import glob
import os
import re
from typing import Tuple
from .model import parse_game
from . import lattice, sheetsvg, asciiart, mapfile, zmachine

MAZE = re.compile(r"maze|oddly-angled|puzzle", re.I)


def read_source(src: str):
    """-> (rooms, objs, game_name, start_id, word)"""
    if os.path.isdir(src):
        rooms, objs = {}, {}
        for f in sorted(glob.glob(os.path.join(src, "*.zil"))):
            r, o = parse_game(open(f, errors="replace").read(), os.path.basename(f)); rooms.update(r); objs.update(o)
        for o in objs.values():
            if o.location in rooms and o.name not in rooms[o.location].objects: rooms[o.location].objects.append(o.name)
        if not rooms: raise ValueError("no ZIL rooms found in %s" % src)
        from . import describe
        rts = {}
        for f in sorted(glob.glob(os.path.join(src, "*.zil"))): rts.update(describe.routines(open(f, errors="replace").read()))
        describe.fill(rooms, rts)
        return rooms, objs, os.path.basename(os.path.normpath(src)), None
    rooms, objs, info = zmachine.read_rooms(src)
    start = "R%d" % info["start"] if info.get("start") else None
    return rooms, objs, os.path.splitext(os.path.basename(src))[0], start


def map_game(src: str, outdir: str, start: str = None) -> str:
    rooms, objs, game, start0 = read_source(src); start = start or start0 or next(iter(rooms))
    ex = {n for n, r in rooms.items() if MAZE.search(r.desc or "") or MAZE.search(n)}
    if start in ex: ex.discard(start)
    word = lambda n: "Puzzle" if re.search("puzzle", rooms[n].desc or n, re.I) else "Maze"
    sh = lattice.build(rooms, start, ex, word=word)
    os.makedirs(outdir, exist_ok=True); base = os.path.join(outdir, game); title = "%s: graph-paper map as text, a square is two characters wide" % game
    mf = mapfile.build(rooms, objs, sh, game, title, start); mf["left_out"] = sorted(rooms[n].desc or n for n in ex); mapfile.save(base + ".map.json", mf); mapfile.save_zmap(base + ".zmap", mf)
    open(base + ".txt", "w").write(asciiart.render(rooms, sh, title, start, False)); open(base + ".ans", "w").write(asciiart.render(rooms, sh, title, start, True))
    open(base + ".svg", "w").write(sheetsvg.render(rooms, sh, "%s: rooms on a graph-paper lattice (3x3 per room)" % game))
    return base + ".map.json"
