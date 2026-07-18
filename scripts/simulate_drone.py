"""
STAND-IN for real drone/sensor flood telemetry — NOT the real thing, and NOT meant to be
extended.

This script fakes what a drone or a fixed water-level sensor would do: post a flood-depth reading
to the backend every few seconds. It exists ONLY so the demo can show the live-observation
pathway working end-to-end before any hardware exists. When real telemetry is built, DELETE this
file and point the hardware at POST /api/observations — do not grow this script into a fake data
source. The numbers here are invented on purpose (DATA_IS_PLACEHOLDER stays True on the backend).

Run (backend must be up on 127.0.0.1:8000):
    python scripts/simulate_drone.py
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "http://127.0.0.1:8000/api/observations"
SITE_ID = "decennial_block"

START_M = 0.2          # ankle-deep
END_M = 1.6            # past the "severe" 1.2 m design case, so the shelter visibly fails
STEP_M = 0.1           # rise per reading
INTERVAL_S = 3.0       # seconds between readings


# The datum this fake sensor reports in. It claims above-finished-floor because that is the one
# datum the model can use without a survey constant, which keeps the demo runnable.
#
# REAL hardware will NOT be this convenient: a drone altimeter reports above mean sea level
# ("above_msl_m"), a staff gauge reports above external ground ("above_external_ground_m"). Both
# are REJECTED with 400 until the finished floor level is surveyed (presets.FINISHED_FLOOR_LEVEL_MSL_M
# / GROUND_TO_FLOOR_STEP_M). That rejection is correct and intended — this script stands in for
# the telemetry, not for the survey, and it must not paper over the missing measurement.
DATUM = "above_finished_floor_m"


def post(depth_m: float) -> None:
    body = json.dumps({
        "site_id": SITE_ID,
        "flood_depth_m": round(depth_m, 2),
        "datum": DATUM,
        "source": "simulated_drone",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        json.load(resp)  # drain
    print(f"[simulated_drone] posted flood_depth_m={depth_m:.2f} m for {SITE_ID}")


def main() -> None:
    print(f"Simulated drone rising from {START_M} m to {END_M} m every {INTERVAL_S}s. Ctrl+C to stop.")
    depth = START_M
    try:
        while True:
            try:
                post(depth)
            except urllib.error.URLError as e:
                print(f"[simulated_drone] backend not reachable ({e}); retrying in {INTERVAL_S}s")
            depth += STEP_M
            if depth > END_M:
                depth = END_M  # hold at peak so the failed state stays on screen
            time.sleep(INTERVAL_S)
    except KeyboardInterrupt:
        print("\n[simulated_drone] stopped.")


if __name__ == "__main__":
    main()
