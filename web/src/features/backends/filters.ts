import type { BackendListQuery } from "../../api/types";

export type BackendFilters = {
  state: string;
  engine: string;
  name_like: string;
  with_models: boolean;
};

export const EMPTY_BACKEND_FILTERS: BackendFilters = {
  state: "",
  engine: "",
  name_like: "",
  with_models: false,
};

export function toBackendQuery(filters: BackendFilters): BackendListQuery {
  return {
    state: filters.state || undefined,
    engine: filters.engine || undefined,
    name_like: filters.name_like.trim() || undefined,
    with_models: filters.with_models ? true : undefined,
  };
}
