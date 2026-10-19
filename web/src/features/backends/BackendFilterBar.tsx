import { useState } from "react";

import { BACKEND_STATE_VALUES } from "../../api/types";
import { Field } from "../../components/Field";
import { ENGINE_VALUES, backendStateLabel, engineLabel } from "../../lib/format";
import { EMPTY_BACKEND_FILTERS } from "./filters";
import type { BackendFilters } from "./filters";

export type BackendFiltersProps = {
  onApply: (filters: BackendFilters) => void;
};

export function BackendFilterBar({ onApply }: BackendFiltersProps) {
  const [draft, setDraft] = useState<BackendFilters>(EMPTY_BACKEND_FILTERS);

  function setFilter<K extends keyof BackendFilters>(key: K, value: BackendFilters[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  return (
    <form
      className="toolbar"
      onSubmit={(event) => {
        event.preventDefault();
        onApply(draft);
      }}
    >
      <Field label="状态">
        <select
          className="field__select"
          value={draft.state}
          onChange={(event) => setFilter("state", event.target.value)}
        >
          <option value="">全部</option>
          {BACKEND_STATE_VALUES.map((value) => (
            <option key={value} value={value}>
              {backendStateLabel(value)}
            </option>
          ))}
        </select>
      </Field>
      <Field label="引擎">
        <select
          className="field__select"
          value={draft.engine}
          onChange={(event) => setFilter("engine", event.target.value)}
        >
          <option value="">全部</option>
          {ENGINE_VALUES.map((value) => (
            <option key={value} value={value}>
              {engineLabel(value)}
            </option>
          ))}
        </select>
      </Field>
      <Field label="名称包含" hint="走 ILIKE 模糊匹配">
        <input
          className="field__input"
          value={draft.name_like}
          placeholder="例如 ollama"
          onChange={(event) => setFilter("name_like", event.target.value)}
        />
      </Field>
      <Field label="附带模型" hint="打开后列表直接带出绑定关系">
        <select
          className="field__select"
          value={draft.with_models ? "yes" : "no"}
          onChange={(event) => setFilter("with_models", event.target.value === "yes")}
        >
          <option value="no">不附带</option>
          <option value="yes">附带</option>
        </select>
      </Field>
      <button type="submit" className="btn btn--primary">
        查询
      </button>
      <button
        type="button"
        className="btn"
        onClick={() => {
          setDraft(EMPTY_BACKEND_FILTERS);
          onApply(EMPTY_BACKEND_FILTERS);
        }}
      >
        重置
      </button>
    </form>
  );
}
