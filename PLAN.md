# Plan — Analog EDA desktop app + sign-off/layout roadmap

## A. Electron desktop app (UI over the Python eda-kit backend)
Skills: `electron-backend`, `electron-frontend`.

**Architecture**
- **Backend (main process → Python):** `eda-kit` is the compute engine (ngspice sim,
  gdstk layout, KLayout DRC/LVS). Main process spawns it via `child_process` (per-task)
  or a loopback FastAPI server (stateful). Ship Python bundled (PyInstaller/venv).
- **Bridge:** preload + `contextBridge` exposing a tiny validated API; IPC via
  `ipcMain.handle`/`ipcRenderer.invoke`. Renderer gets **no Node**.
- **Frontend (renderer):** sandboxed SPA (Vite + React/Svelte), strict CSP, local assets.
  Panels: netlist/schematic · **GDS layout viewer** (canvas from polygons the backend
  returns as JSON) · results (sim curves, DRC/LVS verdicts, scorecard).

**Phases**
1. Scaffold secure shell (Forge) + preload API + one IPC call (`design_cell`). *(needs Node/npm install)*
2. GDS viewer panel (render `layout.py` polygons) + DRC/LVS verdict panel.
3. Migration flow UI (pick cell + source→target node, run, show migrated result).
4. Package: mac code-sign + notarize (avoid the Gatekeeper class of issue).

> Node/npm are **not installed** in the current env — the skills capture the how; the
> scaffold step runs once Node is available.

## B. Layout / sign-off roadmap (what makes it real migration)
Current (open tools, working): generate (**gdstk**) → **DRC** (klayout.db) → **LVS**
(structural + common-centroid). Honest gaps → plan:

| Step | Plan | Reuse |
|---|---|---|
| Real DRC **deck** (not illustrative rules) | Point `drc.py` at the real **ASAP7 KLayout `.lydrc`** + layer map | **sec-soc** `eda/orfs/.../asap7/{drc/asap7.lydrc, KLayout/asap7.lyp}` |
| Real layermap in GDS | Emit ASAP7 layer numbers from `asap7.lyp` in `layout.py` | sec-soc ASAP7 |
| Full connectivity **LVS** | KLayout `LayoutToNetlist` extraction + connectivity, or **netgen** | — |
| Automated **place-and-route** of full cells | **ALIGN** in Docker (consumes our matching/symmetry constraints; supports ASAP7) | `align-docker/` |
| More cell **layouts** | gdstk generators for cap array / CML / guard-ring / ODT | — |

## C. Reuse / alignment with sec-soc (checked)
- sec-soc runs the **digital** flow: **OpenROAD-flow-scripts** on ASAP7 (RTL→GDS, KLayout
  DRC + LVS for standard cells), `project_7_dfm` (yield/cost), `dv/` (RTL verification).
  **Complementary** — no analog LVS/layout, no Electron there; no duplication.
- **Reuse:** the ASAP7 **KLayout DRC deck + layer map** (make our analog DRC real), and
  `scripts/build_openroad_mac.sh` / `run_orfs.sh` as the mac EDA setup pattern.

## D. Known blockers (honest)
- **ALIGN**: source-only C++/CMake, Linux/Docker + py≤3.12 → `align-docker/`.
- **KLayout GUI**: brew cask disabled (Gatekeeper) → use the `klayout` pip module (done).
- **pmos in BSIM-CMG OSDI**: won't DC-bias (works transient) → blocks PLL charge-pump cell.
- **Node/npm**: not installed → Electron scaffold deferred; skills ready.
