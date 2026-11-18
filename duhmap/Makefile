# duhmap / zork-map: derived from Duh DRAW; GPL v2 (see LICENSE)
CC=gcc -O2 -Wall
ROOT=$(abspath ..)
PREFIX=/usr
duhmap: duhmap.c
	$(CC) -DMAPDIR='"$(ROOT)/ASCIIArt"' -DHOME_DIR='"$(ROOT)"' -o duhmap duhmap.c -lncursesw
install: duhmap
	install -m 0755 duhmap $(DESTDIR)$(PREFIX)/bin/zork-map
uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/zork-map
clean:
	rm -f duhmap
