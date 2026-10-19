import { getApiKey } from "./apiKey";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const DEFAULT_TIMEOUT_MS = 15000;

export type ApiErrorPayload = {
  code: string;
  message: string;
  detail: Record<string, unknown>;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: Record<string, unknown>;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.name = "ApiError";
    this.status = status;
    this.code = payload.code;
    this.detail = payload.detail;
  }

  get isOffline(): boolean {
    return this.status === 0;
  }
}

export type QueryValue = string | number | boolean | null | undefined;

export type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Record<string, QueryValue>;
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
};

export function buildQuery(query?: Record<string, QueryValue>): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const serialized = params.toString();
  return serialized.length > 0 ? `?${serialized}` : "";
}

function normalizeError(payload: unknown, fallback: string): ApiErrorPayload {
  if (typeof payload === "object" && payload !== null) {
    const candidate = payload as Partial<ApiErrorPayload>;
    if (typeof candidate.code === "string" && typeof candidate.message === "string") {
      return {
        code: candidate.code,
        message: candidate.message,
        detail: candidate.detail ?? {},
      };
    }
    if (typeof candidate.detail === "object" && candidate.detail !== null) {
      return normalizeError(candidate.detail, fallback);
    }
  }
  return { code: "unexpected_response", message: fallback || "响应格式无法识别", detail: {} };
}

function parseBody(text: string): unknown {
  if (text.length === 0) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { code: "invalid_json", message: text.slice(0, 200), detail: {} };
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", query, body, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = options;

  const controller = new AbortController();
  const timer = window.setTimeout(() => {
    controller.abort(new DOMException("timeout", "TimeoutError"));
  }, timeoutMs);
  const forwardAbort = () => controller.abort(signal?.reason);
  signal?.addEventListener("abort", forwardAbort);

  try {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const apiKey = getApiKey();
    if (apiKey.length > 0) headers["X-API-Key"] = apiKey;

    const response = await fetch(`${BASE_URL}${path}${buildQuery(query)}`, {
      method,
      headers: Object.keys(headers).length > 0 ? headers : undefined,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });

    const text = await response.text();

    if (!response.ok) {
      throw new ApiError(response.status, normalizeError(parseBody(text), response.statusText));
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return parseBody(text) as T;
  } catch (cause) {
    if (cause instanceof ApiError) throw cause;
    if (cause instanceof DOMException && cause.name === "TimeoutError") {
      throw new ApiError(0, {
        code: "timeout",
        message: `请求超时（${timeoutMs}ms）`,
        detail: { path, timeoutMs },
      });
    }
    if (cause instanceof DOMException && cause.name === "AbortError") {
      throw new ApiError(0, { code: "aborted", message: "请求已取消", detail: { path } });
    }
    throw new ApiError(0, {
      code: "network_error",
      message: "无法连接到控制层，确认后端已启动且地址正确",
      detail: { path },
    });
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }
}
