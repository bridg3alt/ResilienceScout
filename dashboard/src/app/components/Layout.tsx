import { useEffect, useState } from "react";
import { Sidebar } from "./Sidebar";
import { Overview } from "./Overview";
import { DependencyMap } from "./DependencyMap";
import { ShelterStatusBoard } from "./ShelterStatusBoard";
import { RecoveryPrioritization } from "./RecoveryPrioritization";
import { CopilotPanel } from "./CopilotPanel";
import { PhaseSelector } from "./PhaseSelector";
import { FloodDepthControl } from "./FloodDepthControl";
import { DemoDataBanner } from "./DemoDataBanner";
import { ErrorState, LoadingState } from "./States";
import { useApi } from "../hooks/useApi";
import { api, type Phase } from "../lib/api";

// Live-telemetry pages poll every 3s so they update on their own as flood readings arrive.
const LIVE_POLL_MS = 3000;

/**
 * One plain sentence per page, in the reader's terms rather than the model's.
 *
 * The domain vocabulary here (CERI, SPOF, dependency graph, ride-through) is opaque to anyone who
 * has not read the docs — which includes most people this is ever demoed to. Each line answers
 * "what question does this screen answer?" without assuming any of it.
 */
const PAGE_INTRO: Record<string, { title: string; blurb: string }> = {
  overview: {
    title: "Overview",
    blurb:
      "How ready this shelter is for a flood, scored 0–100. Lower means more likely to lose power when it is needed most.",
  },
  dependency: {
    title: "What depends on what",
    blurb:
      "The wiring behind the score. Grey boxes are equipment; a line means the thing on the left is needed for the thing on the right. Red has drowned at this water level.",
  },
  shelters: {
    title: "Shelter status",
    blurb:
      "Whether each shelter can still run its essential equipment right now, how many hours of backup power is left, and what broke.",
  },
  recovery: {
    title: "What to repair first",
    blurb:
      "After the water goes down: the smallest set of repairs that turns the power back on, ranked by people helped per hour of work — not by what looks worst.",
  },
  copilot: {
    title: "Ask a question",
    blurb:
      "Ask about this shelter in plain English. Answers are grounded in the numbers shown on the other pages, with sources listed.",
  },
};

/**
 * `depthM` is the depth-control override, or undefined when no override is active. It is a
 * fetch dependency on every page so dragging the slider re-scores the whole dashboard.
 */
function DependencyMapPage(
  { siteId, phase, depthM }: { siteId: string; phase: Phase; depthM?: number },
) {
  const g = useApi(
    () => api.dependencyGraph(siteId, phase, depthM),
    [siteId, phase, depthM],
    LIVE_POLL_MS,
  );
  if (g.error) return <ErrorState message={g.error} onRetry={g.reload} />;
  if (g.loading || !g.data) return <LoadingState label="Building dependency graph…" />;
  return <DependencyMap graph={g.data} />;
}

function ShelterStatusPage({ phase, depthM }: { phase: Phase; depthM?: number }) {
  const s = useApi(() => api.shelterStatus(phase, depthM), [phase, depthM], LIVE_POLL_MS);
  if (s.error) return <ErrorState message={s.error} onRetry={s.reload} />;
  if (s.loading || !s.data) return <LoadingState label="Checking shelter status…" />;
  return <ShelterStatusBoard shelters={s.data.shelters} floodDepthM={s.data.flood_depth_m} />;
}

function RecoveryPage({ phase, depthM }: { phase: Phase; depthM?: number }) {
  const r = useApi(() => api.recovery(phase, depthM), [phase, depthM], LIVE_POLL_MS);
  if (r.error) return <ErrorState message={r.error} onRetry={r.reload} />;
  if (r.loading || !r.data) return <LoadingState label="Ranking repairs…" />;
  return <RecoveryPrioritization recovery={r.data} />;
}

export function Layout() {
  const [currentPage, setCurrentPage] = useState("overview");
  const [phase, setPhase] = useState<Phase>("preparedness");
  const [siteId, setSiteId] = useState<string | null>(null);
  // null = no override; the backend then prefers a live observation, else the phase design flood.
  const [depthOverride, setDepthOverride] = useState<number | null>(null);
  const [landed, setLanded] = useState(false);

  const sites = useApi(() => api.sites(), []);
  const activeSite = siteId ?? sites.data?.sites[0]?.id ?? null;
  const reference = sites.data?.hazard_reference;

  const phaseDepth = sites.data?.flood_scenarios_m
    ? phase === "preparedness"
      ? sites.data.flood_scenarios_m.moderate
      : sites.data.flood_scenarios_m.severe
    : undefined;

  // Open at the OBSERVED 2018 high-water mark rather than at a phase default.
  //
  // That is a surveyed measurement (0.82 m, wall staining, main entrance lobby) and it sits 3 cm
  // below the generator's alternator, so the first thing on screen is this building's actual
  // margin: "3 cm more water and the generator goes under -- and that is inside the survey's own
  // uncertainty". Landing on a round design-flood figure instead would open on a number nobody
  // measured, and bury the one finding that makes the case.
  useEffect(() => {
    if (landed || reference?.flood_line_m === undefined) return;
    setDepthOverride(reference.flood_line_m);
    setLanded(true);
  }, [landed, reference?.flood_line_m]);

  const effectiveDepth = depthOverride ?? phaseDepth;

  // Switching phase hands control back to that phase's design flood -- otherwise the tabs would
  // silently stop changing anything once the slider had been touched.
  const handlePhaseChange = (p: Phase) => {
    setPhase(p);
    setDepthOverride(null);
  };

  const renderContent = () => {
    if (sites.error) return <ErrorState message={sites.error} onRetry={sites.reload} />;
    if (sites.loading || !sites.data || !activeSite)
      return <LoadingState label="Loading shelters…" />;

    switch (currentPage) {
      case "dependency":
        return (
          <DependencyMapPage siteId={activeSite} phase={phase} depthM={depthOverride ?? undefined} />
        );
      case "shelters":
        return <ShelterStatusPage phase={phase} depthM={depthOverride ?? undefined} />;
      case "recovery":
        return <RecoveryPage phase={phase} depthM={depthOverride ?? undefined} />;
      case "copilot":
        return (
          <CopilotPanel siteId={activeSite} phase={phase} depthM={depthOverride ?? undefined} />
        );
      case "overview":
      default:
        return (
          <Overview
            phase={phase}
            sites={sites.data.sites}
            selectedId={activeSite}
            onSelect={setSiteId}
            depthM={depthOverride ?? undefined}
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
              Can this shelter keep its power on through a flood — and if not, what do we fix
              first?
            </p>
          </div>

          {/* Per-page orientation, so a first-time reader never has to infer what a screen is for. */}
          {PAGE_INTRO[currentPage] && (
            <div className="border-l-2 border-slate-400/30 pl-3">
              <h2 className="text-sm font-medium text-foreground">
                {PAGE_INTRO[currentPage].title}
              </h2>
              <p className="max-w-3xl text-xs text-muted-foreground">
                {PAGE_INTRO[currentPage].blurb}
              </p>
            </div>
          )}

          <DemoDataBanner
            placeholder={sites.data?.placeholder}
            unsurveyed={sites.data?.unsurveyed}
            surveyed={sites.data?.surveyed}
            derived={sites.data?.derived}
            reported={sites.data?.reported}
            capacityCheck={sites.data?.capacity_check}
          />

          <PhaseSelector
            phase={phase}
            onPhaseChange={handlePhaseChange}
            floodDepthM={effectiveDepth}
          />

          {effectiveDepth !== undefined && (
            <FloodDepthControl
              depthM={effectiveDepth}
              onDepthChange={setDepthOverride}
              onReset={() => setDepthOverride(null)}
              isOverridden={depthOverride !== null}
              reference={reference}
            />
          )}

          {renderContent()}
        </div>
      </main>
    </div>
  );
}
