"""
Vertical-datum regression tests.

Every elevation in presets.py is metres above FINISHED FLOOR LEVEL. Most flood figures in the
wild are not: street depths are above external ground, satellite/terrain figures are above MSL.
Mixing them offsets every margin in the model by the height of the floor slab, and the outputs
stay entirely plausible while being wrong — which is precisely why it needs a test rather than a
comment.

These pin the CONTRACT (conversion is mandatory, missing survey constants raise), not the
placeholder numbers.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from resilienceos import presets
from resilienceos.api import app


client = TestClient(app)


# --- depth_above_floor -----------------------------------------------------------------------

def test_already_in_model_datum_passes_through():
    assert presets.depth_above_floor(1.2, presets.ELEVATION_DATUM) == 1.2


def test_msl_reading_converts_now_that_the_floor_level_is_surveyed():
    """
    The finished floor level is now tied to MSL (11.84 m), so above-MSL figures convert.

    This test previously asserted the refusal. That flip is the intended lifecycle: the refusal
    held only while the measurement was missing, and rewriting it forces the change to be
    conscious rather than incidental.
    """
    ffl = presets.FINISHED_FLOOR_LEVEL_MSL_M
    assert ffl is not None
    assert presets.depth_above_floor(12.66, "above_msl_m") == pytest.approx(12.66 - ffl)


def test_regional_marker_converts_to_the_observed_wall_mark():
    """
    Pins the identity the survey rests on: the nearest regional reference (ILDM/SoI marker CKD05,
    2018 flood at 12.66 m MSL) converts to 0.82 m above this building's floor — the same figure
    as the wall mark in OBSERVED_EVENTS.

    Asserted so the coincidence is VISIBLE rather than buried. Exact agreement between a mark here
    and a riverbank 8 km away is either a strong cross-check or a sign the floor level was derived
    from the marker; see the note on FINISHED_FLOOR_LEVEL_MSL_M. Either way the arithmetic should
    not silently drift.
    """
    converted = presets.depth_above_floor(12.66, "above_msl_m")
    assert converted == pytest.approx(presets.OBSERVED_EVENTS["kerala_2018"]["depth_m"], abs=1e-9)
    assert converted == pytest.approx(presets.FLOOD_LINE_M, abs=1e-9)


def test_above_ground_reading_converts_now_that_the_step_height_is_surveyed():
    """
    The step from external ground to finished floor IS surveyed (0.18 m), so eyewitness-style
    "water was this deep outside" readings are now convertible.

    This test previously asserted the opposite — that the conversion was refused. That flip is
    the intended lifecycle: the refusal held only while the measurement was missing.
    """
    step = presets.GROUND_TO_FLOOR_STEP_M
    assert step is not None
    # water 1.2 m deep outside stands 1.2 - 0.18 above the floor inside
    assert presets.depth_above_floor(1.2, "above_external_ground_m") == pytest.approx(1.2 - step)


def test_shallow_outside_water_converts_to_a_negative_depth_above_floor():
    """Below the step, there is water outside and none inside. The sign carries that meaning."""
    assert presets.depth_above_floor(0.10, "above_external_ground_m") < 0


def test_unknown_datum_is_refused_rather_than_assumed():
    with pytest.raises(presets.DatumError, match="unknown datum"):
        presets.depth_above_floor(1.0, "metres_of_water_probably")


def test_conversion_never_silently_returns_the_input():
    """
    The failure mode being guarded: returning the raw number when conversion is impossible.

    Both survey constants now exist, so both real datums convert. What must still never happen is
    an UNKNOWN datum quietly passing its input through — that is the silent-corruption case.
    """
    with pytest.raises(presets.DatumError):
        presets.depth_above_floor(9.99, "nonsense")


# --- sanity ceiling on authored constants ----------------------------------------------------

# A depth above a building's own floor is metres. A figure above MSL for inland Thrissur is tens
# of metres. This ceiling is deliberately loose: it is not a claim about how deep floods get, it
# only catches a wrong-datum paste, which is off by an order of magnitude rather than a little.
_PLAUSIBLE_ABOVE_FLOOR_CEILING_M = 5.0


def test_authored_flood_constants_are_plausible_as_above_floor_depths():
    suspects = {
        name: v for name, v in
        [("FLOOD_LINE_M", presets.FLOOD_LINE_M), *presets.FLOOD_SCENARIOS_M.items()]
        if not 0.0 <= v <= _PLAUSIBLE_ABOVE_FLOOR_CEILING_M
    }
    assert not suspects, (
        f"{suspects} are implausible as metres above finished floor — this is what an MSL or "
        f"terrain figure pasted into the wrong datum looks like. Convert via depth_above_floor()."
    )


# Assets can legitimately sit BELOW finished floor level — the access road does, at -0.08 m,
# because the road surface is lower than the building slab. So the floor of this range is not
# zero; it is "not absurdly far below", which still catches a wrong-datum paste.
_PLAUSIBLE_ABOVE_FLOOR_MIN_M = -2.0


def test_equipment_elevations_are_plausible_as_above_floor_heights():
    suspects = {
        a: e for a, e in presets.EQUIPMENT_ELEVATION_M.items()
        # solar panels are roof-mounted, so they legitimately clear the ceiling
        if a != "solar_panels"
        and not _PLAUSIBLE_ABOVE_FLOOR_MIN_M <= e <= _PLAUSIBLE_ABOVE_FLOOR_CEILING_M
    }
    assert not suspects, f"{suspects} implausible as metres above finished floor"


def test_road_access_sits_below_the_finished_floor():
    """
    Surveyed 0.10 m above surrounding grade, converted through the 0.18 m step — so it is below
    the floor. This is the operationally important case: the access road floods before anything
    inside the building, cutting generator fuel resupply first.
    """
    assert presets.EQUIPMENT_ELEVATION_M["road_access"] == pytest.approx(0.10 - 0.18)


# --- API boundary ----------------------------------------------------------------------------

def test_observation_in_model_datum_is_accepted_and_stored_converted():
    r = client.post("/api/observations", json={
        "site_id": "decennial_block",
        "flood_depth_m": 0.8,
        "datum": presets.ELEVATION_DATUM,
        "source": "test",
    })
    assert r.status_code == 200
    stored = r.json()["stored"]
    assert stored["flood_depth_m"] == 0.8
    assert stored["datum"] == presets.ELEVATION_DATUM
    # provenance is kept so a conversion can be audited after the fact
    assert stored["raw_reading_m"] == 0.8
    assert stored["raw_datum"] == presets.ELEVATION_DATUM


def test_msl_observation_is_accepted_and_stored_converted():
    """
    An above-MSL reading now converts at the API boundary and is stored in the model's datum,
    with the raw reading kept alongside so the conversion stays auditable.
    """
    r = client.post("/api/observations", json={
        "site_id": "decennial_block",
        "flood_depth_m": 12.66,
        "datum": "above_msl_m",
        "source": "test",
    })
    assert r.status_code == 200
    stored = r.json()["stored"]
    assert stored["flood_depth_m"] == pytest.approx(12.66 - presets.FINISHED_FLOOR_LEVEL_MSL_M)
    assert stored["datum"] == presets.ELEVATION_DATUM
    # provenance: the untouched input survives the conversion
    assert stored["raw_reading_m"] == 12.66
    assert stored["raw_datum"] == "above_msl_m"


def test_observation_without_a_datum_is_rejected():
    """No default datum: omitting it must fail validation, not be assumed."""
    r = client.post("/api/observations", json={
        "site_id": "decennial_block",
        "flood_depth_m": 0.8,
        "source": "test",
    })
    assert r.status_code == 422


def test_at_risk_margin_is_now_derived_from_survey_uncertainty():
    """
    The margin is no longer the arbitrary 0.3 fallback — it is 2 sigma on the surveyed vertical
    uncertainty, so the amber "water is close" band is now tied to what the survey can actually
    resolve rather than to a chosen round number.
    """
    assert presets.SURVEY_UNCERTAINTY_M is not None
    assert presets.AT_RISK_MARGIN_M == pytest.approx(2 * presets.SURVEY_UNCERTAINTY_M)
    assert presets.AT_RISK_MARGIN_M < presets._FALLBACK_AT_RISK_MARGIN_M


def test_placeholder_flag_is_derived_from_the_registry_not_hand_set():
    """
    The flag must not be settable independently of the data. It is `bool(UNSURVEYED_VALUES)`, so
    the only way to clear the dashboard notice is to actually empty the registry — which means
    replacing each named value with a measurement.
    """
    assert presets.DATA_IS_PLACEHOLDER == bool(presets.UNSURVEYED_VALUES)
    assert presets.DATA_IS_PLACEHOLDER is True, "registry empty; every value is now surveyed?"


def test_registry_entries_match_the_values_that_are_actually_unsurveyed():
    """
    Anchors each registry key to the condition that put it there, so an entry cannot be quietly
    deleted while the underlying value is still invented. Each assertion below fails the day that
    value is genuinely surveyed — at which point the entry should be removed in the same edit.
    """
    unsurveyed = presets.UNSURVEYED_VALUES
    reported = presets.REPORTED_VALUES

    # --- Reported by the college, not verified. These moved OUT of `unsurveyed` when the college
    # supplied a figure, and must be in `reported` instead — never silently dropped from both,
    # which is how a verbal assurance turns into an apparent measurement.
    assert "pop_served" in reported
    assert "pop_served" not in unsurveyed
    assert presets.POP_SERVED["decennial_block"] == 400

    # The college settled WHICH critical-load record to use, but the records still disagree: the
    # itemisation sums to 20.0 against the confirmed 18.0. Resolving the choice is not the same as
    # reconciling the arithmetic, and conflating them would bury a 2.0 kW error nobody has found.
    assert "critical_load_kw" in reported
    assert not presets.critical_load_is_reconciled()

    # The substation's flood exposure is a REPORTED claim, not a height. It must still have no
    # entry in EQUIPMENT_ELEVATION_M — writing a number there to represent "high ground" would
    # fabricate the measurement this whole registry exists to protect.
    assert "substation_flood_exposure" in reported
    assert "substation" in presets.REPORTED_ABOVE_FLOOD
    assert "substation" not in presets.EQUIPMENT_ELEVATION_M

    # the substation repair estimate is still absent from recovery.py
    from resilienceos import recovery
    assert "REPAIR_EFFORT_H" in unsurveyed
    assert "substation" not in recovery.REPAIR_EFFORT_H

    # No value may sit in two tiers at once — that is how a reader ends up seeing the same figure
    # described as both measured and unverified.
    for a, b in ((unsurveyed, reported), (reported, presets.SURVEYED_VALUES),
                 (unsurveyed, presets.SURVEYED_VALUES)):
        assert not set(a) & set(b)
    assert "substation" not in recovery.REPAIR_EFFORT_H


def test_surveyed_and_unsurveyed_registries_do_not_overlap():
    """A value cannot be both measured and provisional; the banner would contradict itself."""
    assert not (set(presets.SURVEYED_VALUES) & set(presets.UNSURVEYED_VALUES))
    assert presets.SURVEYED_VALUES, "nothing recorded as surveyed — the banner would read wrong"


# --- The depth control's reference marks -----------------------------------------------------
# The dashboard's flood-depth slider renders the observed flood line, the uncertainty band and
# every asset elevation. Those are SURVEYED values, so they are served rather than written into
# the frontend: a measurement copied into a React component is a measurement that can drift from
# presets.py with nothing failing. These tests pin the serving contract, not the numbers.

def test_sites_serves_the_surveyed_hazard_reference():
    """The slider's marks must come from presets, so there is one place each height is written."""
    ref = client.get("/api/sites").json()["hazard_reference"]

    assert ref["flood_line_m"] == presets.FLOOD_LINE_M
    assert ref["survey_uncertainty_m"] == presets.SURVEY_UNCERTAINTY_M
    assert ref["at_risk_margin_m"] == presets.AT_RISK_MARGIN_M
    assert ref["equipment_elevation_m"] == presets.EQUIPMENT_ELEVATION_M


def test_hazard_reference_carries_no_elevation_for_the_unmeasured_substation():
    """
    The served payload must not acquire a height the registry refuses to state.

    Serving elevations to the frontend is a new way for an invented number to reach a reader, so
    the substation's absence is asserted on the wire as well as in presets.
    """
    ref = client.get("/api/sites").json()["hazard_reference"]
    assert "substation" not in ref["equipment_elevation_m"]


def test_at_risk_margin_stays_wider_than_the_generator_cliff():
    """
    The generator sits 0.03 m above the observed 2018 flood mark, and the survey's 2-sigma band
    is 0.06 m. So the model CANNOT honestly say whether the generator flooded in 2018 — the
    margin is inside the error bars, which is why node_health reports `at_risk` there.

    This pins that relationship. If a future survey tightens the uncertainty below the margin,
    this test fails and the dashboard's "inside the survey's own uncertainty" wording must be
    re-earned rather than left standing as a claim the data no longer supports.
    """
    cliff = presets.EQUIPMENT_ELEVATION_M["generator"] - presets.FLOOD_LINE_M
    assert 0 < cliff <= presets.AT_RISK_MARGIN_M
