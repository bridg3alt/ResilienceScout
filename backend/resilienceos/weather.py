"""
Weather engine — public data only, no API key.

Open-Meteo forecast for the "before tomorrow's heatwave" story, and the archive
API for recent history / calibration. Returns a tidy hourly DataFrame.
"""
from __future__ import annotations

import datetime as dt
import httpx
import pandas as pd

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

_HOURLY = [
    "temperature_2m",
    "relative_humidity_2m",
    "shortwave_radiation",
    "cloud_cover",
    "wind_speed_10m",
]

_RENAME = {
    "temperature_2m": "temp",
    "relative_humidity_2m": "rh",
    "shortwave_radiation": "ghi",       # global horizontal irradiance [W/m2]
    "cloud_cover": "cloud",
    "wind_speed_10m": "wind",
}


def _to_frame(payload: dict) -> pd.DataFrame:
    h = payload["hourly"]
    df = pd.DataFrame(h)
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns=_RENAME)
    df["hour"] = df["time"].dt.hour
    return df[["time", "hour"] + list(_RENAME.values())]


def fetch_forecast(lat: float, lon: float, days: int = 3) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(_HOURLY),
        "forecast_days": days,
        "timezone": "auto",
    }
    r = httpx.get(FORECAST_URL, params=params, timeout=30)
    r.raise_for_status()
    return _to_frame(r.json())


def fetch_history(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    """start/end as 'YYYY-MM-DD'. Uses ERA5 reanalysis archive."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(_HOURLY),
        "start_date": start,
        "end_date": end,
        "timezone": "auto",
    }
    r = httpx.get(ARCHIVE_URL, params=params, timeout=60)
    r.raise_for_status()
    return _to_frame(r.json())


def heat_index_c(temp_c: float, rh: float) -> float:
    """
    NOAA Rothfusz heat index in Celsius. Valid when it's hot; below ~27C it just
    returns the air temperature.
    """
    t = temp_c * 9 / 5 + 32  # to Fahrenheit
    if t < 80:
        return temp_c
    hi = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * rh
        - 0.22475541 * t * rh
        - 0.00683783 * t * t
        - 0.05481717 * rh * rh
        + 0.00122874 * t * t * rh
        + 0.00085282 * t * rh * rh
        - 0.00000199 * t * t * rh * rh
    )
    return (hi - 32) * 5 / 9  # back to Celsius


def hottest_day(df: pd.DataFrame) -> pd.DataFrame:
    """Return the 24h slice around the hottest calendar day in the frame."""
    df = df.copy()
    df["date"] = df["time"].dt.date
    peak_date = df.groupby("date")["temp"].max().idxmax()
    return df[df["date"] == peak_date].reset_index(drop=True)
