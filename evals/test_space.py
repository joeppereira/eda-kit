"""Evals for the node × segment space primitives (real BSIM-CMG). Skipped w/o toolchain.

Convergence across the full space and 2-D (node × segment) migration are driven by the
agentic loop and tested in the private node-migration repo; here we test the public
primitives: the space is registered, and measurement responds to the segment corner.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim import HAVE_BSIMCMG, HAVE_NGSPICE, CmlDesign, measure_cml
from pdk_nodes import NODES, arch

pytestmark = pytest.mark.skipif(not HAVE_NGSPICE, reason="ngspice not installed")
needs_cmg = pytest.mark.skipif(not HAVE_BSIMCMG, reason="BSIM-CMG OSDI not built")


def test_full_geometry_space_registered():
    # planar → FinFET → GAA all present.
    assert arch("40nm") == "planar" and arch("7nm") == "finfet" and arch("2nm") == "gaa"
    assert {"16nm", "10nm", "7nm", "4nm", "3nm", "2nm"} <= set(NODES)


@needs_cmg
def test_segment_temperature_effect():
    d = CmlDesign(n_units=24, rload_ohm=3000)
    hot = measure_cml(d, "7nm", "automotive")   # 150C
    cool = measure_cml(d, "7nm", "compute")     # 25C, SLVT
    assert hot["temp_c"] == 150 and cool["temp_c"] == 25
    assert cool["gain_dB"] > hot["gain_dB"]      # gain drops at high temperature
