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
    The whole reason elevation is tracked per-asset rather than per-building: at 1.2 m the
    roof-mounted array is untouched but the inverter it feeds is underwater, so the PV
    contributes nothing. A building-level flood flag cannot represent this.
    """
    failed = presets.flooded_equipment(1.2)
    assert "solar_inverter" in failed
    assert "solar_panels" not in failed


def test_flood_zeroes_only_the_der_that_actually_drowned(building, mild_day):
    dry = analyze_flood(building, mild_day, 0.0)
    wet = analyze_flood(building, mild_day, 0.4)   # battery at 0.3 m is under; inverter is not
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
    wet = analyze_flood(building, mild_day, 0.4)
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
    Exhaustive search must select the solar inverter (4h) over the transformer (24h). A greedy
    pass that grabbed the highest-capacity asset would pick wrong here.
    """
    failed = {"transformer", "battery", "solar_inverter", "generator", "distribution_panel"}
    plan = restoration_plan(graph, failed)
    assert set(plan["repairs"]) == {"distribution_panel", "solar_inverter"}
    assert plan["effort_h"] == pytest.approx(12.0)


def test_recovery_ranks_by_population_per_effort_hour(mild_day):
    """At equal repair effort, the shelter serving more people must rank first.

    Built from two SYNTHETIC copies of the one real building with different populations, so the
    population-per-effort-hour ranking stays covered without a multi-shelter roster.
    """
    site = presets.get_shelter("decennial_block")
    b = Building(**site["building"])
    fl = analyze_flood(b, mild_day, 1.3)

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


def test_recovery_does_not_credit_population_to_a_repair_that_restores_nothing(graph):
    """
    Guards the first cut of this module, which credited a shelter's whole population to
    repairing one asset while the distribution panel was still underwater.
    """
    failed = {"transformer", "battery", "solar_inverter", "generator", "distribution_panel"}
    assert not shelter_powered(graph, failed - {"solar_inverter"}), (
        "repairing the inverter alone must NOT power the shelter while the panel is down"
    )
