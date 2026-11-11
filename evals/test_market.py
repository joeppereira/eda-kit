"""Evals for per-market design configurations (reuses sec-soc config pattern)."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from market_config import load, validate, resolve, MarketConfigError

# verify_across_power_states (agentic, sizes across DVFS) is proprietary → tested in
# the private node-migration repo. This public suite covers config load/validate/resolve.


def test_all_markets_validate():
    m = validate()
    assert {"compute", "mobile", "low_power", "automotive", "industrial"} <= set(m)


def test_resolve_has_architecture_library_power_states():
    c = resolve("mobile")
    assert c["node"] in ("3nm",) and c["vt"] in ("lvt", "rvt")
    assert len(c["dvfs"]) >= 1 and c["retention_vdd"] is not None   # microarch/power states


def test_invariants_enforced():
    bad = load()
    bad["automotive"]["temp_c"] = [-40, 125]          # violate 150C invariant
    with pytest.raises(MarketConfigError):
        validate(bad)
