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

> ### Data provenance — four tiers, and the notice cannot be faked away
> Every campus-specific number is **measured**, **reported**, **derived**, or **still
> provisional**, and the code says which.
>
> **Measured (`SURVEYED_VALUES`)** — site surveys of the Decennial Block (latest 2026-07-18)
> closed most of the gaps: the vertical datum (finished floor level tied to MSL at 11.84 m), the
> August 2018 flood mark (0.82 m above floor, evidenced by wall staining), six of eight equipment
> elevations, the full DER nameplate, floor area, and the grid topology.
>
> **Reported (`REPORTED_VALUES`)** — stated by college facilities staff, not independently
> verified: shelter capacity **400**, critical load **18.0 kW** (settling which of two disagreeing
> survey records to use), and the 11 kV substation sitting above flood level. The substation claim
> is modelled as a *flood-exposure claim*, not an elevation — no height was given, and inventing
> one would fabricate a measurement. One written confirmation by email promotes all three to
> sourced.
>
> **Derived (`DERIVED_VALUES`)** — bounded from a desk, from a surveyed input plus a cited public
> standard. Shelter capacity cannot exceed 1450 m² ÷ 3.5 m² per person (KSDMA Ed. 1, 9 Jul 2020)
> = **414**. The reported 400 sits inside that ceiling, so two independent routes — a verbal
> report and surveyed area ÷ a published standard — agree to within 3.5%. That is corroboration,
> not verification.
>
> **Still provisional (`UNSURVEYED_VALUES`)** — `REPAIR_EFFORT_H`. `DATA_IS_PLACEHOLDER` is
> *derived* from this registry rather than hand-set, flowing to `placeholder: true` on every API
> response and a persistent UI notice. Neither a report nor a derivation clears it: a report is
> unverified and a bound constrains rather than measures, which is why all four registries are
> kept disjoint and asserted so in the test suite.
>
> Where a measurement is missing *or merely reported*, its cost is priced rather than assumed —
> `unassessed_sensitivity()` runs the dependency graph both ways and reports whether the gap
> actually changes the outcome. A reported claim is used **and** still challenged: the substation
> renders as working while remaining in the sensitivity test, so vouching for an asset never
> retires the check on whether that vouching matters.
>
> Current finding: none of the four gaps changes any recommendation at the modelled depths.
>
> See [docs/SURVEY.md](docs/SURVEY.md) §7.1 for what was closed without a site visit, and §7.2 for
> which remaining items can be obtained remotely.

---

## What it does

| Layer | Implementation |
|---|---|
| Weather | Open-Meteo forecast + history (free, no key) |
| Digital twin | 5R1C ISO-13790 thermal model via `rcbsim` (ETH Zürich, MIT) |
| Flood hazard | Per-asset elevation → inundation → which DER survives |
| Dependency graph | Shelter → panel → transformer / solar / battery / generator, with SPOF detection |
| Backup energy | Generator fuel endurance (ATS-ordered) → battery → solar, against the critical load |
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
python -m pytest              # 74 regression tests (flood domain + datum + scoring + provenance)

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
