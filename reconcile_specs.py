"""Fill the tracker Specs sheet's 'Code-base value' + 'Check' columns from specs.py.

The LPDDR5 PHY status tracker's Specs sheet lists each electrical target with two empty
columns — 'Code-base value' and 'Check'. This script resolves every *known/derived* target
against our specs.py constants and reports PASS / MISMATCH, and marks the link-budget /
foundry rows as N/A (not modeled in a predictive kit — honest by design). Run:

    python3 reconcile_specs.py            # prints table
    python3 reconcile_specs.py --csv      # also writes specs_vs_jedec.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

from specs import JESD209_5 as J, wck_freq_hz, ck_freq_hz, ca_rate_mbps, driver_spec

# (cell, parameter, target, unit, code-base value)  — the KNOWN/derived rows.
ROWS = [
    ("PHY (all)", "Max data rate", 6400, "Mb/s", J["default_rate_mbps"]),
    ("PHY (all)", "Unit interval at max rate", 156.25, "ps", 1e12 / (J["default_rate_mbps"] * 1e6)),
    ("PHY (all)", "VDDQ nominal", 0.5, "V", J["vddq_v"]),
    ("PHY (all)", "WCK:CK ratio at max rate", "4:1", "—", f"{J['wck_ck_ratio']}:1"),
    ("PHY (all)", "DFI frequency ratio", "1:1:4", "—", J["dfi_ratio"]),
    ("PHY (all)", "Channel width", 16, "x (bits)", J["channel_width"]),
    ("DQ TX driver", "Ron settings", "240/120/80/60/48/40", "Ω",
     "/".join(str(int(x)) for x in driver_spec()["odt_ohm"])),
    ("DQ ODT leg", "ODT settings (RZQ steps)", "240/120/80/60/48/40", "Ω",
     "/".join(str(int(x)) for x in driver_spec()["odt_ohm"])),
    ("WCK TX (diff)", "WCK frequency at max rate", 3200, "MHz", wck_freq_hz(6400) / 1e6),
    ("CK TX (diff)", "CK frequency at max rate", 800, "MHz", ck_freq_hz() / 1e6),
    ("CA TX", "CA rate at max data rate", 1600, "Mb/s", ca_rate_mbps()),
    ("CA TX", "Number of CA bits", 7, "bits", J["ca_bits"]),
    ("DQ sampler", "Sampling phases", 4, "—", J["sampler_phases"]),
    ("ZQ calibration", "External ZQ resistor", 240, "Ω", J["rzq_ohm"]),
    ("Primary ESD", "HBM target", 1000, "V", J["esd_hbm_v"]),
    ("Primary ESD", "CDM target", 250, "V", J["esd_cdm_v"]),
    ("Boundary-scan cell", "Standard", "IEEE 1149.1", "—", J["boundary_scan"]),
]

# Rows the predictive kit intentionally does NOT model (link/jitter budget, foundry kit).
NA = [
    ("DQ TX driver", "Output slew rate / jitter / pin cap", "link/jitter budget"),
    ("DQ RX input buffer", "Input eye mask", "link/jitter budget"),
    ("DQ sampler", "Residual offset after trim", "link/jitter budget"),
    ("PLL", "RMS jitter", "link/jitter budget (silicon-proven hard-IP)"),
    ("Rail power clamp", "Peak clamp current", "foundry ESD kit"),
]


def _eq(target, value) -> bool:
    if isinstance(target, (int, float)) and isinstance(value, (int, float)):
        return abs(float(target) - float(value)) <= 1e-6 * max(1.0, abs(float(target)))
    return str(target).replace(" ", "") == str(value).replace(" ", "")


def rows() -> list[dict]:
    out = []
    for cell, param, target, unit, value in ROWS:
        val = round(value, 4) if isinstance(value, float) else value
        out.append({"cell": cell, "parameter": param, "target": target, "unit": unit,
                    "code_value": val, "check": "PASS" if _eq(target, val) else "MISMATCH"})
    for cell, param, why in NA:
        out.append({"cell": cell, "parameter": param, "target": "TBD", "unit": "—",
                    "code_value": "—", "check": f"N/A — {why}"})
    return out


def main() -> int:
    r = rows()
    w = max(len(x["cell"]) for x in r)
    p = max(len(x["parameter"]) for x in r)
    print(f"{'cell':<{w}}  {'parameter':<{p}}  {'target':<22} {'code-base':<12} check")
    print("-" * (w + p + 50))
    for x in r:
        print(f"{x['cell']:<{w}}  {x['parameter']:<{p}}  {str(x['target']):<22} "
              f"{str(x['code_value']):<12} {x['check']}")
    checks = [x for x in r if x["check"] in ("PASS", "MISMATCH")]
    npass = sum(x["check"] == "PASS" for x in checks)
    print(f"\n{npass}/{len(checks)} known targets PASS; "
          f"{sum('N/A' in x['check'] for x in r)} rows N/A (not modeled: link-budget/foundry).")
    if "--csv" in sys.argv:
        import csv
        f = Path(__file__).resolve().parent / "specs_vs_jedec.csv"
        with f.open("w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=["cell", "parameter", "target", "unit",
                                                "code_value", "check"])
            wr.writeheader(); wr.writerows(r)
        print(f"wrote {f}")
    return 0 if all(x["check"] != "MISMATCH" for x in r) else 1


if __name__ == "__main__":
    raise SystemExit(main())
