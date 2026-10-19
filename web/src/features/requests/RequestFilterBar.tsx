import { useState } from "react";

import type { RequestListQuery } from "../../api/types";
import { REQUEST_STATUS_VALUES } from "../../api/types";
import { Field } from "../../components/Field";
import { requestStatusLabel } from "../../lib/format";
import { EMPTY_REQUEST_FILTERS, toRequestQuery } from "./filters";
import type { RequestFilters } from "./filters";

export function RequestFilterBar({ onApply }: { onApply: (query: RequestListQuery) => void }) {
  const [draft, setDraft] = useState<RequestFilters>(EMPTY_REQUEST_FILTERS);

  function setFilter<K extends keyof RequestFilters>(key: K, value: RequestFilters[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  return (
    <form
      className="toolbar"
      onSubmit={(event) => {
        event.preventDefault();
        onApply(toRequestQuery(draft));
      }}
    >
      <Field label="状态">
        <select
          className="field__select"
          value={draft.status_value}
          onChange={(event) => setFilter("status_value", event.target.value)}
        >
          <option value="">全部</option>
          {REQUEST_STATUS_VALUES.map((value) => (
            <option key={value} value={value}>
              {requestStatusLabel(value)}
            </option>
          ))}
        </select>
      </Field>
      <Field label="后端 ID">
        <input
          className="field__input"
          type="number"
          min="1"
          value={draft.backend_id}
          onChange={(event) => setFilter("backend_id", event.target.value)}
        />
      </Field>
      <Field label="密钥 ID">
        <input
          className="field__input"
          type="number"
          min="1"
          value={draft.api_key_id}
          onChange={(event) => setFilter("api_key_id", event.target.value)}
        />
      </Field>
      <Field label="模型名" hint="精确匹配">
        <input
          className="field__input"
          value={draft.model_name}
          onChange={(event) => setFilter("model_name", event.target.value)}
        />
      </Field>
      <Field label="会话 ID" hint="用于排查粘滞是否生效">
        <input
          className="field__input"
          value={draft.session_id}
          onChange={(event) => setFilter("session_id", event.target.value)}
        />
      </Field>
      <Field label="只看失败">
        <select
          className="field__select"
          value={draft.failures_only ? "yes" : "no"}
          onChange={(event) => setFilter("failures_only", event.target.value === "yes")}
        >
          <option value="no">全部</option>
          <option value="yes">仅失败 / 超时 / 被拒</option>
        </select>
      </Field>
      <Field label="起始不早于">
        <input
          className="field__input"
          type="datetime-local"
          value={draft.started_after}
          onChange={(event) => setFilter("started_after", event.target.value)}
        />
      </Field>
      <Field label="起始不晚于">
        <input
          className="field__input"
          type="datetime-local"
          value={draft.started_before}
          onChange={(event) => setFilter("started_before", event.target.value)}
        />
      </Field>
      <button type="submit" className="btn btn--primary">
        查询
      </button>
      <button
        type="button"
        className="btn"
        onClick={() => {
          setDraft(EMPTY_REQUEST_FILTERS);
          onApply({});
        }}
      >
        重置
      </button>
    </form>
  );
}
