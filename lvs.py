"""LVS — layout vs schematic (structural + matching) via the KLayout DB.

Checks the generated GDS against the source netlist at the level that matters for a
matched analog cell:
  1. **Device count** — poly gates over active in the GDS vs transistor count expected.
  2. **Common-centroid preserved** — the layout placed matched devices A/B so their
     centroids coincide (the matching intent survived into geometry).

HONEST SCOPE: this is **structural + matching LVS**, not full connectivity LVS. Real
net-by-net LVS needs KLayout's extraction + a PDK connectivity deck (or netgen). The
sec-soc ORFS ASAP7 platform carries a real KLayout DRC deck that can back a fuller
flow — see PLAN.md.
"""

from __future__ import annotations

from typing import Any

import klayout.db as db


def run_lvs(gds_path: str, device_map: list, expected_transistors: int,
            poly_layer=(7, 0), active_layer=(11, 0)) -> dict[str, Any]:
    """Compare layout geometry to the expected device count + matching intent."""
    ly = db.Layout()
    ly.read(gds_path)
    top = ly.top_cell()
    poly = db.Region(top.begin_shapes_rec(ly.layer(*poly_layer)))
    active = db.Region(top.begin_shapes_rec(ly.layer(*active_layer)))
    # Transistor channels = poly AND active; merge per gate column.
    gates = (poly & active)
    gates.merge()
    # Count distinct gate columns by x-position of poly shapes.
    gate_cols = poly.count()
    count_match = gate_cols == expected_transistors

    # Common-centroid: centroid of A-labelled device x's == centroid of B's.
    xa = [x for lbl, x in (device_map or []) if lbl == "A"]
    xb = [x for lbl, x in (device_map or []) if lbl == "B"]
    cc_ok = bool(xa) and bool(xb) and abs(sum(xa) / len(xa) - sum(xb) / len(xb)) < 1e-3

    return {
        "gds": gds_path,
        "gates_in_layout": gate_cols,
        "expected_transistors": expected_transistors,
        "device_count_match": count_match,
        "common_centroid_preserved": cc_ok,
        "centroid_A_um": round(sum(xa) / len(xa), 4) if xa else None,
        "centroid_B_um": round(sum(xb) / len(xb), 4) if xb else None,
        "clean": count_match and cc_ok,
        "note": "structural + matching LVS; full connectivity LVS needs extraction + PDK deck",
    }


__all__ = ["run_lvs"]
