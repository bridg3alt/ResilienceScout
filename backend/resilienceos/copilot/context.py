"""Format live simulation results into a grounding context string for the copilot."""
from __future__ import annotations

from ..building import Building
from ..hazard import HeatwaveResult, OutageResult, FloodResult, HI_CAUTION, HI_DANGER


def build_context(b: Building, hw: HeatwaveResult, out: OutageResult, score: dict) -> str:
    lines = [
        f"Building: {b.name} ({b.floor_area_m2:.0f} m2, {b.num_floors} floors, "
        f"{b.wall_material} walls, {b.roof_material} roof, {b.glazing} glazing, "
        f"{b.mass_class} thermal mass).",
        f"DER: {b.solar_kwp:.0f} kWp rooftop solar, {b.battery_kwh:.0f} kWh battery, "
        f"generator={'yes' if b.has_generator else 'no'}, critical load {b.critical_load_kw:.0f} kW.",
        f"Resilience score: {score['score']}/100 ({score['band']}). "
        f"Sub-scores habitability={score['components']['habitability']}, "
        f"thermal_exceedance={score['components']['thermal_exceedance']}, "
        f"backup={score['components']['backup']}.",
        f"Forecast heatwave day: outdoor peak {hw.peak_outdoor:.1f} C.",
        f"PASSIVE survivability (if cooling unavailable): peak indoor {hw.peak_indoor:.1f} C, "
        f"peak heat index {hw.peak_heat_index:.1f} C. "
        f"Safe occupied hours {hw.safe_occupancy_hours}/{hw.occupied_hours}; "
        f"{hw.hours_above_caution}h above caution ({HI_CAUTION:.0f} C), "
        f"{hw.hours_above_danger}h above danger ({HI_DANGER:.0f} C); "
        f"cumulative heat exposure {hw.exceedance_degh:.1f} degree-hours above caution.",
        f"Outage scenario: starts hour {out.start_hour}, lasts {out.duration_h}h. "
        f"Peak indoor during outage {out.peak_indoor_during:.1f} C. "
        + (f"Indoor reaches the caution heat index ~{out.hours_until_unsafe:.0f}h after power loss. "
           if out.hours_until_unsafe is not None
           else "Indoor stays below the caution heat index for the whole outage. ")
        + f"Estimated backup for critical loads: {out.backup_hours:.1f}h.",
    ]
    return "\n".join(lines)


def _shelter_block(name: str, pop_served: int, ceri: dict, flood: FloodResult,
                   spofs: list, is_focus: bool) -> str:
    """One grounded paragraph for a single shelter — the flood analogue of build_context."""
    failed = ", ".join(flood.failed_equipment) if flood.failed_equipment else "none"
    spof_txt = ", ".join(spofs) if spofs else "none"
    marker = "  [CURRENTLY SELECTED SHELTER]" if is_focus else ""
    return (
        f"{name} (serves {pop_served} people).{marker}\n"
        f"  CERI (Climate Energy Readiness Index): {ceri['score']}/100 ({ceri['band']}). "
        f"Sub-scores energy_readiness={ceri['components']['energy_readiness']}, "
        f"flood_readiness={ceri['components']['flood_readiness']}, "
        f"backup_duration={ceri['components']['backup_duration']}, "
        f"critical_vulnerabilities={ceri['components']['critical_vulnerabilities']}.\n"
        f"  Can carry its critical load: {'YES' if flood.operational else 'NO'}. "
        f"Backup {flood.backup_hours:.1f}h available vs {flood.required_backup_h:.0f}h required. "
        f"Surviving DER: {flood.surviving_der['solar_kwp']:.0f} kWp solar, "
        f"{flood.surviving_der['battery_kwh']:.0f} kWh battery, "
        f"generator={'yes' if flood.surviving_der['has_generator'] else 'no'}.\n"
        f"  Flooded/offline equipment: {failed}. "
        f"Single points of failure (lose it and the shelter goes dark): {spof_txt}."
        + (f"\n  Why it fails: {flood.failure_reason}." if flood.failure_reason else "")
    )


def build_flood_context(shelters: list[dict], focus_site_id: str,
                        phase: str, flood_depth_m: float) -> str:
    """
    Grounding context for the FLOOD copilot, mirroring build_context's contract.

    `shelters` is a list of already-computed dicts (one per shelter), each with:
      id, name, pop_served, ceri (engine.ceri_score output), flood (hazard.FloodResult),
      spofs (list[str]).
    Grounds in EVERY shelter so cross-shelter questions ("which should we reinforce first")
    and single-site questions both resolve against real Block A/B/C numbers — never the
    heatwave stub.
    """
    header = (
        f"Scenario: {phase.replace('_', ' ')} phase, assessed against a "
        f"{flood_depth_m:.1f} m flood. All numbers below are live model output for the "
        f"real emergency shelters; ground every answer in them and name the specific shelters."
    )
    blocks = [
        _shelter_block(
            s["name"], s["pop_served"], s["ceri"], s["flood"], s["spofs"],
            is_focus=(s["id"] == focus_site_id),
        )
        for s in shelters
    ]
    return header + "\n\n" + "\n\n".join(blocks)
