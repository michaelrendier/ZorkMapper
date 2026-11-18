"""~/.zorkmapper: the shared config and data directory (tested in a temporary root)."""
import os
from zorkmapper import config


def test_ensure_creates_the_directories_and_default_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ZORKMAPPER_DIR", str(tmp_path / "zm"))
    cfg = config.ensure()
    assert os.path.isdir(cfg["maps_dir"]) and os.path.isdir(cfg["images_dir"]) and os.path.isdir(cfg["sources_dir"])
    assert cfg["maps_dir"] == str(tmp_path / "zm" / "maps") and cfg["panel_left"] == "16"
    assert os.path.exists(tmp_path / "zm" / "config")


def test_config_file_overrides_and_comments(tmp_path, monkeypatch):
    root = tmp_path / "zm"; root.mkdir(); monkeypatch.setenv("ZORKMAPPER_DIR", str(root))
    (root / "config").write_text("# comment\npanel_right = 20   # trailing\nmaps_dir = %s\n" % (tmp_path / "elsewhere"))
    cfg = config.load(); assert cfg["panel_right"] == "20" and cfg["maps_dir"] == str(tmp_path / "elsewhere")


def test_seed_copies_examples_without_overwriting(tmp_path, monkeypatch):
    monkeypatch.setenv("ZORKMAPPER_DIR", str(tmp_path / "zm")); cfg = config.ensure()
    first = config.seed(cfg); assert any(f.endswith("zork1.zmap") for f in first)
    target = os.path.join(cfg["maps_dir"], "zork1.zmap"); open(target, "w").write("mine")
    assert config.seed(cfg) == [] and open(target).read() == "mine"
