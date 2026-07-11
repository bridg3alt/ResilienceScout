"""Format live simulation results into a grounding context string for the copilot."""
from __future__ import annotations

from ..building import Building
from ..hazard import HeatwaveResult, OutageResult, HI_CAUTION, HI_DANGER


def build_context(b: Building, hw: HeatwaveResult, out: OutageResult, score: dict) -> str:
    lines = [
        f"Building: {b.name} ({b.floor_area_m2:.0f} m2, {b.num_floors} floors, "
        f"{b.wall_material} walls, {b.roof_material} roof, {b.glazing} glazing, "
        f"{b.mass_class} thermal mass).",
        f"DER: {b.solar_kwp:.0f} kWp rooftop solar, {b.battery_kwh:.0f} kWh battery, "
        f"generator={'yes' if b.has_generator else 'no'}, critical load {b.critical_load_kw:.0f} kW.",
        f"Resilience score: {score['score']}/100 ({score['band']}). "
        f"Sub-scores habitability={score['components']['habitability']}, "
        f"thermal_headroom={score['components']['thermal_headroom']}, "
        f"backup={score['components']['backup']}.",
        f"Forecast heatwave day: outdoor peak {hw.peak_outdoor:.1f} C.",
        f"PASSIVE survivability (if cooling unavailable): peak indoor {hw.peak_indoor:.1f} C, "
        f"peak heat index {hw.peak_heat_index:.1f} C. "
        f"Safe occupied hours {hw.safe_occupancy_hours}/{hw.occupied_hours}; "
        f"{hw.hours_above_caution}h above caution ({HI_CAUTION:.0f} C), "
        f"{hw.hours_above_danger}h above danger ({HI_DANGER:.0f} C).",
        f"Outage scenario: starts hour {out.start_hour}, lasts {out.duration_h}h. "
        f"Peak indoor during outage {out.peak_indoor_during:.1f} C. "
        + (f"Indoor reaches the caution heat index ~{out.hours_until_unsafe:.0f}h after power loss. "
           if out.hours_until_unsafe is not None
           else "Indoor stays below the caution heat index for the whole outage. ")
        + f"Estimated backup for critical loads: {out.backup_hours:.1f}h.",
    ]
    return "\n".join(lines)
