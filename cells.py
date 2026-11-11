"""Measurement primitives for high-speed cells (real ngspice + ASAP7/BSIM-CMG).

Each function builds a real testbench and returns **measured** quantities — the open
primitives that a design loop sizes against. The agentic sizing loops themselves
(design_tx / design_rx / design_cp / design_lvstl_leg / migrate) are Project-4
proprietary and live in the private node-migration repo, not here.

  * measure_tx   — current-mode TX swing into 50 Ω.
  * measure_ron  — LVSTL pull-down / ODT leg on-resistance (linear region) → RZQ sizing.
  * measure_cp   — PLL charge-pump up/down currents + compliance (pmos+nmos, ASAP7).
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pdk_nodes import get_node
from sim import HAVE_NGSPICE, _cols, _node_card, _run, BSIMCMG_OSDI
from specs import JESD209_5


# --------------------------- reference specs (public) ---------------------------
TX_SPEC = {"name": "tx_driver",
           "swing_mV": {"min": 160.0},        # single-ended into 50 Ω
           "power_uW": {"max": 4000.0}}
RX_SPEC = {"name": "rx_preamp",
           "gain_dB": {"min": 12.0, "target": 14.0},   # higher gain than a buffer
           "bw_hz": {"min": 2.0e9},
           "power_uW": {"max": 600.0}}
CP_SPEC = {"name": "pll_chargepump",
           "icp_uA": {"target": 30.0, "tol": 10.0},   # up/down current
           "match_pct": {"max": 10.0},                 # |Iup−Idn| at mid-rail
           "compliance_V": {"min": 0.30}}              # output swing where both stay in sat

_ASAP7 = Path(__file__).resolve().parent / "pdk" / "asap7"


# --------------------------- TX driver ---------------------------
@dataclass
class TxDesign:
    n_units: int = 32
    itail_ua: float = 3600.0        # sets swing = Itail · R
    rload_ohm: float = 50.0         # controlled-impedance load


def measure_tx(design: TxDesign, node: str) -> dict:
    """Current-mode TX: full-swing gate drive steers I_tail into 50 Ω; measure swing."""
    if not HAVE_NGSPICE:
        raise RuntimeError("ngspice not found — run setup.sh.")
    p = get_node(node); vdd = p["vdd"]
    card, mname = _node_card(node)
    dc = os.path.join(tempfile.mkdtemp(), "dc.data")
    tb = f""".title tx_driver {node}
N0 O_N IN_P TAIL 0 {mname} L={p['lg']} NFIN={design.n_units}
N1 O_P IN_N TAIL 0 {mname} L={p['lg']} NFIN={design.n_units}
RL0 VDD O_N {design.rload_ohm}
RL1 VDD O_P {design.rload_ohm}
Itail TAIL 0 {design.itail_ua}u
VDD VDD 0 {vdd}
VCM cm 0 {vdd*0.5:.4f}
EINP IN_P cm d 0 {vdd:.3f}
EINN IN_N cm d 0 -{vdd:.3f}
Vd d 0 DC 0
.control
pre_osdi {BSIMCMG_OSDI}
dc Vd -1 1 0.05
wrdata {dc} v(o_n)
.endc
.include {card}
.end
"""
    _run(tb)
    v = [b for _, b in _cols(dc)]
    swing = round((max(v) - min(v)) * 1000, 1) if v else None
    return {"node": node, "swing_mV": swing, "power_uW": round(vdd * design.itail_ua, 1),
            "ideal_swing_mV": round(design.itail_ua * 1e-6 * design.rload_ohm * 1e3, 1),
            "model": f"BSIM-CMG ({card.parent.name})"}


# --------------------------- LVSTL driver / ODT leg (JEDEC RON) ---------------------------
@dataclass
class LegDesign:
    n_units: int = 24               # fins in the unit (RZQ) pull-down leg
    vds_lin_mv: float = 50.0        # small Vds for a linear-region RON measurement


def measure_ron(design: LegDesign, node: str, vddq: float | None = None) -> dict:
    """Linear-region on-resistance of the pull-down leg: gate at VDDQ, small Vds,
    RON = Vds / Id. More fins → lower RON (∝ 1/NFIN). Sized to RZQ by the private loop."""
    if not HAVE_NGSPICE:
        raise RuntimeError("ngspice not found — run setup.sh.")
    p = get_node(node)
    vddq = vddq if vddq is not None else JESD209_5["vddq_v"]
    card, mname = _node_card(node)
    vds = design.vds_lin_mv * 1e-3
    out = os.path.join(tempfile.mkdtemp(), "ron.data")
    tb = f""".title lvstl_ron {node}
N0 D G 0 0 {mname} L={p['lg']} NFIN={design.n_units}
VG G 0 {vddq}
VD D 0 {vds}
.control
pre_osdi {BSIMCMG_OSDI}
op
let ron = {vds} / abs(i(VD))
wrdata {out} ron
.endc
.include {card}
.end
"""
    _run(tb)
    rows = _cols(out)
    ron = round(rows[0][1], 2) if rows else None
    return {"node": node, "vddq": vddq, "n_units": design.n_units, "ron_ohm": ron,
            "model": f"BSIM-CMG ({card.parent.name})"}


# --------------------------- PLL charge pump (pmos+nmos, ASAP7) ---------------------------
def measure_cp(n_units: int, node: str = "7nm", up_ratio: float = 1.0) -> dict:
    """Characterize a charge pump: pmos source leg + nmos sink leg vs output voltage.

    ``up_ratio`` sizes the pmos (source) leg relative to the nmos (sink) leg to balance
    the up/down currents. Needs a pmos card → ASAP7 (7nm) today. Returns Icp, mid-rail
    current match, and the compliance range."""
    if not HAVE_NGSPICE:
        raise RuntimeError("ngspice not found.")
    p = get_node(node); vdd = p["vdd"]
    n_up = max(2, round(n_units * up_ratio))
    nc, pc = _ASAP7 / "asap7_nmos_rvt.card", _ASAP7 / "asap7_pmos_rvt.card"
    d = tempfile.mkdtemp(); up = os.path.join(d, "up"); dn = os.path.join(d, "dn")

    def leg(kind):
        out = up if kind == "up" else dn
        if kind == "up":   # pmos sources from vdd into OUT; Vsg=0.3
            dev = f"Nup OUT G vdd vdd pmos_rvt L={p['lg']} NFIN={n_up}\nVG G 0 {vdd-0.30:.3f}"
        else:              # nmos sinks OUT to gnd; Vgs=0.3
            dev = f"Ndn OUT G 0 0 nmos_rvt L={p['lg']} NFIN={n_units}\nVG G 0 0.30"
        tb = (f".title cp {kind}\nVdd vdd 0 {vdd}\n{dev}\nVout OUT 0 0\n"
              f".include {nc}\n.include {pc}\n.control\npre_osdi {BSIMCMG_OSDI}\n"
              f"dc Vout 0 {vdd} 0.02\nlet ia=abs(i(Vout))\nwrdata {out} ia\n.endc\n.end\n")
        _run(tb)
        return _cols(out)

    u, dd = leg("up"), leg("dn")
    def at(curve, v): return min(curve, key=lambda t: abs(t[0] - v))[1] if curve else 0.0
    mid = vdd / 2
    iup, idn = at(u, mid) * 1e6, at(dd, mid) * 1e6
    icp = (iup + idn) / 2
    match = abs(iup - idn) / icp * 100 if icp else 999
    comp = [v for v, _ in u if at(u, v) >= 0.9 * at(u, mid) and at(dd, v) >= 0.9 * at(dd, mid)]
    compliance = round(max(comp) - min(comp), 3) if comp else 0.0
    return {"node": node, "icp_uA": round(icp, 2), "iup_uA": round(iup, 2),
            "idn_uA": round(idn, 2), "match_pct": round(match, 2),
            "compliance_V": compliance, "up_ratio": round(up_ratio, 3),
            "model": "BSIM-CMG (ASAP7 n+p)"}


__all__ = ["TxDesign", "LegDesign", "measure_tx", "measure_ron", "measure_cp",
           "TX_SPEC", "RX_SPEC", "CP_SPEC"]
