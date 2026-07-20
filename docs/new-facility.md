# Deploying to another facility

Deployment is parameterisation, not a rebuild. The distinction matters to anyone estimating
whether this scales beyond one site, so it is stated concretely here.

## What changes per facility — data, entered once

Each facility is a single JSON file under `backend/resilienceos/sites/`. Copy the reference file,
`decennial_block.json`, edit its numbers, and point the backend at it with the `RESILIENCE_SITE`
environment variable (its value is the file's stem, e.g. `RESILIENCE_SITE=my_clinic`). No code
changes.

| Input | JSON key | Effort | Source |
|---|---|---|---|
| Energy nameplate — solar, battery, generator, critical load | `building`, `critical_load` | ~1 hour | Nameplate inspection, institutional records |
| Equipment elevations and vertical datum | `equipment_elevation_m`, `datum` | ~half a day | Tape measure and GNSS fix; no specialist instrument |
| Observed flood marks and scenario depths | `flood` | Varies | Site high-water evidence, or public weather and flood data |
| Occupancy and population served | `pop_served` | Varies | Institutional records, or an area-derived bound |

An elevation measured against external grade or MSL is entered as `{"value": 0.10, "datum":
"above_external_ground_m"}`; the loader converts it to the model's finished-floor datum, so the
file records what was actually surveyed rather than a pre-computed height. Every value entered
carries a provenance tier — see the Data provenance section of the [README](../README.md).
Unsurveyed inputs remain visible as unsurveyed rather than blending into the measured ones.

## What stays unchanged — code, shared across all sites

Dependency-graph reasoning and SPOF detection, the adequacy criterion, the recovery prioritization
engine, the CERI framework and its sub-scores, uncertainty reasoning and the provenance registry,
hazard propagation, and every decision surface.

## What is not yet fully separated

The facility data now lives in a per-site file, but two things remain global. The required
operating window is a fixed engineering choice rather than a per-facility parameter, and the CERI
weights are global constants not yet shown to transfer across facility classes. The provenance
narrative in `presets.py` also still describes the reference site's survey campaign specifically.

None of these blocks a second site; they are the difference between "loads a second facility" and
"is calibrated for a second facility class." Measuring the real cost of that first new deployment
is itself an evaluation task — see [evaluation.md](evaluation.md).
