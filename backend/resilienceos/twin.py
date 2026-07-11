"""
Physics-informed Digital Twin — hour-by-hour 5R1C simulation.

Wraps rcbsim's ISO-13790 Zone (ETH Zürich, MIT). Given a Building and an hourly
weather DataFrame, it marches the thermal-mass temperature forward and reads out
the indoor air temperature, heat index, and cooling electricity each hour.

Cite in research: Jayathissa et al., "Optimising building net energy demand with
dynamic BIPV shading," Applied Energy 202 (2017) — ETH Architecture & Building Systems.
"""
from __future__ import annotations

import pandas as pd

from .building import Building, build_zone, internal_gains_w, occupancy_at
from .weather import heat_index_c


def simulate(
    building: Building,
    weather: pd.DataFrame,
    hvac_active: bool = True,
    outage_start_hour: int | None = None,
    outage_duration_h: int | None = None,
    t_initial: float | None = None,
) -> pd.DataFrame:
    """
    Run the twin over the weather frame.

    outage_start_hour / outage_duration_h: if given, HVAC is forced OFF (free-float)
    for that window even if the building has AC — this is the power-outage scenario.

    Returns a DataFrame aligned with `weather` plus:
      indoor_temp, heat_index, cooling_kw, hvac_on, occupancy, powered
    """
    zone_hvac, geo = build_zone(building, hvac_active=True)
    zone_free, _ = build_zone(building, hvac_active=False)

    # Solar aperture: multiply GHI [W/m2] to get solar gains [W]
    from .building import solar_aperture_m2
    aperture = solar_aperture_m2(building, geo)

    t_m_prev = t_initial if t_initial is not None else float(weather["temp"].iloc[0])
    rows = []

    for i, w in weather.reset_index(drop=True).iterrows():
        hour = int(w["hour"])
        occ = occupancy_at(hour, building)
        ig = internal_gains_w(hour, building)
        sg = aperture * float(w["ghi"])
        t_out = float(w["temp"])

        # Is the building drawing grid/backup power this hour?
        in_outage = (
            outage_start_hour is not None
            and outage_duration_h is not None
            and outage_start_hour <= i < outage_start_hour + outage_duration_h
        )
        powered = not in_outage
        use_hvac = hvac_active and building.has_hvac and powered

        zone = zone_hvac if use_hvac else zone_free
        # keep both zones' mass temps in sync so switching modes is continuous
        zone.solve_energy(ig, sg, t_out, t_m_prev)
        t_m_prev = zone.t_m_next

        indoor = zone.t_air
        cooling_kw = getattr(zone, "cooling_sys_electricity", 0.0) / 1000.0
        rows.append(
            {
                "time": w["time"],
                "hour": hour,
                "t_out": t_out,
                "rh": float(w["rh"]),
                "ghi": float(w["ghi"]),
                "indoor_temp": round(indoor, 2),
                "heat_index": round(heat_index_c(indoor, float(w["rh"])), 2),
                "cooling_kw": round(cooling_kw, 2),
                "hvac_on": use_hvac,
                "occupancy": occ,
                "powered": powered,
            }
        )

    return pd.DataFrame(rows)
