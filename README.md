# ResilienceScout

**Is this shelter energy-ready for the flood — and if not, what do we fix first?**

ResilienceScout turns *minimal* building information + public weather data into a
physics-informed digital twin, then answers three questions across a flood's lifecycle:

- **Before** — audit shelter energy systems and flood exposure. Output: a **Climate Energy
  Readiness Index (CERI)** per shelter, with four transparent sub-scores.
- **During** — determine whether each shelter can still carry its critical load, and *why not*,
  without sending anyone into a flooded switch room.
- **After** — rank repairs by **population restored per repair-hour**, not by what's broken.

The differentiator is not the inspection — it's the **infrastructure dependency graph** and the
**recovery prioritisation** layered on top of it.

Built for the 2026 NY Climate Exchange Climate Tech Fellowship (Energy × Urban Resilience).

> ### Data provenance — mostly surveyed, four values still provisional
> Site surveys of the Decennial Block (latest 2026-07-18) closed most of the model's data gaps.
> **Measured:** the vertical datum (finished floor level tied to MSL at 11.84 m), the August 2018
> flood mark (0.82 m above floor, evidenced by wall staining), six of eight equipment elevations,
> the full DER nameplate, floor area, and the grid topology.
>
> **Still provisional —** `pop_served`, `critical_load_kw`, the substation elevation, and
> `REPAIR_EFFORT_H`. These are enumerated in code as `presets.UNSURVEYED_VALUES`, from which
> `DATA_IS_PLACEHOLDER` is *derived* rather than hand-set. That flows to `placeholder: true` on
> every API response and a persistent notice in the UI reading *"4 of 10 values still
> provisional"*, which expands to name exactly which. The notice cannot be cleared by editing a
> flag — only by replacing the named values with measurements.
>
> See [docs/SURVEY.md](docs/SURVEY.md) §7 for what closes each one.

---

## What it does

| Layer | Implementation |
|---|---|
| Weather | Open-Meteo forecast + history (free, no key) |
| Digital twin | 5R1C ISO-13790 thermal model via `rcbsim` (ETH Zürich, MIT) |
| Flood hazard | Per-asset elevation → inundation → which DER survives |
| Dependency graph | Shelter → panel → transformer / solar / battery / generator, with SPOF detection |
| Scoring | CERI 0–100: energy readiness, flood readiness, backup duration, critical vulnerabilities |
| Recovery | **Exhaustive** minimum-effort repair search, ranked by population-per-repair-hour |
| Retrofits | Scenario comparison + budget optimizer (resilience gain / ₹) |
| Copilot | ChromaDB RAG (→ TF-IDF fallback) grounded in live sim numbers, Groq LLM |

## Quick start (localhost)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on mac/linux)
pip install -r requirements.txt

# 1. backend
cd backend
uvicorn resilienceos.api:app --reload      # http://localhost:8000/docs

# 2. dashboard (separate terminal)
cd "Assets/Energy Management System Dashboard"
npm install
npm run dev                                # http://localhost:5173
```

The app runs **fully offline with zero keys**.

**Optional — natural-language copilot:** get a free Groq key at
https://console.groq.com/keys, then:

```bash
copy .env.example .env       # and paste your key, OR:
set GROQ_API_KEY=your_key     # Windows (export GROQ_API_KEY=... elsewhere)
```

Without a key the copilot still works — it returns the grounded evidence
(retrieved guidelines + simulation numbers) instead of prose.

## Verify it works

```bash
python -m pytest              # 56 regression tests (flood domain + datum + scoring)

cd backend
python validate_physics.py    # twin physics sanity checks (uses real weather)
python smoke_pipeline.py      # heatwave -> outage -> score -> plan -> retrofits
python smoke_copilot.py       # RAG retrieval + grounded answer
```

## Layout

```
backend/resilienceos/
  weather.py     building.py    twin.py        # low-data digital twin
  hazard.py      solar.py                      # heatwave + outage + flood + PV
  presets.py                                   # all campus data + provenance registry
  dependency_graph.py           recovery.py    # SPOF detection, repair prioritisation
  engine.py      scenarios.py                  # CERI scoring, retrofits
  copilot/       report.py      api.py         # RAG copilot, report, JSON API
Assets/Energy Management System Dashboard/     # React dashboard (Vite + Tailwind + Radix)
docs/OVERVIEW.md                               # what's real, what's invented, what's needed
```

## Docs

- [docs/OVERVIEW.md](docs/OVERVIEW.md) — architecture, and the surveyed-vs-provisional ledger.
- [docs/SURVEY.md](docs/SURVEY.md) — what has been surveyed, and §7 what remains.

## Roadmap (post-MVP)

Campus survey to retire the placeholder data, spatial dependency map over real building
footprints, additional hazards (heatwave, wildfire), IoT (ESP32) integration, and validation
against measured indoor-temperature logs.

---

*Digital twin: 5R1C ISO-13790 — Jayathissa et al., Applied Energy 202 (2017),
ETH Zürich Architecture & Building Systems (MIT). Early prototype for decision
support — not a substitute for on-site engineering assessment.*
