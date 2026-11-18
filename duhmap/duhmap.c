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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <unistd.h>
#include <stdarg.h>

#define ALT 1000                    /* Alt-letter codes: ncurses key codes occupy 257..511, so Duh DRAW's 256+letter would collide */
#define MAXR 400
#define MAXX 24
#define MAXL 16

typedef struct { char dir[8], kind[8]; int dest; char text[200]; } Exit;
typedef struct { int num, row, col, level, has_level, bg; char name[100]; char *desc; char items[600]; Exit ex[MAXX]; int nex; } Room;
typedef struct { int z, bg, rooms; char label[80]; } Level;

static wchar_t **canvas; static int crows, ccols;
static Room rooms[MAXR + 1]; static int nrooms, start_room = 1, cur = 1;
static Level levels[MAXL]; static int nlev;
static int PCT_LEFT = 16, PCT_RIGHT = 30, PCT_BOTTOM = 22;                  /* panel sizes, percent of the terminal (config: panel_left / panel_right / panel_bottom) */
static char mapper_home[512] = "..", conf_root[512];
static char title[200], game[100], mapdir[512] = "ASCIIArt", mappath[600], status[400] = "F5 / Alt-O opens a map.";
static int show_left = 1, show_right = 1, show_bottom = 1, show_help = 0, layer_view = 0;     /* layer_view: only the current elevation layer in colour */

/* ------------------------------------------------------------------ map file */
static void free_map(void)
{
  int i;
  if (canvas) { for (i = 0; i < crows; i++) free(canvas[i]); free(canvas); canvas = NULL; }
  for (i = 1; i <= nrooms; i++) { free(rooms[i].desc); rooms[i].desc = NULL; }
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

/* ------------------------------------------------------------------ colours */
static int bright_bg(int c) { return c == 231 || c == 196 || c == 208 || c == 226 || c == 46 || c == 33; }
static short pair_for(int bg)
{
  static int seen[64]; static int n = 0; int i;
  for (i = 0; i < n; i++) if (seen[i] == bg) return (short)(i + 1);
  if (n >= 60) return 0;
  seen[n] = bg; init_pair(n + 1, bright_bg(bg) ? 0 : 15, bg); return (short)(++n);
}
static void put(int y, int x, const char *s, int attr)
{
  int h, w; getmaxyx(stdscr, h, w); if (y < 0 || y >= h || x >= w) return;
  attron(attr); mvaddnstr(y, x, s, w - x - (y == h - 1)); attroff(attr);
}
static void putf(int y, int x, int attr, const char *fmt, ...)
{
  char b[512]; va_list a; va_start(a, fmt); vsnprintf(b, sizeof b, fmt, a); va_end(a); put(y, x, b, attr);
}

/* ------------------------------------------------------------------ navigation */
static int vdx(const char *d) { return !strcmp(d, "EAST") || !strcmp(d, "NE") || !strcmp(d, "SE") ? 1 : !strcmp(d, "WEST") || !strcmp(d, "NW") || !strcmp(d, "SW") ? -1 : 0; }
static int vdy(const char *d) { return !strcmp(d, "SOUTH") || !strcmp(d, "SE") || !strcmp(d, "SW") ? 1 : !strcmp(d, "NORTH") || !strcmp(d, "NE") || !strcmp(d, "NW") ? -1 : 0; }

static int go_compass(const char *d)
{
  Room *r = &rooms[cur]; int i, k, best = 0; double bd = 1e9; int dx = vdx(d), dy = vdy(d);
  for (i = 0; i < r->nex; i++) if (!strcmp(r->ex[i].dir, d) && r->ex[i].dest > 0 && (!strcmp(r->ex[i].kind, "to") || !strcmp(r->ex[i].kind, "cond"))) return r->ex[i].dest;     /* a real exit: positive */
  (void)k; (void)best; (void)bd; (void)dx; (void)dy;                 /* no exit that way: refuse (the caller beeps), never guess a nearby room */
  return 0;
}

/* UP and DOWN are drawn as diagonals: side 'W' or 'E' prefers the exit whose room lies on that side; otherwise any exit of that kind */
static int go_vertical(const char *d, char side)
{
  Room *r = &rooms[cur]; int i, any = 0;
  for (i = 0; i < r->nex; i++) {
    Exit *e = &r->ex[i]; if (strcmp(e->dir, d) || e->dest <= 0 || (strcmp(e->kind, "to") && strcmp(e->kind, "cond"))) continue;
    if (!any) any = e->dest;
    if ((side == 'W' && rooms[e->dest].col < r->col) || (side == 'E' && rooms[e->dest].col > r->col)) return e->dest;
  }
  return any;
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
  else show_banner(strstr(what, "level") ? "NO ROOM ON THAT LEVEL" : "INVALID DIRECTION");                                           /* no such exit: beep and say so across the centre of the map */
}

/* ------------------------------------------------------------------ drawing */
typedef struct { int y, x, h, w; } Rect;
static Rect last_map;                                                         /* the map viewport of the last draw, for the banner */
static void layout(int h, int w, Rect *title_, Rect *left, Rect *map, Rect *right, Rect *bottom)
{
  int lw = show_left ? (w * PCT_LEFT / 100 > 20 ? w * PCT_LEFT / 100 : 20) : 0, rw = show_right ? (w * PCT_RIGHT / 100 > 30 ? w * PCT_RIGHT / 100 : 30) : 0;
  int bh = show_bottom ? (h * PCT_BOTTOM / 100 > 7 ? h * PCT_BOTTOM / 100 : 7) : 0, mh, mw;
  if (lw + rw > w - 20) { if (lw >= rw) lw = 0; else rw = w - 20 > 0 ? w - 20 : 0; }
  mh = h - 1 - bh; if (mh < 3) mh = 3; mw = w - lw - rw; if (mw < 10) mw = 10;
  *title_ = (Rect){0, 0, 1, w}; *left = (Rect){1, 0, mh, lw}; *map = (Rect){1, lw, mh, mw}; *right = (Rect){1, lw + mw, mh, rw}; *bottom = (Rect){1 + mh, 0, h - 1 - mh, w};
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

static void draw_map(Rect m)
{
  last_map = m;
  Room *r = &rooms[cur]; int oy = r->row - m.h / 2, ox = r->col + 1 - m.w / 2, y, k;
  for (y = 0; y < m.h; y++) {
    int cy = oy + y, x0, n; if (cy < 0 || cy >= crows) continue;
    x0 = ox < 0 ? -ox : 0; n = m.w - x0; if (ox + x0 >= ccols) continue; if (n > ccols - (ox + x0)) n = ccols - (ox + x0);
    if (n > 0) { attron(A_DIM); mvaddnwstr(m.y + y, m.x + x0, canvas[cy] + ox + x0, n); attroff(A_DIM); }
  }
  for (k = 1; k <= nrooms; k++) {
    Room *q = &rooms[k]; int y2 = m.y + q->row - oy, x2 = m.x + q->col - ox; wchar_t lab[3]; short pr = pair_for(q->bg);
    if (!q->name[0] || y2 < m.y || y2 >= m.y + m.h || x2 < m.x || x2 >= m.x + m.w - 1) continue;
    lab[0] = canvas[q->row][q->col]; lab[1] = canvas[q->row][q->col + 1]; lab[2] = 0;
    if (layer_view && (q->has_level != r->has_level || q->level != r->level)) { attron(A_DIM); mvaddnwstr(y2, x2, L"\u00b7\u00b7", 2); attroff(A_DIM); continue; }   /* another layer: a faint placeholder */
    if (k == cur) {                                                           /* the selected room: an outline in blue, its number left to the sidebar */
      init_pair(3, 12, -1); attron(COLOR_PAIR(3) | A_BOLD); mvaddstr(y2, x2 - 1, "[  ]"); attroff(COLOR_PAIR(3) | A_BOLD); continue;
    }
    attron(COLOR_PAIR(pr)); mvaddnwstr(y2, x2, lab, 2); attroff(COLOR_PAIR(pr));    /* the whole square in its elevation colour: black text on bright, white on dark */
  }
}

static const char *level_name(Room *r)
{
  static char b[80]; if (!r->has_level) return "unknown"; if (r->level == 0) return "ground level (start)";
  snprintf(b, sizeof b, "%s %d", r->level > 0 ? "up" : "down", r->level > 0 ? r->level : -r->level); return b;
}

static void draw_all(void)
{
  int h, w, i, a, b; Rect T, L, M, R, B; Room *r = &rooms[cur]; erase(); getmaxyx(stdscr, h, w); layout(h, w, &T, &L, &M, &R, &B);
  init_pair(1, 11, -1);
  if (!nrooms) { put(0, 0, " duhmap ", COLOR_PAIR(pair_for(4)) | A_BOLD); put(2, 2, "No map loaded.  Alt-O: open a map   Alt-M: map a game   Alt-X: quit", 0); }
  else {
    char head[300]; snprintf(head, sizeof head, " %s  |  room %02d: %s  |  %s%s ", game, cur, r->name, level_name(r), layer_view ? "  [LAYER VIEW]" : ""); put(0, 0, head, A_REVERSE | A_BOLD);
    draw_map(M);
    if (L.w) {                                                                  /* the elevation legend */
      put(L.y, L.x + 1, "Elevation", COLOR_PAIR(1) | A_BOLD);
      for (i = 0; i < nlev && i + 2 < L.h; i++) {
        put(L.y + 1 + i, L.x, levels[i].z == r->level && r->has_level ? ">" : " ", COLOR_PAIR(1) | A_BOLD);
        put(L.y + 1 + i, L.x + 1, "  ", COLOR_PAIR(pair_for(levels[i].bg)));
        putf(L.y + 1 + i, L.x + 4, 0, "%+d %.*s %d", levels[i].z, L.w - 10, levels[i].z ? strchr(levels[i].label, ':') ? strchr(levels[i].label, ':') + 2 : levels[i].label : "ground", levels[i].rooms);
      }
      if (nlev + 4 < L.h) { put(L.y + nlev + 2, L.x + 1, "white = ground", A_DIM); put(L.y + nlev + 3, L.x + 1, "up: bright rainbow", A_DIM); put(L.y + nlev + 4, L.x + 1, "down: dark rainbow", A_DIM); }
    }
    if (R.w) {                                                                  /* the room list and the current room */
      int lr = R.h / 2 - 1 > 3 ? R.h / 2 - 1 : 3, dy;
      put(R.y, R.x + 1, "Rooms", COLOR_PAIR(1) | A_BOLD);
      a = cur - lr / 2; if (a > nrooms - lr + 1) a = nrooms - lr + 1; if (a < 1) a = 1; b = a + lr - 1; if (b > nrooms) b = nrooms;
      for (i = a; i <= b; i++) {
        put(R.y + 1 + i - a, R.x, i == cur ? ">" : " ", COLOR_PAIR(1) | A_BOLD);
        { char lab[8]; snprintf(lab, sizeof lab, i < 100 ? "%02d" : "**", i); put(R.y + 1 + i - a, R.x + 1, lab, COLOR_PAIR(pair_for(rooms[i].has_level ? rooms[i].bg : 240))); }
        putf(R.y + 1 + i - a, R.x + 4, i == cur ? A_BOLD : 0, "%.*s", R.w - 5, rooms[i].name);
      }
      dy = R.y + lr + 2; put(dy - 1, R.x + 1, "----------------------------------------", A_DIM);
      put(dy++, R.x + 1, r->name, A_BOLD);
      wrap_put(dy, R.x + 1, R.y + R.h - 1, R.w - 2, r->desc && r->desc[0] ? r->desc : "(no fixed description in this source)", 0);
      { int used = (int)((r->desc ? strlen(r->desc) : 40) / (R.w - 2)) + 2; dy += used > 1 ? used : 1; }
      if (r->items[0] && dy < R.y + R.h) putf(dy++, R.x + 1, COLOR_PAIR(pair_for(4)), "Items: %.*s", R.w - 9, r->items);
      for (i = 0; i < r->nex && dy < R.y + R.h; i++)
        if (r->ex[i].dest > 0) putf(dy++, R.x + 1, 0, "%-5.5s -> %02d %.*s", r->ex[i].dir, r->ex[i].dest, R.w - 14, rooms[r->ex[i].dest].name);
        else putf(dy++, R.x + 1, A_DIM, "%-5.5s %s", r->ex[i].dir, !strcmp(r->ex[i].kind, "per") ? "(routine)" : "x");
    }
  }
  if (B.h > 0) {                                                                /* the status box and the function-key strip (as Duh DRAW's last line) */
    put(B.y, 0, " Status ---------------------------------------------------------------------------", A_DIM);
    if (show_help) {
      const char *h_[] = {"arrows N S W E    Shift-Up UPW  Shift-Down UPE  Shift-Left DW  Shift-Right DE    y u b n = NW NE SW SE", "Tab / Shift-Tab next / previous room   Home start   End last   PgUp / PgDn level up / down   F7 or l layer view",
        "F2 legend  F3 sidebar  F4 status   ESC menu bar   Alt-O open  Alt-M map a game  Alt-G go to number  Alt-X quit", 0};
      for (i = 0; h_[i] && B.y + 1 + i < B.y + B.h - 1; i++) put(B.y + 1 + i, 1, h_[i], 0);
    } else wrap_put(B.y + 1, 1, B.y + B.h - 1, w - 2, status, 0);
    put(B.y + B.h - 1, 0, " F1 Help  F2 Legend  F3 Sidebar  F4 Status  Alt-O Open  Alt-M Map a game  Home Start  Tab Next  Alt-X Quit ", COLOR_PAIR(pair_for(6)));
  }
}

static void show_banner(const char *msg)
{
  int len = (int)strlen(msg) + 4, y = last_map.y + last_map.h / 2, x = last_map.x + (last_map.w - len) / 2;
  char b[80]; beep(); snprintf(b, sizeof b, "  %s  ", msg); if (x < 0) x = 0;
  init_pair(2, 15, 196); attron(COLOR_PAIR(2) | A_BOLD); mvaddstr(y, x, b); attroff(COLOR_PAIR(2) | A_BOLD); refresh();
  napms(550); flushinp();                                                     /* a quick flash; keys typed meanwhile are dropped */
}

/* ------------------------------------------------------------------ dialogs */
static int cmpstr(const void *a, const void *b) { return strcmp(*(char **)a, *(char **)b); }
static int pick_map(void)                                   /* Duh DRAW's directory dialog, reduced to *.zmap */
{
  char *names[256]; int n = 0, sel = 0, c, i, h, w; DIR *d = opendir(mapdir); struct dirent *e;
  if (!d) { snprintf(status, sizeof status, "Cannot open the map folder %s (see ~/.zorkmapper/config).", mapdir); return 0; }
  while ((e = readdir(d)) && n < 256) { size_t l = strlen(e->d_name); if (l > 5 && !strcmp(e->d_name + l - 5, ".zmap")) names[n++] = strdup(e->d_name); }
  closedir(d); qsort(names, n, sizeof *names, cmpstr);
  if (!n) { snprintf(status, sizeof status, "No .zmap files in %s.  Map a game with Alt-M.", mapdir); return 0; }
  for (;;) {
    getmaxyx(stdscr, h, w); { int y0 = h / 2 - n / 2 - 1, x0 = w / 2 - 20; put(y0, x0, " Open a map                              ", A_REVERSE | A_BOLD);
      for (i = 0; i < n; i++) putf(y0 + 1 + i, x0, i == sel ? A_REVERSE : A_NORMAL, " %-39.39s", names[i]); }
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
  int c, n = 0, h, w; buf[0] = 0; curs_set(1);
  for (;;) {
    getmaxyx(stdscr, h, w); (void)w; move(h - 2, 0); clrtoeol(); put(h - 2, 0, label, A_REVERSE | A_BOLD); put(h - 2, (int)strlen(label), buf, A_BOLD); refresh(); c = getch();
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

/* ------------------------------------------------------------------ the ESC menu bar (after TheDraw) */
static const char *menu_names[] = {"Files", "Go", "View", "Levels", "Help"};
static const char *menu_items[5][5] = {{"Open map       Alt-O", "Map a game     Alt-M", "Quit           Alt-X", 0, 0}, {"Start          Home", "Next room      Tab", "Previous       S-Tab", "Last room      End", "Go to number   Alt-G"},
  {"Legend         F2", "Sidebar        F3", "Status         F4", 0, 0}, {"Level up       PgUp", "Level down     PgDn", "Layer view     F7", 0, 0}, {"Keys           F1", 0, 0, 0, 0}};
static int menu_bar(void)                                   /* returns a command code: 'o' 'm' 'x' 'g' or 0 */
{
  int m = 0, i = 0, open_ = 0, c, h, w, k, n;
  for (;;) {
    getmaxyx(stdscr, h, w); (void)h; (void)w; move(0, 0); clrtoeol(); put(0, 0, " ", A_REVERSE);
    for (k = 0, n = 1; k < 5; k++) { putf(0, n, k == m ? A_REVERSE | A_BOLD : A_REVERSE, " %s ", menu_names[k]); n += (int)strlen(menu_names[k]) + 3; }
    if (open_) { int cnt = 0, x0 = 1; for (k = 0; k < m; k++) x0 += (int)strlen(menu_names[k]) + 3; while (cnt < 5 && menu_items[m][cnt]) cnt++;
      for (k = 0; k < cnt; k++) putf(1 + k, x0, k == i ? A_REVERSE | A_BOLD : A_REVERSE, " %-20s", menu_items[m][k]); }
    refresh(); c = getch();
    if (c == 27) return 0;
    if (c == KEY_LEFT) { m = (m + 4) % 5; i = 0; } else if (c == KEY_RIGHT) { m = (m + 1) % 5; i = 0; }
    else if (c == KEY_DOWN) { open_ = 1; if (open_) { int cnt = 0; while (cnt < 5 && menu_items[m][cnt]) cnt++; i = (i + 1) % cnt; } }
    else if (c == KEY_UP && open_) { int cnt = 0; while (cnt < 5 && menu_items[m][cnt]) cnt++; i = (i + cnt - 1) % cnt; }
    else if (c == '\n' || c == KEY_ENTER) {
      if (!open_) { open_ = 1; continue; }
      if (m == 0) return i == 0 ? 'o' : i == 1 ? 'm' : 'x';
      if (m == 1) { if (i == 0) cur = start_room; else if (i == 1) cur = cur % nrooms + 1; else if (i == 2) cur = (cur + nrooms - 2) % nrooms + 1; else if (i == 3) cur = nrooms; else return 'g'; return 0; }
      if (m == 2) { if (i == 0) show_left = !show_left; else if (i == 1) show_right = !show_right; else show_bottom = !show_bottom; return 0; }
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
  timeout(25); c = getch(); timeout(-1);
  if (c == ERR) return 27;                                      /* a lone ESC: the menu bar */
  if (c >= 'a' && c <= 'z') return ALT + c;                      /* Alt-letter, as Duh DRAW returns it */
  if (c == '[' || c == 'O') {                                   /* a CSI / SS3 sequence ncurses did not translate (the terminal's cursor-key mode differs from terminfo) */
    int p[4] = {0}, np = 0, f;
    timeout(25); while ((f = getch()) != ERR && (f == ';' || (f >= '0' && f <= '9'))) { if (f == ';') np++; else if (np < 4) p[np] = p[np] * 10 + (f - '0'); } timeout(-1);
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

int main(int argc, char *argv[])
{
  int c, quit = 0; char *env = getenv("ZORKMAP_DIR");
  setlocale(LC_ALL, ""); load_config(); if (env) snprintf(mapdir, sizeof mapdir, "%s", env);                 /* ZORKMAP_DIR still overrides the maps folder */
  if (argc > 2 && !strcmp(argv[1], "--check")) {                 /* a headless self-test: parse a map file and say what is in it */
    int rc = load_map(argv[2]); if (rc) { fprintf(stderr, "cannot read %s (%d)\n", argv[2], rc); return 1; }
    printf("ok rooms=%d levels=%d canvas=%dx%d start=%d title=%s\n", nrooms, nlev, crows, ccols, start_room, title); return 0;
  }
  initscr(); noecho(); cbreak(); keypad(stdscr, TRUE); curs_set(0); set_escdelay(25); start_color(); use_default_colors();
  if (argc > 1 && load_map(argv[1])) snprintf(status, sizeof status, "Could not read %s", argv[1]);
  else if (argc <= 1 && !nrooms) pick_map();
  while (!quit) {
    draw_all(); refresh(); c = read_key();
    if (getenv("DUHMAP_TRACE")) { FILE *t = fopen(getenv("DUHMAP_TRACE"), "a"); if (t) { fprintf(t, "key %d at room %d\n", c, cur); fclose(t); } }   /* test hook: what key arrived, and where we were */
    switch (c) {
    case KEY_UP: move_to(go_compass("NORTH"), "north"); break;
    case KEY_DOWN: move_to(go_compass("SOUTH"), "south"); break;
    case KEY_LEFT: move_to(go_compass("WEST"), "west"); break;
    case KEY_RIGHT: move_to(go_compass("EAST"), "east"); break;
    case KEY_SR: move_to(go_vertical("UP", 'W'), "up (west)"); break;        /* Shift-Up    UPW */
    case KEY_SF: move_to(go_vertical("UP", 'E'), "up (east)"); break;        /* Shift-Down  UPE */
    case KEY_SLEFT: move_to(go_vertical("DOWN", 'W'), "down (west)"); break; /* Shift-Left  DW  */
    case KEY_SRIGHT: move_to(go_vertical("DOWN", 'E'), "down (east)"); break; /* Shift-Right DE  */
    case 'y': move_to(go_compass("NW"), "northwest"); break; case 'u': move_to(go_compass("NE"), "northeast"); break;
    case 'b': move_to(go_compass("SW"), "southwest"); break; case 'n': move_to(go_compass("SE"), "southeast"); break;
    case '\t': if (nrooms) cur = cur % nrooms + 1; break; case KEY_BTAB: if (nrooms) cur = (cur + nrooms - 2) % nrooms + 1; break;
    case KEY_HOME: cur = start_room; break; case KEY_END: if (nrooms) cur = nrooms; break;
    case KEY_PPAGE: move_to(go_level(1), "up a level"); break; case KEY_NPAGE: move_to(go_level(-1), "down a level"); break;
    case KEY_F(1): case ALT + 'h': show_help = !show_help; break;
    case KEY_F(7): case 'l': layer_view = !layer_view; snprintf(status, sizeof status, layer_view ? "Layer view: only this elevation layer in colour; PgUp / PgDn change layer." : "Layer view off."); break;
    case KEY_F(2): show_left = !show_left; break; case KEY_F(3): show_right = !show_right; break; case KEY_F(4): show_bottom = !show_bottom; break;
    case KEY_F(10): case ALT + 'x': case 'q': quit = 1; break;
    case KEY_F(5): case ALT + 'o': pick_map(); break;
    case KEY_F(6): case ALT + 'm': map_a_game(); break;
    case ALT + 'g': { char b[16]; prompt_line("Go to room number > ", b, sizeof b); if (atoi(b) >= 1 && atoi(b) <= nrooms) cur = atoi(b); } break;
    case 27: { int cmd = menu_bar(); if (cmd == 'x') quit = 1; else if (cmd == 'o') pick_map(); else if (cmd == 'm') map_a_game(); else if (cmd == 'g') { char b[16]; prompt_line("Go to room number > ", b, sizeof b); if (atoi(b) >= 1 && atoi(b) <= nrooms) cur = atoi(b); } } break;
    }
  }
  endwin(); free_map(); return 0;
}
