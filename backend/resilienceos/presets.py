"""
ResilienceScout — the placeholder chokepoint.

Almost every number here is INVENTED and has never been surveyed. It exists so the app can run
end-to-end for a demo, and it is quarantined here so that replacing it with real data is a
one-file job rather than an archaeology expedition.

Two epistemic tiers, and the comments say which is which:
  * SOURCED  — a real, cited value. Carries its citation, and no TODO.
  * INVENTED — a guess. Carries a TODO(user). This is still the large majority of the file.

One placeholder lives outside this file: REPAIR_EFFORT_H in recovery.py.

`DATA_IS_PLACEHOLDER` is surfaced through the API as `placeholder: true` on every response, and
the dashboard renders a persistent "DEMO DATA — NOT SURVEYED" banner while it is True. Flip it
to False ONLY once every TODO below (and REPAIR_EFFORT_H) has been replaced with a surveyed
value. See docs/SURVEY.md for how to collect them.

WHAT MUST BE SURVEYED TO MAKE THIS REAL — no amount of desk research substitutes for these.
A site survey of the Decennial Block has now closed several of these; status per item:

  1. OPEN — Campus flood-line elevation and historical flood depths. KSDMA publishes only
     probability zones, not depths, so this still needs the 2018 high-water survey. This is now
     the single biggest thing standing between the model and being real: every asset elevation
     below is measured, but what the water actually does is still a guess.
  2. MOSTLY DONE — Mounting height of each piece of electrical equipment, measured from finished
     floor. Six of eight are now surveyed actuals. Still estimated: road_access and solar_panels.
  3. PARTLY DONE — the substation -> transformer dependency is now confirmed and modelled.
     Population served is still OPEN (the survey measured daily occupancy, which is not the same
     question — see the TODO on pop_served).
  4. DONE — Actual DER nameplate: solar kWp, battery kWh/chemistry, generator fuel + runtime.

So the ASSET side of the model is now largely real; the HAZARD side is not. That asymmetry is
exactly why DATA_IS_PLACEHOLDER stays True.
"""
from __future__ import annotations

# Flip to False only when every TODO in this file has been replaced with surveyed data.
DATA_IS_PLACEHOLDER = True

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

# TODO(user): SURVEY REQUIRED (item 1) — the finished floor level of the Decennial Block tied to
# a fixed external benchmark (MSL, or a named survey mark), from one levelling run with a dumpy
# level or total station. This single number is the CONVERTER: without it, no externally quoted
# flood figure — historical, modelled or satellite — can be brought into this model's datum.
# It is therefore the highest-value unmeasured number in the whole project.
FINISHED_FLOOR_LEVEL_MSL_M: float | None = None

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
    """
    if datum == ELEVATION_DATUM:
        return value_m
    if datum == "above_external_ground_m":
        if GROUND_TO_FLOOR_STEP_M is None:
            raise DatumError(
                "cannot convert an above-ground depth: GROUND_TO_FLOOR_STEP_M is unsurveyed. "
                "Measure the step from external ground to finished floor first."
            )
        return value_m - GROUND_TO_FLOOR_STEP_M
    if datum == "above_msl_m":
        if FINISHED_FLOOR_LEVEL_MSL_M is None:
            raise DatumError(
                "cannot convert an above-MSL depth: FINISHED_FLOOR_LEVEL_MSL_M is unsurveyed. "
                "One levelling run against a fixed benchmark closes this."
            )
        return value_m - FINISHED_FLOOR_LEVEL_MSL_M
    raise DatumError(
        f"unknown datum {datum!r}; expected one of "
        f"{[ELEVATION_DATUM, 'above_external_ground_m', 'above_msl_m']}"
    )


# --- Flood hazard --------------------------------------------------------------------------
# SOURCED: derived from the observed August 2018 high-water mark at the Decennial Block
# electrical room entrance (see OBSERVED_EVENTS below) — 0.78 m above finished floor.
#
# This was previously an invented 0.9, which mattered more than it looked: CERI's
# flood_readiness scores the worst power-source margin against this line (engine.py), so a
# guessed value was setting the headline score of a building whose asset heights are measured.
# It is now an observed event rather than a chosen number.
#
# The battery at 0.45 m still sits 0.33 m BELOW this line — that finding is now real rather than
# an artefact of the placeholder.
FLOOD_LINE_M = 0.78

# TODO(user): SURVEY REQUIRED (item 2) — observed high-water marks, measured above FFL.
# The August 2018 Kerala flood is the event staff remember and can physically point at: wall
# staining, debris lines, photographs. Measuring those marks converts the "severe" scenario below
# from an invention into an OBSERVED event with no modelling required, which is why this is the
# cheapest high-value item on the survey list.
# Record the raw reading with the datum it was taken in, and convert via depth_above_floor().
OBSERVED_EVENTS: dict[str, dict] = {
    "kerala_2018": {
        "building": "Decennial Block",
        "room": "Electrical Room Entrance",
        "depth_m": 0.78,
        "datum": ELEVATION_DATUM,   # already above finished floor — no conversion needed
        # TODO(user): record WHAT physically evidences this mark — wall staining, debris line,
        # photograph, or a named staff account. FLOOD_LINE_M is derived from this reading, so it
        # is the number the whole flood-readiness sub-score rests on; "observed" without a stated
        # form of evidence is the first thing a reviewer will ask about.
        "evidence": None,
    },
}

# Design flood scenarios, metres above finished floor.
#
# `severe` (1.10) and `extreme` (1.40) now sit ABOVE the observed 2018 mark of 0.78, so they
# describe events worse than the one on record rather than merely re-stating it. `minor` and
# `moderate` remain modelled steps below it.
#
# TODO(user): STILL PARTLY INVENTED — the 2018 observation anchors one point on this curve, but
# nothing here is return-period derived. "How deep is a 1-in-50 year event?" needs a terrain
# model plus local Karuvannur/drainage behaviour (docs/SURVEY.md §3.3), which is the drone
# photogrammetry ask. KSDMA publishes flood hazard PROBABILITY zones, not depths, so there is no
# public source that settles this.
#
# EXTERNAL CAUTION (not a source of truth, do NOT copy these into the scenarios below):
# A satellite study of the August 2018 Kerala flood found the Kole lands of Thrissur rose by up
# to ~10 m, with a ~3.84 m regional mean inundation. Those are regional/terrain figures in a
# different datum, an order of magnitude above anything here — which is a standing reminder that
# `extreme` may still be an underestimate for the campus. Do not treat them as scenario inputs.
FLOOD_SCENARIOS_M = {
    "minor": 0.30,
    "moderate": 0.60,
    "severe": 1.10,
    "extreme": 1.40,
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
    "road_access": depth_above_floor(0.10, "above_external_ground_m"),
}

# Margin below which an asset is "at risk" rather than "ok" — i.e. the water is close.
#
# This should be DERIVED from measurement confidence, not chosen. "At risk" means "the water is
# within our ability to tell" — i.e. the asset's height and the water's height are close enough
# that the difference is inside the survey's own error bars. Picking a round 0.3 m instead is
# just a second guess layered on the first.
#
# TODO(user): SURVEY REQUIRED (item 4) — the combined vertical uncertainty of the levelling run:
# instrument error plus how much finished floor level actually varies across the building. This
# falls out of the item-1 levelling run for free, so it costs nothing extra to collect.
SURVEY_UNCERTAINTY_M: float | None = None

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

# TODO(user): NOT MODELLED YET — the survey found two assets the graph has no node for:
#   * UPS          — bridges the gap between mains loss and generator start.
#   * NETWORK RACK — already measured at 2.00 m (it is what "comms" elevation now refers to),
#                    but it is not a separate node.
# They are deliberately left out rather than guessed at, because wiring them in requires a
# DECISION, not a measurement: what Building capability does each one's failure actually remove?
# The existing EQUIPMENT_EFFECT vocabulary only knows how to zero out solar_kwp, battery_kwh and
# has_generator — none of which is what a UPS or a network rack does. A UPS failure does not
# reduce stored energy so much as remove ride-through during the transfer window, and a network
# rack failure removes coordination, not power (which is why comms deliberately never gates power
# in the dependency graph). Modelling either one honestly means first deciding what capability it
# carries and possibly extending the effect vocabulary. Do not guess this one.

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
            # SOURCED: surveyed total critical load.
            #
            # TODO(user): UNRECONCILED against its own itemisation. The circuit breakdown
            # recorded earlier in the survey was:
            #   emergency lights 2.0 + network 0.8 + server rack 1.2 + classrooms 6.0
            #   + lift 5.0 + fans 2.5 + misc 2.5  =  20.0 kW
            # but the total subsequently reported is 18.0 kW. The 18.0 is used here as the later
            # figure; which line item changed (or whether one was dropped) is unresolved. Worth
            # settling because critical_load_kw divides into backup_hours — a 10% error here
            # moves every ride-through number on the dashboard.
            "critical_load_kw": 18.0,
        },
    },
]

POP_SERVED = {s["id"]: s["pop_served"] for s in SHELTERS}


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
