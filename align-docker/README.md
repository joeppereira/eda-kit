# ALIGN in Docker — automated analog layout

ALIGN generates DRC-correct analog **layout** (place + route → GDS) from a **netlist +
constraints**, on ASAP7. It's the real engine for the layout-regeneration step — and it
consumes exactly the constraints our intent extractor already produces (matched pairs,
symmetry, common-centroid). It can't install on this macOS/py3.14 host (source C++ build,
Linux/py≤3.12), so run it in this container.

## Build & run (on any Docker host)
```bash
docker build -t align eda-kit/align-docker
mkdir -p work/diffpair
# put <design>.sp (SPICE netlist) + <design>.const.json (constraints) in work/diffpair/
docker run --rm -v "$PWD/work:/work" align \
    schematic2layout.py /work/diffpair -p /ALIGN-public/pdks/Asap7_PDK
# → GDS + LEF under work/diffpair/
```

## Feeding it our intent (the key integration)
Our `extract_design_intent` output maps directly to ALIGN constraints:

| Our intent | ALIGN constraint |
|---|---|
| `matched_pairs` | `SymmetricBlocks` / `MatchBlocks` |
| `common_centroid_arrays` | `CompactPlacement` + `SymmetricBlocks` (common-centroid) |
| `guard_rings` | `GuardRing` |
| `sensitive_nets` | `ShieldWire` / net priority |

Write a small adapter: `intent_json → ALIGN <design>.const.json`. Then the flow becomes
**real migration**: source netlist + extracted intent → ALIGN → DRC-clean GDS on the
target node.

## Status
Prepared, not yet run here (no Docker daemon in this env). This is the ALIGN track from
`PLAN.md` section B. KLayout DRC/LVS (the `drc.py`/`lvs.py` checks) can verify ALIGN's
output too.
