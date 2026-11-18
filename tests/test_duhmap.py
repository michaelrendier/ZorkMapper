"""duhmap (the C explorer): it builds and parses the generated maps."""
import os
import shutil
import subprocess
import pytest

D = os.path.join(os.path.dirname(__file__), "..", "duhmap")
MAP = os.path.join(os.path.dirname(__file__), "..", "ASCIIArt", "zork1.zmap")
pytestmark = pytest.mark.skipif(not shutil.which("gcc") or not os.path.exists(MAP), reason="needs gcc and ASCIIArt/zork1.zmap")


def test_duhmap_builds_and_reads_every_map():
    subprocess.run(["make", "-C", D], check=True, capture_output=True)
    for g, rooms in (("zork1", 91), ("zork2", 77), ("zork3", 88)):
        out = subprocess.run([os.path.join(D, "duhmap"), "--check", os.path.join(D, "..", "ASCIIArt", g + ".zmap")], capture_output=True, text=True, check=True).stdout
        assert out.startswith("ok rooms=%d " % rooms)
