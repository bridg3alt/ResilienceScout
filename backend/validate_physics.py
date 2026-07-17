"""
Physics sanity checks for the digital twin (per the plan's Verification section).

Run: python validate_physics.py
Uses REAL Open-Meteo data for the default building location.
These are DIRECTIONAL checks — if any fails, the model is wrong, not just imprecise.
"""
import sys
from dataclasses import replace

import pandas as pd

from resilienceos.building import Building
from resilienceos.twin import simulate
from resilienceos import weather as wx


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f"  ({detail})" if detail else ""))
    return condition


def main():
    b = Building()  # default decennial block, Bangalore coords
    print(f"Fetching Open-Meteo forecast for {b.name} ({b.latitude},{b.longitude})...")
    fc = wx.fetch_forecast(b.latitude, b.longitude, days=3)
    day = wx.hottest_day(fc)
    print(f"Hottest forecast day: {day['time'].dt.date.iloc[0]}, "
          f"outdoor peak {day['temp'].max():.1f}C\n")

    ok = True

    # --- 1. Free-float (no HVAC): thermal lag, stays sane vs outdoor -------------
    free = simulate(b, day, hvac_active=False)
    out_peak = day["temp"].max()
    out_peak_hour = int(day.loc[day["temp"].idxmax(), "hour"])
    in_peak = free["indoor_temp"].max()
    in_peak_hour = int(free.loc[free["indoor_temp"].idxmax(), "hour"])
    print("1) Free-float (no HVAC):")
    ok &= check("indoor peak not wildly above outdoor peak",
                in_peak <= out_peak + 3.0,
                f"indoor {in_peak:.1f}C vs outdoor {out_peak:.1f}C")
    ok &= check("thermal lag: indoor peaks at/after outdoor peak",
                in_peak_hour >= out_peak_hour,
                f"indoor peak {in_peak_hour}h vs outdoor {out_peak_hour}h")
    # Swing damping is a CONDUCTION property — thermal mass damps the transmitted outdoor
    # AIR swing. Solar gain through glazing can legitimately push the free-float indoor swing
    # past the outdoor air swing on a muted-swing (cloudy/monsoon) day, so damping is tested on
    # a solar-zeroed run. Comparing the with-solar swing to raw outdoor air tests the weather,
    # not the mass, and fails whenever the sky is overcast.
    free_nosun = simulate(replace(b, solar_aperture_scale=0.0), day, hvac_active=False)
    nosun_swing = free_nosun["indoor_temp"].max() - free_nosun["indoor_temp"].min()
    out_swing = out_peak - day["temp"].min()
    ok &= check("indoor swing damped vs outdoor swing (conduction only, solar zeroed)",
                nosun_swing <= out_swing + 0.5,
                f"indoor swing {nosun_swing:.1f} vs outdoor {out_swing:.1f}")

    # --- 2. HVAC on bends the curve down ---------------------------------------
    ac = simulate(b, day, hvac_active=True)
    print("\n2) HVAC on:")
    ok &= check("AC lowers peak indoor temp vs free-float",
                ac["indoor_temp"].max() < free["indoor_temp"].max(),
                f"AC peak {ac['indoor_temp'].max():.1f}C vs free {in_peak:.1f}C")
    ok &= check("AC keeps occupied hours near/below setpoint+2",
                ac.loc[ac["occupancy"] > 0, "indoor_temp"].max() <= b.t_set_cooling + 2.5,
                f"max occupied {ac.loc[ac['occupancy']>0,'indoor_temp'].max():.1f}C")
    ok &= check("AC draws cooling electricity", ac["cooling_kw"].max() > 0,
                f"peak {ac['cooling_kw'].max():.1f} kW")

    # --- 3. Heavier thermal mass -> lower, later peak (free-float) --------------
    light = simulate(replace(b, mass_class="light"), day, hvac_active=False)
    heavy = simulate(replace(b, mass_class="heavy"), day, hvac_active=False)
    print("\n3) Thermal mass:")
    ok &= check("heavy mass has lower free-float peak than light",
                heavy["indoor_temp"].max() < light["indoor_temp"].max(),
                f"heavy {heavy['indoor_temp'].max():.1f}C vs light {light['indoor_temp'].max():.1f}C")

    # --- 4. Cool roof -> lower peak (free-float) --------------------------------
    bare = simulate(replace(b, roof_material="rcc_bare"), day, hvac_active=False)
    cool = simulate(replace(b, roof_material="cool_roof"), day, hvac_active=False)
    print("\n4) Cool roof:")
    ok &= check("cool roof lowers free-float peak vs bare RCC",
                cool["indoor_temp"].max() < bare["indoor_temp"].max(),
                f"cool {cool['indoor_temp'].max():.1f}C vs bare {bare['indoor_temp'].max():.1f}C")

    print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    # quick profile dump
    print("\nHourly free-float vs outdoor (spot check):")
    prof = free[["hour", "t_out", "indoor_temp", "heat_index"]].copy()
    with pd.option_context("display.max_rows", 30):
        print(prof.to_string(index=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
