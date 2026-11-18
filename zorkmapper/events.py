# SPDX-License-Identifier: GPL-3.0-only
"""
zorkmapper.events: what the exit table does not say.

TELEPORTS: moves that are not exits.  Found in the ZIL by reading routines: a `<GOTO ,ROOM>` inside an object's ACTION routine (the object sits in the
room, or the room lists it under GLOBAL), or inside a COND clause whose test is `<EQUAL? ,HERE ,ROOM>`, where the destination is not already a neighbour
by an exit.  Moves the ZIL builds from a local variable are listed by hand in data/teleports.json (checked against the source).

VERSIONS: a room whose description changes when a game FLAG is set.  Found by reading the ACTION routine's M-LOOK text for COND clauses on a global flag
(`,FLAG` or `<NOT ,FLAG>`) and evaluating the text with the flag off (before) and on (after).  Only an IRREVERSIBLE flag counts (the thief is dead, the
earthquake has happened): one that is set to true somewhere and never set back to false anywhere in the game.  A flag that is switched both ways (the
tide, a lamp) is not an event.
"""
import json
import os
from typing import Dict, List, Optional, Set
from .zil import Atom, Form, Str
from .model import Room, GameObject
from . import describe


def _walk(node):
    yield node
    if isinstance(node, Form):
        for it in node.items: yield from _walk(it)


def _flag(test) -> Optional[tuple]:
    """(flag name, wanted value) if the COND test is `,FLAG` or `<NOT ,FLAG>`"""
    if isinstance(test, Atom) and test.name.startswith(",") and len(test.name) > 1: return test.name[1:], True
    if isinstance(test, Form) and test.angle and test.head == "NOT" and len(test.items) == 2:
        a = test.items[1]
        if isinstance(a, Atom) and a.name.startswith(","): return a.name[1:], False
    return None


def _text(body, flags: Dict[str, bool]) -> List[str]:
    """the strings a clause body prints when the given flags have these values (clauses on other conditions are skipped)"""
    out: List[str] = []
    for n in body:
        if isinstance(n, Form) and n.angle and n.head in ("TELL", "PRINTI"): out += [it.text for it in n.items[1:] if isinstance(it, Str)]
        elif isinstance(n, Form) and n.angle and n.head == "COND":
            for cl in n.items[1:]:
                if not isinstance(cl, Form) or not cl.items: continue
                test = cl.items[0]; f = _flag(test); ok = None
                if isinstance(test, Atom) and test.name == "T": ok = True
                elif f and f[0] in flags: ok = flags[f[0]] == f[1]
                if ok: out += _text(cl.items[1:], flags); break
    return out


def _mlook_body(routine: Form) -> Optional[list]:
    for n in _walk(routine):
        if isinstance(n, Form) and not n.angle and n.items and isinstance(n.items[0], Form) and "M-LOOK" in repr(n.items[0].items): return n.items[1:]
    return None


def flag_setters(all_routine_forms: List[Form]) -> Dict[str, Dict[str, int]]:
    """for every global flag: how many times it is set true and set false in the whole game"""
    out: Dict[str, Dict[str, int]] = {}
    for f in all_routine_forms:
        for n in _walk(f):
            if isinstance(n, Form) and n.angle and n.head == "SETG" and len(n.items) >= 2 and isinstance(n.items[1], Atom):
                v = n.items[2] if len(n.items) > 2 else None; d = out.setdefault(n.items[1].name, {"true": 0, "false": 0, "other": 0})
                if isinstance(v, Atom) and v.name in ("T", ",T", "<T>") or (isinstance(v, Atom) and v.name == ",TRUE"): d["true"] += 1
                elif v is None or (isinstance(v, Form) and v.angle and not v.items) or (isinstance(v, Atom) and v.name in (",FALSE-FLAG", "0")): d["false"] += 1
                else: d["other"] += 1                                                              # a toggle or a computed value: not treated as irreversible
    return out


def versions(rooms: Dict[str, Room], rts: Dict[str, Form]) -> int:
    """fill room.versions for rooms whose text changes with an irreversible flag; returns how many rooms"""
    setters = flag_setters(list(rts.values())); count = 0
    for r in rooms.values():
        f = rts.get(r.action or "")
        if not f: continue
        body = _mlook_body(f)
        if not body: continue
        flags = []
        for n in _walk(Form(list(body))):
            if isinstance(n, Form) and not n.angle and n.items:
                fl = _flag(n.items[0])
                if fl and fl[0] not in flags: flags.append(fl[0])
        for flag in flags:
            st = setters.get(flag)
            if not st or st["true"] < 1 or st["false"] > 0 or st["other"] > 0: continue            # reversible, or never set true
            before = describe.clean(" ".join(_text(body, {flag: False}))); after = describe.clean(" ".join(_text(body, {flag: True})))
            if before and after and before != after:
                r.versions = [{"label": "before", "desc": before, "flag": flag}, {"label": "after", "desc": after, "flag": flag}]; count += 1; break
    return count


def teleports(rooms: Dict[str, Room], objs: Dict[str, GameObject], rts: Dict[str, Form], game: str = "") -> int:
    """fill room.teleports; returns how many teleports were found"""
    found: Dict[tuple, str] = {}
    def neighbours(a): return {e.dest for e in rooms[a].exits.values() if e.dest}
    def add(src, dst, via):
        if src in rooms and dst in rooms and src != dst and dst not in neighbours(src) and src not in neighbours(dst): found.setdefault((src, dst), via)
    def gotos(node):
        for n in _walk(node):
            if isinstance(n, Form) and n.angle and n.head == "GOTO" and len(n.items) > 1 and isinstance(n.items[1], Atom) and n.items[1].name.startswith(","): yield n.items[1].name[1:], n
    def conditional_sources(routine):
        for n in _walk(routine):                                                              # COND clause: test names ,HERE and a room; body has GOTO
            if isinstance(n, Form) and not n.angle and n.items and isinstance(n.items[0], Form):
                t = n.items[0]; atoms = [a.name[1:] for a in _walk(t) if isinstance(a, Atom) and a.name.startswith(",")]
                if "HERE" in atoms:
                    for room in atoms:
                        if room in rooms:
                            for dst, _ in gotos(Form(n.items[1:])): yield room, dst
    for o in objs.values():
        f = rts.get(o.action or "")
        if not f: continue
        cond = list(conditional_sources(f)); [add(a, b, "use the " + (o.desc or o.name.lower())) for a, b in cond]
        if cond: continue
        homes = {o.location} if o.location in rooms else {k for k, r in rooms.items() if o.name in r.globals}
        if 0 < len(homes) <= 2:
            for dst, _ in gotos(f):
                for h in homes: add(h, dst, "use the " + (o.desc or o.name.lower()))
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "teleports.json")
    if os.path.exists(path):
        for t in json.load(open(path)).get(game, []):
            found.setdefault((t["from"], t["to"]), t["via"])
            if t.get("both"): found.setdefault((t["to"], t["from"]), t["via"])
    for (a, b), via in found.items(): rooms[a].teleports.append({"dest": b, "via": via})
    return len(found)
