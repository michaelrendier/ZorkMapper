# SPDX-License-Identifier: GPL-3.0-only
"""zorkmapper.describe: the text a game shows for each room, taken from the ZIL: the LDESC property, or else the strings the room's ACTION routine prints
on M-LOOK.  Plain text, one block per room: the room name, then its description."""
import re
from typing import Dict, List
from .zil import Atom, Form, Str, read_all
from .model import Room


def routines(text: str) -> Dict[str, Form]:
    out = {}
    for n in read_all(text):
        if isinstance(n, Form) and n.angle and n.head == "ROUTINE" and len(n.items) > 1 and isinstance(n.items[1], Atom): out[n.items[1].name] = n
    return out


def _strings(node) -> List[str]:
    if isinstance(node, Str): return [node.text]
    if isinstance(node, Form):
        if node.angle and node.head in ("TELL", "PRINTI", "PRINT"): return [s for it in node.items[1:] for s in _strings(it)]
        return [s for it in node.items for s in _strings(it)]
    return []


def _mlook(form: Form) -> List[str]:
    """strings printed inside any COND clause whose test mentions M-LOOK"""
    found = []
    def walk(n):
        if isinstance(n, Form):
            if not n.angle and n.items and isinstance(n.items[0], Form) and "M-LOOK" in repr(n.items[0].items):
                for body in n.items[1:]: found.extend(_strings(body))
            for it in n.items: walk(it)
    walk(form); return found


def clean(s: str) -> str:
    s = s.replace("|", " ").replace("\n", " "); return re.sub(r"\s+", " ", s).strip()


def room_text(r: Room, rts: Dict[str, Form]) -> str:
    t = clean(r.ldesc)                                  # LDESC " " is a placeholder: the text is printed by the ACTION routine
    if t: return t
    f = rts.get(r.action or "")
    return clean(" ".join(_mlook(f))) if f else ""


def write_descriptions(rooms: Dict[str, Room], rts: Dict[str, Form], path: str, title: str):
    n_empty = 0
    with open(path, "w") as fh:
        fh.write("%s: room names and descriptions (from the ZIL source)\n\n" % title)
        for r in rooms.values():
            t = room_text(r, rts); n_empty += (not t)
            fh.write("%s\n%s\n\n" % (r.desc or r.name.title(), t or "(no fixed description in the source: the game builds this room's text in a routine)"))
    return n_empty


def fill(rooms: Dict[str, Room], rts: Dict[str, Form]):
    """give every room its description: LDESC, else the M-LOOK text of its ACTION routine (stored back in room.ldesc)"""
    for r in rooms.values():
        if not clean(r.ldesc): r.ldesc = room_text(r, rts)
