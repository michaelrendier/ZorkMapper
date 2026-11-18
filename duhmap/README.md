# duhmap: the console map explorer, derived from Duh DRAW

`duhmap` is a modification of **Duh DRAW** (Ben Fowler 1996; Pekka Enberg 2002-03), the Linux open-source clone of TheDraw. The editing core is replaced by a map explorer for the maps ZorkMapper writes; the program shape (init, event loop, a key reader that treats ESC+letter as Alt-letter, the bottom status line and function-key strip, the directory dialog) is Duh DRAW's, now drawn through ncursesw.

**Licence.** Duh DRAW is GNU GPL version 2; `LICENSE` is its licence text, and the original `CREDITS.duhdraw`, `HISTORY.duhdraw` and `README.duhdraw` are kept. This directory as a whole is therefore **GPL v2** (not v3). The rest of ZorkMapper (Python) is GPL v3 and is a separate program; the two only exchange files (`.zmap`).

**Install:** `make && sudo make install` puts it in `/usr/bin/zork-map` (`sudo make uninstall` removes it); run `zork-map` from anywhere. It reads **`~/.zorkmapper/config`** at run time (maps folder, the mapper's home, panel percentages; `ZORKMAPPER_DIR` moves the root) and opens maps from `~/.zorkmapper/maps/`. **Build only:** `make` (gcc, libncursesw). **Run:** `./duhmap ../ASCIIArt/zork1.zmap` (UTF-8, 256 colours, about 100 x 30 or larger). With no argument it lists `*.zmap` in the maps folder (`ZORKMAP_DIR` overrides it). `./duhmap --check FILE` parses a map and prints a summary.

**Keys.** Arrows: N, S, W, E. **Shift-Up UPW, Shift-Down UPE, Shift-Left DW, Shift-Right DE** (up and down are drawn as diagonals; the side chooses which diagonal when a room has two). `y u b n`: NW NE SW SE. Tab / Shift-Tab: next / previous room. Home / End: start / last room. PgUp / PgDn: a level up / down (the nearest room on that level). F2 / F3 / F4: legend, sidebar, status. ESC: the menu bar (Files, Go, View, Levels, Help), after TheDraw. Alt-O open, Alt-M map a game (runs `python3 -m zorkmapper --map PATH` in `$ZORKMAPPER_HOME`), Alt-G go to a number, Alt-H help, Alt-X quit. With no exit in a direction the cursor moves to the nearest room that way on the sheet and says so.

**Screen.** Percentages of the terminal (legend 16%, sidebar 30%, status 22%); the map keeps its scale (two columns per square) and the current room is always at the centre. The legend shows elevation: white = ground level (the start room), bright rainbow going up, dark rainbow going down.

**Not here yet:** editing (palette, drawing), the elevation-layer-only view, the QGraphicsScene / PyQt6 / OpenGL versions.
