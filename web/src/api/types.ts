import type { components } from "./schema";

type Schemas = components["schemas"];

export type ModelOut = Schemas["ModelOut"];
export type ModelCreate = Schemas["ModelCreate"];

export type BackendOut = Schemas["BackendOut"];
export type BackendCreate = Schemas["BackendCreate"];
export type BackendUpdate = Schemas["BackendUpdate"];
export type BackendStateChange = Schemas["BackendStateChange"];

export type HealthCheckOut = Schemas["HealthCheckOut"];
export type HealthCheckCreate = Schemas["HealthCheckCreate"];

export type ModelIdsPayload = Schemas["ModelIdsPayload"];

export type CandidateOut = Schemas["CandidateOut"];
export type CandidateListOut = Schemas["CandidateListOut"];

export type ApiKeyOut = Schemas["ApiKeyOut"];
export type ApiKeyCreatedOut = Schemas["ApiKeyCreatedOut"];
export type ApiKeyCreate = Schemas["ApiKeyCreate"];
export type ApiKeyVerifyOut = Schemas["ApiKeyVerifyOut"];

export type RequestLogOut = Schemas["RequestLogOut"];
export type RequestLogDetailOut = Schemas["RequestLogDetailOut"];
export type RequestLogIn = Schemas["RequestLogIn"];
export type RoutingDecisionOut = Schemas["RoutingDecisionOut"];
export type RoutingDecisionIn = Schemas["RoutingDecisionIn"];

export type SummaryOut = Schemas["SummaryOut"];
export type BackendStatOut = Schemas["BackendStatOut"];
export type StatusStatOut = Schemas["StatusStatOut"];
export type LatencyStatOut = Schemas["LatencyStatOut"];

export type ReadyOut = Schemas["ReadyOut"];
export type PoolStatusOut = Schemas["PoolStatusOut"];

export type PurgeIn = Schemas["PurgeIn"];
export type PurgeOut = Schemas["PurgeOut"];

export type PageMeta = {
  limit: number;
  offset: number;
  total: number;
  count: number;
  has_more: boolean;
};

export type Page<T> = {
  items: T[];
  meta: PageMeta;
};

export type BindResult = {
  backend_id: number;
  inserted?: number;
  removed?: number;
  model_ids: number[];
};

export type BulkRegisterResult = {
  submitted: number;
  inserted: number;
  skipped: number;
};

export type HealthzOut = {
  status: string;
};

export type PageQuery = {
  limit?: number;
  offset?: number;
};

export type BackendListQuery = PageQuery & {
  state?: string;
  engine?: string;
  name_like?: string;
  with_models?: boolean;
};

export type ModelListQuery = PageQuery & {
  family?: string;
  name_like?: string;
};

export type KeyListQuery = PageQuery & {
  active_only?: boolean;
  name_like?: string;
};

export type RequestListQuery = PageQuery & {
  backend_id?: number;
  api_key_id?: number;
  status_value?: string;
  model_name?: string;
  session_id?: string;
  started_after?: string;
  started_before?: string;
  failures_only?: boolean;
};

export type SummaryQuery = {
  started_after?: string;
  started_before?: string;
  backend_id?: number;
};

export type CandidateQuery = {
  model_name: string;
  policy: string;
};

export type RoutingPolicy = "weighted_random" | "least_latency" | "least_inflight" | "round_robin" | "session_sticky" | "prefix_affinity";

export const ROUTING_POLICIES: readonly RoutingPolicy[] = [
  "weighted_random",
  "least_latency",
  "least_inflight",
  "prefix_affinity",
];

export type RequestStatusValue = "success" | "error" | "timeout" | "rejected";

export const REQUEST_STATUS_VALUES: readonly RequestStatusValue[] = [
  "success",
  "error",
  "timeout",
  "rejected",
];

export type BackendStateValue = "active" | "draining" | "disabled";

export const BACKEND_STATE_VALUES: readonly BackendStateValue[] = [
  "active",
  "draining",
  "disabled",
];

export type RouteIn = {
  model_name: string;
  prompt: string;
  policy?: string;
  max_tokens?: number;
  engine_models?: Record<string, string>;
};

export type RouteBackendOut = {
  id: number;
  name: string;
  engine: string;
  url: string;
};

export type RouteDecisionOut = {
  policy: string;
  candidate_ids: number[];
  chosen_id: number | null;
  score_snapshot: {
    ranked: (CandidateOut & { inflight?: number; max_inflight?: number; capacity_excluded?: boolean })[];
    admission?: {
      scope: string;
      selection: string;
      selected_inflight_before: number;
      selected_limit: number;
    };
  };
  fallback_reason: string | null;
};

export type RouteOut = {
  request_id: string | null;
  recorded: boolean;
  backend: RouteBackendOut;
  decision: RouteDecisionOut;
  output: string;
  usage: { prompt_tokens: number | null; completion_tokens: number | null };
  timings: { total_ms: number; engine_model: string };
};
