"""The Z-machine story-file reader, validated against the ZIL source where both exist (Zork I)."""
import glob
import os
import pytest
from zorkmapper import zmachine as Z
from zorkmapper.model import parse_game

DAT = "/home/rendier/Games/dosbox/zork/data/1-zork1.dat"
SRC = os.path.join(os.path.dirname(__file__), "..", "sources", "zork1")
pytestmark = pytest.mark.skipif(not os.path.exists(DAT), reason="needs the Zork I story file")


def test_directions_come_from_the_dictionary():
    st = Z.Story(open(DAT, "rb").read()); votes = st.direction_properties()
    best = {n: max(v, key=lambda k: v[k]) for n, v in votes.items()}
    assert best["NORTH"] == 31 and best["EAST"] == 30 and best["DOWN"] == 22 and best["OUT"] == 20


def test_zork1_rooms_and_start():
    rooms, objs, info = Z.read_rooms(DAT)
    assert info["version"] == 3 and len(rooms) == 110
    start = rooms["R%d" % info["start"]]; assert start.desc == "West of House"


@pytest.mark.skipif(not os.path.exists(os.path.join(SRC, "1dungeon.zil")), reason="needs sources/zork1")
def test_story_file_matches_the_zil_source_exactly():
    from collections import Counter
    rooms = {}
    for f in glob.glob(os.path.join(SRC, "*.zil")):
        r, _ = parse_game(open(f, errors="replace").read(), f); rooms.update(r)
    zr, _, _ = Z.read_rooms(DAT)
    def sig(rs, r):
        return tuple(sorted(((d, e.kind if e.kind in ("to", "cond", "per") else "blocked", (rs[e.dest].desc if e.dest in rs else None)) for d, e in r.exits.items() if e.kind in ("to", "cond", "per", "blocked")), key=str))
    A = Counter((r.desc, sig(rooms, r)) for r in rooms.values()); B = Counter((r.desc, sig(zr, r)) for r in zr.values())
    assert sum((A & B).values()) == 110
