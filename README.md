# ZorkMapper

Reads the **ZIL** source of Infocom games, builds each room as a dataclass, and draws the map: a 3-D grid of cubes (one per room) flattened onto graph paper, with an interactive PyQt6 viewer planned. GNU GPL v3 (code). The Infocom sources are fetched separately (`./fetch_sources.sh`) and are MIT-licensed (Microsoft, 2025).

## What exists (2026-11-17)
- `zorkmapper/zil.py`: a ZIL reader (forms, lists, strings, `;` comments, line numbers).
- `zorkmapper/model.py`: `Room`, `Exit`, `GameObject` dataclasses; exit kinds: **to** (always), **cond** (`TO x IF flag [IS OPEN] [ELSE "msg"]`), **per** (a routine decides), **blocked** (a refusal message). `(IN ROOMS)` (the parent) is told from `(IN TO KITCHEN ...)` (an exit).
- `zorkmapper/layout.py`: places rooms on a 3-D integer grid by walking the exits (N, S, E, W, the four diagonals, UP, DOWN); IN / OUT / LAND are portals (lines, no placement). A taken cell sends the room to the nearest free one (recorded).
- `zorkmapper/svgmap.py` and `python -m zorkmapper sources/zork1 --svg zork1_map.svg`: numbered squares, straight lines, an arrow in the middle of a one-way line, dashed conditional exits, a legend of room names.

## Maps (the graph-paper lattice, `--sheet`)
`images/zork1_sheet.svg`, `zork2_sheet.svg`, `zork3_sheet.svg` (and PNG renders): one sheet of graph paper, a room per square numbered with a legend of names; each room owns a 3 x 3 block (its eight neighbours are pathway squares, so rooms sit on a sub-grid lattice, one path square apart); N/S/E/W through the whole next square, diagonals corner to corner, U and D drawn as diagonals; long runs skip lattice spots; links that cannot be drawn straight are dotted `to N` connectors; mazes and the puzzle are left out and point into blank space. Room names with descriptions (from the ZIL): `descriptions/zork1_rooms.txt`, `zork2_rooms.txt`, `zork3_rooms.txt`.
Regenerate: `./fetch_sources.sh; python3 -m zorkmapper sources/zork1 --sheet --svg images/zork1_sheet.svg --descriptions descriptions/zork1_rooms.txt`.

## Flat view (the earlier 3-D flattening)
Each level is offset half a cell right and up (up is diagonal up, down is diagonal down); in 3-D the same grid is one cube per room.

## The console explorer (rough draft of the viewer)
`python3 -m zorkmapper.explorer [ASCIIArt/zork1.map.json]` (UTF-8, 256 colours, about 100 x 30 or larger). Opens a picker over `ASCIIArt/*.map.json`. The current room is always at the centre of the map viewport; panel sizes are percentages of the screen (map scale stays two characters per square; a bigger terminal adds viewport). Left: elevation legend (white = ground / start level, bright rainbow going up, dark rainbow going down). Right: room list and the current room's description, items and exits. Bottom: status box and a TheDraw-style function-key strip. Arrows go N/S/E/W along the exits, `y u b n` the diagonals, PgUp/PgDn up/down, Tab/Shift-Tab next/previous room, F2/F3/F4 collapse the panels, F5 open, **F6 map a game**, F10 quit.

## Mapping a game
`python3 -m zorkmapper --map PATH` (or F6 in the explorer): PATH is a Z-machine story file (`.dat`, `.z3`, `.z5`; versions 1-5) or a folder of ZIL source. It writes `NAME.map.json`, `NAME.txt`, `NAME.ans` and `NAME.svg` into `ASCIIArt/`. The story-file reader (`zorkmapper/zmachine.py`) finds directions from the game's dictionary and exits from the object property tables; on Zork I it reproduces all 110 rooms with names and exits identical to the ZIL source (a test). Not read from a story file: long descriptions and the destinations of routine-decided exits (those are in routines).

## Next
The order (author): console (rough draft, now) -> `QGraphicsScene` rendering the SVG directly -> PyQt6 -> OpenGL 3-D explorer. The PyQt6 viewer: `QGraphicsScene` for the flat sheet, an OpenGL view for the cubes, a collapsible right panel and bottom status box, a left adventure-toolkit palette for drawing maps by hand. See the project notes.
