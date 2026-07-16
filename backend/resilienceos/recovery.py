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

# Indicative repair effort per asset (person-hours). Cheap proxy for "how hard to fix".
# TODO(user): replace with real crew estimates from the campus maintenance team.
REPAIR_EFFORT_H = {
    "transformer": 24.0,
    "distribution_panel": 8.0,
    "battery": 6.0,
    "solar_inverter": 4.0,
    "solar_panels": 12.0,
    "generator": 10.0,
    "road_access": 16.0,
    "comms": 3.0,
}

_DEFAULT_EFFORT_H = 8.0


def _effort(node: str) -> float:
    return REPAIR_EFFORT_H.get(node, _DEFAULT_EFFORT_H)


def restoration_plan(graph: dict, failed: set[str]) -> dict:
    """
    The minimum-effort set of repairs that re-powers this shelter.

    Exhaustive over subsets of the failed assets, smallest first, tie-broken by total effort —
    so the result is optimal for the modelled graph, not a greedy approximation.
    """
    failed = set(failed)
    if shelter_powered(graph, failed):
        return {"repairs": [], "effort_h": 0.0, "achievable": True, "already_powered": True}

    candidates = sorted(failed)
    for size in range(1, len(candidates) + 1):
        best: tuple[list[str], float] | None = None
        for combo in itertools.combinations(candidates, size):
            if shelter_powered(graph, failed - set(combo)):
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
               pop_served: dict[str, int] | None = None) -> dict:
    """
    graphs: one dependency graph per shelter. failed_by_site: {site_id: [failed node ids]}.

    Returns shelters ranked by population restored per repair-hour, each with the concrete
    minimum repair set that achieves it.
    """
    pop_served = pop_served if pop_served is not None else presets.POP_SERVED
    ranked: list[dict] = []

    for graph in graphs:
        site_id = graph["site_id"]
        failed = set(failed_by_site.get(site_id, []))
        if not failed:
            continue

        plan = restoration_plan(graph, failed)
        if plan["already_powered"]:
            continue   # nothing to prioritise; the shelter is still running

        pop = pop_served.get(site_id, 0)
        effort = plan["effort_h"]
        labels = {n["id"]: n["label"] for n in graph["nodes"]}

        ranked.append({
            "site_id": site_id,
            "site_name": graph["site_name"],
            "repairs": plan["repairs"],
            "repair_labels": [labels.get(r, r) for r in plan["repairs"]],
            "repair_effort_h": effort,
            "population_restored": pop if plan["achievable"] else 0,
            "pop_per_effort_h": round(pop / effort, 2) if effort and plan["achievable"] else 0.0,
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
