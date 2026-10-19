const STORAGE_KEY = "ai-infra.api-key";

const listeners = new Set<() => void>();

let current: string | null = null;

function storage(): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function load(): string {
  if (current !== null) return current;
  const store = storage();
  if (!store) {
    current = "";
    return current;
  }
  try {
    current = store.getItem(STORAGE_KEY) ?? "";
  } catch {
    current = "";
  }
  return current;
}

export function getApiKey(): string {
  return load();
}

export function setApiKey(value: string): void {
  const next = value.trim();
  current = next;
  const store = storage();
  if (store) {
    try {
      if (next.length > 0) store.setItem(STORAGE_KEY, next);
      else store.removeItem(STORAGE_KEY);
    } catch {
      void 0;
    }
  }
  for (const listener of listeners) listener();
}

export function clearApiKey(): void {
  setApiKey("");
}

export function subscribeApiKey(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function maskApiKey(key: string): string {
  if (key.length <= 12) return key;
  return `${key.slice(0, 8)}…${key.slice(-4)}`;
}
