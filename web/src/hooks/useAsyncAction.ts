import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";

export type AsyncAction<Args extends readonly unknown[], Result> = {
  run: (...args: Args) => Promise<Result | null>;
  pending: boolean;
  error: ApiError | null;
  reset: () => void;
};

function toApiError(cause: unknown): ApiError {
  if (cause instanceof ApiError) return cause;
  return new ApiError(0, {
    code: "unknown",
    message: cause instanceof Error ? cause.message : String(cause),
    detail: {},
  });
}

export function useAsyncAction<Args extends readonly unknown[], Result>(
  action: (...args: Args) => Promise<Result>,
): AsyncAction<Args, Result> {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const actionRef = useRef(action);
  actionRef.current = action;

  const reset = useCallback(() => setError(null), []);

  const run = useCallback(async (...args: Args): Promise<Result | null> => {
    setPending(true);
    setError(null);
    try {
      return await actionRef.current(...args);
    } catch (cause) {
      if (mounted.current) setError(toApiError(cause));
      return null;
    } finally {
      if (mounted.current) setPending(false);
    }
  }, []);

  return { run, pending, error, reset };
}
