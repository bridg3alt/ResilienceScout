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
    The substation has no surveyed elevation, so it must never render "ok".

    This pins the direction of the failure. Previously it fell through to "ok" and painted green
    at every depth — the model asserting an asset was dry when it had merely never been measured.
    An unmeasured asset is "unknown"; only a measurement can make it "ok".
    """
    deep = analyze_flood(building, mild_day, 2.0)   # deeper than every surveyed elevation
    g = build_graph(site, building, deep)
    substation = next(n for n in g["nodes"] if n["id"] == "substation")

    assert substation["elevation_m"] is None, "substation was surveyed; this test is now stale"
    assert substation["health"] == "unknown"

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
