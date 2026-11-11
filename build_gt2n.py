"""Translate the GT2N 2nm GAA-nanosheet PDK cards into our ngspice/OSDI flow.

GT2N (Georgia Tech, Naeemi group — github.com/azadnaeemi/GT2N, BSD-3) ships
BSIM-CMG **VERSION=111** model cards in HSPICE syntax (``.LIB`` / ``.MODEL … level=72``).
Our bsimcmg.osdi is the same BSIM-CMG 111, driven via ngspice ``pre_osdi`` +
``.model <name> bsimcmg_va``. So adopting GT2N is a faithful *card translation*, not a
re-model: we strip the HSPICE wrapper, evaluate its ``10**x`` parameter expressions to
numeric literals, drop the three HSPICE-only knobs, and map its per-Vt ``delvtrand``
offset onto the ``dvtshift`` param our ASAP7 cards already use.

This gives a published, peer-authored 2nm nanosheet card (GEOMOD=2 = real GAA, 3-stack
nanosheet, backside power) in place of our hand-calibrated N2 — strictly more credible.
Predictive only; never for sign-off (same rule as every card in this kit).

    python3 build_gt2n.py <dir-with-gt2_w31_*.sp>   # writes pdk/gt2n/*.card

Vt mapping (our flavor -> GT2N flavor):  rvt->svt, lvt->lvt, slvt->ulvt.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
OUT = KIT / "pdk" / "gt2n"

# HSPICE-only params with no BSIM-CMG-OSDI equivalent — dropped with a logged reason.
DROP = {
    "level":     "HSPICE model selector; OSDI selects the module by name",
    "ids0mult":  "HSPICE current-scaling knob, not a BSIM-CMG model param",
    "chargewf":  "HSPICE-only (PMOS cards); not in the BSIM-CMG parameter set",
    "devtype":   "re-emitted as TYPE (OSDI spelling)",
    "delvtrand": "re-emitted as dvtshift = -delvtrand (sign convention differs; see _emit)",
}
# our Vt flavor  ->  GT2N flavor
VT_MAP = {"rvt": "svt", "lvt": "lvt", "slvt": "ulvt"}


def _num(v: str) -> str:
    """Evaluate an HSPICE param value to a numeric literal.

    GT2N encodes a few params as quoted power-of-ten expressions, e.g.
    ``VSAT1="10**4.41992"`` or ``MEXP="2+10**-0.24068"``. ngspice/OSDI needs a plain
    number, so we evaluate the arithmetic (only ``**``, ``+``, ``-``, digits, ``.``).
    """
    v = v.strip().strip('"').strip("'")
    if re.fullmatch(r"[0-9.eE+\-*]+", v) and "**" in v:
        return repr(eval(v, {"__builtins__": {}}))        # safe: charset-restricted
    if re.fullmatch(r"[0-9.eE+\-*]+", v):
        return repr(eval(v, {"__builtins__": {}})) if any(c in v for c in "*") else v
    return v


def _parse_section(text: str, lib: str) -> dict[str, str]:
    """Pull the ``+key=val`` params out of one ``.LIB <lib> … .ENDL`` block."""
    body = re.search(rf"\.LIB\s+{lib}\b(.*?)\.ENDL", text, re.S | re.I).group(1)
    params: dict[str, str] = {}
    for key, val in re.findall(r"^\+\s*([A-Za-z0-9_]+)\s*=\s*(\"[^\"]*\"|\S+)", body, re.M):
        params[key.lower()] = val
    return params


def _emit(name: str, params: dict[str, str]) -> str:
    """Render one OSDI ``.model`` block, translating/dropping HSPICE-only params."""
    devtype = params.get("devtype", "1")
    lines = [f".model {name} bsimcmg_va", f"+ TYPE = {devtype}"]
    dropped = []
    for k, v in params.items():
        if k == "delvtrand":
            # GT2N's HSPICE `delvtrand` *raises drive* as it increases (ulvt has the
            # largest value); BSIM-CMG-OSDI `dvtshift` *raises Vt*. So the faithful map
            # is a sign flip — verified against Ion/Ioff: with -delvtrand the flavors
            # order correctly (slvt > lvt > rvt drive, leakage tracking). For both n & p.
            lines.append(f"+ dvtshift = {-float(_num(v))}")
            continue
        if k in DROP:
            dropped.append(k)
            continue
        lines.append(f"+ {k} = {_num(v)}")
    hdr = (f"* GT2N 2nm GAA nanosheet (BSIM-CMG v111, GEOMOD=2) — model '{name}'.\n"
           f"* Source: github.com/azadnaeemi/GT2N (Georgia Tech, Naeemi group), BSD-3.\n"
           f"* Translated HSPICE->OSDI by build_gt2n.py. Predictive; never for sign-off.\n"
           f"* Dropped HSPICE-only params: {', '.join(dropped)}.\n")
    return hdr + "\n".join(lines) + "\n"


def main(src_dir: str) -> None:
    src = Path(src_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    for our_vt, gt_vt in VT_MAP.items():
        f = src / f"gt2_w31_{gt_vt}_tt.sp"
        if not f.is_file():
            print(f"  skip {our_vt}: {f.name} not found")
            continue
        text = f.read_text()
        n = _emit("nmos", _parse_section(text, "nfet_typ"))
        p = _emit("pmos", _parse_section(text, "pfet_typ"))
        (OUT / f"gt2n_nmos_{our_vt}.card").write_text(n)
        (OUT / f"gt2n_pmos_{our_vt}.card").write_text(p)
        print(f"  {our_vt:4} <- {gt_vt:4}  wrote gt2n_{{nmos,pmos}}_{our_vt}.card")
    print(f"\nGT2N cards -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(KIT / "pdk" / "gt2n_src"))
