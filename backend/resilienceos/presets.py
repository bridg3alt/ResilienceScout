"""
ResilienceScout — the data-provenance chokepoint.

Every facility-specific number the model depends on now lives in a site file under `sites/`,
loaded here at import. This module is the boundary between two kinds of thing:

  * FACILITY DATA — what you measure and enter for a building: nameplate, equipment elevations,
    the vertical datum, observed flood marks, critical load. It lives in `sites/<id>.json`.
    Deploying to a new building is copying that file and editing its numbers — not touching code.
    The active site defaults to `decennial_block`; set the RESILIENCE_SITE environment variable
    to load a different one.

  * MODEL CONSTANTS and PROVENANCE NARRATIVE — the datum machinery, the score thresholds, and the
    epistemic tiering below. These stay in code because they describe the method, not the site.

Four epistemic tiers, and the registries below say which value sits in which:
  * SOURCED  — a real, measured or cited value. Carries its provenance, and no TODO.
  * DERIVED  — not measured here, but COMPUTED from a surveyed input plus a published standard,
               with both named. Weaker than SOURCED, categorically stronger than a guess,
               because a reader can recheck the arithmetic and challenge the citation.
  * REPORTED — stated by the site owner (college facilities staff, institutional records) but not
               independently verified. Weaker than SOURCED because nobody checked it; far stronger
               than INVENTED because it has a named human source who can be asked again.
  * INVENTED — a guess. Carries a TODO(user) and stays in UNSURVEYED_VALUES until measured.

The DERIVED tier exists because some gaps can be closed from a desk and some cannot, and
collapsing that distinction wastes the ones that can. It is NOT a way to retire a TODO quietly:
a derived value stays in UNSURVEYED_VALUES until it is actually measured. What it buys is a
defensible number to reason with, and — as with shelter capacity below — sometimes a derivation
CONTRADICTS the standing guess, which is a finding in itself.

The registries below describe the active site's survey campaign (currently the Decennial Block,
latest survey 2026-07-18). One invented value lives outside this file: REPAIR_EFFORT_H in
recovery.py.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SITES_DIR = Path(__file__).parent / "sites"

DEFAULT_SITE_ID = "decennial_block"

ACTIVE_SITE_ID = os.environ.get("RESILIENCE_SITE", DEFAULT_SITE_ID)


def available_sites() -> list[str]:
    """Site ids with a config file under sites/ — the facilities this deployment can load."""
    return sorted(p.stem for p in SITES_DIR.glob("*.json"))


def _load_site(site_id: str) -> dict:
    path = SITES_DIR / f"{site_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"no site config {path.name!r} in {SITES_DIR} (available: {available_sites()}). "
            f"Set RESILIENCE_SITE to a known site, or add the JSON file."
        )
    return json.loads(path.read_text(encoding="utf-8"))


_SITE = _load_site(ACTIVE_SITE_ID)


# --------------------------------------------------------------------------------------------
# Provenance narrative — describes the active site's survey campaign.
# --------------------------------------------------------------------------------------------

UNSURVEYED_VALUES: dict[str, str] = {
    "REPAIR_EFFORT_H": (
        "The substation has no surveyed repair estimate, so recovery.py falls through to a "
        "generic 8 h default — unlikely to be right for an 11 kV asset. Now only load-bearing if "
        "the college's report that the substation sits above flood level turns out to be wrong: "
        "while that holds, the substation never fails and never enters a repair plan."
    ),
}

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

SURVEYED_VALUES: dict[str, str] = {
    "vertical_datum": "Finished floor level tied to MSL (11.84 m) and to external grade (0.18 m step)",
    "flood_line": "August 2018 high-water mark, 0.82 m above finished floor, evidenced by wall staining",
    "equipment_elevations": "Six of eight measured on site; road_access and solar_panels still estimated",
    "der_nameplate": "Solar kWp, battery kWh + chemistry, generator rating/fuel/runtime, critical load",
    "survey_uncertainty": "Combined vertical uncertainty 0.03 m, driving the at-risk margin",
    "grid_topology": "Campus 11 kV substation confirmed as the feed, upstream of the 250 kVA transformer",
}

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

DATA_IS_PLACEHOLDER = bool(UNSURVEYED_VALUES)


# --------------------------------------------------------------------------------------------
# Vertical datum — model constants plus the site's surveyed reference heights.
# --------------------------------------------------------------------------------------------

ELEVATION_DATUM = "above_finished_floor_m"

FINISHED_FLOOR_LEVEL_MSL_M: float | None = _SITE["datum"].get("finished_floor_level_msl_m")

GROUND_TO_FLOOR_STEP_M: float | None = _SITE["datum"].get("ground_to_floor_step_m")


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


FLOOD_LINE_M = _SITE["flood"]["observed_line_m"]

OBSERVED_EVENTS: dict[str, dict] = _SITE["flood"]["observed_events"]

FLOOD_SCENARIOS_M = _SITE["flood"]["scenarios"]


def _elevation(entry) -> float:
    """
    An equipment elevation from the site file, in metres above finished floor.

    A bare number is already in the model datum. An object {"value", "datum"} was measured against
    something else (external grade, MSL) and is converted through the datum machinery, so the
    file records what was actually surveyed rather than a silently pre-computed height.
    """
    if isinstance(entry, dict):
        return round(depth_above_floor(entry["value"], entry["datum"]), 3)
    return entry


EQUIPMENT_ELEVATION_M = {
    name: _elevation(entry) for name, entry in _SITE["equipment_elevation_m"].items()
}

SURVEY_UNCERTAINTY_M: float | None = _SITE["datum"].get("survey_uncertainty_m")

_FALLBACK_AT_RISK_MARGIN_M = 0.3

AT_RISK_MARGIN_M = (
    2 * SURVEY_UNCERTAINTY_M if SURVEY_UNCERTAINTY_M is not None
    else _FALLBACK_AT_RISK_MARGIN_M
)

EQUIPMENT_EFFECT = {
    "battery": {"battery_kwh": 0.0},
    "solar_inverter": {"solar_kwp": 0.0},
    "generator": {"has_generator": False, "generator_runtime_h": 0.0, "generator_rated_kw": 0.0},
}

REQUIRED_BACKUP_H = 12.0
CRITICAL_SPOF_LIMIT = 2

REPORTED_ABOVE_FLOOD: frozenset[str] = frozenset(_SITE.get("reported_above_flood", ()))


# --------------------------------------------------------------------------------------------
# Facility roster — built from the active site file.
# --------------------------------------------------------------------------------------------

SHELTERS = [
    {
        "id": _SITE["id"],
        "name": _SITE["name"],
        "pop_served": _SITE["pop_served"],
        "building": dict(_SITE["building"]),
    }
]

POP_SERVED = {s["id"]: s["pop_served"] for s in SHELTERS}

SHELTER_AREA_PER_PERSON_M2 = 3.5


def get_shelter(site_id: str) -> dict:
    for s in SHELTERS:
        if s["id"] == site_id:
            return s
    raise KeyError(f"unknown shelter id: {site_id!r} (known: {[s['id'] for s in SHELTERS]})")


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


# --------------------------------------------------------------------------------------------
# Critical load — two disagreeing survey records, kept as a range rather than averaged.
# --------------------------------------------------------------------------------------------

CRITICAL_LOAD_ITEMISATION_KW = dict(_SITE["critical_load"]["itemisation_kw"])

CRITICAL_LOAD_REPORTED_KW = _SITE["critical_load"]["reported_kw"]


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


def critical_load_range_kw() -> tuple[float, float]:
    """(low, high) kW across both survey records. Equal values mean the records agree."""
    a, b = CRITICAL_LOAD_REPORTED_KW, critical_load_itemised_total_kw()
    return (min(a, b), max(a, b))


def flooded_equipment(flood_depth_m: float) -> list[str]:
    """Assets at or below the flood depth. Sorted for deterministic output."""
    return sorted(
        name for name, elev in EQUIPMENT_ELEVATION_M.items() if elev <= flood_depth_m
    )
