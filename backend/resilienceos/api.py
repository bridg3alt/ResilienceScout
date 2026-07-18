"""
FastAPI backend — exposes the ResilienceScout engine as JSON.

This is the product spine: any frontend (the React dashboard, or a partner
integration) can drive the whole pipeline through these endpoints.

Run: uvicorn resilienceos.api:app --reload  (from the backend/ directory)
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .building import Building
from . import presets, weather as wx
from .dependency_graph import build_graph, downstream, failed_nodes, single_points_of_failure
from .hazard import analyze_flood, analyze_heatwave, analyze_outage
from .engine import ceri_score, resilience_score, operational_plan, outage_sequence
from .recovery import prioritize, restoration_plan
from .scenarios import compare, budget_optimizer, RETROFITS
from .copilot.context import build_context, build_flood_context
from .copilot.rag import answer as copilot_answer
from .copilot.agents import answer_multiagent

app = FastAPI(title="ResilienceScout API", version="0.2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class BuildingIn(BaseModel):
    # mirrors resilienceos.building.Building; all optional -> sensible defaults
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
    hw = analyze_heatwave(b, day, hvac_active=False)     # passive survivability
    hw_ac = analyze_heatwave(b, day, hvac_active=True)   # operational energy
    out = analyze_outage(b, day, inp.outage_start_hour, inp.outage_duration_h)
    score = resilience_score(hw, out)
    return b, day, hw, hw_ac, out, score


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version, "placeholder_data": presets.DATA_IS_PLACEHOLDER}


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


# =============================================================================================
# ResilienceScout — flood/shelter API.
#
# Additive: everything above (the heat/outage engine) still works unchanged. Every response
# below carries `placeholder: true` while presets.DATA_IS_PLACEHOLDER holds, so the dashboard
# can never present invented figures as surveyed ones.
# =============================================================================================

# Which design flood each operating phase is assessed against.
# TODO(user): confirm the design event per phase with the disaster-management plan.
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


# Latest live flood-depth reading per site, keyed by site_id. In-memory and non-persistent: this
# stands in for the drone/sensor telemetry the fellowship proposes to build, and a demo has no
# business durably storing invented water levels. `_effective_depth` prefers a real reading over
# the phase-based design-flood GUESS, so the dashboard tracks the water instead of a fixed number.
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


def _repaired_for(phase: str, site_id: str, depth_m: float) -> frozenset[str]:
    """
    Recovery phase = the shelter after its ranked minimum repairs are applied. Find that repair
    set from the AS-FLOODED graph (via the existing recovery search), so the caller can re-score
    the shelter with those assets restored. Any other phase repairs nothing.
    """
    if phase != "recovery":
        return frozenset()
    _site, _b, _day, _flood, graph = _site_state(site_id, depth_m)
    plan = restoration_plan(graph, set(failed_nodes(graph)))
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
        "placeholder": presets.DATA_IS_PLACEHOLDER,
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


@app.get("/api/sites/{site_id}/backup")
def api_backup(site_id: str, phase: str = "active_flood", flood_depth_m: float | None = None):
    depth = _effective_depth(site_id, phase, flood_depth_m)
    repaired = _repaired_for(phase, site_id, depth)
    site, _b, _day, flood, _graph = _site_state(site_id, depth, repaired)
    return {
        "site_id": site_id,
        "site_name": site["name"],
        "phase": phase,
        "flood_depth_m": depth,
        "hours_available": flood.backup_hours,
        "hours_required": flood.required_backup_h,
        "adequate": flood.operational,
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
        # precomputed so the detail drawer doesn't need a round-trip per node
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
        })
    return {
        "phase": phase,
        "flood_depth_m": last_depth,
        "shelters": rows,
        "placeholder": presets.DATA_IS_PLACEHOLDER,
    }


@app.post("/api/recovery/prioritize")
def api_recovery(inp: RecoveryIn):
    graphs, failed_by_site = [], {}
    last_depth = _depth_for(inp.phase, inp.flood_depth_m)
    for s in presets.SHELTERS:
        depth = _effective_depth(s["id"], inp.phase, inp.flood_depth_m)
        last_depth = depth
        _site, _b, _day, _flood, graph = _site_state(s["id"], depth)
        graphs.append(graph)
        failed_by_site[s["id"]] = failed_nodes(graph)
    out = prioritize(graphs, failed_by_site)
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
    # Validate the focus shelter up front so an unknown id 404s rather than silently dropping.
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
    """
    presets.get_shelter(inp.site_id)  # 404 on unknown site
    reading = {
        "site_id": inp.site_id,
        "flood_depth_m": inp.flood_depth_m,
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
