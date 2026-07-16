import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CeriTrendPoint } from "../lib/api";

interface CERITrendChartProps {
  points: CeriTrendPoint[];
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-background border border-border rounded-lg p-3 shadow-lg">
      <p className="font-medium">{`Flood depth: ${label} m`}</p>
      {payload.map((pld: any, i: number) => (
        <div key={i} className="flex items-center gap-2">
          <div className="w-3 h-1 rounded" style={{ backgroundColor: pld.color }} />
          <span className="text-sm">
            {pld.name}: {pld.value}
          </span>
        </div>
      ))}
    </div>
  );
};

/**
 * CERI across modelled flood severities.
 *
 * The x-axis is flood depth, NOT time. The dashboard this replaces plotted a 24h time series
 * of Math.random() values; there is no historical CERI to plot here because nothing is logged
 * and nothing has been surveyed. A time axis would imply monitoring that does not exist, so
 * the chart shows what the model can actually answer: how readiness degrades as water rises.
 */
export function CERITrendChart({ points }: CERITrendChartProps) {
  const data = points.map((p) => ({
    depth: p.flood_depth_m,
    scenario: p.scenario,
    CERI: p.ceri,
    "Backup duration": p.components.backup_duration,
    "Flood readiness": p.components.flood_readiness,
  }));

  return (
    <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
      <CardHeader>
        <CardTitle className="text-sidebar-foreground">Readiness vs flood severity</CardTitle>
        <p className="text-xs text-sidebar-foreground/70">
          Hazard sweep across modelled scenarios — not a time series. No CERI history is
          recorded.
        </p>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis
              dataKey="depth"
              tick={{ fontSize: 12 }}
              label={{ value: "Flood depth (m)", position: "insideBottom", offset: -2, fontSize: 11 }}
            />
            <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Line type="monotone" dataKey="CERI" stroke="#10b981" strokeWidth={3} dot={{ r: 4 }} />
            <Line type="monotone" dataKey="Backup duration" stroke="#38bdf8" strokeWidth={2} strokeDasharray="4 3" dot={false} />
            <Line type="monotone" dataKey="Flood readiness" stroke="#f59e0b" strokeWidth={2} strokeDasharray="4 3" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
