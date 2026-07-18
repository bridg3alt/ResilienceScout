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


def test_msl_reading_is_refused_while_floor_level_is_unsurveyed():
    """
    Documents the CURRENT unsurveyed state: an above-MSL figure cannot be converted because the
    finished floor level has never been levelled against a benchmark.

    When that survey lands, this test SHOULD fail and be rewritten to assert the conversion —
    that is intentional. It forces the change to be conscious rather than incidental.
    """
    assert presets.FINISHED_FLOOR_LEVEL_MSL_M is None, "survey landed; update this test"
    with pytest.raises(presets.DatumError, match="FINISHED_FLOOR_LEVEL_MSL_M"):
        presets.depth_above_floor(3.84, "above_msl_m")


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

    `above_external_ground_m` is no longer in this list because its survey constant now exists —
    it converts rather than raising. `above_msl_m` still has no finished-floor-to-MSL tie.
    """
    for datum in ("above_msl_m", "nonsense"):
        with pytest.raises(presets.DatumError):
            presets.depth_above_floor(9.99, datum)


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


def test_observation_in_unconvertible_datum_is_rejected_not_stored():
    """The deliverable: the bug becomes visible instead of silently entering the model."""
    r = client.post("/api/observations", json={
        "site_id": "decennial_block",
        "flood_depth_m": 3.84,
        "datum": "above_msl_m",
        "source": "test",
    })
    assert r.status_code == 400
    assert "FINISHED_FLOOR_LEVEL_MSL_M" in r.json()["detail"]


def test_observation_without_a_datum_is_rejected():
    """No default datum: omitting it must fail validation, not be assumed."""
    r = client.post("/api/observations", json={
        "site_id": "decennial_block",
        "flood_depth_m": 0.8,
        "source": "test",
    })
    assert r.status_code == 422


def test_at_risk_margin_falls_back_until_uncertainty_is_surveyed():
    assert presets.SURVEY_UNCERTAINTY_M is None, "survey landed; margin should now be derived"
    assert presets.AT_RISK_MARGIN_M == presets._FALLBACK_AT_RISK_MARGIN_M


def test_data_is_still_flagged_placeholder():
    """The hazard side is unsurveyed, so this must not have been flipped."""
    assert presets.DATA_IS_PLACEHOLDER is True
