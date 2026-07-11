"""
FastAPI backend — exposes the ResilienceOS engine as JSON.

This is the product spine / "API platform" from the vision: any frontend (the
Streamlit demo, a future Next.js app, or a partner integration) can drive the
whole pipeline through these endpoints.

Run: uvicorn resilienceos.api:app --reload  (from the backend/ directory)
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .building import Building
from . import weather as wx
from .hazard import analyze_heatwave, analyze_outage
from .engine import resilience_score, operational_plan, outage_sequence
from .scenarios import compare, budget_optimizer, RETROFITS
from .copilot.context import build_context
from .copilot.rag import answer as copilot_answer
from .copilot.agents import answer_multiagent

app = FastAPI(title="ResilienceOS API", version="0.1.0")
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
    return {"status": "ok", "version": "0.1.0"}


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
