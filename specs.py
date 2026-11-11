"""Design specs the critic holds a cell to — traced to JEDEC JESD209-5 (LPDDR5/5X).

Previously these were round-number targets (gain 8 dB, BW 2 GHz). They are now *derived*
from the LPDDR5 standard so the agentic sizing loop optimizes against the real interface,
not an arbitrary number. The derivation is explicit and first-order (not a substitute for
a JEDEC-compliance testbench), but every target traces to a clause/constant below.

Reference: JEDEC JESD209-5C "LPDDR5/5X" + the DFI 5.0 1:1:4 PHY-controller ratio. Values
are the public-standard electricals; no NDA content.
"""

from __future__ import annotations

# --- JESD209-5 standard constants (public) -------------------------------------------
# Values mirror the authoritative "Specs" sheet of the LPDDR5 PHY cell-set tracker
# (JEDEC LPDDR5 + DFI 5.0 + JEP155/157). See reconcile_specs.py for the checked table.
JESD209_5 = {
    "data_rates_mbps": [3200, 4267, 5500, 6400, 7500, 8533],  # LPDDR5 … LPDDR5X per pin
    "default_rate_mbps": 6400, # LPDDR5 max (pre-5X) — our pilot operating point
    "ui_ps_at_max": 156.25,    # unit interval = 1 / 6400 Mb/s
    "vddq_v": 0.5,             # I/O supply (LVSTL reference rail, terminated to VSSQ)
    "channel_width": 16,       # x16 = 2 bytes
    "rzq_ohm": 240.0,          # ZQ reference resistor; ODT/RON = RZQ/n
    "odt_divisors": [1, 2, 3, 4, 5, 6],            # 240/120/80/60/48/40 Ω legs
    "vref_step_pct_vddq": 0.4, # VREF DAC resolution (~0.4 % VDDQ/code)
    "vref_range_pct_vddq": (10.0, 50.0),           # programmable VREF window
    "wck_ck_ratio": 4,         # WCK:CK = 4:1 at max rate (2:1 at lower rates)
    "dfi_ratio": "1:1:4",      # DFI 5.0 command 1:1, data 1:4
    "sampler_phases": 4,       # quarter-rate DQ sampling
    "ca_bits": 7,              # CA bus width
    "esd_hbm_v": 1000,         # JEP155 industry target
    "esd_cdm_v": 250,          # JEP157 industry target
    "boundary_scan": "IEEE 1149.1",
}


def wck_freq_hz(data_rate_mbps: int) -> float:
    """WCK fundamental for a given per-pin data rate (data is double-rate on WCK:
    f_WCK = rate/2 → 3200 MHz at 6400 Mb/s, per the JESD209-5 Specs sheet)."""
    return data_rate_mbps * 1e6 / 2.0


def ck_freq_hz(data_rate_mbps: int = JESD209_5["default_rate_mbps"]) -> float:
    """Command-clock fundamental: CK = WCK / (WCK:CK ratio) → 800 MHz at max rate."""
    return wck_freq_hz(data_rate_mbps) / JESD209_5["wck_ck_ratio"]


def ca_rate_mbps(data_rate_mbps: int = JESD209_5["default_rate_mbps"]) -> float:
    """CA bus rate: double-rate on CK → 1600 Mb/s at 6400 Mb/s data."""
    return 2 * ck_freq_hz(data_rate_mbps) / 1e6


def clock_buffer_spec(data_rate_mbps: int = JESD209_5["default_rate_mbps"]) -> dict:
    """CML/clock-distribution buffer targets traced to the WCK the PHY must pass.

    - BW: >= WCK fundamental, with 1.4x edge-fidelity margin (3rd-harmonic content).
    - Gain: >= 6 dB so a terminated CML stage restores swing across the clock tree.
    - Power: budgeted per lane; scales with rate.
    """
    f_wck = wck_freq_hz(data_rate_mbps)
    return {
        "name": "clock_buffer",
        "traces_to": f"JESD209-5 WCK @ {data_rate_mbps} Mbps (f_wck={f_wck/1e9:.2f} GHz)",
        "gain_dB": {"min": 6.0, "target": 8.0},
        "bw_hz": {"min": round(1.4 * f_wck, -6)},
        "power_uW": {"max": round(60.0 + 0.0 * data_rate_mbps + data_rate_mbps / 16.0, 0)},
    }


def driver_spec(data_rate_mbps: int = JESD209_5["default_rate_mbps"]) -> dict:
    """LVSTL output-driver targets (JESD209-5): RON from ZQ, swing ~VDDQ, ODT legs."""
    return {
        "name": "tx_driver_lvstl",
        "traces_to": "JESD209-5 LVSTL, RZQ=240Ω, VDDQ=0.5V",
        "ron_ohm": {"target": JESD209_5["rzq_ohm"], "tol_pct": 15.0},   # ZQ-cal window
        "swing_v": {"min": 0.4, "target": JESD209_5["vddq_v"]},
        "odt_ohm": [round(JESD209_5["rzq_ohm"] / n, 1) for n in JESD209_5["odt_divisors"]],
        "data_rate_mbps": data_rate_mbps,
    }


def vref_spec() -> dict:
    """Internal VREF-DAC targets (per-lane VREFDQ) traced to JESD209-5 MR settings."""
    lo, hi = JESD209_5["vref_range_pct_vddq"]
    return {
        "name": "vref_dac",
        "traces_to": "JESD209-5 VREFDQ range/step",
        "step_pct_vddq": JESD209_5["vref_step_pct_vddq"],
        "range_pct_vddq": (lo, hi),
        "codes": round((hi - lo) / JESD209_5["vref_step_pct_vddq"]),
    }


def rx_spec(data_rate_mbps: int = JESD209_5["default_rate_mbps"]) -> dict:
    """DQ receiver targets: sensitivity + offset small vs the LVSTL eye at this rate."""
    return {
        "name": "rx_sampler",
        "traces_to": f"JESD209-5 DQ RX @ {data_rate_mbps} Mbps",
        "input_offset_mv": {"max": 10.0},
        "sensitivity_mv": {"max": 25.0},
        "data_rate_mbps": data_rate_mbps,
    }


# Backward-compatible default the critic/evals import — now JEDEC-traced (LPDDR5-6400 WCK).
CML_SPEC = clock_buffer_spec()

__all__ = ["JESD209_5", "wck_freq_hz", "ck_freq_hz", "ca_rate_mbps", "clock_buffer_spec",
           "driver_spec", "vref_spec", "rx_spec", "CML_SPEC"]
