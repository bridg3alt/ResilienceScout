import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "./ui/sheet";
import type { DependencyGraphResponse, GraphNode, Health } from "../lib/api";

/**
 * Shelter dependency map.
 *
 * Hand-rolled SVG with a fixed layered layout (tier -> column). A force-directed graph library
 * would be a heavy dependency for under ten nodes whose hierarchy is already known, and the
 * tiers carry meaning here (shelter <- panel <- sources <- their own inputs) that a physics
 * simulation would only scramble.
 */

const HEALTH_FILL: Record<Health, string> = {
  ok: "#10b981",
  at_risk: "#f59e0b",
  failed: "#ef4444",
  unknown: "#64748b",
};

const HEALTH_LABEL: Record<Health, string> = {
  ok: "Operational",
  at_risk: "At risk — water is close",
  failed: "Failed — inundated",
  unknown: "Not assessed",
};

const NODE_W = 150;
const NODE_H = 46;
const COL_GAP = 90;
const ROW_GAP = 18;

interface Layout {
  positions: Record<string, { x: number; y: number }>;
  width: number;
  height: number;
}

function layout(nodes: GraphNode[]): Layout {
  const tiers = [...new Set(nodes.map((n) => n.tier))].sort((a, b) => a - b);
  const byTier = new Map<number, GraphNode[]>();
  tiers.forEach((t) => byTier.set(t, nodes.filter((n) => n.tier === t)));

  const tallest = Math.max(...[...byTier.values()].map((g) => g.length));
  const height = tallest * NODE_H + (tallest - 1) * ROW_GAP;
  const positions: Record<string, { x: number; y: number }> = {};

  tiers.forEach((t, col) => {
    const group = byTier.get(t)!;
    const groupH = group.length * NODE_H + (group.length - 1) * ROW_GAP;
    const top = (height - groupH) / 2;
    group.forEach((n, i) => {
      positions[n.id] = { x: col * (NODE_W + COL_GAP), y: top + i * (NODE_H + ROW_GAP) };
    });
  });

  return { positions, width: tiers.length * NODE_W + (tiers.length - 1) * COL_GAP, height };
}

interface DependencyMapProps {
  graph: DependencyGraphResponse;
}

export function DependencyMap({ graph }: DependencyMapProps) {
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const { positions, width, height } = layout(graph.nodes);
  const pad = 16;

  const spofs = new Set(graph.single_points_of_failure);

  return (
    <>
      <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
        <CardHeader>
          <CardTitle className="text-sidebar-foreground">
            Dependency map — {graph.site_name}
          </CardTitle>
          <div className="flex flex-wrap items-center gap-3 text-xs text-sidebar-foreground/70">
            <span>Flood depth {graph.flood_depth_m.toFixed(1)} m. Click a node for detail.</span>
            {(["ok", "at_risk", "failed"] as Health[]).map((h) => (
              <span key={h} className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-full" style={{ background: HEALTH_FILL[h] }} />
                {HEALTH_LABEL[h]}
              </span>
            ))}
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-full ring-2 ring-red-400 ring-offset-1 ring-offset-transparent" />
              ringed = single point of failure
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <svg
              width={width + pad * 2}
              height={height + pad * 2}
              role="img"
              aria-label={`Dependency graph for ${graph.site_name}`}
            >
              <defs>
                <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
                  <path d="M0,0 L0,6 L7,3 z" fill="#64748b" />
                </marker>
              </defs>

              {/* edges: provider -> dependent, drawn right-to-left toward the shelter */}
              {graph.edges.map((e, i) => {
                const from = positions[e.from];
                const to = positions[e.to];
                if (!from || !to) return null;
                const x1 = from.x + pad;
                const y1 = from.y + pad + NODE_H / 2;
                const x2 = to.x + pad + NODE_W;
                const y2 = to.y + pad + NODE_H / 2;
                const mid = (x1 + x2) / 2;
                const failed = graph.nodes.find((n) => n.id === e.from)?.health === "failed";
                return (
                  <path
                    key={i}
                    d={`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`}
                    fill="none"
                    stroke={failed ? "#ef4444" : "#64748b"}
                    strokeOpacity={failed ? 0.8 : 0.45}
                    strokeWidth={failed ? 2 : 1.5}
                    strokeDasharray={failed ? "4 3" : undefined}
                    markerEnd="url(#arrow)"
                  />
                );
              })}

              {/* nodes */}
              {graph.nodes.map((n) => {
                const p = positions[n.id];
                const fill = HEALTH_FILL[n.health];
                const isSpof = spofs.has(n.id);
                return (
                  <g
                    key={n.id}
                    transform={`translate(${p.x + pad}, ${p.y + pad})`}
                    onClick={() => setSelected(n)}
                    style={{ cursor: "pointer" }}
                  >
                    <rect
                      width={NODE_W}
                      height={NODE_H}
                      rx={10}
                      fill={fill}
                      fillOpacity={0.16}
                      stroke={isSpof ? "#f87171" : fill}
                      strokeWidth={isSpof ? 2.5 : 1.5}
                      strokeDasharray={isSpof ? "5 3" : undefined}
                    />
                    <circle cx={14} cy={NODE_H / 2} r={5} fill={fill} />
                    <text x={28} y={NODE_H / 2 + 4} fontSize={12} fill="currentColor" className="fill-sidebar-foreground">
                      {n.label.length > 17 ? `${n.label.slice(0, 16)}…` : n.label}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </CardContent>
      </Card>

      <Sheet open={selected !== null} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent className="w-96">
          {selected && (
            <>
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2">
                  <span className="size-3 rounded-full" style={{ background: HEALTH_FILL[selected.health] }} />
                  {selected.label}
                </SheetTitle>
                <SheetDescription>{HEALTH_LABEL[selected.health]}</SheetDescription>
              </SheetHeader>

              <div className="px-4 space-y-4 text-sm">
                <div className="flex flex-wrap gap-2">
                  {selected.is_power_source && <Badge variant="secondary">Power source</Badge>}
                  {spofs.has(selected.id) && (
                    <Badge variant="destructive">Single point of failure</Badge>
                  )}
                </div>

                {selected.elevation_m !== null && (
                  <div>
                    <div className="text-muted-foreground text-xs">Mounting height</div>
                    <div>
                      {selected.elevation_m.toFixed(2)} m above floor
                      <span className="text-muted-foreground">
                        {" "}
                        vs {graph.flood_depth_m.toFixed(2)} m of water
                      </span>
                    </div>
                  </div>
                )}

                <div>
                  <div className="text-muted-foreground text-xs">
                    Stops working if this fails
                  </div>
                  <div>
                    {graph.cascades[selected.id]?.length
                      ? graph.cascades[selected.id]
                          .map((c) => graph.nodes.find((n) => n.id === c)?.label ?? c)
                          .join(", ")
                      : "Nothing downstream"}
                  </div>
                </div>

                {spofs.has(selected.id) && (
                  <p className="text-xs text-muted-foreground border-l-2 border-red-400/50 pl-3">
                    Every power source reaches the shelter through this node, so losing it alone
                    takes the shelter down regardless of how much generation or storage survives.
                  </p>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}
