"""
Tier-2 validation harness — validate the digital twin against REAL measured data.

The single most credibility-defining step (per the project plan): take a few days of
logged indoor-temperature readings from one or two rooms, fetch the matching historical
weather, run the twin, and quantify the error. Then *calibrate* the twin's three unknown
low-data parameters — thermal mass, infiltration, and solar-gain scale — to best fit the
measurements. This turns a "plausible model" into "validated against reality".

Pure numpy + the existing weather/twin modules; no scipy, no keys.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .building import Building, MASS_CLASS
from .twin import simulate
from . import weather as wx


# ---- ingest measurements ------------------------------------------------------
_TIME_HINTS = ("time", "timestamp", "datetime", "date")
_TEMP_HINTS = ("indoor", "temp", "temperature", "reading", "value")


def load_measurements(source) -> pd.DataFrame:
    """
    Accept a CSV path / file-like / DataFrame with a timestamp column and an indoor
    temperature column (tolerant to naming). Returns tidy [time, hour, indoor_measured].
    """
    df = source if isinstance(source, pd.DataFrame) else pd.read_csv(source)
    cols = {c.lower().strip(): c for c in df.columns}

    def _pick(hints, exclude=()):
        for h in hints:
            for low, orig in cols.items():
                if h in low and orig not in exclude:
                    return orig
        return None

    tcol = _pick(_TIME_HINTS)
    vcol = _pick(_TEMP_HINTS, exclude=(tcol,) if tcol else ())
    if tcol is None or vcol is None:
        raise ValueError(
            "CSV must have a timestamp column (e.g. 'time') and an indoor-temperature "
            f"column (e.g. 'indoor_temp'). Found columns: {list(df.columns)}"
        )

    out = pd.DataFrame({
        "time": pd.to_datetime(df[tcol]),
        "indoor_measured": pd.to_numeric(df[vcol], errors="coerce"),
    }).dropna()
    out["hour"] = out["time"].dt.hour
    return out.sort_values("time").reset_index(drop=True)


# ---- run the twin over the measured window ------------------------------------
def predict_over(b: Building, measured: pd.DataFrame, hvac_active: bool = False) -> pd.DataFrame:
    """
    Fetch historical weather covering the measurement window and run the twin.
    hvac_active defaults to False — logs from un-airconditioned rooms are the norm and
    are what actually exercises the passive physics we're validating.
    Returns the twin output frame joined with `indoor_measured` on the hourly timestamp.
    """
    start = measured["time"].min().strftime("%Y-%m-%d")
    end = measured["time"].max().strftime("%Y-%m-%d")
    weather = wx.fetch_history(b.latitude, b.longitude, start, end)
    return _predict_with_weather(b, measured, weather, hvac_active)


def _predict_with_weather(b, measured, weather, hvac_active) -> pd.DataFrame:
    sim = simulate(b, weather, hvac_active=hvac_active)
    m = measured.copy()
    m["time"] = m["time"].dt.floor("h")
    sim = sim.copy()
    sim["time"] = pd.to_datetime(sim["time"]).dt.floor("h")
    return sim.merge(m[["time", "indoor_measured"]], on="time", how="inner")


# ---- error metrics ------------------------------------------------------------
def error_metrics(joined: pd.DataFrame) -> dict:
    """RMSE / MAE / bias between predicted indoor_temp and indoor_measured, plus the
    error in the timing of the daily peak (thermal-lag fidelity)."""
    if joined.empty:
        return {"rmse": None, "mae": None, "bias": None, "peak_lag_err_h": None, "n": 0}
    err = joined["indoor_temp"].to_numpy() - joined["indoor_measured"].to_numpy()
    pred_peak_h = int(joined.loc[joined["indoor_temp"].idxmax(), "hour"])
    meas_peak_h = int(joined.loc[joined["indoor_measured"].idxmax(), "hour"])
    return {
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
        "bias": float(np.mean(err)),
        "peak_lag_err_h": abs(pred_peak_h - meas_peak_h),
        "n": int(len(joined)),
    }


# ---- calibration --------------------------------------------------------------
def calibrate(b: Building, measured: pd.DataFrame, hvac_active: bool = False,
              weather: pd.DataFrame | None = None) -> dict:
    """
    Coarse grid search over the twin's three low-data unknowns, minimising RMSE vs the
    measured indoor curve. Pure numpy — no scipy dependency.

      capacitance_override : light..heavy mass range (J/m2K)
      infiltration_ach     : 0.3 .. 1.5 air changes / h
      solar_aperture_scale : 0.6 .. 1.6

    Returns the calibrated Building plus before/after error, so the UI can show the gain.
    """
    if weather is None:
        start = measured["time"].min().strftime("%Y-%m-%d")
        end = measured["time"].max().strftime("%Y-%m-%d")
        weather = wx.fetch_history(b.latitude, b.longitude, start, end)

    base_metrics = error_metrics(_predict_with_weather(b, measured, weather, hvac_active))

    cap_grid = np.linspace(MASS_CLASS["light"], MASS_CLASS["heavy"], 6)
    ach_grid = np.linspace(0.3, 1.5, 5)
    aper_grid = np.linspace(0.6, 1.6, 5)

    best = {"rmse": np.inf, "params": None}
    history = []
    for cap in cap_grid:
        for ach in ach_grid:
            for aper in aper_grid:
                cand = replace(b, capacitance_override=float(cap),
                               infiltration_ach=float(ach), solar_aperture_scale=float(aper))
                mtr = error_metrics(_predict_with_weather(cand, measured, weather, hvac_active))
                if mtr["rmse"] is None:
                    continue
                history.append({"capacitance": float(cap), "infiltration_ach": float(ach),
                                "solar_aperture_scale": float(aper), "rmse": mtr["rmse"]})
                if mtr["rmse"] < best["rmse"]:
                    best = {"rmse": mtr["rmse"], "params": (float(cap), float(ach), float(aper)),
                            "metrics": mtr}

    cap, ach, aper = best["params"]
    calibrated = replace(b, capacitance_override=cap, infiltration_ach=ach,
                         solar_aperture_scale=aper)
    return {
        "calibrated_building": calibrated,
        "best_params": {"capacitance_override": cap, "infiltration_ach": ach,
                        "solar_aperture_scale": aper},
        "rmse_before": base_metrics["rmse"],
        "rmse_after": best["rmse"],
        "metrics_before": base_metrics,
        "metrics_after": best["metrics"],
        "history": history,
        "weather": weather,
    }


def make_sample_csv(b: Building, days: int = 3, back_days: int = 21,
                    noise_c: float = 0.4) -> str:
    """
    Produce a realistic demo CSV of 'measured' indoor temperatures for THIS building's
    location, so the Validate tab is usable without the operator having their own logger.

    We take a recent historical window, run the twin with slightly perturbed (unknown)
    physical properties, and add sensor noise — exactly the kind of data a cheap logger
    would yield. Re-uploading it lets calibrate() recover those hidden properties.
    """
    import datetime as _dt

    end = _dt.date.today() - _dt.timedelta(days=back_days)
    start = end - _dt.timedelta(days=days - 1)
    weather = wx.fetch_history(b.latitude, b.longitude, start.isoformat(), end.isoformat())

    truth = replace(b, capacitance_override=0.75 * MASS_CLASS[b.mass_class],
                    infiltration_ach=1.1, solar_aperture_scale=1.25)
    sim = simulate(truth, weather, hvac_active=False)
    rng = np.random.default_rng(42)
    indoor = sim["indoor_temp"].to_numpy(dtype=float) + rng.normal(0, noise_c, len(sim))

    out = pd.DataFrame({
        "time": pd.to_datetime(sim["time"]).dt.strftime("%Y-%m-%d %H:%M"),
        "indoor_temp_C": np.round(indoor, 2),
    })
    return out.to_csv(index=False)
