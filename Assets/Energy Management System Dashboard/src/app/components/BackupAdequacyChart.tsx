import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ShelterStatusRow } from "../lib/api";

interface BackupAdequacyChartProps {
  shelters: ShelterStatusRow[];
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  return (
    <div className="bg-background border border-border rounded-lg p-3 shadow-lg max-w-xs">
      <p className="font-medium">{label}</p>
      <p className="text-sm">Available: {row.available.toFixed(1)} h</p>
      <p className="text-sm">Required: {row.required.toFixed(1)} h</p>
      {row.reason && <p className="text-xs text-muted-foreground mt-1">{row.reason}</p>}
    </div>
  );
};

/**
 * Backup hours available vs required, per shelter.
 *
 * Bars are coloured by adequacy against the required window rather than by an absolute
 * threshold: 4 hours is fine for a 3-hour requirement and a failure for a 12-hour one, so the
 * comparison is the only honest way to read the number.
 */
export function BackupAdequacyChart({ shelters }: BackupAdequacyChartProps) {
  const data = shelters.map((s) => ({
    name: s.site_name.replace(/^Block [A-Z] — /, ""),
    available: s.backup_remaining_h,
    required: s.backup_required_h,
    adequate: s.operational,
    reason: s.failure_reason,
  }));

  const required = shelters[0]?.backup_required_h ?? 0;

  return (
    <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
      <CardHeader>
        <CardTitle className="text-sidebar-foreground">Backup adequacy</CardTitle>
        <p className="text-xs text-sidebar-foreground/70">
          Critical-load ride-through with surviving DER vs the {required.toFixed(0)} h required
          window.
        </p>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 12 }} label={{ value: "hours", angle: -90, position: "insideLeft", fontSize: 11 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <ReferenceLine
              y={required}
              stroke="#ef4444"
              strokeDasharray="5 4"
              label={{ value: `required ${required.toFixed(0)}h`, fontSize: 11, fill: "#ef4444", position: "right" }}
            />
            <Bar dataKey="available" name="Backup available (h)" radius={[6, 6, 0, 0]}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.adequate ? "#10b981" : "#ef4444"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
