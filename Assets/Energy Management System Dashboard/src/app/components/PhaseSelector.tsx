import { Tabs, TabsList, TabsTrigger } from "./ui/tabs";
import type { Phase } from "../lib/api";
import { ShieldCheck, Waves, Wrench } from "lucide-react";

const PHASES: { id: Phase; label: string; icon: typeof Waves; hint: string }[] = [
  { id: "preparedness", label: "Before the flood", icon: ShieldCheck, hint: "Assessed against a moderate design flood" },
  { id: "active_flood", label: "During the flood", icon: Waves, hint: "Assessed against a severe flood in progress" },
  { id: "recovery", label: "After the flood", icon: Wrench, hint: "Severe flood with the ranked repairs applied — the 'after' state" },
];

interface PhaseSelectorProps {
  phase: Phase;
  onPhaseChange: (p: Phase) => void;
  floodDepthM?: number;
}

/** Drives which panels render and which design flood the backend scores against. */
export function PhaseSelector({ phase, onPhaseChange, floodDepthM }: PhaseSelectorProps) {
  const active = PHASES.find((p) => p.id === phase);

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <Tabs value={phase} onValueChange={(v) => onPhaseChange(v as Phase)}>
        <TabsList className="bg-sidebar-accent/40">
          {PHASES.map(({ id, label, icon: Icon }) => (
            <TabsTrigger key={id} value={id} className="gap-2">
              <Icon className="size-4" />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <div className="text-xs text-sidebar-foreground/70">
        {active?.hint}
        {floodDepthM !== undefined && (
          <span className="ml-1 font-medium text-sidebar-foreground">
            ({floodDepthM.toFixed(1)} m)
          </span>
        )}
      </div>
    </div>
  );
}
