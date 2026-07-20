import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Wrench, ArrowRight } from "lucide-react";
import type { RecoveryResponse, RecoveryRow } from "../lib/api";

interface RecoveryPrioritizationProps {
  recovery: RecoveryResponse;
}

/**
 * Post-flood repair order.
 *
 * The unit of decision is the minimum SET of repairs that actually re-powers a shelter — in a
 * severe flood no single repair does it alone. The interesting half is what the search chose NOT
 * to repair: a flooded transformer is a real failure that can be both the most expensive job on
 * the list and worth nothing, because every source is wired through the distribution panel.
 * Showing the deferred assets WITH their cost is what makes that an argument the reader can
 * check rather than an assertion.
 *
 * With several shelters the rows also rank against each other by people-restored-per-repair-hour;
 * with one that comparison is meaningless, so it is hidden rather than shown as a lone "#1".
 */
export function RecoveryPrioritization({ recovery }: RecoveryPrioritizationProps) {
  const { ranked, total_population_restorable, total_effort_h } = recovery;
  const comparing = ranked.length > 1;

  if (ranked.length === 0) {
    return (
      <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
        <CardHeader>
          <CardTitle className="text-sidebar-foreground">
            No repairs needed at this water level
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-sidebar-foreground/70">
          <p>
            Equipment has flooded at {recovery.flood_depth_m.toFixed(2)} m, but a power source
            stayed dry — so the shelter never lost power and there is nothing to restore.
          </p>
          <p className="text-xs">Raise the flood depth above the generator to rank real repairs.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
      <CardHeader>
        <CardTitle className="text-sidebar-foreground">
          {comparing ? "Repair plan — which shelter first" : "Repair plan"}
        </CardTitle>
        <p className="text-xs text-sidebar-foreground/70">
          {comparing
            ? `Ranked by people restored per repair-hour. ${total_population_restorable.toLocaleString()} people restorable across ${total_effort_h.toFixed(0)} repair-hours.`
            : "The smallest set of repairs that turns the power back on — and what it is safe to leave until later."}
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {ranked.map((r) => (
          <RepairArgument key={r.site_id} row={r} comparing={comparing} />
        ))}
      </CardContent>
    </Card>
  );
}

function RepairArgument({ row, comparing }: { row: RecoveryRow; comparing: boolean }) {
  return (
    <div className="space-y-3">
      {comparing && (
        <div className="flex items-center gap-2">
          <Badge variant={row.rank === 1 ? "default" : "outline"} className="tabular-nums">
            #{row.rank}
          </Badge>
          <span className="text-sm font-medium text-sidebar-foreground">{row.site_name}</span>
          <span className="text-xs text-sidebar-foreground/60 tabular-nums">
            {row.pop_per_effort_h.toFixed(1)} people/hour
          </span>
        </div>
      )}

      <div className="rounded-xl border border-sidebar-primary/40 bg-sidebar-primary/10 px-4 py-3">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-sidebar-foreground/70">
          <Wrench className="size-3.5" /> Do this first
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {row.repair_labels.map((l) => (
            <Badge key={l} className="text-xs">
              {l}
            </Badge>
          ))}
          <span className="text-sm font-semibold text-sidebar-foreground tabular-nums">
            {row.repair_effort_h.toFixed(0)} h total
          </span>
        </div>
        {row.services_restored.length > 0 && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-sidebar-foreground/70">
            <ArrowRight className="size-3" />
            restores {row.services_restored.join(", ")}
          </div>
        )}
      </div>

      {row.deferred.length > 0 && (
        <div className="rounded-xl border border-sidebar-border/40 px-4 py-3">
          <div className="text-xs uppercase tracking-wide text-sidebar-foreground/60">
            Also flooded — but not needed to restore power
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {row.deferred.map((d) => (
              <Badge key={d.id} variant="outline" className="text-xs tabular-nums">
                {d.label} · {d.effort_h.toFixed(0)} h
              </Badge>
            ))}
          </div>
          <p className="mt-2 text-xs text-sidebar-foreground/60">
            These still need fixing eventually, but the shelter is powered without them — so
            they do not belong in the first repair window.
          </p>
        </div>
      )}

      {row.effort_saved_h > 0 && (
        <p className="text-xs text-sidebar-foreground/70">
          Repairing everything that flooded would take{" "}
          <span className="tabular-nums font-medium">{row.full_repair_effort_h.toFixed(0)} h</span>.
          Working out what actually carries the power finds the{" "}
          <span className="tabular-nums font-medium">{row.repair_effort_h.toFixed(0)} h</span>{" "}
          that matters — <span className="tabular-nums font-medium">{row.effort_saved_h.toFixed(0)} h</span>{" "}
          deferred without leaving anyone in the dark.
        </p>
      )}

      {!row.achievable && (
        <p className="text-xs text-destructive">
          No repair set restores power at this depth — the shelter cannot be brought back until
          the water drops.
        </p>
      )}

      {(row.pop_exceeds_area_bound || (row.estimated_effort_repairs?.length ?? 0) > 0) && (
        <div className="space-y-1.5 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-xs text-sidebar-foreground/80">
          <div className="uppercase tracking-wide text-sidebar-foreground/60">
            Treat with caution
          </div>

          {row.pop_exceeds_area_bound && (
            <p>
              This says{" "}
              <span className="font-medium tabular-nums">
                {row.population_restored.toLocaleString()} people
              </span>{" "}
              restored, but the building&apos;s measured floor area only allows{" "}
              <span className="font-medium tabular-nums">
                {row.population_restored_area_bounded?.toLocaleString()}
              </span>{" "}
              (Kerala relief standard, 3.5 m² per person). Nobody has counted the real figure, so
              the people-per-hour number above is <span className="font-medium">too high</span>.
            </p>
          )}

          {(row.estimated_effort_repairs?.length ?? 0) > 0 && (
            <p>
              Repair time for{" "}
              <span className="font-medium">{row.estimated_effort_repairs?.join(", ")}</span> is a
              generic fallback, not an estimate from the maintenance team — so this plan&apos;s
              total hours, and its position in the ranking, partly rest on a guess.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
