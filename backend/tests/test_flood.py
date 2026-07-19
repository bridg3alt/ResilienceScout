"""
Tests for the flood domain: hazard -> dependency graph -> CERI -> recovery.

These pin BEHAVIOUR, not the placeholder numbers in presets.py. Where a test depends on an
invented value it overrides it explicitly, so replacing presets with surveyed data changes the
recommendations without turning this suite red.
"""
from __future__ import annotations

import pytest

from resilienceos import presets
from resilienceos.building import Building
from resilienceos.dependency_graph import (
    build_graph,
    downstream,
    shelter_powered,
    single_points_of_failure,
)
from resilienceos.engine import ceri_score
from resilienceos.hazard import analyze_flood
from resilienceos.recovery import restoration_plan, prioritize


@pytest.fixture
def site():
    return presets.get_shelter("decennial_block")


@pytest.fixture
def building(site):
    return Building(**site["building"])


@pytest.fixture
def graph(site, building):
    return build_graph(site, building)


# --- elevation -> inundation ---------------------------------------------------------------

def test_flooded_equipment_is_elevation_ordered():
    shallow = presets.flooded_equipment(0.2)
    deep = presets.flooded_equipment(1.2)
    assert set(shallow).issubset(set(deep)), "deeper water must inundate a superset"


def test_roof_panels_survive_while_their_ground_inverter_drowns():
    """
    The whole reason elevation is tracked per-asset rather than per-building: at 1.9 m the
    roof-mounted array is untouched but the inverter it feeds is underwater, so the PV
    contributes nothing. A building-level flood flag cannot represent this.

    Depth raised from 1.2 m to 1.9 m when the survey measured the inverter at 1.85 m (it had
    been estimated at 1.2 m). The property under test is unchanged; the real inverter simply
    sits higher than the guess did.
    """
    failed = presets.flooded_equipment(1.9)
    assert "solar_inverter" in failed
    assert "solar_panels" not in failed


def test_flood_zeroes_only_the_der_that_actually_drowned(building, mild_day):
    dry = analyze_flood(building, mild_day, 0.0)
    wet = analyze_flood(building, mild_day, 0.5)   # battery at 0.45 m is under; inverter is not
    assert "battery" in wet.failed_equipment
    assert wet.surviving_der["battery_kwh"] == 0.0
    assert wet.surviving_der["solar_kwp"] == dry.surviving_der["solar_kwp"]


def test_deeper_flood_never_increases_backup(building, mild_day):
    """Monotonicity: more water can only ever remove resources."""
    hours = [analyze_flood(building, mild_day, d).backup_hours for d in (0.0, 0.4, 0.7, 1.3)]
    assert hours == sorted(hours, reverse=True), f"backup not monotonic in depth: {hours}"


def test_analyze_flood_reuses_the_energy_balance(building, mild_day):
    """
    Losing the battery must reduce ride-through via the EXISTING backup model rather than any
    flood-specific reimplementation.
    """
    dry = analyze_flood(building, mild_day, 0.0)
    wet = analyze_flood(building, mild_day, 0.5)   # surveyed battery height is 0.45 m
    assert wet.backup_hours < dry.backup_hours


def test_flood_result_is_flagged_placeholder(building, mild_day):
    assert analyze_flood(building, mild_day, 0.5).placeholder is presets.DATA_IS_PLACEHOLDER


# --- dependency graph ----------------------------------------------------------------------

def test_distribution_panel_is_a_single_point_of_failure(graph):
    """Every source is wired through the panel, so it is fatal even with full DER redundancy."""
    assert "distribution_panel" in single_points_of_failure(graph)


def test_a_redundant_source_is_not_a_single_point_of_failure(graph):
    """Building has battery + solar + generator, so losing the transformer alone is survivable."""
    assert "transformer" not in single_points_of_failure(graph)
    assert shelter_powered(graph, {"transformer"}) is True


def test_power_is_an_or_across_sources_not_a_bfs(graph):
    """Losing three of four sources still leaves the shelter powered by the fourth."""
    assert shelter_powered(graph, {"transformer", "battery", "generator"}) is True
    assert shelter_powered(graph, {"transformer", "battery", "generator", "solar_inverter"}) is False


def test_a_source_needs_its_own_upstream(graph):
    """AND semantics upstream: the inverter is useless without the panels feeding it."""
    assert shelter_powered(graph, {"transformer", "battery", "generator", "solar_panels"}) is False


def test_comms_never_gates_power(graph):
    """Comms matters for coordination but must not be modelled as a power dependency."""
    assert shelter_powered(graph, {"comms"}) is True


def test_graph_only_contains_assets_the_shelter_actually_has():
    """A solar-only building has no battery and no generator — they must not appear as nodes."""
    site = presets.get_shelter("decennial_block")
    solar_only = {**site["building"], "battery_kwh": 0.0, "has_generator": False}
    g = build_graph({**site, "building": solar_only}, Building(**solar_only))
    ids = {n["id"] for n in g["nodes"]}
    assert "battery" not in ids and "generator" not in ids
    assert "solar_inverter" in ids


def test_downstream_reports_the_cascade(graph):
    assert "shelter" in downstream(graph, "distribution_panel")
    assert "solar_inverter" in downstream(graph, "solar_panels")


# --- CERI ----------------------------------------------------------------------------------

def test_ceri_has_the_four_transparent_sub_scores(building, graph, mild_day):
    c = ceri_score(analyze_flood(building, mild_day, 0.5), graph, building)
    assert set(c["components"]) == {
        "energy_readiness", "flood_readiness", "backup_duration", "critical_vulnerabilities",
    }
    assert 0 <= c["score"] <= 100
    assert c["placeholder"] is presets.DATA_IS_PLACEHOLDER


def test_ceri_falls_as_the_water_rises(building, site, mild_day):
    scores = []
    for depth in (0.0, 0.4, 0.7, 1.3):
        fl = analyze_flood(building, mild_day, depth)
        scores.append(ceri_score(fl, build_graph(site, building, fl), building)["score_exact"])
    assert scores == sorted(scores, reverse=True), f"CERI not monotonic in flood depth: {scores}"


def test_ceri_reward_end_is_never_floored(building, graph, mild_day):
    """
    The Phase 0 lesson, enforced on the new index: no sub-score may clamp at the reward end,
    or improvements stop registering exactly where they matter.
    """
    c = ceri_score(analyze_flood(building, mild_day, 5.0), graph, building)   # catastrophic
    assert c["components"]["flood_readiness"] > 0, "flood_readiness floored — improvements would vanish"
    assert c["components"]["critical_vulnerabilities"] > 0


# --- recovery ------------------------------------------------------------------------------

def test_restoration_plan_is_empty_when_still_powered(graph):
    plan = restoration_plan(graph, {"transformer"})   # battery/solar/gen still up
    assert plan["already_powered"] is True
    assert plan["repairs"] == []


def test_restoration_plan_requires_the_panel_plus_a_source(graph):
    """With everything down, no single repair helps — the panel AND one source are needed."""
    failed = {"transformer", "battery", "solar_inverter", "generator", "distribution_panel"}
    plan = restoration_plan(graph, failed)
    assert plan["achievable"] is True
    assert "distribution_panel" in plan["repairs"]
    assert len(plan["repairs"]) >= 2
    assert shelter_powered(graph, failed - set(plan["repairs"]))


def test_restoration_plan_picks_the_cheapest_viable_source(graph):
    """
    Exhaustive search must select the solar inverter (6h) over the transformer (48h). A greedy
    pass that grabbed the highest-capacity asset would pick wrong here.

    Efforts are the surveyed maintenance-team estimates, which widened this gap considerably
    (the transformer went 24h -> 48h, so the cheap-source choice is now even more clearly right).
    """
    failed = {"transformer", "battery", "solar_inverter", "generator", "distribution_panel"}
    plan = restoration_plan(graph, failed)
    assert set(plan["repairs"]) == {"distribution_panel", "solar_inverter"}
    assert plan["effort_h"] == pytest.approx(14.0)   # panel 8.0 + inverter 6.0


def test_recovery_ranks_by_population_per_effort_hour(mild_day):
    """At equal repair effort, the shelter serving more people must rank first.

    Built from two SYNTHETIC copies of the one real building with different populations, so the
    population-per-effort-hour ranking stays covered without a multi-shelter roster.
    """
    site = presets.get_shelter("decennial_block")
    b = Building(**site["building"])
    # 1.7 m, not 1.3 m: with the surveyed elevations the distribution panel sits at 1.60 m, and
    # until IT goes under the shelter is still powered by the (higher) solar inverter — so at
    # 1.3 m there is nothing to prioritise and the ranking is empty.
    fl = analyze_flood(b, mild_day, 1.7)

    graphs, failed_by_site, pop_served = [], {}, {}
    for sid, pop in (("big", 500), ("small", 150)):
        g = build_graph({**site, "id": sid}, b, fl)
        graphs.append(g)
        failed_by_site[sid] = sorted(n["id"] for n in g["nodes"] if n["health"] == "failed")
        pop_served[sid] = pop

    out = prioritize(graphs, failed_by_site, pop_served=pop_served)
    order = [r["site_id"] for r in out["ranked"]]
    assert order.index("big") < order.index("small")
    assert out["ranked"][0]["rank"] == 1
    assert out["placeholder"] is presets.DATA_IS_PLACEHOLDER


def test_deferred_repairs_are_the_failures_the_plan_deliberately_skips(mild_day):
    """
    The argument the Recovery page makes: what was flooded, what must be fixed to restore power,
    and what it is therefore correct to defer. Deferred and required must partition the failures.
    """
    site = presets.get_shelter("decennial_block")
    b = Building(**site["building"])
    fl = analyze_flood(b, mild_day, 1.7)   # deep enough to take the distribution panel down
    g = build_graph(site, b, fl)
    failed = sorted(n["id"] for n in g["nodes"] if n["health"] == "failed")

    row = prioritize([g], {site["id"]: failed})["ranked"][0]

    # partition: nothing counted twice, nothing dropped
    assert set(row["repairs"]) & set(row["deferred_repairs"]) == set()
    assert set(row["repairs"]) | set(row["deferred_repairs"]) == set(row["all_failed"])

    # the saving is real and consistent
    assert row["full_repair_effort_h"] >= row["repair_effort_h"]
    assert row["effort_saved_h"] == pytest.approx(
        row["full_repair_effort_h"] - row["repair_effort_h"]
    )

    # every deferred asset carries the cost avoided, so the UI can show the comparison
    assert all(d["effort_h"] > 0 for d in row["deferred"])
    assert {d["id"] for d in row["deferred"]} == set(row["deferred_repairs"])


# --- unsurveyed assets must not read as safe -------------------------------------------------

def test_unsurveyed_asset_reads_unknown_not_ok(site, building, mild_day):
    """
    An asset with no surveyed elevation must never render a plain "ok".

    This pins the direction of the failure. Once it fell through to "ok" and painted green at every
    depth — the model asserting an asset was dry when it had merely never been measured.

    The substation is now "ok_reported": the college states it sits above flood level, but no
    height was measured. That is a THIRD state on purpose. It must not collapse into "ok", which
    would let a verbal assurance read off the map as a survey result, and it is no longer "unknown"
    because a named source did make a claim.
    """
    deep = analyze_flood(building, mild_day, 2.0)   # deeper than every surveyed elevation
    g = build_graph(site, building, deep)
    substation = next(n for n in g["nodes"] if n["id"] == "substation")

    assert substation["elevation_m"] is None, "substation was surveyed; this test is now stale"
    assert substation["health"] == "ok_reported"
    assert substation["health"] != "ok", "a reported claim must never render as a measurement"


def test_an_asset_with_neither_height_nor_report_still_reads_unknown(site, building, mild_day):
    """
    Guards the original failure mode for assets nobody has claimed anything about. The UPS has no
    surveyed elevation and no report, so it must stay "unknown" — adding the reported tier must not
    have quietly promoted every unmeasured asset to green.
    """
    deep = analyze_flood(building, mild_day, 2.0)
    g = build_graph(site, building, deep)
    ups = next(n for n in g["nodes"] if n["id"] == "ups")

    assert ups["id"] not in presets.REPORTED_ABOVE_FLOOD
    assert ups["health"] == "unknown"

    # Every asset that IS surveyed still resolves to a real assessment at this depth.
    assessed = [n for n in g["nodes"] if n["elevation_m"] is not None]
    assert assessed, "no surveyed assets in the graph"
    assert all(n["health"] in ("ok", "at_risk", "failed") for n in assessed)


def test_ups_backs_the_it_load_and_is_not_a_single_point_of_failure(site, building, graph):
    """
    The UPS backs the server rack + network (2.0 kW), not the shelter's whole critical load.

    That scoping is the entire correctness question. Wired to the shelter node it would appear as
    a single point of failure — losing it would read as losing the shelter — which is false: what
    a UPS failure actually costs is coordination and ride-through across the transfer window.
    Placed under comms, it drops out of the power path where it belongs.
    """
    ids = {n["id"] for n in graph["nodes"]}
    assert "ups" in ids

    assert "ups" not in single_points_of_failure(graph)
    assert single_points_of_failure(graph) == ["distribution_panel"]

    # it reaches comms, and comms alone — it never carries the shelter's power
    assert downstream(graph, "ups") == ["comms", "shelter"]
    assert shelter_powered(graph, {"ups"}), "UPS loss must not cut shelter power"

    # no guessed height: it was not in the elevation survey
    ups = next(n for n in graph["nodes"] if n["id"] == "ups")
    assert ups["elevation_m"] is None

    # the network rack is deliberately NOT a second node — it is what `comms` already represents
    assert "network_rack" not in ids


def test_unknown_health_does_not_leak_into_the_repair_plan(site, building, mild_day):
    """
    "Unknown" must stay a display state. It is not a failure, so it must not be picked up as a
    repair job and charged the default 8 h effort.
    """
    deep = analyze_flood(building, mild_day, 2.0)
    g = build_graph(site, building, deep)
    failed = sorted(n["id"] for n in g["nodes"] if n["health"] == "failed")

    assert "substation" not in failed
    row = prioritize([g], {site["id"]: failed})["ranked"][0]
    assert "substation" not in row["repairs"]
    assert "substation" not in row["deferred_repairs"]


# --- the two survey records that disagree ----------------------------------------------------

def test_critical_load_itemisation_still_disagrees_with_the_reported_total():
    """
    Guards the 2.0 kW gap between the survey's circuit breakdown (20.0) and its reported total
    (18.0). This test is MEANT to fail the day the survey resolves it — that failure is the
    reminder to update critical_load_kw alongside, rather than letting a stale gap sit unnoticed.
    """
    assert presets.critical_load_itemised_total_kw() == 20.0
    assert presets.CRITICAL_LOAD_REPORTED_KW == 18.0
    assert presets.critical_load_discrepancy_kw() == 2.0
    assert presets.critical_load_is_reconciled() is False


def test_shelter_uses_the_reported_total_so_backup_hours_is_the_optimistic_reading(site):
    """
    Pins WHICH of the two disagreeing figures drives the dashboard. critical_load_kw divides into
    backup_hours, so using the smaller (18.0) makes every ride-through number the optimistic one.
    Worth stating in a test: if someone swaps in the itemised 20.0, ride-through drops ~10% and
    that should be a deliberate, visible change.
    """
    assert site["building"]["critical_load_kw"] == presets.CRITICAL_LOAD_REPORTED_KW
    assert presets.CRITICAL_LOAD_REPORTED_KW < presets.critical_load_itemised_total_kw()


def test_recovery_does_not_credit_population_to_a_repair_that_restores_nothing(graph):
    """
    Guards the first cut of this module, which credited a shelter's whole population to
    repairing one asset while the distribution panel was still underwater.
    """
    failed = {"transformer", "battery", "solar_inverter", "generator", "distribution_panel"}
    assert not shelter_powered(graph, failed - {"solar_inverter"}), (
        "repairing the inverter alone must NOT power the shelter while the panel is down"
    )


# --- Desk-derived bounds -----------------------------------------------------------------------
# These cover the values that were CONSTRAINED without a site visit (presets.DERIVED_VALUES).
# A derivation is not a measurement, so none of them clears DATA_IS_PLACEHOLDER — that is
# asserted too, because quietly retiring the notice is the failure mode worth guarding.


def test_shelter_capacity_bound_is_derived_from_surveyed_area(site):
    """
    Capacity ceiling = surveyed floor area / KSDMA minimum covered area per person.

    Pins the arithmetic so the citation cannot drift away from the number it justifies.
    """
    area = site["building"]["floor_area_m2"]
    bound = presets.shelter_capacity_upper_bound("decennial_block")
    assert bound == int(area // presets.SHELTER_AREA_PER_PERSON_M2)
    assert bound == 414


def test_reported_pop_served_is_corroborated_by_the_floor_area_bound():
    """
    This test previously asserted the OPPOSITE — that the standing 500 exceeded the 414 ceiling.
    That failure is what prompted asking the college, and the answer (400) now sits inside the
    bound. The flip is the intended lifecycle, and rewriting it forces the change to be conscious.

    Two independent routes now agree to within 3.5%: a verbal report from the people who run the
    building, and surveyed floor area divided by a published standard. Corroboration, NOT
    verification — both could still be describing normal occupancy rather than shelter capacity.
    """
    bound = presets.shelter_capacity_upper_bound("decennial_block")
    pop = presets.POP_SERVED["decennial_block"]

    assert pop == 400
    assert pop <= bound, f"reported {pop} exceeds the {bound} the floor area allows"
    assert presets.pop_served_exceeds_area_bound("decennial_block") is False
    assert presets.pop_served_overstatement("decennial_block") == 0


def test_capacity_bound_is_none_rather_than_invented_for_a_site_without_surveyed_area():
    """No floor area, no ceiling. Returning a number anyway would fabricate the constraint."""
    assert presets.shelter_capacity_upper_bound("no_such_site") is None
    # An unknown ceiling is not a violated one.
    assert presets.pop_served_exceeds_area_bound("no_such_site") is False
    assert presets.pop_served_overstatement("no_such_site") == 0


def test_pop_bound_check_honours_a_caller_supplied_population():
    """
    prioritize() can rank against caller-supplied populations, so the bound check must test THAT
    figure. Guards a real bug: the first cut compared the global POP_SERVED regardless of what
    the caller actually ranked with.
    """
    assert presets.pop_served_exceeds_area_bound("decennial_block", pop=100) is False
    assert presets.pop_served_exceeds_area_bound("decennial_block", pop=1000) is True


def test_critical_load_is_reported_as_the_interval_the_records_bracket():
    """The disagreement is bounded, never averaged into a figure neither record supports."""
    low, high = presets.critical_load_range_kw()
    assert (low, high) == (18.0, 20.0)
    assert low == presets.CRITICAL_LOAD_REPORTED_KW
    assert high == presets.critical_load_itemised_total_kw()
    # 19.0 would be the tempting "compromise". Nothing may produce it.
    assert low != high, "records agree; the range machinery should be retired deliberately"


def test_neither_derivations_nor_reports_clear_the_placeholder_notice():
    """
    Neither a desk derivation nor a verbal report is a measurement, so neither may retire the
    notice. `REPAIR_EFFORT_H` is still genuinely unsurveyed, which is what keeps it up.

    This is the load-bearing guard on the whole provenance design: the failure mode being
    prevented is someone clearing the banner by moving entries between registries rather than by
    measuring anything.
    """
    assert presets.DATA_IS_PLACEHOLDER is True
    assert presets.DATA_IS_PLACEHOLDER == bool(presets.UNSURVEYED_VALUES)
    assert "REPAIR_EFFORT_H" in presets.UNSURVEYED_VALUES

    # Values the college supplied moved to REPORTED — they must be in exactly one tier, never
    # dropped from all of them, which is how an unverified figure becomes an invisible one.
    for key in ("pop_served", "critical_load_kw"):
        assert key in presets.REPORTED_VALUES
        assert key not in presets.UNSURVEYED_VALUES
        assert key not in presets.SURVEYED_VALUES

    # The registries are kept disjoint so the UI cannot present a report or a derivation as a survey.
    assert not set(presets.DERIVED_VALUES) & set(presets.SURVEYED_VALUES)
    assert not set(presets.REPORTED_VALUES) & set(presets.SURVEYED_VALUES)
    assert not set(presets.REPORTED_VALUES) & set(presets.UNSURVEYED_VALUES)


# --- Pricing the unmeasured elevations ---------------------------------------------------------


def test_substation_is_reported_unassessed_not_ok(graph):
    """
    The substation has no surveyed elevation, so the model can never flood it. It must therefore
    read "unknown" — rendering it green would be the model asserting an asset is dry when it has
    simply never been measured.
    """
    from resilienceos.dependency_graph import unassessed_nodes
    assert "substation" in unassessed_nodes(graph)


def test_unassessed_sensitivity_runs_the_graph_both_ways(graph):
    """
    The honest substitute for inventing the substation elevation: report whether the outcome
    actually depends on the gap, instead of silently assuming the asset survived.
    """
    from resilienceos.dependency_graph import unassessed_sensitivity
    s = unassessed_sensitivity(graph)

    assert "substation" in s["unassessed"]
    # Both worlds are evaluated, and the pessimistic one is never more optimistic than the other.
    assert s["powered_if_unassessed_fail"] <= s["powered_if_unassessed_survive"]
    assert s["changes_outcome"] == (
        s["powered_if_unassessed_survive"] != s["powered_if_unassessed_fail"]
    )


def test_losing_the_substation_alone_does_not_unpower_the_shelter(graph):
    """
    The graph earning its keep: the substation feeds only the grid path, so losing it drops the
    grid while battery / solar / generator still carry the shelter. A per-asset checklist would
    flag it as a failure and stop there.
    """
    assert shelter_powered(graph, {"substation"})


def test_repair_effort_declares_which_figures_are_fallbacks():
    """
    The substation has no surveyed repair estimate. The generic 8 h default is kept (guessing
    higher would be equally invented and would bias the ranking), but it must be DECLARED.
    """
    from resilienceos.recovery import effort_is_estimated
    assert effort_is_estimated("substation") is True
    assert effort_is_estimated("transformer") is False


def test_a_reported_claim_is_used_but_still_challenged(site, building, mild_day):
    """
    The point of the REPORTED tier: the college's word is good enough to act on, and never good
    enough to stop testing.

    So the substation reads as working (the claim is used) AND still appears in the sensitivity
    analysis (the claim is priced). Promoting it out of `unassessed` the moment someone vouched
    for it would silently retire the only check on whether that vouching matters.

    Built against an actual flood rather than the bare `graph` fixture: with no flood result every
    node reads "unknown", so the fixture cannot distinguish the states this test exists to separate.
    """
    from resilienceos.dependency_graph import unassessed_nodes, unassessed_sensitivity

    deep = analyze_flood(building, mild_day, 2.0)   # deeper than every surveyed elevation
    g = build_graph(site, building, deep)

    substation = next(n for n in g["nodes"] if n["id"] == "substation")
    assert substation["health"] == "ok_reported"       # the claim is used
    assert "substation" in unassessed_nodes(g)         # and still challenged

    s = unassessed_sensitivity(g)
    assert "substation" in s["unassessed"]
    assert s["powered_if_unassessed_fail"] <= s["powered_if_unassessed_survive"]
