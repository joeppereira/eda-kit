"""Architecture-aware predictive node family: FinFET (7–3nm) → GAA (2nm) → [N2/A14].

Reusable across projects. These are **predictive / artificial** nodes expressed as
BSIM4 (fallback) or BSIM-CMG (real, via OSDI) approximations — NOT foundry PDKs.
Public reference points: ASAP7 (predictive 7nm FinFET), ASAP5 (restricted). Real
foundry/IMEC decks (e.g. N2, A14) are NDA-gated and must never be cloned here; add
predictive equivalents only from PUBLIC roadmap data (IRDS, IEDM/VLSI papers).

Device width is quantized by the device *unit*, which changes with architecture:
  * FinFET: unit = fin;            W_eff = n_units · weff_per_unit
  * GAA/nanosheet: unit = stack;   one unit contributes more width per footprint
  * CFET (A14-class): approximate as stacked GAA devices (no open compact model yet)

Designs are expressed in device units (n_units), so the same intent migrates across
architecture boundaries — "migrate design intent, not geometry" applied to cells.

To add a predictive N2/A14 node: copy an entry, set arch/vdd/lg/weff_per_unit from
public targets, and calibrate the BSIM-CMG params against published Ion/Ioff/SS.
"""

from __future__ import annotations

def _fin(vdd, lg, weff=0.028):
    return dict(arch="finfet", unit="fin", vdd=vdd, lg=lg, weff_per_unit=weff,
                vth_n=0.20, vth_p=-0.22, u0_n=0.040, u0_p=0.011, toxe="1.2n")


# Full geometry space: planar(BSIM4) → FinFET(BSIM-CMG) → GAA(BSIM-CMG) → CFET(future).
NODES: dict[str, dict] = {
    # Planar bulk — different model class (BSIM4), not BSIM-CMG.
    "40nm": dict(arch="planar", unit="finger", vdd=1.10, lg="40n", weff_per_unit=0.12,
                 vth_n=0.40, vth_p=-0.42, u0_n=0.045, u0_p=0.010, toxe="2.2n"),
    "28nm": dict(arch="planar", unit="finger", vdd=1.00, lg="28n", weff_per_unit=0.10,
                 vth_n=0.35, vth_p=-0.37, u0_n=0.045, u0_p=0.010, toxe="1.8n"),
    # FinFET — real ASAP7 at 7nm; predictive (calibrated) elsewhere.
    "16nm": _fin(0.80, "20n", 0.030), "14nm": _fin(0.80, "18n", 0.030),
    "10nm": _fin(0.75, "18n", 0.028), "7nm": _fin(0.70, "21n", 0.030),
    "5nm":  _fin(0.70, "16n", 0.026), "4nm": _fin(0.70, "14n", 0.024),
    "3nm":  _fin(0.65, "14n", 0.022),
    # GAA nanosheet.
    # lg=14n matches the GT2N extraction point (github.com/azadnaeemi/GT2N); sim.py
    # drives this node from the translated GT2N 2nm GAA-nanosheet card when present.
    "2nm": dict(arch="gaa", unit="nanosheet_stack", vdd=0.60, lg="14n", weff_per_unit=0.075,
                sheets_per_stack=3, vth_n=0.15, vth_p=-0.17, u0_n=0.048, u0_p=0.013, toxe="0.9n"),
    "n2_predictive": dict(arch="gaa", unit="nanosheet_stack", vdd=0.60, lg="14n",
                          weff_per_unit=0.075, sheets_per_stack=3,
                          vth_n=0.15, vth_p=-0.17, u0_n=0.048, u0_p=0.013, toxe="1.0n"),
    # "a14": CFET (stacked GAA) — beyond-2nm (future).
}

ORDER = ["40nm", "28nm", "16nm", "14nm", "10nm", "7nm", "5nm", "4nm", "3nm", "2nm"]


def get_node(name: str) -> dict:
    if name not in NODES:
        raise ValueError(f"unknown node {name!r} (known: {sorted(NODES)})")
    return NODES[name]


def arch(name: str) -> str:
    return get_node(name)["arch"]


def width_for_units(node: str, n_units: int) -> float:
    """Total effective width (µm) for ``n_units`` device units (fins or sheet stacks)."""
    return round(n_units * get_node(node)["weff_per_unit"], 4)


def model_card(node: str) -> str:
    """BSIM4 (level-14) nmos/pmos cards — the approximation fallback when BSIM-CMG
    OSDI is unavailable. Prefer the real BSIM-CMG model (see sim.py)."""
    p = get_node(node)
    return (
        f".model nmos_ff nmos (level=14 version=4.8.2 toxe={p['toxe']} vth0={p['vth_n']} "
        f"k1=0.38 u0={p['u0_n']} ua=1.0e-9 vsat=1.4e5 rdsw=140 nfactor=1.2 voff=-0.12)\n"
        f".model pmos_ff pmos (level=14 version=4.8.2 toxe={p['toxe']} vth0={p['vth_p']} "
        f"k1=0.38 u0={p['u0_p']} ua=1.3e-9 vsat=1.0e5 rdsw=200 nfactor=1.2 voff=-0.12)"
    )


__all__ = ["NODES", "ORDER", "get_node", "arch", "width_for_units", "model_card"]
