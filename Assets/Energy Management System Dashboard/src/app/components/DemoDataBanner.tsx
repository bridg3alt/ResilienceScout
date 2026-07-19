import { useState } from "react";
import { Info } from "lucide-react";

/**
 * Renders while the backend reports `placeholder: true`.
 *
 * The site survey has closed most of the model's data gaps — the vertical datum, the 2018 flood
 * mark, six of eight equipment elevations and the DER nameplate are measured. A handful of values
 * are still provisional, and this notice names them rather than implying the whole model is
 * guesswork. Both lists come straight from presets.UNSURVEYED_VALUES / SURVEYED_VALUES, so the
 * copy cannot drift out of step with the data.
 *
 * Persistent and NOT dismissible: the point is that a screenshot can never misrepresent a
 * provisional figure as a surveyed one. Deliberately small and calm (neutral, no warning colour,
 * no alarm icon) — honest, not frightening. It disappears on its own once the last entry in
 * UNSURVEYED_VALUES is replaced with a measurement.
 */
export function DemoDataBanner({
  placeholder,
  unsurveyed,
  surveyed,
}: {
  placeholder: boolean | undefined;
  unsurveyed?: Record<string, string>;
  surveyed?: Record<string, string>;
}) {
  const [open, setOpen] = useState(false);
  if (!placeholder) return null;

  const pending = Object.entries(unsurveyed ?? {});
  const measured = Object.entries(surveyed ?? {});
  const total = pending.length + measured.length;

  // Falls back to the generic wording if the backend predates the provenance registry.
  const label =
    pending.length && total
      ? `${pending.length} of ${total} values still provisional`
      : "Some values still provisional";

  return (
    <div
      role="status"
      className="inline-flex max-w-full flex-col gap-1 rounded-lg border border-slate-400/30 bg-slate-500/10 px-3 py-1.5 text-slate-500 dark:text-slate-300"
    >
      <div className="flex items-center gap-2 text-xs font-medium">
        <span>{label}</span>
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label="Which values are still provisional?"
          className="inline-flex size-4 items-center justify-center rounded-full border border-slate-400/40 hover:bg-slate-500/20"
        >
          <Info className="size-3" />
        </button>
      </div>

      {open && (
        <div className="max-w-md space-y-2 pt-1 text-xs text-slate-500/90 dark:text-slate-300/80">
          {measured.length > 0 && (
            <div>
              <p className="font-medium">Measured on site:</p>
              <ul className="list-disc pl-4">
                {measured.map(([key, why]) => (
                  <li key={key}>{why}</li>
                ))}
              </ul>
            </div>
          )}

          {pending.length > 0 && (
            <div>
              <p className="font-medium">Still provisional — don't rely on these:</p>
              <ul className="list-disc pl-4">
                {pending.map(([key, why]) => (
                  <li key={key}>
                    <span className="font-mono">{key}</span> — {why}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
