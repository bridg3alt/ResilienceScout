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
          Critical-load ride-through with surviving{" "}
          <span
            className="underline decoration-dotted underline-offset-2"
            title="DER — distributed energy resources: the shelter's own solar, battery and generator."
          >
            DER
          </span>{" "}
          (distributed energy resources) vs the {required.toFixed(0)} h required window.
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

        <LoadRangeNote shelters={shelters} />
      </CardContent>
    </Card>
  );
}

/**
 * The bars are drawn from ONE critical-load figure, but the survey recorded that load twice and
 * the two records disagree (18.0 kW reported vs 20.0 kW itemised). The lower figure is the one in
 * use, which makes every bar the optimistic reading.
 *
 * A chart cannot show that on its own, so it is stated. The case that matters most is when the
 * two ends straddle the required window — the shelter then "passes" only on the flattering record,
 * which is exactly the kind of thing that must not be rounded away into a green bar.
 */
function LoadRangeNote({ shelters }: { shelters: ShelterStatusRow[] }) {
  const withRange = shelters.filter((s) => s.backup_range && !s.backup_range.critical_load_reconciled);
  if (withRange.length === 0) return null;

  const straddling = withRange.filter(
    (s) => s.backup_range!.hours_min < s.backup_required_h && s.operational,
  );
  const [low, high] = withRange[0].backup_range!.critical_load_range_kw;

  return (
    <div
      className={`mt-3 rounded-lg border px-3 py-2 text-xs ${
        straddling.length > 0
          ? "border-amber-500/40 bg-amber-500/10 text-sidebar-foreground/85"
          : "border-sidebar-border/40 text-sidebar-foreground/70"
      }`}
    >
      <span className="font-medium">
        The essential-equipment load was recorded twice and the two records disagree ({low} kW vs{" "}
        {high} kW).{" "}
      </span>
      These bars use the lower figure, so they show the{" "}
      <span className="font-medium">best case</span>. At the higher figure the shelter runs out
      sooner:{" "}
      {withRange.map((s, i) => (
        <span key={s.site_id} className="tabular-nums">
          {i > 0 && "; "}
          {s.backup_range!.hours_min.toFixed(1)}–{s.backup_range!.hours_max.toFixed(1)} h
        </span>
      ))}
      .
      {straddling.length > 0 && (
        <span className="font-medium">
          {" "}
          On the higher figure {straddling.length > 1 ? "these shelters" : "this shelter"} no
          longer meets the required window — so whether it passes depends on an unsettled survey
          record, not on the building.
        </span>
      )}
    </div>
  );
}
