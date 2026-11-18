# TheDraw 4.63 as the interface model for the curses explorer

Source: the TheDraw 4.63 disk image the author supplied (`SpaceClaude/downloads/The Draw 4.63 (3.5).7z`, a WinWorld archive; `thedraw.exe`, `THEDRAW.DOC`, demo, fonts, helper source for `UNCRUNCH` only). The program's own source is not public. What follows is the interface as the 356 KB manual describes it (names and structure only), 2026-11-18.

## Three layers of command
1. **Command mode** on a full-screen edit canvas, with Alt-letter / Ctrl-letter shortcuts (37 commands: Alt-L load, Alt-V view, Alt-S save, Alt-O change directory, Alt-X quit, Alt-B block, Alt-P paint/fill, Alt-A colours, Alt-F character sets, Alt-H help, Alt-M draw mode, Alt-J animation, Alt-R undo ...). Ctrl-arrows step the foreground / background colour. The bottom line shows the cursor position, a colour sample, mode and set numbers, and the ten characters of the current set on F1-F10.
2. **The pull-down menu bar.** ESC (or the right mouse button) shows a bar across the top:
   `Files  Global  Options  Screen  foNts  Animation  Color  Toggles  Help`
   One letter of each heading is its hotkey (capitalised; `foNts` is N). Left/Right move along the bar; each opens a boxed menu with **the shortcut printed at the right of every item** (`Load  Alt-L`), so the menus teach the keys. Some items are two-key sequences (`Alt-G,C` = Global, Copy).
   - Files: Load, View, Delete, Change Dir, Save, Quit.   Global: Copy, Move, Fill, Text, rePlace.   Options: Character Set, Tab Setup, Paint/Fill, Setup Options.   Screen: Clear Page, Select Page, Insert/Delete Line, Insert/Delete Column, Restore/Undo.   Fonts: a list of lettered fonts.   Animation: rescan, pause ...   Color: Fore/Back, Default, Under Cursor, Shading.   Toggles: Draw Mode, Color Draw, Sprite, Animation, Pick Character, Insert, Full Screen.
3. **Pop-ups and pick lists.** Each command that needs input opens a small dialog; file commands show a **pick list** (a selector bar over a directory listing; type a name or a DOS wildcard mask, or press **TAB** to bring up the list; Enter chooses; Esc leaves).

## Mapping to the explorer (proposal, to be agreed before building)
- Command mode = the map explorer; the bottom line = status and F-key strip (built).
- ESC opens the bar: `Files  Go  View  Levels  Map  Help`.
  - Files: Open map (Alt-O), Map a game (Alt-M), Save map, Quit (Alt-X).
  - Go: Start (Home), Next room (Tab), Previous (Shift-Tab), Room number..., Find room by name (pick list, TAB).
  - View: Legend (F2), Sidebar (F3), Status (F4), Centre on room, Descriptions.
  - Levels: Highlight a level, Show only a level, Legend of elevations.
  - Map: Re-lay-out, Pin a room, Leave out (maze), Export SVG / text (later, with the editing palette).
  - Help: Keys, About.
- Shortcuts printed at the right of every menu item. File pick lists over `ASCIIArt/` with wildcard masks and TAB, as TheDraw's file dialogs.
