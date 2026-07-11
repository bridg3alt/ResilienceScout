"""
Energy Optimization Engine (MVP = rule engine) + resilience scoring.

Produces an operational energy schedule for the forecast heatwave day and a
single headline Resilience Score. This is the "what should the building do"
output that the LLM copilot later explains.
"""
from __future__ import annotations

import pandas as pd

from .building import Building
from .hazard import HeatwaveResult, OutageResult, HI_CAUTION, HI_DANGER
from .solar import pv_generation_kw


def resilience_score(hw: HeatwaveResult, outage: OutageResult) -> dict:
    """
    0-100 composite. Transparent sub-scores so the copilot can explain it.
      - habitability: share of occupied hours that stay safe
      - thermal_headroom: how far peak heat index sits below the danger line
      - backup: outage backup duration vs a 6h target
    """
    habitability = (hw.safe_occupancy_hours / hw.occupied_hours) if hw.occupied_hours else 1.0
    headroom = max(0.0, min(1.0, (HI_DANGER - hw.peak_heat_index) / (HI_DANGER - HI_CAUTION)))
    backup = max(0.0, min(1.0, outage.backup_hours / 6.0))

    score = 100 * (0.45 * habitability + 0.30 * headroom + 0.25 * backup)
    return {
        "score": round(score),
        "band": _band(score),
        "components": {
            "habitability": round(100 * habitability),
            "thermal_headroom": round(100 * headroom),
            "backup": round(100 * backup),
        },
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
