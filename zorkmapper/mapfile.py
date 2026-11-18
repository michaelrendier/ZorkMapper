# SPDX-License-Identifier: GPL-3.0-only
"""zorkmapper.mapfile: the map file the console explorer reads (ASCIIArt/NAME.map.json): the text canvas, the room squares with their level colours,
and for every room its name, description, items and exits (with the destination room NUMBER).  Plain JSON, no code."""
import json
from typing import Dict
from .model import Room, GameObject
from .lattice import Sheet
from . import asciiart, levels

FORMAT = "zorkmapper.map/1"


def build(rooms: Dict[str, Room], objs: Dict[str, GameObject], sh: Sheet, game: str, title: str, start: str) -> dict:
    lines, spans, zl = asciiart.render(rooms, sh, title, start, False, canvas_only=True)
    num = {n: i for i, n in enumerate(sh.order, 1)}; span = {s["n"]: s for s in spans}; out_rooms = {}
    for n in sh.order:
        r = rooms[n]; i = num[n]
        exits = []
        for d, e in r.exits.items():
            exits.append({"dir": d, "kind": e.kind, "dest": num.get(e.dest) if e.dest else None, "dest_name": (rooms[e.dest].desc if e.dest in rooms else None),
                          "cond": e.condition, "msg": e.message, "func": e.func})
        items = [(objs[o].desc if o in objs and objs[o].desc else o.title()) for o in r.objects]
        out_rooms[str(i)] = {"name": r.desc or n.title(), "id": n, "desc": r.ldesc.strip() or "", "items": items, "flags": r.flags, "level": zl.get(n),
                             "row": span[i]["row"], "col": span[i]["col"], "exits": exits, "source": "%s:%d" % (r.source, r.line)}
    lv = sorted({s["z"] for s in spans if s["z"] is not None}, reverse=True)
    return {"format": FORMAT, "game": game, "title": title, "start": 1, "canvas": lines, "spans": spans, "rooms": out_rooms,
            "levels": [{"z": z, "bg": levels.bg(z), "label": levels.label(z), "rooms": sum(1 for s in spans if s["z"] == z)} for z in lv],
            "left_out": [], "set_apart": [num[n] for n in sh.far if n in num]}


def save(path: str, data: dict):
    with open(path, "w") as fh: json.dump(data, fh, ensure_ascii=False)


def load(path: str) -> dict:
    d = json.load(open(path))
    if d.get("format") != FORMAT: raise ValueError("not a zorkmapper map file: %s" % path)
    return d
