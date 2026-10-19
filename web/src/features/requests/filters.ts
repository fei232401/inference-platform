import type { RequestListQuery } from "../../api/types";

export type RequestFilters = {
  status_value: string;
  backend_id: string;
  api_key_id: string;
  model_name: string;
  session_id: string;
  failures_only: boolean;
  started_after: string;
  started_before: string;
};

export const EMPTY_REQUEST_FILTERS: RequestFilters = {
  status_value: "",
  backend_id: "",
  api_key_id: "",
  model_name: "",
  session_id: "",
  failures_only: false,
  started_after: "",
  started_before: "",
};

function optionalText(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function toRequestQuery(filters: RequestFilters): RequestListQuery {
  return {
    status_value: filters.status_value || undefined,
    backend_id: filters.backend_id ? Number(filters.backend_id) : undefined,
    api_key_id: filters.api_key_id ? Number(filters.api_key_id) : undefined,
    model_name: optionalText(filters.model_name),
    session_id: optionalText(filters.session_id),
    failures_only: filters.failures_only ? true : undefined,
    started_after: filters.started_after
      ? new Date(filters.started_after).toISOString()
      : undefined,
    started_before: filters.started_before
      ? new Date(filters.started_before).toISOString()
      : undefined,
  };
}
