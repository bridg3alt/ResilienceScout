"""
Hazard Simulation Engine — heatwave and power-outage analysis.

Turns twin output into the resilience metrics a facility manager cares about:
safe occupancy hours, hours-until-unsafe during an outage, and how long the
solar + battery can carry critical loads.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

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
