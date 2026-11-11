"""Calibrate a PREDICTIVE device card for any node from PUBLIC targets.

Generalizes build_n2_predictive.py: fits a BSIM-CMG card (FinFET/GAA) to public
Ion/Ioff/SS targets via real ngspice, using decoupled geometry knobs
(TFIN→SS, HFIN→Ion, PHIG→Ioff). Lets us fill the missing FinFET nodes (10nm, 4nm)
the same way we did N2 — predictive, from public roadmap data, NOT foundry PDKs.

40nm is PLANAR bulk (BSIM4), a different model class — not handled here (use the
BSIM4 node card / a public PTM 45nm card).

    python3 calibrate_node.py <node>     # e.g. 10nm, 4nm
Writes pdk/<node>/modelcard.<node>.nmos + report.json.
"""

from __future__ import annotations

import json, math, os, re, subprocess, sys, tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent
_NM = Path("/Users/josepereira/code/node-migration/.tools/bsimcmg")
OSDI = Path(os.environ.get("BSIMCMG_OSDI", _NM / "vacode111" / "bsimcmg.osdi"))
BASE = Path(os.environ.get("BSIMCMG_NMOS", _NM / "examples" / "modelcard.nmos"))

# Public-ballpark targets across the FinFET space (NOT foundry data). BSIM-CMG.
# Planar bulk (40/28nm) is a different model class (BSIM4) — see pdk_nodes.
NODE_TARGETS = {
    "16nm": dict(arch="finfet", vdd=0.80, lg="20n", ion_ua=34.0, ioff_na=5.0, ss=72.0),
    "14nm": dict(arch="finfet", vdd=0.80, lg="18n", ion_ua=35.0, ioff_na=4.0, ss=71.0),
    "10nm": dict(arch="finfet", vdd=0.75, lg="18n", ion_ua=36.0, ioff_na=3.0, ss=70.0),
    "5nm":  dict(arch="finfet", vdd=0.70, lg="16n", ion_ua=40.0, ioff_na=2.0, ss=68.0),
    "4nm":  dict(arch="finfet", vdd=0.70, lg="14n", ion_ua=42.0, ioff_na=1.5, ss=67.0),
    "3nm":  dict(arch="finfet", vdd=0.65, lg="14n", ion_ua=44.0, ioff_na=1.0, ss=66.0),
}


def set_param(card, name, value):
    pat = re.compile(rf"(\+\s*{name}\s*=\s*)\S+", re.I)
    return pat.sub(rf"\g<1>{value}", card, 1) if pat.search(card) else card.rstrip() + f"\n+ {name} = {value}\n"


def measure(card_text, vdd, lg):
    d = tempfile.mkdtemp(); cf = os.path.join(d, "c.nmos"); Path(cf).write_text(card_text)
    data = os.path.join(d, "iv.data")
    tb = (f"* iv\nN1 dd gg 0 0 nmos L={lg} NFIN=1\nVg gg 0 0\nVd dd 0 {vdd}\n.control\n"
          f"pre_osdi {OSDI}\ndc Vg 0 {vdd} 0.02\nlet ia=abs(i(Vd))\nwrdata {data} ia\n.endc\n"
          f".include {cf}\n.end\n")
    Path(os.path.join(d, "t.cir")).write_text(tb)
    subprocess.run(["ngspice", "-b", os.path.join(d, "t.cir")], capture_output=True, text=True, timeout=60)
    pts = []
    for line in (open(data) if os.path.exists(data) else []):
        p = line.split()
        if len(p) >= 2:
            try: pts.append((float(p[0]), float(p[1])))
            except ValueError: pass
    pts.sort()
    if not pts: return {}
    ion, ioff = pts[-1][1] * 1e6, pts[0][1] * 1e9
    sl = [(b[0]-a[0])/(math.log10(b[1])-math.log10(a[1]))*1000 for a, b in zip(pts, pts[1:]) if 0 < a[1] < b[1] < 1e-6]
    return {"Ion_uA": round(ion, 3), "Ioff_nA": round(ioff, 4), "SS_mVdec": round(min(sl), 1) if sl else None}


def calibrate(node: str):
    t = NODE_TARGETS[node]
    if t["arch"] != "finfet":
        raise SystemExit(f"{node}: {t['arch']} needs a different model class (BSIM4), not this tool")
    out = KIT / "pdk" / f"{node}_predictive"; out.mkdir(parents=True, exist_ok=True)
    log = open(out / "build.log", "w", buffering=1)
    base = BASE.read_text()
    vdd, lg = t["vdd"], t["lg"]
    eot, tfin, hfin, phig = "1.0n", 7.0, 45.0, 4.61

    def build(tfin, hfin, phig):
        c = set_param(base, "EOT", eot); c = set_param(c, "TFIN", f"{tfin:.2f}n")
        c = set_param(c, "HFIN", f"{hfin:.2f}n"); return set_param(c, "PHIG", round(phig, 4))

    hist = []
    for it in range(22):
        m = measure(build(tfin, hfin, phig), vdd, lg)
        if not m: log.write(f"iter {it}: sim failed\n"); break
        hist.append({"iter": it, "tfin": round(tfin, 2), "hfin": round(hfin, 2), "phig": round(phig, 4), **m})
        log.write(f"iter {it}: TFIN={tfin:.2f} HFIN={hfin:.2f} PHIG={phig:.3f} -> Ion={m['Ion_uA']} Ioff={m['Ioff_nA']} SS={m['SS_mVdec']}\n")
        ion, ioff, ss = m["Ion_uA"], m["Ioff_nA"], m["SS_mVdec"]
        if abs(ion - t["ion_ua"]) <= 0.12 * t["ion_ua"] and 0.3 * t["ioff_na"] <= ioff <= 3 * t["ioff_na"] and ss is not None and ss <= t["ss"] + 3:
            log.write("converged.\n"); break
        if ss is not None and ss > t["ss"] + 3: tfin = max(4.0, tfin - 0.5)
        elif ss is not None and ss < t["ss"] - 4: tfin = min(10.0, tfin + 0.5)
        if abs(ion - t["ion_ua"]) > 0.12 * t["ion_ua"]:
            hfin = max(10.0, min(120.0, hfin * (t["ion_ua"] / max(ion, 1e-3)) ** 0.9))
        if ioff > 3 * t["ioff_na"]: phig += 0.03
        elif ioff < 0.3 * t["ioff_na"]: phig -= 0.03

    f = hist[-1] if hist else {}
    (out / f"modelcard.{node}.nmos").write_text(
        f"* PREDICTIVE {node} FinFET nmos — calibrated to PUBLIC targets, NOT a foundry PDK.\n"
        + build(f.get("tfin", tfin), f.get("hfin", hfin), f.get("phig", phig)))
    (out / "report.json").write_text(json.dumps(
        {"node": node, "arch": "finfet", "vdd": vdd, "lg": lg, "targets": t,
         "achieved": {k: f.get(k) for k in ("Ion_uA", "Ioff_nA", "SS_mVdec")},
         "iterations": len(hist)}, indent=2))
    print(f"{node}: achieved", {k: f.get(k) for k in ("Ion_uA", "Ioff_nA", "SS_mVdec")})


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "10nm"
    nodes = list(NODE_TARGETS) if arg == "all" else [arg]
    for n in nodes:
        try:
            calibrate(n)
        except Exception as e:
            print(f"{n}: FAILED {e}")
