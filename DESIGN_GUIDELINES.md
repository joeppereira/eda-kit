# Analog / Mixed-Signal Design Guidelines — design · manufacturing · yield · performance

The design principles the agentic flow applies (or should apply) when generating and
migrating cells. These are the "rules of the trade" that turn a sized netlist into a
manufacturable, high-yield, performant cell. Grounded in standard practice; the
flow encodes them as constraints (intent), checks (DRC/LVS/PERC), or spec targets.

---
## 1. Device & circuit design principles
- **gm/ID sizing.** Pick the operating region by gm/ID: ~15–25 (sub/moderate) for
  low-power/high-gain, ~5–10 (strong inversion) for speed. Our critic sizes fins to a
  target gm (→ gain/BW) — the real knob, not W by hand.
- **Matching.** Matched devices → identical finger count, orientation, surroundings,
  and current direction. Use **common-centroid** (ABBA / 2-D) for 1st-order gradient
  cancellation; **interdigitation** for local mismatch. σ(Vth) ∝ AVT/√(W·L) (Pelgrom)
  → bigger area for better match (trade vs speed/area).
- **Symmetry.** Differential pairs, current mirrors, DACs: mirror about an axis; keep
  routing symmetric (parasitic balance decides skew as much as device match).
- **Dummies.** Edge dummies on arrays so every real device sees identical etch/stress
  neighborhood. **Guard rings** around sensitive/matched groups for isolation + latch-up.
- **Biasing / headroom.** Keep devices in saturation across corners; I_tail·R ≈ Vdd for
  mid-rail output; budget overdrive for the worst (hot, low-Vdd) corner.

## 2. Manufacturing / DFM
- **Density & fill.** Meet metal/poly/active density windows (min & max) → insert fill;
  constrain fill near matched devices so it doesn't break symmetry or add parasitics.
- **Antenna.** Bound gate-connected conductor area per layer during routing; fix with
  antenna diodes or layer jumps.
- **CMP / planarity.** Balance density for dishing/erosion; dummy fill + slotting of wide metal.
- **Layout-dependent effects (LDE).** Well-proximity, diffusion/STI stress, poly-spacing
  shift Vth/mobility → keep matched devices in identical LDE context (OD-to-poly, OD edge).
- **Advanced-node rules.** Multi-patterning coloring (no odd cycles), unidirectional
  metal, min-area, cut/GCUT rules (FinFET), nanosheet pitch (GAA). Enforced by the DRC deck.
- **Litho.** OPC corrects per neighborhood → matched devices must share identical litho
  context within the optical radius (our matched-device printing check).

## 3. ESD / reliability
- **ESD.** Every pad: primary clamp (CDM/HBM) + secondary; rail clamp network; ballast on
  output drivers. PERC checks: current path resistance, clamp coverage.
- **Latch-up.** Guard rings, well taps within max distance, n+/p+ spacing (PERC).
- **EM / IR.** Size power/signal metal to current density limits; IR-drop budget on PDN;
  I/O and clock nets are the usual offenders.
- **Aging (HCI/BTI).** De-rate drive over lifetime; add margin on critical timing;
  avoid static stress on thin-oxide devices.
- **Voltage-aware spacing.** I/O at VDDQ needs wider spacing than core (PERC rule).

## 4. Yield
- **Defect yield.** Y ≈ (1 + A·D0/α)^-α (negative-binomial): smaller area A and lower
  defect density D0 → higher yield. Litho-hotspot density raises local D0 — screen it.
- **Redundancy / repair.** Memories/arrays: row/col redundancy + eFuse repair; trade
  area for yield. Credit redundancy in the yield model.
- **Parametric yield.** Corners + Monte-Carlo (process + mismatch + temperature); design
  for Cpk, not just nominal. Re-center across corners before layout (migration step 3).
- **Systematic vs random.** Cluster failures: systematic (fix the rule/layout, feed back
  as a new design rule/intent constraint) vs random (defect/particle). Feed-forward loop.

## 5. Performance
- **Speed / power / area trade.** GBW ≈ gm/(2π·C_L) is roughly fixed by gm; trade gain vs
  BW via R. Power = Vdd·I; cut Vdd (segment-dependent) and I where spec allows.
- **Corners.** Sign off at SS (slow, hot, low-Vdd) for speed; FF (fast, cold, high-Vdd)
  for power/leakage & reliability; TT nominal.
- **High-speed I/O (LPDDR5).** Impedance match (ZQ cal, ODT), bit/lane skew via routing
  symmetry + per-bit deskew, JEDEC drive/slew/voltage limits, eye margin across corners,
  package/channel co-sim for SI.
- **Node scaling.** Lower Vdd per node cuts power but shrinks headroom → fewer stacked
  devices, more folding; GAA/CFET change the width quantum (sheets/stacks) — our node
  family + critic re-size for this automatically.

---
## How the flow uses these
- **Intent** (extractor): matching / symmetry / common-centroid / guard rings / sensitive
  nets → carried across nodes (sections 1).
- **Critic spec** (design loop): gm/ID, gain/BW/power, corners, segment Vt/temp/Vdd (1,5).
- **Checks** (DRC/LVS/PERC): density/antenna/LDE/ESD/EM (2,3) — real ASAP7 deck.
- **Yield / feed-forward** (copilot): systematic-detractor loop → new rules/checks (4).

**Honest:** the flow today enforces sections 1 + part of 2/5 (matching, gm/ID sizing,
corners-ready, real DRC subset). ESD/PERC, full density/fill, EM/IR, and the parametric
yield loop are specified here but only partially automated — this doc is the spec for
closing them.
