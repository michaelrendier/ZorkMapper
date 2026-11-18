#!/usr/bin/env bash
# Fetch the Infocom ZIL sources (MIT licence, Microsoft 2025) into sources/.  Every request carries a Mozilla user agent.
set -e; cd "$(dirname "$0")"; mkdir -p sources; cd sources
UA="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
for g in zork1 zork2 zork3; do [ -d "$g" ] || git -c http.userAgent="$UA" clone --depth 1 "https://github.com/historicalsource/$g.git" "$g"; done
