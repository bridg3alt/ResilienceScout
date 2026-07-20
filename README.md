# ResilienceScout

### Autonomous Climate Energy Readiness Platform

**When the flood comes, can this shelter keep its lights on — and if not, which single repair
brings back the most people per hour of work?**

[![Tests](https://img.shields.io/badge/tests-80%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.13-blue)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

Built for the **2026 NY Climate Exchange Climate Tech Fellowship** — Energy × Urban Resilience.

---

## Why this project matters

**The climate problem.** Floods are getting more frequent and more severe, and they take out
electricity precisely when a community needs it most. The buildings people fall back on —
shelters, clinics, schools — stop being useful the moment their power infrastructure goes under.
In Kerala's 2018 floods, buildings across the state became unusable not because they were
structurally damaged, but because a generator, a transformer or a distribution panel sat a few
centimetres too low.

**The current gap.** After a flood, assessment means sending people to walk through buildings and
write down what looks broken. That is slow, dangerous while water is still standing, and produces
a list — not a decision. An emergency manager holding a list of forty damaged components still
does not know which crew to dispatch first.

**Why existing approaches fail.** Inspection tools report *components*. Decisions are about
*consequences*. Knowing a transformer is flooded does not tell you whether the building still has
power, because that depends entirely on what else survived and how it is all wired together. A
per-asset checklist structurally cannot answer:

- Is this building still able to operate as a shelter right now?
- How many hours of backup power does it actually have left?
- Of everything that is broken, which repair restores the most function fastest?

Those are graph questions, not inventory questions.

---

## Our solution

ResilienceScout models a building's energy infrastructure as a **dependency graph**, floods that
graph asset by asset against surveyed elevations, and reports whether the building can still carry
its critical load. It then ranks repairs by **population restored per repair-hour**.

### Before / During / After

| Phase | Question answered | Output |
|---|---|---|
| **Before** the flood | How exposed is this building? | Climate Energy Readiness Index (CERI) 0–100, four inspectable sub-scores, prioritised retrofits |
| **During** the flood | Can it still operate as a shelter? | Live operational status, surviving energy sources, hours of backup remaining — without sending anyone into a flooded switch room |
| **After** the flood | What do we fix first? | Minimum repair set, ranked by people restored per hour of work |

---

## Core innovation

### 1. Infrastructure Dependency Graph

The contribution is not the inspection — it is the reasoning layered on top of it.

```
                    ┌── Transformer ◄── Substation
                    │
Shelter ◄── Panel ◄─┼── Battery
                    │
                    ├── Solar inverter ◄── PV array
                    │
                    └── Generator ◄── Road access (fuel resupply)
```

The graph makes visible what no checklist can:

- Losing the **transformer** is survivable with a charged battery, and fatal without one.
- Losing the **distribution panel** is fatal either way — every source is wired through it. It is a
  single point of failure even when the panel itself is perfectly dry and undamaged.
- Losing **road access** does not cut power today, but it stops fuel resupply, so it silently caps
  how long the generator can run.

Single-point-of-failure detection falls directly out of the topology (OR across sources, AND
through the panel), which is why the graph earns its place over a spreadsheet.

### 2. Climate Energy Readiness Index (CERI)

A 0–100 score built from four sub-scores you can argue with individually, rather than one opaque
number:

| Sub-score | Weight | Measures |
|---|---|---|
| Energy readiness | 0.30 | Surviving generation and storage vs critical load × required window |
| Flood readiness | 0.25 | Elevation margin of the weakest power asset above the flood line |
| Backup duration | 0.30 | Surviving ride-through vs the required backup window |
| Critical vulnerabilities | 0.15 | Single points of failure in the dependency graph |

Bands: **≥75** Resilient · **≥50** Moderate · **≥30** At risk · below that, Critical.

### 3. Recovery Prioritization Engine

An exhaustive search for the *smallest set of repairs* that restores operation — then ranks those
sets by population restored per repair-hour.

Critically, it tests **adequacy, not connectivity**. Asking "is a wire still attached?" gives the
wrong answer: at 1.2 m the roof-mounted solar inverter survives, so the graph reads *powered* while
the energy model reports **zero hours** of backup. Restoration is judged on whether the building
can actually carry its load for the required window.

---

## The finding that validates the approach

The pilot building's entire resilience rests on **three centimetres**.

| Flood depth | CERI | Backup | State |
|---|---|---|---|
| 0.82 m | **76** Resilient | 14.0 h | Generator dry, carries the load |
| 0.85 m | **16** Critical | 0.0 h | Generator inundated, no backup at all |

The generator's alternator sits at **0.85 m** above finished floor. The observed August 2018
high-water mark — evidenced by wall staining in the main entrance lobby — is **0.82 m**.

That 3 cm margin is *narrower than the survey's own uncertainty* (±6 cm at 2σ), so the model
reports the generator **at risk** rather than claiming it is safe. It cannot honestly say whether
that generator flooded in 2018.

This is not a modelling artefact — it falls out of two independent measurements. And it produces
a concrete, cheap recommendation: **raise one generator plinth by 30 cm** and the building moves
across the entire band.

**The dashboard lets you drag the water across that cliff and watch the score collapse.** That
interaction is the whole argument in one gesture.

---

## System architecture

```
┌─────────────────────────────────────────────────────────────┐
│  SENSING LAYER                          [ PLANNED — the ask ]│
│  Autonomous ground robot: RGB + thermal imaging,             │
│  water-level sensing, GPS/SLAM navigation                    │
└───────────────────────────┬─────────────────────────────────┘
                            │  POST /api/observations
                            │  (interface built and live today)
┌───────────────────────────▼─────────────────────────────────┐
│  REASONING LAYER                            [ BUILT ]        │
│                                                              │
│  Open-Meteo ──► Digital twin (5R1C ISO-13790)                │
│                        │                                     │
│                        ▼                                     │
│         Flood hazard: per-asset inundation                   │
│                        │                                     │
│                        ▼                                     │
│         Dependency graph ──► SPOF detection                  │
│                        │                                     │
│                        ▼                                     │
│         Energy model: generator → battery → solar            │
│                        │                                     │
│                        ▼                                     │
│         CERI scoring  +  Recovery prioritization             │
└───────────────────────────┬─────────────────────────────────┘
                            │  FastAPI JSON
┌───────────────────────────▼─────────────────────────────────┐
│  DECISION LAYER                             [ BUILT ]        │
│  React dashboard · interactive flood-depth control ·         │
│  dependency map · repair ranking · grounded copilot          │
└─────────────────────────────────────────────────────────────┘
```

**The decision layer was deliberately built first.** An inspection robot with nothing to reason
over produces photographs. A reasoning system with a defined hardware interface produces decisions
the moment sensing arrives — and, until then, produces them from a tape measure and a survey.

---

## Features

### Built and tested today

- **Physics-informed digital twin** — 5R1C ISO-13790 thermal model, peer-reviewed, sanity-checked
  against live weather
- **Per-asset flood inundation** against a surveyed vertical datum, with mandatory datum
  conversion so a street-depth reading can never be silently mixed with a floor-relative one
- **Dependency graph** with single-point-of-failure detection
- **Backup energy model** sequencing generator → battery → solar the way the transfer switch does
- **CERI scoring** across four transparent sub-scores
- **Recovery prioritization** — exhaustive minimum-repair-set search, ranked by people per
  repair-hour, showing what it deliberately deferred and what that saved
- **Retrofit comparison** and a budget optimiser (resilience gain per ₹)
- **Interactive flood-depth control** — drag the water level, watch every panel re-score live
- **Grounded copilot** — retrieval over live simulation numbers, with sources listed
- **Live telemetry endpoint** — `POST /api/observations`, which rejects any reading whose vertical
  datum it cannot honestly convert
- **80 regression tests**, running fully offline with zero API keys

### Planned — what this fellowship would fund

- **Autonomous ground robot** — RGB and thermal imaging, water-level sensing, GPS/SLAM navigation,
  obstacle avoidance
- **Computer vision pipeline** — asset detection and damage classification from inspection imagery
- **Thermal anomaly detection** — identifying failing electrical components before they fail
- **Terrain data** (LiDAR or photogrammetry) — without it, flood return periods cannot be derived
  from a single observed high-water mark
- **Multi-site deployment** — the ranking layer already accepts multiple buildings; a district-scale
  pilot is what turns population-per-repair-hour from a sort key into a real allocation decision

> **On honesty:** the sensing layer above does not exist yet. It is specified, its ingestion
> endpoint is built and live, and building it is the explicit ask of this application. Everything
> under *Built and tested today* runs and is covered by the test suite.

---

## Technology stack

| Layer | Technology |
|---|---|
| Weather | Open-Meteo forecast + history (free, keyless) |
| Digital twin | `rcbsim` — 5R1C ISO-13790 (ETH Zürich, MIT) |
| Numerics | NumPy, pandas |
| API | FastAPI, Uvicorn, Pydantic |
| Copilot | ChromaDB RAG → TF-IDF fallback, Groq LLM (optional) |
| Dashboard | React 18, TypeScript, Vite, Tailwind CSS, Radix UI, Recharts |
| Testing | pytest — 80 regression tests |

---

## Repository structure

```
backend/
  resilienceos/
    weather.py          Open-Meteo client
    building.py         geometry, U-values → 5R1C zone
    twin.py             hour-by-hour thermal simulation
    solar.py            PV generation
    hazard.py           flood, outage and heat analysis
    presets.py          pilot building data and provenance registries
    dependency_graph.py topology, SPOF detection, sensitivity
    recovery.py         minimum repair set, prioritization
    engine.py           CERI and resilience scoring
    scenarios.py        retrofit comparison, budget optimiser
    copilot/            grounded RAG copilot
    api.py              FastAPI JSON surface
  tests/                80 regression tests
dashboard/              React decision dashboard
```

---

## How it works

```
1. INPUT           Minimal building data + free public weather
                              │
2. SIMULATE        5R1C thermal twin → indoor conditions, PV output
                              │
3. FLOOD           Each asset's surveyed elevation vs water depth
                   → which energy sources survive
                              │
4. GRAPH           Which surviving sources still reach the shelter
                   → single points of failure
                              │
5. ENERGY          Generator fuel → battery → solar, against
                   critical load → hours of ride-through
                              │
6. SCORE           CERI 0–100 across four sub-scores
                              │
7. RANK            Smallest repair set that restores operation,
                   ordered by people restored per repair-hour
                              │
8. DECIDE          Dashboard, API, or plain-English copilot
```

**Worked example — the pilot building at 1.2 m of water:**

Flooded: transformer, battery, generator, road access. A damage report stops here with four
failures and 78 hours of work.

The graph continues: the solar inverter survives but cannot carry the critical load alone, so the
building is **not** operational. Of the four repairs, only the generator is needed to restore
adequate power.

> **Repair the generator — 12 hours — restores 400 people.**
> Defer the battery (10 h), road access (8 h) and transformer (48 h).
> **12 hours of work instead of 78.**

---

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on mac/linux)
pip install -r requirements.txt

# backend
cd backend
uvicorn resilienceos.api:app --reload      # http://localhost:8000/docs

# dashboard (separate terminal)
cd dashboard
npm install
npm run dev                                # http://localhost:5173
```

Runs fully offline with zero API keys. For natural-language copilot answers, set a free
`GROQ_API_KEY` from https://console.groq.com/keys — without one the copilot returns the retrieved
evidence and live numbers instead of prose.

**Verify:**

```bash
python -m pytest              # 80 regression tests
cd backend
python validate_physics.py    # digital-twin physics sanity checks
python smoke_pipeline.py      # end-to-end: hazard → score → plan → retrofits
```

---

## Pilot validation

**Site:** the Decennial Block, Sahrdaya College of Engineering and Technology, Kodakara, Thrissur
district, Kerala.

**Why this building was selected:**

- **Representative.** A three-storey, 1,450 m² institutional building with solar PV, battery
  storage and a diesel generator — the same energy profile as the schools and community buildings
  that get designated as emergency shelters across Kerala.
- **In a real flood corridor.** The Thrissur district was severely affected in the 2018 Kerala
  floods, and the building carries a physical high-water mark from that event.
- **Surveyable to instrument grade.** Accessible for repeated measurement, which allowed the
  vertical datum to be tied to mean sea level and equipment elevations measured directly rather
  than assumed from code minimums.

**What has been measured on site:** the vertical datum (finished floor tied to MSL at 11.84 m),
the August 2018 flood mark (0.82 m above floor), six of eight equipment elevations, the full
distributed-energy nameplate, floor area, and the grid topology.

**Planned field validation:**

- Indoor temperature logging to validate twin predictions against measured conditions
- Remaining asset elevations (solar array, road access) and the substation elevation
- Robot-collected inspection imagery to train and validate the computer-vision layer
- A second building on the same campus grid, to exercise multi-site recovery ranking against a
  shared upstream asset

---

## Research contributions

**Novelty.** Post-disaster infrastructure assessment is well studied as a *detection* problem —
identifying damage from imagery. This work reframes it as a *consequence* problem: given detected
damage, which repair maximises restored function per unit of effort. Modelling the energy
dependency graph and searching it for minimum restorative repair sets is, to our knowledge, not
present in existing shelter-readiness tooling.

**Methodological contribution.** The system prices what it does not know. Where a value cannot be
measured, the model runs the dependency graph both ways — asset dry, asset failed — and reports
whether the outcome actually turns on the gap. This converts "we lack data" from an excuse into a
quantified decision about which measurement is worth funding.

**Scalability.** The method requires no proprietary data: free public weather, a published thermal
standard, and measurements one person can collect with a tape measure and a GNSS fix. That matters
for municipalities that cannot afford consultancy-grade digital twins.

**Potential publications:**

- Dependency-graph-based recovery prioritization for post-flood energy restoration
- Uncertainty-aware readiness scoring where measurement error exceeds decision margins
- Low-data digital twins for climate resilience assessment in the Global South

---

## Climate impact

**Sustainable Development Goals:**

| SDG | Contribution |
|---|---|
| **7** — Affordable and Clean Energy | Improves reliability and resilience of distributed solar, storage and backup generation |
| **9** — Industry, Innovation and Infrastructure | Resilient infrastructure assessment for critical public buildings |
| **11** — Sustainable Cities and Communities | Directly targets disaster resilience of emergency shelters and essential services |
| **13** — Climate Action | Adaptation tooling for communities facing intensifying flood hazard |

**Adaptation.** Most climate funding flows to mitigation. Adaptation — keeping essential services
running through events that are already unavoidable — is chronically under-tooled, particularly at
the building scale where shelters actually fail.

**Resilience.** The 3 cm finding illustrates the wider point: resilience often turns on small,
cheap, invisible margins. A system that surfaces them before the flood converts a disaster into a
maintenance ticket.

---

## Roadmap

| Phase | Milestone |
|---|---|
| **Now** | Decision engine, CERI, dependency graph, recovery ranking, dashboard — complete and tested |
| **Next** | Multi-site deployment across a shared campus grid; hosted public demo |
| **Then** | Robot prototype with RGB, thermal and water-level sensing feeding the live telemetry endpoint |
| **After** | Computer-vision damage classification; terrain data for flood return periods |
| **Later** | District-scale pilot with a municipal disaster-management authority |

---

## Future vision

The long-term aim is a **standing readiness layer for public infrastructure** — not a tool someone
opens after a disaster, but a system that already knows the answer when the water rises.

**From one building to a district.** The dependency graph does not stop at a building boundary.
Extended across a ward, it models the shared substations and feeders that link a shelter, a clinic
and a pumping station — so a single repair can be evaluated for everything it restores at once.
That is where population-per-repair-hour stops being a sort key and becomes a resource-allocation
decision across a city.

**From flood to multi-hazard.** The architecture separates *hazard* from *consequence*. Flood is
implemented; heatwave and outage analysis already exist in the codebase. Wildfire, cyclone and
grid-failure hazards plug into the same dependency reasoning without rebuilding it.

**From inspection to continuous monitoring.** The robot is a step, not the destination. Fixed
low-cost sensors on critical assets would let CERI update continuously, turning readiness from a
periodic audit into a live figure a facilities manager watches the way they watch a fuel gauge.

**From tool to standard.** Kerala's relief standards require that shelter power "shall be ensured"
but specify no duration — so the 12-hour backup target in this system is a design choice, not a
regulation. Evidence from deployments across many buildings is exactly what a defensible standard
would be built from. The most durable outcome of this work is not the software; it is the data to
argue for a real one.

---

## Team

**Brigit Thomas** — *[role, background, relevant experience]*

> *Fill this in: your technical background, why you are positioned to build this, and your time
> commitment including Climate Week NYC in September.*

---

## Acknowledgements

- **Sahrdaya College of Engineering and Technology, Kodakara** — site access, facilities data, and
  survey support for the pilot building.
- **Jayathissa et al.**, *Applied Energy* 202 (2017) — the 5R1C ISO-13790 implementation
  (`rcbsim`), ETH Zürich Architecture & Building Systems, MIT licensed.
- **Open-Meteo** — free, keyless weather forecast and historical APIs.
- **Kerala State Disaster Management Authority** — Minimum Standards of Relief (Ed. 1, 9 July
  2020), the published standard used for shelter capacity bounds.

---

## License

MIT — see [LICENSE](LICENSE).

---

*Early prototype for decision support. Not a substitute for on-site engineering assessment by a
qualified professional.*
