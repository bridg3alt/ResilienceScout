/** CERI band → badge colour. Shared so severity reads the same everywhere a band appears. */
export const BAND_CLASS: Record<string, string> = {
  Resilient: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  Moderate: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  "At risk": "bg-orange-500/20 text-orange-300 border-orange-500/40",
  Critical: "bg-red-500/20 text-red-300 border-red-500/40",
};
