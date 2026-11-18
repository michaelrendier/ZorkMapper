# SPDX-License-Identifier: GPL-3.0-only
"""
zorkmapper.zmachine: read rooms and exits straight out of an Infocom Z-machine story file (no ZIL needed).  Versions 1-3 (and the object/property
layout of 4-5).  Spec: the Z-Machine Standards Document 1.1 (public).  What is read: the header, the dictionary, the object table and its property
tables.  What is NOT read: routines (so no long descriptions, and 'PER' exits are only marked).

How exits are found.  ZIL gives every direction a property number; in the story file the direction words in the DICTIONARY carry that number in their
data bytes (the parser looks it up there).  Exit property formats (from gverbs.zil in the released Infocom sources):
    size 1  UEXIT   byte 0 = destination room object
    size 2  NEXIT   word 0 = address of the refusal message
    size 3  FEXIT   word 0 = routine that decides
    size 4  CEXIT   byte 0 = destination, byte 1 = flag global, word 1 = message
    size 5  DEXIT   byte 0 = destination, byte 1 = door object, word 1 = message
"""
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .model import Room, Exit, GameObject

A0 = "abcdefghijklmnopqrstuvwxyz"; A1 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"; A2 = " \n0123456789.,!?_#'\"/\\-:()"
DIRECTION_WORDS = {"north": "NORTH", "south": "SOUTH", "east": "EAST", "west": "WEST", "ne": "NE", "nw": "NW", "se": "SE", "sw": "SW",
                   "northeast": "NE", "northwest": "NW", "southeast": "SE", "southwest": "SW", "up": "UP", "down": "DOWN", "in": "IN", "out": "OUT",
                   "land": "LAND", "u": "UP", "d": "DOWN", "n": "NORTH", "s": "SOUTH", "e": "EAST", "w": "WEST"}


class Story:
    def __init__(self, data: bytes):
        self.b = data; self.version = data[0]
        if self.version > 5: raise ValueError("Z-machine version %d is not supported (1-5)" % self.version)
        self.dict_addr = self.w(8); self.obj_addr = self.w(10); self.abbrev = self.w(0x18)

    def w(self, a): return (self.b[a] << 8) | self.b[a + 1]

    def zstring(self, a: int, limit: int = 400):
        """decode the Z-string at byte address a; returns (text, address of the next byte)"""
        zc = []
        while len(zc) < limit*3:
            word = self.w(a); a += 2
            zc += [(word >> 10) & 31, (word >> 5) & 31, word & 31]
            if word & 0x8000: break
        out, alpha, i = [], 0, 0
        while i < len(zc):
            c = zc[i]; i += 1
            if c == 0: out.append(" "); alpha = 0
            elif c in (1, 2, 3) and (self.version >= 3 or c != 1) and not (self.version < 3 and c in (2, 3)):
                if i < len(zc):
                    idx = 32*(c - 1) + zc[i]; i += 1; ab = self.w(self.abbrev + 2*idx)*2
                    out.append(self.zstring(ab)[0])
                alpha = 0
            elif c in (4, 5) and self.version >= 3: alpha = c - 3
            elif c == 1 and self.version == 1: out.append("\n")
            elif c in (2, 3, 4, 5): alpha = {2: 1, 3: 2, 4: 1, 5: 2}[c]
            else:
                if alpha == 2 and c == 6:
                    if i + 1 < len(zc): out.append(chr((zc[i] << 5) | zc[i + 1])); i += 2
                else: out.append((A0, A1, A2)[alpha][c - 6] if c >= 6 and (c - 6) < 26 else "")
                alpha = 0
        return "".join(out), a

    def dictionary(self) -> List[tuple]:
        a = self.dict_addr; n = self.b[a]; a += 1 + n; elen = self.b[a]; count = struct.unpack(">h", self.b[a + 1:a + 3])[0]; a += 3
        out = []
        for _ in range(abs(count)):
            text = self.zstring(a, 6)[0].strip(); out.append((text, list(self.b[a + (4 if self.version <= 3 else 6):a + elen]))); a += elen
        return out

    def direction_properties(self) -> Dict[int, str]:
        """property number -> direction name, from the dictionary (the data bytes of direction words)"""
        votes: Dict[str, Dict[int, int]] = {}
        for text, data in self.dictionary():
            name = DIRECTION_WORDS.get(text.lower())
            if name and name not in ("LAND",) or (name == "LAND" and text.lower() == "land"):
                for v in data[1:]:
                    if 1 <= v <= 63: votes.setdefault(name, {}); votes[name][v] = votes[name].get(v, 0) + 1
        return votes

    def objects(self):
        v3 = self.version <= 3; defaults = 31 if v3 else 63; esz = 9 if v3 else 14; base = self.obj_addr + 2*defaults
        first_props = self.w(base + (7 if v3 else 12)); n = (first_props - base)//esz; objs = {}
        for i in range(1, n + 1):
            a = base + (i - 1)*esz
            if v3: parent, sib, child, props = self.b[a + 4], self.b[a + 5], self.b[a + 6], self.w(a + 7)
            else: parent, sib, child, props = self.w(a + 6), self.w(a + 8), self.w(a + 10), self.w(a + 12)
            tl = self.b[props]; name = self.zstring(props + 1)[0] if tl else ""
            objs[i] = {"name": name, "parent": parent, "sibling": sib, "child": child, "props": self.properties(props + 1 + 2*tl)}
        return objs

    def properties(self, a: int) -> Dict[int, bytes]:
        out = {}
        while self.b[a]:
            s = self.b[a]; a += 1
            if self.version <= 3: num, ln = s & 31, (s >> 5) + 1
            else:
                num = s & 63
                if s & 0x80: ln = self.b[a] & 63 or 64; a += 1
                else: ln = 1 if not s & 0x40 else 2
            out[num] = bytes(self.b[a:a + ln]); a += ln
        return out


def start_room(st: "Story", room_objects) -> Optional[int]:
    """where the player starts: the first `store HERE, <room>` (long-form 2OP opcode 13 with two small constants: bytes 0D 10 xx) in the opening routine"""
    pc = st.w(6)
    for a in range(pc, pc + 600):
        if st.b[a] == 0x0D and st.b[a + 1] == 0x10 and st.b[a + 2] in room_objects: return st.b[a + 2]
    return None


def read_rooms(path: str):
    """(rooms, objs, info): Room dataclasses (name in .desc, exits, objects located in the room) like the ZIL reader gives, from the story file alone"""
    st = Story(open(path, "rb").read()); objs = st.objects(); votes = st.direction_properties()
    # a property number is a direction if the dictionary says so; the most voted property for each direction word
    dirprop: Dict[int, str] = {}
    for name, vs in votes.items():
        best = max(vs, key=lambda k: vs[k]); dirprop.setdefault(best, name)
    def exit_of(num: int, data: bytes) -> Optional[tuple]:
        d = dirprop[num]; ln = len(data)
        if ln == 1: return d, "to", data[0], None, None
        if ln == 2: return d, "blocked", None, None, st.zstring(st.w(0) and ((data[0] << 8) | data[1])*2)[0] if False else None
        if ln == 3: return d, "per", None, None, None
        if ln == 4: return d, "cond", data[0], "global %d" % data[1], None
        if ln == 5: return d, "cond", data[0], "door %s is open" % (objs.get(data[1], {}).get("name", "?")), None
        return None
    cand = {}
    for i, o in objs.items():
        ex = {}
        for num, data in o["props"].items():
            if num in dirprop and len(data) in (1, 2, 3, 4, 5):
                e = exit_of(num, data)
                if e and (e[2] is None or e[2] in objs): ex[num] = e
        if ex: cand[i] = ex
    from collections import Counter
    parent = Counter(objs[i]["parent"] for i in cand).most_common(1)[0][0]
    names = {}
    rooms: Dict[str, Room] = {}; gobjs: Dict[str, GameObject] = {}
    ids = {i: "R%d" % i for i, o in objs.items() if o["parent"] == parent and o["name"]}          # every child of the rooms object, with or without exits
    for i in ids:
        r = Room(name=ids[i], desc=objs[i]["name"], parent="ROOMS", source=path.split("/")[-1], line=i)
        for num, (d, kind, dest, cond, msg) in cand.get(i, {}).items():
            if dest is not None and dest not in ids and kind in ("to", "cond"): continue
            r.exits[d] = Exit(d, kind, dest=ids.get(dest) if dest else None, condition=cond, message=msg)
        c = objs[i]["child"]
        while c:
            gobjs["O%d" % c] = GameObject("O%d" % c, desc=objs[c]["name"], location=ids[i]); r.objects.append("O%d" % c); c = objs[c]["sibling"]
        rooms[ids[i]] = r
    info = {"start": start_room(st, set(ids)), "version": st.version, "objects": len(objs), "rooms": len(rooms), "rooms_parent": objs[parent]["name"], "direction_properties": {k: v for k, v in sorted(dirprop.items())}}
    return rooms, gobjs, info
