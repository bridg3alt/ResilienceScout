"""
Post-flood recovery prioritisation — repair what restores the most people per hour of work.

Ranks SHELTERS, not individual assets, because a severe flood takes out several assets at once
and no single repair re-powers anything on its own. Crediting a shelter's whole population to
"repair the solar inverter" while the distribution panel is still underwater would be a lie;
the unit of decision is the smallest set of repairs that actually turns the lights back on.

That set is found EXHAUSTIVELY rather than greedily: a shelter has under ten modelled assets,
so searching subsets by increasing size is cheap and returns the true minimum-effort plan.
Greedy would be faster and occasionally wrong, and there is no reason to accept that here.

Mirrors `scenarios.budget_optimizer`'s ranking idiom (benefit per unit cost, then fit).

The ranking is only ever as honest as `presets.POP_SERVED`, which is currently INVENTED — every
result carries `placeholder: True`. This demonstrates the method; it is not advice.
"""
from __future__ import annotations

import itertools

from . import presets
from .dependency_graph import downstream, shelter_powered

# Repair effort per asset (person-hours). Cheap proxy for "how hard to fix".
#
# SOURCED — replaced with the campus maintenance team's own estimates during the site survey.
# These reorder the recovery ranking materially versus the previous guesses: the transformer is
# far worse than assumed (48 h, not 24) while solar panels are far cheaper (4 h, not 12), so
# plans that lean on grid restoration now score much worse against plans that restore local
# generation first.
REPAIR_EFFORT_H = {
    "comms": 3.0,               # SOURCED
    "solar_panels": 4.0,        # SOURCED: midpoint of the team's 3–5 h range
    "solar_inverter": 6.0,      # SOURCED
    "distribution_panel": 8.0,  # SOURCED (revised up from an earlier 5.0)
    "road_access": 8.0,         # SOURCED (revised down from an earlier 10.0)
    "battery": 10.0,            # SOURCED (revised up from an earlier 8.0)
    "generator": 12.0,          # SOURCED
    "transformer": 48.0,        # SOURCED: the long pole by a wide margin
}

# TODO(user): the substation node has no surveyed repair estimate, so it falls through to the
# default below. A grid asset that big is unlikely to be an 8 h job — get a real figure before
# any plan leans on restoring it.
#
# The number is kept at 8.0 rather than inflated to something "safer": guessing higher would be
# just as invented, and would additionally bias the ranking by making grid restoration look
# unattractive on fabricated grounds. What changes instead is that the guess is now DECLARED —
# `effort_is_estimated()` marks it, and every plan carries the list of repairs whose effort is a
# fallback rather than a survey figure, so a reader can see which parts of a ranking rest on it.
_DEFAULT_EFFORT_H = 8.0


def _effort(node: str) -> float:
    return REPAIR_EFFORT_H.get(node, _DEFAULT_EFFORT_H)


def effort_is_estimated(node: str) -> bool:
    """True when this asset's repair effort is the generic fallback, not a surveyed estimate."""
    return node not in REPAIR_EFFORT_H


def restoration_plan(graph: dict, failed: set[str],
                     is_adequate=None) -> dict:
    """
    The minimum-effort set of repairs that returns this shelter to service.

    Exhaustive over subsets of the failed assets, smallest first, tie-broken by total effort —
    so the result is optimal for the modelled graph, not a greedy approximation.

    `is_adequate`: optional callable(repaired: frozenset[str]) -> bool, layered ON TOP of graph
    connectivity. When supplied, a repair set only counts if the shelter is both wired up AND able
    to carry its critical load for the required window.

    Why it exists. `shelter_powered()` asks "is a wire still connected?", which is not the same
    question as "can this shelter do its job?". At 1.2 m of water the battery, generator and
    transformer are all drowned while the roof-mounted solar inverter survives — so the graph reads
    POWERED and this function used to return "already_powered, nothing to repair", at the exact
    moment the energy model reported 0 h of backup and CERI scored the shelter Critical.

    The recovery page was therefore empty precisely when the shelter was in its worst state, and
    the post-flood phase rendered identically to the during-flood phase because no repairs were
    ever applied. Connectivity is necessary and not sufficient; adequacy is the operational
    question, and the caller supplies it because the energy model lives outside this module.
    """
    failed = set(failed)

    def _restored(remaining_failed: set[str]) -> bool:
        if not shelter_powered(graph, remaining_failed):
            return False
        if is_adequate is None:
            return True
        return is_adequate(frozenset(failed - remaining_failed))

    if _restored(failed):
        return {"repairs": [], "effort_h": 0.0, "achievable": True, "already_powered": True}

    candidates = sorted(failed)
    for size in range(1, len(candidates) + 1):
        best: tuple[list[str], float] | None = None
        for combo in itertools.combinations(candidates, size):
            if _restored(failed - set(combo)):
                eff = sum(_effort(c) for c in combo)
                if best is None or eff < best[1]:
                    best = (list(combo), eff)
        if best is not None:
            return {
                "repairs": best[0],
                "effort_h": round(best[1], 1),
                "achievable": True,
                "already_powered": False,
            }

    # Unreachable in the current model (repairing everything always powers the shelter), but
    # kept explicit so a future topology change fails loudly instead of silently ranking wrong.
    return {
        "repairs": candidates,
        "effort_h": round(sum(_effort(c) for c in candidates), 1),
        "achievable": False,
        "already_powered": False,
    }


def prioritize(graphs: list[dict], failed_by_site: dict[str, list[str]],
               pop_served: dict[str, int] | None = None,
               adequacy_by_site: dict[str, object] | None = None) -> dict:
    """
    graphs: one dependency graph per shelter. failed_by_site: {site_id: [failed node ids]}.

    Returns shelters ranked by population restored per repair-hour, each with the concrete
    minimum repair set that achieves it.

    `adequacy_by_site`: optional {site_id: callable(repaired) -> bool}. Supplying it makes a
    shelter count as needing repair when it cannot carry its critical load for the required
    window, rather than only when the graph is disconnected — see `restoration_plan`.
    """
    pop_served = pop_served if pop_served is not None else presets.POP_SERVED
    adequacy_by_site = adequacy_by_site or {}
    ranked: list[dict] = []

    for graph in graphs:
        site_id = graph["site_id"]
        # The shelter node reports "failed" when it is unpowered, but it is the OUTCOME of the
        # graph, not an asset anyone repairs. Left in, it pollutes the failure list and picks up
        # the default effort, so the plan would offer "repair the shelter, 8h" as if that were a
        # job. Drop it: repairs act on the assets that feed the shelter.
        failed = set(failed_by_site.get(site_id, [])) - {"shelter"}
        if not failed:
            continue

        plan = restoration_plan(graph, failed, adequacy_by_site.get(site_id))
        if plan["already_powered"]:
            continue   # nothing to prioritise; the shelter is carrying its load

        pop = pop_served.get(site_id, 0)
        bound = presets.shelter_capacity_upper_bound(site_id)
        effort = plan["effort_h"]
        labels = {n["id"]: n["label"] for n in graph["nodes"]}

        # What the search decided NOT to repair, and what that decision is worth.
        #
        # This is the whole argument, and it is the half a damage report cannot make: a flooded
        # transformer is a real failure, but repairing it can be both the most expensive job on
        # the list and worth nothing, because every source is wired through the distribution
        # panel. Naming the deferred assets WITH their cost is what turns the minimum repair set
        # from an assertion into a comparison the reader can check.
        deferred_ids = sorted(failed - set(plan["repairs"]))
        deferred = [
            {
                "id": d,
                "label": labels.get(d, d),
                "effort_h": _effort(d),
                "effort_estimated": effort_is_estimated(d),
            }
            for d in deferred_ids
        ]
        full_effort = round(sum(_effort(f) for f in failed), 1)

        ranked.append({
            "site_id": site_id,
            "site_name": graph["site_name"],
            "repairs": plan["repairs"],
            "repair_labels": [labels.get(r, r) for r in plan["repairs"]],
            "repair_effort_h": effort,
            # Which repairs in THIS plan are costed from a fallback rather than a survey figure.
            # Non-empty means the plan's effort total — and therefore its rank — rests partly on
            # a guess, which the dashboard flags rather than presenting the ranking as settled.
            "estimated_effort_repairs": [r for r in plan["repairs"] if effort_is_estimated(r)],
            "deferred_repairs": deferred_ids,
            "deferred": deferred,
            "full_repair_effort_h": full_effort,
            "effort_saved_h": round(full_effort - effort, 1),
            "population_restored": pop if plan["achievable"] else 0,
            "pop_per_effort_h": round(pop / effort, 2) if effort and plan["achievable"] else 0.0,
            # The same figure recapped at the floor-area capacity ceiling (presets), which for
            # this shelter is LOWER than the standing pop_served. Carried alongside rather than
            # substituted: the bound is a ceiling, not a measurement, so it belongs next to the
            # claim as a check on it. With one shelter modelled the ranking is unchanged either
            # way — this exists so that stops being true silently once a second is added.
            #
            # None when the site has no surveyed floor area (synthetic sites in the tests), so an
            # absent bound reads as "unknown" downstream instead of as an unconstrained pass.
            "population_restored_area_bounded": (
                (min(pop, bound) if bound is not None else None)
                if plan["achievable"] else 0
            ),
            "pop_exceeds_area_bound": presets.pop_served_exceeds_area_bound(site_id, pop),
            "achievable": plan["achievable"],
            "services_restored": sorted(
                {s for r in plan["repairs"] for s in downstream(graph, r)}
            ),
            "all_failed": sorted(failed),
        })

    ranked.sort(key=lambda r: (-r["pop_per_effort_h"], r["repair_effort_h"]))
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i

    return {
        "ranked": ranked,
        "total_population_restorable": sum(
            r["population_restored"] for r in ranked
        ),
        "total_effort_h": round(sum(r["repair_effort_h"] for r in ranked), 1),
        "placeholder": presets.DATA_IS_PLACEHOLDER,
    }
