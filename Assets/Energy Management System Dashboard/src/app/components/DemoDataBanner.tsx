import { useState } from "react";
import { Info } from "lucide-react";

/**
 * Renders while the backend reports `placeholder: true`.
 *
 * Every flood depth, equipment elevation and population figure behind this dashboard is currently
 * invented (see backend/resilienceos/presets.py). This notice exists so those numbers can never
 * be mistaken for surveyed data in a demo or a screenshot — so it is persistent and NOT
 * dismissible. It is deliberately small and calm (neutral, no warning colour, no alarm icon):
 * honest, not frightening. It disappears on its own once presets.DATA_IS_PLACEHOLDER is False.
 */
export function DemoDataBanner({ placeholder }: { placeholder: boolean | undefined }) {
  const [open, setOpen] = useState(false);
  if (!placeholder) return null;

  return (
    <div
      role="status"
      className="inline-flex max-w-full flex-col gap-1 rounded-lg border border-slate-400/30 bg-slate-500/10 px-3 py-1.5 text-slate-500 dark:text-slate-300"
    >
      <div className="flex items-center gap-2 text-xs font-medium">
        <span>Practice data — not measured yet.</span>
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label="What does practice data mean?"
          className="inline-flex size-4 items-center justify-center rounded-full border border-slate-400/40 hover:bg-slate-500/20"
        >
          <Info className="size-3" />
        </button>
      </div>
      {open && (
        <p className="max-w-md text-xs text-slate-500/90 dark:text-slate-300/80">
          The numbers on this page are for demonstration. Nobody has measured them at the real
          building yet, so don't use them to make real decisions.
        </p>
      )}
    </div>
  );
}
