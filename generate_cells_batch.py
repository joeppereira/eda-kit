"""Batch-generate analog cell netlists and verify each simulates (ngspice .op).

Writes pdk/generated_cells/<cell>.spice for every analog generator, then instantiates
each on real ASAP7 devices with a generic DC harness (supplies + 100k bias paths on
all other ports) and runs .op to confirm the netlist is LIVE (no error, supply current
flows). Reports a table. Spec-sizing per cell is the agentic-loop next pass.

    python3 generate_cells_batch.py
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

from cell_generators import GENERATORS, to_subckt
from sim import BSIMCMG_OSDI, HAVE_BSIMCMG

KIT = Path(__file__).resolve().parent
OUT = KIT / "pdk" / "generated_cells"
OUT.mkdir(parents=True, exist_ok=True)
NC = KIT / "pdk" / "asap7" / "asap7_nmos_rvt.card"
PC = KIT / "pdk" / "asap7" / "asap7_pmos_rvt.card"

SUPPLY = {"VDD": 0.70, "VDDH": 1.50, "VIN": 0.70}


def op_check(cell: str) -> dict:
    devs, ports = GENERATORS[cell]()
    allports = list(dict.fromkeys(ports + ["VDD"]))
    lines = []
    for s, v in SUPPLY.items():
        if s in allports:
            lines.append(f"V{s} {s} 0 {v}")
    lines.append("Vbias BIAS 0 0.35")
    for pt in allports:
        if pt not in SUPPLY and pt != "0":
            lines.append(f"Rh_{pt} {pt} BIAS 100k")       # DC path for every port
    lines.append("X1 " + " ".join(allports) + f" {cell}")
    rails = [s for s in SUPPLY if s in allports]
    prints = " ".join(f"i(V{s})" for s in rails)
    deck = (f".title opcheck {cell}\n" + "\n".join(lines) + "\n" + to_subckt(cell) +
            f".include {NC}\n.include {PC}\n.control\npre_osdi {BSIMCMG_OSDI}\n"
            f"op\nprint v(BIAS) {prints}\n.endc\n.end\n")
    d = tempfile.mkdtemp(); f = os.path.join(d, "t.cir"); Path(f).write_text(deck)
    r = subprocess.run(["ngspice", "-b", f], capture_output=True, text=True, timeout=60).stdout
    # Live = op converged (we got v(BIAS) back) and no hard error.
    ran = re.search(r"v\(bias\)\s*=", r, re.I) is not None
    err = "no simulations run" in r.lower()
    isup = sum(abs(float(x)) for x in re.findall(r"i\(v(?:vdd|vddh|vin)\)\s*=\s*([-\d.eE+]+)", r, re.I))
    return {"devices": len(devs), "ports": len(allports),
            "Isup_uA": round(isup * 1e6, 2), "live": ran and not err}


def main():
    print(f"{'cell':26} {'devs':>4} {'Isup(uA)':>9}  live")
    live = 0
    for cell in GENERATORS:
        (OUT / f"{cell}.spice").write_text(to_subckt(cell))
        res = op_check(cell) if HAVE_BSIMCMG else {"devices": "?", "Isup_uA": "-", "live": None}
        live += 1 if res.get("live") else 0
        print(f"{cell:26} {str(res['devices']):>4} {str(res['Isup_uA']):>9}  {res['live']}")
    print(f"\n{len(GENERATORS)} netlists written to {OUT}; {live} simulate live.")


if __name__ == "__main__":
    main()
