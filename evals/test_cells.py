"""Evals for the public measurement primitives (real ASAP7 BSIM-CMG).

The agentic cell-design loops (design_tx / design_rx / design_cp / design_lvstl_leg)
are Project-4 proprietary and tested in the private node-migration repo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim import HAVE_BSIMCMG, HAVE_NGSPICE, _node_card  # noqa: E402
from cells import measure_ron, LegDesign  # noqa: E402

pytestmark = pytest.mark.skipif(not HAVE_NGSPICE, reason="ngspice not installed")
needs_cmg = pytest.mark.skipif(not HAVE_BSIMCMG, reason="BSIM-CMG OSDI not built")


@needs_cmg
def test_7nm_uses_real_asap7_card():
    card, model = _node_card("7nm")
    assert card.parent.name == "asap7" and model == "nmos_rvt"


@needs_cmg
def test_measure_ron_primitive_returns_resistance():
    m = measure_ron(LegDesign(n_units=24), "7nm")
    assert isinstance(m["ron_ohm"], float) and m["ron_ohm"] > 0
