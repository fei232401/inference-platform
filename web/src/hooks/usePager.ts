import { useCallback, useState } from "react";

export type Pager = {
  limit: number;
  offset: number;
  next: () => void;
  prev: () => void;
  reset: () => void;
};

export function usePager(limit = 20): Pager {
  const [offset, setOffset] = useState(0);

  const next = useCallback(() => setOffset((current) => current + limit), [limit]);
  const prev = useCallback(() => setOffset((current) => Math.max(0, current - limit)), [limit]);
  const reset = useCallback(() => setOffset(0), []);

  return { limit, offset, next, prev, reset };
}
