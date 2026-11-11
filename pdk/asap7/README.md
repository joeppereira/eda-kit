# ASAP7 device models (real, predictive 7nm FinFET)

`7nm_TT_160803.pm` is the **ASAP7** typical-corner BSIM-CMG model file, from the
public ASAP7 PDK (The-OpenROAD-Project/asap7_pdk_r1p7, models/hspice/). ASAP7 is a
**predictive** 7nm FinFET PDK from Arizona State University (L. Clark et al.), freely
distributed for research — it is NOT a foundry PDK.

`asap7_nmos_rvt.card` / `asap7_pmos_rvt.card` are the RVT devices extracted from it,
with the header rewritten from HSPICE `level=72` to the OSDI module `bsimcmg_va` and a
`TYPE` flag added (nmos=+1, pmos=−1). Loaded into ngspice via `pre_osdi` (BSIM-CMG
111; the cards are version 107 — a benign param-version warning results).

Used for the `7nm` FinFET node in `pdk_nodes.py` / `sim.py`.
Known issue: pmos does not bias in a DC `.op` in this OSDI setup (works in transient).
