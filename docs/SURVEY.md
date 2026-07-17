# Campus survey — what to collect, and how

**Purpose.** Every recommendation ResilienceScout makes is real logic over invented inputs. This
document is what turns that around. It is written to be carried onto the campus and handed to
Sahrdaya's Estate / Facilities Officer.

The survey is complete when every `TODO(user)` in
[`backend/resilienceos/presets.py`](../backend/resilienceos/presets.py) and `REPAIR_EFFORT_H` in
[`backend/resilienceos/recovery.py`](../backend/resilienceos/recovery.py) has been replaced. At
that point `DATA_IS_PLACEHOLDER` flips to `False` and the amber banner self-clears.

**None of this is fetchable from a desk.** It has been checked. KSDMA publishes flood hazard
*probability* zones, not depths. No standard specifies per-asset mounting heights. The data does
not exist until someone measures it.

---

## 1. Ask for the single-line diagram first

**This is the highest-value item in the document.** Ask by name: *"the campus single-line
diagram (SLD)"*. Any institution with an HT connection is required to hold one for the electrical
inspectorate, so it exists.

It answers, in one drawing:
- **Which loads hang off which transformer** — this *is* the dependency graph the tool models
  (`presets.py` → `dependency_graph.py`). Currently invented.
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

## 3. The 2018 flood line

Thrissur district flooded badly in 2018. That event is the anchor for `FLOOD_LINE_M` and
`FLOOD_SCENARIOS_M` (`presets.py`), both currently invented — and unsourceable, because KSDMA's
published maps give probability zones, not depths.

Collect, per block:
- **How high did the water come?** Ask long-serving staff — maintenance, security, estate.
- **Water marks.** Often still visible on walls years later. Measure and photograph them.
- **Did anything flood that is still there?** A transformer that was submerged in 2018 and never
  moved is a finding on its own.
- Record the **datum** for each: above outside grade, or above that room's floor? Same trap as §2.

Corroborating context (regional, not campus-specific): KSDMA hazard maps at
sdma.kerala.gov.in/hazard-maps, and the 2018/2019/2020 event inundation maps at
sdma.kerala.gov.in/maps.

---

## 4. Population served

`pop_served` (`presets.py`) drives the entire recovery ranking. Currently 400 / 250 / 150 —
deliberately round so they read as obviously fake.

**Preferred:** the institution's own shelter capacity or room occupancy records.

**Fallback, if no headcount exists:** derive from floor area. The Kerala State Minimum Standards
of Relief (KSDMA, Edition 1, 9 July 2020) specifies **3.5 m² of covered area per person** in
relief centres (relaxed to 2.5 m² in mountainous areas — not applicable to Kodakara).

> capacity ≈ usable covered floor area (m²) ÷ 3.5

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

| Item | Where | Currently |
|---|---|---|
| Real block names and count | `presets.py` `SHELTERS` | `block_a/b/c` invented — the campus may have a different number of candidate shelters |
| Solar kWp, battery kWh + chemistry, generator fuel + runtime, critical load kW | `presets.py` `SHELTERS[*]["building"]` | invented; SLD + nameplates settle it |
| Floor area, number of floors | `presets.py` `SHELTERS[*]["building"]` | invented; site plan settles it |
| `AT_RISK_MARGIN_M` | `presets.py` | 0.3 — set from survey confidence once elevations are measured |
| `REQUIRED_BACKUP_H` | `presets.py` | 12.0. **No standard to copy from** — see below |

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

- [ ] Single-line diagram obtained
- [ ] All 8 asset elevations measured, per block, **with the floor-above-grade column filled**
- [ ] Photos with tape visible, filed against each measurement
- [ ] 2018 high-water line recorded per block, with datum noted
- [ ] `pop_served` per block — counted, or derived and labelled as derived
- [ ] Clinic / pump → transformer dependencies mapped
- [ ] DER nameplates recorded
- [ ] Repair effort hours estimated
- [ ] `REQUIRED_BACKUP_H` defended or explicitly labelled a design choice
- [ ] Every `TODO(user)` in `presets.py` replaced
- [ ] `REPAIR_EFFORT_H` in `recovery.py` replaced
- [ ] → **`DATA_IS_PLACEHOLDER = False`**, banner clears
