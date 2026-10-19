import { request } from "./client";
import type {
  ApiKeyCreate,
  ApiKeyCreatedOut,
  ApiKeyOut,
  ApiKeyVerifyOut,
  BackendCreate,
  BackendListQuery,
  BackendOut,
  BackendStateChange,
  BackendUpdate,
  BindResult,
  BulkRegisterResult,
  CandidateListOut,
  CandidateQuery,
  HealthCheckCreate,
  HealthCheckOut,
  HealthzOut,
  KeyListQuery,
  ModelCreate,
  ModelListQuery,
  ModelOut,
  Page,
  PurgeIn,
  PurgeOut,
  ReadyOut,
  RequestListQuery,
  RequestLogDetailOut,
  RequestLogIn,
  RequestLogOut,
  RouteIn,
  RouteOut,
  SummaryOut,
  SummaryQuery,
} from "./types";

type Signal = AbortSignal | undefined;

export const api = {
  healthz: (signal?: Signal) => request<HealthzOut>("/healthz", { signal }),
  readyz: (signal?: Signal) => request<ReadyOut>("/readyz", { signal }),

  models: {
    list: (query: ModelListQuery, signal?: Signal) =>
      request<Page<ModelOut>>("/api/v1/models", { query, signal }),
    names: (signal?: Signal) => request<string[]>("/api/v1/models/names", { signal }),
    families: (signal?: Signal) => request<string[]>("/api/v1/models/families", { signal }),
    detail: (modelId: number, signal?: Signal) =>
      request<ModelOut>(`/api/v1/models/${modelId}`, { signal }),
    create: (body: ModelCreate) =>
      request<ModelOut>("/api/v1/models", { method: "POST", body }),
    upsert: (body: ModelCreate) =>
      request<ModelOut>("/api/v1/models/upsert", { method: "POST", body }),
  },

  backends: {
    list: (query: BackendListQuery, signal?: Signal) =>
      request<Page<BackendOut>>("/api/v1/backends", { query, signal }),
    detail: (backendId: number, withModels = false, signal?: Signal) =>
      request<BackendOut>(`/api/v1/backends/${backendId}`, {
        query: { with_models: withModels },
        signal,
      }),
    create: (body: BackendCreate) =>
      request<BackendOut>("/api/v1/backends", { method: "POST", body }),
    bulkCreate: (items: BackendCreate[]) =>
      request<BulkRegisterResult>("/api/v1/backends/bulk", {
        method: "POST",
        body: { items },
      }),
    update: (backendId: number, body: BackendUpdate) =>
      request<BackendOut>(`/api/v1/backends/${backendId}`, { method: "PATCH", body }),
    changeState: (backendId: number, state: string) =>
      request<BackendOut>(`/api/v1/backends/${backendId}/state`, {
        method: "POST",
        body: { state } satisfies BackendStateChange,
      }),
    disable: (backendId: number) =>
      request<BackendOut>(`/api/v1/backends/${backendId}`, { method: "DELETE" }),
    models: (backendId: number, signal?: Signal) =>
      request<ModelOut[]>(`/api/v1/backends/${backendId}/models`, { signal }),
    bindModels: (backendId: number, modelIds: number[]) =>
      request<BindResult>(`/api/v1/backends/${backendId}/models`, {
        method: "POST",
        body: { model_ids: modelIds },
      }),
    replaceModels: (backendId: number, modelIds: number[]) =>
      request<BindResult>(`/api/v1/backends/${backendId}/models`, {
        method: "PUT",
        body: { model_ids: modelIds },
      }),
    unbindModels: (backendId: number, modelIds: number[]) =>
      request<BindResult>(`/api/v1/backends/${backendId}/models`, {
        method: "DELETE",
        body: { model_ids: modelIds },
      }),
    healthHistory: (backendId: number, limit = 20, signal?: Signal) =>
      request<HealthCheckOut[]>(`/api/v1/backends/${backendId}/health`, {
        query: { limit },
        signal,
      }),
    recordHealth: (backendId: number, body: HealthCheckCreate) =>
      request<HealthCheckOut>(`/api/v1/backends/${backendId}/health`, {
        method: "POST",
        body,
      }),
  },

  routing: {
    candidates: (query: CandidateQuery, signal?: Signal) =>
      request<CandidateListOut>("/api/v1/routing/candidates", { query, signal }),
  },

  requests: {
    list: (query: RequestListQuery, signal?: Signal) =>
      request<Page<RequestLogOut>>("/api/v1/requests", { query, signal }),
    detail: (requestId: string, signal?: Signal) =>
      request<RequestLogDetailOut>(`/api/v1/requests/${requestId}`, { signal }),
    record: (body: RequestLogIn) =>
      request<RequestLogDetailOut>("/api/v1/requests", { method: "POST", body }),
    summary: (query: SummaryQuery, signal?: Signal) =>
      request<SummaryOut>("/api/v1/requests/summary", { query, signal }),
    purge: (body: PurgeIn) =>
      request<PurgeOut>("/api/v1/requests/purge", { method: "POST", body }),
  },

  keys: {
    list: (query: KeyListQuery, signal?: Signal) =>
      request<Page<ApiKeyOut>>("/api/v1/keys", { query, signal }),
    create: (body: ApiKeyCreate) =>
      request<ApiKeyCreatedOut>("/api/v1/keys", { method: "POST", body }),
    verify: (key: string, scope = "infer") =>
      request<ApiKeyVerifyOut>("/api/v1/keys/verify", {
        method: "POST",
        query: { scope },
        body: { key },
      }),
    detail: (keyId: number, signal?: Signal) =>
      request<ApiKeyOut>(`/api/v1/keys/${keyId}`, { signal }),
    revoke: (keyId: number) =>
      request<ApiKeyOut>(`/api/v1/keys/${keyId}/revoke`, { method: "POST" }),
  },

  inference: {
    route: (body: RouteIn) => request<RouteOut>("/v1/route", { method: "POST", body, timeoutMs: 300000 }),
  },
};

export type ApiClient = typeof api;
