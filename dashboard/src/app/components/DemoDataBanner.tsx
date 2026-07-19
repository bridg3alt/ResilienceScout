import { useState } from "react";
import { Info } from "lucide-react";
import type { CapacityCheck } from "../lib/api";

/**
 * Renders while the backend reports `placeholder: true`.
 *
 * Three tiers, in the order a reader needs them:
 *   Measured  — surveyed on site.
 *   Worked out — bounded from a desk using a surveyed input plus a published standard. NOT a
 *                measurement, which is why these keep the notice up rather than clearing it.
 *   Still missing — nobody has measured or bounded these.
 *
 * All three come straight from presets (SURVEYED_VALUES / DERIVED_VALUES / UNSURVEYED_VALUES), so
 * the copy cannot drift out of step with the data.
 *
 * Persistent and NOT dismissible: the point is that a screenshot can never misrepresent a
 * provisional figure as a surveyed one. Deliberately small and calm (neutral, no warning colour,
 * no alarm icon) — honest, not frightening. It disappears on its own once the last entry in
 * UNSURVEYED_VALUES is replaced with a measurement.
 *
 * Wording is aimed at a reader who has never seen the codebase: no variable names in the summary
 * line, and the expanded detail explains what each gap would change rather than only naming it.
 */
export function DemoDataBanner({
  placeholder,
  unsurveyed,
  surveyed,
  derived,
  reported,
  capacityCheck,
}: {
  placeholder: boolean | undefined;
  unsurveyed?: Record<string, string>;
  surveyed?: Record<string, string>;
  derived?: Record<string, string>;
  reported?: Record<string, string>;
  capacityCheck?: Record<string, CapacityCheck>;
}) {
  const [open, setOpen] = useState(false);
  if (!placeholder) return null;

  const pending = Object.entries(unsurveyed ?? {});
  const measured = Object.entries(surveyed ?? {});
  const workedOut = Object.entries(derived ?? {});
  const toldUs = Object.entries(reported ?? {});
  const total = pending.length + measured.length + toldUs.length;

  // Summary counts measured and reported separately — collapsing them would let a verbal
  // assurance inflate the "measured" figure, which is the one number a reader skims.
  const label =
    total
      ? `${measured.length} measured, ${toldUs.length} reported by the college, ${pending.length} still open`
      : "Some values still provisional";

  // Surfaced on its own line because it is a FINDING, not a gap: the claimed population is not
  // merely unmeasured, it exceeds what the surveyed floor area can hold under the cited standard.
  const overCapacity = Object.entries(capacityCheck ?? {}).filter(([, c]) => c.exceeds_bound);

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
          aria-label="Show which values are measured and which are still to confirm"
          className="inline-flex size-4 items-center justify-center rounded-full border border-slate-400/40 hover:bg-slate-500/20"
        >
          <Info className="size-3" />
        </button>
      </div>

      {open && (
        <div className="max-w-xl space-y-3 pt-2 text-xs text-slate-500/90 dark:text-slate-300/80">
          <p className="italic">
            Every number on this dashboard is one of four things. This says which.
          </p>

          {measured.length > 0 && (
            <div>
              <p className="font-medium text-emerald-700 dark:text-emerald-400">
                Measured on site — you can rely on these
              </p>
              <ul className="list-disc space-y-0.5 pl-4">
                {measured.map(([key, why]) => (
                  <li key={key}>{why}</li>
                ))}
              </ul>
            </div>
          )}

          {toldUs.length > 0 && (
            <div>
              <p className="font-medium text-indigo-700 dark:text-indigo-400">
                Reported by the college — believable, but nobody has checked
              </p>
              <ul className="list-disc space-y-0.5 pl-4">
                {toldUs.map(([key, why]) => (
                  <li key={key}>
                    <span className="font-mono">{key}</span> — {why}
                  </li>
                ))}
              </ul>
              <p className="pt-1">
                Stated by staff who run the building, with no survey record behind it. One written
                confirmation by email would move these up to measured.
              </p>
            </div>
          )}

          {workedOut.length > 0 && (
            <div>
              <p className="font-medium text-sky-700 dark:text-sky-400">
                Worked out from measurements + a published standard — not measured directly
              </p>
              <ul className="list-disc space-y-0.5 pl-4">
                {workedOut.map(([key, why]) => (
                  <li key={key}>{why}</li>
                ))}
              </ul>
              <p className="pt-1">
                These narrow a gap without closing it, so the notice stays up. Check the arithmetic
                and the source rather than taking the number on trust.
              </p>
            </div>
          )}

          {pending.length > 0 && (
            <div>
              <p className="font-medium text-amber-700 dark:text-amber-500">
                Still to confirm — don&apos;t base a decision on these
              </p>
              <ul className="list-disc space-y-0.5 pl-4">
                {pending.map(([key, why]) => (
                  <li key={key}>
                    <span className="font-mono">{key}</span> — {why}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {overCapacity.map(([id, c]) => (
            <p key={id} className="rounded border border-amber-500/30 bg-amber-500/10 p-2">
              <span className="font-medium">Known inconsistency: </span>
              the shelter population on record ({c.pop_served_claimed}) is {c.overstated_by} more
              than the building can hold ({c.area_upper_bound} max, from {c.basis}). Repair
              rankings therefore overstate how many people each fix restores.
            </p>
          ))}

          <p className="border-t border-slate-400/20 pt-2">
            This notice clears itself only when the missing values are measured. It cannot be
            switched off in the code.
          </p>
        </div>
      )}
    </div>
  );
}
