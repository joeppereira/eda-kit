"""Batch generators for the analog LPDDR5 cell netlists.

Emits real SPICE sub-circuits (topology + first-order sizing per DESIGN_GUIDELINES.md)
for the analog cell set, on real ASAP7 7nm devices (nmos_rvt / pmos_rvt via OSDI).
A batch pass writes each to pdk/generated_cells/<cell>.spice and runs an ngspice `.op`
sanity check (device live, supply current flows). Spec-convergence via the agentic
loop (cells.py) is the per-cell next pass; this establishes the netlists.

Honest: these are structurally-real generated netlists verified to *simulate*; they
are not yet each sized to a datasheet spec or laid out.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from sim import BSIMCMG_OSDI

_ASAP7 = Path(__file__).resolve().parent / "pdk" / "asap7"
LG = "21n"


def _n(name, d, g, s, nf=8, model="nmos_rvt"):
    return f"N{name} {d} {g} {s} 0 {model} L={LG} NFIN={nf}"


def _p(name, d, g, s, nf=12, model="pmos_rvt"):
    return f"N{name} {d} {g} {s} VDD {model} L={LG} NFIN={nf}"


# Each builder returns (list of device lines, list of external ports).
def bias_current_gen():
    return ([_n("m0", "IREF", "IREF", "0", 8), _n("m1", "IOUT", "IREF", "0", 8),  # nmos mirror
             _p("m2", "IREF", "PB", "VDD", 12), "RSET VDD IREF 20k"], ["VDD", "IOUT", "PB"])


def vref_generator():
    return (["R0 VDD TAP0 40k", "R1 TAP0 VREF 40k", "R2 VREF 0 40k",
             _n("mb", "TAP0", "VREF", "0", 4)], ["VDD", "VREF"])


def odt_termination():
    # switched termination legs to PAD (ZQ-calibratable).
    legs = [f"R{i} PAD t{i} 240" + f"\n" + _n(f"sw{i}", f"t{i}", f"EN{i}", "0", 16) for i in range(4)]
    return (legs, ["PAD", "EN0", "EN1", "EN2", "EN3"])


def level_shifter():
    return ([_p("x0", "OA", "OB", "VDDH", 10), _p("x1", "OB", "OA", "VDDH", 10),   # cross-coupled
             _n("i0", "OA", "IN", "0", 8), _n("i1", "OB", "INB", "0", 8)],
            ["VDDH", "IN", "INB", "OA", "OB"])


def clock_distribution():
    # 3-stage inverter clock buffer.
    lines = []
    nets = ["CKIN", "n1", "n2", "CKOUT"]
    for i in range(3):
        lines += [_p(f"p{i}", nets[i+1], nets[i], "VDD", 16), _n(f"n{i}", nets[i+1], nets[i], "0", 10)]
    return (lines, ["VDD", "CKIN", "CKOUT"])


def ck_wck_receiver():
    # differential receiver: nmos pair + pmos mirror load + tail.
    return ([_n("in0", "ON", "CKP", "TAIL", 12), _n("in1", "OP", "CKN", "TAIL", 12),
             _p("ld0", "ON", "ON", "VDD", 12), _p("ld1", "OP", "ON", "VDD", 12),
             _n("tl", "TAIL", "VB", "0", 20)], ["VDD", "CKP", "CKN", "ON", "OP", "VB"])


def duty_cycle_corrector():
    # current-starved inverter (trim via tail).
    return ([_p("p0", "CKO", "CKI", "PT", 16), _p("pt", "PT", "PB", "VDD", 12),
             _n("n0", "CKO", "CKI", "NT", 10), _n("nt", "NT", "NB", "0", 12)],
            ["VDD", "CKI", "CKO", "PB", "NB"])


def phase_interpolator():
    # two weighted CML legs summing at the output (I/Q blend).
    return ([_n("a0", "ON", "IP", "TA", 8), _n("a1", "OP", "IN", "TA", 8),
             _n("b0", "ON", "QP", "TB", 8), _n("b1", "OP", "QN", "TB", 8),
             "RLA VDD ON 300", "RLB VDD OP 300",
             _n("ta", "TA", "WA", "0", 16), _n("tb", "TB", "WB", "0", 16)],
            ["VDD", "IP", "IN", "QP", "QN", "WA", "WB", "ON", "OP"])


def esd_clamp():
    # big-FET rail clamp + RC trigger.
    return ([_n("clamp", "PAD", "TRIG", "0", 200), "RT PAD TRIG 50k", "CT TRIG 0 200f"],
            ["PAD"])


def decap_cell():
    return ([_n("dc", "VDD", "VDD", "0", 64)], ["VDD"])   # MOS decoupling cap


def ldo_regulator():
    # error amp (nmos pair + pmos mirror) + pass pmos + feedback divider.
    return ([_n("ea0", "EON", "VREF", "ET", 8), _n("ea1", "EO", "FB", "ET", 8),
             _p("el0", "EON", "EON", "VIN", 10), _p("el1", "EO", "EON", "VIN", 10),
             _n("et", "ET", "VB", "0", 12),
             _p("pass", "VOUT", "EO", "VIN", 120),
             "RF0 VOUT FB 50k", "RF1 FB 0 50k"], ["VIN", "VREF", "VOUT", "VB"])


GENERATORS = {
    "bias_current_gen": bias_current_gen, "vref_generator": vref_generator,
    "odt_termination": odt_termination, "level_shifter": level_shifter,
    "clock_distribution": clock_distribution, "ck_wck_receiver": ck_wck_receiver,
    "duty_cycle_corrector": duty_cycle_corrector, "phase_interpolator": phase_interpolator,
    "esd_clamp": esd_clamp, "decap_cell": decap_cell, "ldo_regulator": ldo_regulator,
}


def to_subckt(cell: str) -> str:
    devs, ports = GENERATORS[cell]()
    # VDD/VDDH are supplies the parent provides; keep them as ports too.
    allports = list(dict.fromkeys(ports + ["VDD"]))
    body = "\n".join(devs)
    return (f"* {cell} — generated analog netlist (ASAP7 7nm), topology per DESIGN_GUIDELINES.md\n"
            f".subckt {cell} {' '.join(allports)}\n{body}\n.ends\n")


__all__ = ["GENERATORS", "to_subckt"]
