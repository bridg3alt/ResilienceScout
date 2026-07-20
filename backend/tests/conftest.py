"""
Shared fixtures. Weather here is SYNTHETIC on purpose.

The scoring saturation bug this suite pins was weather-dependent: it only appeared when the
live forecast happened to push the peak heat index past the danger line, so a test hitting
Open-Meteo would have passed or failed depending on the day it ran. These frames are
deterministic and offline — the severe case is always severe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def synthetic_day(peak_temp_c: float, min_temp_c: float | None = None) -> pd.DataFrame:
    """
    A 24h frame shaped like the columns weather.fetch_forecast() returns:
    time, hour, temp, rh, ghi, cloud, wind.

    Temperature follows a sinusoid peaking at 15:00; irradiance is a daytime half-sine.
    """
    min_temp_c = min_temp_c if min_temp_c is not None else peak_temp_c - 10.0
    hours = np.arange(24)
    mean = (peak_temp_c + min_temp_c) / 2.0
    amp = (peak_temp_c - min_temp_c) / 2.0
    temp = mean + amp * np.cos((hours - 15) * np.pi / 12.0)
    ghi = np.where((hours >= 6) & (hours <= 18), 950.0 * np.sin((hours - 6) * np.pi / 12.0), 0.0)
    ghi = np.clip(ghi, 0.0, None)
    return pd.DataFrame({
        "time": pd.date_range("2026-05-01", periods=24, freq="h"),
        "hour": hours,
        "temp": temp,
        "rh": np.full(24, 55.0),
        "ghi": ghi,
        "cloud": np.full(24, 20.0),
        "wind": np.full(24, 2.0),
    })


@pytest.fixture
def severe_day() -> pd.DataFrame:
    """
    The regime that broke the old score. Calibrated against the twin, not guessed: a 36 C
    outdoor peak drives the default free-floating Building to a ~58 C indoor heat index and
    ~267 C.h of exceedance — well past HI_DANGER, where the old headroom term clamped to zero.
    """
    return synthetic_day(peak_temp_c=36.0)


@pytest.fixture
def mild_day() -> pd.DataFrame:
    """
    Genuinely mild: a 26 C outdoor peak keeps the indoor heat index at ~31.6 C with zero
    degree-hours of exceedance. (A 31 C peak was tried first and rejected — it still produced
    a 42 C indoor heat index, i.e. above the danger line, so it was not a mild case at all.)
    """
    return synthetic_day(peak_temp_c=26.0)
