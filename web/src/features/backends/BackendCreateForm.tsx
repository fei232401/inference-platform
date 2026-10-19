import { useState } from "react";

import { api } from "../../api/endpoints";
import type { BackendCreate } from "../../api/types";
import { Field } from "../../components/Field";
import { useAsyncAction } from "../../hooks/useAsyncAction";
import { ENGINE_VALUES, engineLabel } from "../../lib/format";

type Draft = {
  name: string;
  url: string;
  engine: string;
  weight: string;
  max_concurrency: string;
  cost_per_token: string;
};

const EMPTY_DRAFT: Draft = {
  name: "",
  url: "",
  engine: "ollama",
  weight: "1",
  max_concurrency: "1",
  cost_per_token: "0",
};

export function BackendCreateForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState<Draft>(EMPTY_DRAFT);
  const create = useAsyncAction(api.backends.create);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: BackendCreate = {
      name: form.name.trim(),
      url: form.url.trim(),
      engine: form.engine,
      weight: form.weight,
      max_concurrency: Number(form.max_concurrency),
      cost_per_token: form.cost_per_token,
    };
    const created = await create.run(payload);
    if (created === null) return;
    setForm({ ...EMPTY_DRAFT, engine: form.engine });
    onCreated();
  }

  return (
    <form className="stack" onSubmit={handleSubmit}>
      <Field label="名称" hint="全局唯一，重复会返回 409">
        <input
          className="field__input"
          required
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
        />
      </Field>
      <Field label="地址" hint="Ollama 默认 11434，OpenAI 兼容一般 8000">
        <input
          className="field__input"
          required
          value={form.url}
          placeholder="http://127.0.0.1:11434"
          onChange={(event) => setForm({ ...form, url: event.target.value })}
        />
      </Field>
      <Field label="引擎">
        <select
          className="field__select"
          value={form.engine}
          onChange={(event) => setForm({ ...form, engine: event.target.value })}
        >
          {ENGINE_VALUES.map((value) => (
            <option key={value} value={value}>
              {engineLabel(value)}
            </option>
          ))}
        </select>
      </Field>
      <div className="grid grid--3">
        <Field label="权重" hint="打分公式的比例因子">
          <input
            className="field__input"
            type="number"
            step="0.1"
            min="0"
            value={form.weight}
            onChange={(event) => setForm({ ...form, weight: event.target.value })}
          />
        </Field>
        <Field label="最大并发">
          <input
            className="field__input"
            type="number"
            min="1"
            value={form.max_concurrency}
            onChange={(event) => setForm({ ...form, max_concurrency: event.target.value })}
          />
        </Field>
        <Field label="每 token 单价" hint="本地部署填 0">
          <input
            className="field__input"
            type="number"
            step="0.0000001"
            min="0"
            value={form.cost_per_token}
            onChange={(event) => setForm({ ...form, cost_per_token: event.target.value })}
          />
        </Field>
      </div>
      <div>
        <button type="submit" className="btn btn--primary" disabled={create.pending}>
          {create.pending ? "提交中" : "登记实例"}
        </button>
      </div>
      {create.error ? (
        <div className="error-box">
          <span className="error-box__title">
            登记失败 · {create.error.code}
            {create.error.status > 0 ? ` · HTTP ${create.error.status}` : ""}
          </span>
          <span>{create.error.message}</span>
        </div>
      ) : null}
    </form>
  );
}
