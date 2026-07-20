"""
Rooftop solar generation model — uses the REAL array on the decennial block.

Simple, defensible PV model: power scales with irradiance, derated for module
temperature and system losses. Good enough for resilience sizing; swap for pvlib
if higher fidelity is ever needed.
"""
from __future__ import annotations

import pandas as pd

PERFORMANCE_RATIO = 0.80
TEMP_COEFF = -0.004
NOCT_RISE = 25.0


def pv_generation_kw(solar_kwp: float, ghi: float, t_air: float) -> float:
    """Instantaneous PV output [kW] from irradiance [W/m2] and ambient temp [C]."""
    if ghi <= 0 or solar_kwp <= 0:
        return 0.0
    cell_temp = t_air + NOCT_RISE * (ghi / 800.0)
    temp_derate = 1.0 + TEMP_COEFF * max(cell_temp - 25.0, 0.0)
    return max(solar_kwp * (ghi / 1000.0) * PERFORMANCE_RATIO * temp_derate, 0.0)


def add_solar(weather: pd.DataFrame, solar_kwp: float) -> pd.DataFrame:
    """Append an hourly `solar_kw` column to a weather/twin frame."""
    df = weather.copy()
    temp_col = "indoor_temp" if "indoor_temp" in df.columns else "temp"
    df["solar_kw"] = [
        round(pv_generation_kw(solar_kwp, float(g), float(t)), 2)
        for g, t in zip(df["ghi"], df[temp_col])
    ]
    return df
