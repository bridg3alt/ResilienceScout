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
| `presets.py` | **The data-provenance chokepoint.** Flood line, equipment elevations, shelter inventory, population. Four tiers: SOURCED (measured/cited), DERIVED (bounded from a surveyed input + a cited standard), REPORTED (stated by the site owner, unverified), INVENTED (`TODO(user)`), with `SURVEYED_VALUES` / `DERIVED_VALUES` / `REPORTED_VALUES` / `UNSURVEYED_VALUES` as the machine-readable registries the UI notice is derived from. |
| `dependency_graph.py` | Shelter → panel → transformer/solar/battery/generator. `single_points_of_failure()` — OR across sources, AND through the panel. |
| `recovery.py` | Exhaustive minimum-effort repair set per shelter, ranked by population restored per repair-hour. |
| `engine.py` | `ceri_score` (flood readiness) + `resilience_score` (heat). Transparent sub-scores; **upper-clamp only** — flooring a reward term is what once made the heat score blind to real gains. |
| `scenarios.py` | Retrofit comparison + budget optimizer (resilience gain per ₹). |
| `copilot/` | ChromaDB RAG (→ TF-IDF fallback) grounded in live sim numbers, Groq LLM (optional). |
| `report.py`, `api.py` | Report generation, FastAPI JSON surface. |

## Headline finding — the shelter's resilience rests on 3 centimetres

Once the generator is modelled (see below), CERI collapses across a 2 cm band of flood depth:

| Flood depth | CERI | Band | State |
|---|---|---|---|
| 0.84 m | 76 | Resilient | generator dry, carries the load |
| 0.86 m | 16 | Critical | generator inundated, no backup at all |

The generator sits at **0.85 m** above finished floor. The observed August 2018 high-water mark is
**0.82 m**. The entire difference between a resilient shelter and a critical one is a **3 cm**
margin.

And that margin is **smaller than the survey's own uncertainty**: `SURVEY_UNCERTAINTY_M` is 0.03 m
at 1σ, so `AT_RISK_MARGIN_M` is 0.06 m at 2σ. The model therefore cannot honestly say whether the
generator flooded in 2018 — the margin is inside the error bars, which is exactly why
`node_health` reports it `at_risk` rather than `ok` at that depth.

This is the most decision-relevant output the project has, and it is not a modelling artefact: it
falls out of two surveyed measurements. It also gives the retrofit recommendation its point —
raising one generator plinth by 30 cm is cheap, and moves the shelter across the entire band.

## Generator modelling — a defect fixed, and why it mattered

The generator was originally in the dependency graph but contributed **zero energy**:
`backup_duration_h` summed battery and solar only, and `ceri_score`'s `energy_readiness` divided by
`battery_kwh` alone while describing itself as "DER capable of carrying critical load".

So the repo simultaneously documented a surveyed 62.5 kVA set with ~14 h of fuel and an ATS, and
reported **3.4 h** of backup with the shelter failing its 12 h requirement. Those two sub-scores are
**60% of CERI**. That was an internal contradiction, not a simplification.

A second defect surfaced on fixing the first: `energy_readiness` read the building's **nameplate**
rather than `flood.surviving_der`, so it returned the same figure at every depth. A readiness
sub-score that cannot move with the hazard is not measuring readiness against that hazard. Both now
read the post-flood resource set.

**What is modelled, and what is assumed:**

- `generator_rated_kw = 50.0` — DERIVED: 62.5 kVA × 0.8 power factor. The 0.8 pf is the standard
  assumption for a diesel set, stated rather than measured. Well above the 18 kW critical load, so
  endurance binds, not capacity.
- `generator_runtime_h = 14.0` — SOURCED, used **unscaled as a floor**. The survey gives one point
  on the fuel curve (220 L, ~14 h at 70% load ≈ 35 kW). The real critical load is ~18 kW, so the set
  would run considerably longer — but scaling 15.7 L/h linearly by 18/35 would assume away the
  no-load consumption and overstate endurance, and fitting the curve needs a second fuel figure
  nobody measured. 14 h is the conservative end of a range whose top is unknown.
- **Sequencing** — generator first, battery behind it. That is what the ATS does; draining storage
  while fuel sits in the tank would be the wrong way round.
- **Undersized sets contribute nothing** rather than a partial load. Load-shedding onto a small
  generator is an operational decision this model has no basis to assume.
- **Solar during the generator run is not credited** to the battery, and the battery phase is not
  time-shifted past the generator run. Both err conservative.

## Recovery targets adequacy, not connectivity

`shelter_powered()` asks *"is a wire still connected?"*. `flood.operational` asks *"can this
shelter carry its critical load for the required window?"*. At 1.2 m those disagree: the
roof-mounted solar inverter (1.80 m) survives, so the graph reads **powered**, while the energy
model reports **0 h** of backup and CERI scores the shelter **Critical**.

The recovery search originally keyed off connectivity alone, so it returned *"already powered,
nothing to repair"* at exactly the depth the shelter was worst off. Two consequences: the
post-flood page was empty, and because no repairs were ever found, the **recovery phase rendered
identically to the active-flood phase**.

`restoration_plan()` now takes an optional `is_adequate` predicate layered on top of connectivity;
the API supplies one backed by `analyze_flood(...).operational`. Connectivity is necessary and not
sufficient. The predicate lives in the caller because the energy model sits outside `recovery.py`.

What the three phases now show:

| Phase | Depth | CERI | Backup | State |
|---|---|---|---|---|
| Before (`preparedness`) | 0.60 m | 76 Resilient | 14.0 h | battery lost, generator carries |
| During (`active_flood`) | 1.20 m | 16 Critical | 0.0 h | generator and transformer lost too |
| After (`recovery`) | 1.20 m | 76 Resilient | 14.0 h | scored with the ranked repairs applied |

And the repair plan it produces: **fix the generator, 12 h** — deferring the battery (10 h), road
access (8 h) and the transformer (48 h). 12 hours of work instead of 78 restores 400 people.

## CERI — Climate Energy Readiness Index

0–100, four transparent sub-scores (`engine.ceri_score`):

| Sub-score | Weight | What it measures |
|---|---|---|
| `energy_readiness` | 0.30 | Surviving DER — battery storage **and** generator fuel endurance — vs the critical load × required backup window. Reads `flood.surviving_der`, so it falls as assets drown |
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

Every scoring endpoint takes an optional `flood_depth_m` that overrides the phase's design flood
(`_effective_depth`). The dashboard's **flood-depth control** drives it, so a reader can drag the
water across the 3 cm generator margin and watch CERI collapse 76 → 16 rather than read that it
does. `/api/sites` serves the marks that control renders — `hazard_reference`: the observed flood
line, the survey uncertainty and 2σ at-risk margin, and the per-asset elevations. Those are
**surveyed** values, so they are served rather than written into the frontend: a measurement
copied into a React component is one that can drift from `presets.py` with nothing failing. The
substation's continued absence from that payload is asserted on the wire, not only in `presets`.

Live telemetry: `POST /api/observations` (and `GET /api/observations`). **This endpoint is
designed to accept live telemetry from drone or sensor hardware. That hardware does not exist yet
— building it is the explicit ask of this fellowship application.** Until it does,
`scripts/simulate_drone.py` stands in for it. When a reading exists, the dashboard scores against
that live depth instead of the fixed phase-based guess (`_effective_depth` in `api.py`), and the
UI polls every few seconds so it updates on its own with zero clicks.

Every response carries `placeholder: true` while `DATA_IS_PLACEHOLDER` is set. `/api/sites` and
`/health` additionally carry `unsurveyed` (and `/api/sites` carries `surveyed`, `derived` and
`reported`) — the named provenance registries, served so any consumer can report which figures
are measured. The dashboard no longer renders them; the guarantee is enforced in the API and the
test suite rather than in a panel a reader can scroll past.

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
  recovery search, CERI scoring, budget optimization. Covered by 80 passing regression tests.
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

### Derived — bounded without a site visit (`presets.DERIVED_VALUES`)

Neither of these is a measurement, and neither clears `DATA_IS_PLACEHOLDER`. They are what could
honestly be done from a desk instead of guessing. See [docs/SURVEY.md](SURVEY.md) §7.1.

- **Shelter capacity ≤ 414.** Surveyed floor area (1450 m²) ÷ the KSDMA minimum covered area per
  person (3.5 m², Ed. 1, 9 Jul 2020). The standing `pop_served` of 500 exceeds this, so it is
  *inconsistent with the surveyed area*, not merely unmeasured — and it errs toward overstating
  how many people each repair restores. An **upper bound only**: gross area counts corridors,
  stairwells and toilets as sleepable, so true capacity is strictly lower. Inventing a usable-area
  fraction to sharpen it would fabricate the measurement the bound exists to avoid.
- **Critical load = the interval 18.0–20.0 kW.** The two disagreeing survey records bracket it.
  `/api/sites/{id}/backup` reports `hours_range` and `adequate_worst_case` across both ends.
  Averaging to 19.0 would produce a figure neither record supports.

Where a value cannot even be bounded, its **absence is priced**:
`dependency_graph.unassessed_sensitivity()` runs the graph with the unmeasured assets dry and then
failed, and reports whether the shelter's outcome actually turns on the gap. It does not say
whether the substation floods — it says how much it matters that we do not know, which is what
decides whether the measurement is worth prioritising.

### Reported by the college, unverified (`presets.REPORTED_VALUES`)

Stated by Sahrdaya facilities staff, recorded on the author's account of that conversation. No
survey record, no document, no instrument reading. Kept as its own tier because treating a
statement from the people who run the building as a guess throws away real knowledge, while
treating it as a measurement claims a rigour nobody applied.

- **`pop_served` = 400.** Supersedes the invented 500, which exceeded the floor-area ceiling.
- **`critical_load_kw` = 18.0.** Settles *which* survey record to use. It does **not** reconcile
  them: the itemisation still sums to 20.0, so a 2.0 kW error sits unlocated in that breakdown.
  `critical_load_discrepancy_kw()` stays non-zero on purpose.
- **Substation above flood level.** Modelled as a flood-exposure claim via `REPORTED_ABOVE_FLOOD`,
  not an elevation — no height was given, and writing one would fabricate a measurement. Its node
  renders `ok_reported`, a state distinct from both `ok` (measured dry) and `unknown`.

**A reported claim is used and still challenged.** All three remain inside
`unassessed_sensitivity()`, so vouching for an asset never retires the check on whether that
vouching matters. One email to the Estate Officer promotes all three to SOURCED — see
[docs/SURVEY.md](SURVEY.md) §7.2.

### Still provisional (`presets.UNSURVEYED_VALUES`)

One entry remains, which is what keeps `DATA_IS_PLACEHOLDER` true:

- **`REPAIR_EFFORT_H`** (`recovery.py`) — the substation falls through to a generic 8 h default.
  Now load-bearing only if the college's report that the substation stays dry turns out to be
  wrong: while that holds, the substation never fails and never enters a repair plan. Every ranked
  plan carries `estimated_effort_repairs` naming any repair costed from this fallback (currently
  empty).

The other three former entries — `pop_served`, `critical_load_kw` and `substation_elevation` —
moved to `REPORTED_VALUES` above when the college supplied figures. They did **not** become
measurements, and the test suite asserts all four registries stay disjoint so an entry can never be
cleared by moving it between tiers rather than by measuring something.

**None of the four gaps currently changes a recommendation.** Verified rather than assumed: the
substation is tested both ways (`changes_outcome: false`), the 18-vs-20 kW spread moves
ride-through 3.4 h → 3.9 h against a 12 h requirement the shelter misses either way, no plan uses
the fallback repair estimate, and with one modelled shelter there is nothing for `pop_served` to
rank against. That is the honest headline: the gaps are documented, bounded, and demonstrably not
driving the output.

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
response, and is carried alongside the named registries so any consumer can say which figures are
measured and which are not. It cannot be cleared by editing a boolean: the only way to clear it is
to replace the named values with measurements, and the test suite asserts the four registries stay
disjoint so an entry can never be retired by moving it between tiers.
**[docs/SURVEY.md](SURVEY.md)** §7 is exactly what that takes.

The dashboard used to render this as a persistent notice. It was removed for being a wall of
explanation in a product surface — a presentation decision, and worth being clear about what it
did and did not change. The guarantee was never the panel: it is that `DATA_IS_PLACEHOLDER` is
derived from the registry and travels on every response. What the removal does cost is
*confrontation* — a reader of the dashboard alone is no longer told which numbers are unmeasured,
and now has to consult the API or these docs to find out.

---

## Verify

```bash
python -m pytest              # 80 regression tests — flood domain + datum + scoring + provenance
cd backend
python validate_physics.py    # twin physics sanity (live weather)
python smoke_pipeline.py      # heatwave → outage → score → plan → retrofits
python smoke_copilot.py       # RAG retrieval + grounded answer
```

Runs fully offline, zero keys. The Groq copilot is the only optional key; without it the
copilot returns the grounded evidence (retrieved guidelines + sim numbers) instead of prose.
