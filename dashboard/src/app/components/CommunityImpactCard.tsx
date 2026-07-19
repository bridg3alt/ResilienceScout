import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Leaf, Users } from "lucide-react";
import type { ShelterStatusRow } from "../lib/api";

interface CommunityImpactCardProps {
  shelters: ShelterStatusRow[];
}

/**
 * Population served / at risk — the equity headline.
 *
 * Replaces the EMS dashboard's CO2 card. Carbon is kept as a secondary line because it is a
 * genuine co-benefit of the solar capacity, but it is not the point: the reason to power a
 * flood shelter is the people inside it, and leading with tonnes of CO2 would misrepresent
 * what this tool is for.
 */
export function CommunityImpactCard({ shelters }: CommunityImpactCardProps) {
  const total = shelters.reduce((a, s) => a + s.pop_served, 0);
  const covered = shelters.filter((s) => s.operational).reduce((a, s) => a + s.pop_served, 0);
  const atRisk = total - covered;
  const pct = total > 0 ? Math.round((covered / total) * 100) : 0;

  return (
    <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm text-sidebar-foreground flex items-center gap-2">
          <Users className="size-4" /> Community impact
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-sidebar-foreground tabular-nums">
              {covered.toLocaleString()}
            </span>
            <span className="text-sm text-sidebar-foreground/70">
              of {total.toLocaleString()} people keep power
            </span>
          </div>
          <div className="mt-2 h-2 w-full rounded-full bg-red-500/25 overflow-hidden">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          {atRisk > 0 && (
            <div className="mt-2 text-xs text-red-300">
              {atRisk.toLocaleString()} people in shelters that lose power in this scenario.
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 border-t border-sidebar-border/30 pt-3 text-xs text-sidebar-foreground/60">
          <Leaf className="size-3.5" />
          Rooftop solar also displaces grid carbon year-round — a co-benefit, not the objective.
        </div>
      </CardContent>
    </Card>
  );
}
