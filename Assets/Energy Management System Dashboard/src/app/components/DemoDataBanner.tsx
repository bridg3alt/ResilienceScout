import { AlertTriangle } from "lucide-react";

/**
 * Renders while the backend reports `placeholder: true`.
 *
 * Every flood depth, equipment elevation and population figure behind this dashboard is
 * currently invented (see backend/resilienceos/presets.py). This banner exists so those
 * numbers can never be mistaken for surveyed data in a demo or a screenshot. It disappears
 * on its own once presets.DATA_IS_PLACEHOLDER is set to False.
 */
export function DemoDataBanner({ placeholder }: { placeholder: boolean | undefined }) {
  if (!placeholder) return null;

  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-amber-200"
    >
      <AlertTriangle className="size-5 shrink-0 mt-0.5" />
      <div className="text-sm">
        <span className="font-semibold">DEMO DATA — NOT SURVEYED.</span>{" "}
        Flood depths, equipment elevations and population-served figures are placeholders, not
        measurements. Scores and repair rankings below demonstrate the method only — they are
        not advice and must not be acted on.
      </div>
    </div>
  );
}
