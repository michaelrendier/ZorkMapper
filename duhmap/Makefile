# duhmap / zork-map: derived from Duh DRAW; GPL v2 (see LICENSE).  Maps and settings come from ~/.zorkmapper at run time.
CC=gcc -O2 -Wall
PREFIX=/usr
duhmap: duhmap.c
	$(CC) -o duhmap duhmap.c -lncursesw
install: duhmap
	install -m 0755 duhmap $(DESTDIR)$(PREFIX)/bin/zork-map
uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/zork-map
clean:
	rm -f duhmap
