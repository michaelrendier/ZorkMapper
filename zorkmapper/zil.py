# SPDX-License-Identifier: GPL-3.0-only
"""
zorkmapper.zil: a reader for ZIL (the Zork Implementation Language) source.

ZIL is a LISP-like language: ``<FORM ...>`` is a call, ``(LIST ...)`` is a list, ``"text"`` a string, ``;`` comments out the next form.
This module only reads: it turns source text into nested Python values and yields the top-level ``<ROOM ...>`` and ``<OBJECT ...>``
forms.  It does not evaluate ZIL.  Reference: the Infocom sources released under the MIT licence (historicalsource/zork1, zork2, zork3).
"""
from dataclasses import dataclass
from typing import Iterator, List, Union


@dataclass(frozen=True)
class Atom:
    """a bare word such as ``NORTH`` or ``KITCHEN-WINDOW``"""
    name: str
    def __repr__(self): return self.name


@dataclass(frozen=True)
class Str:
    """a double-quoted string"""
    text: str
    def __repr__(self): return '"%s"' % self.text


@dataclass
class Form:
    """``<HEAD ...>`` (angle) or ``(HEAD ...)`` (paren, ``angle=False``)"""
    items: list
    angle: bool = True
    line: int = 0
    @property
    def head(self) -> str:
        return self.items[0].name if self.items and isinstance(self.items[0], Atom) else ""


Node = Union[Atom, Str, Form]
_DELIMS = set('<>()"; \t\r\n')


class Reader:
    """character-level reader; tracks line numbers so every room can point at its source line"""

    def __init__(self, text: str):
        self.s, self.i, self.line = text, 0, 1

    def _skip(self):
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == "\n": self.line += 1; self.i += 1
            elif c in " \t\r\f": self.i += 1
            elif c == ";":                                   # ZIL comment: the next form is ignored
                self.i += 1; self._skip(); self.read()
            else: break

    def read(self) -> Node | None:
        self._skip()
        if self.i >= len(self.s): return None
        c, start = self.s[self.i], self.line
        if c in "<(":
            close = ">" if c == "<" else ")"; self.i += 1; items = []
            while True:
                self._skip()
                if self.i >= len(self.s): break
                if self.s[self.i] == close: self.i += 1; break
                if self.s[self.i] in ">)": self.i += 1; break           # tolerate a mismatched closer
                node = self.read()
                if node is not None: items.append(node)
            return Form(items, c == "<", start)
        if c == '"':
            j = self.i + 1; buf = []
            while j < len(self.s) and self.s[j] != '"':
                if self.s[j] == "\\" and j + 1 < len(self.s): buf.append(self.s[j + 1]); j += 2; continue
                if self.s[j] == "\n": self.line += 1
                buf.append(self.s[j]); j += 1
            self.i = j + 1; return Str("".join(buf))
        j = self.i                                                          # an atom; handles %<...>, !\X and .LOCAL tokens as plain atoms
        if c == "%" and j + 1 < len(self.s) and self.s[j + 1] == "<": self.i += 1; return self.read()
        while j < len(self.s) and self.s[j] not in _DELIMS:
            if self.s[j] == "\\" and j + 1 < len(self.s): j += 2; continue
            j += 1
        if j == self.i: j += 1
        tok = self.s[self.i:j]; self.i = j; return Atom(tok)


def read_all(text: str) -> List[Node]:
    r = Reader(text); out = []
    while True:
        n = r.read()
        if n is None: break
        out.append(n)
    return out


def top_forms(text: str, heads=("ROOM", "OBJECT")) -> Iterator[Form]:
    """every top-level ``<ROOM ...>`` / ``<OBJECT ...>`` form (ZIL files nest nothing else that matters for the map)"""
    for n in read_all(text):
        if isinstance(n, Form) and n.angle and n.head in heads: yield n
