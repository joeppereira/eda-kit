"""Catalog-integrity evals: keep lpddr5_cell_catalog.yml honest + machine-valid.

Guards against two failure modes: (1) typos in the status/view vocabulary drifting the
tracker twin out of sync, and (2) a cell claiming `starter_sim`/`spec_sim` without a real
generator/impl behind it (overclaiming). The second check is the honesty backstop.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cell_generators import GENERATORS  # noqa: E402

CATALOG = yaml.safe_load((ROOT / "lpddr5_cell_catalog.yml").read_text())
CELLS = [c for cat in CATALOG["categories"].values() for c in cat]

STATUS = {"spec_sim", "starter_sim", "catalog", "rtl", "foundry"}
VIEW_FLAGS = {"have", "partial", "needed", "na"}
VIEW_KEYS = {"netlist", "layout", "esd", "term", "dft", "nv", "lib", "ibis"}


def test_vocabulary_valid():
    assert len(CATALOG["categories"]) == 8
    for c in CELLS:
        assert c["status"] in STATUS, c
        assert set(c["views"]) == VIEW_KEYS, c["cell"]
        assert all(v in VIEW_FLAGS for v in c["views"].values()), c["cell"]


def test_starter_sim_cells_have_a_real_generator():
    """Every starter_sim cell must name an impl that resolves to a real generator —
    no cell may claim 'simulates live' without the code that builds it."""
    gen_impls = [c for c in CELLS if c["status"] == "starter_sim"]
    assert gen_impls, "expected starter_sim cells"
    for c in gen_impls:
        impl = c.get("impl", "")
        # impl like "cell_generators.py:vref_generator (...)" — pull the symbol(s).
        assert any(g in impl for g in GENERATORS), f"{c['cell']}: impl {impl!r} not in GENERATORS"


def test_specs_reconcile_against_jedec_sheet():
    """Every known/derived JESD209-5 Specs-sheet target must match specs.py (no MISMATCH)."""
    from reconcile_specs import rows
    r = rows()
    mismatches = [x for x in r if x["check"] == "MISMATCH"]
    assert not mismatches, mismatches
    assert sum(x["check"] == "PASS" for x in r) >= 17


def test_counts_match_meta():
    import collections
    st = collections.Counter(c["status"] for c in CELLS)
    assert st["spec_sim"] == CATALOG["meta"]["counts"]["spec_sim"]
    assert st["starter_sim"] == CATALOG["meta"]["counts"]["starter_sim"]
