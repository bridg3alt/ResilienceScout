import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Battery, ShieldAlert, Waves, Zap } from "lucide-react";
import type { CeriComponents } from "../lib/api";

const CARDS: {
  id: keyof CeriComponents;
  name: string;
  fullName: string;
  icon: typeof Zap;
}[] = [
  { id: "energy_readiness", name: "Energy Readiness", fullName: "Stored energy vs critical load", icon: Zap },
  { id: "flood_readiness", name: "Flood Readiness", fullName: "Equipment elevation vs flood line", icon: Waves },
  { id: "backup_duration", name: "Backup Duration", fullName: "Ride-through vs required window", icon: Battery },
  { id: "critical_vulnerabilities", name: "Critical Vulnerabilities", fullName: "Single points of failure", icon: ShieldAlert },
];

/** Sub-score bands. Higher is always better for every CERI component. */
function bandFor(value: number): { label: string; className: string } {
  if (value >= 75) return { label: "strong", className: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" };
  if (value >= 50) return { label: "moderate", className: "bg-amber-500/20 text-amber-300 border-amber-500/40" };
  if (value >= 30) return { label: "at risk", className: "bg-orange-500/20 text-orange-300 border-orange-500/40" };
  return { label: "critical", className: "bg-red-500/20 text-red-300 border-red-500/40" };
}

interface CERISummaryCardsProps {
  components: CeriComponents;
  spofs: string[];
}

export function CERISummaryCards({ components, spofs }: CERISummaryCardsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {CARDS.map(({ id, name, fullName, icon: Icon }) => {
        const value = components[id];
        const band = bandFor(value);
        return (
          <Card
            key={id}
            className="border-sidebar-border/30 shadow-lg hover:shadow-xl transition-all duration-300 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent backdrop-blur-sm hover:scale-[1.02] transform"
          >
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
              <CardTitle className="text-sm font-medium text-sidebar-foreground flex items-center gap-2">
                <Icon className="size-4" />
                {name}
              </CardTitle>
              <Badge variant="outline" className={`text-xs ${band.className}`}>
                {band.label}
              </Badge>
            </CardHeader>
            <CardContent className="pb-4">
              <div className="space-y-3">
                <div className="flex items-baseline gap-1">
                  <div className="text-2xl font-bold text-sidebar-foreground">{value}</div>
                  <div className="text-sm text-sidebar-foreground/70">/ 100</div>
                </div>

                {/* progress rail */}
                <div className="h-1.5 w-full rounded-full bg-sidebar-accent/50 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-sidebar-primary to-sidebar-primary/70 transition-all duration-500"
                    style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
                  />
                </div>

                <div className="text-xs text-sidebar-foreground/70">
                  {id === "critical_vulnerabilities" && spofs.length > 0
                    ? `${spofs.length} single point${spofs.length > 1 ? "s" : ""} of failure: ${spofs.join(", ")}`
                    : fullName}
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
