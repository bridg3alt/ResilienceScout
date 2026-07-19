# Campus survey — what to collect, and how

**Purpose.** ResilienceScout is real logic over campus-specific inputs. This document is the
record of which of those inputs have been measured and which have not. It is written to be
carried onto the campus and handed to Sahrdaya's Estate / Facilities Officer.

**Status after the surveys of 2026-07-18.** Most of the model is now measured: the vertical
datum, the August 2018 flood mark, six of eight equipment elevations, the full DER nameplate and
the grid topology. Four values remain provisional — they are listed in §6 and enumerated in code
as `presets.UNSURVEYED_VALUES`.

The survey is complete when that registry is empty. `DATA_IS_PLACEHOLDER` is *derived* from it
(`bool(UNSURVEYED_VALUES)`), so the dashboard notice clears itself the moment the last value is
replaced — it cannot be cleared by editing a flag.

**None of this is fetchable from a desk.** It has been checked. KSDMA publishes flood hazard
*probability* zones, not depths. No standard specifies per-asset mounting heights. The data does
not exist until someone measures it.

One route did open up, though: the ILDM / Survey of India *Flood Level Marking Survey* report
(Govt of Kerala, March 2026) confirms that with the state CORS network, geoid model and dense
benchmark network now in place, the MSL height of any location in Kerala can be fixed with a few
minutes of GNSS observation (§5.2(iii)). That is what made §3.1 below cheap.

---

## 1. Ask for the single-line diagram first

**This is the highest-value item in the document.** Ask by name: *"the campus single-line
diagram (SLD)"*. Any institution with an HT connection is required to hold one for the electrical
inspectorate, so it exists.

It answers, in one drawing:
- **Which loads hang off which transformer** — this *is* the dependency graph the tool models
  (`presets.py` → `dependency_graph.py`). The campus 11 kV substation is now confirmed as the
  feed, upstream of the 250 kVA transformer, and the UPS is confirmed as backing the IT load
  only (server rack + network, 2.0 kW). The SLD would confirm the rest of the panel hierarchy.
- **DER nameplate ratings** — transformer kVA, generator kVA, solar kWp, inverter rating.
- Panel hierarchy, which tells you whether the distribution panel really is the single point of
  failure the model currently assumes it is.

**Route:** Electrical Engineering HOD → Estate Officer. An engineering college has both.

**Ask alongside it:** the campus site plan / block layout, and the KSEB net-metering or PPA
agreement (gives the sanctioned solar capacity in writing).

---

## 2. Equipment elevations — the measurement that matters most

One row per asset per block. Keys must match `EQUIPMENT_ELEVATION_M` in `presets.py` exactly so
transcription is mechanical.

| Block | Asset key | Height above finished floor (m) | Floor height above outside grade (m) | Photo ref | Notes |
|---|---|---|---|---|---|
| | `transformer` | | | | measure to base of windings/bushings |
| | `battery` | | | | measure to bottom of the **lowest** cell |
| | `solar_inverter` | | | | bottom of enclosure — usually ground level |
| | `solar_panels` | | | | roof-mounted; height above grade is fine |
| | `generator` | | | | base of the skid/alternator |
| | `distribution_panel` | | | | bottom of the enclosure |
| | `road_access` | | | | lowest point of the access road |
| | `comms` | | | | mast/rack base |

### Rules

1. **Measure the lowest vulnerable component**, not the top of the box. A transformer is dead when
   its windings are wet, not when the enclosure lid is.
2. **Record floor height above outside grade in its own column. Do not skip this.** It is the
   single most likely thing to be forgotten, and getting it wrong silently offsets the entire
   flood model. `presets.py` stores elevations *above finished floor level*, but flood depth is
   quoted *above outside ground*. A panel 1.0 m above a floor that sits 0.4 m above grade is
   really 1.4 m above grade. Mixing the two datums makes every result wrong in a way nothing in
   the code can detect.
3. **Photograph each measurement with the tape visible.** That is the evidence, and it doubles as
   training data if computer-vision inspection is ever added.
4. **Do not substitute code minimums for measurements.** Standards give minimums, not actuals, and
   retrofit solar installs routinely ignore plinth specs. If you assume code-minimum and the real
   inverter sits lower, the tool reports a shelter operational when it will drown — the one
   direction this tool must never be wrong in. If a measurement is impossible, leave it blank and
   flag it. A gap is honest; a guess dressed as a measurement is not.

---

## 3. The hazard side — now anchored to measurements

Both sides of the model are now measured. The asset side has six surveyed elevations, a real DER
nameplate and a real critical load; the hazard side has a floor level tied to MSL and an observed,
evidenced 2018 flood mark. `FLOOD_LINE_M` is no longer a guess driving the headline score of a
building whose assets are known — that asymmetry is closed.

What remains open on this side is the *scenario ladder*: the depths for return-period events are
still modelled rather than derived (§3.3).

### 3.1 Finished floor level, tied to a fixed benchmark — DONE

Every elevation in `presets.py` is measured *above finished floor level* (FFL). Every flood figure
you will ever be handed is measured against something else — above the street, above mean sea
level, above terrain. Without the FFL you cannot convert between them.

**Recorded 2026-07-18:**
- `FINISHED_FLOOR_LEVEL_MSL_M = 11.84` — Decennial Block FFL above mean sea level.
- `GROUND_TO_FLOOR_STEP_M = 0.18` — step from external grade to finished floor, which makes
  "water was this deep outside" eyewitness accounts convertible.
- `SURVEY_UNCERTAINTY_M = 0.03` — see §3.4.

**Consequence:** `presets.depth_above_floor()` now converts `above_msl_m` readings instead of
raising, and `POST /api/observations` accepts them, storing the converted depth alongside the
untouched raw reading so the conversion stays auditable.

> **Open caveat on this number.** The nearest regional reference — ILDM/SoI Flood Level Marker
> **CKD05** (Chalakudy taluk office, ~8 km SE), 2018 flood at **12.66 m MSL** — satisfies
> `12.66 − 11.84 = 0.82`, exactly the wall mark in §3.2. Exact centimetre agreement between a mark
> here and a riverbank 8 km away across different terrain is not what independent measurements do.
> If 11.84 was measured at the building, that agreement is a genuine and striking cross-check. If
> it was computed as `12.66 − 0.82`, the identity is a *definition* and must not be cited as
> confirming either figure. Confirm which, and record it — this is the first thing a reviewer will
> check. See the note on `FINISHED_FLOOR_LEVEL_MSL_M` in `presets.py`.

### 3.2 The 2018 high-water mark — RECORDED

**Done.** Decennial Block, **main entrance lobby**: **0.82 m above finished floor**, already in
the model's datum so no conversion was needed. Evidence: **wall staining** — a continuous mud line
along the north entrance wall, observed 2026-07-18 by the field survey team. Recorded in
`presets.OBSERVED_EVENTS["kerala_2018"]`; `FLOOD_LINE_M` derives from it.

The ground-to-floor step at **0.18 m** makes above-grade readings convertible — the access road,
measured at 0.10 m above surrounding grade, resolves to **−0.08 m** relative to the floor, i.e.
the road floods before anything inside the building does.

**Still outstanding on this item:** state *why* the mark survived eight years. The ILDM/SoI report
(§2.1.2) records that mud lines persist "even for weeks if not cleaned up" and seed lines only
"hours or days"; only stain lines absorbed into porous material are described as durable. A mark
read in 2026 from a 2018 event is plausible as an absorbed stain line, not a surface mud line —
and the note currently says "mud line". Reconcile the wording, or a reviewer will read the
discrepancy as the mark being something other than 2018.

**Superseded:** an earlier reading of 0.78 m at the electrical room entrance. If that mark still
exists it is worth keeping as a *second* observation — two marks in one building cross-check each
other inside a single datum, which is stronger evidence than any comparison against a marker 8 km
away.

Original collection guidance retained below for the remaining blocks.



Thrissur district flooded badly in 2018 and it is the event people remember and can physically
point at. Measuring those marks converts the `severe` scenario from an invention into an
**observed event with no modelling required** — the cheapest real hazard number available.

Collect, per block:
- **How high did the water come?** Ask long-serving staff — maintenance, security, estate.
- **Water marks.** Often still visible on walls years later. Measure and photograph them.
- **Did anything flood that is still there?** A transformer that was submerged in 2018 and never
  moved is a finding on its own.
- **Record the datum for every single reading** — above outside grade, or above that room's
  floor? Do not normalise in your head on site; write the raw number and what it was measured
  against, and let `depth_above_floor()` convert it.

→ `OBSERVED_EVENTS["kerala_2018"]` in `presets.py` (`depth_m`, `datum`, `evidence`).

Corroborating context (regional, not campus-specific): KSDMA hazard maps at
sdma.kerala.gov.in/hazard-maps, and the 2018/2019/2020 event inundation maps at
sdma.kerala.gov.in/maps. Note these are *probability zones, not depths* — corroboration only.

### 3.3 Return-period depths — explicitly left open

The "what about a 1-in-50 year event?" question needs a terrain model plus local Karuvannur river
and campus drainage behaviour. That is not a clipboard item: it needs photogrammetry or LiDAR and
a hydraulic model.

**This is exactly the drone ask in the fellowship application, and the honest position is to say
so rather than to model it badly.** `FLOOD_SCENARIOS_M` stays flagged until then.

### 3.4 Survey uncertainty — RECORDED

**Done.** `SURVEY_UNCERTAINTY_M = 0.03`. `AT_RISK_MARGIN_M` is now *derived* from it at ~2σ
(0.06 m) rather than chosen as a round number — "at risk" now means "the water is within our
ability to tell", not "within 30 cm because 30 sounded reasonable". The old 0.3 m fallback remains
in code as a guard for the case where the uncertainty is ever reset to `None`.

**Still outstanding:** confirm 0.03 is the **combined** figure — instrument error *plus* how much
finished floor level varies across the building — and not just the instrument spec. A 1450 m²
three-storey slab commonly varies by more than 3 cm on its own. This is not cosmetic: the margin
is 2× this number, so 0.03 shrinks the amber "water is close" band by a factor of five, and assets
that used to warn before drowning now go straight from *ok* to *failed*. The error direction is
falsely-safe, which is the one direction this tool must not be wrong in.

---

## 4. Population served

`pop_served` (`presets.py`) drives the entire recovery ranking. Currently a round, obviously-fake
500 for the Decennial Block.

**Not answered by the equipment survey.** That survey reported 350–450 *daily occupancy*, which is
a different quantity: occupancy counts who is normally in the building on a working day, capacity
counts who could be sheltered there during a flood. The placeholder was deliberately left in
rather than silently overwritten with an occupancy figure.

**Preferred:** the institution's own shelter capacity or room occupancy records, or the
disaster-management plan.

**Fallback, if no headcount exists:** derive from floor area. The Kerala State Minimum Standards
of Relief (KSDMA, Edition 1, 9 July 2020) specifies **3.5 m² of covered area per person** in
relief centres (relaxed to 2.5 m² in mountainous areas — not applicable to Kodakara).

> capacity ≈ usable covered floor area (m²) ÷ 3.5

**This is now implemented as a bound** — `presets.shelter_capacity_upper_bound()`, computed from
the *gross* surveyed area (1450 m²) because usable area is not yet known. It yields **414**, which
is *below* the standing placeholder of 500. See §7.1: the guess is not merely unmeasured, it is
inconsistent with the surveyed area under the governing standard.

**If you derive it, record that it was derived, not counted.** Write the floor area you used and
the date. A derived number is defensible; a derived number presented as a census is not.

**Also capture** — no formula substitutes for this: which clinics, water pumps, or other critical
services depend on which transformer. The SLD (§1) answers this.

---

## 5. Repair effort hours

`REPAIR_EFFORT_H` in `recovery.py`. An informal interview with the maintenance supervisor is
enough: *"if the solar inverter drowned, how long to swap it? The transformer? The panel?"*

Rough is fine — these only affect ranking **order**, not magnitude. Capture whether the estimate
assumes parts on hand or procurement lead time, and note it.

---

## 6. Remaining smaller items

| Item | Where | Status |
|---|---|---|
| Shelter roster | `presets.py` `SHELTERS` | **DONE** — the invented `block_a/b/c` scaffolding is gone; the model covers the one real building, the Decennial Block |
| Solar kWp, battery kWh + chemistry, generator fuel + runtime | `presets.py` `SHELTERS[*]["building"]` | **DONE** — 18.0 kWp (40 × 450 W), 40 kWh LiFePO4 @ 384 V / 94% SoH, 62.5 kVA diesel, 220 L, ~14 h at 70% load, ATS fitted |
| Critical load kW | `presets.py` `SHELTERS[*]["building"]` | **OPEN** — two survey records disagree: itemisation sums to 20.0 kW, reported total 18.0 kW. See `critical_load_discrepancy_kw()` |
| Floor area | `presets.py` `SHELTERS[*]["building"]` | **DONE** — 1450 m² surveyed |
| Number of floors | `presets.py` `SHELTERS[*]["building"]` | **OPEN** — 3 not re-confirmed by this survey |
| `AT_RISK_MARGIN_M` | `presets.py` | **DONE** — now derived at 2σ of `SURVEY_UNCERTAINTY_M` (0.06 m), not chosen |
| `solar_panels` / `road_access` elevations | `presets.py` | **OPEN** — the two of eight still estimated rather than measured |
| `extreme` flood scenario | `presets.py` `FLOOD_SCENARIOS_M` | **OPEN** — the 1.40 m band was *removed* in the 2026-07 update, so the modelled worst case is now 1.20 m. Confirm the removal is deliberate; it cuts the envelope optimistically |
| `REQUIRED_BACKUP_H` | `presets.py` | **OPEN** — 12.0. **No standard to copy from** — see below |

### On `REQUIRED_BACKUP_H`

This was checked and the honest answer is that no source specifies it. The Kerala State Minimum
Standards of Relief requires only that *"Power supply to relief camps shall be ensured (KSEB)"*
and that *"Basic lighting facilities shall be made available in the temporary shelters"* — no
duration. NDMA's national guidelines are no more specific.

So 12 h is **our assumption**, not a regulatory threshold. Either defend it locally (e.g. against
the observed KSEB restoration time in the 2018 event) or state plainly that it is a design choice.
Do not describe a shelter as "meeting the standard" on backup hours — there is no such standard.

---

## Completion checklist

Done:

- [x] Finished floor level tied to MSL (11.84 m) — §3.1
- [x] Ground-to-floor step recorded (0.18 m) — §3.1
- [x] Survey uncertainty recorded (0.03 m) → `AT_RISK_MARGIN_M` now derived — §3.4
- [x] 2018 high-water line recorded, with datum and evidence noted (0.82 m, wall staining) — §3.2
- [x] DER nameplates recorded (solar, battery, generator, ATS)
- [x] Floor area surveyed (1450 m²)
- [x] Substation → transformer dependency confirmed and modelled
- [x] UPS scope confirmed (IT load only: server rack + network, 2.0 kW) and wired into the graph

Outstanding:

- [ ] Single-line diagram obtained
- [ ] Remaining 2 of 8 asset elevations measured (`solar_panels`, `road_access`)
- [ ] Substation elevation measured — until then it never floods in the model
- [ ] Photos with tape visible, filed against each measurement
- [ ] Confirm the 2018 mark's evidence type (absorbed stain line vs surface mud line) — §3.2
- [ ] Confirm `FINISHED_FLOOR_LEVEL_MSL_M` was measured, not derived from CKD05 — §3.1
- [ ] Confirm `SURVEY_UNCERTAINTY_M` is the combined figure, not the instrument spec — §3.4
- [ ] `pop_served` — counted, or derived and labelled as derived
- [ ] Critical load reconciled (20.0 kW itemised vs 18.0 kW reported)
- [ ] Number of floors re-confirmed
- [ ] Clinic / pump → transformer dependencies mapped
- [ ] Repair effort hours estimated (`REPAIR_EFFORT_H`, incl. the substation)
- [ ] `REQUIRED_BACKUP_H` defended or explicitly labelled a design choice
- [ ] Confirm the removal of the `extreme` flood band is deliberate
- [ ] Return-period depths for `FLOOD_SCENARIOS_M` — needs LiDAR/photogrammetry (§3.3)
- [ ] → `presets.UNSURVEYED_VALUES` empty, so **`DATA_IS_PLACEHOLDER` becomes `False`** on its
      own and the dashboard notice clears

---

## 7. What is still provisional, and how each one closes

The four entries in `presets.UNSURVEYED_VALUES` — the registry that keeps the dashboard notice up.
This is the project's remaining data ask.

| Value | Why it matters | How it closes |
|---|---|---|
| `pop_served` | Drives the entire recovery ranking — which shelter gets fixed first | Institution's shelter capacity records or disaster-management plan. **Now bounded from a desk** at ≤414 — see §7.1 |
| `critical_load_kw` | Divides into `backup_hours`; a 10% error moves every ride-through figure on the dashboard | Survey team confirms which of the two records is right, or which line item changed between them. Do **not** scale the itemisation to force agreement — §6. **Now reported as a range** rather than a point — §7.1 |
| `substation_elevation` | Unmeasured, so the substation never floods in the model and SPOF detection is incomplete | One height measurement, same method as §2. **Its cost is now priced** by `unassessed_sensitivity()` — §7.1 |
| `REPAIR_EFFORT_H` | Substation falls through to a generic 8 h default, unrealistic for an 11 kV asset | Interview with the maintenance supervisor — §5. **Now declared** as a fallback in every plan that uses it — §7.1 |

**Route for anything needing an MSL tie:** per the ILDM/SoI report §5.2(iii), the state CORS
network, geoid model and SoI benchmark network make this a few minutes of GNSS observation, not a
levelling expedition. Trained teams exist at SoI, the State Survey Department, KLRMM and the River
Management Centre, coordinated through ILDM.

---

### 7.1 What was closed WITHOUT a site visit

None of these four can be *measured* from a desk, and none of them has been. What follows is what
could be done instead: bound them, price them, or declare them. Each is implemented and tested.

They deliberately do **not** clear `DATA_IS_PLACEHOLDER`. A bound is not a measurement, and the
notice must not soften just because the gaps are now better characterised. `presets.DERIVED_VALUES`
is a separate registry from `SURVEYED_VALUES` for exactly this reason — so the dashboard can never
present a derivation as a survey.

**`pop_served` — bounded, and the bound contradicts the guess.**
Capacity cannot exceed surveyed floor area ÷ the KSDMA minimum covered area per person:
1450 m² ÷ 3.5 = **414 people**. The standing `pop_served` is 500. So it is not merely unmeasured —
it is *inconsistent with the surveyed floor area under the governing standard*, and it errs toward
overstating how many people each repair restores. `presets.pop_served_exceeds_area_bound()` asserts
this, and the test fails the day someone replaces 500 with a real figure — which is the prompt to
re-check the new number against the same ceiling.
This is an **upper bound only**. Gross floor area counts corridors, stairwells, toilets and plant
rooms as sleepable, so true capacity is strictly lower. Inventing a usable-area fraction to
"improve" the estimate would fabricate the very measurement the bound exists to avoid.

**`critical_load_kw` — reported as the interval, never averaged.**
The two records (18.0 reported, 20.0 itemised) bracket the load. `/api/sites/{id}/backup` now
returns `hours_range` computed at *both* ends, plus `adequate_worst_case`. When that disagrees with
`adequate`, whether the shelter meets its backup target depends on an unsettled survey record —
which is precisely what must not be rounded away. Averaging to 19.0 would produce a number neither
record supports and would hide the disagreement behind false precision.

**`substation_elevation` — its absence is now priced, not inherited.**
The model can never flood an asset it has no elevation for, so every result silently assumed the
substation survived. `dependency_graph.unassessed_sensitivity()` runs the graph *both* ways — all
unassessed assets dry, then all failed — and reports whether the shelter's outcome actually turns
on the gap. It does not tell us whether the substation floods; it tells us how much it matters that
we do not know, which is what decides whether the measurement is worth prioritising.

**`REPAIR_EFFORT_H` — the guess is declared rather than dressed up.**
The generic 8 h fallback is *kept*, deliberately. Inflating it to something "safer" would be
equally invented and would additionally bias the ranking by making grid restoration look
unattractive on fabricated grounds. Instead `recovery.effort_is_estimated()` marks it, and every
ranked plan carries `estimated_effort_repairs` — so a reader can see which parts of a ranking rest
on a fallback.

### 7.2 Getting the rest without going to campus

The highest-value remaining items are **documents, not measurements** — they can be requested
remotely. In rough order of value per unit of effort:

| Ask | From whom | Closes |
|---|---|---|
| Single-line diagram (§1) | Estate / Facilities Officer, by email | Grid topology, clinic/pump dependencies, and usually the substation's location |
| Approved building floor plans | Estate Office or the original architect | Usable (not gross) floor area → tightens the `pop_served` bound from an upper limit toward an estimate |
| Institutional disaster-management plan | Principal's office / NSS or NCC unit | `pop_served` directly, as a counted figure |
| The two conflicting load records (§6) | The survey team that produced them | `critical_load_kw` — this needs one email asking which line item changed, not a re-survey |
| Maintenance contract / AMC schedule | Estate Office | `REPAIR_EFFORT_H` — AMC documents usually state response and restoration times per asset class |
| KSEB restoration log for the 2018 event | KSEB section office, or the institution's own outage records | Would let `REQUIRED_BACKUP_H = 12` be *defended* locally instead of remaining a bare design choice |

**A remotely-obtained figure is still a sourced figure**, provided the provenance says so. Record
who supplied it, when, and in what document — the same discipline §3 applies to a tape measure. A
floor plan emailed by the Estate Office is better evidence than a number someone recalled on site.

**What genuinely cannot be done remotely:** the two remaining asset elevations
(`solar_panels`, `road_access`), the substation elevation, and the photographic record. These need
someone physically present with a tape. If no visit is possible at all, they stay open — and the
dashboard keeps saying so, which is the correct outcome rather than a failure of the tool.
