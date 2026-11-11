"""Calibrate a PREDICTIVE planar-bulk BSIM4 card (40/28nm) from PUBLIC targets.

The planar nodes are a different model class than FinFET/GAA — BSIM4 (bulk), which
ngspice runs natively (level 14). We generate the card ourselves (we have the tools)
rather than depend on an external PTM download: tune VTH0→Ioff, U0→Ion, NFACTOR→SS
against public Ion/Ioff/SS targets using real ngspice. Reference width W = 1 µm.

    python3 calibrate_planar.py [40nm|28nm|all]
Writes pdk/<node>_planar/modelcard.<node>.nmos + report.json.
"""

from __future__ import annotations

import json, math, os, re, subprocess, sys, tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent

# Public-ballpark planar-bulk targets (µA/µm, nA/µm, mV/dec). NOT foundry data.
PLANAR_TARGETS = {
    "40nm": dict(vdd=1.10, lg="40n", ion_ua=600.0, ioff_na=5.0, ss=85.0),
    "28nm": dict(vdd=1.00, lg="28n", ion_ua=650.0, ioff_na=5.0, ss=82.0),
}


def card(vth0, u0, nfactor, toxe="2.0n"):
    return (f".model nmos_bulk nmos (level=14 version=4.8.2 tnom=27 toxe={toxe} toxp=1.8n "
            f"toxm={toxe} vth0={round(vth0,4)} k1=0.50 k2=0.0 u0={round(u0,5)} ua=1.2e-9 "
            f"vsat=9.0e4 rdsw=120 wint=0 lint=0 xj=1.4e-8 nfactor={round(nfactor,3)} "
            f"voff=-0.11 cdsc=1e-4 cit=0 dvt0=2.0 dvt1=0.5)\n")


def measure(c, vdd, lg):
    d = tempfile.mkdtemp(); cf = os.path.join(d, "c"); Path(cf).write_text(c); dat = os.path.join(d, "d")
    tb = (f"* iv\nM1 dd gg 0 0 nmos_bulk L={lg} W=1u\nVg gg 0 0\nVd dd 0 {vdd}\n.control\n"
          f"dc Vg 0 {vdd} 0.02\nlet ia=abs(i(Vd))\nwrdata {dat} ia\n.endc\n.include {cf}\n.end\n")
    Path(os.path.join(d, "t.cir")).write_text(tb)
    subprocess.run(["ngspice", "-b", os.path.join(d, "t.cir")], capture_output=True, text=True, timeout=60)
    pts = []
    for line in (open(dat) if os.path.exists(dat) else []):
        p = line.split()
        if len(p) >= 2:
            try: pts.append((float(p[0]), float(p[1])))
            except ValueError: pass
    pts.sort()
    if not pts: return {}
    ion, ioff = pts[-1][1] * 1e6, pts[0][1] * 1e9
    sl = [(b[0]-a[0])/(math.log10(b[1])-math.log10(a[1]))*1000 for a, b in zip(pts, pts[1:]) if 0 < a[1] < b[1] < 1e-5]
    return {"Ion_uA": round(ion, 1), "Ioff_nA": round(ioff, 4), "SS_mVdec": round(min(sl), 1) if sl else None}


def calibrate(node):
    t = PLANAR_TARGETS[node]
    out = KIT / "pdk" / f"{node}_planar"; out.mkdir(parents=True, exist_ok=True)
    log = open(out / "build.log", "w", buffering=1)
    vth0, u0, nf = 0.40, 0.045, 1.2
    hist = []
    for it in range(26):
        m = measure(card(vth0, u0, nf), t["vdd"], t["lg"])
        if not m: log.write(f"iter {it}: sim failed\n"); break
        hist.append({"iter": it, "vth0": round(vth0, 4), "u0": round(u0, 5), "nfactor": round(nf, 3), **m})
        log.write(f"iter {it}: vth0={vth0:.3f} u0={u0:.4f} nf={nf:.2f} -> Ion={m['Ion_uA']} Ioff={m['Ioff_nA']} SS={m['SS_mVdec']}\n")
        ion, ioff, ss = m["Ion_uA"], m["Ioff_nA"], m["SS_mVdec"]
        if abs(ion - t["ion_ua"]) <= 0.12 * t["ion_ua"] and 0.3 * t["ioff_na"] <= ioff <= 3 * t["ioff_na"] and ss and abs(ss - t["ss"]) <= 5:
            log.write("converged.\n"); break
        if ss and ss < t["ss"] - 5: nf = min(2.4, nf * (t["ss"] / ss))      # raise SS
        elif ss and ss > t["ss"] + 5: nf = max(0.8, nf * (t["ss"] / ss))
        if ioff > 3 * t["ioff_na"]: vth0 += 0.02                             # cut Ioff
        elif ioff < 0.3 * t["ioff_na"]: vth0 -= 0.02
        if abs(ion - t["ion_ua"]) > 0.12 * t["ion_ua"]:
            u0 = max(0.005, min(0.08, u0 * (t["ion_ua"] / max(ion, 1)) ** 0.8))  # Ion via mobility
    f = hist[-1] if hist else {}
    (out / f"modelcard.{node}.nmos").write_text(
        f"* PREDICTIVE {node} planar-bulk nmos (BSIM4) — calibrated to PUBLIC targets, NOT a foundry PDK.\n"
        + card(f.get("vth0", vth0), f.get("u0", u0), f.get("nfactor", nf)))
    (out / "report.json").write_text(json.dumps(
        {"node": node, "arch": "planar", "model": "BSIM4", "vdd": t["vdd"], "lg": t["lg"],
         "targets": t, "achieved": {k: f.get(k) for k in ("Ion_uA", "Ioff_nA", "SS_mVdec")},
         "iterations": len(hist)}, indent=2))
    print(f"{node}: achieved", {k: f.get(k) for k in ("Ion_uA", "Ioff_nA", "SS_mVdec")})


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "40nm"
    for n in (list(PLANAR_TARGETS) if arg == "all" else [arg]):
        calibrate(n)
