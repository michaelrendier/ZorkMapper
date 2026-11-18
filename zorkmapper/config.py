# SPDX-License-Identifier: GPL-3.0-only
"""
zorkmapper.config: the shared ~/.zorkmapper config and data directory, used by every version (Python mapper and explorer, the C `zork-map`, the later graphical ones).

    ~/.zorkmapper/config     key = value lines (below)
    ~/.zorkmapper/maps/      NAME.zmap, NAME.map.json, NAME.txt, NAME.ans   (what the explorers open)
    ~/.zorkmapper/images/    NAME.svg, NAME.png, and later the generated room pictures
    ~/.zorkmapper/sources/   fetched ZIL source (zork1 ...)
Override the root with the environment variable ZORKMAPPER_DIR.
"""
import glob
import os
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULTS = {"maps_dir": "~/.zorkmapper/maps", "images_dir": "~/.zorkmapper/images", "sources_dir": "~/.zorkmapper/sources", "mapper_home": REPO,
            "panel_left": "16", "panel_right": "30", "panel_bottom": "22"}


def root() -> str:
    return os.path.expanduser(os.environ.get("ZORKMAPPER_DIR") or "~/.zorkmapper")


def _expand(v: str, r: str) -> str:
    return os.path.join(r, v[len("~/.zorkmapper/"):]) if v.startswith("~/.zorkmapper/") else os.path.expanduser(v)


def load() -> dict:
    r = root(); cfg = dict(DEFAULTS); path = os.path.join(r, "config")
    if os.path.exists(path):
        for line in open(path):
            line = line.split("#", 1)[0].strip()
            if "=" in line: k, v = line.split("=", 1); cfg[k.strip()] = v.strip()
    for k in ("maps_dir", "images_dir", "sources_dir", "mapper_home"): cfg[k] = _expand(cfg[k], r)
    return cfg


def ensure() -> dict:
    """create the directories and a default config if missing; returns the loaded config"""
    r = root(); os.makedirs(r, exist_ok=True); path = os.path.join(r, "config")
    if not os.path.exists(path):
        with open(path, "w") as fh:
            fh.write("# ZorkMapper config, shared by every version (Python, C zork-map, graphical). key = value; ~/.zorkmapper/ is the root.\n")
            for k, v in DEFAULTS.items(): fh.write("%s = %s\n" % (k, v))
    cfg = load()
    for k in ("maps_dir", "images_dir", "sources_dir"): os.makedirs(cfg[k], exist_ok=True)
    return cfg


def seed(cfg: dict = None, force: bool = False) -> list:
    """copy the example maps and images shipped in the repo (ASCIIArt/, images/) into the data directory, without overwriting anything"""
    cfg = cfg or ensure(); copied = []
    for pat, dst in ((os.path.join(REPO, "ASCIIArt", "*.*"), cfg["maps_dir"]), (os.path.join(REPO, "images", "*.*"), cfg["images_dir"])):
        for f in glob.glob(pat):
            t = os.path.join(dst, os.path.basename(f))
            if force or not os.path.exists(t): shutil.copy2(f, t); copied.append(t)
    return copied
