"""
Scenario comparison + a simple budget/retrofit optimizer.

Compares the building "as-is" against candidate interventions (cool roof, more
solar, battery, night ventilation) on resilience metrics, and ranks retrofits by
resilience-improvement-per-rupee.
"""
from __future__ import annotations

from dataclasses import replace

import pandas as pd

from .building import Building
from .hazard import analyze_heatwave, analyze_outage
from .engine import resilience_score

# Indicative retrofit costs (INR). Tune to local quotes.
RETROFITS = {
    "cool_roof": {
        "label": "Cool-roof coating",
        "cost_inr": 60000,
        "apply": lambda b: replace(b, roof_material="cool_roof"),
    },
    "add_solar_10kwp": {
        "label": "+10 kWp rooftop solar",
        "cost_inr": 500000,
        "apply": lambda b: replace(b, solar_kwp=b.solar_kwp + 10),
    },
    "battery_20kwh": {
        "label": "+20 kWh battery storage",
        "cost_inr": 400000,
        "apply": lambda b: replace(b, battery_kwh=b.battery_kwh + 20),
    },
    "double_glazing": {
        "label": "Double-glazed windows",
        "cost_inr": 300000,
        "apply": lambda b: replace(b, glazing="double_lowe"),
    },
}


def _metrics(b: Building, day: pd.DataFrame, outage_start: int, outage_dur: int) -> dict:
    # Resilience = passive survivability when cooling is unavailable (grid-stressed
    # heatwave / outage). With AC forced on, every building looks identical, so we
    # score the free-float condition — that's what retrofits actually move.
    hw = analyze_heatwave(b, day, hvac_active=False)
    out = analyze_outage(b, day, outage_start, outage_dur)
    score = resilience_score(hw, out)
    return {
        "resilience_score": score["score"],            # rounded — for display
        "resilience_score_exact": score["score_exact"],  # unrounded — for ranking/deltas
        "band": score["band"],
        "peak_heat_index": hw.peak_heat_index,
        "safe_occupancy_hours": hw.safe_occupancy_hours,
        "exceedance_degh": hw.exceedance_degh,
        "backup_hours": out.backup_hours,
    }


def compare(b: Building, day: pd.DataFrame, intervention: str,
            outage_start: int = 14, outage_dur: int = 6) -> dict:
    base = _metrics(b, day, outage_start, outage_dur)
    b2 = RETROFITS[intervention]["apply"](b)
    new = _metrics(b2, day, outage_start, outage_dur)
    return {
        "intervention": RETROFITS[intervention]["label"],
        "baseline": base,
        "with_intervention": new,
        "deltas": {k: round(new[k] - base[k], 2)
                   for k in base if isinstance(base[k], (int, float))},
    }


def budget_optimizer(b: Building, day: pd.DataFrame, budget_inr: float,
                     outage_start: int = 14, outage_dur: int = 6) -> dict:
    """Rank retrofits by resilience-score gain per rupee, greedily fit to budget."""
    base = _metrics(b, day, outage_start, outage_dur)
    ranked = []
    for key, spec in RETROFITS.items():
        b2 = spec["apply"](b)
        m = _metrics(b2, day, outage_start, outage_dur)
        # Rank on the UNROUNDED score: a cheap retrofit worth <1 point is still worth doing,
        # and rounding first zeroed it out of the ranking entirely.
        gain = m["resilience_score_exact"] - base["resilience_score_exact"]
        ranked.append({
            "key": key,
            "label": spec["label"],
            "cost_inr": spec["cost_inr"],
            "score_gain": round(gain, 2),
            "gain_per_lakh": round(gain / (spec["cost_inr"] / 100000), 2) if spec["cost_inr"] else 0,
            "backup_gain_h": round(m["backup_hours"] - base["backup_hours"], 1),
            "heat_index_drop": round(base["peak_heat_index"] - m["peak_heat_index"], 2),
            "degh_drop": round(base["exceedance_degh"] - m["exceedance_degh"], 1),
        })
    ranked.sort(key=lambda r: r["gain_per_lakh"], reverse=True)

    # greedy selection within budget
    remaining = budget_inr
    chosen = []
    for r in ranked:
        if r["cost_inr"] <= remaining and r["score_gain"] > 0:
            chosen.append(r["key"])
            remaining -= r["cost_inr"]

    return {
        "budget_inr": budget_inr,
        "baseline_score": base["resilience_score"],
        "ranked": ranked,
        "recommended": chosen,
        "spend_inr": budget_inr - remaining,
    }
