import { AlertCircle, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { API_BASE } from "../lib/api";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-sidebar-border/30 bg-sidebar-accent/20 px-4 py-6 text-sm text-sidebar-foreground/70">
      <Loader2 className="size-4 animate-spin" />
      {label}
    </div>
  );
}

/**
 * Failures are shown, never swallowed.
 *
 * The dashboard this replaces rendered random numbers that were indistinguishable from real
 * readings. A visible error is strictly better than a plausible-looking fabrication, so there
 * is deliberately no fallback data path here.
 */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const looksOffline = /failed to fetch|networkerror|load failed/i.test(message);
  return (
    <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-4 text-sm text-red-200">
      <div className="flex items-start gap-2">
        <AlertCircle className="size-4 mt-0.5 shrink-0" />
        <div className="space-y-2">
          <div>
            <span className="font-semibold">Could not load data.</span> {message}
          </div>
          {looksOffline && (
            <div className="text-xs text-red-200/80">
              The backend at <code>{API_BASE}</code> is not responding. Start it with:{" "}
              <code>cd backend &amp;&amp; uvicorn resilienceos.api:app --reload</code>
            </div>
          )}
          {onRetry && (
            <Button size="sm" variant="outline" onClick={onRetry}>
              Retry
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
