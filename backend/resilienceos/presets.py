"""
ResilienceScout — the placeholder chokepoint.

Almost every number here is INVENTED and has never been surveyed. It exists so the app can run
end-to-end for a demo, and it is quarantined here so that replacing it with real data is a
one-file job rather than an archaeology expedition.

Two epistemic tiers, and the comments say which is which:
  * SOURCED  — a real, cited value. Carries its citation, and no TODO.
  * INVENTED — a guess. Carries a TODO(user). This is still the large majority of the file.

One placeholder lives outside this file: REPAIR_EFFORT_H in recovery.py.

`DATA_IS_PLACEHOLDER` is surfaced through the API as `placeholder: true` on every response, and
the dashboard renders a persistent "DEMO DATA — NOT SURVEYED" banner while it is True. Flip it
to False ONLY once every TODO below (and REPAIR_EFFORT_H) has been replaced with a surveyed
value. See docs/SURVEY.md for how to collect them.

WHAT MUST BE SURVEYED TO MAKE THIS REAL — no amount of desk research substitutes for these:
  1. Campus flood-line elevation and historical flood depths. KSDMA publishes only probability
     zones, not depths, so this needs the 2018 high-water survey.
  2. Mounting height of each piece of electrical equipment, measured from finished floor.
     Standards give MINIMUMS, not actuals; assuming code-minimum biases the model toward
     falsely reporting a shelter safe.
  3. Population served per shelter, and which clinics/pumps depend on which transformer.
     The campus single-line diagram answers the dependency half of this directly.
  4. Actual DER nameplate: solar kWp, battery kWh/chemistry, generator fuel + runtime.
"""
from __future__ import annotations

# Flip to False only when every TODO in this file has been replaced with surveyed data.
DATA_IS_PLACEHOLDER = True

# --- Flood hazard --------------------------------------------------------------------------
# TODO(user): replace with the surveyed campus flood line (m above finished floor level).
FLOOD_LINE_M = 0.9

# TODO(user): replace with modelled/observed depths for the Kodakara campus area.
# Checked KSDMA (sdma.kerala.gov.in/hazard-maps): they publish flood hazard PROBABILITY maps
# per district (historic + RCP 8.5) and return-period rasters, but no inundation DEPTH in
# metres. So there is no public source for these numbers — they must come from the 2018
# high-water survey described in docs/SURVEY.md. Still invented.
#
# EXTERNAL CAUTION (not a source of truth, do NOT copy these into the scenarios below):
# A satellite study of the August 2018 Kerala flood found the Kole lands of Thrissur rose by up
# to ~10 m, with a ~3.84 m regional mean inundation. That is a whole different order than the
# 1.2 m "severe" case here — so this "severe" is very plausibly an UNDERESTIMATE. It is left as
# a placeholder on purpose (DATA_IS_PLACEHOLDER stays True); the point of the citation is that it
# makes the real on-site campus survey more urgent, not that these regional figures are our
# numbers. Do not treat the 10 m / 3.84 m as scenario inputs.
FLOOD_SCENARIOS_M = {
    "nuisance": 0.2,
    "moderate": 0.6,
    "severe": 1.2,
}

# --- Equipment elevations ------------------------------------------------------------------
# Height of each asset above finished floor [m]. Anything at or below the flood depth is
# assumed inundated and offline.
# TODO(user): measure each of these on site. Roof-mounted PV panels survive almost any flood,
# but the INVERTER is usually at ground level — that distinction is the whole point of
# modelling elevation per-asset rather than per-building, so verify it rather than trusting it.
EQUIPMENT_ELEVATION_M = {
    "transformer": 0.5,
    "battery": 0.3,
    "solar_inverter": 1.2,
    "solar_panels": 9.6,        # roof-mounted; effectively never inundated
    "generator": 0.6,
    "distribution_panel": 1.0,
    "road_access": 0.25,        # access road overtops early; blocks fuel resupply
    "comms": 2.5,               # mast/rooftop mounted
}

# Margin below which an asset is "at risk" rather than "ok" — i.e. the water is close.
# TODO(user): set from survey confidence once elevations are measured rather than estimated.
AT_RISK_MARGIN_M = 0.3

# Which Building capability each asset carries. When an asset floods, its effect is applied to
# a copy of the Building, and the EXISTING energy-balance backup model does the rest.
EQUIPMENT_EFFECT = {
    "battery": {"battery_kwh": 0.0},
    "solar_inverter": {"solar_kwp": 0.0},   # panels intact, but nothing to convert their DC
    "generator": {"has_generator": False},
}

# --- Operational targets -------------------------------------------------------------------
# TODO(user): pick and defend this number locally — there is no standard to copy it from.
# Checked the Kerala State Minimum Standards of Relief (KSDMA, Ed. 1, 9 July 2020): it requires
# only that "Power supply to relief camps shall be ensured (KSEB)" and that "Basic lighting
# facilities shall be made available", with NO duration in hours. NDMA's national guidelines are
# no more specific. So 12 h is OUR assumption, not a regulatory threshold, and any claim that a
# shelter "meets the standard" on backup hours would be unfounded.
REQUIRED_BACKUP_H = 12.0     # target critical-load ride-through during a flood event
CRITICAL_SPOF_LIMIT = 2      # above this many single points of failure, score bottoms out

# --- Shelter inventory ---------------------------------------------------------------------
# ONE real candidate building — the Decennial Block at Sahrdaya College of Engineering &
# Technology, Kodakara, Thrissur. The earlier three-shelter roster (Blocks A/B/C) was invented
# scaffolding; the demo is now honest about modelling the single building that actually exists.
#
# What is SOURCED vs INVENTED for this entry:
#   * SOURCED  — the building's identity and campus location (10.3595, 76.2859, Kodakara campus
#                centre; Open-Meteo's grid is coarser than the campus, so centre precision is
#                fine).
#   * INVENTED — pop_served (500) and solar_kwp (180) are round placeholders; battery_kwh,
#                has_generator, floor area, critical load, and every EQUIPMENT_ELEVATION_M are
#                UNMEASURED and TODO(user)-flagged below. Nothing here is surveyed
#                (DATA_IS_PLACEHOLDER stays True).
#
# TODO(user): a campus SUBSTATION exists and is the real grid feed for this block. It should be
# added as an upstream node in the dependency graph (feeding the transformer) once its physical
# connection to the Decennial Block is confirmed on site. Not modelled yet — adding it before the
# connection is confirmed would invent a topology.
SHELTERS = [
    {
        "id": "decennial_block",
        "name": "Decennial Block — Sahrdaya College of Engineering, Kodakara",
        "pop_served": 500,   # TODO(user): INVENTED round number; confirm real shelter capacity.
        "building": {
            "name": "Decennial Block — Sahrdaya College of Engineering, Kodakara",
            # SOURCED: Sahrdaya College of Engineering & Technology, Kodakara, Thrissur campus
            # centre (10.3595, 76.2859).
            "latitude": 10.3595, "longitude": 76.2859,
            # TODO(user): floor area / floors — estimated, not surveyed.
            "floor_area_m2": 1200.0, "num_floors": 3,
            "solar_kwp": 180.0,      # TODO(user): INVENTED nameplate; confirm installed PV kWp.
            "battery_kwh": 20.0,     # TODO(user): UNMEASURED — placeholder so the model keeps a
                                     # battery source; confirm real storage (kWh/chemistry).
            "critical_load_kw": 5.0, # TODO(user): UNMEASURED critical load.
            "has_generator": True,   # TODO(user): UNMEASURED — assumed present; confirm on site.
        },
    },
]

POP_SERVED = {s["id"]: s["pop_served"] for s in SHELTERS}


def get_shelter(site_id: str) -> dict:
    for s in SHELTERS:
        if s["id"] == site_id:
            return s
    raise KeyError(f"unknown shelter id: {site_id!r} (known: {[s['id'] for s in SHELTERS]})")


def flooded_equipment(flood_depth_m: float) -> list[str]:
    """Assets at or below the flood depth. Sorted for deterministic output."""
    return sorted(
        name for name, elev in EQUIPMENT_ELEVATION_M.items() if elev <= flood_depth_m
    )
