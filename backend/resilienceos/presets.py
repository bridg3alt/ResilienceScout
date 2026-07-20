"""
ResilienceScout — the data-provenance chokepoint.

Every campus-specific number the model depends on lives here, so that replacing an assumption
with a measurement is a one-file job rather than an archaeology expedition.

Four epistemic tiers, and the comments say which is which:
  * SOURCED  — a real, measured or cited value. Carries its provenance, and no TODO.
  * DERIVED  — not measured here, but COMPUTED from a surveyed input plus a published standard,
               with both named. Weaker than SOURCED, categorically stronger than a guess,
               because a reader can recheck the arithmetic and challenge the citation.
  * REPORTED — stated by the site owner (college facilities staff, institutional records) but not
               independently verified. Weaker than SOURCED because nobody checked it; far stronger
               than INVENTED because it has a named human source who can be asked again.
  * INVENTED — a guess. Carries a TODO(user).

The DERIVED tier exists because some gaps can be closed from a desk and some cannot, and
collapsing that distinction wastes the ones that can. It is NOT a way to retire a TODO quietly:
a derived value stays in UNSURVEYED_VALUES until it is actually measured. What it buys is a
defensible number to reason with, and — as with shelter capacity below — sometimes a derivation
CONTRADICTS the standing guess, which is a finding in itself.

After the site surveys of the Decennial Block (latest 2026-07-18) the SOURCED tier is now the
large majority: the vertical datum, the 2018 flood mark, six of eight equipment elevations and
the full DER nameplate are measured. What remains invented is enumerated in UNSURVEYED_VALUES
below — that registry, not a hand-set boolean, is what drives the dashboard notice.

One invented value lives outside this file: REPAIR_EFFORT_H in recovery.py.

See the site survey record for how the remaining figures get collected.
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
    "REPAIR_EFFORT_H": (
        "The substation has no surveyed repair estimate, so recovery.py falls through to a "
        "generic 8 h default — unlikely to be right for an 11 kV asset. Now only load-bearing if "
        "the college's report that the substation sits above flood level turns out to be wrong: "
        "while that holds, the substation never fails and never enters a repair plan."
    ),
}

# --- Reported by the site owner, NOT independently verified -------------------------------------
# Values stated by Sahrdaya College facilities staff and recorded on the author's account of that
# conversation. There is no survey record, no document reference and no instrument reading behind
# any of them.
#
# This tier exists because the alternative was worse in both directions. Treating a statement from
# the people who run the building as if it were a guess throws away real knowledge; treating it as
# a measurement claims a rigour that was never applied. Naming it for what it is lets the model use
# the figure while leaving a reviewer free to weigh it — and leaves an obvious next step, which is
# simply to get it in writing.
#
# These do NOT clear DATA_IS_PLACEHOLDER on their own, but they are reported separately from
# UNSURVEYED_VALUES so the dashboard can distinguish "nobody knows" from "the college says, but
# nobody has checked".
#
# TODO(user): ask the Estate / Facilities Officer to confirm each of these BY EMAIL. A one-line
# written reply converts all three from REPORTED to SOURCED at zero cost and no site visit, and is
# the single highest-value follow-up left on the project — see the site survey record §7.2.
REPORTED_VALUES: dict[str, str] = {
    "pop_served": (
        "Shelter capacity of 400 reported by college staff. Supersedes the invented pre-survey "
        "500, which exceeded what the floor area allows. 400 sits WITHIN the independently "
        "derived ceiling of 414 (see shelter_capacity_upper_bound), so the report and the "
        "surveyed floor area corroborate each other — a genuine cross-check, not a coincidence "
        "worth glossing over."
    ),
    "critical_load_kw": (
        "College confirms the reported total of 18.0 kW is the correct figure, resolving which "
        "of the two survey records to use. NOTE this does not make the records agree: the "
        "circuit itemisation still sums to 20.0 kW, so there is an error of 2.0 kW somewhere in "
        "that breakdown which nobody has located. Kept visible via critical_load_discrepancy_kw()."
    ),
    "substation_flood_exposure": (
        "College reports the 11 kV substation sits on notably high ground and did not flood in "
        "2018. Recorded as a flood-exposure claim rather than an elevation, because no height "
        "was given and inventing one would fabricate a measurement. Modelled via "
        "REPORTED_ABOVE_FLOOD below; unassessed_sensitivity() still prices what happens if the "
        "report is wrong."
    ),
}

# Assets the site owner reports as sitting above any credible flood level, WITHOUT giving a height.
#
# Deliberately a set of names rather than an elevation dict: the college said "high ground", not
# "2.4 m". Writing a number here to make the arithmetic work would invent the very measurement
# this file exists to protect. So the claim is modelled at the resolution it was actually made —
# binary, not metric — and node_health reports these as "ok (reported)" rather than "unknown".
#
# The claim is used AND still tested: unassessed_sensitivity() continues to run the graph with
# these assets failed, so the cost of the report being wrong stays visible on the dashboard.
REPORTED_ABOVE_FLOOD: frozenset[str] = frozenset({"substation"})

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

# What has been CONSTRAINED without a site visit — computed from a surveyed input plus a cited
# public standard. Each entry names the inputs and the source, so the arithmetic is recheckable.
#
# These deliberately do NOT clear their UNSURVEYED_VALUES entries. A derivation bounds a value;
# it does not measure it. The registry stays the record of what is still unmeasured, and this is
# the record of how far the unmeasured values have been pinned down from a desk.
DERIVED_VALUES: dict[str, str] = {
    "pop_served_upper_bound": (
        "Shelter capacity cannot exceed floor_area_m2 (1450, surveyed) / 3.5 m2 per person "
        "(Kerala State Minimum Standards of Relief, KSDMA Ed. 1, 9 Jul 2020) = 414 people. The "
        "college-reported 400 sits within this ceiling, so the report is consistent with the "
        "surveyed floor area — the bound now corroborates the figure instead of contradicting it."
    ),
    "critical_load_range_kw": (
        "The two disagreeing survey records (18.0 reported, 20.0 itemised) bound the true load "
        "rather than being averaged. Backup duration is reported across the full range so the "
        "dashboard shows the pessimistic end instead of only the flattering one."
    ),
}

# Derived, never hand-set. True while any value above remains unmeasured.
#
# Note this reads UNSURVEYED_VALUES only. DERIVED_VALUES deliberately does not clear the flag:
# bounding a number from a desk is real progress, but it is not a measurement, and the notice
# must not soften just because the remaining gaps are now better characterised.
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
# model plus local Karuvannur/drainage behaviour (site survey record §3.3), which is the drone
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
# SOURCED — measured on site at the Decennial Block (see the site survey record). These are actuals, not
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
    # Zeroing the runtime and rating as well as the flag is load-bearing now that the generator
    # carries energy: clearing has_generator alone would leave a drowned set still contributing
    # 14 h of fuel to any caller that reads the runtime directly.
    "generator": {"has_generator": False, "generator_runtime_h": 0.0, "generator_rated_kw": 0.0},
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
        # REPORTED: 400, stated by college staff. Supersedes the invented 500, which exceeded
        # what the floor area allows under the KSDMA standard (see shelter_capacity_upper_bound
        # = 414). That 400 lands inside that independently derived ceiling is a real cross-check:
        # two unrelated routes — a verbal report and surveyed floor area ÷ a published standard —
        # agree to within 3.5%. Note this is corroboration, NOT verification; both could still be
        # describing normal occupancy rather than flood-shelter capacity.
        #
        # TODO(user): get it in writing. One email to the Estate Officer promotes this from
        # REPORTED to SOURCED. Until then it stays in REPORTED_VALUES.
        "pop_served": 400,
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
            # DERIVED from the surveyed nameplate: 62.5 kVA x 0.8 power factor = 50 kW. 0.8 pf is
            # the standard assumption for a diesel set and is stated rather than measured. Well
            # above the 18 kW critical load, so the set carries it comfortably while fuel lasts —
            # the binding constraint is endurance, not capacity.
            "generator_rated_kw": 50.0,
            # SOURCED, used as a deliberate FLOOR rather than an estimate.
            #
            # The survey gives one point on the fuel curve: 220 L lasting ~14 h at 70% load
            # (~35 kW), i.e. ~15.7 L/h. The actual critical load is 18 kW — roughly half that —
            # so the set would in reality run considerably LONGER than 14 h.
            #
            # How much longer cannot be computed from one point. Diesel consumption is load
            # dependent with a substantial no-load component, so scaling 15.7 L/h linearly by
            # 18/35 would assume the no-load draw away and overstate endurance. Fitting the curve
            # needs a second fuel measurement nobody took.
            #
            # So 14 h is used unscaled. It is the conservative end of a range whose upper bound is
            # unknown, which is the safe direction to be wrong in for a shelter.
            # TODO(user): one more fuel-burn figure at a second load closes this.
            "generator_runtime_h": 14.0,
            # REPORTED: college confirms 18.0 kW is the correct total, settling WHICH of the two
            # survey records to use. That is a real answer to a real question.
            #
            # It does NOT reconcile them. The circuit itemisation still sums to 20.0 kW, so a
            # 2.0 kW error sits somewhere in that breakdown and nobody has found it. Deleting the
            # itemisation to make the numbers agree would destroy the only evidence that the error
            # exists — see critical_load_discrepancy_kw(), which stays non-zero on purpose.
            "critical_load_kw": 18.0,
        },
    },
]

POP_SERVED = {s["id"]: s["pop_served"] for s in SHELTERS}

# --- Shelter capacity, bounded from the surveyed floor area -----------------------------------
# pop_served cannot be measured from a desk. It CAN be bounded from one, and the bound turns out
# to be informative.
#
# DERIVED: Kerala State Minimum Standards of Relief (KSDMA, Edition 1, 9 July 2020) — 3.5 m2 of
# covered area per person in a relief centre. This is the GOVERNING standard for a shelter in
# Kodakara, which is why it is cited ahead of the Sphere Handbook (2018, Shelter and Settlement
# Standard 3); Sphere independently specifies the same 3.5 m2, so the two agree.
#
# KSDMA relaxes the figure to 2.5 m2 in mountainous areas. That relaxation does NOT apply here —
# using it would raise the ceiling to 580 and manufacture agreement with the standing 500.
#
# Dividing the SURVEYED gross floor area by that minimum gives the largest population the
# building could possibly shelter to standard.
#
# This is deliberately an UPPER BOUND and nothing more. Gross floor area includes corridors,
# stairwells, toilets, walls and plant rooms, none of which are sleepable, so true capacity is
# strictly lower — by how much cannot be known without a floor plan. Quoting the bound as an
# estimate would be the same error as quoting the guess, in the opposite direction. Refusing to
# invent a usable-area fraction is what keeps this a bound rather than a fabricated measurement.
#
# The bound is worth computing because 1450 / 3.5 = 414 < 500. The standing pop_served is not
# merely unmeasured; it is INCONSISTENT with the surveyed floor area under the cited standard,
# and it errs toward overstating how many people each repair restores.
SHELTER_AREA_PER_PERSON_M2 = 3.5


def shelter_capacity_upper_bound(site_id: str) -> int | None:
    """
    Largest population this shelter could hold at the Sphere minimum area per person.

    Upper bound, not an estimate: computed from GROSS floor area, so unusable circulation and
    service space is still counted as sleepable. Floored to a whole person.

    Returns None for a site with no surveyed floor area — including the synthetic sites the
    recovery tests build. No area, no bound: returning a number anyway would be inventing the
    very thing this function exists to avoid, and callers must handle the gap explicitly rather
    than inherit a fabricated ceiling.
    """
    try:
        site = get_shelter(site_id)
    except KeyError:
        return None
    area = site["building"].get("floor_area_m2")
    if not area:
        return None
    return int(area // SHELTER_AREA_PER_PERSON_M2)


def pop_served_exceeds_area_bound(site_id: str, pop: int | None = None) -> bool:
    """
    True when the claimed population exceeds what the floor area can hold.

    `pop` defaults to the standing POP_SERVED but can be overridden, so callers ranking against
    a caller-supplied population check THAT figure rather than a global one it does not use.
    False when no bound exists — an unknown ceiling is not a violated one.

    Asserted in the test suite, so the day pop_served is replaced with a surveyed figure this
    either goes quiet or fails loudly — it cannot rot into a stale claim the way a comment can.
    """
    bound = shelter_capacity_upper_bound(site_id)
    if bound is None:
        return False
    return (POP_SERVED.get(site_id, 0) if pop is None else pop) > bound


def pop_served_overstatement(site_id: str, pop: int | None = None) -> int:
    """How many people the claimed population exceeds the area bound by (0 if within, or if
    no bound can be computed)."""
    bound = shelter_capacity_upper_bound(site_id)
    if bound is None:
        return 0
    return max(0, (POP_SERVED.get(site_id, 0) if pop is None else pop) - bound)

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


# DERIVED: while the records disagree, the honest reading of the critical load is the interval
# they bracket — not either endpoint on its own. Callers report backup duration across the whole
# range so the dashboard shows the pessimistic end alongside the flattering one, rather than
# inheriting whichever figure happened to be assigned to critical_load_kw.
#
# Averaging the two would manufacture a number neither survey record supports, and would hide
# the disagreement behind false precision. The interval keeps it visible.
def critical_load_range_kw() -> tuple[float, float]:
    """(low, high) kW across both survey records. Equal values mean the records agree."""
    a, b = CRITICAL_LOAD_REPORTED_KW, critical_load_itemised_total_kw()
    return (min(a, b), max(a, b))


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
