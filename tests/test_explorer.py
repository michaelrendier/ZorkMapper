"""The explorer's pure parts and its drawing, on a fake screen (no terminal needed)."""
import os
import pytest
from zorkmapper import explorer as E, mapfile

MAP = os.path.join(os.path.dirname(__file__), "..", "ASCIIArt", "zork1.map.json")
pytestmark = pytest.mark.skipif(not os.path.exists(MAP), reason="needs ASCIIArt/zork1.map.json (python3 -m zorkmapper sources/zork1 --sheet --ascii ASCIIArt/zork1)")


def test_panel_layout_is_percentages_and_fills_the_screen():
    for h, w in ((24, 80), (50, 200), (30, 120)):
        L = E.panel_layout(h, w)
        assert L["map"][2] + L["bottom"][2] + 1 == h and L["left"][3] + L["map"][3] + L["right"][3] == w
    big, small = E.panel_layout(60, 240), E.panel_layout(30, 120)
    assert big["map"][3] > small["map"][3]                      # a bigger screen adds viewport
    assert E.panel_layout(30, 120, left=False, right=False, bottom=False)["map"][3] == 120


def test_current_room_is_centred():
    oy, ox = E.view_origin(40, 60, 21, 51); assert (40 - oy, 61 - ox) == (10, 25)


def test_neighbour_follows_exits_then_geometry():
    d = mapfile.load(MAP); assert E.neighbour(d, 1, "NORTH") == 2 and E.neighbour(d, 1, "WEST") == 4
    assert E.step_number(d, len(d["rooms"]), 1) == 1 and E.step_number(d, 1, -1) == len(d["rooms"])


def test_sidebar_window_keeps_current_visible():
    for cur in (1, 50, 91):
        a, b = E.sidebar_window(91, cur, 12); assert a <= cur <= b and b - a + 1 == 12


def test_draw_shows_room_legend_and_details():
    d = mapfile.load(MAP); st = E.State(d, MAP); scr = E.FakeScreen(40, 140); E.draw(scr, st); t = "\n".join(scr.text())
    assert "West of House" in t and "Elevation" in t and "ground" in t and "Rooms" in t and "F10 Quit" in t
    st.right = False; scr2 = E.FakeScreen(40, 140); E.draw(scr2, st); assert "Rooms" not in "\n".join(scr2.text())


def test_keys_move_and_toggle():
    d = mapfile.load(MAP); st = E.State(d, MAP)
    E.handle_key(st, "KEY_UP"); assert st.cur == 2
    E.handle_key(st, "\t"); assert st.cur == 3
    E.handle_key(st, "KEY_HOME"); assert st.cur == 1
    E.handle_key(st, "KEY_F(3)"); assert st.right is False
    assert E.handle_key(st, "q") == "quit" and E.handle_key(st, "KEY_F(5)") == "open" and E.handle_key(st, "M-m") == "map"
