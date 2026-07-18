import { Card, CardContent } from "./ui/card";
import { Badge } from "./ui/badge";
import { CERISummaryCards } from "./CERISummaryCards";
import { CERITrendChart } from "./CERITrendChart";
import { BackupAdequacyChart } from "./BackupAdequacyChart";
import { CommunityImpactCard } from "./CommunityImpactCard";
import { SiteSelector } from "./SiteSelector";
import { ErrorState, LoadingState } from "./States";
import { useApi } from "../hooks/useApi";
import { api, type Phase, type Site } from "../lib/api";
import { BAND_CLASS } from "../lib/bands";

interface OverviewProps {
  phase: Phase;
  sites: Site[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export function Overview({ phase, sites, selectedId, onSelect }: OverviewProps) {
  // Poll CERI + status every 3s so the headline readiness tracks live flood readings; the trend
  // is a fixed hazard-severity sweep, so it doesn't poll.
  const ceri = useApi(() => api.ceri(selectedId, phase), [selectedId, phase], 3000);
  const trend = useApi(() => api.ceriTrend(selectedId), [selectedId]);
  const status = useApi(() => api.shelterStatus(phase), [phase], 3000);

  return (
    <div className="space-y-4">
      <SiteSelector sites={sites} selectedId={selectedId} onSelect={onSelect} />

      {ceri.error && <ErrorState message={ceri.error} onRetry={ceri.reload} />}
      {ceri.loading && <LoadingState label="Scoring shelter readiness…" />}

      {ceri.data && (
        <>
          <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
            <CardContent className="flex flex-wrap items-center justify-between gap-4 py-5">
              <div>
                <div className="text-xs uppercase tracking-wide text-sidebar-foreground/60">
                  Climate Energy Readiness Index
                </div>
                <div className="flex items-baseline gap-3">
                  <span className="text-5xl font-bold text-sidebar-foreground tabular-nums">
                    {ceri.data.score}
                  </span>
                  <span className="text-sm text-sidebar-foreground/70">/ 100</span>
                  <Badge variant="outline" className={BAND_CLASS[ceri.data.band] ?? ""}>
                    {ceri.data.band}
                  </Badge>
                </div>
                <div className="mt-1 text-xs text-sidebar-foreground/70">
                  {ceri.data.site_name} · assessed at {ceri.data.flood_depth_m.toFixed(1)} m
                </div>
              </div>
              {status.data && <CommunityImpactCard shelters={status.data.shelters} />}
            </CardContent>
          </Card>

          <CERISummaryCards
            components={ceri.data.components}
            spofs={ceri.data.single_points_of_failure}
          />
        </>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {trend.error && <ErrorState message={trend.error} onRetry={trend.reload} />}
        {trend.data && <CERITrendChart points={trend.data.points} />}

        {status.error && <ErrorState message={status.error} onRetry={status.reload} />}
        {status.data && <BackupAdequacyChart shelters={status.data.shelters} />}
      </div>
    </div>
  );
}
