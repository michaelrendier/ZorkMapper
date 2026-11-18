# SPDX-License-Identifier: GPL-3.0-only
"""zorkmapper.levels: elevation colours.  White is ground level (the start room's level).  Going UP: bright colours in rainbow order
(red, orange, yellow, green, blue, violet).  Going DOWN (underground): dark colours in the same rainbow order.  ANSI 256-colour codes."""
UP = [196, 208, 226, 46, 33, 129]          # bright: red, orange, yellow, green, blue, violet   (level +1 .. +6)
DOWN = [88, 130, 100, 22, 18, 54]          # dark:   red, orange, yellow, green, blue, violet   (level -1 .. -6)
GROUND, UNKNOWN = 231, 240
NAMES_UP = ["red", "orange", "yellow", "green", "blue", "violet"]


def bg(z):
    if z is None: return UNKNOWN
    if z == 0: return GROUND
    return UP[(z - 1) % len(UP)] if z > 0 else DOWN[(-z - 1) % len(DOWN)]


def fg(code):
    """black on the bright colours and white, bold, on the dark ones"""
    return "30" if code in (GROUND, 196, 208, 226, 46, 33) else "97;1"


def black_text(code):
    return code in (GROUND, 196, 208, 226, 46, 33)


def label(z):
    if z is None: return "unknown"
    if z == 0: return "ground level (start)"
    return ("up %d: %s" % (z, NAMES_UP[(z - 1) % 6])) if z > 0 else ("down %d: dark %s" % (-z, NAMES_UP[(-z - 1) % 6]))
