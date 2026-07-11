# ResilienceOS

**AI energy-resilience OS for under-instrumented public buildings.**

ResilienceOS turns *minimal* building information + public weather data into a
physics-informed digital twin, simulates how the building copes with **heatwaves**
and **power outages**, generates an **operational energy plan**, ranks **retrofits**
by resilience-per-rupee, and explains it all through a **RAG-grounded AI copilot** —
with **no BMS, no sensors, and no dedicated facility engineer required**.

Built for the 2026 NY Climate Exchange Climate Tech Fellowship (Energy × Urban Resilience).

---

## What it does (the vertical slice)

| Layer | MVP implementation |
|---|---|
| Weather | Open-Meteo forecast + history (free, no key) |
| Digital twin | 5R1C ISO-13790 thermal model via `rcbsim` (ETH Zürich, MIT) |
| Hazard sim | Heatwave (safe occupancy hours) + power outage (free-float temp rise) |
| Solar/DER | Rooftop PV generation model + battery backup-duration |
| Optimizer | Rule-based operational schedule + resilience score |
| Retrofits | Scenario comparison + budget optimizer (resilience gain / ₹) |
| Copilot | ChromaDB RAG (→ TF-IDF fallback) grounded in live sim numbers, Groq LLM |
| Report | One-page HTML resilience report (print → PDF) |

The twin's physics is **validated** (`backend/validate_physics.py`): thermal lag,
mass effects, and cool-roof deltas all behave correctly against real weather.

## Quick start (localhost)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on mac/linux)
pip install -r requirements.txt

# run the demo dashboard
streamlit run streamlit_app.py
```

Open http://localhost:8501. The app runs **fully offline with zero keys**.

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
cd backend
python validate_physics.py    # twin physics sanity checks (uses real weather)
python smoke_pipeline.py      # heatwave -> outage -> score -> plan -> retrofits
python smoke_copilot.py       # RAG retrieval + grounded answer
```

## JSON API (optional)

```bash
cd backend
uvicorn resilienceos.api:app --reload
# POST /analyze, /scenario/{name}, /budget/{inr}, /copilot  — see /docs
```

## Layout

```
backend/resilienceos/
  weather.py     building.py    twin.py        # low-data digital twin
  hazard.py      solar.py                        # heatwave + outage + PV
  engine.py      scenarios.py                    # rule engine, scoring, retrofits
  copilot/       report.py      api.py           # RAG copilot, report, JSON API
streamlit_app.py                                 # demo dashboard
```

## Roadmap (post-MVP)

Physics-informed calibration against real indoor-temperature logs, MILP optimization,
multi-agent copilot, IoT (ESP32) integration, knowledge graph, and validation against
the Building Data Genome 2 dataset.

---

*Digital twin: 5R1C ISO-13790 — Jayathissa et al., Applied Energy 202 (2017),
ETH Zürich Architecture & Building Systems (MIT). Early prototype for decision
support — not a substitute for on-site engineering assessment.*
