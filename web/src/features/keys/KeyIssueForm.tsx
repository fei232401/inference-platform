import { useState } from "react";

import { api } from "../../api/endpoints";
import type { ApiKeyCreate, ApiKeyCreatedOut } from "../../api/types";
import { Field } from "../../components/Field";
import { useAsyncAction } from "../../hooks/useAsyncAction";
import { SCOPE_VALUES } from "../../lib/format";

type Draft = {
  name: string;
  scopes: string[];
  rate_limit_per_second: string;
  ttl_days: string;
  expires_at: string;
};

const EMPTY_DRAFT: Draft = {
  name: "",
  scopes: ["infer"],
  rate_limit_per_second: "",
  ttl_days: "",
  expires_at: "",
};

export function KeyIssueForm({ onIssued }: { onIssued: (issued: ApiKeyCreatedOut) => void }) {
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const create = useAsyncAction(api.keys.create);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ttlProvided = draft.ttl_days.length > 0;
    const payload: ApiKeyCreate = {
      name: draft.name.trim(),
      scopes: draft.scopes,
      rate_limit_per_second:
        draft.rate_limit_per_second.length > 0 ? Number(draft.rate_limit_per_second) : null,
      ttl_days: ttlProvided ? Number(draft.ttl_days) : null,
      expires_at:
        !ttlProvided && draft.expires_at.length > 0
          ? new Date(draft.expires_at).toISOString()
          : null,
    };
    const created = await create.run(payload);
    if (created === null) return;
    setDraft({ ...EMPTY_DRAFT, scopes: draft.scopes });
    onIssued(created);
  }

  return (
    <form className="stack" onSubmit={handleSubmit}>
      <Field label="名称" hint="给人看的用途标记，例如 ci-pipeline">
        <input
          className="field__input"
          required
          value={draft.name}
          onChange={(event) => setDraft({ ...draft, name: event.target.value })}
        />
      </Field>
      <Field label="权限范围" hint="infer 只能推理，admin 可管理资源">
        <span className="row">
          {SCOPE_VALUES.map((scope) => (
            <label className="row" key={scope}>
              <input
                type="checkbox"
                checked={draft.scopes.includes(scope)}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    scopes: event.target.checked
                      ? [...draft.scopes, scope]
                      : draft.scopes.filter((value) => value !== scope),
                  })
                }
              />
              <span>{scope}</span>
            </label>
          ))}
        </span>
      </Field>
      <div className="grid grid--3">
        <Field label="每秒限速" hint="留空为不限">
          <input
            className="field__input"
            type="number"
            step="0.1"
            min="0.1"
            value={draft.rate_limit_per_second}
            onChange={(event) => setDraft({ ...draft, rate_limit_per_second: event.target.value })}
          />
        </Field>
        <Field label="有效天数" hint="填了它，过期时间会被忽略">
          <input
            className="field__input"
            type="number"
            min="1"
            value={draft.ttl_days}
            onChange={(event) => setDraft({ ...draft, ttl_days: event.target.value })}
          />
        </Field>
        <Field label="指定过期时间">
          <input
            className="field__input"
            type="datetime-local"
            disabled={draft.ttl_days.length > 0}
            value={draft.expires_at}
            onChange={(event) => setDraft({ ...draft, expires_at: event.target.value })}
          />
        </Field>
      </div>
      <div>
        <button type="submit" className="btn btn--primary" disabled={create.pending}>
          {create.pending ? "签发中" : "签发密钥"}
        </button>
      </div>
      {create.error ? (
        <div className="error-box">
          <span className="error-box__title">签发失败 · {create.error.code}</span>
          <span>{create.error.message}</span>
        </div>
      ) : null}
    </form>
  );
}
