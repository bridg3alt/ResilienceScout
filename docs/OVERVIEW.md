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
| `presets.py` | **The data-provenance chokepoint.** Flood line, equipment elevations, shelter inventory, population. Two tiers: SOURCED (measured/cited) vs INVENTED (`TODO(user)`), with `UNSURVEYED_VALUES` / `SURVEYED_VALUES` as the machine-readable registry the UI notice is derived from. |
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

Every response carries `placeholder: true` while `DATA_IS_PLACEHOLDER` is set. `/api/sites` and
`/health` additionally carry `unsurveyed` (and `/api/sites` carries `surveyed`) — the named
provenance registry the dashboard notice renders from.

---

## The real-vs-invented ledger

The method is demonstrable, and after the 2026-07 surveys most of the numbers are too. This is the
honest split, kept current with `presets.py`.

**Current state.** Both sides of the model are anchored to measurements. Equipment elevations
(six of eight), the DER nameplate, floor area and the grid topology are surveyed. The **vertical
datum is now closed**: finished floor level is tied to MSL (11.84 m) and to external grade
(0.18 m step). The **2018 flood line is observed** — 0.82 m above finished floor at the Decennial
Block **main entrance lobby**, evidenced by wall staining — so `FLOOD_LINE_M` is sourced rather
than guessed. Survey uncertainty (0.03 m) is recorded, so `AT_RISK_MARGIN_M` is derived at 2σ
rather than chosen.

Four values remain provisional; they are enumerated in code as `presets.UNSURVEYED_VALUES` and
listed under *Still provisional* below.

The vertical **datum** is enforced rather than assumed: every elevation is metres above finished
floor level, and any external figure must be converted through `presets.depth_above_floor()`,
which raises rather than guessing if a required survey constant is missing. `POST
/api/observations` requires an explicit `datum` and rejects any reading it cannot honestly
convert. Now that the MSL tie exists, above-MSL readings convert — the raw reading and its datum
are stored alongside the converted depth so the conversion stays auditable.

### Real

- **Digital twin physics.** 5R1C ISO-13790 via `rcbsim` (Jayathissa et al., *Applied Energy*
  202, 2017; ETH Zürich, MIT). Sanity-checked by `backend/validate_physics.py`.
- **Weather.** Live Open-Meteo forecast + history. Verified resolving at the corrected campus
  coordinates (Kodakara: 10.3595, 76.2859) — ~23 °C, 99% RH, monsoon-plausible for July.
- **All the logic** — flood inundation per asset, dependency-graph SPOF detection, exhaustive
  recovery search, CERI scoring, budget optimization. Covered by 56 passing regression tests.
- **Campus coordinates.** SOURCED and corrected: were 10.5276, 76.2144 (Thrissur *city*,
  ~19 km north — every weather call was keyed to the wrong town). Now the Kodakara campus.

### Surveyed (2026-07-18, `presets.SURVEYED_VALUES`)

- **Vertical datum** — `FINISHED_FLOOR_LEVEL_MSL_M = 11.84`, `GROUND_TO_FLOOR_STEP_M = 0.18`.
  One open caveat: this figure and the wall mark satisfy `12.66 − 11.84 = 0.82` exactly against
  regional marker CKD05 8 km away. Confirm it was measured, not back-computed — `docs/SURVEY.md`
  §3.1.
- **`FLOOD_LINE_M = 0.82`** — observed August 2018 mark, wall staining, main entrance lobby.
- **`EQUIPMENT_ELEVATION_M`** — six of eight measured on site (actuals, not code minimums, which
  matters: assuming code-minimum biases toward falsely reporting a shelter safe). `solar_panels`
  and `road_access` are still estimated.
- **DER nameplate** — 18.0 kWp solar, 40 kWh LiFePO4, 62.5 kVA diesel with ATS.
- **`SURVEY_UNCERTAINTY_M = 0.03`** → `AT_RISK_MARGIN_M` derived at 2σ.
- **Grid topology** — 11 kV substation confirmed upstream of the transformer; UPS confirmed as
  backing the IT load only (2.0 kW) and wired so it never gates shelter power.

### Still provisional (`presets.UNSURVEYED_VALUES`)

- **`pop_served`** — still the pre-survey 500. The survey measured *daily occupancy* (350–450),
  a different quantity. Drives the recovery ranking, so leaving it invented leaves the
  recommendations invented.
- **`critical_load_kw`** — two survey records disagree: the circuit itemisation sums to 20.0 kW
  against a reported total of 18.0 kW. Held as data (`critical_load_discrepancy_kw()`) rather
  than a comment, so it cannot be forgotten.
- **`substation_elevation`** — never measured, so the substation never floods in the model. Its
  graph node reports `unknown` rather than `ok` so the gap stays visible on the map.
- **`REPAIR_EFFORT_H`** (`recovery.py`) — the substation falls through to a generic 8 h default.

Also still modelled rather than derived: **`FLOOD_SCENARIOS_M`**, the return-period ladder. One
observed point does not give return periods; that needs terrain data (LiDAR/photogrammetry), which
is the explicit ask of this application. Note the `extreme` band was removed in the 2026-07 update
— confirm that was deliberate, as it cuts the modelled envelope optimistically.

And **`REQUIRED_BACKUP_H = 12.0`** — **no standard to copy.** The Kerala State Minimum Standards
of Relief (KSDMA, Ed. 1, 9 Jul 2020) requires only that power "shall be ensured" and lighting
"made available", with no duration. NDMA is no more specific. So 12 h is *our* design choice, not
a regulatory threshold — never claim a shelter "meets the standard" on backup hours.

**How the honesty is enforced in code:** `DATA_IS_PLACEHOLDER` is *derived* — it is
`bool(UNSURVEYED_VALUES)`, not a hand-set flag — and flows to `placeholder: true` on every API
response. The dashboard renders a persistent, non-dismissible notice reading *"N of M values still
provisional"*, which expands to name what was measured and what was not, straight from the same
registry. It cannot be cleared by editing a boolean: the only way to clear it is to replace the
named values with measurements. **[docs/SURVEY.md](SURVEY.md)** §7 is exactly what that takes.

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
