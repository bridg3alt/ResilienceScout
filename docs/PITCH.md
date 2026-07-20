# ResilienceScout

**Is this shelter energy-ready for the flood — and if not, what do we fix first?**

*2026 NY Climate Exchange Climate Tech Fellowship — Energy × Urban Resilience*

---

## Summary

Floods knock out power to the buildings communities fall back on — shelters, clinics, schools.
The damage is usually assessed by sending people to look at equipment, which is slow, hazardous
while water is still up, and produces the wrong output: a list of broken components, when what an
emergency manager needs is a decision about which repair to send the first crew to.

ResilienceScout is a decision-support system that answers the operational question instead of the
inventory one. It models a building's energy infrastructure as a dependency graph, floods that
graph asset by asset against surveyed elevations, and reports whether the building can still carry
its critical load — then ranks repairs by **population restored per repair-hour**.

The working system runs today on one surveyed building. This application asks for the autonomous
inspection layer that would feed it at scale.

---

## The finding that justifies the approach

The pilot building is the Decennial Block at Sahrdaya College of Engineering, Kodakara, Kerala —
surveyed in July 2026, and used as a shelter-representative institutional building.

Its resilience rests on **three centimetres**.

| Flood depth | CERI | State |
|---|---|---|
| 0.84 m | 76 — Resilient | generator dry, carries the load for 14 h |
| 0.86 m | 16 — Critical | generator inundated, no backup at all |

The generator's alternator sits 0.85 m above finished floor. The observed August 2018 high-water
mark — evidenced by wall staining in the main entrance lobby — is 0.82 m. The entire distance
between a working shelter and a dark one is 3 cm, and that margin is *smaller than the survey's own
uncertainty* (0.03 m at 1σ). The model therefore reports the generator `at_risk` rather than `ok`
at that depth, because claiming to know would be dishonest.

This is not a modelling artefact. It falls directly out of two measurements, and it produces an
actionable recommendation: raising one generator plinth by 30 cm is cheap and moves the building
across the entire band. No per-asset damage checklist surfaces this, because the finding is not
about an asset — it is about a margin between two of them.

---

## What the system does

```
Open-Meteo (free, keyless)
      │
      ▼
Digital twin ──────── 5R1C ISO-13790 thermal model (rcbsim, ETH Zürich)
      │
      ▼
Flood hazard ──────── per-asset elevation → inundation → which sources survive
      │
      ▼
Dependency graph ──── shelter ← panel ← transformer / solar / battery / generator
      │                                  single-point-of-failure detection
      ▼
Energy model ──────── generator fuel endurance (ATS-ordered) → battery → solar
      │                                  vs. the critical load
      ▼
CERI ──────────────── 0–100, four transparent sub-scores
      │
      ▼
Recovery ranking ──── exhaustive minimum-effort repair search,
                      ranked by population restored per repair-hour
```

**Before a flood** — audit exposure and score readiness. Output: a Climate Energy Readiness Index
with four sub-scores you can argue with individually (energy readiness, flood readiness, backup
duration, critical vulnerabilities).

**During** — determine whether the building can still carry its critical load, and why not,
without sending anyone into a flooded switch room.

**After** — rank repairs by what they restore per hour of work, not by what is most broken.

For the pilot building at 1.2 m of water, that produces: **repair the generator, 12 hours** —
deferring the battery (10 h), road access (8 h) and the transformer (48 h). Twelve hours of work
instead of seventy-eight, restoring the same 400 people.

---

## Why the dependency graph is the contribution

A damage report says *"the transformer is flooded."* That is true and close to useless, because it
does not say whether it matters.

The graph says: losing the transformer is survivable with a charged battery and fatal without one
— and losing the distribution panel is fatal either way, because every source is wired through it.
The panel is a single point of failure that no per-asset inspection can reveal, since the panel
itself may be perfectly dry and undamaged. It is a property of the *topology*, not the equipment.

Two design decisions that took real work:

**Connectivity is necessary, not sufficient.** Asking "is a wire still connected?" gives the wrong
answer at 1.2 m: the roof-mounted solar inverter survives, so the graph reads *powered*, while the
energy model reports 0 h of backup. The recovery search now takes an adequacy predicate — can this
building carry its critical load for the required window — layered on top of connectivity. Before
that fix, the system reported "already powered, nothing to repair" at exactly the depth the
shelter was worst off.

**The backup model sequences sources the way the hardware does.** Generator first, battery behind
it, because that is what the automatic transfer switch does; draining storage while fuel sits in
the tank would be the wrong way round. Undersized sets contribute nothing rather than a partial
load, since load-shedding is an operational decision the model has no basis to assume.

---

## Data honesty as an engineering property

Decision-support tools fail in the field when they present a guess and a measurement in the same
typeface. This system makes that structurally impossible.

Every campus-specific number is classified into one of four disjoint registries, in code:

- **Surveyed** — measured on site. The vertical datum (finished floor tied to MSL at 11.84 m), the
  2018 flood mark, six of eight equipment elevations, the DER nameplate, the grid topology.
- **Derived** — bounded from a desk using a surveyed input plus a cited public standard. Shelter
  capacity cannot exceed 1450 m² ÷ 3.5 m² per person (KSDMA Ed. 1) = 414.
- **Reported** — stated by facilities staff, not independently verified. Kept as its own tier
  because treating the people who run the building as guessing throws away real knowledge, while
  treating them as instruments claims a rigour nobody applied.
- **Still provisional** — not known.

The "still provisional" flag every API response carries is *derived* from that registry, not
hand-set. It cannot be cleared by editing a flag — only by replacing named values with
measurements. The test suite asserts the four registries stay disjoint, so an entry can never be
retired by moving it between tiers instead of measuring something.

Where a value cannot even be bounded, its absence is **priced**: the model runs the dependency
graph with unmeasured assets both dry and failed, and reports whether the outcome actually turns
on the gap. It does not claim to know whether the substation floods — it says how much it matters
that we don't, which is what decides whether the measurement is worth prioritising.

Current finding: none of the remaining gaps changes any recommendation at the modelled depths.

Two consequences worth stating plainly. The reported shelter capacity of 400 was checked against
the independently derived ceiling of 414 and agrees within 3.5% — that is corroboration, not
verification, and it is labelled as such. And the 12-hour backup requirement is **our design
choice, not a standard**: Kerala's relief standards require only that power "shall be ensured,"
with no duration, so the system never claims a building "meets the standard" on backup hours.

---

## What is built, and what this fellowship would fund

**Built and tested** — 80 passing regression tests, runs fully offline with zero API keys:

- Physics-informed digital twin (5R1C ISO-13790, peer-reviewed, sanity-checked against live weather)
- Per-asset flood inundation against a surveyed vertical datum
- Dependency graph with single-point-of-failure detection
- Backup energy model across generator, battery and solar
- CERI scoring with four transparent sub-scores
- Exhaustive minimum-effort recovery search and population-per-repair-hour ranking
- Retrofit scenario comparison and budget optimiser
- FastAPI backend, React decision dashboard, RAG copilot grounded in live simulation numbers

**Designed and stubbed** — `POST /api/observations` accepts live depth readings with an explicit
vertical datum, rejecting any reading it cannot honestly convert. When a reading arrives, the
dashboard scores against that live depth instead of a fixed scenario. A simulation script stands
in for the hardware today.

**Not built — this is the ask.** The autonomous ground robot that would populate that endpoint:
RGB and thermal imaging, water-level sensing, GPS/SLAM navigation, and the computer-vision layer
that turns inspection imagery into asset health states. Also terrain data (LiDAR or
photogrammetry), without which flood return periods cannot be derived from a single observed
high-water mark.

The decision layer is deliberately built first. An inspection robot with nothing to reason over
produces photographs; a reasoning system with a defined hardware interface produces decisions the
moment sensing arrives — and, in the meantime, produces them from a tape measure and a survey.

---

## Scaling

The pilot is one building because one building is what has been surveyed, and the system reports
exactly that rather than padding the demo with invented sites.

The architecture generalises to any set of buildings sharing upstream infrastructure — a campus,
a municipal ward, a hospital complex. The ranking layer already accepts multiple sites; what a
larger deployment adds is the case this project most wants to demonstrate: a single shared asset
whose repair restores a shelter, a clinic and a pump station at once. That is where
population-per-repair-hour stops being a sort key and starts being an allocation decision across
a district.

The method needs no proprietary data. It runs on free public weather, a published thermal standard,
and measurements a person with a tape measure and a GNSS fix can collect in an afternoon.

---

## Impact

Emergency managers allocate crews under time pressure with incomplete information. The prevailing
failure is not that damage goes undetected — it is that detected damage arrives as an
undifferentiated list, and the most expensive repair is not the most valuable one. This system
converts inspection data into an ordered plan, states its own uncertainty, and refuses to
manufacture the numbers it does not have.

---

*Digital twin: 5R1C ISO-13790 — Jayathissa et al., Applied Energy 202 (2017), ETH Zürich
Architecture & Building Systems (MIT licence). Early prototype for decision support — not a
substitute for on-site engineering assessment.*
