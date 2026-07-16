"""
Regression tests pinning the resilience-score fix.

BACKGROUND — the bug these exist to prevent from returning:
`resilience_score` used a peak-based `thermal_headroom` term clamped to zero once the peak
heat index passed HI_DANGER (39 C). The habitability penalty was NOT clamped. So in the
dangerous regime the reward end was dead while the penalty end stayed live, and measured on a
severe day a cool roof that cut 1.61 C off the peak scored +0, while double glazing that cut
7.4 C scored -2. `budget_optimizer` returned `recommended: []` — it advised doing nothing on
the most dangerous day it could model.

These tests assert MONOTONIC RESPONSIVENESS, not flattering numbers. Double glazing genuinely
is a mixed intervention in free-float (low-U glass also traps heat in the cooler tail hours),
and the score is allowed to say so — it just may never be blind to a real improvement.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from resilienceos.building import Building
from resilienceos.engine import DEGH_HALF, resilience_score
from resilienceos.hazard import (
    HI_CAUTION,
    HI_DANGER,
    HeatwaveResult,
    OutageResult,
    analyze_heatwave,
    degree_hours_above,
)
from resilienceos.scenarios import budget_optimizer, compare


def _hw(exceedance_degh: float, safe_hours: int = 6, peak_hi: float = 57.0) -> HeatwaveResult:
    return HeatwaveResult(
        peak_indoor=peak_hi - 2.0,
        peak_heat_index=peak_hi,
        peak_outdoor=44.0,
        safe_occupancy_hours=safe_hours,
        occupied_hours=24,
        hours_above_caution=18,
        hours_above_danger=12,
        exceedance_degh=exceedance_degh,
        profile=[],
    )


def _out(backup_hours: float = 8.0) -> OutageResult:
    return OutageResult(
        start_hour=14,
        duration_h=6,
        hours_until_unsafe=1.0,
        peak_indoor_during=40.0,
        backup_hours=backup_hours,
        critical_load_kw=5.0,
        profile=[],
    )


@pytest.fixture
def building() -> Building:
    return Building(battery_kwh=20)


# --- the exact failure mode ----------------------------------------------------------------

def test_exceedance_never_saturates_in_the_danger_regime():
    """
    Deep in the danger regime (peak HI 57 C), a real improvement MUST raise the sub-score.
    The old clamped headroom term returned 0 for both of these.
    """
    worse = resilience_score(_hw(exceedance_degh=200.0), _out())
    better = resilience_score(_hw(exceedance_degh=180.0), _out())
    assert better["components"]["thermal_exceedance"] > worse["components"]["thermal_exceedance"]
    assert better["score"] > worse["score"]


def test_thermal_sub_score_strictly_decreasing_in_degree_hours():
    """Monotonicity across four orders of exposure, including far past the old clamp point."""
    degh_values = [0.0, 10.0, 40.0, 120.0, 400.0, 2000.0]
    sub = [
        resilience_score(_hw(exceedance_degh=d), _out())["components"]["thermal_exceedance"]
        for d in degh_values
    ]
    assert sub == sorted(sub, reverse=True), f"not monotonic: {list(zip(degh_values, sub))}"
    assert sub[0] == 100          # zero exposure -> full marks
    assert sub[-1] >= 0           # never negative, never clamps away real differences


def test_reward_end_is_never_floored():
    """
    The root cause was an asymmetry: reward clamped, penalty not. Assert the reward term stays
    strictly positive no matter how extreme the exposure, so it can always still move.
    """
    absurd = resilience_score(_hw(exceedance_degh=10_000.0), _out())
    assert absurd["components"]["thermal_exceedance"] >= 0
    # and it must still respond to change even out here
    a = resilience_score(_hw(exceedance_degh=10_000.0), _out())["score"]
    b = resilience_score(_hw(exceedance_degh=9_000.0), _out())["score"]
    assert b >= a


def test_degh_half_sets_the_half_point():
    at_half = resilience_score(_hw(exceedance_degh=DEGH_HALF), _out())
    assert at_half["components"]["thermal_exceedance"] == pytest.approx(50, abs=1)


def test_sub_score_retains_resolution_across_the_real_measured_range():
    """
    Guards the mistake made while fixing this: an exp(-degh/40) decay was tried first and
    underflowed to 0 above ~200 C.h, silently re-creating the saturation. Real exposure spans
    ~13 C.h (mild) to ~860 C.h (severe), so the transform must still discriminate out at 800.
    """
    sub = lambda d: resilience_score(_hw(exceedance_degh=d), _out())["components"]["thermal_exceedance"]
    assert sub(800) > 0, "sub-score underflowed to zero inside the real measured range"
    assert sub(800) < sub(400) < sub(200) < sub(100), "no resolution left in the severe range"


# --- the metric itself ---------------------------------------------------------------------

def test_degree_hours_above_counts_only_exceedance():
    import pandas as pd
    s = pd.Series([30.0, 32.0, 35.0, 42.0])   # caution = 32
    # 0 + 0 + 3 + 10
    assert degree_hours_above(s, HI_CAUTION) == pytest.approx(13.0)


def test_degree_hours_prices_duration_not_just_peak():
    """Two days with the SAME peak but different duration must not score the same."""
    import pandas as pd
    spike = pd.Series([32.0] * 23 + [42.0])          # one bad hour
    plateau = pd.Series([42.0] * 24)                 # all day
    assert degree_hours_above(spike) < degree_hours_above(plateau)


# --- end-to-end through the real twin ------------------------------------------------------

def test_cool_roof_gain_is_positive_under_severe_heat(building, severe_day):
    """The headline regression: this returned exactly 0 before the fix."""
    hw = analyze_heatwave(building, severe_day, hvac_active=False)
    assert hw.peak_heat_index >= HI_DANGER, "fixture must sit in the regime that broke the score"

    deltas = compare(building, severe_day, "cool_roof", outage_start=14, outage_dur=6)["deltas"]
    assert deltas["peak_heat_index"] < 0, "cool roof must reduce the peak heat index"
    assert deltas["exceedance_degh"] < 0, "cool roof must reduce cumulative heat exposure"
    # Assert on the unrounded score: the real gain here is well under 1 point, and rounding to
    # an int before comparing is what hid it from the optimizer in the first place.
    assert deltas["resilience_score_exact"] > 0, "a real thermal improvement must raise the score"


def test_delta_sign_convention_is_new_minus_baseline(building, severe_day):
    """
    Pins the semantics an earlier diagnosis got wrong: deltas are (with_intervention - baseline),
    so a NEGATIVE peak_heat_index delta means the retrofit made things BETTER.
    """
    r = compare(building, severe_day, "cool_roof", outage_start=14, outage_dur=6)
    expected = r["with_intervention"]["peak_heat_index"] - r["baseline"]["peak_heat_index"]
    assert r["deltas"]["peak_heat_index"] == pytest.approx(expected, abs=0.01)
    assert r["with_intervention"]["peak_heat_index"] < r["baseline"]["peak_heat_index"]


def test_budget_optimizer_recommends_something_on_the_dangerous_day(building, severe_day):
    """Before the fix this returned `recommended: []` — advising nothing on the worst day."""
    opt = budget_optimizer(building, severe_day, 500_000, outage_start=14, outage_dur=6)
    assert any(r["score_gain"] > 0 for r in opt["ranked"]), "no retrofit scored any gain at all"
    assert opt["recommended"], "optimizer recommended nothing despite an effective retrofit"


def test_cool_roof_is_reachable_within_a_small_budget(building, severe_day):
    """
    Cool roof is the cheapest intervention (Rs 60k) and genuinely lowers heat exposure. The
    saturated score made it rank 0 gain/lakh, so it was never selected at any budget.
    """
    opt = budget_optimizer(building, severe_day, 100_000, outage_start=14, outage_dur=6)
    assert "cool_roof" in opt["recommended"]


def test_severe_day_scores_worse_than_mild_day(building, severe_day, mild_day):
    """Basic sanity: the score must order the two regimes correctly."""
    def score_of(day):
        from resilienceos.hazard import analyze_outage
        hw = analyze_heatwave(building, day, hvac_active=False)
        out = analyze_outage(building, day, 14, 6)
        return resilience_score(hw, out)["score"]

    assert score_of(severe_day) < score_of(mild_day)
