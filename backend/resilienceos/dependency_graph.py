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
    "distribution_panel": 1, "comms": 1,
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
    """"failed" | "at_risk" | "ok", derived from the flood result's inundated asset list."""
    if asset == "shelter":
        return "failed" if not flood.operational else "ok"
    if asset in flood.failed_equipment:
        return "failed"
    elev = presets.EQUIPMENT_ELEVATION_M.get(asset)
    if elev is not None and elev - flood.flood_depth_m <= presets.AT_RISK_MARGIN_M:
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
