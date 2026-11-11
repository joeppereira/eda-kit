# eda-kit — reusable open-source analog EDA

Project-agnostic building blocks for **real** analog device simulation and
node-portable agentic design. Extracted from the node-migration project so other
projects (sec-soc, 3D-IC-Design, …) can reuse them.

## What's here
| Module | Purpose |
|---|---|
| `pdk_nodes.py` | Architecture-aware **predictive** node family: FinFET 7/5/3 nm → GAA 2 nm (+ N2/A14 extension points). Width quantized by device unit (fin / nanosheet stack). **Artificial, not foundry PDKs.** |
| `sim.py` | Real **ngspice** harness. Uses **BSIM-CMG** (multi-gate FinFET/GAA) via **OSDI** when available; BSIM4 fallback. Returns measured gain/BW/power. |
| `specs.py` | Design specs the critic enforces — **traced to JEDEC JESD209-5** (LPDDR5/5X): BW derived from WCK, RON/ODT from RZQ, VREF/CA/CK from the standard. |
| `build_gt2n.py` | Translate the **GT2N** 2 nm GAA-nanosheet PDK (Georgia Tech, BSD-3) HSPICE→OSDI → the `2nm` node card (real published 2 nm, supersedes the hand-calibrated N2). |
| `reconcile_specs.py` | Fill the JESD209-5 Specs-sheet "code-base value/check" columns from `specs.py` (17/17 known targets PASS). |
| `design_agent.py` | **Agentic loop**: propose → simulate → critic → iterate; `migrate_cml()` carries a design across nodes incl. the **FinFET→GAA** boundary. |
| `setup.sh` | One-time macOS toolchain build: ngspice + OpenVAF + BSIM-CMG → `.osdi`. |
| `build_n2_predictive.py` | Calibrate a predictive **N2-class** card to **public** targets (Ion/Ioff/SS). Converges: Ion 40.5µA, Ioff 0.38nA, SS 68mV/dec. |
| `cells.py` | Cells beyond the CML: **tx_driver** (swing into 50Ω) + **rx_preamp** (gain/BW) + **charge_pump** (up/down current-matched), real & converging. |
| `pdk/asap7/` | **Real ASAP7** 7nm FinFET BSIM-CMG cards → the `7nm` node. `pdk/gt2n/` → the translated **GT2N** 2nm GAA card (`2nm` node); `pdk/n2_predictive/` → calibrated-N2 fallback. |
| `layout.py` | Generate **real GDS** (gdstk) from intent+sizing: common-centroid matched pair + guard ring. *Geometry is real; not DRC-signed-off.* |
| `lpddr5_cell_catalog.yml` | Full manufacturable LPDDR5 cell list (8 categories) with per-cell status. |

### The layout track (what makes it migration)
A migration must regenerate a **layout** on the target node — not just a netlist.
Status: `layout.py` emits real GDS geometry now (first rung). Sign-off path:
**ALIGN** (open analog auto-layout, consumes our matching/symmetry constraints,
supports ASAP7) → **KLayout/magic + PDK deck** for DRC/LVS/PERC. Not installed yet.

## Quickstart
```bash
bash setup.sh                         # build the real device-model toolchain (.tools/)
python -c "from design_agent import migrate_cml; print(migrate_cml('7nm','2nm'))"
pytest evals -q
```

## Honesty / IP boundary
- Nodes are **predictive**, not foundry PDKs. The `7nm` node uses **real ASAP7** cards
  and `2nm` uses the **real published GT2N** 2nm GAA card; intermediate nodes are
  calibrated to public Ion/Ioff/SS. Credible for exploration — **never for sign-off.**
- **Never clone NDA PDKs.** Real foundry/IMEC decks (N2, A14, …) are license- and
  export-controlled via Europractice. Predictive equivalents here are built only
  from **public** roadmap data (IRDS, IEDM/VLSI) and are for exploration, not sign-off.
- `.tools/` (downloaded toolchain) is gitignored; rebuild with `setup.sh`.

## Reuse from another project
```python
import sys; sys.path.insert(0, "/Users/josepereira/code/eda-kit")
from design_agent import design_cml, migrate_cml
```
or set `PYTHONPATH=/Users/josepereira/code/eda-kit`. The OSDI model path can be
pointed anywhere via the `BSIMCMG_OSDI` / `BSIMCMG_NMOS` env vars.

## Layout deps
`pip install gdstk klayout` (pure-Python GDS + KLayout DRC engine; no GUI needed).
ALIGN (auto analog place-and-route) is **not** installable here — source-only C++/CMake
build, needs Linux/Docker + py≤3.12. Run it in a container when needed; it consumes the
same matching/symmetry constraints our intent extractor emits.
