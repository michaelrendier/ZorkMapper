/*****************************************************************************
*  duhmap: the ZorkMapper console map explorer, derived from Duh DRAW.
*
*  Duh DRAW for Linux  (c) Copyleft February 1996  Ben Fowler
*  Copyright (c) 2002-2003 Pekka Enberg
*  Duh DRAW is free software, GNU General Public License version 2 (see LICENSE).
*  Modified 2026 by Cody Michael Allison (Michael Rendier): the editing core is replaced by a map
*  explorer; kept from Duh DRAW: the program shape (init, edit loop, key reader that treats ESC+letter
*  as Alt-letter, bottom status line and function-key strip, directory dialog); the screen is now drawn
*  through ncursesw, not raw escape strings.  This derived work is therefore GPL v2, as a whole.
*
*  Reads NAME.zmap files written by ZorkMapper (python3 -m zorkmapper ... --ascii ASCIIArt/NAME).
*  Keys:  arrows = N S W E     Shift-Up UPW   Shift-Down UPE   Shift-Left DW   Shift-Right DE
*         y u b n = NW NE SW SE  Tab / Shift-Tab next / previous room  Home start  End last room
*         PgUp / PgDn = level up / down   F2 legend  F3 sidebar  F4 status  ESC menu bar
*         Alt-O open  Alt-M map a game  Alt-G go to number  Alt-H help  Alt-X quit
*  Screen sizes are percentages of the terminal; the map keeps its scale (two columns per square).
*****************************************************************************/
#define _GNU_SOURCE
#define _XOPEN_SOURCE_EXTENDED 1
#include <ncursesw/curses.h>
#include <locale.h>
#include <wchar.h>
#include <wctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <unistd.h>
#include <stdarg.h>
#include <sys/ioctl.h>

#define ALT 1000                    /* Alt-letter codes: ncurses key codes occupy 257..511, so Duh DRAW's 256+letter would collide */
#define MAXR 400
#define MAXX 24
#define MAXL 16

typedef struct { char dir[8], kind[8]; int dest; char text[200]; } Exit;
typedef struct { int dest; char name[100], via[200]; } Tele;
typedef struct { int num, row, col, level, has_level, bg; char name[100]; char *desc; char items[600]; Exit ex[MAXX]; int nex; Tele tele[4]; int ntele; char alt_flag[48]; char *alt_before, *alt_after; } Room;
typedef struct { int z, bg, rooms; char label[80]; } Level;

static wchar_t **canvas; static int crows, ccols;
static Room rooms[MAXR + 1]; static int nrooms, start_room = 1, cur = 1;
static Level levels[MAXL]; static int nlev; static unsigned char ver[MAXR + 1];   /* ver[room] = 1 shows the room after its irreversible event */
static int PCT_LEFT = 16, PCT_RIGHT = 30, PCT_BOTTOM = 22;                  /* panel sizes, percent of the terminal (config: panel_left / panel_right / panel_bottom) */
static char mapper_home[512] = "..", conf_root[512];
static char title[200], game[100], mapdir[512] = "ASCIIArt", mappath[600], status[400] = "F5 / Alt-O opens a map.";
static int show_left = 1, show_right = 1, show_bottom = 1, show_help = 0, layer_view = 0;     /* layer_view: only the current elevation layer in colour */

/* ------------------------------------------------------------------ map file */
static void free_map(void)
{
  int i;
  if (canvas) { for (i = 0; i < crows; i++) free(canvas[i]); free(canvas); canvas = NULL; }
  for (i = 1; i <= nrooms; i++) { free(rooms[i].desc); rooms[i].desc = NULL; free(rooms[i].alt_before); free(rooms[i].alt_after); rooms[i].alt_before = rooms[i].alt_after = NULL; ver[i] = 0; }
  nrooms = nlev = 0;
}

static int load_map(const char *path)
{
  FILE *f = fopen(path, "r"); char *line = NULL; size_t cap = 0; ssize_t n; int i, r = 0;
  if (!f) return -1;
  free_map();
  if (getline(&line, &cap, f) < 0 || strncmp(line, "ZMAP 1", 6)) { fclose(f); free(line); return -2; }
  while ((n = getline(&line, &cap, f)) > 0) {
    if (line[n - 1] == '\n') line[--n] = 0;
    if (!strncmp(line, "title\t", 6)) snprintf(title, sizeof title, "%s", line + 6);
    else if (!strncmp(line, "game\t", 5)) snprintf(game, sizeof game, "%s", line + 5);
    else if (!strncmp(line, "start\t", 6)) start_room = atoi(line + 6);
    else if (!strncmp(line, "canvas\t", 7)) {
      sscanf(line + 7, "%d\t%d", &crows, &ccols); canvas = calloc(crows, sizeof(wchar_t *));
      for (i = 0; i < crows; i++) {
        n = getline(&line, &cap, f); if (n > 0 && line[n - 1] == '\n') line[--n] = 0;
        canvas[i] = calloc(ccols + 8, sizeof(wchar_t)); mbstowcs(canvas[i], line, ccols + 6);
      }
    } else if (!strncmp(line, "room\t", 5)) {
      char lv[16]; Room *rm; int num;
      sscanf(line + 5, "%d\t%*d\t%*d\t%15s", &num, lv); if (num < 1 || num > MAXR) continue;
      rm = &rooms[num]; memset(rm, 0, sizeof *rm); rm->num = num;
      sscanf(line + 5, "%*d\t%d\t%d\t%*s\t%d", &rm->row, &rm->col, &rm->bg);
      rm->has_level = strcmp(lv, "N") != 0; rm->level = rm->has_level ? atoi(lv) : 0; if (num > nrooms) nrooms = num; r = num;
    } else if (r && !strncmp(line, "name\t", 5)) snprintf(rooms[r].name, sizeof rooms[r].name, "%s", line + 5);
    else if (r && !strncmp(line, "desc\t", 5)) rooms[r].desc = strdup(line + 5);
    else if (r && !strncmp(line, "items\t", 6)) snprintf(rooms[r].items, sizeof rooms[r].items, "%s", line + 6);
    else if (r && !strncmp(line, "alt\t", 4)) {                                 /* before / after an irreversible event: flag, text before, text after */
      char *p = line + 4, *t1 = strchr(p, '\t'), *t2; if (!t1) continue; *t1 = 0; t2 = strchr(t1 + 1, '\t'); if (!t2) continue; *t2 = 0;
      snprintf(rooms[r].alt_flag, sizeof rooms[r].alt_flag, "%s", p); rooms[r].alt_before = strdup(t1 + 1); rooms[r].alt_after = strdup(t2 + 1);
    } else if (r && !strncmp(line, "tele\t", 5) && rooms[r].ntele < 4) {          /* a teleport: destination number, its name, how */
      Tele *tl = &rooms[r].tele[rooms[r].ntele]; char *p = line + 5, *t1 = strchr(p, '\t'), *t2; if (!t1) continue; *t1 = 0; t2 = strchr(t1 + 1, '\t'); if (!t2) continue; *t2 = 0;
      tl->dest = atoi(p); snprintf(tl->name, sizeof tl->name, "%s", t1 + 1); snprintf(tl->via, sizeof tl->via, "%s", t2 + 1); rooms[r].ntele++;
    }
    else if (r && !strncmp(line, "exit\t", 5) && rooms[r].nex < MAXX) {
      Exit *e = &rooms[r].ex[rooms[r].nex++]; char *p = line + 5, *t;
      t = strchr(p, '\t'); if (!t) continue; *t = 0; snprintf(e->dir, sizeof e->dir, "%s", p); p = t + 1;
      t = strchr(p, '\t'); if (!t) continue; *t = 0; snprintf(e->kind, sizeof e->kind, "%s", p); p = t + 1;
      t = strchr(p, '\t'); if (!t) continue; *t = 0; e->dest = atoi(p); snprintf(e->text, sizeof e->text, "%s", t + 1);
    } else if (!strncmp(line, "endroom", 7)) r = 0;
    else if (!strncmp(line, "level\t", 6) && nlev < MAXL) {
      Level *l = &levels[nlev++]; sscanf(line + 6, "%d\t%d\t%d\t%79[^\n]", &l->z, &l->bg, &l->rooms, l->label);
    }
  }
  free(line); fclose(f); snprintf(mappath, sizeof mappath, "%s", path);
  cur = start_room; return nrooms ? 0 : -3;
}

/* ------------------------------------------------------------------ ~/.zorkmapper (shared by every version) */
static void expand(char *dst, size_t n, const char *v)       /* '~/.zorkmapper/x' -> ROOT/x ; '~/x' -> $HOME/x */
{
  const char *h = getenv("HOME");
  if (!strncmp(v, "~/.zorkmapper/", 14)) snprintf(dst, n, "%s/%s", conf_root, v + 14);
  else if (!strncmp(v, "~/", 2) && h) snprintf(dst, n, "%s/%s", h, v + 2); else snprintf(dst, n, "%s", v);
}
static void load_config(void)
{
  const char *e = getenv("ZORKMAPPER_DIR"), *h = getenv("HOME"); char path[600], line[600]; FILE *f;
  if (e && *e) snprintf(conf_root, sizeof conf_root, "%s", e); else snprintf(conf_root, sizeof conf_root, "%s/.zorkmapper", h ? h : ".");
  snprintf(mapdir, sizeof mapdir, "%s/maps", conf_root);                     /* defaults, used when there is no config file */
  snprintf(path, sizeof path, "%s/config", conf_root);
  if (!(f = fopen(path, "r"))) return;
  while (fgets(line, sizeof line, f)) {
    char *c = strchr(line, '#'), *eq, *k, *v; if (c) *c = 0; eq = strchr(line, '='); if (!eq) continue; *eq = 0; k = line; v = eq + 1;
    while (*k == ' ' || *k == '\t') k++; { char *t = k + strlen(k); while (t > k && (t[-1] == ' ' || t[-1] == '\t')) *--t = 0; }
    while (*v == ' ' || *v == '\t') v++; { char *t = v + strlen(v); while (t > v && (t[-1] == ' ' || t[-1] == '\t' || t[-1] == '\n')) *--t = 0; }
    if (!strcmp(k, "maps_dir")) expand(mapdir, sizeof mapdir, v);
    else if (!strcmp(k, "mapper_home")) expand(mapper_home, sizeof mapper_home, v);
    else if (!strcmp(k, "panel_left")) PCT_LEFT = atoi(v); else if (!strcmp(k, "panel_right")) PCT_RIGHT = atoi(v); else if (!strcmp(k, "panel_bottom")) PCT_BOTTOM = atoi(v);
  }
  fclose(f);
}

/* ------------------------------------------------------------------ colours and boxes
   Every surface has an explicit background, so the screen reads the same on a light or a dark terminal theme.
   The rule: black text on light backgrounds, white (or a bright accent) text on dark backgrounds, never light on light or dark on dark. */
enum { P_TEXT = 1, P_DIM, P_BORDER, P_HEAD, P_STRIP, P_MENU, P_MENUSEL, P_BANNER, P_BRACKET, P_YEL, P_CYAN, P_GRN, P_MAP, P_BLACKBOX, P_TELE, P_LEVEL0 = 30 };
static void init_colors(void)
{
  init_pair(P_TEXT, 15, 234);      /* white on near-black */
  init_pair(P_DIM, 250, 234);      /* light grey on near-black */
  init_pair(P_BORDER, 81, 234);    /* light blue box lines on near-black */
  init_pair(P_HEAD, 15, 18);       /* white on dark blue */
  init_pair(P_STRIP, 16, 51);      /* black on bright cyan */
  init_pair(P_MENU, 16, 252);      /* black on light grey (menus and dialogs) */
  init_pair(P_MENUSEL, 15, 21);    /* white on blue (the selected menu item) */
  init_pair(P_BANNER, 15, 124);    /* white on dark red */
  init_pair(P_BRACKET, 196, 234);  /* bright red brackets on near-black */
  init_pair(P_YEL, 226, 234); init_pair(P_CYAN, 51, 234); init_pair(P_GRN, 46, 234);
  init_pair(P_MAP, 250, 233);      /* the map's passages: light grey on black */
  init_pair(P_BLACKBOX, 16, 252);  /* the lines of a dialog or menu: black on light grey */
  init_pair(P_TELE, 16, 196);      /* the teleport notice: black on bright red */
}
static int bright_bg(int c) { return c == 231 || c == 196 || c == 208 || c == 226 || c == 46 || c == 33; }
static short pair_for(int bg)                                /* an elevation colour: black text on the bright ones, white on the dark ones, the whole square */
{
  static int seen[64]; static int n = 0; int i;
  for (i = 0; i < n; i++) if (seen[i] == bg) return (short)(P_LEVEL0 + i);
  if (n >= 60) return P_TEXT;
  seen[n] = bg; init_pair(P_LEVEL0 + n, bright_bg(bg) ? 16 : 15, bg); return (short)(P_LEVEL0 + n++);
}
static void put(int y, int x, const char *s, int attr)
{
  int h, w; getmaxyx(stdscr, h, w); if (y < 0 || y >= h || x >= w) return; if (x < 0) { s += -x < (int)strlen(s) ? -x : (int)strlen(s); x = 0; }
  attron(attr); mvaddnstr(y, x, s, w - x - (y == h - 1)); attroff(attr);
}
static void putf(int y, int x, int attr, const char *fmt, ...)
{
  char b[512]; va_list a; va_start(a, fmt); vsnprintf(b, sizeof b, fmt, a); va_end(a); put(y, x, b, attr);
}
static void fill(int y, int x, int h, int w, int pair)
{
  int r; char line[400]; if (w <= 0) return; if (w > 399) w = 399; memset(line, ' ', w); line[w] = 0;
  for (r = 0; r < h; r++) put(y + r, x, line, COLOR_PAIR(pair));
}
static void draw_box(int y, int x, int h, int w, const char *title, int pair, int body)       /* a window outline; the inside is filled with `body` */
{
  int i; if (h < 2 || w < 4) return; fill(y, x, h, w, body);
  attron(COLOR_PAIR(pair) | A_BOLD);
  mvaddstr(y, x, "┌"); mvaddstr(y, x + w - 1, "┐"); mvaddstr(y + h - 1, x, "└"); mvaddstr(y + h - 1, x + w - 1, "┘");
  for (i = 1; i < w - 1; i++) { mvaddstr(y, x + i, "─"); mvaddstr(y + h - 1, x + i, "─"); }
  for (i = 1; i < h - 1; i++) { mvaddstr(y + i, x, "│"); mvaddstr(y + i, x + w - 1, "│"); }
  attroff(COLOR_PAIR(pair) | A_BOLD);
  if (title && title[0]) putf(y, x + 2, pair == P_BLACKBOX ? COLOR_PAIR(P_BLACKBOX) | A_BOLD : COLOR_PAIR(P_YEL) | A_BOLD, " %.*s ", w - 6 > 0 ? w - 6 : 0, title);
}

/* ------------------------------------------------------------------ navigation */
/* Navigation follows the DRAWN map, cell by cell, exactly as the eye does: from the room's square, step in the pressed direction along the passage
   glyphs (== || // \\); a room at the end is the destination; a superscript label (²³) at the end names the destination; a one-way arrow pointing
   against you, a blank square, a wrong kind of glyph, or a maze word ends it: INVALID.  Nothing is guessed from the game's exit table. */
static int sup_digit(wchar_t c)
{
  switch (c) { case 0x2070: return 0; case 0xB9: return 1; case 0xB2: return 2; case 0xB3: return 3;
    case 0x2074: return 4; case 0x2075: return 5; case 0x2076: return 6; case 0x2077: return 7; case 0x2078: return 8; case 0x2079: return 9; }
  return -1;
}
static void cellch(int cx, int cy, wchar_t *a, wchar_t *b)
{
  int r = 2 * cy, c = 4 * cx; *a = *b = L' ';
  if (cx < 0 || cy < 0 || r >= crows || c + 1 >= ccols) return;
  *a = canvas[r][c]; *b = canvas[r][c + 1];
}
static int room_at(int cx, int cy)
{
  int k; for (k = 1; k <= nrooms; k++) if (rooms[k].name[0] && rooms[k].row == 2 * cy && rooms[k].col == 4 * cx) return k;
  return 0;
}
static int is_pass(wchar_t a, wchar_t b, int dx, int dy)       /* does this two-character square carry a passage running the pressed way? */
{
  if (a == L'X' || b == L'X' || (a == L'+' && b == L'+')) return 1;                      /* crossings, also one carrying a U / D marker (UX) */
  if (dy == 0) return a == L'=' || b == L'=';                                            /* == => <= */
  if (dx == 0) return a == L'|' || a == L'^' || a == L'v';                               /* || ^^ vv */
  if (dx * dy < 0) return b == L'/';                                                     /* // U/ D/ and the arrows with a slash */
  return b == L'\\';                                                                     /* \\ U\ D\ */
}
static int arrow_allows(wchar_t a, wchar_t b, int dx, int dy)     /* a one-way arrow may only be walked the way it points */
{
  (void)b;
  if (a == L'=' && b == L'>') return dx == 1;      if (a == L'<' && b == L'=') return dx == -1;
  if (a == L'^') return dy == -1;                  if (a == L'v') return dy == 1;
  if (a == 0x2197) return dx == 1 && dy == -1;     if (a == 0x2199) return dx == -1 && dy == 1;
  if (a == 0x2196) return dx == -1 && dy == -1;    if (a == 0x2198) return dx == 1 && dy == 1;
  return 1;
}
static int go_geo(int dx, int dy, char vertical)     /* vertical: 0 for a compass key, 'U' or 'D' for the shifted keys; returns a room, 0 (invalid) or -2 (a maze) */
{
  Room *r = &rooms[cur]; int cx = r->col / 4, cy = r->row / 2, j, dest = 0, marker = 0, i, first_marker = 0;
  for (j = 1; j < 80; j++) {
    int x = cx + j * dx, y = cy + j * dy, rm, n, any; wchar_t a, b; cellch(x, y, &a, &b);
    if ((rm = room_at(x, y))) { dest = rm; break; }
    if (j > 1 && (sup_digit(a) >= 0 || sup_digit(b) >= 0)) {                              /* a link label: "to room N" */
      n = 0; any = 0; if (sup_digit(a) >= 0) { n = sup_digit(a); any = 1; } if (sup_digit(b) >= 0) { n = n * 10 + sup_digit(b); any = 1; }
      if (any && n >= 1 && n <= nrooms) { dest = n; break; } return 0;
    }
    if (j > 1 && iswalpha(a) && iswalpha(b)) return -2;                                   /* a maze or puzzle, left out of the map */
    if (!is_pass(a, b, dx, dy) || !arrow_allows(a, b, dx, dy)) return 0;
    if ((a == L'U' || a == L'D') && (b == L'/' || b == L'\\')) { marker = (int)a; if (j == 1) first_marker = (int)a; }   /* a marker on a crossing (UX) belongs to the other link */
  }
  if (!dest) return 0;
  if (marker) {                                                                          /* a vertical link: decide UP or DOWN from the game's own exits, else the marker */
    char type = 0;
    for (i = 0; i < r->nex; i++) if (r->ex[i].dest == dest) { if (!strcmp(r->ex[i].dir, "UP")) { type = 'U'; break; } if (!strcmp(r->ex[i].dir, "DOWN")) type = 'D'; }
    if (!type) type = first_marker ? (char)first_marker : (marker == 'U' ? 'D' : 'U');
    if (vertical != type) return 0;
  } else if (vertical) return 0;                                                        /* shifted keys climb or descend only along a marked link */
  return dest;
}

static int go_level(int dz)
{
  Room *r = &rooms[cur]; int k, best = 0; double bd = 1e9;
  for (k = 1; k <= nrooms; k++) {
    double dx, dy, dist; if (!rooms[k].has_level || !r->has_level || rooms[k].level != r->level + dz) continue;
    dx = (rooms[k].col - r->col) / 4.0; dy = (rooms[k].row - r->row) / 2.0; dist = dx * dx + dy * dy; if (dist < bd) { bd = dist; best = k; }
  }
  return best;
}

static void show_banner(const char *msg);
static void move_to(int n, const char *what)
{
  (void)what;
  if (n > 0) { cur = n; status[0] = 0; }
  else if (n == -2) show_banner("MAZE: NOT MAPPED");
  else show_banner(strstr(what, "level") ? "NO ROOM ON THAT LEVEL" : "INVALID DIRECTION");                                           /* no such exit: beep and say so across the centre of the map */
}

/* ------------------------------------------------------------------ drawing */
typedef struct { int y, x, h, w; } Rect;
static Rect last_map;                                                         /* the map's inner viewport of the last draw, for the banner */

/* dynamic layout: panel sizes are percentages of whatever the terminal is right now (laptop panel, TV over HDMI, a maximized window) */
static void layout(int h, int w, Rect *left, Rect *map, Rect *right, Rect *status)
{
  int lw = show_left ? (w * PCT_LEFT / 100 > 22 ? w * PCT_LEFT / 100 : 22) : 0, rw = show_right ? (w * PCT_RIGHT / 100 > 32 ? w * PCT_RIGHT / 100 : 32) : 0;
  int bh = show_bottom ? (h * PCT_BOTTOM / 100 > 6 ? h * PCT_BOTTOM / 100 : 6) : 0, mh, mw;
  if (lw + rw > w - 24) { if (lw >= rw) lw = 0; else rw = w - 24 > 0 ? w - 24 : 0; }
  mh = h - 2 - bh; if (mh < 5) mh = 5; mw = w - lw - rw; if (mw < 12) mw = 12;
  *left = (Rect){1, 0, mh, lw}; *map = (Rect){1, lw, mh, mw}; *right = (Rect){1, lw + mw, mh, rw}; *status = (Rect){1 + mh, 0, bh, w};
}

/* the map zoom: spacing grows with the terminal.  zoom k keeps the sheet's structure and spreads the squares over k+1 rows and 2(k+1) columns per grid step */
static wchar_t **zc; static int zrows, zcols, zk = 1, zoom_manual = 0;
static int cell_nonblank(int x, int y)
{
  int r = 2 * y, c = 4 * x; if (x < 0 || y < 0 || r >= crows || c + 1 >= ccols) return 0;
  return canvas[r][c] != L' ' || canvas[r][c + 1] != L' ';
}
static void build_zoom(int k)
{
  int CX = (ccols + 3) / 4, CY = (crows + 1) / 2, pw = 2 * (k + 1), ph = k + 1, x, y, r, i;
  if (zc) { for (i = 0; i < zrows; i++) free(zc[i]); free(zc); zc = NULL; }
  zk = k; if (k == 1) return;                                                  /* zoom 1 is the file's canvas as it is */
  zrows = CY * ph + 2; zcols = CX * pw + 4; zc = calloc(zrows, sizeof(wchar_t *));
  for (i = 0; i < zrows; i++) { int j; zc[i] = calloc(zcols + 2, sizeof(wchar_t)); for (j = 0; j < zcols; j++) zc[i][j] = L' '; }
  for (y = 0; y < CY; y++) for (x = 0; x < CX; x++) {
    int rr = 2 * y, cc = 4 * x; wchar_t a, b, g, v;
    if (rr >= crows || cc + 1 >= ccols) continue;
    a = canvas[rr][cc]; b = canvas[rr][cc + 1]; g = cc + 2 < ccols ? canvas[rr][cc + 2] : L' '; v = rr + 1 < crows ? canvas[rr + 1][cc] : L' ';
    if (a != L' ' || b != L' ') { zc[y * ph][x * pw] = a; zc[y * ph][x * pw + 1] = b; }
    if (g == L'=') for (i = 2; i < pw; i++) zc[y * ph][x * pw + i] = L'=';            /* a horizontal passage continues across the wider gap */
    if (v == L'|') for (r = 1; r < ph; r++) { zc[y * ph + r][x * pw] = L'|'; zc[y * ph + r][x * pw + 1] = L'|'; }
    if (b == L'/' || b == L'\\') {                                                    /* a diagonal square: strokes toward its diagonal neighbours */
      int sx = (b == L'/') ? 1 : -1;                                                  /* '/' leans up-right / down-left, '\' leans up-left / down-right */
      for (i = -1; i <= 1; i += 2) {
        int nx = x + i * sx, ny = y - i; if (!cell_nonblank(nx, ny)) continue;
        for (r = 1; r < ph; r++) { int row = y * ph + (-i) * r, col = x * pw + i * sx * (r * pw / ph); if (row >= 0 && col >= 0 && col + 1 < zcols) { zc[row][col] = b; zc[row][col + 1] = b; } }
      }
    }
  }
}
static int pick_zoom(int mw, int mh)
{
  int k, best = 1; if (zoom_manual) return zoom_manual;
  for (k = 1; k <= 5; k++) if (mw / (2 * (k + 1)) >= 18 && mh / (k + 1) >= 9) best = k;          /* the largest zoom that still shows about 18 x 9 squares */
  return best;
}
static void room_pos(Room *q, int k, int *row, int *col) { *row = (q->row / 2) * (k + 1); *col = (q->col / 4) * 2 * (k + 1); if (k == 1) { *row = q->row; *col = q->col; } }

static void draw_map(Rect m)                                                    /* m: the inner viewport */
{
  Room *r = &rooms[cur]; int k = pick_zoom(m.w, m.h), rr, rc, oy, ox, y, n, kk; wchar_t **cv; int rows_, cols_;
  last_map = m; if (k != zk || (k > 1 && !zc)) build_zoom(k);
  cv = (zk == 1) ? canvas : zc; rows_ = (zk == 1) ? crows : zrows; cols_ = (zk == 1) ? ccols : zcols;
  room_pos(r, zk, &rr, &rc); oy = rr - m.h / 2; ox = rc + 1 - m.w / 2;
  fill(m.y, m.x, m.h, m.w, P_MAP);
  for (y = 0; y < m.h; y++) {
    int cy = oy + y, x0, w; if (cy < 0 || cy >= rows_) continue;
    x0 = ox < 0 ? -ox : 0; w = m.w - x0; if (ox + x0 >= cols_) continue; if (w > cols_ - (ox + x0)) w = cols_ - (ox + x0);
    if (w > 0) { attron(COLOR_PAIR(P_MAP)); mvaddnwstr(m.y + y, m.x + x0, cv[cy] + ox + x0, w); attroff(COLOR_PAIR(P_MAP)); }
  }
  for (n = 1; n <= nrooms; n++) {
    Room *q = &rooms[n]; int qr, qc, y2, x2; wchar_t lab[3]; if (!q->name[0]) continue;
    room_pos(q, zk, &qr, &qc); y2 = m.y + qr - oy; x2 = m.x + qc - ox;
    if (y2 < m.y || y2 >= m.y + m.h || x2 < m.x - 1 || x2 >= m.x + m.w - 1) continue;
    lab[0] = canvas[q->row][q->col]; lab[1] = canvas[q->row][q->col + 1]; lab[2] = 0;
    if (layer_view && n != cur && (q->has_level != r->has_level || q->level != r->level)) { attron(COLOR_PAIR(P_MAP) | A_DIM); mvaddnwstr(y2, x2, L"··", 2); attroff(COLOR_PAIR(P_MAP) | A_DIM); continue; }
    attron(COLOR_PAIR(pair_for(q->has_level ? q->bg : 240))); mvaddnwstr(y2, x2, lab, 2); attroff(COLOR_PAIR(pair_for(q->has_level ? q->bg : 240)));   /* the whole square in its elevation colour */
    (void)kk;
    if (n == cur) { attron(COLOR_PAIR(P_BRACKET) | A_BOLD); mvaddstr(y2, x2 - 1, "["); mvaddstr(y2, x2 + 2, "]"); attroff(COLOR_PAIR(P_BRACKET) | A_BOLD); }   /* bright red brackets around the selected room, its number kept */
  }
}

static const char *level_name(Room *r)
{
  static char b[80]; if (!r->has_level) return "unknown"; if (r->level == 0) return "ground level (start)";
  snprintf(b, sizeof b, "%s %d", r->level > 0 ? "up" : "down", r->level > 0 ? r->level : -r->level); return b;
}

static void wrap_put(int y0, int x0, int ymax, int w, const char *s, int attr)
{
  int y = y0; const char *p = s; char line[300];
  while (*p && y < ymax) {
    int n = (int)strlen(p) < w ? (int)strlen(p) : w, cut = n;
    if (n == w && p[n]) { while (cut > 0 && p[cut] != ' ') cut--; if (cut == 0) cut = n; }
    memcpy(line, p, cut); line[cut] = 0; put(y++, x0, line, attr); p += cut; while (*p == ' ') p++;
  }
}

static const char *room_desc(Room *r)
{
  if (r->alt_after) return ver[r->num] ? r->alt_after : r->alt_before;
  return r->desc && r->desc[0] ? r->desc : "(no fixed description in this source)";
}

static void draw_all(void)
{
  int h, w, i, a, b, lr; Rect L, M, R, S; Room *r = &rooms[cur]; erase(); getmaxyx(stdscr, h, w); layout(h, w, &L, &M, &R, &S);
  fill(0, 0, h, w, P_TEXT);
  if (!nrooms) { put(0, 0, " zork-map ", COLOR_PAIR(P_HEAD) | A_BOLD); put(2, 2, "No map loaded.  Alt-O: open a map   Alt-M: map a game   Alt-X: quit", COLOR_PAIR(P_TEXT)); }
  else {
    draw_box(M.y, M.x, M.h, M.w, "Map", P_BORDER, P_MAP); draw_map((Rect){M.y + 1, M.x + 1, M.h - 2, M.w - 2});
    { char head[300]; snprintf(head, sizeof head, " %s  |  room %02d: %s  |  %s%s  |  zoom %d%s ", game, cur, r->name, level_name(r), layer_view ? "  [LAYER VIEW]" : "", zk, zoom_manual ? " (manual)" : " (auto)");
    fill(0, 0, 1, w, P_HEAD); put(0, 0, head, COLOR_PAIR(P_HEAD) | A_BOLD); }
    if (L.w) {                                                                  /* the elevation legend */
      draw_box(L.y, L.x, L.h, L.w, "Elevation", P_BORDER, P_TEXT);
      for (i = 0; i < nlev && i + 4 < L.h; i++) {
        int on = levels[i].z == r->level && r->has_level;
        put(L.y + 1 + i, L.x + 1, on ? ">" : " ", COLOR_PAIR(P_YEL) | A_BOLD);
        put(L.y + 1 + i, L.x + 2, "    ", COLOR_PAIR(pair_for(levels[i].bg)));
        putf(L.y + 1 + i, L.x + 7, COLOR_PAIR(P_TEXT), "%+d %.*s %d", levels[i].z, L.w - 14 > 0 ? L.w - 14 : 0, levels[i].z ? strchr(levels[i].label, ':') ? strchr(levels[i].label, ':') + 2 : levels[i].label : "ground", levels[i].rooms);
      }
      if (nlev + 4 < L.h - 1) { put(L.y + nlev + 2, L.x + 2, "white = ground", COLOR_PAIR(P_DIM)); put(L.y + nlev + 3, L.x + 2, "up: bright rainbow", COLOR_PAIR(P_DIM)); put(L.y + nlev + 4, L.x + 2, "down: dark rainbow", COLOR_PAIR(P_DIM)); }
    }
    if (R.w) {                                                                  /* the room list and the current room, in two boxes */
      int lh = R.h / 2 > 5 ? R.h / 2 : 5, dh = R.h - lh, dy;
      draw_box(R.y, R.x, lh, R.w, "Rooms", P_BORDER, P_TEXT); lr = lh - 2; if (lr < 1) lr = 1;
      a = cur - lr / 2; if (a > nrooms - lr + 1) a = nrooms - lr + 1; if (a < 1) a = 1; b = a + lr - 1; if (b > nrooms) b = nrooms;
      for (i = a; i <= b; i++) {
        char lab[8]; snprintf(lab, sizeof lab, i < 100 ? "%02d" : "**", i);
        put(R.y + 1 + i - a, R.x + 1, i == cur ? ">" : " ", COLOR_PAIR(P_YEL) | A_BOLD);
        put(R.y + 1 + i - a, R.x + 2, lab, COLOR_PAIR(pair_for(rooms[i].has_level ? rooms[i].bg : 240)));
        if (rooms[i].alt_after) put(R.y + 1 + i - a, R.x + 4, "*", COLOR_PAIR(P_YEL) | A_BOLD); else if (rooms[i].ntele) put(R.y + 1 + i - a, R.x + 4, "~", COLOR_PAIR(P_CYAN) | A_BOLD);
        putf(R.y + 1 + i - a, R.x + 5, COLOR_PAIR(P_TEXT) | (i == cur ? A_BOLD : 0), "%.*s", R.w - 7 > 0 ? R.w - 7 : 0, rooms[i].name);
      }
      if (dh >= 4) {
        draw_box(R.y + lh, R.x, dh, R.w, r->name, P_BORDER, P_TEXT); dy = R.y + lh + 1;
        if (r->alt_after) putf(dy++, R.x + 2, COLOR_PAIR(P_YEL) | A_BOLD, "%s%s%s   (* switches)", ver[cur] ? "AFTER: " : "BEFORE", ver[cur] ? r->alt_flag : "", "");
        wrap_put(dy, R.x + 2, R.y + lh + dh - 1, R.w - 4, room_desc(r), COLOR_PAIR(P_TEXT));
        dy += (int)(strlen(room_desc(r)) / (R.w - 4 > 4 ? R.w - 4 : 4)) + 2;
        if (r->items[0] && dy < R.y + lh + dh - 1) putf(dy++, R.x + 2, COLOR_PAIR(P_CYAN), "Items: %.*s", R.w - 11 > 0 ? R.w - 11 : 0, r->items);
        for (i = 0; i < r->ntele && dy < R.y + lh + dh - 1; i++) putf(dy++, R.x + 2, COLOR_PAIR(P_CYAN) | A_BOLD, "~ t: %.*s -> %02d %.*s", 30, r->tele[i].via, r->tele[i].dest, 24, r->tele[i].name);
        for (i = 0; i < r->nex && dy < R.y + lh + dh - 1; i++)
          if (r->ex[i].dest > 0) putf(dy++, R.x + 2, COLOR_PAIR(P_GRN), "%-5.5s -> %02d %.*s", r->ex[i].dir, r->ex[i].dest, R.w - 17 > 0 ? R.w - 17 : 0, rooms[r->ex[i].dest].name);
          else putf(dy++, R.x + 2, COLOR_PAIR(P_DIM), "%-5.5s %s", r->ex[i].dir, !strcmp(r->ex[i].kind, "per") ? "(routine)" : "x");
      }
    }
  }
  if (S.h > 0) {                                                                /* the status box, boxed, and the function-key strip on the last line */
    draw_box(S.y, S.x, S.h, S.w, "Status", P_BORDER, P_TEXT);
    if (show_help) {
      const char *h_[] = {"arrows N S W E   Shift-Up UPW  Shift-Down UPE  Shift-Left DW  Shift-Right DE   y u b n = NW NE SW SE", "Tab / Shift-Tab next / previous room   Home start   End last   PgUp / PgDn level up / down   F7 or l layer view   + - = zoom",
        "F2 legend  F3 sidebar  F4 status   ESC menu bar   Alt-O open  Alt-M map a game  Alt-G go to number  Alt-X quit", "t teleport (asks TELEPORT? Y/n)   * other version of a room marked * in the list   ~ marks a teleporter", 0};
      for (i = 0; h_[i] && i < S.h - 2; i++) put(S.y + 1 + i, S.x + 2, h_[i], COLOR_PAIR(P_TEXT));
    } else wrap_put(S.y + 1, S.x + 2, S.y + S.h - 1, S.w - 4, status, COLOR_PAIR(P_TEXT));
  }
  fill(h - 1, 0, 1, w, P_STRIP);
  put(h - 1, 0, " F1 Help  F2 Legend  F3 Sidebar  F4 Status  F7 Layers  +/- Zoom  Alt-O Open  Alt-M Map a game  Home Start  Alt-X Quit ", COLOR_PAIR(P_STRIP));
}

static void show_banner(const char *msg)
{
  int len = (int)strlen(msg) + 6, y = last_map.y + last_map.h / 2, x = last_map.x + (last_map.w - len) / 2; char b[80];
  beep(); snprintf(b, sizeof b, "   %s   ", msg); if (x < 0) x = 0;
  draw_box(y - 1, x - 1, 3, len + 2, NULL, P_BANNER, P_BANNER); put(y, x, b, COLOR_PAIR(P_BANNER) | A_BOLD); refresh();
  napms(550); flushinp();                                                     /* a quick flash; keys typed meanwhile are dropped */
}

static void teleport_prompt(void)                                            /* a push notification across the viewport that waits for Y or n */
{
  Room *r = &rooms[cur]; int sel = 0, c, y, w, x;
  if (!r->ntele) { show_banner("NO TELEPORT HERE"); return; }
  nocbreak(); cbreak(); beep();
  for (;;) {
    char l2[200]; Tele *t = &r->tele[sel]; draw_all();
    snprintf(l2, sizeof l2, "%s -> %02d %s", t->via, t->dest, t->name); w = (int)strlen(l2) + 6; if (w < 30) w = 30; if (w > last_map.w - 2) w = last_map.w - 2;
    y = last_map.y + last_map.h / 2 - 2; x = last_map.x + (last_map.w - w) / 2; if (x < 0) x = 0;
    draw_box(y, x, 5, w, NULL, P_TELE, P_TELE);
    putf(y + 1, x + (w - 13) / 2, COLOR_PAIR(P_TELE) | A_BOLD, "TELEPORT? Y/n");
    putf(y + 2, x + 2, COLOR_PAIR(P_TELE), "%.*s", w - 4, l2);
    if (r->ntele > 1) putf(y + 3, x + 2, COLOR_PAIR(P_TELE), "Tab: next destination (%d of %d)", sel + 1, r->ntele);
    refresh(); c = getch();
    if (c == 'y' || c == 'Y' || c == '\n' || c == KEY_ENTER) { cur = t->dest; snprintf(status, sizeof status, "Teleported to %02d %s.", t->dest, t->name); break; }
    if (c == 'n' || c == 'N' || c == 27 || c == 'q') { snprintf(status, sizeof status, "Teleport cancelled."); break; }
    if (c == '\t' && r->ntele > 1) sel = (sel + 1) % r->ntele;
  }
  halfdelay(5);
}

/* ------------------------------------------------------------------ dialogs (black on light grey, boxed) */
static int cmpstr(const void *a, const void *b) { return strcmp(*(char **)a, *(char **)b); }
static int pick_map(void)                                   /* Duh DRAW's directory dialog, reduced to *.zmap */
{
  char *names[256]; int n = 0, sel = 0, c, i, h, w; DIR *d = opendir(mapdir); struct dirent *e;
  if (!d) { snprintf(status, sizeof status, "Cannot open the map folder %s (see ~/.zorkmapper/config).", mapdir); return 0; }
  while ((e = readdir(d)) && n < 256) { size_t l = strlen(e->d_name); if (l > 5 && !strcmp(e->d_name + l - 5, ".zmap")) names[n++] = strdup(e->d_name); }
  closedir(d); qsort(names, n, sizeof *names, cmpstr);
  if (!n) { snprintf(status, sizeof status, "No .zmap files in %s.  Map a game with Alt-M.", mapdir); return 0; }
  for (;;) {
    int bw, y0, x0; getmaxyx(stdscr, h, w); bw = 44 < w - 2 ? 44 : w - 2; y0 = h / 2 - n / 2 - 1; if (y0 < 0) y0 = 0; x0 = (w - bw) / 2;
    draw_box(y0, x0, n + 2, bw, "Open a map", P_BLACKBOX, P_MENU);
    for (i = 0; i < n; i++) putf(y0 + 1 + i, x0 + 1, i == sel ? COLOR_PAIR(P_MENUSEL) | A_BOLD : COLOR_PAIR(P_MENU), " %-*.*s", bw - 4, bw - 4, names[i]);
    refresh(); c = getch();
    if (c == KEY_UP) sel = (sel + n - 1) % n; else if (c == KEY_DOWN) sel = (sel + 1) % n;
    else if (c == '\n' || c == KEY_ENTER) { char p[700]; snprintf(p, sizeof p, "%s/%s", mapdir, names[sel]); for (i = 0; i < n; i++) free(names[i]);
      if (load_map(p)) { snprintf(status, sizeof status, "Could not read %s", p); return 0; } snprintf(status, sizeof status, "Loaded %s: %d rooms.", p, nrooms); return 1; }
    else if (c == 27) { nodelay(stdscr, TRUE); getch(); nodelay(stdscr, FALSE); break; } else if (c == 'q') break;
    draw_all();
  }
  for (i = 0; i < n; i++) free(names[i]);
  return 0;
}

static void prompt_line(const char *label, char *buf, int max)
{
  int c, n = 0, h, w, bw; buf[0] = 0; curs_set(1);
  for (;;) {
    getmaxyx(stdscr, h, w); bw = w - 6 > 20 ? w - 6 : 20; draw_all(); draw_box(h / 2 - 1, 2, 3, bw, NULL, P_BLACKBOX, P_MENU);
    putf(h / 2, 3, COLOR_PAIR(P_MENU) | A_BOLD, "%s", label); putf(h / 2, 3 + (int)strlen(label), COLOR_PAIR(P_MENU), "%s", buf); refresh(); c = getch();
    if (c == '\n' || c == KEY_ENTER) break;
    if (c == 27) { buf[0] = 0; break; }
    if ((c == KEY_BACKSPACE || c == 127 || c == 8) && n) buf[--n] = 0; else if (c >= 32 && c < 127 && n < max - 1) { buf[n++] = (char)c; buf[n] = 0; }
  }
  curs_set(0);
}

static void map_a_game(void)
{
  char path[500], cmd[1200], *home = getenv("ZORKMAPPER_HOME"), stem[200], *b, *dot; prompt_line("Map a game: Z-machine file or ZIL folder > ", path, sizeof path);
  if (!path[0]) return;
  snprintf(cmd, sizeof cmd, "cd '%s' && python3 -m zorkmapper --map '%s'", home ? home : mapper_home, path);
  def_prog_mode(); endwin(); printf("Mapping %s ...\n", path); fflush(stdout); if (system(cmd) != 0) { reset_prog_mode(); refresh(); snprintf(status, sizeof status, "Mapping %s failed.", path); return; }
  reset_prog_mode(); refresh();
  b = strrchr(path, '/'); snprintf(stem, sizeof stem, "%s", b ? b + 1 : path); dot = strrchr(stem, '.'); if (dot && dot != stem) *dot = 0;
  snprintf(cmd, sizeof cmd, "%s/%s.zmap", mapdir, stem);
  if (load_map(cmd)) snprintf(status, sizeof status, "Mapped %s, but %s was not found.", path, cmd); else snprintf(status, sizeof status, "Mapped %s -> %s (%d rooms).", path, cmd, nrooms);
}

/* ------------------------------------------------------------------ the ESC menu bar (after TheDraw): black on light grey, the selection white on blue */
static const char *menu_names[] = {"Files", "Go", "View", "Levels", "Help"};
static const char *menu_items[5][7] = {{"Open map       Alt-O", "Map a game     Alt-M", "Quit           Alt-X", 0, 0, 0, 0}, {"Start          Home", "Next room      Tab", "Previous       S-Tab", "Last room      End", "Go to number   Alt-G", "Teleport       t", 0},
  {"Legend         F2", "Sidebar        F3", "Status         F4", "Zoom auto      =", "Other version  *", 0, 0}, {"Level up       PgUp", "Level down     PgDn", "Layer view     F7", 0, 0, 0, 0}, {"Keys           F1", 0, 0, 0, 0, 0, 0}};
static int menu_bar(void)                                   /* returns a command code: 'o' 'm' 'x' 'g' or 0 */
{
  int m = 0, i = 0, open_ = 0, c, k, n, cnt;
  for (;;) {
    draw_all(); fill(0, 0, 1, COLS, P_MENU); put(0, 0, " ", COLOR_PAIR(P_MENU));
    for (k = 0, n = 1; k < 5; k++) { putf(0, n, k == m ? COLOR_PAIR(P_MENUSEL) | A_BOLD : COLOR_PAIR(P_MENU), " %s ", menu_names[k]); n += (int)strlen(menu_names[k]) + 3; }
    cnt = 0; while (cnt < 7 && menu_items[m][cnt]) cnt++;
    if (open_) { int x0 = 1; for (k = 0; k < m; k++) x0 += (int)strlen(menu_names[k]) + 3; draw_box(1, x0, cnt + 2, 24, NULL, P_BLACKBOX, P_MENU);
      for (k = 0; k < cnt; k++) putf(2 + k, x0 + 1, k == i ? COLOR_PAIR(P_MENUSEL) | A_BOLD : COLOR_PAIR(P_MENU), " %-21s", menu_items[m][k]); }
    refresh(); c = getch();
    if (c == 27) return 0;
    if (c == KEY_LEFT) { m = (m + 4) % 5; i = 0; } else if (c == KEY_RIGHT) { m = (m + 1) % 5; i = 0; }
    else if (c == KEY_DOWN) { open_ = 1; i = (i + 1) % (cnt ? cnt : 1); }
    else if (c == KEY_UP && open_) { i = (i + cnt - 1) % (cnt ? cnt : 1); }
    else if (c == '\n' || c == KEY_ENTER) {
      if (!open_) { open_ = 1; continue; }
      if (m == 0) return i == 0 ? 'o' : i == 1 ? 'm' : 'x';
      if (m == 1) { if (i == 0) cur = start_room; else if (i == 1) cur = cur % nrooms + 1; else if (i == 2) cur = (cur + nrooms - 2) % nrooms + 1; else if (i == 3) cur = nrooms; else if (i == 4) return 'g'; else return 't'; return 0; }
      if (m == 2) { if (i == 0) show_left = !show_left; else if (i == 1) show_right = !show_right; else if (i == 2) show_bottom = !show_bottom; else if (i == 3) zoom_manual = 0; else if (rooms[cur].alt_after) ver[cur] = !ver[cur]; return 0; }
      if (m == 3) { if (i == 2) layer_view = !layer_view; else move_to(go_level(i == 0 ? 1 : -1), i == 0 ? "up a level" : "down a level"); return 0; }
      show_help = !show_help; return 0;
    } else if (c == 'f' || c == 'F') { m = 0; open_ = 1; } else if (c == 'g' || c == 'G') { m = 1; open_ = 1; } else if (c == 'v' || c == 'V') { m = 2; open_ = 1; }
    else if (c == 'l' || c == 'L') { m = 3; open_ = 1; } else if (c == 'h' || c == 'H') { m = 4; open_ = 1; }
  }
}

/* ------------------------------------------------------------------ keys: Duh DRAW's reader, with ESC+letter as Alt-letter, on top of ncurses */
static int read_key(void)
{
  int c = getch();
  if (c != 27) return c;
  timeout(25); c = getch(); timeout(500);
  if (c == ERR) return 27;                                      /* a lone ESC: the menu bar */
  if (c >= 'a' && c <= 'z') return ALT + c;                      /* Alt-letter, as Duh DRAW returns it */
  if (c == '[' || c == 'O') {                                   /* a CSI / SS3 sequence ncurses did not translate (the terminal's cursor-key mode differs from terminfo) */
    int p[4] = {0}, np = 0, f;
    timeout(25); while ((f = getch()) != ERR && (f == ';' || (f >= '0' && f <= '9'))) { if (f == ';') np++; else if (np < 4) p[np] = p[np] * 10 + (f - '0'); } timeout(500);
    { int shifted = (np >= 1 && p[1] == 2);
      switch (f) {
      case 'A': return shifted ? KEY_SR : KEY_UP;   case 'B': return shifted ? KEY_SF : KEY_DOWN;
      case 'C': return shifted ? KEY_SRIGHT : KEY_RIGHT; case 'D': return shifted ? KEY_SLEFT : KEY_LEFT;
      case 'H': return KEY_HOME; case 'F': return KEY_END; case 'Z': return KEY_BTAB;
      case '~': return p[0] == 5 ? KEY_PPAGE : p[0] == 6 ? KEY_NPAGE : (p[0] == 1 || p[0] == 7) ? KEY_HOME : (p[0] == 4 || p[0] == 8) ? KEY_END : 0;
      } }
  }
  return 0;
}

static int read_key_wait(void) { int c = read_key(); return c; }

static void follow_resize(void)                                 /* maximize, un-maximize, a different screen: take the real size from the tty and re-lay-out everything */
{
  struct winsize ws;
  if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &ws) == 0 && ws.ws_row > 0 && (ws.ws_row != LINES || ws.ws_col != COLS)) { resizeterm(ws.ws_row, ws.ws_col); clearok(stdscr, TRUE); }
}

int main(int argc, char *argv[])
{
  int c, quit = 0; char *env = getenv("ZORKMAP_DIR");
  setlocale(LC_ALL, ""); load_config(); if (env) snprintf(mapdir, sizeof mapdir, "%s", env);                 /* ZORKMAP_DIR still overrides the maps folder */
  if (argc > 2 && !strcmp(argv[1], "--check")) {                 /* a headless self-test: parse a map file and say what is in it */
    int rc = load_map(argv[2]); if (rc) { fprintf(stderr, "cannot read %s (%d)\n", argv[2], rc); return 1; }
    printf("ok rooms=%d levels=%d canvas=%dx%d start=%d title=%s\n", nrooms, nlev, crows, ccols, start_room, title); return 0;
  }
  initscr(); noecho(); cbreak(); keypad(stdscr, TRUE); curs_set(0); set_escdelay(25); start_color(); use_default_colors(); init_colors(); halfdelay(5);
  if (argc > 1 && load_map(argv[1])) snprintf(status, sizeof status, "Could not read %s", argv[1]);
  else if (argc <= 1 && !nrooms) { nocbreak(); cbreak(); pick_map(); halfdelay(5); }
  while (!quit) {
    follow_resize(); draw_all(); refresh(); c = read_key_wait();
    if (c == ERR || c == KEY_RESIZE) continue;                   /* a timeout (so a resize is noticed within half a second) or the resize itself: just redraw */
    if (getenv("DUHMAP_TRACE")) { FILE *t = fopen(getenv("DUHMAP_TRACE"), "a"); if (t) { fprintf(t, "key %d at room %d\n", c, cur); fclose(t); } }   /* test hook: what key arrived, and where we were */
    switch (c) {
    case KEY_UP: move_to(go_geo(0, -1, 0), "north"); break;
    case KEY_DOWN: move_to(go_geo(0, 1, 0), "south"); break;
    case KEY_LEFT: move_to(go_geo(-1, 0, 0), "west"); break;
    case KEY_RIGHT: move_to(go_geo(1, 0, 0), "east"); break;
    case KEY_SR: move_to(go_geo(-1, -1, 'U'), "up (west)"); break;        /* Shift-Up    UPW */
    case KEY_SF: move_to(go_geo(1, -1, 'U'), "up (east)"); break;        /* Shift-Down  UPE */
    case KEY_SLEFT: move_to(go_geo(-1, 1, 'D'), "down (west)"); break; /* Shift-Left  DW  */
    case KEY_SRIGHT: move_to(go_geo(1, 1, 'D'), "down (east)"); break; /* Shift-Right DE  */
    case 'y': move_to(go_geo(-1, -1, 0), "northwest"); break; case 'u': move_to(go_geo(1, -1, 0), "northeast"); break;
    case 'b': move_to(go_geo(-1, 1, 0), "southwest"); break; case 'n': move_to(go_geo(1, 1, 0), "southeast"); break;
    case '\t': if (nrooms) cur = cur % nrooms + 1; break; case KEY_BTAB: if (nrooms) cur = (cur + nrooms - 2) % nrooms + 1; break;
    case KEY_HOME: cur = start_room; break; case KEY_END: if (nrooms) cur = nrooms; break;
    case KEY_PPAGE: move_to(go_level(1), "up a level"); break; case KEY_NPAGE: move_to(go_level(-1), "down a level"); break;
    case '+': zoom_manual = (zoom_manual ? zoom_manual : zk) + 1; if (zoom_manual > 5) zoom_manual = 5; break;
    case '-': zoom_manual = (zoom_manual ? zoom_manual : zk) - 1; if (zoom_manual < 1) zoom_manual = 1; break;
    case '=': zoom_manual = 0; break;
    case '*': if (nrooms && rooms[cur].alt_after) { ver[cur] = !ver[cur]; snprintf(status, sizeof status, ver[cur] ? "Showing the room AFTER %s (irreversible)." : "Showing the room BEFORE the event.", rooms[cur].alt_flag); } else snprintf(status, sizeof status, "This room has no other version."); break;
    case 't': if (nrooms) teleport_prompt(); break;
    case KEY_F(7): case 'l': layer_view = !layer_view; snprintf(status, sizeof status, layer_view ? "Layer view: only this elevation layer in colour; PgUp / PgDn change layer." : "Layer view off."); break;
    case KEY_F(1): case ALT + 'h': show_help = !show_help; break;
    case KEY_F(2): show_left = !show_left; break; case KEY_F(3): show_right = !show_right; break; case KEY_F(4): show_bottom = !show_bottom; break;
    case KEY_F(10): case ALT + 'x': case 'q': quit = 1; break;
    case KEY_F(5): case ALT + 'o': nocbreak(); cbreak(); pick_map(); halfdelay(5); break;
    case KEY_F(6): case ALT + 'm': nocbreak(); cbreak(); map_a_game(); halfdelay(5); break;
    case ALT + 'g': { char b[16]; nocbreak(); cbreak(); prompt_line("Go to room number > ", b, sizeof b); halfdelay(5); if (atoi(b) >= 1 && atoi(b) <= nrooms) cur = atoi(b); } break;
    case 27: { int cmd; nocbreak(); cbreak(); cmd = menu_bar(); halfdelay(5);
      if (cmd == 't') teleport_prompt(); else if (cmd == 'x') quit = 1; else if (cmd == 'o') { nocbreak(); cbreak(); pick_map(); halfdelay(5); } else if (cmd == 'm') { nocbreak(); cbreak(); map_a_game(); halfdelay(5); }
      else if (cmd == 'g') { char b[16]; nocbreak(); cbreak(); prompt_line("Go to room number > ", b, sizeof b); halfdelay(5); if (atoi(b) >= 1 && atoi(b) <= nrooms) cur = atoi(b); } } break;
    }
  }
  endwin(); free_map(); return 0;
}
