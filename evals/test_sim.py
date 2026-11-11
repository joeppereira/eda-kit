"""Portable evals for eda-kit. Skipped cleanly when the toolchain is absent."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdk_nodes import ORDER, arch, width_for_units  # noqa: E402
from sim import HAVE_BSIMCMG, HAVE_NGSPICE, CmlDesign, measure_cml  # noqa: E402

pytestmark = pytest.mark.skipif(not HAVE_NGSPICE, reason="ngspice not installed")
needs_cmg = pytest.mark.skipif(not HAVE_BSIMCMG, reason="BSIM-CMG OSDI not built (run setup.sh)")


def test_node_family_architecture():
    # Full space: planar → FinFET → GAA.
    assert arch("40nm") == "planar" and arch("7nm") == "finfet" and arch("2nm") == "gaa"
    assert all(n in ORDER for n in ("40nm", "16nm", "7nm", "4nm", "2nm"))


def test_width_quantization():
    assert width_for_units("7nm", 10) == 0.30
    assert width_for_units("2nm", 10) == 0.75


def test_specs_trace_to_jesd209_5():
    """Clock-buffer BW target is derived from the JESD209-5 WCK, not a round number."""
    from specs import clock_buffer_spec, wck_freq_hz, driver_spec, JESD209_5
    s = clock_buffer_spec(6400)
    assert "JESD209-5" in s["traces_to"]
    assert s["bw_hz"]["min"] == round(1.4 * wck_freq_hz(6400), -6)   # 1.4 x 3.2 GHz
    assert clock_buffer_spec(8533)["bw_hz"]["min"] > s["bw_hz"]["min"]  # 5X scales up
    assert driver_spec()["odt_ohm"][0] == JESD209_5["rzq_ohm"]         # RZQ/1 = 240Ω


def test_real_measurement():
    m = measure_cml(CmlDesign(), "7nm")
    assert isinstance(m["gain_dB"], float) and m["power_uW"] > 0


def test_gt2n_card_drives_2nm_node():
    """The 2nm node runs on the real published GT2N GAA card (not hand-calibrated N2),
    with physically-correct multi-Vt: lower-Vt flavors carry a more-negative dvtshift
    (= lower Vt = higher drive). This is the signature the HSPICE->OSDI sign fix restores.
    """
    import re
    from pathlib import Path
    gt = Path(__file__).resolve().parents[1] / "pdk" / "gt2n"

    def dvtshift(vt: str) -> float:
        txt = (gt / f"gt2n_nmos_{vt}.card").read_text()
        return float(re.search(r"dvtshift\s*=\s*(\S+)", txt).group(1))

    assert (gt / "gt2n_nmos_rvt.card").is_file()
    # slvt (lowest Vt) most negative; rvt (highest Vt) least negative.
    assert dvtshift("slvt") < dvtshift("lvt") < dvtshift("rvt") <= 0


@needs_cmg
def test_gt2n_measures_live_at_2nm():
    """2nm/GT2N measures live (the agentic convergence test lives in node-migration)."""
    m = measure_cml(CmlDesign(n_units=16), "2nm", segment="compute")
    assert "GT2N" in m["model"] and isinstance(m["gain_dB"], float)
