"""Calibrate a PREDICTIVE N2-class (IMEC-N2-like, GAA nanosheet) BSIM-CMG card.

Independent predictive model fit to PUBLIC roadmap targets (IRDS / IEDM ballpark) —
NOT the confidential IMEC N2 PDK and not derived from it. Tunes a BSIM-CMG sample
card's threshold (DELVTO) and mobility (U0) against public Ion / Ioff / SS targets
using real ngspice, then writes a calibrated nmos card + a report.

Run (usually in the background):
    python3 build_n2_predictive.py
Outputs under pdk/n2_predictive/: modelcard.n2.nmos, report.json, build.log
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

KIT = Path(__file__).resolve().parent
OUT = KIT / "pdk" / "n2_predictive"
OUT.mkdir(parents=True, exist_ok=True)
LOG = open(OUT / "build.log", "w", buffering=1)

# Toolchain (reuse an existing build if present).
_NM = Path("/Users/josepereira/code/node-migration/.tools/bsimcmg")
OSDI = Path(os.environ.get("BSIMCMG_OSDI", _NM / "vacode111" / "bsimcmg.osdi"))
BASE = Path(os.environ.get("BSIMCMG_NMOS", _NM / "examples" / "modelcard.nmos"))

# Public-ballpark N2 targets (GAA nanosheet, per device/fin unit). Documented as
# PUBLIC estimates, not a foundry datasheet.
VDD, LG = 0.60, "14n"
ION_TARGET_UA = 40.0      # |Id| at Vg=Vd=Vdd
IOFF_TARGET_NA = 1.0      # |Id| at Vg=0, Vd=Vdd
SS_TARGET_MVDEC = 68.0


def log(msg: str):
    LOG.write(msg + "\n")


def set_param(card: str, name: str, value) -> str:
    """Set a + param in a .model card: replace if present, else append."""
    pat = re.compile(rf"(\+\s*{name}\s*=\s*)\S+", re.IGNORECASE)
    if pat.search(card):
        return pat.sub(rf"\g<1>{value}", card, count=1)
    return card.rstrip() + f"\n+ {name} = {value}\n"


def measure(card_text: str) -> dict:
    """DC sweep Vg at Vd=Vdd on one device; extract Ion, Ioff, SS."""
    d = tempfile.mkdtemp()
    cardf = os.path.join(d, "card.nmos")
    Path(cardf).write_text(card_text)
    data = os.path.join(d, "iv.data")
    tb = f"""* n2 device IV
N1 dd gg 0 0 nmos L={LG} NFIN=1
Vg gg 0 0
Vd dd 0 {VDD}
.control
pre_osdi {OSDI}
dc Vg 0 {VDD} 0.02
let iabs = abs(i(Vd))
wrdata {data} iabs
.endc
.include {cardf}
.end
"""
    Path(os.path.join(d, "tb.cir")).write_text(tb)
    subprocess.run(["ngspice", "-b", os.path.join(d, "tb.cir")],
                   capture_output=True, text=True, timeout=60)
    pts = []
    if os.path.exists(data):
        for line in open(data):
            p = line.split()
            if len(p) >= 2:
                try:
                    pts.append((float(p[0]), float(p[1])))
                except ValueError:
                    pass
    if not pts:
        return {}
    pts.sort(key=lambda t: t[0])
    ion = pts[-1][1] * 1e6                       # µA  (Vg=Vd=Vdd)
    ioff = pts[0][1] * 1e9                        # nA  (Vg=0)
    # SS = steepest (min) slope in the subthreshold region (Id < 1 µA).
    slopes = []
    for (v1, a), (v2, b) in zip(pts, pts[1:]):
        if 0 < a < b < 1e-6:
            slopes.append((v2 - v1) / (math.log10(b) - math.log10(a)) * 1000.0)
    ss = min(slopes) if slopes else None
    return {"Ion_uA": round(ion, 3), "Ioff_nA": round(ioff, 4),
            "SS_mVdec": round(ss, 1) if ss else None}


def main():
    t0 = 0  # (no wall clock in-script; count iterations instead)
    base = BASE.read_text()
    log(f"N2 predictive calibration — targets: Ion≥{ION_TARGET_UA}µA, "
        f"Ioff≈{IOFF_TARGET_NA}nA, SS≈{SS_TARGET_MVDEC}mV/dec @ Vdd={VDD}")

    # Decoupled BSIM-CMG knobs: TFIN→SS (thinner=steeper), HFIN→Ion (drive),
    # PHIG→Ioff (gate workfunction/Vth). EOT fixed thin for good electrostatics.
    eot, tfin, hfin, phig = "1.0n", 7.0, 45.0, 4.61

    def build(tfin, hfin, phig):
        c = set_param(base, "EOT", eot)
        c = set_param(c, "TFIN", f"{tfin:.2f}n")
        c = set_param(c, "HFIN", f"{hfin:.2f}n")
        c = set_param(c, "PHIG", round(phig, 4))
        return c

    history = []
    for it in range(20):
        meas = measure(build(tfin, hfin, phig))
        if not meas:
            log(f"iter {it}: sim failed"); break
        history.append({"iter": it, "tfin_nm": round(tfin, 2), "hfin_nm": round(hfin, 2),
                        "phig": round(phig, 4), **meas})
        log(f"iter {it}: TFIN={tfin:.2f}n HFIN={hfin:.2f}n PHIG={phig:.3f} -> "
            f"Ion={meas['Ion_uA']}µA Ioff={meas['Ioff_nA']}nA SS={meas['SS_mVdec']}")
        ion, ioff, ss = meas["Ion_uA"], meas["Ioff_nA"], meas["SS_mVdec"]
        ion_ok = 35.0 <= ion <= 45.0
        ioff_ok = 0.3 <= ioff <= 3.0
        ss_ok = ss is not None and ss <= 72.0
        if ion_ok and ioff_ok and ss_ok:
            log("converged."); break
        if ss is not None and ss > 72.0:
            tfin = max(4.0, tfin - 0.5)          # thinner body → steeper SS
        elif ss is not None and ss < 60.0:
            tfin = min(10.0, tfin + 0.5)
        if not ion_ok:
            hfin = max(10.0, min(120.0, hfin * (ION_TARGET_UA / max(ion, 1e-3)) ** 0.9))
        if ioff > 3.0:
            phig += 0.03
        elif ioff < 0.3:
            phig -= 0.03

    final = history[-1] if history else {}
    card = build(final.get("tfin_nm", tfin), final.get("hfin_nm", hfin),
                 final.get("phig", phig))
    (OUT / "modelcard.n2.nmos").write_text(
        "* PREDICTIVE N2-class nmos (GAA nanosheet) — calibrated to PUBLIC targets.\n"
        "* NOT the IMEC N2 PDK; independent predictive fit. For exploration only.\n" + card)
    report = {
        "node": "n2_predictive", "arch": "gaa", "vdd": VDD, "lg": LG,
        "targets": {"Ion_uA_min": ION_TARGET_UA, "Ioff_nA": IOFF_TARGET_NA,
                    "SS_mVdec": SS_TARGET_MVDEC},
        "achieved": {k: final.get(k) for k in ("Ion_uA", "Ioff_nA", "SS_mVdec")},
        "params": {"EOT": "1.0n", "TFIN_nm": final.get("tfin_nm"),
                   "HFIN_nm": final.get("hfin_nm"), "PHIG": final.get("phig")},
        "iterations": len(history), "history": history,
        "note": "Predictive model from public roadmap ballpark; not foundry-calibrated.",
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2))
    log(f"DONE. iterations={len(history)} achieved={report['achieved']}")
    print("N2 predictive build complete:", report["achieved"])


if __name__ == "__main__":
    main()
