"""Evals for batch analog cell-netlist generation."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cell_generators import GENERATORS, to_subckt
from sim import HAVE_BSIMCMG, HAVE_NGSPICE

pytestmark = pytest.mark.skipif(not HAVE_NGSPICE, reason="ngspice not installed")
needs_cmg = pytest.mark.skipif(not HAVE_BSIMCMG, reason="BSIM-CMG OSDI not built")


def test_all_cells_generate_valid_subckt():
    assert len(GENERATORS) >= 11
    for c in GENERATORS:
        s = to_subckt(c)
        assert s.startswith("* " + c) and ".subckt" in s and ".ends" in s


@needs_cmg
@pytest.mark.parametrize("cell", list(GENERATORS))
def test_every_generated_netlist_simulates(cell):
    from generate_cells_batch import op_check
    assert op_check(cell)["live"] is True
