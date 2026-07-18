# ResilienceScout — architecture, and an honest real-vs-invented ledger

**One question:** *is this shelter energy-ready for the flood — and if not, what do we fix
first?* ResilienceScout answers it across a flood's lifecycle (before / during / after) from
minimal building information plus free public weather. This document says what the system
actually does, and — the harder half — which numbers are real and which are placeholders.

The differentiator is not the equipment inspection. It is the **dependency graph** and the
**recovery prioritisation** layered on top of it: a per-asset checklist cannot tell you that
losing the transformer is survivable with a charged battery and fatal without one, or that the
distribution panel is fatal either way because every source is wired through it.

---

## Pipeline

```
Open-Meteo (forecast + history, no key)
        │
        ▼
weather.py ──► building.py ──► twin.py            low-data physics-informed digital twin
                                  │                (5R1C ISO-13790 via rcbsim, ETH Zürich)
                                  ▼
        ┌───────────── hazard.py ─────────────┐   heatwave · outage · flood
        │  analyze_heatwave / _outage / _flood │   + solar.py PV generation
        └───────────────────┬─────────────────┘
                            ▼
    dependency_graph.py ──► engine.py ──► scenarios.py    SPOF · CERI · retrofits
              │                                recovery.py    population-per-repair-hour
              ▼
   presets.py  ◄── ALL placeholder data quarantined here (DATA_IS_PLACEHOLDER)
                            │
                            ▼
        report.py · copilot/ (RAG + Groq) · api.py (FastAPI JSON)
                            │
                            ▼
          React dashboard (Vite + Tailwind + Radix)
```

## Modules

| Module | Responsibility |
|---|---|
| `weather.py` | Open-Meteo forecast + history. Free, keyless. |
| `building.py` | Minimal inputs → geometry, U-values, capacitance → rcbsim 5R1C Zone (ISO 13790). |
| `twin.py` | Hour-by-hour 5R1C thermal simulation. |
| `solar.py` | PV generation from GHI + temperature. |
| `hazard.py` | Heatwave, outage, and **flood** analysis. Flood decides *which* DER survives; the existing energy-balance model (`backup_duration_h`) decides how long it lasts. |
| `presets.py` | **The placeholder chokepoint.** Flood line, equipment elevations, shelter inventory, population. Two tiers: SOURCED (cited) vs INVENTED (`TODO(user)`). |
| `dependency_graph.py` | Shelter → panel → transformer/solar/battery/generator. `single_points_of_failure()` — OR across sources, AND through the panel. |
| `recovery.py` | Exhaustive minimum-effort repair set per shelter, ranked by population restored per repair-hour. |
| `engine.py` | `ceri_score` (flood readiness) + `resilience_score` (heat). Transparent sub-scores; **upper-clamp only** — flooring a reward term is what once made the heat score blind to real gains. |
| `scenarios.py` | Retrofit comparison + budget optimizer (resilience gain per ₹). |
| `copilot/` | ChromaDB RAG (→ TF-IDF fallback) grounded in live sim numbers, Groq LLM (optional). |
| `report.py`, `api.py` | Report generation, FastAPI JSON surface. |

## CERI — Climate Energy Readiness Index

0–100, four transparent sub-scores (`engine.ceri_score`):

| Sub-score | Weight | What it measures |
|---|---|---|
| `energy_readiness` | 0.30 | DER (battery) capacity vs the critical load × required backup window |
| `flood_readiness` | 0.25 | Logistic on the weakest power asset's elevation margin over the flood line |
| `backup_duration` | 0.30 | Surviving ride-through vs `REQUIRED_BACKUP_H` |
| `critical_vulnerabilities` | 0.15 | Single points of failure in the dependency graph |

Bands: ≥75 Resilient · ≥50 Moderate · ≥30 At risk · else Critical.

## API surface (FastAPI)

Heat/legacy: `/health`, `/options`, `/analyze`, `/scenario/{intervention}`,
`/budget/{budget_inr}`, `/copilot`.

Flood domain: `/api/sites`, `/api/sites/{id}/ceri`, `/api/sites/{id}/backup`,
`/api/dependency-graph/{id}`, `/api/shelters/status`, `/api/recovery/prioritize`,
`/api/ceri-trend/{id}`, `/api/copilot`.

Live telemetry: `POST /api/observations` (and `GET /api/observations`). **This endpoint is
designed to accept live telemetry from drone or sensor hardware. That hardware does not exist yet
— building it is the explicit ask of this fellowship application.** Until it does,
`scripts/simulate_drone.py` stands in for it. When a reading exists, the dashboard scores against
that live depth instead of the fixed phase-based guess (`_effective_depth` in `api.py`), and the
UI polls every few seconds so it updates on its own with zero clicks.

Every response carries `placeholder: true` while `DATA_IS_PLACEHOLDER` is set.

---

## The real-vs-invented ledger

The method is demonstrable; the numbers are not. This is the honest split.

**Current state after the site survey.** Equipment elevations, DER nameplate and critical load
are measured. The **2018 flood line is now observed** (0.78 m above finished floor at the
Decennial Block electrical room entrance), so `FLOOD_LINE_M` is sourced rather than guessed, and
the ground-to-floor step (0.18 m) makes above-grade readings convertible.

Still invented: the **design scenario ladder** (`FLOOD_SCENARIOS_M` — one observed point does not
give return periods), `pop_served`, the survey uncertainty, and three elevations. So
`DATA_IS_PLACEHOLDER` stays `True`.

Because the two sides are now mixed, the vertical **datum** is enforced rather than assumed:
every elevation is metres above finished floor level, and any external figure must be converted
through `presets.depth_above_floor()`, which raises instead of guessing when the finished floor
level is unsurveyed. `POST /api/observations` requires an explicit `datum` and returns 400 for a
reading it cannot honestly convert. See `docs/SURVEY.md` §3 for what closes this.

### Real

- **Digital twin physics.** 5R1C ISO-13790 via `rcbsim` (Jayathissa et al., *Applied Energy*
  202, 2017; ETH Zürich, MIT). Sanity-checked by `backend/validate_physics.py`.
- **Weather.** Live Open-Meteo forecast + history. Verified resolving at the corrected campus
  coordinates (Kodakara: 10.3595, 76.2859) — ~23 °C, 99% RH, monsoon-plausible for July.
- **All the logic** — flood inundation per asset, dependency-graph SPOF detection, exhaustive
  recovery search, CERI scoring, budget optimization. Covered by 33 passing regression tests.
- **Campus coordinates.** SOURCED and corrected: were 10.5276, 76.2144 (Thrissur *city*,
  ~19 km north — every weather call was keyed to the wrong town). Now the Kodakara campus.

### Invented (`TODO(user)`, quarantined in `presets.py` + `recovery.py`)

- `FLOOD_LINE_M`, `FLOOD_SCENARIOS_M` — **unsourceable from a desk.** KSDMA publishes flood
  hazard *probability* zones, not depths in metres. Needs the 2018 high-water survey.
- `EQUIPMENT_ELEVATION_M` — must be measured on site. Standards give *minimums*, not actuals;
  assuming code-minimum biases toward falsely reporting a shelter safe.
- `SHELTERS` inventory + `pop_served` — deliberately round numbers so they read as fake.
  `pop_served` drives the recovery ranking, so inventing it invents the recommendations.
- `REPAIR_EFFORT_H` (`recovery.py`) — affects ranking order only; a maintenance-team interview
  settles it.
- `REQUIRED_BACKUP_H = 12.0` — **no standard to copy.** The Kerala State Minimum Standards of
  Relief (KSDMA, Ed. 1, 9 Jul 2020) requires only that power "shall be ensured" and lighting
  "made available", with no duration. So 12 h is *our* design choice, not a regulatory
  threshold — never claim a shelter "meets the standard" on backup hours.

**How the honesty is enforced in code:** `DATA_IS_PLACEHOLDER = True` flows to `placeholder:
true` on every API response and a persistent "DEMO DATA — NOT SURVEYED" banner in the UI. Flip
it to `False` only once every `TODO(user)` (and `REPAIR_EFFORT_H`) is replaced with a surveyed
value. **[docs/SURVEY.md](SURVEY.md)** is exactly what to collect to get there.

---

## Verify

```bash
python -m pytest              # 33 regression tests — flood domain + scoring
cd backend
python validate_physics.py    # twin physics sanity (live weather)
python smoke_pipeline.py      # heatwave → outage → score → plan → retrofits
python smoke_copilot.py       # RAG retrieval + grounded answer
```

Runs fully offline, zero keys. The Groq copilot is the only optional key; without it the
copilot returns the grounded evidence (retrieved guidelines + sim numbers) instead of prose.
