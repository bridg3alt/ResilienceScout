"""
FastAPI backend — exposes the ResilienceScout engine as JSON.

This is the product spine: any frontend (the React dashboard, or a partner
integration) can drive the whole pipeline through these endpoints.

Run: uvicorn resilienceos.api:app --reload  (from the backend/ directory)
"""
from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .building import Building
from . import presets, weather as wx
from .dependency_graph import (
    build_graph, downstream, failed_nodes, single_points_of_failure, unassessed_sensitivity,
)
from .hazard import analyze_flood, analyze_heatwave, analyze_outage
from .engine import ceri_score, resilience_score, operational_plan, outage_sequence
from .recovery import prioritize, restoration_plan
from .scenarios import compare, budget_optimizer, RETROFITS
from .copilot.context import build_context, build_flood_context
from .copilot.rag import answer as copilot_answer
from .copilot.agents import answer_multiagent

app = FastAPI(title="ResilienceScout API", version="0.2.0")

_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BuildingIn(BaseModel):
    name: str = "Decennial Block"
    latitude: float = 12.9716
    longitude: float = 77.5946
    floor_area_m2: float = 1200.0
    num_floors: int = 3
    window_to_wall_ratio: float = 0.25
    wall_material: str = "brick_plaster"
    roof_material: str = "rcc_bare"
    glazing: str = "single_clear"
    mass_class: str = "heavy"
    has_hvac: bool = True
    hvac_capacity_w_per_m2: float = 80.0
    occupancy_peak: int = 120
    solar_kwp: float = 20.0
    battery_kwh: float = 0.0
    has_generator: bool = False
    generator_rated_kw: float = 0.0
    generator_runtime_h: float = 0.0
    t_set_cooling: float = 26.0
    critical_load_kw: float = 5.0


class AnalyzeIn(BaseModel):
    building: BuildingIn
    outage_start_hour: int = 14
    outage_duration_h: int = 6


class CopilotIn(AnalyzeIn):
    question: str = "What should this building do before tomorrow's heatwave, and why?"
    multiagent: bool = False


@lru_cache(maxsize=64)
def _day_for(lat: float, lon: float):
    return wx.hottest_day(wx.fetch_forecast(lat, lon, days=3))


def _run(inp: AnalyzeIn):
    b = Building(**inp.building.model_dump())
    day = _day_for(b.latitude, b.longitude)
    hw = analyze_heatwave(b, day, hvac_active=False)
    hw_ac = analyze_heatwave(b, day, hvac_active=True)
    out = analyze_outage(b, day, inp.outage_start_hour, inp.outage_duration_h)
    score = resilience_score(hw, out)
    return b, day, hw, hw_ac, out, score


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": app.version,
        "placeholder_data": presets.DATA_IS_PLACEHOLDER,
        "unsurveyed": presets.UNSURVEYED_VALUES,
        "surveyed_count": len(presets.SURVEYED_VALUES),
        "reported_count": len(presets.REPORTED_VALUES),
        "derived_count": len(presets.DERIVED_VALUES),
    }


@app.get("/options")
def options():
    from .building import WALL_U, ROOF_U, GLAZING, MASS_CLASS
    return {
        "wall_material": list(WALL_U),
        "roof_material": list(ROOF_U),
        "glazing": list(GLAZING),
        "mass_class": list(MASS_CLASS),
        "retrofits": {k: v["label"] for k, v in RETROFITS.items()},
    }


@app.post("/analyze")
def analyze(inp: AnalyzeIn):
    b, day, hw, hw_ac, out, score = _run(inp)
    return {
        "resilience_score": score,
        "heatwave_passive": hw.to_dict(),
        "heatwave_ac_peak_cooling_kw": max(r["cooling_kw"] for r in hw_ac.profile),
        "outage": out.to_dict(),
        "operational_plan": operational_plan(b, day, hw),
        "outage_sequence": outage_sequence(b, out),
    }


@app.post("/scenario/{intervention}")
def scenario(intervention: str, inp: AnalyzeIn):
    b, day, *_ = _run(inp)
    return compare(b, day, intervention, inp.outage_start_hour, inp.outage_duration_h)


@app.post("/budget/{budget_inr}")
def budget(budget_inr: float, inp: AnalyzeIn):
    b, day, *_ = _run(inp)
    return budget_optimizer(b, day, budget_inr, inp.outage_start_hour, inp.outage_duration_h)


@app.post("/copilot")
def copilot(inp: CopilotIn):
    b, day, hw, hw_ac, out, score = _run(inp)
    ctx = build_context(b, hw, out, score)
    if inp.multiagent:
        return answer_multiagent(inp.question, ctx)
    return copilot_answer(inp.question, ctx)


PHASE_DEPTH_M = {
    "preparedness": presets.FLOOD_SCENARIOS_M["moderate"],
    "active_flood": presets.FLOOD_SCENARIOS_M["severe"],
    "recovery": presets.FLOOD_SCENARIOS_M["severe"],
}


class RecoveryIn(BaseModel):
    phase: str = "recovery"
    flood_depth_m: float | None = None


def _depth_for(phase: str, explicit: float | None = None) -> float:
    if explicit is not None:
        return explicit
    if phase not in PHASE_DEPTH_M:
        raise HTTPException(400, f"unknown phase {phase!r}; expected one of {list(PHASE_DEPTH_M)}")
    return PHASE_DEPTH_M[phase]


_OBSERVATIONS: dict[str, dict] = {}


def _effective_depth(site_id: str, phase: str, explicit: float | None = None) -> float:
    """Explicit override wins; else the live observation for this site; else the phase guess."""
    if explicit is not None:
        return explicit
    obs = _OBSERVATIONS.get(site_id)
    if obs is not None:
        return obs["flood_depth_m"]
    return _depth_for(phase)


def _site_state(site_id: str, depth_m: float, repaired: frozenset[str] = frozenset()):
    """
    (site, building, day, flood, graph) for one shelter. Reuses the cached weather day.

    `repaired` restores the named assets (the "after the flood" recovery phase) so the shelter
    is re-scored on the mended resource set. Empty by default = as-flooded state.
    """
    try:
        site = presets.get_shelter(site_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    b = Building(**site["building"])
    day = _day_for(b.latitude, b.longitude)
    flood = analyze_flood(b, day, depth_m, repaired=repaired)
    graph = build_graph(site, b, flood, repaired=repaired)
    return site, b, day, flood, graph


def _adequacy_check(site_id: str, depth_m: float):
    """
    Predicate for the recovery search: does repairing `repaired` let the shelter carry its
    critical load for the required window?

    This is what makes the recovery phase answer the operational question rather than a wiring
    one. `shelter_powered()` only asks whether a source is still connected — at 1.2 m the roof
    inverter survives, so the graph reads powered while the energy model reports 0 h of backup.
    Without this check the search concluded "nothing to repair" on a shelter scoring Critical.
    """
    site = presets.get_shelter(site_id)
    b = Building(**site["building"])
    day = _day_for(b.latitude, b.longitude)

    def is_adequate(repaired: frozenset[str]) -> bool:
        return analyze_flood(b, day, depth_m, repaired=repaired).operational

    return is_adequate


def _repaired_for(phase: str, site_id: str, depth_m: float) -> frozenset[str]:
    """
    Recovery phase = the shelter after its ranked minimum repairs are applied. Find that repair
    set from the AS-FLOODED graph (via the existing recovery search), so the caller can re-score
    the shelter with those assets restored. Any other phase repairs nothing.
    """
    if phase != "recovery":
        return frozenset()
    _site, _b, _day, _flood, graph = _site_state(site_id, depth_m)
    plan = restoration_plan(
        graph, set(failed_nodes(graph)), _adequacy_check(site_id, depth_m)
    )
    return frozenset(plan["repairs"])


@app.get("/api/sites")
def api_sites():
    return {
        "sites": [
            {
                "id": s["id"],
                "name": s["name"],
                "pop_served": s["pop_served"],
                "latitude": s["building"]["latitude"],
                "longitude": s["building"]["longitude"],
                "solar_kwp": s["building"]["solar_kwp"],
                "battery_kwh": s["building"]["battery_kwh"],
                "critical_load_kw": s["building"]["critical_load_kw"],
            }
            for s in presets.SHELTERS
        ],
        "phases": list(PHASE_DEPTH_M),
        "flood_scenarios_m": presets.FLOOD_SCENARIOS_M,
        "hazard_reference": {
            "flood_line_m": presets.FLOOD_LINE_M,
            "survey_uncertainty_m": presets.SURVEY_UNCERTAINTY_M,
            "at_risk_margin_m": presets.AT_RISK_MARGIN_M,
            "equipment_elevation_m": presets.EQUIPMENT_ELEVATION_M,
        },
        "placeholder": presets.DATA_IS_PLACEHOLDER,
        "unsurveyed": presets.UNSURVEYED_VALUES,
        "surveyed": presets.SURVEYED_VALUES,
        "derived": presets.DERIVED_VALUES,
        "reported": presets.REPORTED_VALUES,
        "capacity_check": {
            s["id"]: {
                "pop_served_claimed": s["pop_served"],
                "area_upper_bound": presets.shelter_capacity_upper_bound(s["id"]),
                "exceeds_bound": presets.pop_served_exceeds_area_bound(s["id"]),
                "overstated_by": presets.pop_served_overstatement(s["id"]),
                "basis": (
                    f"{s['building']['floor_area_m2']:.0f} m2 surveyed floor area / "
                    f"{presets.SHELTER_AREA_PER_PERSON_M2} m2 per person "
                    "(Kerala State Minimum Standards of Relief, KSDMA Ed. 1, 9 Jul 2020)"
                ),
            }
            for s in presets.SHELTERS
        },
    }


@app.get("/api/sites/{site_id}/ceri")
def api_ceri(site_id: str, phase: str = "preparedness", flood_depth_m: float | None = None):
    depth = _effective_depth(site_id, phase, flood_depth_m)
    repaired = _repaired_for(phase, site_id, depth)
    site, b, _day, flood, graph = _site_state(site_id, depth, repaired)
    c = ceri_score(flood, graph, b)
    return {
        "site_id": site_id,
        "site_name": site["name"],
        "phase": phase,
        "flood_depth_m": depth,
        **c,
    }


def _backup_across_load_range(site_id: str, depth: float, repaired: frozenset[str]) -> dict:
    """
    Ride-through recomputed at BOTH ends of the unreconciled critical load.

    The survey recorded critical load twice and the records disagree (18.0 kW reported, 20.0 kW
    itemised). `critical_load_kw` carries the lower one, so the headline backup figure is the
    optimistic reading of a number nobody has settled. Reporting only that would present a
    disagreement as a fact.

    So the endpoint reports the interval. `hours_available` stays the model's own figure for
    backward compatibility; `hours_range` is what the dashboard should show.
    """
    low_kw, high_kw = presets.critical_load_range_kw()
    site = presets.get_shelter(site_id)
    day = _day_for(site["building"]["latitude"], site["building"]["longitude"])

    hours = {}
    for label, load_kw in (("high_load", high_kw), ("low_load", low_kw)):
        b = Building(**{**site["building"], "critical_load_kw": load_kw})
        hours[label] = analyze_flood(b, day, depth, repaired=repaired).backup_hours

    return {
        "critical_load_range_kw": [low_kw, high_kw],
        "critical_load_reconciled": presets.critical_load_is_reconciled(),
        "hours_min": hours["high_load"],
        "hours_max": hours["low_load"],
    }


@app.get("/api/sites/{site_id}/backup")
def api_backup(site_id: str, phase: str = "active_flood", flood_depth_m: float | None = None):
    depth = _effective_depth(site_id, phase, flood_depth_m)
    repaired = _repaired_for(phase, site_id, depth)
    site, _b, _day, flood, _graph = _site_state(site_id, depth, repaired)
    rng = _backup_across_load_range(site_id, depth, repaired)
    return {
        "site_id": site_id,
        "site_name": site["name"],
        "phase": phase,
        "flood_depth_m": depth,
        "hours_available": flood.backup_hours,
        "hours_required": flood.required_backup_h,
        "adequate": flood.operational,
        "adequate_worst_case": rng["hours_min"] >= flood.required_backup_h,
        "hours_range": rng,
        "surviving_der": flood.surviving_der,
        "failed_equipment": flood.failed_equipment,
        "placeholder": flood.placeholder,
    }


@app.get("/api/dependency-graph/{site_id}")
def api_dependency_graph(site_id: str, phase: str = "active_flood",
                         flood_depth_m: float | None = None):
    depth = _effective_depth(site_id, phase, flood_depth_m)
    repaired = _repaired_for(phase, site_id, depth)
    _site, _b, _day, _flood, graph = _site_state(site_id, depth, repaired)
    spofs = single_points_of_failure(graph)
    return {
        **graph,
        "phase": phase,
        "flood_depth_m": depth,
        "single_points_of_failure": spofs,
        "unassessed_sensitivity": unassessed_sensitivity(graph),
        "cascades": {n["id"]: downstream(graph, n["id"]) for n in graph["nodes"]},
    }


@app.get("/api/shelters/status")
def api_shelter_status(phase: str = "active_flood", flood_depth_m: float | None = None):
    rows = []
    last_depth = _depth_for(phase, flood_depth_m)
    for s in presets.SHELTERS:
        depth = _effective_depth(s["id"], phase, flood_depth_m)
        last_depth = depth
        repaired = _repaired_for(phase, s["id"], depth)
        site, b, _day, flood, graph = _site_state(s["id"], depth, repaired)
        c = ceri_score(flood, graph, b)
        rows.append({
            "site_id": s["id"],
            "site_name": s["name"],
            "pop_served": s["pop_served"],
            "operational": flood.operational,
            "backup_remaining_h": flood.backup_hours,
            "backup_required_h": flood.required_backup_h,
            "failure_reason": flood.failure_reason,
            "failed_equipment": flood.failed_equipment,
            "ceri": c["score"],
            "band": c["band"],
            "backup_range": _backup_across_load_range(s["id"], depth, repaired),
        })
    return {
        "phase": phase,
        "flood_depth_m": last_depth,
        "shelters": rows,
        "critical_load_reconciled": presets.critical_load_is_reconciled(),
        "placeholder": presets.DATA_IS_PLACEHOLDER,
    }


@app.post("/api/recovery/prioritize")
def api_recovery(inp: RecoveryIn):
    graphs, failed_by_site, adequacy = [], {}, {}
    last_depth = _depth_for(inp.phase, inp.flood_depth_m)
    for s in presets.SHELTERS:
        depth = _effective_depth(s["id"], inp.phase, inp.flood_depth_m)
        last_depth = depth
        _site, _b, _day, _flood, graph = _site_state(s["id"], depth)
        graphs.append(graph)
        failed_by_site[s["id"]] = failed_nodes(graph)
        adequacy[s["id"]] = _adequacy_check(s["id"], depth)
    out = prioritize(graphs, failed_by_site, adequacy_by_site=adequacy)
    return {"phase": inp.phase, "flood_depth_m": last_depth, **out}


class FloodCopilotIn(BaseModel):
    site_id: str = "decennial_block"
    phase: str = "active_flood"
    flood_depth_m: float | None = None
    question: str = "What should we reinforce first at this building, and why?"
    multiagent: bool = False


@app.post("/api/copilot")
def api_copilot(inp: FloodCopilotIn):
    """
    Flood-aware copilot: grounds the LLM in the REAL shelters' live flood/CERI/dependency data
    (the same numbers the dashboard shows), not the heat-engine stub. Reuses the existing RAG /
    multi-agent pipeline unchanged — only the grounding context differs.
    """
    presets.get_shelter(inp.site_id)

    shelters, last_depth = [], _depth_for(inp.phase, inp.flood_depth_m)
    for s in presets.SHELTERS:
        depth = _effective_depth(s["id"], inp.phase, inp.flood_depth_m)
        last_depth = depth
        repaired = _repaired_for(inp.phase, s["id"], depth)
        _site, b, _day, flood, graph = _site_state(s["id"], depth, repaired)
        c = ceri_score(flood, graph, b)
        shelters.append({
            "id": s["id"],
            "name": s["name"],
            "pop_served": s["pop_served"],
            "ceri": c,
            "flood": flood,
            "spofs": single_points_of_failure(graph),
        })

    ctx = build_flood_context(shelters, inp.site_id, inp.phase, last_depth)
    result = answer_multiagent(inp.question, ctx) if inp.multiagent else copilot_answer(inp.question, ctx)
    result["site_id"] = inp.site_id
    result["phase"] = inp.phase
    return result


class ObservationIn(BaseModel):
    site_id: str
    flood_depth_m: float
    datum: str
    source: str = "sensor"
    timestamp: str | None = None


@app.post("/api/observations")
def api_post_observation(inp: ObservationIn):
    """
    Ingest one live flood-depth reading for a site and store it as the latest for that site.

    This endpoint is designed to accept live telemetry from drone or sensor hardware. That
    hardware does not exist yet — building it is the explicit ask of this fellowship application.
    Until then scripts/simulate_drone.py stands in for it. Once a reading exists, the whole
    dashboard scores against it (see `_effective_depth`) instead of the fixed phase-based guess,
    so the numbers track the real water with zero manual entry.

    The reading is converted into the model's datum (metres above finished floor) before storage.
    If that conversion needs a survey constant that has not been measured yet, the reading is
    REJECTED with 400 rather than stored at face value — a loud failure beats a plausible wrong
    number, because a datum error is invisible in the output.
    """
    presets.get_shelter(inp.site_id)
    try:
        depth_above_floor = presets.depth_above_floor(inp.flood_depth_m, inp.datum)
    except presets.DatumError as e:
        raise HTTPException(400, str(e))

    reading = {
        "site_id": inp.site_id,
        "flood_depth_m": depth_above_floor,
        "datum": presets.ELEVATION_DATUM,
        "raw_reading_m": inp.flood_depth_m,
        "raw_datum": inp.datum,
        "source": inp.source,
        "timestamp": inp.timestamp,
    }
    _OBSERVATIONS[inp.site_id] = reading
    return {"stored": reading, "placeholder": presets.DATA_IS_PLACEHOLDER}


@app.get("/api/observations")
def api_get_observations():
    """Latest live reading per site (empty until telemetry — real or simulated — arrives)."""
    return {"observations": _OBSERVATIONS, "placeholder": presets.DATA_IS_PLACEHOLDER}


@app.get("/api/ceri-trend/{site_id}")
def api_ceri_trend(site_id: str):
    """
    CERI across the modelled flood scenarios — the x-axis for the dashboard trend chart.

    NOTE: this is a hazard-severity sweep, NOT a time series. There is no historical CERI to
    plot: nothing has been surveyed and no readings are logged. Presenting a fabricated
    time axis would imply monitoring the project does not do.
    """
    points = []
    for label, depth in sorted(presets.FLOOD_SCENARIOS_M.items(), key=lambda kv: kv[1]):
        _site, b, _day, flood, graph = _site_state(site_id, depth)
        c = ceri_score(flood, graph, b)
        points.append({
            "scenario": label,
            "flood_depth_m": depth,
            "ceri": c["score"],
            "components": c["components"],
        })
    return {
        "site_id": site_id,
        "x_axis": "flood_depth_m",
        "points": points,
        "placeholder": presets.DATA_IS_PLACEHOLDER,
    }
