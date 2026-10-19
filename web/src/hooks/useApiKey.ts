import { useSyncExternalStore } from "react";

import { getApiKey, subscribeApiKey } from "../api/apiKey";

export function useApiKey(): string {
  return useSyncExternalStore(subscribeApiKey, getApiKey, getApiKey);
}
