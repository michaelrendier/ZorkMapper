"""ZorkMapper: the ZIL reader, the room model, the layout and the SVG, on small inline sources and (if fetched) the real Zork I."""
import os
import pytest
from zorkmapper.zil import read_all, Atom, Str, Form
from zorkmapper.model import parse_game, parse_exit
from zorkmapper import layout, svgmap

MINI = '''
<ROOM A (IN ROOMS) (DESC "Room A") (NORTH TO B) (EAST "A wall.") (DOWN PER GO-DOWN) (FLAGS RLANDBIT ONBIT)>
<ROOM B (IN ROOMS) (DESC "Room B") (SOUTH TO A) (WEST TO C IF DOOR IS OPEN) (UP TO C) (IN TO A)>
<ROOM C (IN ROOMS) (DESC "Room C") (DOWN TO B) (EAST TO C ELSE "nowhere")>
<OBJECT LAMP (IN A) (DESC "brass lamp") (FLAGS TAKEBIT) (SYNONYM LAMP LANTERN)>
;<ROOM IGNORED (DESC "commented out")>
'''


def test_reader_handles_strings_comments_and_nesting():
    n = read_all('<ROOM X (DESC "a \\"quoted\\" word") ;<ROOM Y> (NORTH TO Z)>')
    assert len(n) == 1 and isinstance(n[0], Form) and n[0].head == "ROOM"
    assert any(isinstance(i, Form) and not i.angle and i.head == "DESC" for i in n[0].items)


def test_rooms_exits_and_objects():
    rooms, objs = parse_game(MINI)
    assert set(rooms) == {"A", "B", "C"} and "IGNORED" not in rooms
    a = rooms["A"]
    assert a.exits["NORTH"].kind == "to" and a.exits["NORTH"].dest == "B"
    assert a.exits["EAST"].kind == "blocked" and a.exits["EAST"].message == "A wall."
    assert a.exits["DOWN"].kind == "per" and a.exits["DOWN"].func == "GO-DOWN"
    b = rooms["B"]
    assert b.exits["WEST"].kind == "cond" and b.exits["WEST"].condition == "DOOR IS OPEN"
    assert b.exits["IN"].kind == "to" and b.parent == "ROOMS"            # (IN TO A) is an exit, (IN ROOMS) the parent
    assert rooms["A"].objects == ["LAMP"] and objs["LAMP"].synonyms == ["LAMP", "LANTERN"]


def test_layout_places_by_direction_and_marks_one_way():
    rooms, _ = parse_game(MINI)
    lay = layout.build(rooms, "A")
    assert lay.pos["A"] == (0, 0, 0) and lay.pos["B"] == (0, -1, 0)
    e = {(x.a, x.b, x.direction): x for x in lay.edges}
    assert e[("A", "B", "NORTH")].one_way is False                        # B has SOUTH back to A
    assert e[("B", "C", "UP")].direction == "UP" and lay.pos["C"][2] in (1, -1, 0)
    assert e[("B", "A", "IN")].portal is True
    assert len(set(lay.pos.values())) == len(lay.pos)                    # no two rooms share a cell


def test_flat_projection_offsets_levels_diagonally():
    rooms, _ = parse_game(MINI); lay = layout.build(rooms, "A")
    lay.pos["B"] = (0, 0, 1); x, y = lay.flat("B"); assert x > 0 and y < 0   # one level up: right and up on the sheet


def test_svg_has_every_square_and_a_legend():
    rooms, _ = parse_game(MINI); lay = layout.build(rooms, "A"); s = svgmap.render(rooms, lay, "mini")
    assert s.startswith("<svg") and s.count("<rect") >= 3 + 1 and "Room A" in s and "Legend" in s


ZORK1 = os.path.join(os.path.dirname(__file__), "..", "sources", "zork1", "1dungeon.zil")


@pytest.mark.skipif(not os.path.exists(ZORK1), reason="run fetch_sources.sh first")
def test_zork1_counts():
    rooms, _ = parse_game(open(ZORK1).read())
    assert len(rooms) == 110
    lay = layout.build(rooms, "WEST-OF-HOUSE")
    assert len(lay.pos) == 110 and len(set(lay.pos.values())) == 110
    assert rooms["EAST-OF-HOUSE"].exits["IN"].kind == "cond" and rooms["EAST-OF-HOUSE"].exits["IN"].dest == "KITCHEN"


from zorkmapper import lattice, sheetsvg


def test_lattice_puts_rooms_two_squares_apart_with_one_path_square_between():
    rooms, _ = parse_game(MINI); sh = lattice.build(rooms, "A")
    assert sh.pos["A"] == (0, 0) and sh.pos["B"] == (0, -1)                 # lattice units: a room cell is (2a, 2b); one path square between
    assert sh.cell("B") == (0, -2)
    assert len(set(sh.pos.values())) == len(sh.pos)


def test_excluded_rooms_become_stubs_not_squares():
    rooms, _ = parse_game(MINI); sh = lattice.build(rooms, "A", excluded={"C"}, word=lambda n: "Maze")
    assert "C" not in sh.pos and any(w == "Maze" for _, _, w in sh.stubs)


def test_up_and_down_use_diagonals_and_carry_u_d():
    rooms, _ = parse_game(MINI); sh = lattice.build(rooms, "A"); up = [l for l in sh.links if l.direction == "UP"]
    assert up and up[0].vertical == "U" and (abs(up[0].vec[0]) == 1 and abs(up[0].vec[1]) == 1 or up[0].mode == "connector")


def test_sheet_svg_and_descriptions():
    from zorkmapper import describe
    rooms, _ = parse_game(MINI); sh = lattice.build(rooms, "A"); s = sheetsvg.render(rooms, sh, "mini")
    assert s.startswith("<svg") and "Room A" in s and 'font-weight="700"' in s
    assert describe.clean("A  b|c\n d") == "A b c d"
