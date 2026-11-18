"""Teleports and before/after versions, found from ZIL routines (a small invented game)."""
from zorkmapper.model import parse_game
from zorkmapper import describe, events

GAME = '''
<ROOM HALL (IN ROOMS) (DESC "Hall") (NORTH TO CELL) (ACTION HALL-F)>
<ROOM CELL (IN ROOMS) (DESC "Cell") (SOUTH TO HALL)>
<ROOM TOWER (IN ROOMS) (DESC "Tower") (ACTION TOWER-F)>
<ROOM POOL (IN ROOMS) (DESC "Pool") (ACTION POOL-F)>
<OBJECT MIRROR (IN HALL) (DESC "magic mirror") (ACTION MIRROR-F)>
<ROUTINE MIRROR-F () <COND (<VERB? RUB> <GOTO ,TOWER>)>>
<ROUTINE HALL-F (RARG) <COND (<EQUAL? .RARG ,M-LOOK> <TELL "A hall." CR> <COND (,QUAKE-FLAG <TELL " The roof has fallen in." CR>) (T <TELL " The roof is sound." CR>)>)>>
<ROUTINE POOL-F (RARG) <COND (<EQUAL? .RARG ,M-LOOK> <COND (,TIDE <TELL "The pool is full." CR>) (T <TELL "The pool is empty." CR>)>)>>
<ROUTINE TOWER-F (RARG) <COND (<EQUAL? .RARG ,M-LOOK> <TELL "A tower." CR>)>>
<ROUTINE QUAKE () <SETG QUAKE-FLAG T>>
<ROUTINE TIDE-IN () <SETG TIDE T>>
<ROUTINE TIDE-OUT () <SETG TIDE <>>>
'''


def build():
    rooms, objs = parse_game(GAME); rts = describe.routines(GAME); describe.fill(rooms, rts); return rooms, objs, rts


def test_irreversible_flag_gives_a_before_and_after_version_but_a_reversible_one_does_not():
    rooms, objs, rts = build()
    assert events.versions(rooms, rts) == 1
    v = rooms["HALL"].versions
    assert v[0]["label"] == "before" and "sound" in v[0]["desc"] and v[1]["label"] == "after" and "fallen" in v[1]["desc"] and v[0]["flag"] == "QUAKE-FLAG"
    assert rooms["POOL"].versions == []                       # TIDE is set both ways: not an event


def test_teleport_from_an_objects_goto():
    rooms, objs, rts = build(); n = events.teleports(rooms, objs, rts, "")
    assert n == 1 and rooms["HALL"].teleports[0]["dest"] == "TOWER" and "mirror" in rooms["HALL"].teleports[0]["via"]


def test_a_destination_that_is_already_an_exit_is_not_a_teleport():
    g = GAME.replace('(NORTH TO CELL)', '(NORTH TO TOWER)')
    rooms, objs = parse_game(g); rts = describe.routines(g)
    assert events.teleports(rooms, objs, rts, "") == 0


def test_the_real_zork1_mirror_and_rainbow():
    import os, glob
    src = os.path.join(os.path.dirname(__file__), "..", "sources", "zork1")
    if not os.path.isdir(src): return
    rooms, objs, rts = {}, {}, {}
    for f in glob.glob(os.path.join(src, "*.zil")):
        t = open(f, errors="replace").read(); r, o = parse_game(t, f); rooms.update(r); objs.update(o); rts.update(describe.routines(t))
    describe.fill(rooms, rts); events.versions(rooms, rts); events.teleports(rooms, objs, rts, "zork1")
    assert any(t["dest"] == "MIRROR-ROOM-2" for t in rooms["MIRROR-ROOM-1"].teleports)
    assert any(t["dest"] == "END-OF-RAINBOW" for t in rooms["ARAGAIN-FALLS"].teleports)
    assert rooms["MIRROR-ROOM-1"].versions and rooms["MIRROR-ROOM-1"].versions[0]["flag"] == "MIRROR-MUNG"
