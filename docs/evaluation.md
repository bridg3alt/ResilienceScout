# Evaluation plan

No evaluation results are reported yet. This document states what would count as evidence for the
claims made in the [README](../README.md), and is the project's near-term work.

## Recovery prioritization correctness

The search returns a minimum-effort repair set for the modelled graph; the open question is
whether the *model* ranks as an engineer would. Construct failure scenarios of varying severity,
collect independent repair orderings from facilities and electrical engineers working blind to the
system output, and report agreement and disagreement cases. Systematic disagreement is the
informative result — it localises whether the objective function or the topology is wrong.

## CERI sensitivity

Perturb the four weights across plausible ranges and report how often band assignment changes and
which sub-scores dominate. A band that flips under small perturbation is not usable for comparison
between facilities, and that rate should be known before CERI is presented as comparable. This is
also the mechanism for calibrating the weights against expert judgement rather than defending
them.

## Digital twin validation

Log indoor temperature across at least one full seasonal swing and report error against 5R1C
predictions — RMSE, bias, and worst-case deviation — under live weather forcing. Required before
the twin is described as validated anywhere in this repository.

## Runtime and scalability

Report end-to-end assessment latency, and how minimum-repair-set search scales with the number of
simultaneously failed assets, including the measured point at which exhaustive enumeration stops
being practical. That number determines when the district-scale work needs approximation methods
rather than a faster machine.

## Uncertainty reasoning

Characterise how interval bounds widen as unmeasured assets accumulate, and identify where they
stop discriminating between operational and non-operational outcomes. The result is a minimum
survey completeness — the point below which a deployment cannot produce actionable output, which
is useful to know before surveying rather than after.

## Multi-site deployment

Instrument the second site: hours to survey, hours to parameterise, and which components required
code changes rather than data entry. This is the direct test of the deployment claim in
[new-facility.md](new-facility.md), and the first deployment is the only unbiased chance to measure
it.

## Operational readiness prediction

The strongest available evidence and the slowest to obtain: where a facility with a recorded CERI
subsequently experiences a hazard event, compare predicted operational state and sustainable hours
against what actually happened. One such case would be worth more than any volume of synthetic
testing.
