# SPDX-License-Identifier: GPL-3.0-only
"""python -m zorkmapper SOURCE_DIR --svg out.svg [--start ROOM]: read every *.zil in SOURCE_DIR, lay the rooms out, write the SVG map and a text report."""
import argparse, glob, os, sys
from .model import parse_game
from . import layout, svgmap, lattice, sheetsvg
import re

PROFILES = {"zork1": r"^(MAZE-\d+|DEAD-END-[1-4])$", "zork2": r"DESC:^Oddly-angled Room$", "zork3": r"^CP$"}
STARTS = {"zork1": "WEST-OF-HOUSE", "zork2": "INSIDE-BARROW", "zork3": "ZORK2-STAIR"}
WORDS = {"zork1": "Maze", "zork2": "Maze", "zork3": "Puzzle"}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="zorkmapper"); ap.add_argument("source", nargs="?"); ap.add_argument("--svg"); ap.add_argument("--start", default=None); ap.add_argument("--sheet", action="store_true", help="graph-paper lattice map (3x3 blocks) instead of the 3-D grid flattening"); ap.add_argument("--exclude", default=None); ap.add_argument("--map", default=None, metavar="SRC", help="map a Z-machine story file (.dat/.z3/.z5) or a ZIL folder into ASCIIArt/ (json, txt, ans, svg)"); ap.add_argument("--ascii", default=None, help="write PREFIX.txt (plain Unicode) and PREFIX.ans (ANSI colour)"); ap.add_argument("--descriptions", default=None, help="write a plain-text file of room names and descriptions")
    a = ap.parse_args(argv)
    if a.map:
        from . import mapper
        print("wrote", mapper.map_game(a.map, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ASCIIArt"))); return
    rooms, objs = {}, {}
    for f in sorted(glob.glob(os.path.join(a.source, "*.zil"))):
        r, o = parse_game(open(f, errors="replace").read(), os.path.basename(f)); rooms.update(r); objs.update(o)
    for o in objs.values():
        if o.location in rooms and o.name not in rooms[o.location].objects: rooms[o.location].objects.append(o.name)
    if a.descriptions:
        from . import describe
        rts = {}
        for f in sorted(glob.glob(os.path.join(a.source, "*.zil"))): rts.update(describe.routines(open(f, errors="replace").read()))
        empty = describe.write_descriptions(rooms, rts, a.descriptions, os.path.basename(os.path.normpath(a.source)).title())
        print("wrote %s: %d rooms, %d without a fixed description" % (a.descriptions, len(rooms), empty))
    game = os.path.basename(os.path.normpath(a.source)); a.start = a.start or STARTS.get(game, "WEST-OF-HOUSE"); pat = a.exclude or PROFILES.get(game, "")
    if a.sheet:
        ex = {n for n, r in rooms.items() if pat and (re.search(pat[5:], r.desc) if pat.startswith("DESC:") else re.search(pat, n))}
        sh = lattice.build(rooms, a.start, ex, word=lambda n: WORDS.get(game, "Maze"))
        print("%d rooms (%d left out as %s), %d placed on the lattice: %d straight, %d connectors, %d stubs, %d loops, %d redundant, %d set apart" % (
            len(rooms), len(ex), WORDS.get(game, "maze"), len(sh.pos), sum(l.mode == "straight" for l in sh.links), sum(l.mode == "connector" for l in sh.links), len(sh.stubs), len(sh.loops), sh.redundant, len(sh.far)))
        if a.ascii:
            from . import asciiart
            t = "%s: graph-paper map as text, a square is two characters wide" % game.title()
            from . import mapfile
            mf = mapfile.build(rooms, objs, sh, game, t, a.start); mf["left_out"] = sorted(rooms[n].desc or n for n in ex); mapfile.save(a.ascii + ".map.json", mf)
            open(a.ascii + ".txt", "w").write(asciiart.render(rooms, sh, t, a.start, False)); open(a.ascii + ".ans", "w").write(asciiart.render(rooms, sh, t, a.start, True)); print("wrote", a.ascii + ".txt/.ans")
        if a.svg: open(a.svg, "w").write(sheetsvg.render(rooms, sh, "%s: rooms on a graph-paper lattice (3x3 per room)" % game.title())); print("wrote", a.svg)
        return
    a.start = a.start or STARTS.get(os.path.basename(os.path.normpath(a.source)), "WEST-OF-HOUSE")
    lay = layout.build(rooms, a.start)
    for i, n in enumerate(lay.order, 1): rooms[n].number = i
    print("%d rooms, %d objects, %d edges (%d one-way, %d irregular, %d portals); %d rooms nudged; %d islands" % (
        len(rooms), len(objs), len(lay.edges), sum(e.one_way for e in lay.edges), sum(e.irregular for e in lay.edges), sum(e.portal for e in lay.edges), len(lay.nudged), len(lay.islands)))
    if a.svg:
        open(a.svg, "w").write(svgmap.render(rooms, lay, title=os.path.basename(os.path.normpath(a.source)))); print("wrote", a.svg)


if __name__ == "__main__":
    main()
