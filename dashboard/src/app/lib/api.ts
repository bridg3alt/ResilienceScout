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

/**
 * `ok_reported` is the middle state between measured-dry and never-assessed: the site owner says
 * the asset stays above the water, but no height was ever measured. Kept distinct from `ok` so a
 * verbal assurance is never read off the map as a survey result.
 */
export type Health = "ok" | "ok_reported" | "at_risk" | "failed" | "unknown";

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
  /**
   * Values CONSTRAINED without a site visit — computed from a surveyed input plus a cited
   * standard. Deliberately separate from `surveyed`: a derivation bounds a value, it does not
   * measure it, so these do NOT clear `placeholder` and must never be shown as measurements.
   */
  derived?: Record<string, string>;
  /** Stated by the site owner but not independently verified. Never render as measured. */
  reported?: Record<string, string>;
  /** Per-site check of the claimed population against what the floor area can actually hold. */
  capacity_check?: Record<string, CapacityCheck>;
  /** Surveyed reference marks for the depth control. Served, never hardcoded here. */
  hazard_reference?: HazardReference;
}

/**
 * The surveyed hazard datum, straight from presets.py.
 *
 * `at_risk_margin_m` is 2x the survey's own 1-sigma uncertainty: once the water is within that
 * distance of an asset, the difference between "dry" and "drowned" is inside measurement noise,
 * and the model reports `at_risk` rather than claiming to know. The depth control renders that
 * band rather than a hard line, because a hard line would assert a precision nobody measured.
 */
export interface HazardReference {
  /** Observed August 2018 high-water mark, m above finished floor. */
  flood_line_m: number;
  /** 1-sigma survey uncertainty, m. Null before any survey established one. */
  survey_uncertainty_m: number | null;
  /** ~2 sigma. Half-width of the amber "cannot honestly resolve this" band. */
  at_risk_margin_m: number;
  /** Asset id -> height above finished floor, m. */
  equipment_elevation_m: Record<string, number>;
}

export interface CapacityCheck {
  pop_served_claimed: number;
  area_upper_bound: number;
  exceeds_bound: boolean;
  overstated_by: number;
  /** Human-readable arithmetic + citation, so the ceiling can be rechecked by a reader. */
  basis: string;
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
  /**
   * Adequacy at the pessimistic end of the unreconciled critical load. When this differs from
   * `adequate`, whether the shelter meets its target depends on an unsettled survey record.
   */
  adequate_worst_case?: boolean;
  hours_range?: BackupHoursRange;
  surviving_der: { solar_kwp: number; battery_kwh: number; has_generator: boolean };
  failed_equipment: string[];
  placeholder: boolean;
}

/** Ride-through recomputed at both ends of the disagreeing critical-load records. */
export interface BackupHoursRange {
  critical_load_range_kw: [number, number];
  critical_load_reconciled: boolean;
  hours_min: number;
  hours_max: number;
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
  unassessed_sensitivity?: UnassessedSensitivity;
  placeholder: boolean;
}

/**
 * What the unmeasured elevations are worth. The model can never flood an asset it has no
 * elevation for, so every result assumes those assets survived; this reports whether that
 * assumption actually changes the outcome — i.e. whether the missing survey is load-bearing.
 */
export interface UnassessedSensitivity {
  unassessed: string[];
  powered_if_unassessed_survive: boolean;
  powered_if_unassessed_fail: boolean;
  changes_outcome: boolean;
  spofs_if_unassessed_fail: string[];
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
  /** Ride-through at both ends of the unreconciled critical load. */
  backup_range?: BackupHoursRange;
}

export interface ShelterStatusResponse {
  phase: Phase;
  flood_depth_m: number;
  shelters: ShelterStatusRow[];
  /** False while the two survey records for critical load still disagree. */
  critical_load_reconciled?: boolean;
  placeholder: boolean;
}

/** A failed asset the search deliberately did NOT include in the minimum repair set. */
export interface DeferredRepair {
  id: string;
  label: string;
  effort_h: number;
  /** True when this hours figure is the generic fallback, not a surveyed estimate. */
  effort_estimated?: boolean;
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
  /** Recapped at the floor-area capacity ceiling. null when the site has no surveyed area. */
  population_restored_area_bounded?: number | null;
  /** True when the claimed population exceeds what the floor area can hold. */
  pop_exceeds_area_bound?: boolean;
  /** Repairs in this plan costed from a fallback rather than a surveyed estimate. */
  estimated_effort_repairs?: string[];
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

/**
 * Every scoring endpoint accepts an explicit `flood_depth_m` that overrides the phase's design
 * flood (see `_effective_depth` in api.py). `undefined` means "no override" — the backend then
 * falls back to a live observation if one exists, and only then to the phase guess. Passing the
 * phase default explicitly would look identical but would silently outrank live telemetry, so
 * the parameter is omitted rather than defaulted.
 */
function depthQuery(floodDepthM?: number): string {
  return floodDepthM === undefined ? "" : `&flood_depth_m=${floodDepthM}`;
}

export const api = {
  sites: () => get<SitesResponse>("/api/sites"),
  ceri: (siteId: string, phase: Phase, floodDepthM?: number) =>
    get<CeriResponse>(`/api/sites/${siteId}/ceri?phase=${phase}${depthQuery(floodDepthM)}`),
  backup: (siteId: string, phase: Phase, floodDepthM?: number) =>
    get<BackupResponse>(`/api/sites/${siteId}/backup?phase=${phase}${depthQuery(floodDepthM)}`),
  dependencyGraph: (siteId: string, phase: Phase, floodDepthM?: number) =>
    get<DependencyGraphResponse>(
      `/api/dependency-graph/${siteId}?phase=${phase}${depthQuery(floodDepthM)}`,
    ),
  shelterStatus: (phase: Phase, floodDepthM?: number) =>
    get<ShelterStatusResponse>(`/api/shelters/status?phase=${phase}${depthQuery(floodDepthM)}`),
  ceriTrend: (siteId: string) => get<CeriTrendResponse>(`/api/ceri-trend/${siteId}`),
  recovery: (phase: Phase, floodDepthM?: number) =>
    post<RecoveryResponse>("/api/recovery/prioritize", { phase, flood_depth_m: floodDepthM }),
  copilot: (
    siteId: string,
    phase: Phase,
    question: string,
    multiagent = false,
    floodDepthM?: number,
  ) =>
    post<CopilotResponse>("/api/copilot", {
      site_id: siteId,
      phase,
      question,
      multiagent,
      flood_depth_m: floodDepthM,
    }),
};
