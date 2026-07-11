"""
MILP energy-dispatch optimizer — the "actual innovation" upgrade over the rule engine.

Given the day's weather, the building's DER (solar + battery) and its thermal behaviour,
this schedules — hour by hour — how much to draw from the grid, how much rooftop PV to
self-consume, when to charge/discharge the battery, and how hard to run cooling, so as to
MINIMISE energy cost + thermal discomfort subject to real physical constraints (battery
state-of-charge dynamics, cooling capacity, and islanded operation during an outage).

Thermal coupling is handled with an honest **linear surrogate** of the 5R1C twin:
    indoor_temp[h] ≈ T0[h] − k · cooling_kwh[h]
where T0[h] is the twin's free-float indoor path and k (°C per kWh of electrical cooling)
is estimated empirically from a second twin run with cooling on. This keeps the problem a
tractable MILP while staying anchored to the validated physics — the caveat is stated in
the UI. Falls back to the rule engine if PuLP/CBC is unavailable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .building import Building
from .twin import simulate
from .solar import pv_generation_kw

BATTERY_EFF = 0.92          # round-trip-ish one-way charge/discharge efficiency
COMFORT_PENALTY = 40.0      # INR per degree-hour of discomfort (tunes cool-vs-cost trade)
UNMET_PENALTY = 1e5         # INR per kWh of unmet CRITICAL load (keeps it always feasible)


def tariff_inr_per_kwh(hour: int) -> float:
    """Simple time-of-use tariff: cheap overnight, expensive midday peak."""
    if 22 <= hour or hour < 6:
        return 6.0          # off-peak
    if 10 <= hour < 18:
        return 10.0         # peak
    return 8.0              # shoulder


def _thermal_surrogate(b: Building, day: pd.DataFrame):
    """Return (T0[h], k) — free-float indoor path and °C-drop-per-kWh cooling sensitivity."""
    free = simulate(b, day, hvac_active=False)
    T0 = free["indoor_temp"].to_numpy(dtype=float)

    ac = simulate(b, day, hvac_active=True)
    cool_kw = ac["cooling_kw"].to_numpy(dtype=float)
    drop = free["indoor_temp"].to_numpy(dtype=float) - ac["indoor_temp"].to_numpy(dtype=float)
    active = cool_kw > 0.05
    if active.any():
        k = float(np.median(drop[active] / cool_kw[active]))
    else:
        k = 0.5
    k = max(k, 1e-3)
    cap_kw = float(cool_kw.max()) if cool_kw.max() > 0 else 0.0
    return T0, k, cap_kw, free, ac


def _baseline(b: Building, hours, T0, k, cap_kw, comfort_c, outage) -> dict:
    """
    Fair "unoptimized" baseline on the SAME linear surrogate and SAME outage: cool greedily
    to the comfort setpoint straight from the grid whenever powered, with no PV self-
    consumption, no time-of-use arbitrage and no battery reserved for the outage. During the
    outage the naive operator has nothing stored, so cooling stops and comfort degrades.
    This is exactly the value the optimizer adds — cheaper energy AND ride-through cooling.
    """
    n = len(hours)
    cost = 0.0
    degh = 0.0
    for h in range(n):
        need = max(0.0, (T0[h] - comfort_c) / k)
        cool = min(need, cap_kw)
        if h in outage:                     # no stored energy in the naive plan
            cool = 0.0
        indoor = T0[h] - k * cool
        degh += max(0.0, indoor - comfort_c)
        if h not in outage:
            cost += (cool + b.critical_load_kw) * tariff_inr_per_kwh(int(hours[h]))
    return {"cost_inr": round(cost, 1), "comfort_degh": round(degh, 2)}


def optimize_day(b: Building, day: pd.DataFrame, outage_start: int | None = None,
                 outage_dur: int | None = None, comfort_c: float | None = None) -> dict:
    """
    Solve the day-ahead dispatch MILP. Returns a schedule frame + cost/comfort metrics and
    a comparison against the grid-only baseline. Degrades to the rule engine on any failure.
    """
    comfort_c = comfort_c if comfort_c is not None else (b.t_set_cooling + 1.0)
    T0, k, cap_kw, free, ac = _thermal_surrogate(b, day)

    rows = day.reset_index(drop=True)
    n = len(rows)
    hours = rows["hour"].astype(int).tolist()
    pv_avail = [pv_generation_kw(b.solar_kwp, float(r["ghi"]), float(r["temp"]))
                for _, r in rows.iterrows()]

    outage = set()
    if outage_start is not None and outage_dur is not None:
        outage = {i for i in range(outage_start, min(outage_start + outage_dur, n))}

    base = _baseline(b, hours, T0, k, cap_kw, comfort_c, outage)

    try:
        schedule = _solve_milp(b, n, hours, pv_avail, T0, k, cap_kw, comfort_c, outage)
        method = "MILP (PuLP/CBC)"
    except Exception as e:  # no solver / infeasible / import error -> rule engine
        return _fallback(b, day, free, base, comfort_c, repr(e))

    opt_cost = float((schedule["grid_kw"] * schedule["tariff"]).sum())
    opt_degh = float(np.clip(schedule["indoor_temp"] - comfort_c, 0, None).sum())
    return {
        "method": method,
        "comfort_c": comfort_c,
        "schedule": schedule,
        "cost_inr": round(opt_cost, 1),
        "comfort_degh": round(opt_degh, 2),
        "baseline": base,
        "cost_saved_inr": round(base["cost_inr"] - opt_cost, 1),
        "comfort_gain_degh": round(base["comfort_degh"] - opt_degh, 2),
        "surrogate_k": round(k, 3),
        "outage_hours": sorted(outage),
    }


def _solve_milp(b, n, hours, pv_avail, T0, k, cap_kw, comfort_c, outage) -> pd.DataFrame:
    import pulp

    cap_kwh = max(b.battery_kwh, 0.0)
    p_batt = cap_kwh                     # 1C charge/discharge power limit [kW]
    soc0 = 0.5 * cap_kwh                 # start half-charged

    m = pulp.LpProblem("resilienceos_dispatch", pulp.LpMinimize)
    grid = [pulp.LpVariable(f"grid_{h}", lowBound=0) for h in range(n)]
    pv_used = [pulp.LpVariable(f"pv_{h}", lowBound=0, upBound=pv_avail[h]) for h in range(n)]
    chg = [pulp.LpVariable(f"chg_{h}", lowBound=0, upBound=p_batt) for h in range(n)]
    dis = [pulp.LpVariable(f"dis_{h}", lowBound=0, upBound=p_batt) for h in range(n)]
    soc = [pulp.LpVariable(f"soc_{h}", lowBound=0, upBound=cap_kwh) for h in range(n)]
    cool = [pulp.LpVariable(f"cool_{h}", lowBound=0, upBound=cap_kw) for h in range(n)]
    slack = [pulp.LpVariable(f"slack_{h}", lowBound=0) for h in range(n)]   # discomfort °C
    unmet = [pulp.LpVariable(f"unmet_{h}", lowBound=0) for h in range(n)]   # unserved load kW

    for h in range(n):
        demand = cool[h] + b.critical_load_kw
        # energy balance: supply == demand + charging  (unmet relaxes it if truly starved)
        m += pv_used[h] + dis[h] + grid[h] + unmet[h] == demand + chg[h]
        # battery state of charge dynamics (1-hour steps)
        prev = soc[h - 1] if h > 0 else soc0
        m += soc[h] == prev + BATTERY_EFF * chg[h] - dis[h] / BATTERY_EFF
        # comfort: indoor = T0 - k*cool must sit at/below comfort + slack
        m += T0[h] - k * cool[h] <= comfort_c + slack[h]
        if h in outage:
            m += grid[h] == 0            # islanded: no grid during the outage window

    total_cost = pulp.lpSum(grid[h] * tariff_inr_per_kwh(hours[h]) for h in range(n))
    total_discomfort = COMFORT_PENALTY * pulp.lpSum(slack)
    total_unmet = UNMET_PENALTY * pulp.lpSum(unmet)
    m += total_cost + total_discomfort + total_unmet

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"solver status: {pulp.LpStatus[status]}")

    val = lambda v: float(v.value() or 0.0)
    return pd.DataFrame({
        "hour": hours,
        "tariff": [tariff_inr_per_kwh(h) for h in hours],
        "pv_avail_kw": [round(x, 2) for x in pv_avail],
        "grid_kw": [round(val(grid[h]), 2) for h in range(n)],
        "pv_used_kw": [round(val(pv_used[h]), 2) for h in range(n)],
        "batt_charge_kw": [round(val(chg[h]), 2) for h in range(n)],
        "batt_discharge_kw": [round(val(dis[h]), 2) for h in range(n)],
        "soc_kwh": [round(val(soc[h]), 2) for h in range(n)],
        "cooling_kw": [round(val(cool[h]), 2) for h in range(n)],
        "unmet_kw": [round(val(unmet[h]), 2) for h in range(n)],
        "indoor_temp": [round(T0[h] - k * val(cool[h]), 2) for h in range(n)],
    })


def _fallback(b, day, free, base, comfort_c, reason) -> dict:
    """MILP unavailable — return a rule-engine dispatch so the app never breaks."""
    from .engine import operational_plan
    from .hazard import analyze_heatwave
    hw = analyze_heatwave(b, day, hvac_active=False)
    return {
        "method": "rule-engine (fallback)",
        "comfort_c": comfort_c,
        "reason": reason,
        "schedule": None,
        "plan": operational_plan(b, day, hw),
        "baseline": base,
    }
