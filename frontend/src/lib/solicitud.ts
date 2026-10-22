import { useCallback, useEffect, useRef } from "react";

/**
 * Returns a function that starts a new request "slot": it aborts the previous
 * controller (so the newest call always wins) and aborts the last one on unmount.
 */
export function useSolicitudVigente(): () => AbortController {
  const ref = useRef<AbortController | null>(null);
  useEffect(() => () => ref.current?.abort(), []);
  return useCallback(() => {
    ref.current?.abort();
    const ctrl = new AbortController();
    ref.current = ctrl;
    return ctrl;
  }, []);
}
