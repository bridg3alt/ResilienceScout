# Deploying to another facility

Deployment is parameterisation, not a rebuild. The distinction matters to anyone estimating
whether this scales beyond one site, so it is stated concretely here.

## What changes per facility — data, entered once

| Input | Effort | Source |
|---|---|---|
| Energy topology — nodes and dependencies | ~1 hour | Single-line diagram or facilities walkthrough |
| Equipment elevations and vertical datum | ~half a day | Tape measure and GNSS fix; no specialist instrument |
| Critical load and distributed-energy nameplate | ~1 hour | Nameplate inspection, institutional records |
| Hazard inputs | Varies | Site high-water evidence, or public weather and flood data |
| Occupancy and population served | Varies | Institutional records, or an area-derived bound |

Every value entered carries a provenance tier — see the Data provenance section of the
[README](../README.md). Unsurveyed inputs remain visible as unsurveyed rather than blending into
the measured ones.

## What stays unchanged — code, shared across all sites

Dependency-graph reasoning and SPOF detection, the adequacy criterion, the recovery prioritization
engine, the CERI framework and its sub-scores, uncertainty reasoning and the provenance registry,
hazard propagation, and every decision surface.

## What is not yet fully separated

Reference-site values currently sit in the parameter module directly rather than in a per-site
configuration. The required operating window is a fixed engineering choice rather than a
per-facility parameter. The CERI weights are global constants not yet shown to transfer across
facility classes.

Factoring these out is the immediate precondition for the second site. It is also the main reason
multi-site deployment is listed in the README as architecture-supports rather than demonstrated.
Measuring the cost of that first real deployment is itself an evaluation task — see
[evaluation.md](evaluation.md).
