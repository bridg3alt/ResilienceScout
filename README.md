# ResilienceScout

**Can this shelter keep its power on through a flood — and if not, what do we fix first?**

Floods knock out power to the buildings communities depend on: shelters, clinics, schools. Damage
is usually assessed by sending people to look at equipment, which is slow, dangerous while water
is still up, and answers the wrong question. A list of broken components does not tell an
emergency manager which repair to send the first crew to.

ResilienceScout models a building's energy infrastructure as a dependency graph, floods it asset
by asset against surveyed elevations, and reports whether the building can still carry its
critical load — then ranks repairs by **population restored per repair-hour**.

Pilot building: the Decennial Block at Sahrdaya College of Engineering, Kodakara, Kerala.

---

## What it does

**Before a flood** — scores flood readiness 0–100 as a Climate Energy Readiness Index (CERI),
built from four sub-scores you can inspect individually: energy readiness, flood readiness, backup
duration, and critical vulnerabilities.

**During** — determines whether the building can still carry its critical load, and why not,
without sending anyone into a flooded switch room.

**After** — ranks repairs by what each one restores per hour of work, rather than by what is most
badly damaged.

At 1.2 m of water the pilot building's answer is: **repair the generator, 12 hours** — deferring
the battery (10 h), road access (8 h) and the transformer (48 h). Twelve hours of work instead of
seventy-eight, restoring the same 400 people.

## How it works

| Layer | Implementation |
|---|---|
| Weather | Open-Meteo forecast + history (free, no key) |
| Digital twin | 5R1C ISO-13790 thermal model via `rcbsim` (ETH Zürich, MIT) |
| Flood hazard | Per-asset elevation → inundation → which energy sources survive |
| Dependency graph | Shelter → panel → transformer / solar / battery / generator, with single-point-of-failure detection |
| Backup energy | Generator fuel endurance (ATS-ordered) → battery → solar, against the critical load |
| Scoring | CERI 0–100 across four transparent sub-scores |
| Recovery | Exhaustive minimum-effort repair search, ranked by population per repair-hour |
| Copilot | Retrieval over the live simulation numbers, optional Groq LLM |

The contribution is the dependency graph and the recovery ranking on top of it, not the
inspection. A damage report says the transformer is flooded; the graph says whether that matters —
losing the transformer is survivable with a charged battery and fatal without one, while losing
the distribution panel is fatal either way, because every source is wired through it.

## Run it

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

Runs fully offline with zero API keys.

**Optional** — for natural-language copilot answers, get a free key at
https://console.groq.com/keys and set `GROQ_API_KEY`. Without one the copilot returns the
retrieved evidence and simulation numbers instead of prose.

## Tests

```bash
python -m pytest              # 80 regression tests

cd backend
python validate_physics.py    # digital-twin physics sanity checks
python smoke_pipeline.py      # end-to-end: hazard → score → plan → retrofits
```

## Layout

```
backend/resilienceos/
  weather.py     building.py    twin.py        # digital twin
  hazard.py      solar.py                      # flood, outage, heat, PV
  presets.py                                   # building data and provenance
  dependency_graph.py           recovery.py    # SPOF detection, repair ranking
  engine.py      scenarios.py                  # CERI scoring, retrofits
  copilot/       report.py      api.py         # copilot, report, JSON API
dashboard/                                     # React dashboard (Vite + Tailwind)
```

---

*Digital twin: 5R1C ISO-13790 — Jayathissa et al., Applied Energy 202 (2017), ETH Zürich
Architecture & Building Systems (MIT). Early prototype for decision support — not a substitute
for on-site engineering assessment.*
