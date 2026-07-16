"""
Energy Optimization Engine (MVP = rule engine) + resilience scoring.

Produces an operational energy schedule for the forecast heatwave day and a
single headline Resilience Score. This is the "what should the building do"
output that the LLM copilot later explains.
"""
from __future__ import annotations

import math

import pandas as pd

from .building import Building
from .hazard import HeatwaveResult, OutageResult, HI_CAUTION
from .solar import pv_generation_kw

# Heat-index degree-hours above caution at which the thermal sub-score halves.
# Chosen against MEASURED exposure from the twin, which spans ~13 C.h (mild) to ~860 C.h
# (severe free-float). An exponential decay was tried first and rejected: exp(-degh/40)
# underflows to 0 above ~200 C.h, which silently re-created the very saturation this replaces.
# A hyperbolic decay keeps resolution across the whole real range.
# TODO(user): re-anchor against surveyed comfort outcomes once field data exists.
DEGH_HALF = 200.0


def resilience_score(hw: HeatwaveResult, outage: OutageResult) -> dict:
    """
    0-100 composite. Transparent sub-scores so the copilot can explain it.
      - habitability: share of occupied hours that stay safe
      - thermal_exceedance: cumulative heat-index degree-hours above the caution line
      - backup: outage backup duration vs a 6h target

    `thermal_exceedance` replaces an earlier peak-based "headroom" term that was clamped to
    zero once the peak heat index passed the danger line. That clamp made the reward term
    saturate while the habitability penalty stayed live, so a retrofit could cut 7.4C off the
    peak and still score WORSE overall. 1/(1+degh/HALF) is strictly decreasing on [0, inf) and
    never reaches zero, so any reduction in degree-hours always raises the sub-score — no dead
    zone in the dangerous regime. It also prices duration, not just the single worst hour.
    """
    habitability = (hw.safe_occupancy_hours / hw.occupied_hours) if hw.occupied_hours else 1.0
    exceedance = 1.0 / (1.0 + hw.exceedance_degh / DEGH_HALF)
    # Upper clamp only: exceeding the 6h backup target earns no extra credit, but the reward
    # end is never floored (that asymmetry is exactly what broke the old headroom term).
    backup = min(1.0, outage.backup_hours / 6.0)

    score = 100 * (0.45 * habitability + 0.30 * exceedance + 0.25 * backup)
    return {
        "score": round(score),
        # Unrounded score for RANKING. Rounding to int destroys sub-point differences, and a
        # cheap-but-real retrofit can easily be worth <1 point — rounding first made the budget
        # optimizer see a 0 gain and refuse to recommend it. Display uses `score`; comparisons
        # must use `score_exact`.
        "score_exact": round(score, 3),
        "band": _band(score),
        "components": {
            "habitability": round(100 * habitability),
            "thermal_exceedance": round(100 * exceedance),
            "backup": round(100 * backup),
        },
    }


def ceri_score(flood, graph: dict, b: Building) -> dict:
    """
    CERI — Climate Energy Readiness Index. 0-100, four transparent sub-scores:

      energy_readiness         DER capacity vs the critical load it must carry
      flood_readiness          how much elevation margin the assets have over the flood line
      backup_duration          surviving ride-through vs the required window
      critical_vulnerabilities single points of failure in the dependency graph

    Follows `resilience_score`'s transparency contract (score / score_exact / band /
    components) and its hard-won rule: clamp the UPPER end only. Flooring a reward term is what
    made the old heat score blind to real improvements, so every sub-score below stays able to
    move in both directions across its whole real range.
    """
    from . import presets
    from .dependency_graph import single_points_of_failure

    # DER capable of carrying critical load. Ratio >= 1 means fully covered; upper-clamped
    # because over-provisioning past the need earns no more credit.
    if b.critical_load_kw > 0:
        der_cover = (b.battery_kwh / b.critical_load_kw) / presets.REQUIRED_BACKUP_H
    else:
        der_cover = 1.0
    energy_readiness = min(1.0, der_cover)

    # Elevation margin of the WEAKEST power-relevant asset over the flood line.
    margins = [
        presets.EQUIPMENT_ELEVATION_M[n["id"]] - presets.FLOOD_LINE_M
        for n in graph["nodes"]
        if n["is_power_source"] and n["id"] in presets.EQUIPMENT_ELEVATION_M
    ]
    if margins:
        worst = min(margins)
        # Logistic on the margin: continuous either side of the flood line, so a deeply
        # submerged asset still scores worse than a marginally submerged one and any
        # re-siting always registers. Clamped at neither end.
        flood_readiness = 1.0 / (1.0 + math.exp(-worst / 0.3))
    else:
        flood_readiness = 0.0

    backup_duration = min(1.0, flood.backup_hours / presets.REQUIRED_BACKUP_H)

    spofs = single_points_of_failure(graph)
    critical_vulnerabilities = 1.0 / (1.0 + len(spofs) / max(presets.CRITICAL_SPOF_LIMIT, 1))

    score = 100 * (
        0.30 * energy_readiness
        + 0.25 * flood_readiness
        + 0.30 * backup_duration
        + 0.15 * critical_vulnerabilities
    )
    return {
        "score": round(score),
        "score_exact": round(score, 3),
        "band": _band(score),
        "components": {
            "energy_readiness": round(100 * energy_readiness),
            "flood_readiness": round(100 * flood_readiness),
            "backup_duration": round(100 * backup_duration),
            "critical_vulnerabilities": round(100 * critical_vulnerabilities),
        },
        "single_points_of_failure": spofs,
        "placeholder": presets.DATA_IS_PLACEHOLDER,
    }


def _band(score: float) -> str:
    if score >= 75:
        return "Resilient"
    if score >= 50:
        return "Moderate"
    if score >= 30:
        return "At risk"
    return "Critical"


def operational_plan(b: Building, day: pd.DataFrame, hw: HeatwaveResult) -> list[dict]:
    """
    Rule-based operational schedule for the forecast heatwave day.
    Each action: {time, action, reason, category}.
    """
    rows = day.reset_index(drop=True)
    peak_hour = int(rows.loc[rows["temp"].idxmax(), "hour"])
    solar = [pv_generation_kw(b.solar_kwp, float(r["ghi"]), float(r["temp"])) for _, r in rows.iterrows()]
    solar_peak_hour = int(max(range(len(solar)), key=lambda i: solar[i])) if any(solar) else 12

    plan: list[dict] = []

    def add(hour, action, reason, category):
        plan.append({
            "time": f"{hour:02d}:00",
            "action": action,
            "reason": reason,
            "category": category,
        })

    # Overnight — charge storage & flush heat
    if b.battery_kwh > 0:
        add(22, "Charge battery to full", "Off-peak grid hours; reserve capacity for tomorrow's peak and any outage.", "storage")
    add(23, "Night-purge ventilation (open up / run fans)",
        "Outdoor air is coolest overnight; flush accumulated heat from the thermal mass before sunrise.", "ventilation")

    # Pre-cool before the heat builds, using early solar
    add(6, "Pre-cool occupied classrooms/offices to lower setpoint",
        f"Cheap morning cooling (solar ramping, mild ambient) banks 'coolth' in the mass before the {peak_hour:02d}:00 peak of {hw.peak_outdoor:.0f}C.",
        "cooling")

    # Ride solar through midday
    if b.solar_kwp > 0:
        add(max(solar_peak_hour - 2, 9), "Run cooling from rooftop solar",
            f"PV output peaks around {solar_peak_hour:02d}:00 (~{max(solar):.0f} kW); self-consume it to cool at near-zero marginal cost.",
            "solar")

    # Peak-heat load management
    add(peak_hour, "Ease mechanical cooling; prioritise fans + shading in low-occupancy rooms",
        f"Indoor heat index peaks near {hw.peak_heat_index:.0f}C; concentrate cooling on occupied critical rooms, coast on stored coolth elsewhere.",
        "load_mgmt")

    # Vulnerability flag
    if hw.hours_above_caution > 0:
        add(peak_hour, "Move occupants to designated cool refuge room(s)",
            f"{hw.hours_above_caution}h above the {HI_CAUTION:.0f}C caution threshold today; keep the most vulnerable in the best-conditioned space.",
            "safety")

    plan.sort(key=lambda a: a["time"])
    return plan


def outage_sequence(b: Building, outage: OutageResult) -> list[dict]:
    """Critical-load / recovery steps for the outage scenario."""
    seq = [
        {"step": "Detect outage", "action": "Switch to backup; drop all non-critical loads",
         "reason": f"Preserve {b.critical_load_kw:.0f} kW of critical load on stored energy."},
        {"step": "Sustain", "action": "Run critical loads on solar + battery",
         "reason": f"Estimated {outage.backup_hours:.1f}h of backup from {b.battery_kwh:.0f} kWh battery + daytime solar."},
    ]
    if outage.hours_until_unsafe is not None:
        seq.append({
            "step": "Thermal watch",
            "action": f"Begin evacuation/relocation planning by hour {outage.hours_until_unsafe:.0f} of the outage",
            "reason": f"Indoor heat index crosses the {HI_CAUTION:.0f}C caution line ~{outage.hours_until_unsafe:.0f}h after power loss.",
        })
    else:
        seq.append({
            "step": "Thermal watch",
            "action": "Occupancy remains within safe limits for the modelled outage window",
            "reason": "Thermal mass holds the indoor heat index below the caution threshold for the full outage.",
        })
    seq.append({"step": "Recovery", "action": "On restoration: pre-cool from thermal setback, then recharge battery",
                "reason": "Return to normal setpoints gradually to avoid a demand spike; refill storage for the next event."})
    return seq
