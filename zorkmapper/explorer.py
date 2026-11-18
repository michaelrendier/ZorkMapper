# SPDX-License-Identifier: GPL-3.0-only
"""
zorkmapper.explorer: the console map explorer (the rough draft of the viewer).  Python curses, UTF-8, 256 colours.

    python3 -m zorkmapper.explorer [ASCIIArt/zork1.map.json]

Screen (every size is a PERCENTAGE of the terminal, so a bigger screen adds viewport and the map keeps its scale: two characters per grid square):
    top line        title and current room
    left   (16%)    legend: elevation colours (white = ground level, bright rainbow up, dark rainbow down)         [F2 toggles]
    centre          the map viewport; the current room is always at its centre
    right  (30%)    the room list and the current room: description, items, exits                                  [F3 toggles]
    bottom (22%)    status box and the function-key strip                                                          [F4 toggles]
Keys:  arrows go N/S/W/E along the map's exits (or to the nearest room that way); Shift-Up UPW, Shift-Down UPE, Shift-Left DW, Shift-Right DE;
       y u b n = NW NE SW SE; PgUp / PgDn = a level up / down; F7 or l = layer view; Tab / Shift-Tab = next / previous room; Home = start;
       F5 or Alt-O open a map; F6 or Alt-M map a game; F1 or Alt-H help; q, F10 or Alt-X quit.
"""
import curses
import glob
import locale
import os
import textwrap
from typing import Dict, List, Optional, Tuple
from . import levels, mapfile

PCT = {"left": 16, "right": 30, "bottom": 22}
MIN = {"left": 20, "right": 30, "bottom": 7}
DIRS = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "NE": (1, -1), "NW": (-1, -1), "SE": (1, 1), "SW": (-1, 1)}
ARROWS = {"KEY_UP": "NORTH", "KEY_DOWN": "SOUTH", "KEY_LEFT": "WEST", "KEY_RIGHT": "EAST", "y": "NW", "u": "NE", "b": "SW", "n": "SE"}
# shifted arrows (every version): up and down are drawn as diagonals; Shift-Up UPW, Shift-Down UPE, Shift-Left DW, Shift-Right DE
SHIFTED = {"KEY_SR": ("UP", "W"), "KEY_SF": ("UP", "E"), "KEY_SLEFT": ("DOWN", "W"), "KEY_SRIGHT": ("DOWN", "E")}
MAPS_DIR = os.environ.get("ZORKMAPPER_MAPS") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ASCIIArt")


# ------------------------------------------------------------------ pure parts (tested without a terminal)
def panel_layout(h: int, w: int, left: bool = True, right: bool = True, bottom: bool = True) -> Dict[str, Tuple[int, int, int, int]]:
    """rectangles (y, x, height, width) for each panel from percentages of the screen; the map viewport takes what is left"""
    lw = max(MIN["left"], w*PCT["left"]//100) if left else 0
    rw = max(MIN["right"], w*PCT["right"]//100) if right else 0
    bh = max(MIN["bottom"], h*PCT["bottom"]//100) if bottom else 0
    if lw + rw > w - 20: lw = 0 if lw >= rw else lw; rw = max(0, min(rw, w - lw - 20))
    top = 1; mh = max(3, h - top - bh); mw = max(10, w - lw - rw)
    return {"title": (0, 0, 1, w), "left": (top, 0, mh, lw), "map": (top, lw, mh, mw), "right": (top, lw + mw, mh, rw), "bottom": (top + mh, 0, h - top - mh, w)}


def view_origin(room_row: int, room_col: int, vh: int, vw: int) -> Tuple[int, int]:
    """top-left corner of the visible part of the canvas so that the room's square is at the centre of the viewport (no clamping: the edge of the map shows blank)"""
    return room_row - vh//2, room_col + 1 - vw//2


def neighbour(data: dict, cur: int, direction: str) -> Optional[int]:
    """the room reached by going `direction`: the map's own exit first (it follows long runs and connectors), else the nearest room that way on the sheet"""
    r = data["rooms"][str(cur)]
    for e in r["exits"]:
        if e["dir"] == direction and e["dest"] and e["kind"] in ("to", "cond"): return e["dest"]
    if direction not in DIRS: return None
    dx, dy = DIRS[direction]; best, bd = None, 1e9
    for k, o in data["rooms"].items():
        k = int(k)
        if k == cur: continue
        ox, oy = (o["col"] - r["col"])/4.0, (o["row"] - r["row"])/2.0
        along = ox*dx + oy*dy; across = abs(ox*dy - oy*dx)
        if along > 0.5 and across <= along*0.6 + 0.3:
            d = along + across*2
            if d < bd: best, bd = k, d
    return best


def vertical(data: dict, cur: int, direction: str, side: str) -> Optional[int]:
    """UP / DOWN go by the exit; `side` (W or E) prefers the exit whose room lies on that side of this one, else any exit of that kind"""
    r = data["rooms"][str(cur)]; any_ = None
    for e in r["exits"]:
        if e["dir"] != direction or not e["dest"] or e["kind"] not in ("to", "cond"): continue
        any_ = any_ or e["dest"]; c = data["rooms"][str(e["dest"])]["col"]
        if (side == "W" and c < r["col"]) or (side == "E" and c > r["col"]): return e["dest"]
    return any_


def level_jump(data: dict, cur: int, dz: int) -> Optional[int]:
    """the nearest room (on the sheet) one elevation level up (+1) or down (-1)"""
    r = data["rooms"][str(cur)]
    if r["level"] is None: return None
    best, bd = None, 1e9
    for k, o in data["rooms"].items():
        if o["level"] == r["level"] + dz:
            d = ((o["col"] - r["col"])/4.0)**2 + ((o["row"] - r["row"])/2.0)**2
            if d < bd: best, bd = int(k), d
    return best


def step_number(data: dict, cur: int, delta: int) -> int:
    n = len(data["rooms"]); return (cur - 1 + delta) % n + 1


def sidebar_window(total: int, cur: int, rows: int) -> Tuple[int, int]:
    """first and last room index (1-based) shown in a list of `rows` lines, keeping the current room visible and near the middle"""
    top = max(1, min(cur - rows//2, total - rows + 1)); return top, min(total, top + rows - 1)


def wrap(text: str, width: int) -> List[str]:
    return textwrap.wrap(text, max(8, width)) if text else []


def list_maps(dirpath: str = MAPS_DIR) -> List[str]:
    return sorted(glob.glob(os.path.join(dirpath, "*.map.json")))


# ------------------------------------------------------------------ screens: one real (curses) and one fake (tests)
class FakeScreen:
    def __init__(self, h, w): self.h, self.w, self.cells = h, w, [[(" ", None) for _ in range(w)] for _ in range(h)]
    def size(self): return self.h, self.w
    def put(self, y, x, s, style=None):
        for i, ch in enumerate(s):
            if 0 <= y < self.h and 0 <= x + i < self.w: self.cells[y][x + i] = (ch, style)
    def text(self): return ["".join(c for c, _ in row).rstrip() for row in self.cells]
    def clear(self): self.cells = [[(" ", None) for _ in range(self.w)] for _ in range(self.h)]
    def refresh(self): pass


class CursesScreen:
    def __init__(self, scr): self.scr = scr; self.pairs: Dict[Tuple[int, int], int] = {}
    def size(self): return self.scr.getmaxyx()
    def _attr(self, style):
        if not style: return 0
        fg, bg, flags = style
        key = (fg, bg)
        if key not in self.pairs and len(self.pairs) < curses.COLOR_PAIRS - 2:
            n = len(self.pairs) + 1
            try: curses.init_pair(n, fg, bg)
            except curses.error: n = 0
            self.pairs[key] = n
        a = curses.color_pair(self.pairs.get(key, 0))
        return a | (curses.A_BOLD if "b" in flags else 0) | (curses.A_REVERSE if "r" in flags else 0) | (curses.A_DIM if "d" in flags else 0)
    def put(self, y, x, s, style=None):
        h, w = self.size()
        if y < 0 or y >= h or x >= w: return
        if x < 0: s = s[-x:]; x = 0
        s = s[:max(0, w - x - (1 if y == h - 1 else 0))]
        try: self.scr.addstr(y, x, s, self._attr(style))
        except curses.error: pass
    def clear(self): self.scr.erase()
    def refresh(self): self.scr.refresh()


def style_for_bg(code):
    return (0 if levels.black_text(code) else 15, code, "")


# ------------------------------------------------------------------ drawing
class State:
    def __init__(self, data: Optional[dict] = None, path: str = ""):
        self.data, self.path = data, path; self.cur = 1; self.left = self.right = self.bottom = True; self.msg = "Open a map with F5, or map a game with F6."
        self.help = False; self.layer = False


def draw(screen, st: State):
    screen.clear(); h, w = screen.size(); lay = panel_layout(h, w, st.left, st.right, st.bottom)
    d = st.data
    if not d:
        screen.put(0, 0, " ZorkMapper explorer ", (15, 4, "b")); screen.put(2, 2, "No map loaded.  F5 / Alt-O: open a map from ASCIIArt/    F6 / Alt-M: map a game    F10 / q: quit"); draw_bottom(screen, st, lay); return
    room = d["rooms"][str(st.cur)]
    screen.put(0, 0, (" %s  |  room %02d: %s  |  level %s%s " % (d["title"].split(":")[0], st.cur, room["name"], levels.label(room["level"]), "  [LAYER VIEW]" if st.layer else "")).ljust(w), (15, 4, "b"))
    my, mx, mh, mw = lay["map"]
    oy, ox = view_origin(room["row"], room["col"], mh, mw)
    for r in range(mh):
        cy = oy + r
        if 0 <= cy < len(d["canvas"]):
            line = d["canvas"][cy]; seg = line[max(0, ox):max(0, ox) + mw - max(0, -ox)] if ox + mw > 0 else ""
            screen.put(my + r, mx + max(0, -ox), seg, (8, -1, ""))
    for sp in d["spans"]:                                           # room squares in their level colour; the current room is marked with > <
        y, x = my + sp["row"] - oy, mx + sp["col"] - ox
        if my <= y < my + mh and mx <= x < mx + mw - 1:
            cur = sp["n"] == st.cur
            lab = d["canvas"][sp["row"]][sp["col"]:sp["col"] + 2]
            if st.layer and sp["z"] != room["level"]: screen.put(y, x, "\u00b7\u00b7", (8, -1, "d")); continue         # another layer: a faint placeholder
            screen.put(y, x, lab, style_for_bg(sp["bg"]) if not cur else (0 if levels.black_text(sp["bg"]) else 15, sp["bg"], "br"))
            if cur:
                screen.put(y, x - 1, ">", (11, -1, "b")); screen.put(y, x + 2, "<", (11, -1, "b"))
    if lay["left"][3]: draw_legend(screen, st, lay["left"])
    if lay["right"][3]: draw_right(screen, st, lay["right"])
    draw_bottom(screen, st, lay)


def draw_legend(screen, st, rect):
    y0, x0, hh, ww = rect; d = st.data; screen.put(y0, x0 + 1, "Elevation", (11, -1, "b"))
    zc = d["rooms"][str(st.cur)]["level"]
    for i, lv in enumerate(d["levels"]):
        if 2 + i >= hh: break
        mark = ">" if lv["z"] == zc else " "
        screen.put(y0 + 1 + i, x0, mark, (11, -1, "b")); screen.put(y0 + 1 + i, x0 + 1, "  ", style_for_bg(lv["bg"]))
        screen.put(y0 + 1 + i, x0 + 4, ("%+d %s" % (lv["z"], lv["label"].split(":")[-1].strip() if lv["z"] else "ground"))[:ww - 9] + " " + str(lv["rooms"]))
    n = len(d["levels"]) + 2
    for j, t in enumerate(["white = ground", "up: bright rainbow", "down: dark rainbow"]):
        if n + j < hh: screen.put(y0 + n + j, x0 + 1, t[:ww - 2], (8, -1, ""))


def draw_right(screen, st, rect):
    y0, x0, hh, ww = rect; d = st.data; total = len(d["rooms"]); lr = max(3, hh//2 - 1)
    screen.put(y0, x0 + 1, "Rooms", (11, -1, "b"))
    a, b = sidebar_window(total, st.cur, lr)
    for i, n in enumerate(range(a, b + 1)):
        r = d["rooms"][str(n)]; cur = n == st.cur
        screen.put(y0 + 1 + i, x0, ">" if cur else " ", (11, -1, "b")); screen.put(y0 + 1 + i, x0 + 1, "%02d" % n if n < 100 else "**", style_for_bg(levels.bg(r["level"])))
        screen.put(y0 + 1 + i, x0 + 4, r["name"][:ww - 5], (15, -1, "b") if cur else None)
    dy = y0 + lr + 2; r = d["rooms"][str(st.cur)]
    screen.put(dy - 1, x0 + 1, "-" * (ww - 2), (8, -1, ""))
    lines = [(r["name"], (15, -1, "b"))] + [(t, None) for t in wrap(r["desc"] or "(no fixed description in this source)", ww - 2)]
    if r["items"]: lines += [("Items: " + ", ".join(r["items"]), (14, -1, ""))]
    ex = ["%s %s" % (e["dir"][:5], ("-> %02d %s" % (e["dest"], e["dest_name"] or "")) if e["dest"] else ("(routine)" if e["kind"] == "per" else "x")) for e in r["exits"]]
    for t in ex: lines.append((t, (10, -1, "")))
    for i, (t, sty) in enumerate(lines):
        if dy + i >= y0 + hh: break
        screen.put(dy + i, x0 + 1, t[:ww - 2], sty)


def draw_bottom(screen, st, lay):
    y0, x0, hh, ww = lay["bottom"]
    if hh <= 0: return
    keys = " F1 Help  F2 Legend  F3 Sidebar  F4 Status  F5 Open  F6 Map a game  Home Start  Tab Next  F10 Quit "
    screen.put(y0 + hh - 1, 0, keys[:ww].ljust(ww), (0, 6, ""))
    screen.put(y0, 0, " Status ".ljust(ww, "-"), (8, -1, ""))
    if st.help:
        for i, t in enumerate(__doc__.split("Keys:")[1].strip().splitlines()):
            if 1 + i < hh - 1: screen.put(y0 + 1 + i, 1, t[:ww - 2])
    else:
        for i, t in enumerate(wrap(st.msg, ww - 2)[:hh - 2]): screen.put(y0 + 1 + i, 1, t)


# ------------------------------------------------------------------ keys and the loop
def handle_key(st: State, key: str) -> Optional[str]:
    """update the state for one key; returns a command ('quit', 'open', 'map') for the loop to run, else None"""
    if key in ("q", "KEY_F(10)", "M-x"): return "quit"
    if key in ("KEY_F(5)", "M-o", "o"): return "open"
    if key in ("KEY_F(6)", "M-m", "m"): return "map"
    if key in ("KEY_F(1)", "M-h", "h", "?"): st.help = not st.help; return None
    if key == "KEY_F(2)": st.left = not st.left
    elif key == "KEY_F(3)": st.right = not st.right
    elif key == "KEY_F(4)": st.bottom = not st.bottom
    if not st.data: return None
    if key in ("\t", "KEY_RIGHT_TAB"): st.cur = step_number(st.data, st.cur, 1); st.msg = ""
    elif key == "KEY_BTAB": st.cur = step_number(st.data, st.cur, -1); st.msg = ""
    elif key in ("KEY_HOME",): st.cur = st.data.get("start", 1)
    elif key in ARROWS:
        n = neighbour(st.data, st.cur, ARROWS[key])
        if n: st.cur = n; st.msg = ""
        else: st.msg = "No way %s from here." % ARROWS[key].lower()
    elif key in SHIFTED:
        n = vertical(st.data, st.cur, *SHIFTED[key])
        if n: st.cur = n; st.msg = ""
        else: st.msg = "No way %s from here." % SHIFTED[key][0].lower()
    elif key in ("KEY_PPAGE", "KEY_NPAGE"):
        n = level_jump(st.data, st.cur, 1 if key == "KEY_PPAGE" else -1)
        if n: st.cur = n; st.msg = ""
        else: st.msg = "No room on that level."
    elif key in ("KEY_F(7)", "l"): st.layer = not st.layer; st.msg = "Layer view: only this elevation layer in colour; PgUp / PgDn change layer." if st.layer else "Layer view off."
    return None


def read_key(scr) -> str:
    c = scr.get_wch()
    if isinstance(c, str):
        if c == "\x1b":                                              # Alt-letter arrives as ESC then the letter
            scr.timeout(25)
            try: c2 = scr.get_wch()
            except curses.error: c2 = None
            scr.timeout(-1)
            return "M-" + c2 if isinstance(c2, str) else "ESC"
        return "\t" if c == "\t" else c
    return curses.keyname(c).decode() if c != curses.KEY_BTAB else "KEY_BTAB"


def prompt(screen_, scr, title: str, items: List[str]) -> Optional[str]:
    """a centred menu: arrows choose, Enter selects, Esc cancels"""
    i = 0
    while True:
        h, w = screen_.size(); bw = min(w - 4, max(len(title), *(len(os.path.basename(x)) for x in items)) + 8) if items else 40
        y0, x0 = max(1, h//2 - len(items)//2 - 2), max(0, (w - bw)//2)
        screen_.put(y0, x0, (" " + title).ljust(bw), (15, 4, "b"))
        for k, it in enumerate(items): screen_.put(y0 + 1 + k, x0, (" " + os.path.basename(it)).ljust(bw), (0, 7, "r") if k == i else (0, 7, ""))
        screen_.refresh(); key = read_key(scr)
        if key == "KEY_UP": i = (i - 1) % len(items)
        elif key == "KEY_DOWN": i = (i + 1) % len(items)
        elif key in ("\n", "\r", "KEY_ENTER"): return items[i]
        elif key in ("ESC", "q"): return None


def ask_text(screen_, scr, label: str) -> str:
    buf = ""; curses.curs_set(1)
    while True:
        h, w = screen_.size(); screen_.put(h - 2, 0, (label + buf).ljust(w - 1), (15, 4, "b")); screen_.refresh(); k = read_key(scr)
        if k in ("\n", "\r", "KEY_ENTER"): curses.curs_set(0); return buf
        if k == "ESC": curses.curs_set(0); return ""
        if k in ("KEY_BACKSPACE", "\x7f", "\b"): buf = buf[:-1]
        elif len(k) == 1: buf += k


def load_into(st: State, path: str):
    st.data = mapfile.load(path); st.path = path; st.cur = st.data.get("start", 1); st.msg = "Loaded %s: %d rooms." % (os.path.basename(path), len(st.data["rooms"]))


def run(scr, path: Optional[str] = None):
    curses.curs_set(0); curses.start_color(); curses.use_default_colors(); scr.keypad(True)
    screen_ = CursesScreen(scr); st = State()
    if path: load_into(st, path)
    else:
        maps = list_maps()
        if maps:
            ch = prompt(screen_, scr, "Open a map (ASCIIArt/)", maps)
            if ch: load_into(st, ch)
    while True:
        draw(screen_, st); screen_.refresh(); cmd = handle_key(st, read_key(scr))
        if cmd == "quit": return
        if cmd == "open":
            maps = list_maps(); ch = prompt(screen_, scr, "Open a map (ASCIIArt/)", maps) if maps else None
            if ch: load_into(st, ch)
        if cmd == "map":
            src = ask_text(screen_, scr, "Map a game: path to a Z-machine file or a ZIL source folder > ")
            if src:
                try:
                    from . import mapper
                    out = mapper.map_game(src, MAPS_DIR); load_into(st, out); st.msg = "Mapped %s -> %s" % (src, out)
                except Exception as e:
                    st.msg = "Could not map %s: %s" % (src, e)


def main(argv=None):
    import sys
    locale.setlocale(locale.LC_ALL, ""); path = (argv or sys.argv[1:] or [None])[0]
    curses.wrapper(run, path)


if __name__ == "__main__":
    main()
