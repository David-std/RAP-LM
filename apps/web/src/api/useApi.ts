import { useEffect, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

/**
 * Run ``load`` whenever ``deps`` change. The previous request is aborted, so a
 * slow response for an old period can never overwrite a newer one.
 * Pass ``enabled=false`` to skip the call (e.g. nothing selected yet).
 */
export function useApi<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: unknown[],
  enabled = true,
): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: enabled });

  useEffect(() => {
    if (!enabled) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    const controller = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    load(controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error: Error) => {
        if (error.name === "AbortError") return;
        setState({ data: null, error, loading: false });
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled]);

  return state;
}
