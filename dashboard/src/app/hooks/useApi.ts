import { useCallback, useEffect, useState } from "react";

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Fetch-on-mount hook with explicit loading/error states.
 *
 * `error` is surfaced rather than swallowed: a failed request must be visible, never quietly
 * replaced with placeholder-looking data.
 *
 * `deps` drives refetching (e.g. the selected site or phase). Stale responses are discarded
 * so a slow earlier request can't overwrite a newer one.
 *
 * `pollMs` (optional) enables live updates: every `pollMs` ms the data is refetched SILENTLY —
 * `loading` is never toggled and errors from a poll are swallowed — so panels update in place
 * with no spinner flicker. This is how the dashboard tracks live flood telemetry with zero
 * clicks. The initial deps-driven fetch still shows loading/errors normally.
 */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[], pollMs?: number): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetcher()
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
        setData(null);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  useEffect(() => {
    if (!pollMs) return;
    let cancelled = false;
    const id = setInterval(() => {
      fetcher()
        .then((d) => {
          if (!cancelled) setData(d);
        })
        .catch(() => {
        });
    }, pollMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, pollMs]);

  return { data, loading, error, reload };
}
