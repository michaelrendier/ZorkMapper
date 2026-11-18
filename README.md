# ZorkMapper

Reads the **ZIL** source of Infocom games, builds each room as a dataclass, and draws the map: a 3-D grid of cubes (one per room) flattened onto graph paper, with an interactive PyQt6 viewer planned. GNU GPL v3 (code). The Infocom sources are fetched separately (`./fetch_sources.sh`) and are MIT-licensed (Microsoft, 2025).

## What exists (2026-11-17)
- `zorkmapper/zil.py`: a ZIL reader (forms, lists, strings, `;` comments, line numbers).
- `zorkmapper/model.py`: `Room`, `Exit`, `GameObject` dataclasses; exit kinds: **to** (always), **cond** (`TO x IF flag [IS OPEN] [ELSE "msg"]`), **per** (a routine decides), **blocked** (a refusal message). `(IN ROOMS)` (the parent) is told from `(IN TO KITCHEN ...)` (an exit).
- `zorkmapper/layout.py`: places rooms on a 3-D integer grid by walking the exits (N, S, E, W, the four diagonals, UP, DOWN); IN / OUT / LAND are portals (lines, no placement). A taken cell sends the room to the nearest free one (recorded).
- `zorkmapper/svgmap.py` and `python -m zorkmapper sources/zork1 --svg zork1_map.svg`: numbered squares, straight lines, an arrow in the middle of a one-way line, dashed conditional exits, a legend of room names.

## Flat view
Each level is offset half a cell right and up (up is diagonal up, down is diagonal down); in 3-D the same grid is one cube per room.

## Next
The PyQt6 viewer: `QGraphicsScene` for the flat sheet, an OpenGL view for the cubes, a collapsible right panel and bottom status box, a left adventure-toolkit palette for drawing maps by hand. See the project notes.
