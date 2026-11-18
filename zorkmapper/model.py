# SPDX-License-Identifier: GPL-3.0-only
"""zorkmapper.model: dataclasses for a game's rooms, exits and objects, built from ZIL forms."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .zil import Atom, Form, Str, top_forms

COMPASS = ("NORTH", "NE", "EAST", "SE", "SOUTH", "SW", "WEST", "NW", "UP", "DOWN", "IN", "OUT", "LAND", "LAUNCH", "CROSS", "ENTER", "EXIT")
OPPOSITE = {"NORTH": "SOUTH", "SOUTH": "NORTH", "EAST": "WEST", "WEST": "EAST", "NE": "SW", "SW": "NE", "NW": "SE", "SE": "NW",
            "UP": "DOWN", "DOWN": "UP", "IN": "OUT", "OUT": "IN"}


@dataclass
class Exit:
    """one exit of a room.  kind: 'to' (always), 'cond' (TO ... IF flag [ELSE msg]), 'per' (a routine decides), 'blocked' (a message only)"""
    direction: str
    kind: str
    dest: Optional[str] = None
    condition: Optional[str] = None       # e.g. 'KITCHEN-WINDOW IS OPEN' or a global flag name
    func: Optional[str] = None            # the PER routine
    message: Optional[str] = None         # the refusal text (blocked) or the ELSE text (cond)


@dataclass
class GameObject:
    name: str
    desc: str = ""
    location: Optional[str] = None
    flags: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    action: Optional[str] = None
    line: int = 0


@dataclass
class Room:
    """everything the source says about one room: what the info panel will show"""
    name: str
    desc: str = ""
    ldesc: str = ""
    flags: List[str] = field(default_factory=list)
    exits: Dict[str, Exit] = field(default_factory=dict)
    globals: List[str] = field(default_factory=list)
    action: Optional[str] = None
    parent: Optional[str] = None
    objects: List[str] = field(default_factory=list)     # names of objects whose (IN ...) is this room
    source: str = ""
    line: int = 0
    number: int = 0                                      # square number on the map, assigned by the layout


def _props(form: Form):
    for it in form.items[2:]:
        if isinstance(it, Form) and not it.angle and it.items and isinstance(it.items[0], Atom): yield it.items[0].name, it.items[1:]


def _text(vals) -> str:
    return " ".join(v.text if isinstance(v, Str) else repr(v) for v in vals)


def _is_exit_vals(vals) -> bool:
    a = vals[0] if vals else None
    return isinstance(a, Str) or (isinstance(a, Atom) and a.name in ("TO", "PER", "SORRY"))


def parse_exit(direction: str, vals: list) -> Optional[Exit]:
    """(DIR TO ROOM) | (DIR TO ROOM IF FLAG [IS OPEN|CLOSED]) [ELSE "msg"] | (DIR PER ROUTINE) | (DIR "message") | (DIR SORRY "msg")"""
    if not vals: return None
    a = vals[0]
    if isinstance(a, Str): return Exit(direction, "blocked", message=a.text)
    if isinstance(a, Atom) and a.name == "PER" and len(vals) > 1: return Exit(direction, "per", func=repr(vals[1]))
    if isinstance(a, Atom) and a.name == "TO" and len(vals) > 1:
        dest = repr(vals[1]); rest = vals[2:]
        if rest and isinstance(rest[0], Atom) and rest[0].name == "IF":
            cond, msg, i = [], None, 1
            while i < len(rest):
                if isinstance(rest[i], Atom) and rest[i].name == "ELSE": msg = _text(rest[i + 1:]); break
                cond.append(repr(rest[i])); i += 1
            return Exit(direction, "cond", dest=dest, condition=" ".join(cond), message=msg)
        return Exit(direction, "to", dest=dest)
    if isinstance(a, Atom) and a.name == "SORRY": return Exit(direction, "blocked", message=_text(vals[1:]))
    return Exit(direction, "blocked", message=_text(vals))


def parse_game(text: str, source: str = "") -> (Dict[str, Room], Dict[str, GameObject]):
    """read rooms and objects out of ZIL text; objects are attached to their rooms"""
    rooms: Dict[str, Room] = {}; objs: Dict[str, GameObject] = {}
    for f in top_forms(text):
        if len(f.items) < 2 or not isinstance(f.items[1], Atom): continue
        name = f.items[1].name
        if f.head == "ROOM":
            r = Room(name=name, source=source, line=f.line)
            for key, vals in _props(f):
                if key == "DESC": r.desc = _text(vals)
                elif key == "LDESC": r.ldesc = _text(vals)
                elif key == "FLAGS": r.flags = [repr(v) for v in vals]
                elif key == "GLOBAL": r.globals = [repr(v) for v in vals]
                elif key == "ACTION": r.action = _text(vals)
                elif key == "IN" and not _is_exit_vals(vals): r.parent = _text(vals)          # (IN ROOMS) is the parent; (IN TO KITCHEN ...) is an exit
                elif key in COMPASS:
                    e = parse_exit(key, vals)
                    if e: r.exits[key] = e
            rooms[name] = r
        else:
            o = GameObject(name=name, line=f.line)
            for key, vals in _props(f):
                if key == "DESC": o.desc = _text(vals)
                elif key == "IN": o.location = _text(vals)
                elif key == "FLAGS": o.flags = [repr(v) for v in vals]
                elif key == "SYNONYM": o.synonyms = [repr(v) for v in vals]
                elif key == "ACTION": o.action = _text(vals)
            objs[name] = o
    for o in objs.values():
        if o.location in rooms: rooms[o.location].objects.append(o.name)
    return rooms, objs
