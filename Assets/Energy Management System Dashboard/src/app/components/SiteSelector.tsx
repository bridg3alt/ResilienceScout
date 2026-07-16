import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { cn } from "./ui/utils";
import { Building2, Users } from "lucide-react";
import type { Site } from "../lib/api";

interface SiteSelectorProps {
  sites: Site[];
  selectedId: string;
  onSelect: (id: string) => void;
}

/** Single-select shelter picker (replaces the multi-device selector's device list). */
export function SiteSelector({ sites, selectedId, onSelect }: SiteSelectorProps) {
  return (
    <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm text-sidebar-foreground flex items-center gap-2">
          <Building2 className="size-4" /> Shelter
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {sites.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelect(s.id)}
              aria-pressed={s.id === selectedId}
              className={cn(
                "rounded-xl border px-3 py-2 text-left transition-all",
                s.id === selectedId
                  ? "border-sidebar-primary bg-sidebar-primary/15 shadow-md"
                  : "border-sidebar-border/40 hover:border-sidebar-primary/50 hover:bg-sidebar-accent/40",
              )}
            >
              <div className="text-sm font-medium text-sidebar-foreground">{s.name}</div>
              <div className="flex items-center gap-3 text-xs text-sidebar-foreground/70">
                <span className="flex items-center gap-1">
                  <Users className="size-3" />
                  {s.pop_served.toLocaleString()}
                </span>
                <span>{s.solar_kwp} kWp</span>
                <span>{s.battery_kwh} kWh</span>
              </div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
