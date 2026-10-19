import { useState } from "react";

import { api } from "../../api/endpoints";
import { Field } from "../../components/Field";
import { useAsyncAction } from "../../hooks/useAsyncAction";

type Draft = {
  healthy: string;
  latency_ms: string;
  error: string;
  checked_at: string;
};

const EMPTY_DRAFT: Draft = { healthy: "true", latency_ms: "", error: "", checked_at: "" };

export type BackendHealthFormProps = {
  backendId: number;
  onRecorded: (recordId: number) => void;
};

export function BackendHealthForm({ backendId, onRecorded }: BackendHealthFormProps) {
  const [form, setForm] = useState<Draft>(EMPTY_DRAFT);
  const recordHealth = useAsyncAction(api.backends.recordHealth);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const created = await recordHealth.run(backendId, {
      healthy: form.healthy === "true",
      latency_ms: form.latency_ms.length > 0 ? Number(form.latency_ms) : null,
      error: form.error.length > 0 ? form.error : null,
      checked_at: form.checked_at.length > 0 ? new Date(form.checked_at).toISOString() : null,
    });
    if (created === null) return;
    setForm(EMPTY_DRAFT);
    onRecorded(created.id);
  }

  return (
    <form className="stack" onSubmit={handleSubmit}>
      <Field label="探测结果" hint="失败会让打分因子归零并被排除出候选集">
        <select
          className="field__select"
          value={form.healthy}
          onChange={(event) => setForm({ ...form, healthy: event.target.value })}
        >
          <option value="true">通过</option>
          <option value="false">失败</option>
        </select>
      </Field>
      <Field label="探测延迟（毫秒）" hint="留空表示没测延迟，因子按 0.5 计">
        <input
          className="field__input"
          type="number"
          min="0"
          value={form.latency_ms}
          onChange={(event) => setForm({ ...form, latency_ms: event.target.value })}
        />
      </Field>
      <Field label="错误信息" hint="失败时才有值">
        <input
          className="field__input"
          value={form.error}
          onChange={(event) => setForm({ ...form, error: event.target.value })}
        />
      </Field>
      <Field label="探测时间" hint="留空则由数据库取当前时间">
        <input
          className="field__input"
          type="datetime-local"
          value={form.checked_at}
          onChange={(event) => setForm({ ...form, checked_at: event.target.value })}
        />
      </Field>
      <div>
        <button type="submit" className="btn btn--primary" disabled={recordHealth.pending}>
          {recordHealth.pending ? "上报中" : "上报"}
        </button>
      </div>
      {recordHealth.error ? (
        <div className="error-box">
          <span className="error-box__title">上报失败 · {recordHealth.error.code}</span>
          <span>{recordHealth.error.message}</span>
        </div>
      ) : null}
    </form>
  );
}
