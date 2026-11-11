"""Market-segment profiles — the second migration axis (node × segment).

Migration isn't only across geometry nodes; a design is retargeted across market
segments, each with its own process option (Vt flavor), operating voltage, and
temperature corner:

  compute/HPC   — fastest Vt (SLVT), nominal Vdd, 25°C
  mobile        — balanced Vt (LVT), reduced Vdd (power/area), 25°C
  low_power     — low-leakage Vt (RVT), lowest Vdd, 25°C
  automotive    — RVT, nominal Vdd, 150°C (AEC-Q reliability margin)
  industrial    — RVT, nominal Vdd, 125°C (robustness)

Vt flavor is real on ASAP7 (SLVT/LVT/RVT cards extracted); on predictive nodes it
is approximated (single calibrated card) — temperature and Vdd still apply.
"""

from __future__ import annotations

SEGMENTS = {
    "compute":    dict(vt="slvt", temp_c=25,  vdd_scale=1.00, priority="speed",
                       desc="HPC / datacenter — fastest Vt, nominal/overdrive Vdd"),
    "mobile":     dict(vt="lvt",  temp_c=25,  vdd_scale=0.90, priority="power",
                       desc="mobile — balanced Vt, reduced Vdd for power/area"),
    "low_power":  dict(vt="rvt",  temp_c=25,  vdd_scale=0.85, priority="leakage",
                       desc="IoT / ULP — low-leakage Vt, lowest Vdd"),
    "automotive": dict(vt="rvt",  temp_c=150, vdd_scale=1.00, priority="margin",
                       desc="automotive (AEC-Q) — 150°C, reliability margin"),
    "industrial": dict(vt="rvt",  temp_c=125, vdd_scale=1.00, priority="margin",
                       desc="industrial — 125°C, robustness"),
}


def get_segment(name: str | None) -> dict:
    if name is None:
        return dict(vt="rvt", temp_c=25, vdd_scale=1.0, priority="nominal", desc="nominal")
    if name not in SEGMENTS:
        raise ValueError(f"unknown segment {name!r} (known: {sorted(SEGMENTS)})")
    return SEGMENTS[name]


__all__ = ["SEGMENTS", "get_segment"]
