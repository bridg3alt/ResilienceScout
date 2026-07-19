/**
 * Typed client for the ResilienceScout backend.
 *
 * There are no mock fallbacks here by design. If the backend is down the UI shows an error --
 * it must never silently render invented numbers that look like real ones. The dashboard this
 * was built from displayed Math.random() data indistinguishable from live readings; that is
 * exactly the failure mode this file exists to prevent.
 */

export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export type Phase = "preparedness" | "active_flood" | "recovery";

export type Health = "ok" | "at_risk" | "failed" | "unknown";

export interface Site {
  id: string;
  name: string;
  pop_served: number;
  latitude: number;
  longitude: number;
  solar_kwp: number;
  battery_kwh: number;
  critical_load_kw: number;
}

export interface SitesResponse {
  sites: Site[];
  phases: Phase[];
  flood_scenarios_m: Record<string, number>;
  placeholder: boolean;
  /**
   * Named provenance from backend/resilienceos/presets.py. `unsurveyed` maps each still-invented
   * value to why it matters; `surveyed` maps each measured one to what was recorded. `placeholder`
   * is derived from `unsurveyed` being non-empty, so the three can never disagree.
   */
  unsurveyed?: Record<string, string>;
  surveyed?: Record<string, string>;
}

export interface CeriComponents {
  energy_readiness: number;
  flood_readiness: number;
  backup_duration: number;
  critical_vulnerabilities: number;
}

export interface CeriResponse {
  site_id: string;
  site_name: string;
  phase: Phase;
  flood_depth_m: number;
  score: number;
  score_exact: number;
  band: string;
  components: CeriComponents;
  single_points_of_failure: string[];
  placeholder: boolean;
}

export interface BackupResponse {
  site_id: string;
  site_name: string;
  phase: Phase;
  flood_depth_m: number;
  hours_available: number;
  hours_required: number;
  adequate: boolean;
  surviving_der: { solar_kwp: number; battery_kwh: number; has_generator: boolean };
  failed_equipment: string[];
  placeholder: boolean;
}

export interface GraphNode {
  id: string;
  label: string;
  tier: number;
  elevation_m: number | null;
  health: Health;
  is_power_source: boolean;
}

export interface GraphEdge {
  from: string;
  to: string;
}

export interface DependencyGraphResponse {
  site_id: string;
  site_name: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  phase: Phase;
  flood_depth_m: number;
  single_points_of_failure: string[];
  cascades: Record<string, string[]>;
  placeholder: boolean;
}

export interface ShelterStatusRow {
  site_id: string;
  site_name: string;
  pop_served: number;
  operational: boolean;
  backup_remaining_h: number;
  backup_required_h: number;
  failure_reason: string | null;
  failed_equipment: string[];
  ceri: number;
  band: string;
}

export interface ShelterStatusResponse {
  phase: Phase;
  flood_depth_m: number;
  shelters: ShelterStatusRow[];
  placeholder: boolean;
}

/** A failed asset the search deliberately did NOT include in the minimum repair set. */
export interface DeferredRepair {
  id: string;
  label: string;
  effort_h: number;
}

export interface RecoveryRow {
  site_id: string;
  site_name: string;
  repairs: string[];
  repair_labels: string[];
  repair_effort_h: number;
  /** Failed but not required to re-power the shelter, each with the cost avoided. */
  deferred_repairs: string[];
  deferred: DeferredRepair[];
  /** Effort to repair everything that failed — the comparison the minimum set is beating. */
  full_repair_effort_h: number;
  effort_saved_h: number;
  population_restored: number;
  pop_per_effort_h: number;
  achievable: boolean;
  services_restored: string[];
  all_failed: string[];
  rank: number;
}

export interface RecoveryResponse {
  phase: Phase;
  flood_depth_m: number;
  ranked: RecoveryRow[];
  total_population_restorable: number;
  total_effort_h: number;
  placeholder: boolean;
}

export interface CeriTrendPoint {
  scenario: string;
  flood_depth_m: number;
  ceri: number;
  components: CeriComponents;
}

export interface CeriTrendResponse {
  site_id: string;
  /** "flood_depth_m" -- this is a hazard-severity sweep, NOT a time series. */
  x_axis: string;
  points: CeriTrendPoint[];
  placeholder: boolean;
}

export interface CopilotResponse {
  answer: string;
  sources: string[];
  grounded: boolean;
  llm: string;
  retrieval: string;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body wasn't JSON; keep the status text */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  sites: () => get<SitesResponse>("/api/sites"),
  ceri: (siteId: string, phase: Phase) =>
    get<CeriResponse>(`/api/sites/${siteId}/ceri?phase=${phase}`),
  backup: (siteId: string, phase: Phase) =>
    get<BackupResponse>(`/api/sites/${siteId}/backup?phase=${phase}`),
  dependencyGraph: (siteId: string, phase: Phase) =>
    get<DependencyGraphResponse>(`/api/dependency-graph/${siteId}?phase=${phase}`),
  shelterStatus: (phase: Phase) =>
    get<ShelterStatusResponse>(`/api/shelters/status?phase=${phase}`),
  ceriTrend: (siteId: string) => get<CeriTrendResponse>(`/api/ceri-trend/${siteId}`),
  recovery: (phase: Phase) => post<RecoveryResponse>("/api/recovery/prioritize", { phase }),
  copilot: (siteId: string, phase: Phase, question: string, multiagent = false) =>
    post<CopilotResponse>("/api/copilot", { site_id: siteId, phase, question, multiagent }),
};
