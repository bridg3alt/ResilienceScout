"""
Building model: turn MINIMAL building info into a physics-ready 5R1C zone.

This is the "low-data" core of ResilienceOS. From a handful of numbers a facility
manager actually knows (floor area, floors, window fraction, wall/roof material,
glazing) we derive the geometry and U-values that the ISO-13790 5R1C engine needs.
No BMS, no sensors, no detailed CAD required.

U-value / SHGC presets are indicative values for typical Indian public-building
construction. Swap for TEASER archetype tables (RWTH-EBC) when calibrating.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from math import sqrt

WALL_U = {
    "brick_uninsulated": 2.0,
    "brick_plaster": 1.8,
    "rcc_solid": 2.5,
    "aac_block": 0.6,
    "insulated": 0.35,
}
ROOF_U = {
    "rcc_bare": 3.2,
    "rcc_tiled": 2.6,
    "cool_roof": 3.2,
    "insulated_roof": 0.5,
}
ROOF_SOLAR_ABSORPTANCE = {
    "rcc_bare": 0.85,
    "rcc_tiled": 0.65,
    "cool_roof": 0.25,
    "insulated_roof": 0.6,
}
GLAZING = {
    "single_clear": {"u": 5.7, "shgc": 0.82},
    "single_tinted": {"u": 5.7, "shgc": 0.55},
    "double_clear": {"u": 2.8, "shgc": 0.70},
    "double_lowe": {"u": 1.8, "shgc": 0.40},
}
MASS_CLASS = {
    "light": 80000,
    "medium": 165000,
    "heavy": 260000,
}

CEILING_HEIGHT_M = 3.2
LAMBDA_AT = 4.5
PERSON_SENSIBLE_W = 90.0
EQUIPMENT_W_PER_M2 = 5.0


@dataclass
class Building:
    """Minimal building description a non-technical operator can supply."""
    name: str = "Decennial Block"
    latitude: float = 12.9716
    longitude: float = 77.5946
    floor_area_m2: float = 1200.0
    num_floors: int = 3
    window_to_wall_ratio: float = 0.25
    wall_material: str = "brick_plaster"
    roof_material: str = "rcc_bare"
    glazing: str = "single_clear"
    mass_class: str = "heavy"
    has_hvac: bool = True
    hvac_capacity_w_per_m2: float = 80.0
    occupancy_peak: int = 120
    solar_kwp: float = 20.0
    battery_kwh: float = 0.0
    has_generator: bool = False
    generator_rated_kw: float = 0.0
    generator_runtime_h: float = 0.0
    t_set_cooling: float = 26.0
    critical_load_kw: float = 5.0
    infiltration_ach: float = 0.7
    capacitance_override: float | None = None
    solar_aperture_scale: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Geometry:
    floor_area: float
    walls_area: float
    window_area: float
    roof_area: float
    room_vol: float
    total_internal_area: float
    facade_area: float


def derive_geometry(b: Building) -> Geometry:
    """Estimate envelope areas from footprint, treating the block as ~square."""
    footprint = b.floor_area_m2 / max(b.num_floors, 1)
    side = sqrt(footprint)
    perimeter = 4.0 * side
    height = CEILING_HEIGHT_M * b.num_floors
    facade = perimeter * height
    window_area = facade * b.window_to_wall_ratio
    opaque_facade = facade - window_area
    roof_area = footprint
    walls_area = opaque_facade + roof_area
    room_vol = b.floor_area_m2 * CEILING_HEIGHT_M
    total_internal_area = LAMBDA_AT * b.floor_area_m2
    return Geometry(
        floor_area=b.floor_area_m2,
        walls_area=walls_area,
        window_area=window_area,
        roof_area=roof_area,
        room_vol=room_vol,
        total_internal_area=total_internal_area,
        facade_area=facade,
    )


def effective_wall_u(b: Building, geo: Geometry) -> float:
    """Area-weighted U across opaque facade (walls) and roof."""
    wall_u = WALL_U[b.wall_material]
    roof_u = ROOF_U[b.roof_material]
    opaque_facade = geo.walls_area - geo.roof_area
    return (wall_u * opaque_facade + roof_u * geo.roof_area) / geo.walls_area


def solar_aperture_m2(b: Building, geo: Geometry) -> float:
    """
    Effective solar-collecting area [m2] = window_area * SHGC * shading, PLUS an
    equivalent contribution from the sun-baked roof (absorptance-weighted).
    Multiply by global horizontal irradiance [W/m2] to get solar gains [W].
    """
    shgc = GLAZING[b.glazing]["shgc"]
    window_frac = geo.window_area * shgc * 0.7
    roof_abs = ROOF_SOLAR_ABSORPTANCE[b.roof_material]
    roof_u = ROOF_U[b.roof_material]
    roof_equiv = geo.roof_area * roof_abs * (roof_u / 3.2) * 0.04
    return (window_frac + roof_equiv) * b.solar_aperture_scale


def occupancy_at(hour_of_day: int, b: Building) -> int:
    """Simple public-building occupancy schedule (school/office hours)."""
    if 9 <= hour_of_day < 17:
        return b.occupancy_peak
    if 8 == hour_of_day or 17 == hour_of_day:
        return b.occupancy_peak // 2
    return max(b.occupancy_peak // 20, 0)


def internal_gains_w(hour_of_day: int, b: Building) -> float:
    occ = occupancy_at(hour_of_day, b)
    equip = EQUIPMENT_W_PER_M2 * b.floor_area_m2 if occ > 0 else 0.15 * EQUIPMENT_W_PER_M2 * b.floor_area_m2
    return occ * PERSON_SENSIBLE_W + equip


def build_zone(b: Building, hvac_active: bool):
    """
    Construct an rcbsim 5R1C Zone for the whole building (single representative zone).

    hvac_active=False -> cooling capacity 0 -> indoor temp FREE-FLOATS (outage / no-AC).
    hvac_active=True  -> cooling capacity limited by installed kW (normal operation).
    """
    from rcbsim.building_physics import Zone

    geo = derive_geometry(b)
    u_walls = effective_wall_u(b, geo)
    u_windows = GLAZING[b.glazing]["u"]

    if hvac_active and b.has_hvac:
        max_cool = -abs(b.hvac_capacity_w_per_m2)
    else:
        max_cool = 0.0

    capacitance = b.capacitance_override if b.capacitance_override is not None else MASS_CLASS[b.mass_class]

    zone = Zone(
        window_area=geo.window_area,
        walls_area=geo.walls_area,
        floor_area=geo.floor_area,
        room_vol=geo.room_vol,
        total_internal_area=geo.total_internal_area,
        u_walls=u_walls,
        u_windows=u_windows,
        ach_vent=0.0,
        ach_infl=b.infiltration_ach,
        ventilation_efficiency=0.0,
        thermal_capacitance_per_floor_area=capacitance,
        t_set_heating=12.0,
        t_set_cooling=b.t_set_cooling,
        max_cooling_energy_per_floor_area=max_cool,
        max_heating_energy_per_floor_area=0.0,
    )
    return zone, geo
