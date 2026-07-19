"""
Shelter dependency graph — what a flood actually takes down, and what that cascades into.

Plain dicts and a BFS. No graph library: the graph is a handful of nodes per site, so a
dependency is not worth the install.

Edges point from PROVIDER to DEPENDENT (`transformer -> shelter` reads "the transformer
supports the shelter"), so `downstream(node)` answers the operational question — if this asset
drowns, what else stops working?

The analytical payload is `single_points_of_failure()`: a shelter with a battery AND a
generator survives losing either one, while a shelter running on grid alone does not. That
distinction is invisible in a per-asset checklist and is the reason for modelling the graph.
"""
from __future__ import annotations

from collections import deque

from . import presets

# Assets that can independently carry the shelter's critical load.
POWER_SOURCES = ("transformer", "battery", "solar_inverter", "generator")

# tier drives the layered layout the dashboard renders (0 = shelter, left/top).
_TIERS = {
    "shelter": 0,
    "distribution_panel": 1, "comms": 1, "ups": 1,
    "transformer": 2, "battery": 2, "solar_inverter": 2, "generator": 2,
    "solar_panels": 3, "road_access": 3, "substation": 3,
}

_LABELS = {
    "shelter": "Shelter",
    "transformer": "Transformer",
    "distribution_panel": "Distribution panel",
    "battery": "Battery",
    "solar_inverter": "Solar inverter",
    "solar_panels": "Solar panels (roof)",
    "generator": "Generator",
    "road_access": "Road access",
    "comms": "Communications",
    "ups": "UPS (IT load)",
    "substation": "Campus substation (11 kV)",
}

# provider -> dependents. Every power source feeds the shelter THROUGH the distribution panel:
# that is what makes the panel a genuine single point of failure, and modelling sources as
# wiring straight into the shelter would hide it.
_DEPENDENCIES = [
    # SOURCED: the site survey confirmed the campus 11 kV substation is the grid feed for this
    # block, upstream of its 250 kVA transformer. Modelled now that the connection is confirmed;
    # before the survey it was deliberately left out rather than assumed.
    # Consequence: the grid path is only alive if BOTH substation and transformer are alive, so
    # losing the substation drops the grid but not the shelter — battery/solar/generator still
    # carry it. That is the graph earning its keep rather than a checklist.
    # TODO(user): the substation's elevation was not surveyed, so it has no entry in
    # EQUIPMENT_ELEVATION_M and therefore never floods in the model. Measure it — a substation
    # below the water line would take the grid out earlier than the model currently shows.
    ("substation", "transformer"),
    ("transformer", "distribution_panel"),
    ("battery", "distribution_panel"),
    ("solar_inverter", "distribution_panel"),
    ("generator", "distribution_panel"),
    ("distribution_panel", "shelter"),
    ("solar_panels", "solar_inverter"),   # panels feed the inverter, not the shelter directly
    ("road_access", "generator"),         # no road, no fuel resupply
    # SOURCED: the UPS backs the IT load only — server rack (1.2 kW) + network (0.8 kW) — so it
    # sits between the panel and comms rather than under the shelter. That placement is the whole
    # point: a UPS wired to the shelter node would register as a single point of failure, which
    # would be false, because losing it costs coordination and transfer-window ride-through, not
    # the shelter's power. Losing the panel already takes comms down; the UPS is what carries the
    # IT load across the seconds between mains loss and the generator's ATS picking up.
    ("distribution_panel", "ups"),
    ("ups", "comms"),
    ("comms", "shelter"),                 # coordination, not power — never gates power
]


def _asset_present(asset: str, building) -> bool:
    """Only graph what the shelter actually has — don't invent a generator it lacks."""
    if asset == "battery":
        return building.battery_kwh > 0
    if asset in ("solar_inverter", "solar_panels"):
        return building.solar_kwp > 0
    if asset == "generator":
        return building.has_generator
    return True


def build_graph(site: dict, building, flood=None, repaired=frozenset()) -> dict:
    """
    site: a presets.SHELTERS entry. building: the resilienceos Building for that site.
    flood: an optional hazard.FloodResult — when given, every node carries a health status.
    repaired: assets restored in the recovery phase — forced to "ok" health regardless of the
    water line, so the post-flood map shows them mended.
    """
    present = [a for a in _TIERS if a == "shelter" or _asset_present(a, building)]
    nodes = [
        {
            "id": a,
            "label": _LABELS[a],
            "tier": _TIERS[a],
            "elevation_m": presets.EQUIPMENT_ELEVATION_M.get(a),
            "health": ("ok" if a in repaired else node_health(a, flood)) if flood is not None else "unknown",
            "is_power_source": a in POWER_SOURCES,
        }
        for a in present
    ]
    edges = [
        {"from": src, "to": dst}
        for src, dst in _DEPENDENCIES
        if src in present and dst in present
    ]
    return {
        "site_id": site["id"],
        "site_name": site["name"],
        "nodes": nodes,
        "edges": edges,
        "placeholder": presets.DATA_IS_PLACEHOLDER,
    }


def node_health(asset: str, flood) -> str:
    """
    "failed" | "at_risk" | "ok" | "unknown", derived from the flood result's inundated asset list.

    An asset with NO surveyed elevation returns "unknown", never "ok". This previously fell
    through to "ok", which failed in the dangerous direction: the substation has no entry in
    EQUIPMENT_ELEVATION_M, so it rendered green at every depth — the model asserting an asset
    was dry when it had simply never been measured. "Unknown" is the honest state, and the
    dashboard already paints it slate ("Not assessed") rather than green.

    "ok_reported" is the middle state: the site owner says the asset stays dry, but no height was
    measured. Kept distinct from "ok" so a verbal assurance can never be read off the map as a
    survey result, and still included in unassessed_nodes() so its risk is priced.

    Note this makes the node visibly unassessed but does not make it fail: it still never enters
    the failed set, so `shelter_powered` continues to treat the grid path as alive. Closing that
    needs the measurement, not more code — see the TODO on the substation edge above.

    What CAN be done without the measurement is to price the assumption rather than inherit it:
    `unassessed_sensitivity()` runs the graph with these nodes failed as well as dry, and reports
    whether the shelter's outcome actually turns on the gap.
    """
    if asset == "shelter":
        return "failed" if not flood.operational else "ok"
    if asset in flood.failed_equipment:
        return "failed"
    # Reported by the site owner as above any credible flood level, without a height being given.
    # Distinct from both "ok" (measured dry) and "unknown" (nobody knows): the claim is used, but
    # it is labelled so the dashboard never presents hearsay as a survey result.
    if asset in presets.REPORTED_ABOVE_FLOOD:
        return "ok_reported"
    elev = presets.EQUIPMENT_ELEVATION_M.get(asset)
    if elev is None:
        return "unknown"
    if elev - flood.flood_depth_m <= presets.AT_RISK_MARGIN_M:
        return "at_risk"
    return "ok"


def downstream(graph: dict, node_id: str) -> list[str]:
    """Everything that stops working if `node_id` fails. BFS over provider->dependent edges."""
    adj: dict[str, list[str]] = {}
    for e in graph["edges"]:
        adj.setdefault(e["from"], []).append(e["to"])

    seen: set[str] = set()
    q = deque(adj.get(node_id, []))
    while q:
        cur = q.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        q.extend(adj.get(cur, []))
    return sorted(seen)


def _source_alive(graph: dict, source: str, failed: set[str]) -> bool:
    """
    A power source works only if it is dry AND everything it needs is dry (panels for the
    inverter, road access for the generator's fuel). AND semantics, walked upstream.
    """
    if source in failed:
        return False
    for e in graph["edges"]:
        if e["to"] == source and not _source_alive(graph, e["from"], failed):
            return False
    return True


def shelter_powered(graph: dict, failed: set[str]) -> bool:
    """
    Can the shelter carry power with `failed` nodes down?

    Power is an OR across sources (any one live source suffices) but an AND through the
    distribution panel (everything is wired through it). Plain BFS reachability cannot express
    that mix, which is why this is not just `downstream()`.
    """
    ids = {n["id"] for n in graph["nodes"]}
    if "distribution_panel" in ids and "distribution_panel" in failed:
        return False
    sources = [n["id"] for n in graph["nodes"] if n["is_power_source"]]
    return any(_source_alive(graph, s, failed) for s in sources)


def single_points_of_failure(graph: dict) -> list[str]:
    """
    Nodes whose individual failure alone leaves the shelter unpowered.

    This is the question a per-asset checklist cannot answer: losing the transformer is
    survivable with a charged battery and fatal without one, and the distribution panel is
    fatal either way because every source is wired through it.
    """
    ids = {n["id"] for n in graph["nodes"]}
    if not shelter_powered(graph, set()):
        return []   # already unpowered with nothing failed; SPOF is not meaningful
    return sorted(c for c in ids - {"shelter"} if not shelter_powered(graph, {c}))


def failed_nodes(graph: dict) -> list[str]:
    return sorted(n["id"] for n in graph["nodes"] if n["health"] == "failed")


def unassessed_nodes(graph: dict) -> list[str]:
    """
    Assets whose flood exposure rests on something other than a measurement.

    Covers both "unknown" (no elevation, nobody knows) and "ok_reported" (the site owner says it
    stays dry, but nobody has checked). Neither ever enters the failed set, which means every
    downstream result assumes they SURVIVED — in the first case by default, in the second on
    hearsay. Naming both is what lets a caller price that assumption instead of inheriting it.

    A reported claim is better evidence than no claim, but it is still not a measurement, so it
    belongs in the same sensitivity test rather than being quietly promoted to certainty.
    """
    return sorted(n["id"] for n in graph["nodes"] if n["health"] in ("unknown", "ok_reported"))


def unassessed_sensitivity(graph: dict) -> dict:
    """
    What the unmeasured assets are worth, by testing the assumption instead of trusting it.

    The model assumes every unassessed asset survives the flood, because an asset with no
    surveyed elevation can never be inundated. That assumption is optimistic and invisible: the
    substation has no measured elevation, so the grid path reads alive at every depth.

    So run the graph BOTH ways — once as the model currently assumes (unassessed assets dry) and
    once with all of them failed — and report whether the shelter's power outcome actually
    depends on the gap. `changes_outcome` False means the missing survey is not load-bearing for
    this result and can be deprioritised; True means the headline number rests on a measurement
    nobody has taken, and the dashboard says so rather than showing a single confident answer.

    This is the honest substitute for inventing the elevation: it does not tell us whether the
    substation floods, it tells us how much it matters that we do not know.
    """
    unknown = set(unassessed_nodes(graph))
    already_failed = set(failed_nodes(graph))

    powered_optimistic = shelter_powered(graph, already_failed)
    powered_pessimistic = shelter_powered(graph, already_failed | unknown)

    return {
        "unassessed": sorted(unknown),
        "powered_if_unassessed_survive": powered_optimistic,
        "powered_if_unassessed_fail": powered_pessimistic,
        "changes_outcome": powered_optimistic != powered_pessimistic,
        # SPOFs can appear only in the pessimistic world; naming them tells the reader which
        # measurement would change the recommendation, not merely that one is missing.
        "spofs_if_unassessed_fail": sorted(
            c for c in {n["id"] for n in graph["nodes"]} - {"shelter"}
            if not shelter_powered(graph, (already_failed | unknown) | {c})
        ),
    }
