"""Real DRC on generated GDS, via the KLayout DRC engine (klayout.db).

This is a genuine geometry rule-checker — width and spacing per layer — not a mock.
The RULESET here is **illustrative** (not a foundry deck); swap in a PDK deck for
sign-off. It closes the verify half of the layout loop: generate (layout.py) → DRC.
"""

from __future__ import annotations

from typing import Any

import klayout.db as db

# REAL ASAP7 width/space rules (µm), from sec-soc ORFS asap7.lydrc, on real ASAP7
# layers. This is the width/space SUBSET of the deck our klayout.db engine checks;
# the full deck's enclosure/select/well/LI rules need a complete layout (ALIGN).
RULESET = [
    ("fin",    2,  0, 0.006, 0.018),   # fin width ~6.5nm; pitch 27nm
    ("poly",   7,  0, 0.020, 0.034),   # gate length ~21nm; GATE.S.3 space 34nm
    ("active", 11, 0, 0.016, 0.038),   # ACTIVE.W.3 16nm; ACTIVE.S.2B 38nm
    ("m1",     19, 0, 0.018, 0.018),   # M1 min width/space
]


def run_drc(gds_path: str, ruleset=RULESET) -> dict[str, Any]:
    """Run width/space checks per layer; return per-rule violation counts + total."""
    ly = db.Layout()
    ly.read(gds_path)
    top = ly.top_cell()
    results = []
    total = 0
    for name, layer, dt, min_w, min_s in ruleset:
        li = ly.layer(layer, dt)
        reg = db.Region(top.begin_shapes_rec(li))
        wv = reg.width_check(min_w / ly.dbu).count() if min_w else 0
        sv = reg.space_check(min_s / ly.dbu).count() if min_s else 0
        results.append({"layer": name, "width_viol": wv, "space_viol": sv,
                        "min_width_um": min_w, "min_space_um": min_s})
        total += wv + sv
    return {"gds": gds_path, "dbu": ly.dbu, "bbox_um": str(top.dbbox()),
            "rules": results, "total_violations": total, "clean": total == 0,
            "note": "illustrative ruleset (not a PDK deck); swap a real deck for sign-off"}


__all__ = ["run_drc", "RULESET"]
