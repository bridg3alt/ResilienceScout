import { useState } from "react";
import { Sidebar } from "./Sidebar";
import { Overview } from "./Overview";
import { DependencyMap } from "./DependencyMap";
import { ShelterStatusBoard } from "./ShelterStatusBoard";
import { RecoveryPrioritization } from "./RecoveryPrioritization";
import { CopilotPanel } from "./CopilotPanel";
import { PhaseSelector } from "./PhaseSelector";
import { DemoDataBanner } from "./DemoDataBanner";
import { ErrorState, LoadingState } from "./States";
import { useApi } from "../hooks/useApi";
import { api, type Phase } from "../lib/api";

function DependencyMapPage({ siteId, phase }: { siteId: string; phase: Phase }) {
  const g = useApi(() => api.dependencyGraph(siteId, phase), [siteId, phase]);
  if (g.error) return <ErrorState message={g.error} onRetry={g.reload} />;
  if (g.loading || !g.data) return <LoadingState label="Building dependency graph…" />;
  return <DependencyMap graph={g.data} />;
}

function ShelterStatusPage({ phase }: { phase: Phase }) {
  const s = useApi(() => api.shelterStatus(phase), [phase]);
  if (s.error) return <ErrorState message={s.error} onRetry={s.reload} />;
  if (s.loading || !s.data) return <LoadingState label="Checking shelter status…" />;
  return <ShelterStatusBoard shelters={s.data.shelters} floodDepthM={s.data.flood_depth_m} />;
}

function RecoveryPage({ phase }: { phase: Phase }) {
  const r = useApi(() => api.recovery(phase), [phase]);
  if (r.error) return <ErrorState message={r.error} onRetry={r.reload} />;
  if (r.loading || !r.data) return <LoadingState label="Ranking repairs…" />;
  return <RecoveryPrioritization recovery={r.data} />;
}

export function Layout() {
  const [currentPage, setCurrentPage] = useState("overview");
  const [phase, setPhase] = useState<Phase>("preparedness");
  const [siteId, setSiteId] = useState<string | null>(null);

  const sites = useApi(() => api.sites(), []);
  const activeSite = siteId ?? sites.data?.sites[0]?.id ?? null;
  const floodDepth = sites.data?.flood_scenarios_m
    ? phase === "preparedness"
      ? sites.data.flood_scenarios_m.moderate
      : sites.data.flood_scenarios_m.severe
    : undefined;

  const renderContent = () => {
    if (sites.error) return <ErrorState message={sites.error} onRetry={sites.reload} />;
    if (sites.loading || !sites.data || !activeSite)
      return <LoadingState label="Loading shelters…" />;

    switch (currentPage) {
      case "dependency":
        return <DependencyMapPage siteId={activeSite} phase={phase} />;
      case "shelters":
        return <ShelterStatusPage phase={phase} />;
      case "recovery":
        return <RecoveryPage phase={phase} />;
      case "copilot":
        return <CopilotPanel siteId={activeSite} phase={phase} />;
      case "overview":
      default:
        return (
          <Overview
            phase={phase}
            sites={sites.data.sites}
            selectedId={activeSite}
            onSelect={setSiteId}
          />
        );
    }
  };

  return (
    <div className="flex h-screen bg-background">
      <div className="flex-shrink-0">
        <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
      </div>
      <main className="flex-1 overflow-auto">
        <div className="p-6 space-y-4">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">ResilienceScout</h1>
            <p className="text-sm text-muted-foreground">
              Flood-preparedness energy readiness for public emergency shelters.
            </p>
          </div>

          <DemoDataBanner placeholder={sites.data?.placeholder} />

          <PhaseSelector phase={phase} onPhaseChange={setPhase} floodDepthM={floodDepth} />

          {renderContent()}
        </div>
      </main>
    </div>
  );
}
