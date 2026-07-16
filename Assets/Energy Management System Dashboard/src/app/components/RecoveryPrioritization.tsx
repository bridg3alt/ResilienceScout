import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import type { RecoveryResponse } from "../lib/api";

interface RecoveryPrioritizationProps {
  recovery: RecoveryResponse;
}

/**
 * Post-flood repair order.
 *
 * Rows are shelters, not individual assets: in a severe flood no single repair re-powers
 * anything on its own, so each row carries the minimum SET of repairs that actually restores
 * that shelter, and credits its population only to that complete set.
 */
export function RecoveryPrioritization({ recovery }: RecoveryPrioritizationProps) {
  const { ranked, total_population_restorable, total_effort_h } = recovery;

  if (ranked.length === 0) {
    return (
      <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
        <CardHeader>
          <CardTitle className="text-sidebar-foreground">Recovery prioritisation</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-sidebar-foreground/70">
            No shelter has lost power at this flood depth, so there is nothing to prioritise.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
      <CardHeader>
        <CardTitle className="text-sidebar-foreground">Recovery prioritisation</CardTitle>
        <p className="text-xs text-sidebar-foreground/70">
          Ranked by people restored per repair-hour. {total_population_restorable.toLocaleString()}{" "}
          people restorable across {total_effort_h.toFixed(0)} repair-hours.
        </p>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                <TableHead>Shelter</TableHead>
                <TableHead>Minimum repair set</TableHead>
                <TableHead className="text-right">Effort</TableHead>
                <TableHead className="text-right">People restored</TableHead>
                <TableHead className="text-right">People / hour</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ranked.map((r) => (
                <TableRow key={r.site_id}>
                  <TableCell>
                    <Badge
                      variant={r.rank === 1 ? "default" : "outline"}
                      className="tabular-nums"
                    >
                      {r.rank}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-medium">{r.site_name}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {r.repair_labels.map((l) => (
                        <Badge key={l} variant="secondary" className="text-xs">
                          {l}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.repair_effort_h.toFixed(0)} h
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.population_restored.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right tabular-nums font-medium">
                    {r.pop_per_effort_h.toFixed(1)}
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
