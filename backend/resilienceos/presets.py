"""
ResilienceScout — the data-provenance chokepoint.

Every campus-specific number the model depends on lives here, so that replacing an assumption
with a measurement is a one-file job rather than an archaeology expedition.

Two epistemic tiers, and the comments say which is which:
  * SOURCED  — a real, measured or cited value. Carries its provenance, and no TODO.
  * INVENTED — a guess. Carries a TODO(user).

After the site surveys of the Decennial Block (latest 2026-07-18) the SOURCED tier is now the
large majority: the vertical datum, the 2018 flood mark, six of eight equipment elevations and
the full DER nameplate are measured. What remains invented is enumerated in UNSURVEYED_VALUES
below — that registry, not a hand-set boolean, is what drives the dashboard notice.

One invented value lives outside this file: REPAIR_EFFORT_H in recovery.py.

See docs/SURVEY.md for how the remaining figures get collected.
"""
from __future__ import annotations

# --- Provenance registry ----------------------------------------------------------------------
# What is still NOT measured, and why each one matters. This is the single source of truth for
# the dashboard notice: `DATA_IS_PLACEHOLDER` is derived from it rather than set by hand, so the
# banner cannot drift out of step with the data the way a manual flag does.
#
# Remove an entry ONLY when the value it names has been replaced with a surveyed figure. When the
# last entry goes, DATA_IS_PLACEHOLDER becomes False on its own and the notice disappears.
UNSURVEYED_VALUES: dict[str, str] = {
    "pop_served": (
        "Shelter capacity is still the pre-survey 500. The survey measured DAILY OCCUPANCY "
        "(350–450), which is a different quantity — occupancy counts who is normally in the "
        "building, capacity counts who could shelter there. Drives the whole recovery ranking."
    ),
    "REPAIR_EFFORT_H": (
        "The substation has no surveyed repair estimate, so recovery.py falls through to a "
        "generic 8 h default — unlikely to be right for an 11 kV asset."
    ),
    "substation_elevation": (
        "Never measured, so it has no entry in EQUIPMENT_ELEVATION_M and therefore never floods "
        "in the model. Its graph node reads 'unknown' rather than 'ok' so the gap stays visible."
    ),
    "critical_load_kw": (
        "The survey recorded critical load twice and the records disagree: the circuit "
        "itemisation sums to 20.0 kW against a reported total of 18.0 kW. Divides into "
        "backup_hours, so a 10% error moves every ride-through figure on the dashboard."
    ),
}

# What IS measured. Kept alongside so the dashboard can lead with it: a notice that names only
# the gaps reads as though nothing has been done, which stopped being true after the 2026-07
# survey. Descriptive only — nothing in the model reads this.
SURVEYED_VALUES: dict[str, str] = {
    "vertical_datum": "Finished floor level tied to MSL (11.84 m) and to external grade (0.18 m step)",
    "flood_line": "August 2018 high-water mark, 0.82 m above finished floor, evidenced by wall staining",
    "equipment_elevations": "Six of eight measured on site; road_access and solar_panels still estimated",
    "der_nameplate": "Solar kWp, battery kWh + chemistry, generator rating/fuel/runtime, critical load",
    "survey_uncertainty": "Combined vertical uncertainty 0.03 m, driving the at-risk margin",
    "grid_topology": "Campus 11 kV substation confirmed as the feed, upstream of the 250 kVA transformer",
}

# Derived, never hand-set. True while any value above remains unmeasured.
DATA_IS_PLACEHOLDER = bool(UNSURVEYED_VALUES)

# --- Vertical datum ---------------------------------------------------------------------------
# READ THIS BEFORE ADDING ANY DEPTH OR ELEVATION.
#
# EVERY elevation and depth in this module is in metres ABOVE FINISHED FLOOR LEVEL (FFL) of the
# building. The surveyed equipment heights (transformer 1.10, battery 0.45, ...) are measured
# from the finished floor, so a flood depth is only comparable to them if it is in that same
# datum.
#
# Most flood figures in the wild are NOT. "1.2 m of water in the street" is above external
# ground. "3.84 m regional mean" (the 2018 satellite study) is above terrain/MSL, not above
# anyone's floor. Dropping such a figure straight into FLOOD_SCENARIOS_M silently offsets every
# margin in the model by the height of the floor slab, and nothing downstream can detect it —
# the numbers stay plausible and are simply wrong.
#
# So external figures MUST be converted through `depth_above_floor()` below, which refuses to
# guess: if the constant needed for the conversion has not been surveyed yet, it raises instead
# of returning a number.
ELEVATION_DATUM = "above_finished_floor_m"

# SOURCED: finished floor level of the Decennial Block, 11.84 m above MSL, reported by the field
# survey team (2026-07-18). This is the CONVERTER: it is what allows any externally quoted flood
# figure — historical, modelled or satellite — to be brought into this model's datum.
#
# READ THIS BEFORE CITING IT AS VALIDATED. The survey also reports the 2018 wall mark at 0.82 m
# above finished floor, and notes that the nearest regional reference (ILDM/SoI Flood Level Marker
# CKD05, Chalakudy taluk office, ~8 km SE) recorded the 2018 flood at 12.66 m MSL. Those three
# numbers satisfy 12.66 - 11.84 = 0.82 EXACTLY.
#
# Exact agreement to the centimetre between a wall mark here and a riverbank marker 8 km away,
# across different terrain and drainage, is not what independent measurements do. Either:
#   (a) 11.84 was measured at the building (GNSS/CORS or levelling), and the agreement is a
#       genuine and remarkable cross-check worth writing up; or
#   (b) 11.84 was computed as 12.66 - 0.82, in which case the identity is a DEFINITION, not a
#       check, and must not be cited as confirming either the wall mark or the campus flood level.
# The survey team has stated the values are measured, so this is recorded as SOURCED. But the
# arithmetic identity is documented here because it is invisible once the numbers are separated,
# and it is the first thing a reviewer will notice. Do not present (b) as (a).
FINISHED_FLOOR_LEVEL_MSL_M: float | None = 11.84

# SOURCED: surveyed step height from external ground to finished floor at the Decennial Block.
# This is what converts "water was this deep outside" observations — the most common kind of
# eyewitness report — into depth above the floor.
GROUND_TO_FLOOR_STEP_M: float | None = 0.18


class DatumError(ValueError):
    """Raised when a flood figure cannot be converted into this model's datum."""


def depth_above_floor(value_m: float, datum: str) -> float:
    """
    Convert an externally quoted flood figure into metres above finished floor level.

    `datum` must state what the figure was measured against:
      * "above_finished_floor_m" — already in our datum; passes through.
      * "above_external_ground_m" — needs GROUND_TO_FLOOR_STEP_M.
      * "above_msl_m" — needs FINISHED_FLOOR_LEVEL_MSL_M.

    Raises DatumError rather than guessing when the required survey constant is missing. That is
    the point: a loud failure beats a plausible wrong number, because a wrong datum is invisible
    in the output.

    Results are rounded to 4 dp (0.1 mm — far finer than any survey resolves). Without it the
    subtractions leak binary float noise into the API and onto the dashboard: 12.66 - 11.84 reads
    as 0.8200000000000003, which looks like false precision on a number measured with a tape.
    """
    if datum == ELEVATION_DATUM:
        return value_m
    if datum == "above_external_ground_m":
        if GROUND_TO_FLOOR_STEP_M is None:
            raise DatumError(
                "cannot convert an above-ground depth: GROUND_TO_FLOOR_STEP_M is unsurveyed. "
                "Measure the step from external ground to finished floor first."
            )
        return round(value_m - GROUND_TO_FLOOR_STEP_M, 4)
    if datum == "above_msl_m":
        if FINISHED_FLOOR_LEVEL_MSL_M is None:
            raise DatumError(
                "cannot convert an above-MSL depth: FINISHED_FLOOR_LEVEL_MSL_M is unsurveyed. "
                "One levelling run against a fixed benchmark closes this."
            )
        return round(value_m - FINISHED_FLOOR_LEVEL_MSL_M, 4)
    raise DatumError(
        f"unknown datum {datum!r}; expected one of "
        f"{[ELEVATION_DATUM, 'above_external_ground_m', 'above_msl_m']}"
    )


# --- Flood hazard --------------------------------------------------------------------------
# SOURCED: the observed August 2018 high-water mark at the Decennial Block main entrance lobby
# (see OBSERVED_EVENTS below) — 0.82 m above finished floor, evidenced by wall staining.
#
# This was previously an invented 0.9, then 0.78 from an earlier reading at the electrical room
# entrance. It matters more than it looks: CERI's flood_readiness scores the worst power-source
# margin against this line (engine.py), so this number sets the headline score of the building.
#
# The battery at 0.45 m sits 0.37 m BELOW this line — a real finding, not an artefact.
FLOOD_LINE_M = 0.82

# Observed high-water marks, measured above FFL. The August 2018 Kerala flood is the event staff
# remember and can physically point at, which is why an observed mark beats any modelled depth.
# Record the raw reading with the datum it was taken in, and convert via depth_above_floor().
OBSERVED_EVENTS: dict[str, dict] = {
    "kerala_2018": {
        "building": "Decennial Block",
        "room": "Main Entrance Lobby",
        "depth_m": 0.82,
        "datum": ELEVATION_DATUM,   # already above finished floor — no conversion needed
        "evidence": "wall staining",
        "observation_date": "2026-07-18",
        "observer": "Field Survey Team",
        "notes": (
            "Continuous mud line visible along north entrance wall. Highest clear flood mark "
            "measured 0.82 m above finished floor."
        ),
        # TODO(user): state WHY this mark survived eight years. The ILDM/SoI Flood Level Marking
        # report (Govt of Kerala, March 2026, §2.1.2) records that mud lines persist "even for
        # weeks if not cleaned up" and seed lines only "hours or days"; only stain lines absorbed
        # into porous material (concrete, wood) are described as durable. A mark read in 2026 from
        # a 2018 event is therefore plausible ONLY as an absorbed stain line, not a surface mud
        # line. The note above says "mud line". Reconcile the two, or a reviewer will read the
        # discrepancy as the mark being something other than 2018.
        #
        # SUPERSEDED: an earlier reading of 0.78 m at the Electrical Room Entrance. If that mark
        # still exists it is worth keeping as a SECOND observation — two marks in one building
        # cross-check each other within a single datum, which is stronger evidence than any
        # comparison against a regional marker 8 km away.
    },
}

# Design flood scenarios, metres above finished floor.
#
# `severe` (1.20) sits ABOVE the observed 2018 mark of 0.82, so it describes an event worse than
# the one on record rather than merely re-stating it. `minor` and `moderate` are modelled steps
# below it.
#
# TODO(user): the `extreme` band (previously 1.40) was REMOVED in the 2026-07 survey update, so
# the worst case the model now considers is 1.20 m. Confirm that removal is deliberate. It cuts
# the modelled envelope in the optimistic direction, and the caution below argues the opposite
# way — that the old 1.40 may itself have been an underestimate. A shelter that "passes" now has
# only been tested to 1.20 m.
#
# TODO(user): STILL PARTLY INVENTED — the 2018 observation anchors one point on this curve, but
# nothing here is return-period derived. "How deep is a 1-in-50 year event?" needs a terrain
# model plus local Karuvannur/drainage behaviour (docs/SURVEY.md §3.3), which is the drone
# photogrammetry ask. KSDMA publishes flood hazard PROBABILITY zones, not depths, so there is no
# public source that settles this. The ILDM/SoI report (March 2026) §5.2(vii-viii) confirms this
# route: with the state CORS network and geoid model in place, flood risk zonation now needs
# LiDAR drone terrain data, which is the same ask.
#
# EXTERNAL CAUTION (not a source of truth, do NOT copy these into the scenarios below):
# A satellite study of the August 2018 Kerala flood found the Kole lands of Thrissur rose by up
# to ~10 m, with a ~3.84 m regional mean inundation. Those are regional/terrain figures in a
# different datum, an order of magnitude above anything here — a standing reminder that the top
# of this range may still be an underestimate for the campus.
FLOOD_SCENARIOS_M = {
    "minor": 0.30,
    "moderate": 0.60,
    "severe": 1.20,
}

# --- Equipment elevations ------------------------------------------------------------------
# Height of each asset above finished floor [m]. Anything at or below the flood depth is
# assumed inundated and offline.
#
# SOURCED — measured on site at the Decennial Block (see docs/SURVEY.md). These are actuals, not
# code minimums, which matters: assuming code-minimum biases the model toward falsely reporting
# the shelter safe. Two entries are still NOT surveyed and keep their TODO(user).
#
# Note the survey corrected an estimate that was wrong in the dangerous direction: comms was
# guessed at 2.5 m assuming a mast mount, but the thing that actually carries connectivity is the
# NETWORK RACK at 2.00 m. Lower than assumed = floods sooner than the model previously believed.
EQUIPMENT_ELEVATION_M = {
    "transformer": 1.10,        # SOURCED: surveyed
    "battery": 0.45,            # SOURCED: surveyed — lowest-mounted asset, floods first
    "solar_inverter": 1.80,     # SOURCED: surveyed
    "distribution_panel": 1.60, # SOURCED: surveyed
    # SOURCED: surveyed. The survey measured the generator TWICE — alternator and control panel
    # sit at different heights. This models the ALTERNATOR (0.85 m), because that is the point at
    # which power generation physically stops. Caveat: collapsing two real measurements into one
    # node loses the case where the control panel drowns while the alternator is still dry (the
    # set survives but cannot be started/regulated). Splitting generator into two nodes would
    # capture it; not done here because it changes the graph topology.
    "generator": 0.85,
    "comms": 2.00,              # SOURCED: surveyed — network rack height (NOT a mast)
    "solar_panels": 9.6,        # TODO(user): still ESTIMATED — roof-mounted, not in this survey.
                                # Effectively never inundated, so the estimate is low-risk.
    # SOURCED: surveyed as 0.10 m above SURROUNDING GRADE — a different datum from every other
    # entry here. Converted rather than hand-adjusted, so the arithmetic is auditable and the
    # conversion fails loudly if GROUND_TO_FLOOR_STEP_M is ever unset again.
    #
    # The result is NEGATIVE (-0.08 m): the road sits below the building's finished floor, which
    # is both physically ordinary and operationally important — the access road floods before
    # anything inside the building does, cutting generator fuel resupply first.
    # Rounded at the point of definition: the raw subtraction yields -0.07999999999999999, which
    # serialises into the API and onto the dashboard as float noise.
    "road_access": round(depth_above_floor(0.10, "above_external_ground_m"), 3),
}

# Margin below which an asset is "at risk" rather than "ok" — i.e. the water is close.
#
# This should be DERIVED from measurement confidence, not chosen. "At risk" means "the water is
# within our ability to tell" — i.e. the asset's height and the water's height are close enough
# that the difference is inside the survey's own error bars. Picking a round 0.3 m instead is
# just a second guess layered on the first.
#
# SOURCED: 0.03 m, reported by the field survey team (2026-07-18).
#
# TODO(user): confirm this is the COMBINED figure, not the instrument spec. It must include how
# much finished floor level actually varies across the building, not just levelling precision. A
# 1450 m2 three-storey slab commonly varies by more than 3 cm on its own, so 0.03 looks like an
# instrument number that has not had floor variation folded in.
#
# This is not cosmetic. AT_RISK_MARGIN_M below is 2x this value, so 0.03 shrinks the amber
# "water is close" band from 0.30 m to 0.06 m — a factor of five. Assets that previously warned
# before drowning now go straight from "ok" to "failed", and the error is in the falsely-safe
# direction. If the combined figure is larger, this number should be larger.
SURVEY_UNCERTAINTY_M: float | None = 0.03

# Pre-survey placeholder. NOT derived from anything — retained only so the model runs and so the
# dashboard's amber "at risk" bands do not move until a real uncertainty exists.
_FALLBACK_AT_RISK_MARGIN_M = 0.3

# ~2 sigma: an asset counts as at risk once the water is within two standard deviations of it,
# so the warning fires while the difference is still inside measurement noise.
AT_RISK_MARGIN_M = (
    2 * SURVEY_UNCERTAINTY_M if SURVEY_UNCERTAINTY_M is not None
    else _FALLBACK_AT_RISK_MARGIN_M
)

# Which Building capability each asset carries. When an asset floods, its effect is applied to
# a copy of the Building, and the EXISTING energy-balance backup model does the rest.
EQUIPMENT_EFFECT = {
    "battery": {"battery_kwh": 0.0},
    "solar_inverter": {"solar_kwp": 0.0},   # panels intact, but nothing to convert their DC
    "generator": {"has_generator": False},
}

# RESOLVED (2026-07): the survey found two assets the graph had no node for. Wiring them in
# required a DECISION rather than a measurement, and both decisions have now been taken.
#
#   * UPS — MODELLED. Confirmed scope: it backs the IT load only (server rack 1.2 kW + network
#     0.8 kW = 2.0 kW of the critical load), NOT the 6.0 kW classroom circuit. It therefore sits
#     between the distribution panel and comms, and never gates shelter power — see
#     dependency_graph.py. This scoping is what keeps it honest: wiring the UPS to the shelter
#     node would have made it a single point of failure, which would be false. It carries no
#     EQUIPMENT_EFFECT entry because a UPS failure removes ride-through during the transfer
#     window, not stored energy, and the effect vocabulary below cannot express that. Modelling
#     it structurally without inventing an energy effect is deliberate.
#
#   * NETWORK RACK — NOT a separate node, on purpose. It is already what the `comms` node's
#     2.00 m elevation refers to. Adding a second node would duplicate the same physical asset
#     and double-count its failure.
#
# The UPS has no surveyed elevation, so node_health() reports it "unknown" rather than "ok".
# That is correct and must stay: do not give it a guessed height to make the map look complete.

# --- Operational targets -------------------------------------------------------------------
# TODO(user): pick and defend this number locally — there is no standard to copy it from.
# Checked the Kerala State Minimum Standards of Relief (KSDMA, Ed. 1, 9 July 2020): it requires
# only that "Power supply to relief camps shall be ensured (KSEB)" and that "Basic lighting
# facilities shall be made available", with NO duration in hours. NDMA's national guidelines are
# no more specific. So 12 h is OUR assumption, not a regulatory threshold, and any claim that a
# shelter "meets the standard" on backup hours would be unfounded.
REQUIRED_BACKUP_H = 12.0     # target critical-load ride-through during a flood event
CRITICAL_SPOF_LIMIT = 2      # above this many single points of failure, score bottoms out

# --- Shelter inventory ---------------------------------------------------------------------
# ONE real candidate building — the Decennial Block at Sahrdaya College of Engineering &
# Technology, Kodakara, Thrissur. The earlier three-shelter roster (Blocks A/B/C) was invented
# scaffolding; the demo is now honest about modelling the single building that actually exists.
#
# What is SOURCED vs INVENTED for this entry, AFTER the site survey:
#   * SOURCED  — identity and campus location; floor area; the full DER nameplate (solar kWp,
#                battery kWh/chemistry, generator rating/fuel/runtime); critical load; and six of
#                the eight equipment elevations.
#   * OPEN     — pop_served (see its TODO below), flood depths, road_access and solar_panels
#                elevations. DATA_IS_PLACEHOLDER therefore stays True: the hazard side of the
#                model is still unsurveyed even though the asset side is now real.
#
# The campus SUBSTATION (11 kV) is now CONFIRMED as the grid feed for this block and is modelled
# as an upstream node in dependency_graph.py, feeding the existing 250 kVA transformer.
SHELTERS = [
    {
        "id": "decennial_block",
        "name": "Decennial Block — Sahrdaya College of Engineering, Kodakara",
        # TODO(user): OPEN QUESTION — deliberately NOT overwritten by the survey. The survey
        # reported 350–450 DAILY OCCUPANCY, which is a different quantity from shelter capacity
        # during a flood (occupancy counts who is normally in the building; capacity counts who
        # could be sheltered there). 500 is the earlier placeholder, retained only so the model
        # runs. pop_served drives the entire recovery ranking, so this needs a real answer —
        # from the disaster-management plan, not from occupancy — before any ranking is acted on.
        "pop_served": 500,
        "building": {
            "name": "Decennial Block — Sahrdaya College of Engineering, Kodakara",
            # SOURCED: Sahrdaya College of Engineering & Technology, Kodakara, Thrissur campus
            # centre (10.3595, 76.2859).
            "latitude": 10.3595, "longitude": 76.2859,
            "floor_area_m2": 1450.0,   # SOURCED: surveyed
            "num_floors": 3,           # TODO(user): not re-confirmed by this survey.
            # SOURCED: surveyed — 40 panels x 450 W = 18.0 kWp.
            # CORRECTION: this was previously 180.0, an order-of-magnitude placeholder error.
            "solar_kwp": 18.0,
            # SOURCED: surveyed — LiFePO4, 384 V, 94% state of health.
            "battery_kwh": 40.0,
            # SOURCED: surveyed — 62.5 kVA diesel, 220 L tank, ~14 h runtime at 70% load,
            # automatic transfer switch (ATS) available.
            "has_generator": True,
            # SOURCED: surveyed total critical load, but UNRECONCILED against its own
            # itemisation — see CRITICAL_LOAD_ITEMISATION_KW and critical_load_discrepancy_kw()
            # below. The 18.0 is used here as the later-reported figure; the circuit breakdown
            # sums to 20.0. Worth settling because critical_load_kw divides into backup_hours —
            # a 10% error here moves every ride-through number on the dashboard.
            "critical_load_kw": 18.0,
        },
    },
]

POP_SERVED = {s["id"]: s["pop_served"] for s in SHELTERS}

# --- Critical load reconciliation ------------------------------------------------------------
# The survey recorded critical load TWICE and the two records disagree: this per-circuit
# breakdown sums to 20.0 kW, while the total reported later in the same survey is 18.0 kW.
#
# Held as data rather than as a comment so the disagreement is CHECKABLE. A note in a docstring
# decays silently the moment someone edits critical_load_kw; a function that recomputes the gap
# cannot. `critical_load_discrepancy_kw()` is asserted in the test suite, so the day the survey
# resolves this, the test fails and points at the remaining edit rather than letting a stale
# 2.0 kW gap sit in the file unnoticed.
#
# TODO(user): resolve which record is right. Not resolvable from here — it needs the survey team
# to say which line item changed or was dropped between the two readings. Do NOT "fix" this by
# scaling the itemisation to match 18.0: that would manufacture agreement rather than find it,
# and the whole value of holding both numbers is that they still disagree.
CRITICAL_LOAD_ITEMISATION_KW = {
    "emergency_lights": 2.0,
    "network": 0.8,
    "server_rack": 1.2,
    "classrooms": 6.0,
    "lift": 5.0,
    "fans": 2.5,
    "misc": 2.5,
}

# The later-reported total, used as critical_load_kw on the shelter above.
CRITICAL_LOAD_REPORTED_KW = 18.0


def critical_load_itemised_total_kw() -> float:
    return round(sum(CRITICAL_LOAD_ITEMISATION_KW.values()), 3)


def critical_load_discrepancy_kw() -> float:
    """
    Signed gap between the itemisation and the reported total (itemised - reported).

    Non-zero means the two survey records still disagree. Currently +2.0 kW: the circuits add up
    to more load than the reported total, so the dashboard's backup_hours is computed against the
    SMALLER figure and is therefore the OPTIMISTIC of the two readings — ride-through would be
    ~10% shorter if the itemisation turns out to be the correct one. That direction is why this
    is worth surfacing rather than quietly averaging.
    """
    return round(critical_load_itemised_total_kw() - CRITICAL_LOAD_REPORTED_KW, 3)


def critical_load_is_reconciled() -> bool:
    return critical_load_discrepancy_kw() == 0.0


def get_shelter(site_id: str) -> dict:
    for s in SHELTERS:
        if s["id"] == site_id:
            return s
    raise KeyError(f"unknown shelter id: {site_id!r} (known: {[s['id'] for s in SHELTERS]})")


def flooded_equipment(flood_depth_m: float) -> list[str]:
    """Assets at or below the flood depth. Sorted for deterministic output."""
    return sorted(
        name for name, elev in EQUIPMENT_ELEVATION_M.items() if elev <= flood_depth_m
    )
