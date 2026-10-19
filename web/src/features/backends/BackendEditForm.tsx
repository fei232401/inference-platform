import { useState } from "react";

import { api } from "../../api/endpoints";
import type { BackendOut, BackendUpdate } from "../../api/types";
import { Field } from "../../components/Field";
import { useAsyncAction } from "../../hooks/useAsyncAction";

type Draft = {
  url: string;
  weight: string;
  max_concurrency: string;
  cost_per_token: string;
};

export type BackendEditFormProps = {
  backend: BackendOut;
  onSaved: () => void;
};

export function BackendEditForm({ backend, onSaved }: BackendEditFormProps) {
  const [edits, setEdits] = useState<Partial<Draft>>({});
  const update = useAsyncAction(api.backends.update);

  const draft: Draft = {
    url: edits.url ?? backend.url,
    weight: edits.weight ?? String(backend.weight),
    max_concurrency: edits.max_concurrency ?? String(backend.max_concurrency),
    cost_per_token: edits.cost_per_token ?? String(backend.cost_per_token),
  };

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: BackendUpdate = {
      url: draft.url.trim(),
      weight: draft.weight,
      max_concurrency: Number(draft.max_concurrency),
      cost_per_token: draft.cost_per_token,
    };
    const updated = await update.run(backend.id, payload);
    if (updated === null) return;
    setEdits({});
    onSaved();
  }

  return (
    <form className="stack" onSubmit={handleSubmit}>
      <Field label="地址">
        <input
          className="field__input"
          value={draft.url}
          onChange={(event) => setEdits({ ...edits, url: event.target.value })}
        />
      </Field>
      <div className="grid grid--3">
        <Field label="权重">
          <input
            className="field__input"
            type="number"
            step="0.1"
            min="0"
            value={draft.weight}
            onChange={(event) => setEdits({ ...edits, weight: event.target.value })}
          />
        </Field>
        <Field label="最大并发">
          <input
            className="field__input"
            type="number"
            min="1"
            value={draft.max_concurrency}
            onChange={(event) => setEdits({ ...edits, max_concurrency: event.target.value })}
          />
        </Field>
        <Field label="每 token 单价">
          <input
            className="field__input"
            type="number"
            step="0.0000001"
            min="0"
            value={draft.cost_per_token}
            onChange={(event) => setEdits({ ...edits, cost_per_token: event.target.value })}
          />
        </Field>
      </div>
      <div className="row">
        <button type="submit" className="btn btn--primary" disabled={update.pending}>
          {update.pending ? "保存中" : "保存"}
        </button>
        <button type="button" className="btn" onClick={() => setEdits({})}>
          还原
        </button>
      </div>
      {update.error ? (
        <div className="error-box">
          <span className="error-box__title">保存失败 · {update.error.code}</span>
          <span>{update.error.message}</span>
        </div>
      ) : null}
    </form>
  );
}
