# SPDX-License-Identifier: GPL-3.0-only
"""python -m zorkmapper SOURCE_DIR --svg out.svg [--start ROOM]: read every *.zil in SOURCE_DIR, lay the rooms out, write the SVG map and a text report."""
import argparse, glob, os, sys
from .model import parse_game
from . import layout, svgmap


def main(argv=None):
    ap = argparse.ArgumentParser(prog="zorkmapper"); ap.add_argument("source"); ap.add_argument("--svg"); ap.add_argument("--start", default="WEST-OF-HOUSE")
    a = ap.parse_args(argv); rooms, objs = {}, {}
    for f in sorted(glob.glob(os.path.join(a.source, "*.zil"))):
        r, o = parse_game(open(f, errors="replace").read(), os.path.basename(f)); rooms.update(r); objs.update(o)
    for o in objs.values():
        if o.location in rooms and o.name not in rooms[o.location].objects: rooms[o.location].objects.append(o.name)
    lay = layout.build(rooms, a.start)
    for i, n in enumerate(lay.order, 1): rooms[n].number = i
    print("%d rooms, %d objects, %d edges (%d one-way, %d irregular, %d portals); %d rooms nudged; %d islands" % (
        len(rooms), len(objs), len(lay.edges), sum(e.one_way for e in lay.edges), sum(e.irregular for e in lay.edges), sum(e.portal for e in lay.edges), len(lay.nudged), len(lay.islands)))
    if a.svg:
        open(a.svg, "w").write(svgmap.render(rooms, lay, title=os.path.basename(os.path.normpath(a.source)))); print("wrote", a.svg)


if __name__ == "__main__":
    main()
