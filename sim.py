"""Real ngspice simulation harness (BSIM-CMG via OSDI) — reusable.

Runs real DC/AC on a cell and returns measured quantities (not fixtures). Uses the
BSIM-CMG multi-gate model via OSDI when available; falls back to a BSIM4 node card.

Toolchain paths resolve from env vars (set by setup.sh) or default to ``./.tools``:
  EDA_KIT_TOOLS   base dir holding bsimcmg/ (default: <kit>/.tools)
  BSIMCMG_OSDI    path to compiled bsimcmg.osdi
  BSIMCMG_NMOS    path to the nmos modelcard
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pdk_nodes import model_card, get_node, width_for_units
from profiles import get_segment

HAVE_NGSPICE = shutil.which("ngspice") is not None

_TOOLS = Path(os.environ.get("EDA_KIT_TOOLS", Path(__file__).resolve().parent / ".tools")) / "bsimcmg"
BSIMCMG_OSDI = Path(os.environ.get("BSIMCMG_OSDI", _TOOLS / "vacode111" / "bsimcmg.osdi"))
BSIMCMG_NMOS = Path(os.environ.get("BSIMCMG_NMOS", _TOOLS / "examples" / "modelcard.nmos"))
HAVE_BSIMCMG = HAVE_NGSPICE and BSIMCMG_OSDI.is_file() and BSIMCMG_NMOS.is_file()

# Per-node model cards: real ASAP7 for the 7nm FinFET node, the calibrated predictive
# card for N2, else the generic BSIM-MG sample card. (card_path, nmos_model_name).
_PDK = Path(__file__).resolve().parent / "pdk"
# Predictive calibrated cards per FinFET/GAA node (7nm = real ASAP7, handled below).
NODE_MODEL: dict[str, tuple[Path, str]] = {
    "n2_predictive": (_PDK / "n2_predictive" / "modelcard.n2.nmos", "nmos"),
    "2nm": (_PDK / "n2_predictive" / "modelcard.n2.nmos", "nmos"),
}
for _n in ("16nm", "14nm", "10nm", "5nm", "4nm", "3nm"):
    NODE_MODEL[_n] = (_PDK / f"{_n}_predictive" / f"modelcard.{_n}.nmos", "nmos")

# Planar bulk nodes → calibrated BSIM4 cards (native ngspice, not OSDI).
PLANAR_MODEL: dict[str, tuple[Path, str]] = {
    n: (_PDK / f"{n}_planar" / f"modelcard.{n}.nmos", "nmos_bulk") for n in ("40nm", "28nm")
}


def _node_card(node: str, vt: str = "rvt") -> tuple[Path, str]:
    """Return (card, nmos_model_name). ASAP7 7nm and GT2N 2nm support Vt flavors."""
    if node == "7nm":
        card = _PDK / "asap7" / f"asap7_nmos_{vt}.card"
        if card.is_file():
            return card, f"nmos_{vt}"
    if node in ("2nm", "gt2n"):
        # Real published 2nm GAA-nanosheet card (GT2N) when built; else fall through to
        # the hand-calibrated N2 card below. GT2N Vt flavors: rvt/lvt/slvt (see build_gt2n.py).
        card = _PDK / "gt2n" / f"gt2n_nmos_{vt}.card"
        if not card.is_file():
            card = _PDK / "gt2n" / "gt2n_nmos_rvt.card"
        if card.is_file():
            return card, "nmos"
    card, name = NODE_MODEL.get(node, (BSIMCMG_NMOS, "nmos"))
    return (card if Path(card).is_file() else BSIMCMG_NMOS,
            name if Path(card).is_file() else "nmos")


@dataclass
class CmlDesign:
    """A CML buffer point. ``n_units`` = fins (FinFET) or nanosheet stacks (GAA)."""
    n_units: int = 16
    rload_ohm: float = 3000.0
    cl_ff: float = 20.0


def _run(tb: str) -> str:
    d = tempfile.mkdtemp()
    cir = os.path.join(d, "tb.cir")
    Path(cir).write_text(tb)
    return subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True, timeout=90).stdout


def _cols(path):
    rows = []
    if os.path.exists(path):
        for line in open(path):
            p = line.split()
            if len(p) >= 2:
                try:
                    rows.append((float(p[0]), float(p[1])))
                except ValueError:
                    pass
    return rows


def measure_cml(design: CmlDesign, node: str, segment: str | None = None,
                vdd: float | None = None, temp_c: float | None = None) -> dict:
    """Simulate a CML buffer on (node, segment); return measured gain / BW / power.

    ``segment`` (compute/mobile/low_power/automotive/industrial) sets Vt flavor,
    temperature, and Vdd scale — the second migration axis (see profiles.py).
    ``vdd`` / ``temp_c`` override the operating point (e.g. a per-market DVFS state).
    """
    if not HAVE_NGSPICE:
        raise RuntimeError("ngspice not found on PATH — run setup.sh.")
    p = get_node(node)
    seg = get_segment(segment)
    vdd = round(vdd if vdd is not None else p["vdd"] * seg["vdd_scale"], 4)
    temp = temp_c if temp_c is not None else seg["temp_c"]
    R = design.rload_ohm
    itail_a = vdd / R                                 # bias for mid-rail output
    acfile = os.path.join(tempfile.mkdtemp(), "ac.data")

    planar = p["arch"] == "planar"
    if planar or not HAVE_BSIMCMG:
        # Planar bulk → BSIM4. The .model goes in the NETLIST (not .control).
        W = width_for_units(node, design.n_units)
        pc = PLANAR_MODEL.get(node)
        if planar and pc and pc[0].is_file():
            mname, netdef, tag = pc[1], f".include {pc[0]}", f"BSIM4 planar ({node})"
        else:
            mname, netdef, tag = "nmos_ff", model_card(node) + "\n", f"BSIM4 ({p['arch']})"
        devices = (f"M0 O_N IN_P TAIL 0 {mname} L={p['lg']} W={W}u\n"
                   f"M1 O_P IN_N TAIL 0 {mname} L={p['lg']} W={W}u")
        ctrl = ""
    else:
        card, mname = _node_card(node, seg["vt"])
        devices = (f"N0 O_N IN_P TAIL 0 {mname} L={p['lg']} NFIN={design.n_units}\n"
                   f"N1 O_P IN_N TAIL 0 {mname} L={p['lg']} NFIN={design.n_units}")
        ctrl, netdef = f"pre_osdi {BSIMCMG_OSDI}", f".include {card}"
        src = ("ASAP7" if card.parent.name == "asap7" else "GT2N" if card.parent.name == "gt2n"
               else "N2-pred" if "n2" in card.name
               else "pred" if "predictive" in str(card) else "sample")
        tag = f"BSIM-CMG ({src}/{seg['vt']})"

    tb = f""".title cml_buffer {node} {segment or 'nominal'}
.options temp={temp}
{devices}
RL0 VDD O_N {R}
RL1 VDD O_P {R}
CL0 O_N 0 {design.cl_ff}f
CL1 O_P 0 {design.cl_ff}f
Itail TAIL 0 {itail_a}
VDD VDD 0 {vdd}
VCM cm 0 {vdd*0.5:.4f}
EINP IN_P cm d 0 0.5
EINN IN_N cm d 0 -0.5
Vd d 0 DC 0 AC 1
{netdef}
.control
{ctrl}
ac dec 20 1e6 1e12
let gmag = db(v(o_p)-v(o_n))
wrdata {acfile} gmag
.endc
.end
"""
    _run(tb)
    ac = _cols(acfile)
    gain_db = round(ac[0][1], 2) if ac else None
    bw_hz = next((f for f, g in ac if g <= ac[0][1] - 3), None) if ac else None
    return {
        "node": node, "arch": p["arch"], "segment": segment or "nominal",
        "vt": seg["vt"], "temp_c": temp, "n_units": design.n_units,
        "rload_ohm": round(R, 1), "gain_dB": gain_db, "bw_hz": bw_hz,
        "power_uW": round(vdd * itail_a * 1e6, 1), "model": tag,
        "measured_by": "ngspice (real)",
    }


__all__ = ["HAVE_NGSPICE", "HAVE_BSIMCMG", "CmlDesign", "measure_cml"]
