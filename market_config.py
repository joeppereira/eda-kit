"""Per-market design configuration — validate + resolve + drive the flow.

Reuses the sec-soc config pattern (feature-flag yaml → validated config with hard
invariants; cf. project_7_dfm/skills/config_gen.py). Each market in market_config.yml
selects an architecture (node), a library (Vt flavors), and microarch power states
(DVFS/retention/body-bias/adaptive-clocking — see sec-soc `adaptive-clocking` skill).
Resolves a market into operating points the real-sim flow verifies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pdk_nodes import NODES, arch

KIT = Path(__file__).resolve().parent
CONFIG = KIT / "market_config.yml"
VALID_VT = {"slvt", "lvt", "rvt"}          # Vt flavors we have real ASAP7 cards for


class MarketConfigError(ValueError):
    """Raised when a market config violates the schema or a hard invariant."""


def load() -> dict[str, Any]:
    return yaml.safe_load(CONFIG.read_text())["markets"]


def validate(markets: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate every market against the schema + hard invariants; return them."""
    markets = markets or load()
    for name, m in markets.items():
        node = m["architecture"]["node"]
        if node not in NODES:
            raise MarketConfigError(f"{name}: unknown node {node!r}")
        if m["architecture"]["arch"] != arch(node):
            raise MarketConfigError(f"{name}: arch {m['architecture']['arch']} != node arch {arch(node)}")
        for vt in m["library"]["vt"]:
            if vt not in VALID_VT:
                raise MarketConfigError(f"{name}: Vt {vt!r} has no real card (have {sorted(VALID_VT)})")
        ps = m["power_states"]
        if not ps.get("dvfs"):
            raise MarketConfigError(f"{name}: needs >=1 DVFS state")
        # --- hard invariants (mirror sec-soc's security-invariant idea) ---
        if name == "automotive":
            if m["temp_c"][1] < 150:
                raise MarketConfigError("automotive: temp_max must be >= 150C")
            if m.get("reliability", {}).get("aging_margin_pct", 0) < 10:
                raise MarketConfigError("automotive: aging_margin_pct must be >= 10")
        if name in ("mobile", "low_power") and "retention_vdd" not in ps:
            raise MarketConfigError(f"{name}: power_states.retention_vdd required")
    return markets


def resolve(market: str) -> dict[str, Any]:
    """Resolve a market into the operating points the flow runs."""
    m = validate()[market]
    return {
        "market": market,
        "node": m["architecture"]["node"],
        "arch": m["architecture"]["arch"],
        "vt": m["library"]["vt"][0],              # primary Vt for sizing
        "dvfs": m["power_states"]["dvfs"],        # [{name, vdd, freq_ghz}]
        "temp_c": m["temp_c"],
        "retention_vdd": m["power_states"].get("retention_vdd"),
        "adaptive_clocking": m["power_states"].get("adaptive_clocking"),
        "priorities": m["priorities"],
    }


# NOTE: verify_across_power_states() — which SIZES a cell across every DVFS state via the
# agentic loop — is Project-4 proprietary and lives in the private node-migration repo
# (migration/market_verify.py). This public module provides only config load/validate/resolve.

__all__ = ["load", "validate", "resolve", "MarketConfigError"]
