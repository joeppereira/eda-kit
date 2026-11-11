"""Eval for real GDS layout generation. Skipped if gdstk is absent."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

gdstk = pytest.importorskip("gdstk")
from layout import generate_diffpair_gds  # noqa: E402


def test_generates_real_readable_gds(tmp_path):
    s = generate_diffpair_gds(nfin=16, node="7nm", out_dir=str(tmp_path))
    assert Path(s.gds_path).is_file() and s.area_um2 > 0
    # It is real GDS: reads back with geometry on multiple layers.
    lib = gdstk.read_gds(s.gds_path)
    cell = lib.cells[0]
    assert len(cell.polygons) > 10
    layers = {p.layer for p in cell.polygons}
    assert {1, 2}.issubset(layers)      # active + poly present


def test_generated_layout_passes_real_drc(tmp_path):
    pytest.importorskip("klayout.db")
    from drc import run_drc
    s = generate_diffpair_gds(nfin=16, node="7nm", out_dir=str(tmp_path))
    r = run_drc(s.gds_path)
    assert r["clean"] is True and r["total_violations"] == 0


def test_layout_passes_structural_lvs(tmp_path):
    pytest.importorskip("klayout.db")
    from lvs import run_lvs
    s = generate_diffpair_gds(nfin=16, node="7nm", out_dir=str(tmp_path))
    r = run_lvs(s.gds_path, s.device_map, expected_transistors=6)
    assert r["clean"] is True and r["common_centroid_preserved"] is True


def test_cap_array_drc_lvs_clean(tmp_path):
    pytest.importorskip("klayout.db")
    from layout import generate_cap_array_gds
    from drc import run_drc
    from lvs import run_lvs
    s = generate_cap_array_gds(4, "7nm", out_dir=str(tmp_path))
    assert run_drc(s.gds_path)["clean"] is True
    assert run_lvs(s.gds_path, s.device_map, expected_transistors=4)["common_centroid_preserved"]
