import { Card, CardContent } from "./ui/card";
import { Slider } from "./ui/slider";
import { Button } from "./ui/button";
import { RotateCcw, Waves } from "lucide-react";
import type { HazardReference } from "../lib/api";

/**
 * Drives the water level every panel is scored against.
 *
 * This exists because the project's most decision-relevant finding is a MARGIN, not a state:
 * the generator's alternator sits at 0.85 m above finished floor and the observed 2018 flood
 * reached 0.82 m, so three centimetres separate a shelter that carries its load for 14 hours
 * from one with no backup at all. A fixed set of phase buttons can show either side of that
 * cliff but never the cliff itself. Dragging across it is the argument.
 *
 * Every number rendered here arrives from `/api/sites` (`hazard_reference`). None is written
 * down in the frontend: a surveyed value copied into a component is one that can silently drift
 * from presets.py, which is exactly the failure the provenance registries exist to prevent.
 */

// The slider's upper bound. Covers the severe design flood (1.20 m) and every asset mounted at
// ground level; the roof PV array (9.6 m) sits far off this scale and is never the binding
// constraint, so stretching the axis to reach it would waste the whole range on empty space.
const MAX_DEPTH_M = 2.0;

/** "solar_inverter" -> "Solar inverter". Derived rather than mapped, so asset labels keep a
 *  single source of truth in the backend graph instead of a second copy drifting here. */
function humanize(assetId: string): string {
  const s = assetId.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

interface FloodDepthControlProps {
  depthM: number;
  onDepthChange: (m: number) => void;
  /** Clears the override so the phase's design flood (or a live reading) governs again. */
  onReset: () => void;
  isOverridden: boolean;
  reference?: HazardReference;
}

export function FloodDepthControl({
  depthM,
  onDepthChange,
  onReset,
  isOverridden,
  reference,
}: FloodDepthControlProps) {
  // Assets on the slider's scale, shallowest first.
  //
  // Only the upper end is filtered: an asset far above the axis (the 9.6 m roof array) would pin
  // to the right edge and imply a proximity that isn't real. The LOWER end is deliberately kept.
  // Road access sits at -0.08 m -- below the finished floor -- so it is already under water at
  // every depth on this scale, and it is the asset that cuts generator fuel resupply. Filtering
  // it out for being off-scale would hide the first thing this site loses.
  const assets = Object.entries(reference?.equipment_elevation_m ?? {})
    .filter(([, elev]) => elev <= MAX_DEPTH_M)
    .sort((a, b) => a[1] - b[1]);

  const margin = reference?.at_risk_margin_m;

  // The asset the outcome next turns on: the shallowest one still above the water. This is what
  // makes the readout a margin rather than a status.
  const nextAsset = assets.find(([, elev]) => elev > depthM);
  const distanceToNext = nextAsset ? nextAsset[1] - depthM : null;

  // Inside the survey's own error bars, the model cannot honestly say which side of the asset
  // the water is on -- which is why node_health reports `at_risk` here instead of `ok`.
  const withinNoise =
    distanceToNext !== null && margin !== undefined && distanceToNext <= margin;

  // Clamped, so an asset below the finished floor pins to the left edge instead of rendering
  // off-card at a negative offset. It reads as "already gone", which is exactly what it is.
  const pct = (m: number) => Math.min(100, Math.max(0, (m / MAX_DEPTH_M) * 100));

  return (
    <Card className="border-sidebar-border/40">
      <CardContent className="space-y-3 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Waves className="size-4 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">Flood depth</span>
            <span className="text-xs text-muted-foreground">above finished floor</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-semibold tabular-nums text-foreground">
              {depthM.toFixed(2)} m
            </span>
            {isOverridden && (
              <Button variant="ghost" size="sm" className="gap-1.5" onClick={onReset}>
                <RotateCcw className="size-3.5" />
                Reset
              </Button>
            )}
          </div>
        </div>

        <div className="space-y-1.5">
          <Slider
            value={[depthM]}
            min={0}
            max={MAX_DEPTH_M}
            step={0.01}
            onValueChange={([v]) => onDepthChange(v)}
            aria-label="Flood depth above finished floor, metres"
          />

          {/* Surveyed asset heights, positioned on the same scale as the slider. A reader can
              see WHY the score moves where it moves instead of watching a number jump.

              Labels alternate between two rows. On this site the upper assets land 10% apart
              (distribution panel 80%, solar inverter 90%, comms 100%) while the label text needs
              rather more than 10% of the card to fit, so a single row overlaps into mush exactly
              where the reader is looking. Staggering doubles the room each label gets without
              shrinking the type or dropping any asset. */}
          <div className="relative h-12">
            {reference && (
              <div
                className="absolute top-0 h-2 w-px bg-sky-500/70"
                style={{ left: `${pct(reference.flood_line_m)}%` }}
                title={`Observed August 2018 high-water mark: ${reference.flood_line_m.toFixed(2)} m`}
              />
            )}
            {assets.map(([id, elev], i) => {
              const drowned = elev <= depthM;
              const p = pct(elev);
              // Ticks at the extremes would hang off the card if centred on their own position,
              // so the end labels align inward instead of straddling the edge.
              const anchor = p <= 2 ? "translateX(0)" : p >= 98 ? "translateX(-100%)" : "translateX(-50%)";
              const lower = i % 2 === 1;
              return (
                <div
                  key={id}
                  className="absolute top-0 flex flex-col items-start"
                  style={{ left: `${p}%`, transform: anchor }}
                  title={`${humanize(id)} — ${elev.toFixed(2)} m above finished floor`}
                >
                  <div
                    className={`w-px ${lower ? "h-5" : "h-2"} ${
                      drowned ? "bg-red-500/80" : "bg-muted-foreground/40"
                    }`}
                    style={{ alignSelf: p <= 2 ? "flex-start" : p >= 98 ? "flex-end" : "center" }}
                  />
                  <span
                    className={`mt-0.5 whitespace-nowrap text-[9px] leading-tight ${
                      drowned ? "text-red-500/90" : "text-muted-foreground/70"
                    }`}
                  >
                    {humanize(id)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* The verdict line. Phrased as a distance to the next failure, because that is the
            quantity a facilities manager can actually act on -- and, when the water is inside
            the survey's uncertainty, it says so rather than picking a side. */}
        {distanceToNext !== null && nextAsset && (
          <div
            className={`rounded-md border px-3 py-2 text-xs leading-relaxed ${
              withinNoise
                ? "border-amber-500/40 bg-amber-500/10 text-amber-200"
                : "border-sidebar-border/40 bg-sidebar-accent/20 text-muted-foreground"
            }`}
          >
            <span className="font-medium text-foreground">
              {(distanceToNext * 100).toFixed(0)} cm
            </span>{" "}
            more water and the{" "}
            <span className="font-medium text-foreground">
              {humanize(nextAsset[0]).toLowerCase()}
            </span>{" "}
            goes under.
            {withinNoise && margin !== undefined && (
              <>
                {" "}
                That is inside the survey's own ±{(margin * 100).toFixed(0)} cm uncertainty, so
                the model reports it <span className="font-medium">at risk</span> rather than
                claiming it is safe.
              </>
            )}
          </div>
        )}

        {/* `assets.length > 0` is load-bearing, not defensive noise. Without it, a backend that
            serves no `hazard_reference` produces an empty asset list, no "next asset", and this
            branch would announce that everything has drowned -- inventing a catastrophic reading
            out of missing data, which is the one thing this dashboard must never do. */}
        {assets.length > 0 && distanceToNext === null && (
          <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
            Every surveyed asset on this scale is under water.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
