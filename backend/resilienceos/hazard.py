"""
Hazard Simulation Engine — heatwave and power-outage analysis.

Turns twin output into the resilience metrics a facility manager cares about:
safe occupancy hours, hours-until-unsafe during an outage, and how long the
solar + battery can carry critical loads.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from . import presets
from .building import Building
from .twin import simulate
from .solar import pv_generation_kw

# Habitability thresholds on the heat index [C] (NOAA / NDMA-style bands)
HI_CAUTION = 32.0        # occupants uncomfortable; vulnerable at risk
HI_DANGER = 39.0         # unsafe for continued occupancy


@dataclass
class HeatwaveResult:
    peak_indoor: float
    peak_heat_index: float
    peak_outdoor: float
    safe_occupancy_hours: int          # occupied hours with HI < caution
    occupied_hours: int
    hours_above_caution: int
    hours_above_danger: int
    exceedance_degh: float              # degree-hours of heat index above caution [C.h]
    profile: list                       # hourly dicts for charting

    def to_dict(self):
        d = self.__dict__.copy()
        return d


@dataclass
class OutageResult:
    start_hour: int
    duration_h: int
    hours_until_unsafe: float | None    # from outage start until HI crosses caution
    peak_indoor_during: float
    backup_hours: float                 # how long solar+battery carry critical load
    critical_load_kw: float
    profile: list

    def to_dict(self):
        return self.__dict__.copy()


def degree_hours_above(heat_index: pd.Series, threshold: float = HI_CAUTION) -> float:
    """
    Cumulative degree-hours of heat index above `threshold` [C.h].

    Unlike a peak-only metric this is continuous and unbounded: it responds to BOTH how hot
    it gets and for how long, and it never saturates. That matters because the peak-based
    headroom score used to clamp to zero above the danger line, making the model blind to
    real improvements in exactly the dangerous regime it exists to analyse.
    """
    return float((heat_index - threshold).clip(lower=0).sum())


@dataclass
class FloodResult:
    flood_depth_m: float
    failed_equipment: list           # asset names inundated at this depth
    surviving_der: dict              # what the shelter still has after the water
    backup_hours: float              # critical-load ride-through with the surviving DER
    required_backup_h: float
    operational: bool                # can it carry critical load for the required window?
    failure_reason: str | None
    placeholder: bool                # True while presets data is unsurveyed

    def to_dict(self):
        return self.__dict__.copy()


def analyze_flood(
    b: Building,
    day: pd.DataFrame,
    flood_depth_m: float,
    start_hour: int = 14,
    repaired: frozenset[str] = frozenset(),
) -> FloodResult:
    """
    Flood hazard: water above an asset's mounting height takes that asset offline, and the
    shelter must then carry its critical load on whatever DER survived.

    Deliberately REUSES `backup_duration_h()` unchanged rather than reimplementing the energy
    balance: the flood only decides WHICH resources exist, and the existing solar+battery model
    decides how long they last. Roof PV panels survive but their ground-level inverter usually
    does not, which is why elevation is tracked per-asset.

    `repaired` names assets that have been restored (the post-flood "recovery" phase): they are
    treated as dry, so their capability comes back and the shelter is re-scored on the mended
    resource set. Empty by default, so every existing caller is unaffected.
    """
    failed = [a for a in presets.flooded_equipment(flood_depth_m) if a not in repaired]

    # Apply each drowned asset's effect to a copy of the Building, then let the existing
    # energy-balance model run against the degraded resource set.
    effects: dict = {}
    for asset in failed:
        effects.update(presets.EQUIPMENT_EFFECT.get(asset, {}))
    degraded = replace(b, **effects) if effects else b

    backup = backup_duration_h(degraded, day, start_hour)
    required = presets.REQUIRED_BACKUP_H
    operational = backup >= required

    reason = None
    if not operational:
        if "transformer" in failed:
            reason = f"Transformer inundated at {flood_depth_m:.1f} m; grid supply lost"
        elif failed:
            reason = f"{', '.join(failed)} inundated; {backup:.1f}h backup vs {required:.0f}h required"
        else:
            reason = f"Insufficient stored energy: {backup:.1f}h vs {required:.0f}h required"

    return FloodResult(
        flood_depth_m=flood_depth_m,
        failed_equipment=failed,
        surviving_der={
            "solar_kwp": degraded.solar_kwp,
            "battery_kwh": degraded.battery_kwh,
            "has_generator": degraded.has_generator,
        },
        backup_hours=backup,
        required_backup_h=required,
        operational=operational,
        failure_reason=reason,
        placeholder=presets.DATA_IS_PLACEHOLDER,
    )


def analyze_heatwave(b: Building, day: pd.DataFrame, hvac_active: bool = True) -> HeatwaveResult:
    sim = simulate(b, day, hvac_active=hvac_active)
    occ = sim[sim["occupancy"] > 0]
    return HeatwaveResult(
        peak_indoor=float(sim["indoor_temp"].max()),
        peak_heat_index=float(sim["heat_index"].max()),
        peak_outdoor=float(sim["t_out"].max()),
        safe_occupancy_hours=int((occ["heat_index"] < HI_CAUTION).sum()),
        occupied_hours=int(len(occ)),
        hours_above_caution=int((sim["heat_index"] >= HI_CAUTION).sum()),
        hours_above_danger=int((sim["heat_index"] >= HI_DANGER).sum()),
        exceedance_degh=round(degree_hours_above(sim["heat_index"]), 2),
        profile=sim.assign(time=sim["time"].astype(str)).to_dict("records"),
    )


def backup_duration_h(b: Building, day: pd.DataFrame, start_hour: int) -> float:
    """
    Energy-balance backup: battery + solar generated during the outage serving the
    critical load. Returns hours the critical load can be sustained from outage start.
    """
    stored = b.battery_kwh
    load = b.critical_load_kw
    if load <= 0:
        return float("inf")
    hours = 0.0
    rows = day.reset_index(drop=True)
    for i in range(start_hour, len(rows)):
        w = rows.iloc[i]
        solar = pv_generation_kw(b.solar_kwp, float(w["ghi"]), float(w["temp"]))
        net = solar - load                # kW into(+)/out of(-) storage this hour
        if net >= 0:
            stored = min(stored + net, b.battery_kwh)  # can't exceed capacity
            hours += 1
        else:
            deficit = -net                # kW that must come from battery
            if stored >= deficit:
                stored -= deficit
                hours += 1
            else:
                hours += stored / deficit  # partial final hour
                stored = 0.0
                break
    return round(hours, 1)


def analyze_outage(
    b: Building, day: pd.DataFrame, start_hour: int, duration_h: int
) -> OutageResult:
    sim = simulate(
        b, day, hvac_active=True,
        outage_start_hour=start_hour, outage_duration_h=duration_h,
    )
    during = sim.iloc[start_hour:start_hour + duration_h]

    hours_until_unsafe = None
    for k, (_, row) in enumerate(during.iterrows()):
        if row["heat_index"] >= HI_CAUTION:
            hours_until_unsafe = float(k)
            break

    return OutageResult(
        start_hour=start_hour,
        duration_h=duration_h,
        hours_until_unsafe=hours_until_unsafe,
        peak_indoor_during=float(during["indoor_temp"].max()),
        backup_hours=backup_duration_h(b, day, start_hour),
        critical_load_kw=b.critical_load_kw,
        profile=sim.assign(time=sim["time"].astype(str)).to_dict("records"),
    )
