import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { CheckCircle2, XCircle } from "lucide-react";
import type { ShelterStatusRow } from "../lib/api";
import { BAND_CLASS } from "../lib/bands";

interface ShelterStatusBoardProps {
  shelters: ShelterStatusRow[];
  floodDepthM: number;
}

/** Active-flood view: which shelters are still carrying load, and why the others are not. */
export function ShelterStatusBoard({ shelters, floodDepthM }: ShelterStatusBoardProps) {
  const up = shelters.filter((s) => s.operational).length;
  const peopleAtRisk = shelters
    .filter((s) => !s.operational)
    .reduce((acc, s) => acc + s.pop_served, 0);

  return (
    <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
      <CardHeader>
        <CardTitle className="text-sidebar-foreground">Shelter status board</CardTitle>
        <p className="text-xs text-sidebar-foreground/70">
          {up} of {shelters.length} shelters operational at {floodDepthM.toFixed(1)} m.{" "}
          {peopleAtRisk > 0 && (
            <span className="text-red-300 font-medium">
              {peopleAtRisk.toLocaleString()} people in shelters without adequate power.
            </span>
          )}
        </p>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Shelter</TableHead>
                <TableHead>Operational</TableHead>
                <TableHead className="text-right">Backup left</TableHead>
                <TableHead className="text-right">People</TableHead>
                <TableHead
                  className="text-right"
                  title="CERI — Climate Energy Readiness Index (0–100): how ready this shelter's energy system is for the flood."
                >
                  CERI
                </TableHead>
                <TableHead>Failure reason</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shelters.map((s) => (
                <TableRow key={s.site_id}>
                  <TableCell className="font-medium">{s.site_name}</TableCell>
                  <TableCell>
                    {s.operational ? (
                      <span className="flex items-center gap-1.5 text-emerald-400">
                        <CheckCircle2 className="size-4" /> Yes
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-red-400">
                        <XCircle className="size-4" /> No
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    <span className={s.operational ? "" : "text-red-400"}>
                      {s.backup_remaining_h.toFixed(1)} h
                    </span>
                    <span className="text-muted-foreground text-xs">
                      {" "}
                      / {s.backup_required_h.toFixed(0)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {s.pop_served.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant="outline" className={BAND_CLASS[s.band] ?? ""} title={s.band}>
                      {s.ceri}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground max-w-xs">
                    {s.failure_reason ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
